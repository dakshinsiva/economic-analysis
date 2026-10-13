# macrodesk — an agentic macro research desk over FRED

[![tests](https://github.com/dakshinsiva/economic-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/dakshinsiva/economic-analysis/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.12%2B-blue)
![langgraph](https://img.shields.io/badge/langgraph-1.x-1c3c3c)
![next](https://img.shields.io/badge/next.js-16-black)
![license](https://img.shields.io/badge/license-MIT-green)
[![live](https://img.shields.io/badge/live-macrodesk--agent.vercel.app-5598e7)](https://macrodesk-agent.vercel.app)

Ask a macro question in plain English and get back an analyst's answer in which every number carries
its FRED series id and observation date, with the data fetched live from the St. Louis Fed, a chart
when one helps, and a fact-checker's verdict on the draft. Before anything is fetched, the agent shows
you its plan and waits: approve it, or tell it to use ten years of history instead of three, and it
re-plans. What you tell it at that step, it remembers next time.

![macrodesk: plan, evidence, chart and a critic-checked answer for a JOLTS question](docs/images/cover-dark.png)

*A JOLTS question in the research desk. Top, the macro dashboard and the pipeline strip. Then the plan
the agent proposed and the user approved, the evidence it fetched (a four-series JOLTS table), the
chart drawn from the same data, and the answer with each figure linked to its FRED series. The critic
approved this draft on the first pass.*

## Why this is hard

Language models are fluent about the economy and will happily tell you that job openings "peaked near
12 million in 2022" without having looked. In the first version of this agent the model did exactly
that: the number was roughly right, it was uncited, and it came from training memory rather than from
the four series it had just fetched. A prompt that says "cite everything" lowers the rate of such
claims; it does not make them detectable.

So the answer has to be *verifiable by construction*. The plan is data, not prose, so a person can
approve it. Fetching is deterministic, with no model in the loop. The writer only sees the evidence.
And a separate critic compares the draft with the evidence and sends it back when a figure, date,
peak or range is not there. Along the way the usual things went wrong, each one is written up, and
they are the part of this repository most worth reading: [docs/02-debugging.md](docs/02-debugging.md).

## Pipeline

```mermaid
flowchart LR
    Q[question] --> P[planner\nstructured output: which series, which tools]
    P --> R{review\ninterrupt: approve or edit}
    R -- feedback --> P
    R -- approve --> F[fetch\nruns the plan, no LLM]
    F --> A[analyst\nwrites from evidence only]
    A --> C{critic\nregex citation check + LLM fact-check}
    C -- reject, max 2 --> A
    C -- approve --> Z[answer\ncited, linked, downloadable]
    M[(Store\nremembered plan feedback)] -.-> P
    R -.-> M
```

| Node | Model? | What it does |
|---|---|---|
| **planner** | yes, structured output | Turns the question (plus anything you said at earlier reviews) into a list of tool calls over a curated registry of 24 FRED series: JOLTS, payrolls, claims, GDP, CPI/PCE, the Treasury curve |
| **review** | no | Pauses the graph with `interrupt()` and shows the plan. Resume with "approve" or with feedback; feedback is also written to long-term memory |
| **fetch** | no | Executes each step against FRED through a cached client. Errors are recorded as evidence, not raised |
| **analyst** | yes | Writes the answer from the evidence block only, citing `(SERIES_ID, YYYY-MM-DD)` and stating units |
| **critic** | yes + regex | A deterministic check that every cited series and date exists in the evidence, then an LLM pass for uncited numbers and historical claims. Rejections go back to the analyst, at most twice |
| **finalize** | no | Posts the answer; if issues remain after the cap, they are appended rather than hidden |

Stage 1 of the project, a prebuilt ReAct agent with the same tools, is kept as `--v1` for comparison.

## The research desk

The web app in `web/` is a Next.js front end to the LangGraph server, deployed at [macrodesk-agent.vercel.app](https://macrodesk-agent.vercel.app), where it replays a recorded run on arrival. It is built for someone who
works with this data rather than for a chat demo:

| | |
|---|---|
| ![plan review](docs/images/plan-review-dark.png) | ![home](docs/images/home-light.png) |

*Left, the plan review: the agent has proposed two tool calls and is waiting. Right, the desk on
arrival in light mode: six indicators with sparklines and 12-month changes; clicking one asks about it.*

- **Macro dashboard.** Unemployment, quits, openings, the 10y–2y spread, core PCE and real GDP, with
  sparklines and the change over the natural horizon for each. A tile is a question.
- **Plan review in the page.** Approve, or type feedback and watch the plan change. The same
  `Command(resume=...)` path serves the CLI, the REST API and LangGraph Studio.
- **Evidence you can read.** Every tool result is shown as fetched, with a green or red mark.
- **Charts from the same data.** One panel per series (never a dual axis), NBER recessions shaded,
  the latest value labelled.
- **Citations that go somewhere.** `(UNRATE, 2026-09-01)` is a link to the series on FRED; the
  sources used are listed under the answer; copy as markdown or download.
- **Follow-ups.** Suggested next questions built from the series the answer cited.
- **Trace.** Per-node timings and the raw graph state, for the debugging story.
- **Demo mode.** With no backend configured the page replays a recorded run, so the deployed URL
  always shows the whole pipeline.

## What comes out

From a run on 2026-10-13, *"What does the latest JOLTS report say about the labor market?"*:

> Job openings fell to 7,079,000 in August 2026 (JTSJOL, 2026-08-01), down from the series peak of
> 12,301,000 in the window — a decline of roughly 42%. Quits held at 1.9% (JTSQUR, 2026-08-01),
> matching the window low. Layoffs totalled 1,641,000 (JTSLDL, 2026-08-01), close to the series mean,
> so the market is cooling without a layoff spike. *Caveat: the 12,301,000 peak is the maximum of the
> retrieved window (from 2021-01-01); the all-time peak date was not retrieved.*

The caveat is the point: the analyst had the window summary but not the peak's date, said so, and the
critic let it through. The eval harness scores six such questions on series coverage, tool choice,
regex-verified grounding and critic approval; the first run found two bugs the unit tests had passed
over, which is also written up.

## Running it

Python side (the agent, CLI, LangGraph server):

```bash
uv sync
cp .env.example .env            # FRED_API_KEY (free), ANTHROPIC_API_KEY, optional LANGSMITH_*
uv run macrodesk "Is the yield curve inverted right now?"   # pauses for plan approval
uv run macrodesk --auto-approve "..."                        # skip the review
uv run macrodesk --v1 "..."                                  # the Stage 1 ReAct agent
uv run macrodesk brief                                       # outputs/brief-<date>.md
uv run pytest                                           # 26 offline tests, no keys needed
uv run python evals/run_evals.py [--langsmith]          # eval harness
uv run langgraph dev                                    # LangGraph server + Studio
```

The research desk, against that server:

```bash
cd web && npm install
cp .env.example .env.local      # LANGGRAPH_API_URL=http://127.0.0.1:2024, FRED_API_KEY for the dashboard
npm run dev                     # http://localhost:3000 ; add ?demo=1 to force the recorded replay
```

Inside the CLI: `/state`, `/history`, `/replay N` (time travel to a checkpoint), `/threads`,
`/thread <name|new|rename|delete>`, `/prefs`, `/forget`. `--thread NAME` resumes a conversation,
`--last` the most recent one, `--user NAME` keeps a separate memory per person.

## Deploying the desk

The Next.js app deploys to Vercel as is. Point `LANGGRAPH_API_URL` and `LANGSMITH_API_KEY` at a
LangSmith Deployment of this graph for a live backend, or set `NEXT_PUBLIC_DEMO=1` for the replay.
`FRED_API_KEY` on the server enables the live dashboard; without it the recorded snapshot is shown.

## Design notes

- **Plan as data.** Structured output turns "which tools" into something a human can approve or edit
  before any time or money is spent, and something tests can assert on exactly.
- **Fetch has no model.** Deterministic execution of an approved plan is cheap, testable and cannot
  hallucinate. The FRED client caches to disk by (call, args, day), so a debugging session replays
  offline and test fixtures were recorded straight from the cache.
- **Tools return text the model can cite.** Series id, units and observation dates in every output;
  errors returned as `ERROR: ...` strings so the loop can self-correct rather than crash.
- **Two checks are better than one judge.** The regex citation check never misfires; the LLM critic
  catches what regex cannot (an uncited "peak", a unit error) and was itself measured for false
  rejections before being trusted as a gate.
- **State is a wire format.** Graph state holds plain dicts; Pydantic models are validated inside
  nodes. Every checkpointer (SQLite, the server's, Postgres) can serialise it.
- **Identity and session are configuration.** `thread_id` selects the checkpoint lineage and
  `user_id` the memory namespace, both in `config["configurable"]`; one compiled graph serves every
  user from the CLI, the API and Studio.
- **Memory is narrow on purpose.** Only plan-review feedback is persisted. It is high-signal because a
  person just said it was worth saying, and cheap to apply.

## Debugging log

Fifteen incidents so far, each with the symptom, how it was localised and the fix:
a native wheel that tried to compile Rust, a gateway that silently rewrote the model endpoint, a
400 from a prompt with no user turn (twice: once in Studio, once in my own critic), a circular
import, Pydantic objects in checkpointed state, a critic that rejected correct arithmetic, two
libraries sharing one SQLite connection, and a `copy_thread` that exists on the base class but not in
SQLite, plus two from wiring the web app. [docs/02-debugging.md](docs/02-debugging.md).

## Repository layout

| Path | What it is |
|---|---|
| `src/macrodesk/graph.py`, `nodes.py`, `state.py` | The Stage 2 graph: planner, review, fetch, analyst, critic, finalize |
| `src/macrodesk/tools.py`, `fred/` | Eight tools over a cached FRED client and a curated series registry |
| `src/macrodesk/charts.py` | Small-multiple PNG charts for the CLI; JSON payloads for the web |
| `src/macrodesk/memory.py`, `threads.py` | Store-backed plan memory; thread list, rename, delete |
| `src/macrodesk/cli.py`, `brief.py` | REPL with checkpoint inspection and time travel; the daily brief |
| `web/` | The research desk: Next.js 16, LangGraph SDK `useStream`, Recharts |
| `tests/` | 26 offline tests: stub FRED, recorded fixtures, scripted models, SQLite threads |
| `evals/` | Cases, scorer, LangSmith experiment |
| `docs/` | Architecture, the debugging log, interview notes |

## Built by

Dakshin Siva — [github.com/dakshinsiva](https://github.com/dakshinsiva) · dakshinrajsiva@gmail.com

Built with Claude Code as a from-the-ground-up exercise in constructing and debugging LangGraph
agents; every incident in the debugging log happened as described. Data from FRED, Federal Reserve
Bank of St. Louis. Licensed MIT.
