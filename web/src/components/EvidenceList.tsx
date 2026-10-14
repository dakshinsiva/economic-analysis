"use client";
import { memo, useState } from "react";
import type { Evidence } from "@/lib/types";
import { parseEvidence } from "@/lib/evidenceTable";

function Result({ text, muted }: { text: string; muted?: boolean }) {
  const [raw, setRaw] = useState(false);
  const parsed = raw ? null : parseEvidence(text);
  if (!parsed) return <pre className={`px-4 pb-1 text-xs font-mono whitespace-pre-wrap ${muted ? "text-fg/80" : "text-fg/90"} max-h-72 overflow-auto`}>{text}</pre>;
  return (
    <div className="px-4 pb-1 text-xs">
      {parsed.pre && <pre className="font-mono whitespace-pre-wrap text-fg/80 mb-1">{parsed.pre}</pre>}
      <div className="max-h-72 overflow-auto rounded border border-line">
        <table className="w-full font-mono tabular-nums">
          {parsed.header && <thead className="bg-line/30 text-muted"><tr>{parsed.header.map((h, i) => <th key={i} className={`px-2 py-1 font-medium ${i ? "text-right" : "text-left"}`}>{h}</th>)}</tr></thead>}
          <tbody>
            {parsed.rows.map((r, i) => <tr key={i} className="odd:bg-line/10">{r.map((c, k) => <td key={k} className={`px-2 py-0.5 ${k ? "text-right" : "text-left text-muted"}`}>{c}</td>)}</tr>)}
          </tbody>
        </table>
      </div>
      {parsed.post && <pre className="font-mono whitespace-pre-wrap text-fg/80 mt-1">{parsed.post}</pre>}
      <button className="text-[11px] text-muted hover:text-fg mt-1" onClick={() => setRaw(true)}>raw</button>
    </div>
  );
}

function EvidenceListInner({ evidence, prior = [], collapsed: collapsedDefault = false }:
  { evidence: Evidence[]; prior?: Evidence[]; collapsed?: boolean }) {
  const [override, setOverride] = useState<boolean | null>(null);
  const collapsed = override ?? collapsedDefault;
  const failed = evidence.filter((e) => !e.ok).length;
  const copy = (text: string) => navigator.clipboard?.writeText(text);
  return (
    <section className="card border-l-4 border-l-evidence">
      <button className="card-h w-full text-left" onClick={() => setOverride(!collapsed)} aria-expanded={!collapsed}>
        <span className="tag bg-evidence/15 text-evidence">evidence</span>
        <span className="text-sm text-muted">{evidence.length} tool result{evidence.length === 1 ? "" : "s"}, fetched deterministically from FRED{failed ? ` · ${failed} failed` : ""}{prior.length ? ` · ${prior.length} carried over from earlier in this thread` : ""}</span>
        <span className="ml-auto text-xs text-muted shrink-0">{collapsed ? "show" : "hide"}</span>
      </button>
      {!collapsed && <div className="divide-y divide-line">
        {evidence.map((e, i) => (
          <details key={i} className="group" open={i === 0}>
            <summary className="px-4 py-2 text-sm cursor-pointer flex items-center gap-2 select-none">
              <span className={`h-2 w-2 rounded-full ${e.ok ? "bg-ok" : "bg-bad"}`} />
              <code className="font-mono text-[13px]">{e.tool}({JSON.stringify(e.args)})</code>
            </summary>
            <Result text={e.result} />
            <div className="px-4 pb-2"><button className="btn text-[11px]" onClick={() => copy(e.result)}>copy</button></div>
          </details>
        ))}
        {prior.map((e, i) => (
          <details key={"p" + i} className="group opacity-80">
            <summary className="px-4 py-2 text-sm cursor-pointer flex items-center gap-2 select-none">
              <span className="h-2 w-2 rounded-full bg-muted" />
              <code className="font-mono text-[13px]">{e.tool}({JSON.stringify(e.args)})</code>
              <span className="text-[11px] text-muted ml-1">earlier in this thread</span>
            </summary>
            <Result text={e.result} muted />
          </details>
        ))}
      </div>}
    </section>
  );
}

export const EvidenceList = memo(EvidenceListInner);
