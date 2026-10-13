# 04 - What I learned, who this is for, and what it cannot do

I built macrodesk to learn how agents are constructed and debugged, one layer at
a time, with a real data source and real failures. This is what the project
taught me, where I think a tool like this belongs, and where it stops.

## What I learned

**Grounding is verified, not prompted.** The first version had a system prompt
that said "cite every number". The model still wrote that job openings "peaked
near 12 million in 2022" from memory, uncited, having fetched only three years
of data. The number was roughly right, which is the dangerous case. A prompt
lowers the rate of unsupported claims; only a separate check makes them
detectable. The critic node, half regex and half model, is the single most
important thing in the repository.

**Make the plan data and put the human before the cost.** Structured output
turns "which series, which window" into an object a person can approve or edit
before any request is made. `interrupt()` with a descriptive payload and
`Command(resume=...)` gave me one review mechanism that works identically from
the CLI, the REST API, Studio and the web app. What the reviewer types becomes
long-term memory, which is the only memory the agent has, on purpose.

**Be deterministic wherever a model is not needed.** Fetch runs the approved
plan with no model in the loop; it cannot hallucinate and it is trivially
testable. The regex citation check never misfires. The model-based critic is
useful and noisy: before I tightened its rubric it rejected correct arithmetic
in one of six eval cases while also catching a genuine unit error. An LLM
judge is another model that can be wrong, and it has to be measured before it
is trusted as a gate.

**Tool output design matters more than prompt wording.** Every tool returns
series id, units and observation dates so the model can cite them. Errors come
back as `ERROR: ...` text so the loop self-corrects. Labelling units on the
summary line ("7,437.97, all in Thousands") removed a class of unit mistakes
that no amount of instruction had fixed.

**Most failures were environmental.** Of sixteen logged incidents, the model
was the cause of two. The rest were a gateway silently rewriting the API
endpoint, a native wheel that tried to compile Rust, a 400 from a prompt with
no user turn, a circular import, Pydantic objects in checkpointed state, two
libraries sharing one SQLite connection, a transaction mode that only failed
on a fresh file, and a relative URL handed to an SDK that needs an absolute
one. Localise before blaming the model, and keep a log: the log is the proof
of how you work.

**Convenient test doubles hide integration bugs.** The in-memory store passed
every unit test; the SQLite store failed on the first real run, twice, for two
different reasons. The eval harness, which runs the real stack, caught what
the unit tests could not. Verify fixes on empty state as well as existing state.

**Each observability layer answers a different question.** Terminal panels
show what the model saw. JSONL logs survive without any cloud. Checkpoints
make "what was the state three steps ago" a query and "re-run from there" a
fork. Studio draws it. LangSmith prices it. I needed all five at different
moments.

## Who this is for

The pattern is "planned, reviewable retrieval over a structured source, with a
critic", and macroeconomics is the demonstration, not the limit. The people it
serves are those who have to *defend* a number rather than just produce one:

- Research associates and economists at banks and asset managers writing
  morning notes and client answers, where every figure must trace to a release
  and a date.
- Policy and central-bank analysts who need the current reading, the recent
  trend and the revision caveat in one place.
- Financial journalists and graduate students who know what JOLTS is but not
  the series id, and who should see which series a question maps to.
- Teams that need an audit trail: the plan, the evidence and the verdict are
  stored per thread and can be replayed.

The same architecture fits any source with stable identifiers and release
dates: BLS and BEA tables, central-bank statistical warehouses, Eurostat,
company filings, or an internal data warehouse. The product is not the chat;
it is the approved plan, the fetched evidence and the checked answer. In a
research platform that already has the data, this is the layer that lets
someone ask in English and still get something they can sign.

## Limitations

- **Scope.** FRED only; 24 curated series plus search; no non-US macro, no
  company data, and no data vintages. "What was known in March, before the
  revision" cannot be answered without ALFRED support.
- **Description, not forecasting.** The agent reports and cautiously
  interprets. It builds no models, runs no backtests, and the critic checks
  numbers, not economic logic: a well-cited but wrong-headed argument passes.
- **The critic is partial.** It verifies citations exactly and uncited figures
  approximately. Derived claims beyond simple arithmetic are not checked, the
  model half still has false positives and negatives, and after two rejections
  the answer ships with the issues attached rather than being withheld.
- **Latency and cost.** Three to five model calls and 40 to 90 seconds per
  answer at the default effort. This is a research tool, not a chat toy.
- **The human step is both the safeguard and the bottleneck.** Auto-approval
  exists for batch use and removes the safeguard.
- **Memory is deliberately thin.** Only plan-review feedback is remembered, as
  plain text, per `user_id`. There is no account system in the web app.
- **Deployment.** Persistence is SQLite on one machine. The hosted page is a
  replay unless a LangGraph server is attached, because the backend is Python
  and the FRED key must stay server-side.
- **Evidence base.** Six eval cases are enough to catch regressions and not
  enough to quote a reliable false-rejection rate for the critic.
- **Model dependence.** Prompts were tuned against one Claude model behind one
  gateway. A different model or effort setting needs the evals re-run.
- **Data caveats carry through.** FRED release lags, seasonal adjustment and
  later revisions all apply. Nothing here is investment advice.
