"use client";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { citedSeries, linkCitations } from "@/lib/cite";

export function Answer({ text, draft, onFollowUp, followUps, streaming, onSeries }:
  { text: string; draft?: boolean; onFollowUp?: (q: string) => void; followUps?: string[]; streaming?: boolean; onSeries?: (id: string) => void }) {
  const [copied, setCopied] = useState(false);
  // Belt and braces: the analyst is told not to emit file paths, but strip any that slip through.
  const clean = text
    .replace(/^.*File path.*$/gm, "")                 // "**File path:** `/.../x.png`"
    .replace(/^#+\s*(?:[^\w\s]\s*)?Chart\s*$/gm, "")   // a heading that only says "Chart"
    .replace(/^.*outputs\/.*\.png.*$/gm, "")           // any other stray path line
    .replace(/\n{3,}/g, "\n\n").trim();
  const ids = citedSeries(clean);
  const download = () => {
    const blob = new Blob([clean], { type: "text/markdown" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = `macrodesk-${new Date().toISOString().slice(0, 10)}.md`; a.click(); URL.revokeObjectURL(a.href);
  };
  return (
    <section className={`card border-l-4 ${draft ? "border-l-muted" : "border-l-accent"}`}>
      <header className="card-h">
        <span className={`tag ${draft ? "bg-muted/15 text-muted" : "bg-accent/15 text-accent"}`}>{draft ? "draft" : "answer"}</span>
        {draft ? <span className="text-sm text-muted">{streaming ? "writing from the evidence…" : "awaiting the critic"}</span> : <span className="text-sm text-muted hidden md:inline">every figure cites (series, date); links open FRED</span>}
        {!draft && (
          <span className="ml-auto flex gap-1">
            <button className="btn text-xs" onClick={() => { navigator.clipboard.writeText(clean); setCopied(true); setTimeout(() => setCopied(false), 1200); }}>{copied ? "copied" : "copy md"}</button>
            <button className="btn text-xs" onClick={download}>download</button>
          </span>
        )}
      </header>
      <div className={`prose px-4 py-3 ${streaming ? "streaming" : ""}`}>
        <ReactMarkdown components={{ a: (p) => <a {...p} target="_blank" rel="noreferrer" className="text-accent underline-offset-2 hover:underline" /> }}>
          {linkCitations(clean)}
        </ReactMarkdown>
      </div>
      {!draft && (ids.length > 0 || followUps?.length) && (
        <footer className="px-4 py-3 border-t border-line flex flex-col gap-2">
          {ids.length > 0 && (
            <div className="flex flex-wrap items-center gap-1 text-xs">
              <span className="text-muted mr-1">sources</span>
              {ids.map((id) => onSeries
                ? <button key={id} className="tag bg-line/50 text-fg hover:bg-line font-mono normal-case" onClick={() => onSeries(id)} title="series card">{id}</button>
                : <a key={id} className="tag bg-line/50 text-fg hover:bg-line font-mono normal-case" href={`https://fred.stlouisfed.org/series/${id}`} target="_blank" rel="noreferrer">{id} ↗</a>)}
            </div>
          )}
          {onFollowUp && followUps?.length ? (
            <div className="flex flex-wrap items-center gap-1 text-xs">
              <span className="text-muted mr-1">follow up</span>
              {followUps.map((f) => <button key={f} className="btn text-xs" onClick={() => onFollowUp(f)}>{f}</button>)}
            </div>
          ) : null}
        </footer>
      )}
    </section>
  );
}
