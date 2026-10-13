"""Terminal REPL for the agent, with built-in debugging commands.

    uv run econ "Is the labor market cooling? Use JOLTS."   # one-shot
    uv run econ                                               # REPL
    uv run econ --thread my-thread                            # resume a thread
    uv run econ --v1 "..."                                    # Stage 1 ReAct agent
    uv run econ --auto-approve "..."                          # skip plan review
    uv run econ brief                                         # write outputs/brief-<date>.md

Stage 2 graphs pause after planning: press Enter to approve the plan, or type
feedback (e.g. "use 10 years of history") to re-plan.

Debug commands inside the REPL:
    /state          show the current checkpoint's state summary
    /history        list checkpoints for this thread (newest first)
    /replay N       re-run from the Nth checkpoint in /history (time travel)
    /thread new     start a fresh thread id
    /prefs          show remembered plan feedback (long-term memory)
    /forget         clear remembered plan feedback
    /quit
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore
from langgraph.types import Command
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from econ_agent.config import get_settings
from econ_agent.brief import run_brief
from econ_agent.graph import build_graph, build_graph_v2
from econ_agent.memory import forget_all, recall_feedback
from econ_agent.logging import log_event, setup_logging

console = Console()
AUTO_APPROVE = False


def _cfg(thread_id: str, checkpoint_id: str | None = None) -> dict[str, Any]:
    c: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    if checkpoint_id:
        c["configurable"]["checkpoint_id"] = checkpoint_id
    return c


def _render_message(msg: BaseMessage) -> None:
    """Pretty-print one message emitted by a node update."""
    if isinstance(msg, AIMessage):
        for tc in msg.tool_calls:
            console.print(Panel(json.dumps(tc["args"], indent=1), title=f"[bold cyan]tool call -> {tc['name']}",
                                border_style="cyan"))
        text = msg.text
        if isinstance(text, str) and text.strip():
            console.print(Panel(Markdown(text), title="[bold green]assistant", border_style="green"))
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            log_event("model.usage", **{k: v for k, v in usage.items() if isinstance(v, int)})
    elif isinstance(msg, ToolMessage):
        content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
        style = "red" if content.startswith("ERROR") else "yellow"
        console.print(Panel(content, title=f"[bold {style}]tool result <- {msg.name}", border_style=style))


def _render_update(node: str, update: Any) -> None:
    log_event("node.update", node=node)
    if node == "__interrupt__":
        return
    if not isinstance(update, dict):
        return
    for m in update.get("messages", []):
        _render_message(m)
    if "plan" in update and update["plan"] is not None:
        plan = update["plan"]
        steps = "\n".join(f"{i}. {s['tool']}({json.dumps(s['args'])})  - {s['why']}" for i, s in enumerate(plan["steps"], 1))
        console.print(Panel(f"[bold]{plan['goal']}[/]\n{steps}", title="[bold magenta]plan", border_style="magenta"))
    if "evidence" in update and update["evidence"]:
        for e in update["evidence"]:
            style = "yellow" if e["ok"] else "red"
            console.print(Panel(e["result"], title=f"[bold {style}]evidence <- {e['tool']}", border_style=style))
    if "draft" in update and update["draft"]:
        console.print(Panel(Markdown(update["draft"]), title=f"[bold blue]{node} draft", border_style="blue"))
    if "critique" in update and update["critique"] is not None:
        c = update["critique"]
        ok = c["approved"]
        body = "approved" if ok else "\n".join(f"- {i}" for i in c["issues"])
        console.print(Panel(body, title=f"[bold {'green' if ok else 'red'}]critic", border_style="green" if ok else "red"))


def _stream(graph, payload, cfg) -> bool:
    """Stream one graph run. Returns True if the run paused at an interrupt."""
    interrupted = False
    for chunk in graph.stream(payload, cfg, stream_mode="updates"):
        for node, update in chunk.items():
            if node == "__interrupt__":
                interrupted = True
            _render_update(node, update)
    return interrupted


def run_turn(graph, thread_id: str, user_input: str | None, checkpoint_id: str | None = None) -> None:
    """Stream one turn. user_input=None resumes/replays from a checkpoint.
    If the graph pauses for plan review, ask the human and resume until it finishes."""
    payload = {"messages": [HumanMessage(user_input)]} if user_input else None
    cfg = _cfg(thread_id, checkpoint_id)
    log_event("turn.start", thread_id=thread_id, input=user_input, checkpoint_id=checkpoint_id)
    interrupted = _stream(graph, payload, cfg)
    while interrupted:
        console.print("[magenta]Plan review:[/] press Enter to approve, or type feedback to re-plan.")
        if AUTO_APPROVE:
            decision = "approve"
        else:
            try:
                decision = console.input("[bold magenta]review>[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                decision = "approve"
        interrupted = _stream(graph, Command(resume=decision or "approve"), _cfg(thread_id))
    log_event("turn.end", thread_id=thread_id)


def show_state(graph, thread_id: str) -> None:
    snap = graph.get_state(_cfg(thread_id))
    msgs = snap.values.get("messages", [])
    t = Table(title=f"state for thread {thread_id}", show_lines=False)
    t.add_column("#"); t.add_column("type"); t.add_column("preview")
    for i, m in enumerate(msgs):
        preview = str(m.text)[:90].replace("\n", " ")
        if isinstance(m, AIMessage) and m.tool_calls:
            preview = "tool_calls: " + ", ".join(tc["name"] for tc in m.tool_calls)
        t.add_row(str(i), type(m).__name__, preview)
    console.print(t)
    console.print(f"next node(s): {snap.next or '(idle)'}   checkpoint: {snap.config['configurable'].get('checkpoint_id')}")


def list_history(graph, thread_id: str) -> list[Any]:
    hist = list(graph.get_state_history(_cfg(thread_id)))
    t = Table(title=f"checkpoints for {thread_id} (0 = newest)")
    t.add_column("#"); t.add_column("step"); t.add_column("next"); t.add_column("msgs"); t.add_column("checkpoint_id")
    for i, s in enumerate(hist):
        t.add_row(str(i), str(s.metadata.get("step")), ",".join(s.next) or "-",
                  str(len(s.values.get("messages", []))), s.config["configurable"]["checkpoint_id"][-12:])
    console.print(t)
    return hist


def repl(graph, thread_id: str, store=None) -> None:
    console.print(Panel(f"econ agent - thread [bold]{thread_id}[/]  (type /help)", border_style="blue"))
    hist: list[Any] = []
    while True:
        try:
            line = console.input("[bold blue]you>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line in ("/quit", "/exit"):
            break
        if line == "/help":
            console.print(__doc__)
        elif line == "/state":
            show_state(graph, thread_id)
        elif line == "/history":
            hist = list_history(graph, thread_id)
        elif line.startswith("/replay"):
            parts = line.split()
            if len(parts) != 2 or not parts[1].isdigit():
                console.print("usage: /replay N   (run /history first)"); continue
            hist = hist or list(graph.get_state_history(_cfg(thread_id)))
            n = int(parts[1])
            if n >= len(hist):
                console.print(f"only {len(hist)} checkpoints"); continue
            snap = hist[n]
            console.print(f"[magenta]replaying from checkpoint {snap.config['configurable']['checkpoint_id'][-12:]} "
                          f"(next={snap.next})[/]")
            run_turn(graph, thread_id, None, snap.config["configurable"]["checkpoint_id"])
        elif line == "/prefs":
            prefs = recall_feedback(store)
            console.print(Panel("\n".join(f"- {p}" for p in prefs) or "(nothing remembered yet)",
                                title="[bold]remembered plan feedback", border_style="blue"))
        elif line == "/forget":
            console.print(f"forgot {forget_all(store)} item(s)")
        elif line == "/thread new":
            thread_id = uuid.uuid4().hex[:8]
            setup_logging(get_settings().log_dir, thread_id)
            console.print(f"new thread [bold]{thread_id}[/]")
        else:
            run_turn(graph, thread_id, line)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="econ", description="FRED economic-analysis agent")
    p.add_argument("question", nargs="*", help="one-shot question; omit for REPL")
    p.add_argument("--thread", default=None, help="thread id to resume (default: new)")
    p.add_argument("--v1", action="store_true", help="use the Stage 1 prebuilt ReAct agent instead of the Stage 2 graph")
    p.add_argument("--auto-approve", action="store_true", help="skip the plan review prompt (Stage 2)")
    args = p.parse_args(argv)

    settings = get_settings()
    thread_id = args.thread or uuid.uuid4().hex[:8]
    setup_logging(settings.log_dir, thread_id, settings.log_level)

    conn = sqlite3.connect(str(settings.checkpoint_db), check_same_thread=False)
    saver = SqliteSaver(conn)
    # The store gets its OWN connection: SqliteStore and SqliteSaver both manage
    # transactions, and sharing one connection raises "cannot start a transaction
    # within a transaction" the first time a node touches the store mid-run
    # (debugging note 11).
    store = SqliteStore(sqlite3.connect(str(settings.checkpoint_db), check_same_thread=False))
    store.setup()
    graph = build_graph(checkpointer=saver) if args.v1 else build_graph_v2(checkpointer=saver, store=store)
    global AUTO_APPROVE
    AUTO_APPROVE = args.auto_approve

    if args.question and args.question[0] == "brief":
        AUTO_APPROVE = True
        path = run_brief(graph, thread_id, run_turn)
        console.print(f"[green]brief written to {path}[/]")
    elif args.question:
        run_turn(graph, thread_id, " ".join(args.question))
        console.print(f"[dim]thread {thread_id}  -  resume with: uv run econ --thread {thread_id}[/]")
    else:
        repl(graph, thread_id, store)


if __name__ == "__main__":
    main(sys.argv[1:])
