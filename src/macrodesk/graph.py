"""Stage 1: a single ReAct-style agent built with langchain.agents.create_agent.

Two entry points on purpose:
- `build_graph(checkpointer=...)` for the CLI, which owns persistence.
- module-level `graph` (no checkpointer) for `langgraph dev` / Studio, which
  injects its own checkpointer. Compiling with a custom checkpointer and then
  handing the graph to the LangGraph server is a classic footgun - the server
  refuses or silently overrides it.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from macrodesk.models import make_model
from macrodesk.tools import ALL_TOOLS

SYSTEM_PROMPT = """You are an economic analyst assistant with live access to FRED (Federal Reserve Economic Data).

How to work:
1. Start with list_known_series for the relevant topic; only use search_fred if the curated list lacks what you need.
2. Fetch data before making any quantitative claim. Never guess numbers.
3. Every number you state must be followed by its source in the form (SERIES_ID, YYYY-MM-DD). State units.
4. Prefer rates of change and spreads over raw levels when interpreting (use compute_change, yield_curve_snapshot).
5. Distinguish clearly between what the data shows and your interpretation of it.
6. If a tool returns ERROR, read the message, fix the input (e.g. search for the right id) and retry once. If it still fails, tell the user what could not be retrieved.
7. If asked to graph/chart/plot, call plot_series and give the user the saved file path.
8. Be concise: lead with the answer, then 3-6 bullets of evidence, then caveats (data lags, revisions).

Today's date is available from the latest observations; JOLTS lags ~6 weeks, GDP ~1 month after quarter end, Treasury yields are daily."""


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    from langchain.agents import create_agent
    from langchain.agents.middleware import before_model
    from langchain_core.messages import AIMessage

    @before_model(can_jump_to=["end"])
    def nothing_to_answer(state, runtime):
        """Resuming a finished thread with no new input (Studio 'continue', `invoke(None)`) would send a
        conversation that ends with the assistant's own message. Claude 4.6+ rejects that as a prefill
        (debugging note 21). End the run instead; the state is unchanged."""
        msgs = state.get("messages") or []
        if msgs and isinstance(msgs[-1], AIMessage) and not msgs[-1].tool_calls:
            return {"jump_to": "end"}
        return None

    return create_agent(
        model=make_model(),
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        middleware=[nothing_to_answer],
        checkpointer=checkpointer,
        name="macrodesk_v1",
    )


# For `langgraph dev` (Studio). No checkpointer: the server provides one.
graph = build_graph()


# --------------------------------------------------------------------------- #
# Stage 2: explicit StateGraph with human-in-the-loop and a critic loop.
# --------------------------------------------------------------------------- #
def build_graph_v2(checkpointer: BaseCheckpointSaver | None = None, store: BaseStore | None = None):
    from langgraph.graph import END, START, StateGraph

    from macrodesk import nodes
    from macrodesk.state import AgentState

    g = StateGraph(AgentState)
    g.add_node("planner", nodes.planner)
    g.add_node("review", nodes.review)
    g.add_node("fetch", nodes.fetch)
    g.add_node("analyst", nodes.analyst)
    g.add_node("critic", nodes.critic)
    g.add_node("finalize", nodes.finalize)

    g.add_edge(START, "planner")
    g.add_edge("planner", "review")
    g.add_conditional_edges("review", nodes.route_after_review, {"planner": "planner", "fetch": "fetch"})
    g.add_edge("fetch", "analyst")
    g.add_edge("analyst", "critic")
    g.add_conditional_edges("critic", nodes.route_after_critic, {"analyst": "analyst", "finalize": "finalize"})
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer, store=store, name="macrodesk")


graph_v2 = build_graph_v2()
