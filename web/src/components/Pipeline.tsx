import { NODES, type NodeName } from "@/lib/types";

const LABEL: Record<NodeName, string> = {
  planner: "plan", review: "review", fetch: "fetch", analyst: "write", critic: "check", finalize: "answer",
};

export function Pipeline({ active, done }: { active: NodeName | null; done: NodeName[] }) {
  return (
    <ol className="flex items-center gap-1 text-xs font-medium" aria-label="pipeline">
      {NODES.map((n, i) => {
        const state = active === n ? "active" : done.includes(n) ? "done" : "idle";
        return (
          <li key={n} className="flex items-center gap-1">
            <span
              className={[
                "rounded-full px-2.5 py-1 border transition-colors",
                state === "active" && "border-accent bg-accent/15 text-accent animate-pulse",
                state === "done" && "border-ok/60 bg-ok/10 text-ok",
                state === "idle" && "border-line text-muted",
              ].filter(Boolean).join(" ")}
            >
              {LABEL[n]}
            </span>
            {i < NODES.length - 1 && <span className="text-line">→</span>}
          </li>
        );
      })}
    </ol>
  );
}
