"use client";
import { useState } from "react";
import type { AgentState, NodeName } from "@/lib/types";

export type NodeTiming = { node: NodeName | "submitted" | "resumed"; at: number };

export function Trace({ timings, values }: { timings: NodeTiming[]; values: AgentState }) {
  const [open, setOpen] = useState(false);
  if (!timings.length) return null;
  const t0 = timings[0].at;
  return (
    <section className="card">
      <button className="card-h w-full text-left" onClick={() => setOpen((o) => !o)}>
        <span className="tag bg-line/60 text-fg">trace</span>
        <span className="text-sm text-muted">{timings.filter((t) => t.node !== "submitted" && t.node !== "resumed").length} nodes · {(((timings[timings.length - 1].at - t0) / 1000) || 0).toFixed(1)}s wall clock incl. review wait · {open ? "hide" : "show"} raw state</span>
      </button>
      <ol className="px-4 py-2 text-xs font-mono grid grid-cols-[6rem_1fr] gap-x-3 gap-y-0.5">
        {timings.map((t, i) => {
          const prev = timings[i - 1];
          const took = prev ? ((t.at - prev.at) / 1000).toFixed(1) + "s" : null;
          const marker = t.node === "submitted" || t.node === "resumed";
          return (
            <li key={i} className="contents">
              <span className="text-muted">+{((t.at - t0) / 1000).toFixed(1)}s</span>
              <span className={marker ? "text-muted" : ""}>
                {marker ? `(${t.node})` : `${t.node} done`}
                {took && !marker ? <span className="text-muted"> · {t.node === "review" ? "waited " : ""}{took}</span> : null}
              </span>
            </li>
          );
        })}
      </ol>
      {open && (
        <pre className="px-4 pb-3 text-[11px] font-mono whitespace-pre-wrap max-h-96 overflow-auto text-fg/80 border-t border-line pt-2">
          {JSON.stringify({ ...values, messages: values.messages?.map((m) => ({ type: m.type, content: typeof m.content === "string" ? m.content.slice(0, 120) + "…" : m.content })) }, null, 1)}
        </pre>
      )}
    </section>
  );
}
