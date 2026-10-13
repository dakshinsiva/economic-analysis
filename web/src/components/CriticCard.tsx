import type { Critique } from "@/lib/types";

export function CriticCard({ critique, revisions }: { critique: Critique; revisions?: number }) {
  const ok = critique.approved;
  return (
    <section className={`card border-l-4 ${ok ? "border-l-ok" : "border-l-bad"}`}>
      <header className="card-h">
        <span className={`tag ${ok ? "bg-ok/15 text-ok" : "bg-bad/15 text-bad"}`}>critic</span>
        <span className="text-sm">
          {ok ? "Every figure traces to fetched evidence." : "Draft sent back: unsupported claims found."}
          {revisions ? <span className="text-muted"> · pass {revisions}</span> : null}
        </span>
      </header>
      {!ok && (
        <ul className="px-4 py-2 text-sm list-disc pl-8 space-y-1">
          {critique.issues.map((i, k) => <li key={k}>{i}</li>)}
        </ul>
      )}
    </section>
  );
}
