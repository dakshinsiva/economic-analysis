/**
 * Indicator snapshot for the dashboard strip. Runs server-side with FRED_API_KEY
 * (never exposed to the browser). Each upstream fetch is cached for an hour; FRED data moves daily at most.
 */
import { INDICATORS, type Indicator } from "@/lib/indicators";
import registry from "@/lib/registry.json";
import { NextRequest } from "next/server";

type Reg = { id: string; title: string; units: string; frequency: string };
const REG = registry as Reg[];
const MAX_IDS = 12;

/** Watchlist entries for arbitrary ids: label/units from the registry, else from the id. */
function specFor(ids: string[]) {
  return ids.map((id) => {
    const k = INDICATORS.find((x) => x.id === id);
    if (k) return k;
    const reg = REG.find((x) => x.id === id);
    const freq = (reg?.frequency ?? "M") as Indicator["freq"];
    const index = /^Index/i.test(reg?.units ?? "");
    return { id, label: reg?.title?.replace(/\s*\(.*?\)\s*/g, " ").trim().slice(0, 22) ?? id,
             units: index ? "%" : reg?.units?.includes("Percent") ? "%" : reg?.units?.includes("Thousands") ? "k" : "",
             freq, changeLabel: freq === "D" ? "vs 3m ago" : freq === "Q" ? "vs prev qtr" : freq === "W" ? "vs 13w ago" : "vs 12m ago", yoy: index };
  });
}

type Obs = { date: string; value: string };

async function series(id: string, start: string): Promise<Obs[]> {
  const u = new URL("https://api.stlouisfed.org/fred/series/observations");
  u.searchParams.set("series_id", id);
  u.searchParams.set("api_key", process.env.FRED_API_KEY ?? "");
  u.searchParams.set("file_type", "json");
  u.searchParams.set("observation_start", start);
  const r = await fetch(u, { next: { revalidate: 3600 } });
  if (!r.ok) throw new Error(`FRED ${id} ${r.status}`);
  const j = (await r.json()) as { observations: Obs[] };
  return j.observations.filter((o) => o.value !== ".");
}

export async function GET(req: NextRequest) {
  if (!process.env.FRED_API_KEY) return Response.json({ error: "FRED_API_KEY not set" }, { status: 503 });
  const start = new Date(Date.now() - 3 * 365 * 86400e3).toISOString().slice(0, 10);
  const idsParam = req.nextUrl.searchParams.get("ids");
  const ids = idsParam ? idsParam.toUpperCase().split(",").map((x) => x.trim()).filter(Boolean).slice(0, MAX_IDS) : INDICATORS.map((m) => m.id);
  try {
    const out: Indicator[] = await Promise.all(specFor(ids).map(async (m) => {
      let obs = await series(m.id, start);
      if (m.id === "PCEPILFE" || (m as { yoy?: boolean }).yoy) {
        // index -> YoY % change
        const byDate = new Map(obs.map((o) => [o.date, Number(o.value)]));
        obs = obs.flatMap((o) => {
          const d = new Date(o.date); d.setUTCFullYear(d.getUTCFullYear() - 1);
          const prev = byDate.get(d.toISOString().slice(0, 10));
          return prev ? [{ date: o.date, value: ((Number(o.value) / prev - 1) * 100).toFixed(2) }] : [];
        });
      }
      const vals = obs.map((o) => Number(o.value));
      const last = vals[vals.length - 1];
      const back = m.freq === "D" ? 63 : m.freq === "W" ? 13 : m.freq === "Q" ? 1 : 12;
      const prev = vals[Math.max(0, vals.length - 1 - back)];
      const tail = m.freq === "D" ? vals.slice(-250) : vals.slice(-36);
      return { id: m.id, label: m.label, units: m.units, freq: m.freq, latest: last, date: obs[obs.length - 1].date,
               change: +(last - prev).toFixed(2), changeLabel: m.changeLabel, points: tail };
    }));
    return Response.json({ asOf: new Date().toISOString(), indicators: out });
  } catch (e) {
    return Response.json({ error: String(e) }, { status: 502 });
  }
}
