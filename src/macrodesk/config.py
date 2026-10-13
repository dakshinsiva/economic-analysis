"""Runtime settings, loaded from the environment / .env.

Everything the agent needs to know about its environment lives here so that
nodes and tools never read os.environ directly. That makes tests trivial
(override one object) and keeps secrets out of the graph state.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Export .env into os.environ so libraries that read the environment directly
# (LangSmith tracing, the Anthropic SDK) see the same values the Settings do.
# Existing shell variables win: override=False.
load_dotenv(PROJECT_ROOT / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    fred_api_key: str = Field(default="", alias="FRED_API_KEY")
    # ECON_MODEL wins; else ANTHROPIC_MODEL (set by some shells / gateways such as
    # Microsoft Foundry, where the name must match a *deployment*); else Opus 5.5.
    model: str = Field(
        default_factory=lambda: os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5"),
        alias="ECON_MODEL",
    )
    max_tokens: int = Field(default=8000, alias="ECON_MAX_TOKENS")
    # Optional cheaper/faster models for the planner and critic; default to `model`.
    planner_model: str | None = Field(default=None, alias="ECON_PLANNER_MODEL")
    critic_model: str | None = Field(default=None, alias="ECON_CRITIC_MODEL")
    log_level: str = Field(default="INFO", alias="ECON_LOG_LEVEL")

    # Optional Postgres for the checkpointer and the Store (multi-machine deployments); SQLite otherwise.
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    cache_dir: Path = PROJECT_ROOT / ".cache"
    log_dir: Path = PROJECT_ROOT / "logs"
    checkpoint_db: Path = PROJECT_ROOT / ".checkpoints.sqlite"


def get_settings() -> Settings:
    s = Settings()
    s.cache_dir.mkdir(exist_ok=True)
    s.log_dir.mkdir(exist_ok=True)
    return s
