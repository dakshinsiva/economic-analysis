"""Thread management on top of the checkpointer.

A LangGraph thread is just a `thread_id` in `config["configurable"]`; the
checkpointer stores every step under it. Nothing stops you using a readable
name ("jolts-oct") as the id, so that is the convention here. This module adds
the listing/rename/delete operations the checkpointer API leaves to you.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver


@dataclass
class ThreadInfo:
    thread_id: str
    updated: datetime | None
    steps: int
    messages: int
    first_question: str


def list_threads(saver: BaseCheckpointSaver, graph=None) -> list[ThreadInfo]:
    """Newest first. Uses only public checkpointer APIs so it works for any saver."""
    latest: dict[str, tuple[datetime | None, int]] = {}
    for ct in saver.list(None):
        tid = ct.config["configurable"]["thread_id"]
        ts = ct.checkpoint.get("ts")
        when = datetime.fromisoformat(ts) if ts else None
        step = ct.metadata.get("step", -1) if ct.metadata else -1
        cur = latest.get(tid)
        if cur is None or (when and cur[0] and when > cur[0]):
            latest[tid] = (when, step)
    out = []
    for tid, (when, step) in latest.items():
        msgs, first = 0, ""
        if graph is not None:
            values = graph.get_state({"configurable": {"thread_id": tid}}).values
            ms = values.get("messages", [])
            msgs = len(ms)
            first = next((m.text for m in ms if isinstance(m, HumanMessage)), "")
        out.append(ThreadInfo(tid, when, step, msgs, first[:60]))
    out.sort(key=lambda t: t.updated or datetime.min, reverse=True)
    return out


def latest_thread_id(saver: BaseCheckpointSaver) -> str | None:
    threads = list_threads(saver)
    return threads[0].thread_id if threads else None


def delete_thread(saver: BaseCheckpointSaver, thread_id: str) -> None:
    saver.delete_thread(thread_id)


def rename_thread(saver: BaseCheckpointSaver, old: str, new: str) -> None:
    """Rename a thread in place.

    `BaseCheckpointSaver.copy_thread` exists but SqliteSaver raises
    NotImplementedError (debugging note 13). For SQLite the thread id is a plain
    column on both tables and is not embedded in the serialised blobs, so an
    UPDATE is safe. Other savers are refused rather than half-renamed.
    """
    conn = getattr(saver, "conn", None)
    if conn is None or not hasattr(conn, "execute"):
        raise NotImplementedError(f"{type(saver).__name__} cannot rename threads")
    if any(True for _ in saver.list({"configurable": {"thread_id": new}}, limit=1)):
        raise ValueError(f"thread {new!r} already exists")
    with conn:
        conn.execute("UPDATE checkpoints SET thread_id = ? WHERE thread_id = ?", (new, old))
        conn.execute("UPDATE writes SET thread_id = ? WHERE thread_id = ?", (new, old))
