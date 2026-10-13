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

## Stage 2 graph (`graph_v2`, `build_graph_v2`)

```
START -> planner -> review -> fetch -> analyst -> critic -> finalize -> END
                      |  ^                 ^         |
                      |  '-- feedback      '-- reject (max 2)
                      '-- interrupt(): human approves or edits the plan
```

| Node | LLM? | In -> out |
|---|---|---|
| `planner` | yes, structured output (`Plan`) | question (+ feedback) -> `plan` |
| `review` | no | `interrupt()` with the plan; resume `"approve"` or feedback text -> `plan_feedback` |
| `fetch` | no | executes each step's tool deterministically -> `evidence` (errors recorded, not raised) |
| `analyst` | yes | evidence (+ critique) -> `draft` |
| `critic` | yes + regex | deterministic citation check + LLM fact-check -> `critique`, `revisions += 1` |
| `finalize` | no | `draft` -> `messages` (with a reviewer note if still rejected) |

Design decisions worth defending:
- **Plan is data.** Structured output turns "which tools" into something a
  human can approve or edit before any money/time is spent.
- **Fetch has no LLM.** Deterministic execution of an approved plan is cheap,
  testable, and never hallucinates.
- **Critic combines a regex check and an LLM check.** The regex catches
  citations of series/dates that were never fetched (free, exact). The LLM
  catches uncited numbers and historical claims (judgement). Both must pass.
- **Loop guard.** `revisions < MAX_REVISIONS` on the conditional edge, and
  `finalize` appends the unresolved issues rather than hiding them.
- **State holds plain dicts.** Pydantic models are validated inside nodes and
  stored as `model_dump()` so every checkpointer can serialise them.
- **Dynamic `interrupt()` over `interrupt_before`.** The payload tells the
  human what to decide, and `Command(resume=...)` carries their answer; works
  identically from the CLI, the REST API, and Studio.

Tests: `tests/test_graph_v2.py` scripts the three LLM factories and asserts on
routing (pause at review, re-plan on feedback, bounce on rejection, cap).

## Stage 3 additions

**Long-term memory (`memory.py`).** Checkpoints remember a thread; the Store
remembers the user. Feedback typed at plan review is written to the Store
namespace `("prefs", user)`; the planner reads it back on every new thread and
applies it when relevant. CLI: `/prefs`, `/forget`. In Studio the server
supplies the Store.

**Evals (`evals/`).** `cases.yaml` holds questions with expected series and
tools. `run_evals.py` runs each through the v2 graph with a fresh in-memory
checkpointer and store, scores `series_coverage`, `tools_ok`,
`citations_grounded` (regex) and `critic_approved`, writes
`results-<date>.json`, and with `--langsmith` uploads the dataset and runs an
experiment so prompt changes are comparable over time.

**Brief (`brief.py`).** `econ brief` runs a fixed three-question playbook
(labor, rates, growth/inflation) with auto-approved plans and writes
`outputs/brief-<date>.md` with embedded charts. Deterministic questions make it
schedulable and comparable day to day.
