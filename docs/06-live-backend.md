# 06 - Attaching a live backend to the hosted desk

The Vercel site replays a recording until it can reach a LangGraph server. Everything on the
web side is already wired for a live one: the `/api/[...path]` passthrough forwards to
`LANGGRAPH_API_URL`, attaches `LANGSMITH_API_KEY` server-side, allows only the endpoints the
desk uses, and rate-limits per IP. What remains is hosting the Python graph somewhere the
internet can reach, which needs an account login, so it is a ten-minute job for the owner.

## Option A: LangSmith Deployment (recommended)

1. In LangSmith (smith.langchain.com) open **Deployments → New deployment**, connect the
   GitHub account, and pick `dakshinsiva/macrodesk`, branch `main`. The config path is the
   repo root `langgraph.json`; it registers two graphs, `macrodesk` (Stage 2) and
   `macrodesk_v1`.
2. Environment variables for the deployment: `FRED_API_KEY`, `ANTHROPIC_API_KEY`
   (and `ANTHROPIC_BASE_URL` + `ECON_MODEL` if you route through a gateway),
   `LANGSMITH_PROJECT=macrodesk`. Tracing is on by default inside a deployment.
3. Deploy. Copy the deployment's API URL.
4. On Vercel, project `macrodesk`: set `LANGGRAPH_API_URL` to that URL and
   `LANGSMITH_API_KEY` to a LangSmith key with access to the deployment; optionally
   `FRED_API_KEY` for the live dashboard and `LANGSMITH_PROJECT` for trace links. Redeploy.
5. Open the site: the badge reads **live backend**, questions run for real, and threads,
   remembered feedback and the trace link all work.

The checkpointer and Store are provided by the deployment, so `DATABASE_URL` is not needed.

## Option B: your own container

```bash
pip install "langgraph-cli[inmem]"
langgraph build -t macrodesk-server          # Docker image from langgraph.json
# run it anywhere with Postgres + Redis per the LangGraph self-hosting docs, then set
# LANGGRAPH_API_URL on Vercel to its public URL
```

For a multi-process self-hosted setup, point `DATABASE_URL` at Postgres so the CLI and the
server share threads and memory (`persistence.py`; verified against Postgres 16).

## Verifying

```bash
curl -s https://macrodesk-agent.vercel.app/api/info          # 200 with a live backend, 502 without
curl -s -X POST https://macrodesk-agent.vercel.app/api/assistants   # 403: not on the allowlist
```

## Budget guard

The passthrough's limiter is 30 requests per IP, then one every four seconds, per function
instance. For a public demo also set a monthly spend cap on the model account; a question costs
three to five model calls.
