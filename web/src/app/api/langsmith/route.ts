/**
 * Resolve a LangSmith trace URL for a run id. The API key stays server-side; the browser only
 * ever sees the resulting URL. Returns {url: null} when tracing is not configured.
 */
import { NextRequest } from "next/server";

export async function GET(req: NextRequest) {
  const runId = req.nextUrl.searchParams.get("run_id");
  const key = process.env.LANGSMITH_API_KEY;
  const project = process.env.LANGSMITH_PROJECT ?? "macrodesk";
  if (!runId || !key) return Response.json({ url: null });
  try {
    const h = { "x-api-key": key };
    const org = await fetch("https://api.smith.langchain.com/api/v1/orgs/current", { headers: h, cache: "no-store" }).then((r) => r.json());
    const sessions = await fetch(`https://api.smith.langchain.com/api/v1/sessions?name=${encodeURIComponent(project)}`, { headers: h, cache: "no-store" }).then((r) => r.json());
    const session = Array.isArray(sessions) ? sessions[0] : null;
    if (!org?.id || !session?.id) return Response.json({ url: null });
    return Response.json({ url: `https://smith.langchain.com/o/${org.id}/projects/p/${session.id}/r/${runId}?poll=true` });
  } catch {
    return Response.json({ url: null });
  }
}
