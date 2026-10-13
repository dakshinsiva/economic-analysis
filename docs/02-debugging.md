# 02 - Debugging notes (running log)

Each entry: what broke, how it was found, what fixed it. These are the
interview stories.

## 1. `uv add` failed: hatch could not find the package
**Symptom.** `uv add ...` printed a hatch hint about `packages = ["src/foo"]` and
nothing installed.
**Cause.** I deleted `src/econ_agent` after `uv init --lib`, so the build backend
had nothing to build when resolving the project itself.
**Fix.** Explicit `[tool.hatch.build.targets.wheel] packages = ["src/econ_agent"]`
and recreate the package dir before syncing.
**Lesson.** uv builds *your* project during sync; an unbuildable project blocks
every dependency.

## 2. `cryptography` tried to compile Rust
**Symptom.** `uv sync` spent minutes downloading rustup and failed on `xcrun`.
**Cause.** `langgraph-cli[inmem]` -> `langgraph-api` -> `cryptography==50`, which
has no wheel for this macOS/Python combination.
**Fix.** `[tool.uv] constraint-dependencies = ["cryptography<46"]`.
**Lesson.** Transitive deps can drag in native builds; constraints are cheaper
than toolchains.

## 3. 404 `DeploymentNotFound` for `claude-opus-5-5`
**Symptom.** First real agent run raised `AnthropicModelNotFoundError` from
inside the `model` node (LangGraph surfaces the node name in the traceback:
`During task with name 'model'`).
**Cause.** The shell exports `ANTHROPIC_BASE_URL` pointing at a Microsoft
Foundry gateway. The Anthropic SDK honours that silently, and Foundry addresses
models by *deployment name*; the only deployment is `claude-sonnet-4-6`.
**Fix.** `Settings.model` now falls back to `ANTHROPIC_MODEL` when set.
**Lesson.** When an LLM call fails, check the SDK's environment-driven config
(`ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`) before blaming the code. Print the
host, never the key.

## 4. Model hallucinated history it never fetched
**Symptom.** In the first successful JOLTS answer the model said quits peaked
"~3.0% in late 2021" and "averaged 2.1-2.2% in 2018-2019". It only fetched data
from 2023-10 onward. The numbers happen to be roughly right, but they are from
training memory, not from FRED, and were not cited per the system prompt.
**How found.** Reading the tool-result panels against the prose. The JSONL log
confirms only two `fred.call` events.
**Status.** Open. Prompt tweaks help a little; the real fix is Stage 2's critic
node that rejects any number lacking a `(SERIES_ID, date)` citation backed by
`evidence` in state.
**Lesson.** "Grounded" is a property you verify, not a prompt you write.

## 5. Streaming loop ran the graph twice
**Symptom.** A hastily written `for node, update in graph.stream(...).__iter__() and (...)`
expression would have invoked the graph twice per turn.
**How found.** Re-reading the code before running it.
**Fix.** Plain nested loop over `graph.stream(..., stream_mode="updates")`.
**Lesson.** `stream()` is lazy; every iteration of a new generator is a new run.

## Toolkit cheat-sheet

| Question | Tool |
|---|---|
| What did the model see / call? | terminal panels; `logs/run-<thread>.jsonl` |
| What is in state right now? | `/state` -> `graph.get_state(config)` |
| What happened N steps ago? | `/history` -> `graph.get_state_history(config)` |
| Re-run from an earlier point | `/replay N` -> stream with `checkpoint_id` in config |
| Visual step-through | `uv run langgraph dev` -> Studio |
| Hosted traces, token costs | `LANGSMITH_TRACING=true` |
| Deterministic repro without the API | `tests/test_graph.py` scripted model pattern |
