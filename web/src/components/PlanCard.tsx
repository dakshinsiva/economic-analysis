"use client";
import { memo, useEffect, useRef, useState } from "react";
import type { Plan } from "@/lib/types";

function PlanCardInner({ plan, awaiting, onDecide, autoApproveIn, collapsed: collapsedDefault = false }:
  { plan: Plan; awaiting: boolean; onDecide?: (d: string) => void; autoApproveIn?: number; collapsed?: boolean }) {
  const [fb, setFb] = useState("");
  const [override, setOverride] = useState<boolean | null>(null);
  const collapsed = !awaiting && (override ?? collapsedDefault);
  // Demo autoplay: count down to approval unless the visitor touches the controls.
  // The card is keyed per run, so the initial value is enough; ticks happen in the interval.
  const [left, setLeft] = useState<number | null>(autoApproveIn ?? null);
  const leftRef = useRef<number | null>(autoApproveIn ?? null);
  const cancel = () => { leftRef.current = null; setLeft(null); };
  useEffect(() => {
    if (!awaiting || autoApproveIn === undefined) return;
    // Tick in the timer callback (outside render) so approving the parent is safe.
    const id = setInterval(() => {
      if (leftRef.current === null) { clearInterval(id); return; }
      leftRef.current -= 1;
      setLeft(leftRef.current);
      if (leftRef.current <= 0) { clearInterval(id); onDecide?.("approve"); }
    }, 1000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [awaiting, autoApproveIn]);
  return (
    <section className="card border-l-4 border-l-plan">
      <button className="card-h w-full text-left" onClick={() => !awaiting && setOverride(!collapsed)} aria-expanded={!collapsed}>
        <span className="tag bg-plan/15 text-plan">plan</span>
        <span className="text-sm text-muted truncate">{plan.goal}</span>
        {!awaiting && <span className="ml-auto text-xs text-muted shrink-0">{plan.steps.length} step{plan.steps.length === 1 ? "" : "s"} · {collapsed ? "show" : "hide"}</span>}
      </button>
      {!collapsed && <ol className="divide-y divide-line">
        {plan.steps.map((s, i) => (
          <li key={i} className="px-4 py-2 text-sm grid grid-cols-[1.5rem_1fr] gap-2">
            <span className="text-muted">{i + 1}.</span>
            <div>
              <code className="font-mono text-[13px]">{s.tool}({JSON.stringify(s.args)})</code>
              <div className="text-muted text-xs mt-0.5">{s.why}</div>
            </div>
          </li>
        ))}
      </ol>}
      {awaiting && onDecide && (
        <footer className="px-4 py-3 border-t border-line bg-plan/5 flex flex-col gap-2">
          <div className="text-sm font-medium flex items-center gap-2">
            Review the plan before any data is fetched.
            {left !== null && left > 0 && <span className="text-xs text-muted font-normal">auto-approving in {left}s, or take over</span>}
          </div>
          <div className="flex gap-2 flex-wrap">
            <button className="btn-primary" onClick={() => onDecide("approve")}>Approve</button>
            <input
              className="input flex-1 min-w-[12rem]"
              placeholder='or give feedback, e.g. "use 10 years of history and add a chart"'
              value={fb}
              onChange={(e) => { setFb(e.target.value); cancel(); }}
              onFocus={cancel}
              onKeyDown={(e) => { if (e.key === "Enter" && fb.trim()) { onDecide(fb.trim()); setFb(""); } }}
            />
            <button className="btn" disabled={!fb.trim()} onClick={() => { onDecide(fb.trim()); setFb(""); }}>Re-plan</button>
          </div>
        </footer>
      )}
    </section>
  );
}

export const PlanCard = memo(PlanCardInner);
