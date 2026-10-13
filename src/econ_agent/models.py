"""Chat-model factory. Lives in its own module so graph.py and nodes.py can
both import it without importing each other (see debugging note 7)."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic

from econ_agent.config import get_settings


def make_model() -> ChatAnthropic:
    s = get_settings()
    return ChatAnthropic(model=s.model, max_tokens=s.max_tokens)
