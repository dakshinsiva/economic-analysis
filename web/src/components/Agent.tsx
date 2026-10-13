"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import type { Thread } from "@langchain/langgraph-sdk";
import { Pipeline } from "./Pipeline";
import { PlanCard } from "./PlanCard";
import { EvidenceList } from "./EvidenceList";
import { ChartCard } from "./ChartCard";
import { CriticCard } from "./CriticCard";
import { Answer } from "./Answer";
import { Sidebar, type Pref } from "./Sidebar";
import { Dashboard } from "./Dashboard";
import { Trace, type NodeTiming } from "./Trace";
import { followUps } from "@/lib/cite";
import { useDemo } from "@/lib/useDemo";
import { EXAMPLES, type AgentState, type NodeName, type PlanReviewInterrupt, textOf } from "@/lib/types";

type Mode = "checking" | "live" | "demo";

export const APP_NAME = "econ-agent";
export const APP_TAGLINE = "agentic research desk over FRED: planned retrieval, human review, cited and fact-checked answers";

async function detectMode(): Promise<Mode> {
  const forced = new URLSearchParams(window.location.search).get("demo") === "1" || process.env.NEXT_PUBLIC_DEMO === "1";
  if (forced) return "demo";
  try {
    const r = await fetch("/api/info", { cache: "no-store" });
    return r.ok ? "live" : "demo";
  } catch {
    return "demo";
  }
}

export function Agent() {
  const [mode, setMode] = useState<Mode>("checking");
  useEffect(() => {
    detectMode().then(setMode);
  }, []);
  if (mode === "checking") return <div className="p-8 text-muted text-sm">Connecting to the agent…</div>;
  return mode === "live" ? <Live /> : <Demo />;
}

/* ------------------------------------------------------------------ live */
function Live() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [active, setActive] = useState<NodeName | null>(null);
  const [done, setDone] = useState<NodeName[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [prefs, setPrefs] = useState<Pref[]>([]);
  const [timings, setTimings] = useState<NodeTiming[]>([]);

  const stream = useStream<AgentState, { InterruptType: PlanReviewInterrupt }>({
    // The SDK builds absolute URLs, so a relative base is rejected ("Invalid URL").
    apiUrl: `${window.location.origin}/api`,
    assistantId: "econ_agent_v2",
    threadId,
    onThreadId: setThreadId,
    onUpdateEvent: (data) => {
      const nodes = Object.keys(data).filter((k) => k !== "__interrupt__") as NodeName[];
      const now = Date.now();
      for (const n of nodes) {
        setDone((d) => (d.includes(n) ? d : [...d, n]));
        setActive(n === "finalize" ? null : n);
        setTimings((t) => [...t, { node: n, at: now }]);
      }
    },
    onFinish: () => setActive(null),
    onError: () => setActive(null),
  });

  const client = stream.client;
  const refresh = useCallback(async () => {
    try {
      const [t, p] = await Promise.all([
        client.threads.search({ limit: 20, sortBy: "updated_at", sortOrder: "desc" }),
        client.store.searchItems(["prefs", "default"], { limit: 20 }),
      ]);
      setThreads(t);
      setPrefs(p.items.map((i) => i.value as Pref).sort((a, b) => a.ts.localeCompare(b.ts)));
    } catch { /* store may be unavailable; sidebar degrades */ }
  }, [client]);
  const loading = stream.isLoading;
  useEffect(() => { const id = setTimeout(refresh, 0); return () => clearTimeout(id); }, [refresh, loading]);

  const interrupt = stream.interrupt?.value?.type === "plan_review" ? stream.interrupt.value : null;
  const shownActive: NodeName | null = interrupt ? "review" : active;

  const ask = (q: string) => {
    setDone([]); setActive("planner"); setTimings([{ node: "submitted", at: Date.now() }]);
    stream.submit({ messages: [{ type: "human", content: q }] }, { config: { configurable: { user_id: "default" } } });
  };
  const decide = (d: string) => {
    setActive(d === "approve" ? "fetch" : "planner");
    setTimings((t) => [...t, { node: "resumed", at: Date.now() }]);
    stream.submit(null, { command: { resume: d } });
  };

  return (
    <Shell mode="live" sidebar={<Sidebar mode="live" threads={threads} currentId={threadId} prefs={prefs}
      onPick={(id) => { setThreadId(id); setDone(["planner", "review", "fetch", "analyst", "critic", "finalize"]); setActive(null); setTimings([]); }}
      onNew={() => { setThreadId(null); setDone([]); setActive(null); setTimings([]); }} />}>
      <Dashboard mode="live" onAsk={ask} />
      <Run values={stream.values} active={shownActive} done={done} interrupt={interrupt} isLoading={stream.isLoading}
        error={stream.error ? String(stream.error) : null} onDecide={decide} onAsk={ask} onStop={() => stream.stop()} timings={timings} />
    </Shell>
  );
}

/* ------------------------------------------------------------------ demo */
function Demo() {
  const d = useDemo();
  return (
    <Shell mode="demo" sidebar={<Sidebar mode="demo" threads={[]} currentId={null} prefs={[]} onPick={() => {}} onNew={d.reset} />}>
      <Dashboard mode="demo" onAsk={() => d.start()} />
      <Run values={d.values} active={d.active} done={d.done} interrupt={d.interrupt} isLoading={d.isLoading} error={null}
        onDecide={d.resume} onAsk={() => d.start()} onStop={d.reset} demoQuestion={d.question} timings={d.timings} />
    </Shell>
  );
}

/* ------------------------------------------------------------------ shared */
function Shell({ mode, sidebar, children }: { mode: "live" | "demo"; sidebar: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex h-dvh">
      {sidebar}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="border-b border-line px-5 py-3 flex items-center gap-3 flex-wrap">
          <h1 className="font-semibold tracking-tight">{APP_NAME}</h1>
          <span className="text-muted text-sm hidden sm:inline">{APP_TAGLINE}</span>
          <span className={`ml-auto tag ${mode === "live" ? "bg-ok/15 text-ok" : "bg-plan/15 text-plan"}`}>
            {mode === "live" ? "live backend" : "demo replay"}
          </span>
          <a className="text-sm text-muted hover:text-fg" href="https://github.com/dakshinsiva/economic-analysis" target="_blank" rel="noreferrer">GitHub ↗</a>
        </header>
        {children}
      </div>
    </div>
  );
}

function Run({ values, active, done, interrupt, isLoading, error, onDecide, onAsk, onStop, demoQuestion, timings }: {
  values: AgentState; active: NodeName | null; done: NodeName[]; interrupt: PlanReviewInterrupt | null; isLoading: boolean;
  error: string | null; onDecide: (d: string) => void; onAsk: (q: string) => void; onStop: () => void; demoQuestion?: string;
  timings: NodeTiming[];
}) {
  const [q, setQ] = useState("");
  const msgs = useMemo(() => values.messages ?? [], [values.messages]);
  const lastHuman = useMemo(() => [...msgs].reverse().find((m) => m.type === "human"), [msgs]);
  const lastAi = useMemo(() => [...msgs].reverse().find((m) => m.type === "ai"), [msgs]);
  const finalReady = done.includes("finalize") && lastAi;
  const empty = !lastHuman && !isLoading;

  return (
    <>
      <div className="px-5 py-2 border-b border-line flex items-center gap-4 flex-wrap">
        <Pipeline active={active} done={done} />
        {isLoading && <button className="btn text-xs" onClick={onStop}>stop</button>}
      </div>
      <main className="flex-1 overflow-y-auto px-5 py-4 space-y-4 max-w-4xl w-full mx-auto">
        {empty && (
          <div className="py-10">
            <h2 className="text-xl font-semibold mb-2">Research desk</h2>
            <p className="text-muted mb-5 max-w-xl">Ask a macro question. The agent plans which FRED series to fetch, pauses for your approval, fetches them with no model in the loop, writes a cited answer, then a critic rejects any figure not backed by the evidence. Click a dashboard tile to start from an indicator.</p>
            <div className="flex flex-wrap gap-2">
              {(demoQuestion ? [demoQuestion] : EXAMPLES).map((e) => (
                <button key={e} className="btn" onClick={() => onAsk(e)}>{e}</button>
              ))}
            </div>
          </div>
        )}
        {lastHuman && <div className="text-sm"><span className="tag bg-line/60 text-fg mr-2">you</span>{textOf(lastHuman)}</div>}
        {error && <div className="card border-l-4 border-l-bad p-3 text-sm text-bad">{error}</div>}
        {values.plan && <PlanCard plan={values.plan} awaiting={!!interrupt} onDecide={onDecide} />}
        {!!values.evidence?.length && <EvidenceList evidence={values.evidence} />}
        {values.charts?.map((c, i) => <ChartCard key={i} chart={c} />)}
        {values.draft && !finalReady && <Answer text={values.draft} draft />}
        {values.critique && <CriticCard critique={values.critique} revisions={values.revisions} />}
        {finalReady && <Answer text={textOf(lastAi!)} onFollowUp={demoQuestion ? undefined : onAsk}
          followUps={followUps(textOf(lastAi!), lastHuman ? textOf(lastHuman) : "")} />}
        {finalReady && <Trace timings={timings} values={values} />}
        {isLoading && !interrupt && <div className="text-xs text-muted animate-pulse">running {active ?? "…"}</div>}
      </main>
      {!demoQuestion && (
        <form className="border-t border-line px-5 py-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) { onAsk(q.trim()); setQ(""); } }}>
          <input className="input flex-1" placeholder="Ask about JOLTS, GDP, inflation, the yield curve…" value={q} onChange={(e) => setQ(e.target.value)} disabled={isLoading} />
          <button className="btn-primary" disabled={isLoading || !q.trim()}>Ask</button>
        </form>
      )}
    </>
  );
}
