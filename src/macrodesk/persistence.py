"""Checkpointer + Store factory: SQLite on one machine, Postgres when DATABASE_URL is set.

Both backends expose the same LangGraph interfaces, so the graph and the CLI do not care which
one they get. Postgres lets several processes (or a hosted server) share threads and memory.
"""

from __future__ import annotations

import sqlite3
from contextlib import ExitStack
from dataclasses import dataclass

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from macrodesk.config import Settings


@dataclass
class Persistence:
    saver: BaseCheckpointSaver
    store: BaseStore
    backend: str
    _stack: ExitStack

    def close(self) -> None:
        self._stack.close()


def open_persistence(settings: Settings) -> Persistence:
    stack = ExitStack()
    if settings.database_url:
        from langgraph.checkpoint.postgres import PostgresSaver
        from langgraph.store.postgres import PostgresStore

        saver = stack.enter_context(PostgresSaver.from_conn_string(settings.database_url))
        saver.setup()
        store = stack.enter_context(PostgresStore.from_conn_string(settings.database_url))
        store.setup()
        return Persistence(saver, store, "postgres", stack)

    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.store.sqlite import SqliteStore

    saver = SqliteSaver(sqlite3.connect(str(settings.checkpoint_db), check_same_thread=False))
    # isolation_level=None (autocommit) is required for the store: see debugging note 16.
    store = SqliteStore(sqlite3.connect(str(settings.checkpoint_db), check_same_thread=False, isolation_level=None))
    store.setup()
    return Persistence(saver, store, "sqlite", stack)
