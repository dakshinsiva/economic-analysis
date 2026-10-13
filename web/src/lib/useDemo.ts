"use client";
/**
 * Replays a recorded run so the hosted demo shows the whole pipeline without a
 * backend: plan -> (you approve) -> evidence -> draft -> critic -> answer.
 * Exposes the same surface the live hook does, so the page does not care.
 */
import { useCallback, useRef, useState } from "react";
import run from "@/demo/run.json";
import type { AgentState, NodeName, PlanReviewInterrupt } from "./types";
import type { NodeTiming } from "@/components/Trace";

const DEMO = run as unknown as AgentState & { question: string };

export function useDemo() {
  const [values, setValues] = useState<AgentState>({ messages: [] });
  const [active, setActive] = useState<NodeName | null>(null);
  const [done, setDone] = useState<NodeName[]>([]);
  const [interrupt, setInterrupt] = useState<PlanReviewInterrupt | null>(null);
  const [isLoading, setLoading] = useState(false);
  const [timings, setTimings] = useState<NodeTiming[]>([]);
  const timers = useRef<number[]>([]);
  const mark = (node: NodeTiming["node"]) => setTimings((t) => [...t, { node, at: Date.now() }]);

  const wait = (ms: number) => new Promise<void>((r) => timers.current.push(window.setTimeout(r, ms)));

  const start = useCallback(async () => {
    setValues({ messages: [{ type: "human", content: DEMO.question }] });
    setDone([]); setInterrupt(null); setLoading(true); setTimings([]);
    mark("submitted"); setActive("planner"); await wait(1400); mark("planner");
    setValues((v) => ({ ...v, plan: DEMO.plan }));
    setDone(["planner"]); setActive("review");
    setInterrupt({ type: "plan_review", goal: DEMO.plan!.goal, steps: DEMO.plan!.steps, hint: "" });
    setLoading(false);
  }, []);

  const resume = useCallback(async (decision: string) => {
    setInterrupt(null); setLoading(true);
    if (decision !== "approve") {
      // The recorded run has one plan; show the feedback being absorbed, then proceed.
      setActive("planner"); await wait(1200); setActive("review");
      setInterrupt({ type: "plan_review", goal: DEMO.plan!.goal, steps: DEMO.plan!.steps, hint: "" });
      setLoading(false); return;
    }
    mark("resumed"); mark("review"); setDone(["planner", "review"]); setActive("fetch");
    const ev = DEMO.evidence ?? [];
    for (let i = 0; i < ev.length; i++) {
      await wait(700);
      setValues((v) => ({ ...v, evidence: ev.slice(0, i + 1), charts: i === ev.length - 1 ? DEMO.charts : v.charts }));
    }
    mark("fetch"); setDone(["planner", "review", "fetch"]); setActive("analyst");
    // Type the draft out in word-sized chunks, as the live analyst streams tokens.
    const words = (DEMO.draft ?? "").split(/(\s+)/);
    for (let i = 0; i < words.length; i += 14) {
      setValues((v) => ({ ...v, draft: words.slice(0, i + 14).join("") }));
      await wait(45);
    }
    setValues((v) => ({ ...v, draft: DEMO.draft })); mark("analyst");
    setDone(["planner", "review", "fetch", "analyst"]); setActive("critic"); await wait(1500); mark("critic");
    setValues((v) => ({ ...v, critique: DEMO.critique, revisions: DEMO.revisions }));
    setDone(["planner", "review", "fetch", "analyst", "critic"]); setActive("finalize"); await wait(500); mark("finalize");
    setValues((v) => ({ ...v, messages: DEMO.messages }));
    setDone([...NODES_ALL]); setActive(null); setLoading(false);
  }, []);

  const reset = useCallback(() => {
    timers.current.forEach(clearTimeout); timers.current = [];
    setValues({ messages: [] }); setDone([]); setActive(null); setInterrupt(null); setLoading(false); setTimings([]);
  }, []);

  return { values, active, done, interrupt, isLoading, start, resume, reset, timings, question: DEMO.question };
}

const NODES_ALL: NodeName[] = ["planner", "review", "fetch", "analyst", "critic", "finalize"];
