# 05 - How this project uses LangGraph and LangSmith

A guided tour of every LangGraph and LangSmith capability in the repository: what it is,
where it lives in the code, why it was chosen, and what it looks like when it breaks. Read it
top to bottom once; after that, each section stands alone.

## The mental model in one paragraph

LangGraph runs a **graph of functions over a shared state**. Each node takes the state, returns
a partial update, and the runtime merges it (reducers decide how, e.g. `add_messages` appends).
After every step the runtime writes a **checkpoint**, so a run can pause, resume, be replayed,
or be forked. Pausing on purpose is an **interrupt**; resuming is a **Command**. Memory that
should outlive a conversation goes in a **Store**, keyed by namespace. Everything the runtime
does is observable as a **stream** of events, and when tracing is on, every node and model call
is also recorded in **LangSmith** as a tree you can inspect, compare and evaluate against.

## 1. State: `src/macrodesk/state.py`

The state is a `TypedDict`. One field uses a reducer:

```python
messages: Annotated[list[AnyMessage], add_messages]
```

`add_messages` appends new messages instead of replacing the list, and de-duplicates by id.
Every other field (`plan`, `evidence`, `draft`, `critique`, `revisions`, `charts`,
`prior_evidence`) is replaced wholesale by whatever a node returns. That is deliberate: the
planner returns a fresh `plan` and clears `evidence`, the critic replaces `critique`.

Two decisions worth knowing. State holds **plain dicts**, not Pydantic objects; the models in
the same file (`Plan`, `Step`, `Evidence`, `Critique`) are validated *inside* nodes and stored
as `model_dump()`. Checkpointers serialise with msgpack and warn about unregistered classes
(debugging note 9). And `prior_evidence` carries the previous turn's evidence forward so a
follow-up can cite it without re-fetching, which the critic then accepts (note 18).

## 2. Nodes and edges: `src/macrodesk/graph.py`, `nodes.py`

```python
g = StateGraph(AgentState)
g.add_node("planner", nodes.planner) ... g.add_node("finalize", nodes.finalize)
g.add_edge(START, "planner"); g.add_edge("planner", "review")
g.add_conditional_edges("review", nodes.route_after_review, {"planner": "planner", "fetch": "fetch"})
g.add_edge("fetch", "analyst"); g.add_edge("analyst", "critic")
g.add_conditional_edges("critic", nodes.route_after_critic, {"analyst": "analyst", "finalize": "finalize"})
g.add_edge("finalize", END)
graph = g.compile(checkpointer=..., store=..., name="macrodesk")
```

A **conditional edge** is a plain function of the state that returns the name of the next node.
`route_after_critic` is also the loop guard: it sends the draft back only while
`revisions < MAX_REVISIONS`. Loops in LangGraph are just edges that point backwards; the guard
is your responsibility, which is why `revisions` is in the state and not in a local variable.

Nodes receive extras by **signature injection**: `planner(state, runtime: Runtime)` gets the
runtime, whose `.store` is the long-term memory. The analyst gets a stream writer via
`get_stream_writer()` (section 6). You read per-run configuration with
`langgraph.config.get_config()`; `memory.current_user_id()` does exactly that.

Stage 1 is still in the file: `build_graph()` wraps `langchain.agents.create_agent`, the
prebuilt ReAct loop (one `model` node, one `tools` node). Keeping both lets you compare a
model-driven loop against an explicit graph with the same tools.

## 3. Checkpointers: `src/macrodesk/persistence.py`, `cli.py`

Compiling with a checkpointer turns every run into a **thread**. The thread id travels in
`config["configurable"]["thread_id"]`; nothing else identifies the conversation. The CLI uses
`SqliteSaver`; set `DATABASE_URL` and `open_persistence` swaps in `PostgresSaver` without
touching the graph.

What a checkpointer gives you, and where the CLI exposes it:

| Capability | API | CLI |
|---|---|---|
| Inspect the current state | `graph.get_state(config)` | `/state` |
| Every past state | `graph.get_state_history(config)` | `/history` |
| Time travel: re-run from a checkpoint (forks the thread) | `graph.stream(None, {"configurable": {"thread_id", "checkpoint_id"}})` | `/replay N` |
| List, rename, delete threads | `saver.list(None)`, `saver.delete_thread` | `/threads`, `/thread ...` |

Two things the server does for you that the CLI must do itself: `langgraph dev` injects its
own checkpointer and store, so the module-level `graph` object is compiled **without** them
(a graph compiled with a checkpointer and then handed to the server is a classic footgun), and
threads on the server are created through its REST API, which the web app calls via
`client.threads.search`.

Two SQLite-specific lessons live in the debugging log: the checkpointer and the store must not
share a connection (note 11), and the store's connection must be autocommit (note 16).

## 4. Human-in-the-loop: `nodes.review`

```python
decision = interrupt({"type": "plan_review", "goal": ..., "steps": [...], "hint": ...})
```

`interrupt()` suspends the run and surfaces the payload to whoever is driving the graph.
Resuming means invoking again with `Command(resume=value)`; the node re-executes from its top
and `interrupt()` returns `value`. The review node accepts three shapes: `"approve"`, free text
(feedback, which re-plans and is also remembered), or `{"plan": {...}}` (an edited plan from the
web UI, validated and executed as approved).

The same code path serves every client. The CLI prompts in the terminal. The web app reads
`stream.interrupt` from `useStream` and submits `{command: {resume}}`. Studio shows the
interrupt and lets you type the resume value. The REST call is
`POST /threads/{id}/runs/wait` with `{"command": {"resume": "approve"}}`.

Static interrupts (`interrupt_before=["fetch"]` at compile time) would also have worked;
the dynamic form was chosen because the payload tells the human what they are deciding.

## 5. Long-term memory: `src/macrodesk/memory.py`

The **Store** is the second persistence layer. Checkpoints remember a thread; the Store
remembers across threads, keyed by a namespace tuple, here `("prefs", user_id)`. The review
node writes plan feedback with `store.put`; the planner reads it with `store.search` on every
new thread and puts it in its prompt.

Only plan-review feedback is persisted, on purpose: a person just said it was worth saying, and
it is cheap to apply. `user_id` comes from the run config, so one compiled graph serves every
user; the web app's sidebar field is the hook where a login would plug in.

## 6. Streaming: what each mode is for

`graph.stream(..., stream_mode=[...])` yields `(mode, payload)` tuples:

| Mode | Payload | Used by |
|---|---|---|
| `updates` | `{node_name: partial_state}` after each node | CLI panels, web node progress and timings |
| `values` | the full state after each step | `useStream` keeps `values` current from this |
| `custom` | whatever a node writes with `get_stream_writer()` | the analyst's tokens (`draft_delta`) |
| `messages` | LLM token chunks for message-producing nodes | not used: the analyst writes to `draft`, not `messages` |

The last row is the subtle one. Token streaming comes for free only for nodes that return
messages. The analyst returns a `draft` field, so it streams tokens itself:
`writer({"draft_delta": text})` for each chunk. The web app's `onCustomEvent` mutates
`values.draft` as they arrive; the CLI prints them dim. Interrupts appear in `updates` as a
`__interrupt__` key.

## 7. The server and the SDK: `langgraph.json`, `web/`

`langgraph dev` reads `langgraph.json`, imports the two graphs, and serves the LangGraph API:
threads, runs (streaming over SSE), state, history, store. Studio is a UI over that API.

The web app uses `@langchain/langgraph-sdk/react`'s `useStream`: it creates threads, streams
runs, keeps `values`, exposes `interrupt`, and fires `onUpdateEvent` / `onCustomEvent` /
`onMetadataEvent` callbacks. Two details that cost real debugging time: `apiUrl` must be
absolute (note 14), and the browser never talks to the server directly. A Next.js route
handler at `/api/[...path]` forwards requests, attaches the LangSmith key server-side, allows
only the endpoints the desk needs, and rate-limits by IP. That is also what makes a hosted
LangSmith Deployment a drop-in: change `LANGGRAPH_API_URL`.

## 8. LangSmith: tracing, experiments, and where to look

Set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY`, and every run becomes a trace: the graph
as the root, one span per node, one per model call with its prompt, output and token counts,
one per tool call. `config.py` loads `.env` into `os.environ` because LangSmith reads the
environment directly (an earlier version traced from Studio but not from the CLI).

Three ways this project uses it:

1. **Debugging a single run.** The web trace panel links to the run (`/api/langsmith` resolves
   the URL server-side from the run id). The CLI logs the same information to `logs/*.jsonl`
   so you can work offline; LangSmith is the version with a UI and prices.
2. **Experiments.** `evals/run_evals.py --langsmith` uploads `cases.yaml` as a dataset and runs
   `langsmith.evaluate(target, data, evaluators)`. Each evaluator returns `{key, score}`; the
   experiment page shows per-case scores over time, so a prompt change is a comparison, not a
   feeling. The first run caught two bugs the unit tests had passed over (notes 11 and 12).
3. **Measuring the judge.** `evals/run_critic_evals.py` scores the critic itself against
   labelled drafts, separately for the deterministic layer and the model layer. A judge is
   another model that can be wrong; this is how you know its false-rejection rate.

## 9. Testing a graph without an API key: `tests/test_graph_v2.py`

The three LLM factories in `nodes.py` (`planner_llm`, `analyst_llm`, `critic_llm`) are
monkeypatched with scripted stand-ins that return canned `Plan` / `AIMessage` / `Critique`
objects. Tests then assert on the **trajectory**: the graph pauses at review, feedback
re-plans, a rejected draft goes back to the analyst, the revision cap finalizes with a note,
feedback lands in the Store and is recalled on a new thread. `InMemorySaver` and
`InMemoryStore` make each test independent. The eval harness runs the same graph against the
real model and FRED, which is where integration bugs surface.

## 10. What I would tell someone starting their first graph

- Put everything a node needs in the state or the config; never in module globals.
- Return partial updates; let reducers merge. Use `add_messages` for chat history only.
- Add a checkpointer from day one, even in memory. Time travel is the best debugger you have.
- Make loops explicit with a counter in the state and a conditional edge.
- Use `interrupt()` with a payload that explains the decision; resume with `Command`.
- Compile the Studio graph without a checkpointer; the server brings its own.
- Stream `updates` for progress and `custom` for anything that is not a message.
- Turn tracing on before you need it. Then build an eval set before you trust a judge.
