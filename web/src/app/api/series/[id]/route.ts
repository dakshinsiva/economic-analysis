/**
 * Series card data: metadata plus the last observations, server-side with the FRED key.
 * GET /api/series/UNRATE?n=120
 */
import { NextRequest } from "next/server";
import registry from "@/lib/registry.json";

type Obs = { date: string; value: string };
const KEY = () => process.env.FRED_API_KEY ?? "";

async function fred(path: string, params: Record<string, string>) {
  const u = new URL(`https://api.stlouisfed.org/fred/${path}`);
  Object.entries({ api_key: KEY(), file_type: "json", ...params }).forEach(([k, v]) => u.searchParams.set(k, v));
  const r = await fetch(u, { next: { revalidate: 3600 } });
  if (!r.ok) throw new Error(`FRED ${path} ${r.status}`);
  return r.json();
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id: raw } = await ctx.params;
  const id = raw.toUpperCase();
  const n = Math.min(400, Math.max(12, Number(req.nextUrl.searchParams.get("n") ?? 120)));
  const known = (registry as { id: string; title: string; units: string; frequency: string; reading: string }[]).find((s) => s.id === id);
  if (!KEY()) return Response.json({ id, known: known ?? null, error: "FRED_API_KEY not set" }, { status: 503 });
  try {
    const [info, obs] = await Promise.all([
      fred("series", { series_id: id }),
      fred("series/observations", { series_id: id, sort_order: "desc", limit: String(n) }),
    ]);
    const s = info.seriess?.[0];
    if (!s) return Response.json({ id, error: "unknown series" }, { status: 404 });
    const points = (obs.observations as Obs[]).filter((o) => o.value !== ".").map((o) => ({ d: o.date, v: Number(o.value) })).reverse();
    const last = points[points.length - 1];
    const freq = (s.frequency_short as string) || "M";
    const back = freq === "D" ? 63 : freq === "W" ? 13 : freq === "Q" ? 4 : 12;
    const prev = points[Math.max(0, points.length - 1 - back)];
    return Response.json({
      id, title: s.title, units: s.units_short, frequency: freq, seasonal: s.seasonal_adjustment_short,
      last_updated: s.last_updated, observation_end: s.observation_end, popularity: s.popularity,
      notes: (s.notes as string | undefined)?.slice(0, 600) ?? "", reading: known?.reading ?? null,
      latest: last, change: last && prev ? +(last.v - prev.v).toFixed(3) : null, changeLabel: `vs ${back} obs ago`,
      points,
    });
  } catch (e) {
    return Response.json({ id, error: String(e) }, { status: 502 });
  }
}
