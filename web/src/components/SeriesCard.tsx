"use client";
/** A series at a glance: latest value and change, sparkline, metadata, one-click actions. Esc closes. */
import { useEffect, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import registry from "@/lib/registry.json";

type Card = { id: string; title?: string; units?: string; frequency?: string; seasonal?: string; last_updated?: string;
  observation_end?: string; notes?: string; reading?: string | null; latest?: { d: string; v: number }; change?: number | null;
  changeLabel?: string; points?: { d: string; v: number }[]; error?: string; known?: { title: string; units: string; reading: string } | null };

export function SeriesCard({ id, onClose, onAsk }: { id: string; onClose: () => void; onAsk: (q: string) => void }) {
  const [card, setCard] = useState<Card | null>(null);
  useEffect(() => {
    let alive = true;
    fetch(`/api/series/${encodeURIComponent(id)}`).then(async (r) => ({ ok: r.ok, body: await r.json() }))
      .then(({ body }) => { if (alive) setCard(body); }).catch(() => { if (alive) setCard({ id, error: "unreachable" }); });
    return () => { alive = false; };
  }, [id]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const reg = (registry as { id: string; title: string; units: string; reading: string }[]).find((s) => s.id === id);
  const title = card?.title ?? reg?.title ?? id;
  const pts = card?.points ?? [];
  return (
    <div className="fixed inset-0 z-40 bg-black/50 flex items-start justify-center p-4 pt-[8vh]" onMouseDown={onClose} role="dialog" aria-modal="true" aria-label={`${id} series card`}>
      <div className="card w-full max-w-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <header className="card-h">
          <span className="tag bg-chart/15 text-chart font-mono normal-case">{id}</span>
          <span className="text-sm truncate">{title}</span>
          <span className="ml-auto text-xs text-muted">{card?.units ?? reg?.units} · {card?.frequency ?? ""}{card?.seasonal ? ` · ${card.seasonal}` : ""}</span>
          <button className="btn text-xs" onClick={onClose} aria-label="close">esc</button>
        </header>
        {!card && <div className="px-4 py-6 text-sm text-muted">loading…</div>}
        {card?.error && (
          <div className="px-4 py-3 text-sm">
            <div className="text-muted">Live series data needs <code>FRED_API_KEY</code> on the server ({card.error}).</div>
            {reg && <div className="mt-2 text-sm">{reg.reading}</div>}
          </div>
        )}
        {card && !card.error && (
          <>
            <div className="px-4 pt-3 flex items-end gap-6 flex-wrap">
              <div>
                <div className="text-3xl font-semibold tabular-nums leading-none">{card.latest?.v.toLocaleString(undefined, { maximumFractionDigits: 2 })}</div>
                <div className="text-xs text-muted mt-1">{card.latest?.d} · {card.units}</div>
              </div>
              {card.change !== null && card.change !== undefined && (
                <div className={`text-sm tabular-nums ${card.change > 0 ? "text-ok" : card.change < 0 ? "text-bad" : "text-muted"}`}>
                  {card.change > 0 ? "+" : ""}{card.change.toLocaleString(undefined, { maximumFractionDigits: 2 })} <span className="text-muted">{card.changeLabel}</span>
                </div>
              )}
              <div className="ml-auto text-[11px] text-muted text-right">last updated {card.last_updated?.slice(0, 10)}<br />observations through {card.observation_end}</div>
            </div>
            <div className="px-2">
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={pts.map((p) => ({ t: new Date(p.d).getTime(), v: p.v }))} margin={{ top: 12, right: 16, bottom: 0, left: 0 }}>
                  <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tickFormatter={(t) => new Date(t).getUTCFullYear().toString()} tick={{ fontSize: 10, fill: "var(--color-muted)" }} axisLine={{ stroke: "var(--color-line)" }} tickLine={false} />
                  <YAxis width={48} tick={{ fontSize: 10, fill: "var(--color-muted)" }} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
                  <Tooltip contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-line)", fontSize: 12 }} labelFormatter={(t) => new Date(Number(t)).toISOString().slice(0, 10)} formatter={(v) => [Number(v).toLocaleString(), id]} />
                  <Line type="monotone" dataKey="v" stroke="var(--color-accent)" strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {(card.reading || card.notes) && <p className="px-4 pb-2 text-xs text-muted leading-relaxed">{card.reading ?? card.notes}</p>}
          </>
        )}
        <footer className="px-4 py-2 border-t border-line flex gap-2 flex-wrap text-xs">
          <button className="btn-primary text-xs" onClick={() => { onClose(); onAsk(`What is the latest ${title} (${id}) and what does its trend signal?`); }}>Ask about {id}</button>
          <button className="btn text-xs" onClick={() => { onClose(); onAsk(`Plot ${id} since 2015 with recession shading and summarise the trend.`); }}>Plot</button>
          <button className="btn text-xs" onClick={() => { onClose(); onAsk(`How much has ${id} been revised recently and when is its next release?`); }}>Revisions & next release</button>
          <a className="btn text-xs ml-auto" href={`https://fred.stlouisfed.org/series/${id}`} target="_blank" rel="noreferrer">FRED ↗</a>
        </footer>
      </div>
    </div>
  );
}
