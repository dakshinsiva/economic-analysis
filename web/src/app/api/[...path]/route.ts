/**
 * Passthrough to the LangGraph server.
 *
 * The browser talks to /api/*; this handler forwards to LANGGRAPH_API_URL and
 * attaches the LangSmith API key server-side, so the key never ships to the
 * client. Streaming responses (SSE from /runs/stream) are piped through.
 */
import { NextRequest } from "next/server";

const TARGET = process.env.LANGGRAPH_API_URL ?? "http://127.0.0.1:2024";

async function forward(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const url = new URL(`${TARGET.replace(/\/$/, "")}/${path.join("/")}`);
  url.search = req.nextUrl.search;

  const headers = new Headers();
  const ct = req.headers.get("content-type");
  if (ct) headers.set("content-type", ct);
  headers.set("accept", req.headers.get("accept") ?? "application/json");
  if (process.env.LANGSMITH_API_KEY) headers.set("x-api-key", process.env.LANGSMITH_API_KEY);

  const init: RequestInit & { duplex?: "half" } = { method: req.method, headers, signal: req.signal };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    init.duplex = "half";
  }

  let upstream: Response;
  try {
    upstream = await fetch(url, init);
  } catch (e) {
    return Response.json({ error: "backend_unreachable", detail: String(e) }, { status: 502 });
  }
  const out = new Headers();
  for (const k of ["content-type", "cache-control", "content-encoding"]) {
    const v = upstream.headers.get(k);
    if (v) out.set(k, v);
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
