# econ-agent: a LangGraph agent over FRED

A from-the-ground-up LangGraph agent that answers macro questions (JOLTS, GDP,
inflation, yield curve) with live data from the St. Louis Fed's FRED API, built
to be **debugged and explained**, not just demoed.

```
you> Is the labor market cooling? Use JOLTS.
  tool call -> list_known_series {"topic": "labor"}
  tool call -> compare_series {"series_ids": ["JTSJOL","JTSQUR","JTSLDL"]}
  tool call -> compute_change {"series_id": "JTSQUR", "periods": 12, "pct": false}
assistant: Yes, gradually. Quits rate 1.9% (JTSQUR, 2026-08-01), down 0.1pp YoY ...
```

## Architecture

**Stage 2 (default):** an explicit `StateGraph` with human-in-the-loop and a
fact-checking critic.

```
START -> planner -> review -> fetch -> analyst -> critic -> finalize -> END
                      |  ^                 ^         |
                      |  '-- feedback      '-- reject (max 2)
                      '-- interrupt(): approve or edit the plan
```

**Stage 1 (`--v1`):** the prebuilt ReAct loop, kept for comparison.

```
START -> model -> (tool calls?) -> tools -> model -> ... -> END
```

| Layer | File | Role |
|---|---|---|
| Settings | `src/econ_agent/config.py` | env/.env -> one `Settings` object; nothing else reads `os.environ` |
| Data | `src/econ_agent/fred/client.py` | cached, error-normalising wrapper over `fredapi` |
| Registry | `src/econ_agent/fred/series.py` | 24 curated series with units + "how to read it" |
| Tools | `src/econ_agent/tools.py` | 8 `@tool`s returning compact, citable text (incl. `plot_series` -> PNG) |
| Charts | `src/econ_agent/charts.py` | matplotlib small multiples with recession shading; files land in `outputs/` |
| Graph v1 | `src/econ_agent/graph.py` | `create_agent` ReAct loop; `graph` for Studio, `build_graph()` for CLI |
| Graph v2 | `src/econ_agent/graph.py`, `nodes.py`, `state.py` | planner / review / fetch / analyst / critic / finalize |
| CLI | `src/econ_agent/cli.py` | rich REPL with `/state`, `/history`, `/replay` |
| Logs | `src/econ_agent/logging.py` | JSONL per thread in `logs/` |

Roadmap: Stage 3 adds long-term memory, evals, and a scheduled brief. See `docs/`.

## Setup

```bash
uv sync
cp .env.example .env   # add FRED_API_KEY (free), ANTHROPIC_API_KEY, optional LANGSMITH_*
```

Model selection: `ECON_MODEL` > `ANTHROPIC_MODEL` > `claude-opus-5-5`. If your
shell routes the Anthropic SDK through a gateway (`ANTHROPIC_BASE_URL`, e.g.
Microsoft Foundry), the model string must be a *deployment name* on that
gateway.

## Run

```bash
uv run econ "Is the yield curve inverted right now?"   # one-shot; pauses for plan approval
uv run econ --auto-approve "..."                        # skip the review prompt
uv run econ --v1 "..."                                  # Stage 1 ReAct agent
uv run econ                                             # REPL
uv run econ --thread d4b30282                           # resume a thread
uv run langgraph dev                                    # LangGraph Studio
uv run pytest                                           # offline tests
```

## Debugging toolkit

- **Terminal panels**: every tool call and result is printed as it streams.
- **`/state`, `/history`, `/replay N`**: inspect the SQLite checkpointer and
  time-travel to an earlier checkpoint.
- **`logs/run-<thread>.jsonl`**: structured events (FRED latency, cache hits,
  node updates, token usage). Works offline.
- **LangGraph Studio** (`langgraph dev`): step through nodes visually; `econ_agent_v2` pauses at `review` and resumes from the UI.
- **LangSmith**: set `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` in `.env`; `config.py` exports `.env` into the process so both the CLI and Studio trace to `LANGSMITH_PROJECT`.

Details and war stories in `docs/02-debugging.md`.
