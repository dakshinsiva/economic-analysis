"""Stage 1: a single ReAct-style agent built with langchain.agents.create_agent.

Two entry points on purpose:
- `build_graph(checkpointer=...)` for the CLI, which owns persistence.
- module-level `graph` (no checkpointer) for `langgraph dev` / Studio, which
  injects its own checkpointer. Compiling with a custom checkpointer and then
  handing the graph to the LangGraph server is a classic footgun - the server
  refuses or silently overrides it.
"""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.base import BaseCheckpointSaver

from econ_agent.config import get_settings
from econ_agent.tools import ALL_TOOLS

SYSTEM_PROMPT = """You are an economic analyst assistant with live access to FRED (Federal Reserve Economic Data).

How to work:
1. Start with list_known_series for the relevant topic; only use search_fred if the curated list lacks what you need.
2. Fetch data before making any quantitative claim. Never guess numbers.
3. Every number you state must be followed by its source in the form (SERIES_ID, YYYY-MM-DD). State units.
4. Prefer rates of change and spreads over raw levels when interpreting (use compute_change, yield_curve_snapshot).
5. Distinguish clearly between what the data shows and your interpretation of it.
6. If a tool returns ERROR, read the message, fix the input (e.g. search for the right id) and retry once. If it still fails, tell the user what could not be retrieved.
7. Be concise: lead with the answer, then 3-6 bullets of evidence, then caveats (data lags, revisions).

Today's date is available from the latest observations; JOLTS lags ~6 weeks, GDP ~1 month after quarter end, Treasury yields are daily."""


def make_model() -> ChatAnthropic:
    s = get_settings()
    return ChatAnthropic(model=s.model, max_tokens=s.max_tokens)


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    from langchain.agents import create_agent

    return create_agent(
        model=make_model(),
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        name="econ_agent",
    )


# For `langgraph dev` (Studio). No checkpointer: the server provides one.
graph = build_graph()
