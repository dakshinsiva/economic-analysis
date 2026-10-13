"use client";
import type { Thread } from "@langchain/langgraph-sdk";

export type Pref = { text: string; ts: string };

export function Sidebar({ threads, currentId, onPick, onNew, prefs, mode }:
  { threads: Thread[]; currentId: string | null; onPick: (id: string) => void; onNew: () => void; prefs: Pref[]; mode: "live" | "demo" }) {
  return (
    <aside className="w-64 shrink-0 border-r border-line hidden lg:flex flex-col gap-6 p-4 text-sm overflow-y-auto">
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold">Threads</h2>
          <button className="btn text-xs" onClick={onNew}>new</button>
        </div>
        {mode === "demo" ? (
          <>
            <ul className="space-y-1 text-xs">
              <li className="rounded bg-line/60 px-2 py-1.5">Latest JOLTS report (recorded)</li>
            </ul>
            <p className="text-muted text-xs mt-2">With a backend attached, every conversation is a LangGraph thread you can resume, replay or fork.</p>
          </>
        ) : threads.length === 0 ? (
          <p className="text-muted text-xs">No threads yet.</p>
        ) : (
          <ul className="space-y-1">
            {threads.map((t) => {
              const first = (t.values as { messages?: { content?: unknown }[] } | undefined)?.messages?.[0]?.content;
              const label = typeof first === "string" ? first : t.thread_id.slice(0, 8);
              return (
                <li key={t.thread_id}>
                  <button
                    onClick={() => onPick(t.thread_id)}
                    className={`w-full text-left rounded px-2 py-1.5 truncate hover:bg-line/40 ${t.thread_id === currentId ? "bg-line/60" : ""}`}
                    title={t.thread_id}>
                    {label}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div>
        <h2 className="font-semibold mb-2">Remembered feedback</h2>
        {prefs.length === 0 ? (
          <p className="text-muted text-xs">Feedback you give at plan review is stored in the LangGraph Store and applied to future plans.</p>
        ) : (
          <ul className="space-y-1 text-xs">{prefs.map((p, i) => <li key={i} className="rounded bg-line/30 px-2 py-1">{p.text}</li>)}</ul>
        )}
      </div>
      <div className="mt-auto text-xs text-muted leading-relaxed">
        <div className="font-semibold text-fg mb-1">How it works</div>
        planner → <span className="text-plan">review</span> → fetch → analyst → <span className="text-ok">critic</span> → answer.
        The plan is data you approve; fetch runs with no model; the critic rejects any figure not backed by evidence.
      </div>
    </aside>
  );
}
