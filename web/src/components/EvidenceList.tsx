"use client";
import { useState } from "react";
import type { Evidence } from "@/lib/types";

export function EvidenceList({ evidence, collapsed: collapsedDefault = false }: { evidence: Evidence[]; collapsed?: boolean }) {
  const [override, setOverride] = useState<boolean | null>(null);
  const collapsed = override ?? collapsedDefault;
  const failed = evidence.filter((e) => !e.ok).length;
  return (
    <section className="card border-l-4 border-l-evidence">
      <button className="card-h w-full text-left" onClick={() => setOverride(!collapsed)} aria-expanded={!collapsed}>
        <span className="tag bg-evidence/15 text-evidence">evidence</span>
        <span className="text-sm text-muted">{evidence.length} tool result{evidence.length === 1 ? "" : "s"}, fetched deterministically from FRED{failed ? ` · ${failed} failed` : ""}</span>
        <span className="ml-auto text-xs text-muted shrink-0">{collapsed ? "show" : "hide"}</span>
      </button>
      {!collapsed && <div className="divide-y divide-line">
        {evidence.map((e, i) => (
          <details key={i} className="group" open={i === 0}>
            <summary className="px-4 py-2 text-sm cursor-pointer flex items-center gap-2 select-none">
              <span className={`h-2 w-2 rounded-full ${e.ok ? "bg-ok" : "bg-bad"}`} />
              <code className="font-mono text-[13px]">{e.tool}({JSON.stringify(e.args)})</code>
            </summary>
            <pre className="px-4 pb-3 text-xs font-mono whitespace-pre-wrap text-fg/90 max-h-72 overflow-auto">{e.result}</pre>
          </details>
        ))}
      </div>}
    </section>
  );
}
