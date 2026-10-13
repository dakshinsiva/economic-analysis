"""Long-term memory: user planning preferences that survive across threads.

Checkpoints remember *a conversation*. The Store remembers *the user*. Here the
only thing we persist is feedback given at plan review ("use 10 years of
history", "always include a chart"), so the planner can apply it next time
without being told again. Namespace: ("prefs", user_id).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from langgraph.store.base import BaseStore

NAMESPACE_ROOT = "prefs"
DEFAULT_USER = "default"


def namespace(user_id: str = DEFAULT_USER) -> tuple[str, str]:
    return (NAMESPACE_ROOT, user_id)


def remember_feedback(store: BaseStore | None, text: str, user_id: str = DEFAULT_USER) -> None:
    if store is None or not text.strip():
        return
    store.put(namespace(user_id), uuid.uuid4().hex[:8],
              {"text": text.strip(), "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")})


def recall_feedback(store: BaseStore | None, user_id: str = DEFAULT_USER, limit: int = 10) -> list[str]:
    if store is None:
        return []
    items = store.search(namespace(user_id), limit=limit)
    items.sort(key=lambda i: i.value.get("ts", ""))
    return [i.value["text"] for i in items]


def forget_all(store: BaseStore | None, user_id: str = DEFAULT_USER) -> int:
    if store is None:
        return 0
    items = store.search(namespace(user_id), limit=1000)
    for i in items:
        store.delete(namespace(user_id), i.key)
    return len(items)
