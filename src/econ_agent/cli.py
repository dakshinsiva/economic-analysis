"""Terminal REPL for the agent, with built-in debugging commands.

    uv run econ "Is the labor market cooling? Use JOLTS."   # one-shot
    uv run econ                                               # REPL
    uv run econ --thread my-thread                            # resume a thread

Debug commands inside the REPL:
    /state          show the current checkpoint's state summary
    /history        list checkpoints for this thread (newest first)
    /replay N       re-run from the Nth checkpoint in /history (time travel)
    /thread new     start a fresh thread id
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
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from econ_agent.config import get_settings
from econ_agent.graph import build_graph
from econ_agent.logging import log_event, setup_logging

console = Console()


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


def run_turn(graph, thread_id: str, user_input: str | None, checkpoint_id: str | None = None) -> None:
    """Stream one turn. user_input=None resumes/replays from a checkpoint."""
    payload = {"messages": [HumanMessage(user_input)]} if user_input else None
    log_event("turn.start", thread_id=thread_id, input=user_input, checkpoint_id=checkpoint_id)
    for chunk in graph.stream(payload, _cfg(thread_id, checkpoint_id), stream_mode="updates"):
        for node, update in chunk.items():
            log_event("node.update", node=node, n_messages=len((update or {}).get("messages", [])))
            for m in (update or {}).get("messages", []):
                _render_message(m)
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


def repl(graph, thread_id: str) -> None:
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
    args = p.parse_args(argv)

    settings = get_settings()
    thread_id = args.thread or uuid.uuid4().hex[:8]
    setup_logging(settings.log_dir, thread_id, settings.log_level)

    conn = sqlite3.connect(str(settings.checkpoint_db), check_same_thread=False)
    graph = build_graph(checkpointer=SqliteSaver(conn))

    if args.question:
        run_turn(graph, thread_id, " ".join(args.question))
        console.print(f"[dim]thread {thread_id}  -  resume with: uv run econ --thread {thread_id}[/]")
    else:
        repl(graph, thread_id)


if __name__ == "__main__":
    main(sys.argv[1:])
