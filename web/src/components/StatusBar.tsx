import type { NodeName } from "@/lib/types";

export function StatusBar({ mode, threadId, userId, active, lastRunSeconds, backendHost }:
  { mode: "live" | "demo"; threadId: string | null; userId?: string; active: NodeName | null; lastRunSeconds?: number | null; backendHost?: string | null }) {
  return (
    <footer className="border-t border-line px-3 h-7 flex items-center gap-4 text-[11px] text-muted font-mono shrink-0 overflow-x-auto whitespace-nowrap">
      <span className="flex items-center gap-1"><span className={`h-1.5 w-1.5 rounded-full ${mode === "live" ? "bg-ok" : "bg-plan"}`} />{mode === "live" ? `LIVE ${backendHost ?? ""}` : "DEMO replay"}</span>
      <span>thread {threadId ? threadId.slice(0, 8) : "—"}</span>
      {userId && <span>user {userId}</span>}
      <span>{active ? `running ${active}` : lastRunSeconds ? `last run ${lastRunSeconds.toFixed(1)}s` : "idle"}</span>
      <span className="ml-auto hidden md:inline">⌘K command · / search · Enter approve · E edit · Esc cancel</span>
    </footer>
  );
}
