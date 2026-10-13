"""Structured JSON-lines logging.

Every tool call, node transition and model call writes one JSON object per
line to logs/run-<thread>.jsonl. This is the "works without any cloud"
debugging layer: grep-able, diff-able, and attachable to a bug report.
LangSmith gives you the same information with a UI; this file is what you
read when LangSmith is down or you are offline.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

_LOGGER_NAME = "macrodesk"


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: dict[str, Any] = {
            "ts": round(time.time(), 3),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "data", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(log_dir: Path, thread_id: str, level: str = "INFO") -> logging.Logger:
    """Configure the macrodesk logger to write JSONL for this thread."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level.upper())
    # Avoid duplicate handlers when called twice in the same process (tests, REPL).
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = logging.FileHandler(log_dir / f"run-{thread_id}.jsonl", encoding="utf-8")
    handler.setFormatter(JsonLineFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def log_event(event: str, **data: Any) -> None:
    """Convenience: logger.info(event, extra={"data": {...}})."""
    get_logger().info(event, extra={"data": data})
