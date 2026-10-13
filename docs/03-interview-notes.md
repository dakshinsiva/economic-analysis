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
