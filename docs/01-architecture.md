# 01 - Architecture

## Why these pieces exist

**Settings object, not `os.environ`.** Every secret and knob flows through
`config.Settings`. Tests override one object; nodes stay pure.

**FRED client with disk cache.** Keyed by `(call, args, today)`. Reruns of a
debugging session are instant and deterministic for the day, FRED's rate limit
is never a concern, and fixtures for tests were recorded straight from the cache.
Errors are normalised to `FredError` with text a model can act on
("not found... use search_fred").

**Curated registry before search.** FRED has ~800k series. A 24-entry registry
with units and a one-line interpretation makes tool selection reliable and lets
tests assert on exact ids. `search_fred` is the escape hatch.

**Tools return text, not DataFrames.** Each tool output includes series id,
units, and observation dates so the model can cite them. Errors are *returned*
as strings starting with `ERROR:` rather than raised, so the ReAct loop feeds
them back to the model for self-correction (see `test_agent_recovers_from_tool_error`).

**Two graph entry points.** `graph` (no checkpointer) is what `langgraph dev`
loads: the server injects its own persistence. `build_graph(checkpointer)` is
what the CLI uses with `SqliteSaver`. Compiling with a custom checkpointer and
handing that to the server is a common footgun.

## Stage 1 graph

`langchain.agents.create_agent` produces a two-node loop:

```
__start__ -> model -> tools -> model -> ... -> __end__
```

State is `{"messages": [...]}` with the `add_messages` reducer. Each turn
appends Human -> AI(tool_calls) -> Tool -> ... -> AI(final).

## Testing strategy

- `tests/test_fred_client.py`: caching and error normalisation with a stub `fredapi`.
- `tests/test_tools.py`: formatting and partial-failure behaviour with recorded fixtures.
- `tests/test_graph.py`: a `GenericFakeChatModel` subclass with `bind_tools`
  returning scripted `AIMessage`s. Assert on the **trajectory** (which tools,
  which args, message count in the checkpoint), never on prose.

## What Stage 2 changes

Replace the prebuilt loop with an explicit `StateGraph`:
planner (structured output) -> fetch (deterministic) -> analyst -> critic -> finalize,
with `interrupt_before=["fetch"]` for human approval and a critic loop guard.
