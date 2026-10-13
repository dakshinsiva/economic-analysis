export type Step = { tool: string; args: Record<string, unknown>; why: string };
export type Plan = { goal: string; steps: Step[] };
export type Evidence = { tool: string; args: Record<string, unknown>; result: string; ok: boolean };
export type Critique = { approved: boolean; issues: string[] };
export type ChartPanel = { id: string; title: string; units: string; points: { d: string; v: number }[] };
export type Chart = { title: string; panels: ChartPanel[]; recessions: { from: string; to: string }[] };
export type Msg = { id?: string; type: "human" | "ai" | string; content: string | unknown[] };

export type AgentState = {
  messages: Msg[];
  plan?: Plan | null;
  plan_feedback?: string | null;
  evidence?: Evidence[];
  charts?: Chart[];
  draft?: string;
  critique?: Critique | null;
  revisions?: number;
};

export type PlanReviewInterrupt = {
  type: "plan_review";
  goal: string;
  steps: Step[];
  hint: string;
};

export const NODES = ["planner", "review", "fetch", "analyst", "critic", "finalize"] as const;
export type NodeName = (typeof NODES)[number];

export const EXAMPLES = [
  "What does the latest JOLTS report say about the labor market?",
  "Is the yield curve inverted right now?",
  "Plot the unemployment rate over the last five years.",
  "Is core inflation still above the Fed's 2% target?",
];

export function textOf(m: Msg): string {
  if (typeof m.content === "string") return m.content;
  return (m.content as { type?: string; text?: string }[])
    .filter((b) => b.type === "text" && b.text)
    .map((b) => b.text)
    .join("\n");
}
