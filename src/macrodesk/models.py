"""Chat-model factory. Lives in its own module so graph.py and nodes.py can
both import it without importing each other (see debugging note 7)."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from macrodesk.config import get_settings


def make_model(role: str | None = None) -> ChatAnthropic:
    """role in {None, "planner", "critic"}: picks ECON_PLANNER_MODEL / ECON_CRITIC_MODEL when set."""
    s = get_settings()
    model = {"planner": s.planner_model, "critic": s.critic_model}.get(role or "") or s.model
    return ChatAnthropic(model=model, max_tokens=s.max_tokens)
