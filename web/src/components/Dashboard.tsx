"use client";
import { useEffect, useState } from "react";
import type { Indicator } from "@/lib/indicators";
import demo from "@/demo/indicators.json";

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

export function Dashboard({ mode, onAsk }: { mode: "live" | "demo"; onAsk: (q: string) => void }) {
  type Snap = { asOf: string; indicators: Indicator[]; recorded?: boolean };
  const [data, setData] = useState<Snap | null>(mode === "demo" ? { ...(demo as Snap), recorded: true } : null);
  const [open, setOpen] = useState(true);
  useEffect(() => {
    if (mode === "demo") return;
    let alive = true;
    fetch("/api/fred").then(async (r) => (r.ok ? r.json() : { ...demo, recorded: true })).catch(() => ({ ...demo, recorded: true }))
      .then((snap) => { if (alive) setData(snap as Snap); });
    return () => { alive = false; };
  }, [mode]);
  if (!data) return null;
  return (
    <section className="border-b border-line px-5 py-2">
      <div className="flex items-center gap-2 text-xs text-muted">
        <button className="hover:text-fg" onClick={() => setOpen((o) => !o)}>{open ? "▾" : "▸"} Macro dashboard</button>
        <span>· as of {data.asOf.slice(0, 10)}{data.recorded ? " (recorded snapshot)" : " (live FRED)"} · click a tile to ask about it</span>
      </div>
      {open && (
        <div className="mt-2 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2">
          {data.indicators.map((x) => {
            const up = x.change > 0;
            const good = (x.id === "UNRATE" || x.id === "PCEPILFE") ? !up : up;
            const col = x.change === 0 ? "text-muted" : good ? "text-ok" : "text-bad";
            return (
              <button key={x.id} onClick={() => onAsk(`How has ${x.label.toLowerCase()} (${x.id}) been trending, and what does it signal? Plot it since 2019.`)}
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
