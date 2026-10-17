# 03 - Design decisions and trade-offs

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

## The architecture in two minutes

**The 45-second version.**

> macrodesk is a research agent over the Fed's FRED data, built so every number it
> states can be traced. A planner turns the question into a list of tool calls; a
> human approves or edits that plan before anything runs; fetch executes it with no
> model in the loop; an analyst writes from the fetched evidence only; and a critic
> checks the draft, deterministically for citations and numbers, with a model for
> prose, and sends it back if anything isn't supported. It's a LangGraph state graph
> with checkpoints, so every run can be inspected and replayed, and an eval harness
> measures it in LangSmith: 24 questions, tool choice and grounding at 1.0, critic
> approval at 1.0.

**The three-minute walk.** Problem first: models are fluent about the economy and
will cite a 2022 peak from memory; mine did, and the number was roughly right,
which is the dangerous case. Then the pipeline left to right, one sentence per
node, stopping on the two choices that matter: the plan is *data* so a person can
approve it, and fetch has *no model* so it cannot hallucinate. Then the critic: two
deterministic checks that never misfire, and a model layer that cannot overrule a
number the regex verified, measured at 0.71 precision before scoping and 1.0
after. Finish with operations: checkpoints give time travel, the Store remembers
plan edits, LangSmith gives traces and experiments, and the debugging log has 21
incidents with symptom, localisation and fix.

**Decisions to defend.**
- *Why a hand-built graph over the prebuilt agent?* Both are kept. The prebuilt
  loop lets the model decide everything; the graph separates deciding, approving,
  doing, writing and checking, so each is testable and observable. The prebuilt
  agent shipped a wrong citation year in an end-to-end test; the graph's check
  rejects it.
- *Why interrupt for a human?* The plan is where cost and risk are decided.
  `interrupt()` with a payload, `Command(resume=...)` to continue; one path for
  CLI, API, Studio and web.
- *Why not just a better prompt?* A prompt lowers the rate; a critic makes it
  detectable; then the critic has to be measured, because a judge is another model
  that can be wrong.
- *What breaks?* Two stories from the log: the shared SQLite connection that passed
  unit tests and failed on the first real run; the whitelist that let "3.0% peak"
  through until a labelled set exposed it.

**Numbers to have ready.** 18 tools, 24 eval cases, grounding 1.00, critic approval
1.00, critic layers at precision and recall 1.0 on labelled drafts, 10 to 45
seconds per answer, 48 offline tests, 21 logged incidents.

**One habit.** When asked about LangGraph, answer with the mechanism, not the
brand: state plus reducers, nodes returning partial updates, a checkpoint after
every step, interrupts for humans, a Store for cross-thread memory.

