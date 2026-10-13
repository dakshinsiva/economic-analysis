# 03 - Interview talking points (draft, grows with each stage)

- **Why LangGraph over a plain loop?** Persistence (checkpointer -> threads,
  time travel), interrupts for human-in-the-loop, streaming of per-node updates,
  and a graph you can draw. For Stage 1 the prebuilt `create_agent` gives all of
  this for free; Stage 2 shows I can build the `StateGraph` by hand.
- **Tool design matters more than prompt design.** Compact outputs with ids,
  units and dates; errors returned as text so the loop self-corrects.
- **Testing agents.** Scripted fake model + trajectory assertions; recorded
  fixtures for data; no network in CI.
- **Grounding is verified, not assumed.** See debugging note 4.
- **Environment-driven failures** (base URL gateway, native wheels) are the
  most common real-world blockers; know how to localise them fast.

## Stage 2 additions
- **Prebuilt vs hand-built.** `create_agent` = one model node + tool node; the
  model decides everything. The v2 graph separates *deciding* (planner),
  *approving* (human), *doing* (fetch, no LLM), *writing* (analyst) and
  *checking* (critic). Each is independently testable and observable.
- **Human-in-the-loop done right.** `interrupt()` inside a node with a
  descriptive payload; resume with `Command(resume=...)`. Same code path for
  CLI, REST and Studio.
- **Why a critic and not just a better prompt.** Prompts reduce the rate of
  unsupported claims; the critic makes them *detectable*. The regex half is
  free and exact; the LLM half handles judgement. Debugging notes 4 and 10
  are the before/after.
- **Cost of Stage 2.** Three model calls minimum (planner, analyst, critic)
  vs one or two for v1. Worth it when correctness matters more than latency;
  `--v1` stays available for quick lookups.

## Stage 3 additions
- **Checkpointer vs Store.** Thread memory vs user memory; different lifetimes,
  different namespaces. The only thing stored is plan feedback, which is both
  high-signal and cheap to apply.
- **Evals before trust.** The critic looked great in demos and still rejected
  correct arithmetic 1 time in 6. You find that with a harness, not by reading
  transcripts. Scores live next to the code and in LangSmith experiments.
- **Integration bugs hide behind convenient doubles.** `InMemoryStore` passed;
  `SqliteStore` on a shared connection did not. (Debugging note 11.)

See also [04-reflections.md](04-reflections.md): what I learned, the market, the limitations.

## The "build everything" pass
- **Deterministic beats judged, where possible.** The numeric grounding check is a
  few dozen lines of regex and arithmetic. Calibrated on twenty recorded drafts
  (zero false positives) and measured on a labelled set (precision 1.0, recall
  1.0 for the deterministic layer). The model critic still matters for prose
  claims; the deterministic layer makes the gate predictable.
- **Validate at the tool boundary.** Structured output guaranteed a well-formed
  plan and still produced an impossible step. The fix was the tool's own schema,
  applied before execution, with one retry.
- **Context is not evidence.** Showing the analyst the previous answer taught it
  to cite the previous answer. Carrying forward the previous *evidence* fixed the
  behaviour and made follow-ups cheaper.
- **Vintages change the product.** `series_as_of` and `revision_history` let the
  desk answer "what was known then" and "how much was it revised", which is the
  question practitioners actually argue about.
- **Persistence is an interface.** SQLite and Postgres behind one factory; the
  graph never knew which it had. Verified against a real Postgres in Docker, after
  two SQLite transaction bugs taught me not to trust in-memory doubles.
- **A public API surface should be narrow.** The passthrough allows nine endpoint
  shapes and rate-limits by IP; the general server behind it stays general.

