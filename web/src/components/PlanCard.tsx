"use client";
import { useState } from "react";
import type { Plan } from "@/lib/types";

export function PlanCard({ plan, awaiting, onDecide }:
  { plan: Plan; awaiting: boolean; onDecide?: (d: string) => void }) {
  const [fb, setFb] = useState("");
  return (
    <section className="card border-l-4 border-l-plan">
      <header className="card-h">
        <span className="tag bg-plan/15 text-plan">plan</span>
        <span className="text-sm text-muted">{plan.goal}</span>
      </header>
      <ol className="divide-y divide-line">
        {plan.steps.map((s, i) => (
          <li key={i} className="px-4 py-2 text-sm grid grid-cols-[1.5rem_1fr] gap-2">
            <span className="text-muted">{i + 1}.</span>
            <div>
              <code className="font-mono text-[13px]">{s.tool}({JSON.stringify(s.args)})</code>
              <div className="text-muted text-xs mt-0.5">{s.why}</div>
            </div>
          </li>
        ))}
      </ol>
      {awaiting && onDecide && (
        <footer className="px-4 py-3 border-t border-line bg-plan/5 flex flex-col gap-2">
          <div className="text-sm font-medium">Review the plan before any data is fetched.</div>
          <div className="flex gap-2 flex-wrap">
            <button className="btn-primary" onClick={() => onDecide("approve")}>Approve</button>
            <input
              className="input flex-1 min-w-[12rem]"
              placeholder='or give feedback, e.g. "use 10 years of history and add a chart"'
              value={fb}
              onChange={(e) => setFb(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && fb.trim()) { onDecide(fb.trim()); setFb(""); } }}
            />
            <button className="btn" disabled={!fb.trim()} onClick={() => { onDecide(fb.trim()); setFb(""); }}>Re-plan</button>
          </div>
        </footer>
      )}
    </section>
  );
}
