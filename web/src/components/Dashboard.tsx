"use client";
import { memo, useEffect, useState } from "react";
import type { Indicator } from "@/lib/indicators";
import demo from "@/demo/indicators.json";
import registry from "@/lib/registry.json";
import { INDICATORS } from "@/lib/indicators";

const WATCH_KEY = "macrodesk.watchlist";
const DEFAULT_IDS = INDICATORS.map((i) => i.id);

function Spark({ pts, color }: { pts: number[]; color: string }) {
  const w = 96, h = 28, min = Math.min(...pts), max = Math.max(...pts), span = max - min || 1;
  const d = pts.map((v, i) => `${(i / (pts.length - 1)) * w},${h - ((v - min) / span) * (h - 4) - 2}`).join(" ");
  return (
    <svg width={w} height={h} className="shrink-0" aria-hidden>
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx={w} cy={h - ((pts[pts.length - 1] - min) / span) * (h - 4) - 2} r="2" fill={color} />
    </svg>
  );
}

const fmt = (v: number, u: string) => (u === "k" ? Math.round(v).toLocaleString() : v.toFixed(2)) + (u === "k" ? "k" : u === "%" ? "%" : u === "pp" ? " pp" : "");

function DashboardInner({ mode, onAsk, open, onToggle, onSeries }:
  { mode: "live" | "demo"; onAsk: (q: string) => void; open: boolean; onToggle: () => void; onSeries?: (id: string) => void }) {
  type Snap = { asOf: string; indicators: Indicator[]; recorded?: boolean };
  const [ids, setIds] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem(WATCH_KEY) || "null") || DEFAULT_IDS; } catch { return DEFAULT_IDS; } });
  const [editing, setEditing] = useState(false);
  const readCache = (list: string[]): Snap | null => {
    try { const c = JSON.parse(sessionStorage.getItem(`macrodesk.fred.${list.join(",")}`) || "null"); return c && Date.now() - c.at < 10 * 60e3 ? c.snap : null; } catch { return null; }
  };
  const [data, setData] = useState<Snap | null>(() => (mode === "demo" ? { ...(demo as Snap), recorded: true } : readCache(ids)));
  useEffect(() => {
    if (mode === "demo") return;
    let alive = true;
    const key = `macrodesk.fred.${ids.join(",")}`;
    const cached = readCache(ids);
    const load = async () => {
      if (cached) setData(cached);  // runs after the microtask, not synchronously in the effect
      const snap = await fetch(`/api/fred?ids=${encodeURIComponent(ids.join(","))}`).then(async (r) => (r.ok ? r.json() : { ...demo, recorded: true })).catch(() => ({ ...demo, recorded: true }));
      if (!alive) return;
      setData(snap as Snap);
      try { if (!(snap as Snap).recorded) sessionStorage.setItem(key, JSON.stringify({ at: Date.now(), snap })); } catch {}
    };
    queueMicrotask(load);
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, ids]);
  const save = (next: string[]) => { setIds(next); try { localStorage.setItem(WATCH_KEY, JSON.stringify(next)); } catch {} };
  if (!data) return (
    <section className="border-b border-line px-5 py-2">
      <div className="text-xs text-muted">▾ Macro dashboard · loading live FRED…</div>
      <div className="mt-2 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2">{ids.map((i) => <div key={i} className="h-[74px] rounded-md border border-line animate-pulse bg-line/20" />)}</div>
    </section>
  );
  return (
    <section className="border-b border-line px-5 py-2">
      <div className="flex items-center gap-2 text-xs text-muted">
        <button className="hover:text-fg" onClick={onToggle}>{open ? "▾" : "▸"} Macro dashboard</button>
        <span>· as of {data.asOf.slice(0, 10)}{data.recorded ? " (recorded snapshot)" : " (live FRED)"} · click a tile for the series card</span>
        {mode === "live" && open && <button className="ml-auto hover:text-fg" onClick={() => setEditing((e) => !e)}>{editing ? "done" : "customise"}</button>}
      </div>
      {editing && mode === "live" && (
        <div className="mt-2 flex flex-wrap gap-1 text-xs items-center">
          <span className="text-muted mr-1">watchlist:</span>
          {ids.map((i) => <button key={i} className="tag bg-line/50 text-fg font-mono normal-case hover:bg-bad/20" title="remove" onClick={() => save(ids.filter((x) => x !== i))}>{i} ×</button>)}
          <select className="input text-xs py-0.5" value="" onChange={(e) => { if (e.target.value && !ids.includes(e.target.value) && ids.length < 12) save([...ids, e.target.value]); }}>
            <option value="">+ add series</option>
            {(registry as { id: string; title: string }[]).filter((r) => !ids.includes(r.id)).map((r) => <option key={r.id} value={r.id}>{r.id} · {r.title}</option>)}
          </select>
          <button className="text-muted hover:text-fg ml-1" onClick={() => save(DEFAULT_IDS)}>reset</button>
        </div>
      )}
      {open && (
        <div className="mt-2 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2">
          {data.indicators.map((x) => {
            const up = x.change > 0;
            const good = (x.id === "UNRATE" || x.id === "PCEPILFE") ? !up : up;
            const col = x.change === 0 ? "text-muted" : good ? "text-ok" : "text-bad";
            return (
              <button key={x.id} onClick={() => onSeries ? onSeries(x.id) : onAsk(`How has ${x.label.toLowerCase()} (${x.id}) been trending, and what does it signal? Plot it since 2019.`)}
                className="text-left rounded-md border border-line px-3 py-2 hover:border-accent/60 transition-colors">
                <div className="flex items-center justify-between text-[11px] text-muted">
                  <span>{x.label}</span><span className="font-mono">{x.id}</span>
                </div>
                <div className="flex items-end justify-between gap-2 mt-0.5">
                  <div>
                    <div className="text-lg font-semibold leading-tight tabular-nums">{fmt(x.latest, x.units)}</div>
                    <div className={`text-[11px] tabular-nums ${col}`}>{x.change > 0 ? "+" : ""}{fmt(x.change, x.units)} <span className="text-muted">{x.changeLabel}</span></div>
                  </div>
                  <Spark pts={x.points} color="var(--color-accent)" />
                </div>
                <div className="text-[10px] text-muted mt-0.5">{x.date}</div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

export const Dashboard = memo(DashboardInner);
