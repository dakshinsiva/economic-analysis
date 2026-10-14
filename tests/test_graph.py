"""Graph tests with a scripted fake chat model: no API key, no network.

This is the pattern for unit-testing any LangGraph agent: replace the model
with something deterministic, then assert on the *trajectory* (which tools
were called with what) rather than on prose.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from macrodesk import graph as graph_mod


class ScriptedModel(GenericFakeChatModel):
    """Returns pre-canned AIMessages in order; ignores the prompt."""

    def bind_tools(self, tools: Any, **kwargs: Any):  # create_agent calls this
        return self


def scripted(*msgs: AIMessage) -> ScriptedModel:
    return ScriptedModel(messages=iter(msgs))


def test_graph_topology():
    g = graph_mod.graph
    assert set(g.get_graph().nodes) >= {"model", "tools"}


def test_agent_calls_tool_then_answers(monkeypatch, fake_fred):
    script = scripted(
        AIMessage(content="", tool_calls=[{"name": "get_series", "args": {"series_id": "JTSQUR", "last_n": 2}, "id": "c1"}]),
        AIMessage(content="Quits rate is 1.9% (JTSQUR, 2026-08-01)."),
    )
    monkeypatch.setattr(graph_mod, "make_model", lambda: script)
    g = graph_mod.build_graph(checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "t1"}}
    out = g.invoke({"messages": [HumanMessage("quits?")]}, cfg)

    msgs = out["messages"]
    tool_msgs = [m for m in msgs if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1 and tool_msgs[0].name == "get_series"
    assert "JTSQUR" in tool_msgs[0].content
    assert msgs[-1].content.endswith("2026-08-01).")
    assert fake_fred.calls == [("get_series", "JTSQUR", fake_fred.calls[0][2], None)]
    # checkpointer persisted the thread
    assert len(g.get_state(cfg).values["messages"]) == 4  # human, ai(tool call), tool, ai


def test_agent_recovers_from_tool_error(monkeypatch, fake_fred):
    script = scripted(
        AIMessage(content="", tool_calls=[{"name": "get_series", "args": {"series_id": "BOGUS"}, "id": "c1"}]),
        AIMessage(content="", tool_calls=[{"name": "search_fred", "args": {"query": "quits"}, "id": "c2"}]),
        AIMessage(content="", tool_calls=[{"name": "get_series", "args": {"series_id": "JTSQUR"}, "id": "c3"}]),
        AIMessage(content="done"),
    )
    monkeypatch.setattr(graph_mod, "make_model", lambda: script)
    g = graph_mod.build_graph(checkpointer=InMemorySaver())
    out = g.invoke({"messages": [HumanMessage("quits?")]}, {"configurable": {"thread_id": "t2"}})
    tool_msgs = [m for m in out["messages"] if isinstance(m, ToolMessage)]
    assert [m.name for m in tool_msgs] == ["get_series", "search_fred", "get_series"]
    assert tool_msgs[0].content.startswith("ERROR")


def test_resuming_a_finished_thread_does_not_call_the_model(monkeypatch, fake_fred):
    """Studio 'continue' / invoke(None) on a thread whose last message is the answer: v1 must end,
    not send an assistant-terminated conversation (a prefill, rejected by Claude 4.6+)."""
    script = scripted(AIMessage(content="Done (JTSQUR, 2026-08-01)."), AIMessage(content="SHOULD NOT BE CALLED"))
    monkeypatch.setattr(graph_mod, "make_model", lambda: script)
    g = graph_mod.build_graph(checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "t3"}}
    g.invoke({"messages": [HumanMessage("quits?")]}, cfg)
    before = len(g.get_state(cfg).values["messages"])
    g.invoke(None, cfg)  # resume with no input
    after = g.get_state(cfg).values["messages"]
    assert len(after) == before and after[-1].content == "Done (JTSQUR, 2026-08-01)."
