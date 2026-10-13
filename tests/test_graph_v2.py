"""Stage 2 graph tests with scripted planner/analyst/critic. No network, no keys.

Pattern: monkeypatch the three LLM factories in nodes.py with stand-ins that
return canned structured objects, then assert on routing and state.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from macrodesk import nodes
from macrodesk.graph import build_graph_v2
from macrodesk.state import Critique, Evidence, Plan, Step


class Canned:
    def __init__(self, *outs):
        self.outs, self.calls = list(outs), []

    def invoke(self, prompt):
        self.calls.append(prompt)
        return self.outs.pop(0) if len(self.outs) > 1 else self.outs[0]

    def stream(self, prompt):  # the analyst node streams; yield the canned message as one chunk
        yield self.invoke(prompt)


PLAN = Plan(goal="quits?", steps=[Step(tool="get_series", args={"series_id": "JTSQUR", "last_n": 3}, why="latest")])
CFG = {"configurable": {"thread_id": "t"}}


def _wire(monkeypatch, planner, analyst, critic):
    monkeypatch.setattr(nodes, "planner_llm", lambda: planner)
    monkeypatch.setattr(nodes, "analyst_llm", lambda: analyst)
    monkeypatch.setattr(nodes, "critic_llm", lambda: critic)


def test_pauses_for_review_then_runs_to_end_on_approve(monkeypatch, fake_fred):
    _wire(monkeypatch, Canned(PLAN), Canned(AIMessage("Quits 1.9% (JTSQUR, 2026-08-01).")),
          Canned(Critique(approved=True)))
    g = build_graph_v2(InMemorySaver())
    out = g.invoke({"messages": [HumanMessage("quits?")]}, CFG)
    assert "__interrupt__" in out
    assert out["__interrupt__"][0].value["steps"][0]["tool"] == "get_series"
    assert g.get_state(CFG).next == ("review",)
    assert fake_fred.calls == []  # nothing fetched before approval

    out = g.invoke(Command(resume="approve"), CFG)
    assert fake_fred.calls[0][:2] == ("get_series", "JTSQUR")
    assert out["evidence"][0]["ok"] and out["critique"]["approved"]
    assert out["messages"][-1].content.startswith("Quits 1.9%")
    assert g.get_state(CFG).next == ()


def test_feedback_at_review_replans(monkeypatch, fake_fred):
    plan2 = Plan(goal="quits 5y", steps=[Step(tool="get_series", args={"series_id": "JTSQUR", "start": "2021-01-01"}, why="hist")])
    planner = Canned(PLAN, plan2)
    _wire(monkeypatch, planner, Canned(AIMessage("ok")), Canned(Critique(approved=True)))
    g = build_graph_v2(InMemorySaver())
    g.invoke({"messages": [HumanMessage("quits?")]}, CFG)
    out = g.invoke(Command(resume="use five years of history"), CFG)
    # second interrupt with the revised plan
    assert out["__interrupt__"][0].value["steps"][0]["args"]["start"] == "2021-01-01"
    assert "five years" in str(planner.calls[1][-1].content)
    g.invoke(Command(resume="approve"), CFG)
    assert fake_fred.calls[0][2] == "2021-01-01"


def test_critic_bounces_unsupported_claim_then_accepts(monkeypatch, fake_fred):
    analyst = Canned(AIMessage("Quits peaked near 3.0% in 2022 (JTSQUR, 2022-04-01)."),
                     AIMessage("Quits 1.9% (JTSQUR, 2026-08-01)."))
    critic = Canned(Critique(approved=False, issues=["'peaked near 3.0% in 2022' not in evidence"]),
                    Critique(approved=True))
    _wire(monkeypatch, Canned(PLAN), analyst, critic)
    g = build_graph_v2(InMemorySaver())
    g.invoke({"messages": [HumanMessage("quits?")]}, CFG)
    out = g.invoke(Command(resume="approve"), CFG)
    assert out["revisions"] == 2 and out["critique"]["approved"]
    assert "peaked" in str(analyst.calls[1][0].content)  # critique fed back into analyst prompt
    assert out["messages"][-1].content == "Quits 1.9% (JTSQUR, 2026-08-01)."


def test_revision_cap_finalizes_with_reviewer_note(monkeypatch, fake_fred):
    _wire(monkeypatch, Canned(PLAN), Canned(AIMessage("bad (JTSQUR, 2026-08-01)")),
          Canned(Critique(approved=False, issues=["still wrong"])))
    g = build_graph_v2(InMemorySaver())
    g.invoke({"messages": [HumanMessage("q")]}, CFG)
    out = g.invoke(Command(resume="approve"), CFG)
    assert out["revisions"] == nodes.MAX_REVISIONS
    assert "Reviewer note" in out["messages"][-1].content


def test_deterministic_citation_check():
    ev = [Evidence(tool="get_series", args={}, result="JTSQUR ... 2026-08-01  1.90", ok=True).model_dump()]
    issues = nodes._deterministic_checks("x (JTSQUR, 2026-08-01) y (UNRATE, 2026-09-01) z (JTSQUR, 2019-01-01)", ev)
    assert len(issues) == 2 and any("UNRATE" in i for i in issues) and any("2019-01-01" in i for i in issues)


def test_fetch_records_tool_errors_without_crashing(fake_fred):
    plan = Plan(goal="g", steps=[Step(tool="get_series", args={"series_id": "BOGUS"}, why="w"),
                                 Step(tool="get_series", args={"series_id": "JTSQUR"}, why="w")])
    out = nodes.fetch({"plan": plan.model_dump()})
    assert [e["ok"] for e in out["evidence"]] == [False, True]


def test_review_feedback_is_remembered_and_recalled_next_thread(monkeypatch, fake_fred):
    from langgraph.store.memory import InMemoryStore
    from macrodesk.memory import recall_feedback

    planner = Canned(PLAN)
    _wire(monkeypatch, planner, Canned(AIMessage("ok")), Canned(Critique(approved=True)))
    store = InMemoryStore()
    g = build_graph_v2(InMemorySaver(), store=store)

    g.invoke({"messages": [HumanMessage("q")]}, CFG)
    g.invoke(Command(resume="always use 10 years of history"), CFG)  # feedback -> remembered
    assert recall_feedback(store) == ["always use 10 years of history"]

    cfg2 = {"configurable": {"thread_id": "t2"}}
    g.invoke({"messages": [HumanMessage("another question")]}, cfg2)
    system_prompt = str(planner.calls[-1][0].content)
    assert "always use 10 years of history" in system_prompt  # new thread, memory applied


def test_fetch_adds_chart_payload_for_plot_steps(fake_fred):
    plan = Plan(goal="g", steps=[Step(tool="plot_series", args={"series_ids": ["JTSQUR"], "title": "q"}, why="w")])
    out = nodes.fetch({"plan": plan.model_dump()})
    assert out["evidence"][0]["ok"]
    assert out["charts"][0]["panels"][0]["id"] == "JTSQUR"
    assert out["charts"][0]["panels"][0]["points"][-1]["d"] == "2026-08-01"
