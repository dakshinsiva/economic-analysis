import sqlite3

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from macrodesk import nodes
from macrodesk.graph import build_graph_v2
from macrodesk.memory import recall_feedback
from macrodesk.state import Critique
from macrodesk.threads import delete_thread, latest_thread_id, list_threads, rename_thread
from tests.test_graph_v2 import PLAN, Canned, _wire


def _graph(monkeypatch, tmp_path):
    _wire(monkeypatch, Canned(PLAN), Canned(AIMessage("ok")), Canned(Critique(approved=True)))
    saver = SqliteSaver(sqlite3.connect(str(tmp_path / "cp.sqlite"), check_same_thread=False))
    return build_graph_v2(saver, store=InMemoryStore()), saver


def test_list_rename_delete_threads(monkeypatch, tmp_path, fake_fred):
    g, saver = _graph(monkeypatch, tmp_path)
    for tid, q in (("a", "first?"), ("b", "second?")):
        cfg = {"configurable": {"thread_id": tid}}
        g.invoke({"messages": [HumanMessage(q)]}, cfg)
        g.invoke(Command(resume="approve"), cfg)

    threads = list_threads(saver, g)
    assert [t.thread_id for t in threads] == ["b", "a"]
    assert threads[1].first_question == "first?" and threads[0].messages == 2
    assert latest_thread_id(saver) == "b"

    rename_thread(saver, "a", "jolts")
    assert {t.thread_id for t in list_threads(saver)} == {"b", "jolts"}
    assert g.get_state({"configurable": {"thread_id": "jolts"}}).values["messages"][0].content == "first?"

    delete_thread(saver, "b")
    assert [t.thread_id for t in list_threads(saver)] == ["jolts"]


def test_user_id_scopes_memory(monkeypatch, tmp_path, fake_fred):
    g, _ = _graph(monkeypatch, tmp_path)
    store = g.store
    cfg = {"configurable": {"thread_id": "t", "user_id": "alice"}}
    g.invoke({"messages": [HumanMessage("q")]}, cfg)
    g.invoke(Command(resume="use charts"), cfg)
    assert recall_feedback(store, "alice") == ["use charts"]
    assert recall_feedback(store, "bob") == []
    assert recall_feedback(store) == []  # default user untouched
