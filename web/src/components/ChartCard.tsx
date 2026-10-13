"use client";
import { Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Chart } from "@/lib/types";

const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"];

export function ChartCard({ chart }: { chart: Chart }) {
  return (
    <section className="card border-l-4 border-l-chart">
      <header className="card-h">
        <span className="tag bg-chart/15 text-chart">chart</span>
        <span className="text-sm">{chart.title}</span>
      </header>
      <div className="px-2 pb-2">
        {chart.panels.map((p, i) => {
          const data = p.points.map((pt) => ({ t: new Date(pt.d).getTime(), v: pt.v }));
          const last = p.points[p.points.length - 1];
          const y0 = new Date(p.points[0].d).getUTCFullYear(), y1 = new Date(last.d).getUTCFullYear();
          const step = Math.max(1, Math.ceil((y1 - y0) / 8));
          const ticks: number[] = [];
          for (let y = y0 + 1; y <= y1; y += step) ticks.push(Date.UTC(y, 0, 1));
          return (
            <div key={p.id} className="px-2 pt-3">
              <div className="flex items-baseline justify-between text-xs">
                <span><span className="font-mono font-semibold">{p.id}</span> <span className="text-muted">{p.title}</span></span>
                <span className="text-muted">{p.units}</span>
              </div>
              <ResponsiveContainer width="100%" height={150}>
                <LineChart data={data} margin={{ top: 8, right: 48, bottom: 0, left: 0 }}>
                  {chart.recessions.map((r, k) => (
                    <ReferenceArea key={k} x1={new Date(r.from).getTime()} x2={new Date(r.to).getTime()} fill="var(--color-line)" fillOpacity={0.5} strokeOpacity={0} />
                  ))}
                  <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} scale="time" ticks={ticks}
                    tickFormatter={(t) => new Date(t).getUTCFullYear().toString()} tick={{ fontSize: 10, fill: "var(--color-muted)" }}
                    axisLine={{ stroke: "var(--color-line)" }} tickLine={false} />
                  <YAxis width={44} tick={{ fontSize: 10, fill: "var(--color-muted)" }} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
                  <Tooltip
                    contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-line)", fontSize: 12 }}
                    labelFormatter={(t) => new Date(Number(t)).toISOString().slice(0, 10)}
                    formatter={(v) => [Number(v).toLocaleString(), p.id]} />
                  <Line type="monotone" dataKey="v" stroke={PALETTE[i % PALETTE.length]} strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
              <div className="text-right text-xs -mt-2 pr-1">latest <span className="font-mono">{last.v.toLocaleString()}</span> <span className="text-muted">({last.d})</span></div>
            </div>
          );
        })}
        <div className="px-2 pt-2 text-[11px] text-muted">Source: FRED, Federal Reserve Bank of St. Louis. Shaded = NBER recession.</div>
      </div>
    </section>
  );
}
