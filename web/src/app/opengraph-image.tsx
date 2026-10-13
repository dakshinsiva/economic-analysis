import { ImageResponse } from "next/og";

export const alt = "econ-agent: an agentic research desk over FRED";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const PTS = [42, 38, 41, 27, 31, 22, 25, 18, 21, 16];

export default function OpenGraphImage() {
  const w = 420, h = 200, pad = 12;
  // y grows downward on screen, so invert: a falling quits rate draws as a falling line.
  const pts = PTS.map((v, i) => `${pad + (i / (PTS.length - 1)) * (w - 2 * pad)},${h - (v / 48) * h}`).join(" ");
  const [lx, ly] = pts.split(" ").pop()!.split(",").map(Number);
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", background: "#15161a", color: "#f2f1ec",
                    fontFamily: "sans-serif", padding: 64, alignItems: "center", justifyContent: "space-between", gap: 40 }}>
        <div style={{ display: "flex", flexDirection: "column", width: 640, flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
            <svg width="72" height="72" viewBox="0 0 64 64">
              <rect width="64" height="64" rx="14" fill="#22242a" />
              <rect x="24" y="10" width="9" height="44" fill="#34363e" />
              <polyline points="9,42 16,38 23,41 30,27 37,31 44,22 51,25 55,18" fill="none" stroke="#5598e7" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="55" cy="18" r="4.5" fill="#5598e7" stroke="#22242a" strokeWidth="2.5" />
              <path d="M12 50h40" stroke="#3fc27a" strokeWidth="3" strokeLinecap="round" />
            </svg>
            <div style={{ fontSize: 56, fontWeight: 700, letterSpacing: -1 }}>econ-agent</div>
          </div>
          <div style={{ fontSize: 30, marginTop: 28, lineHeight: 1.3, color: "#c9c8c0" }}>
            An agentic research desk over FRED. Plans its retrieval, waits for your approval, cites every figure, and fact-checks its own draft.
          </div>
          <div style={{ display: "flex", gap: 7, marginTop: 36, fontSize: 17 }}>
            {["plan", "review", "fetch", "write", "check", "answer"].map((n, i) => (
              <div key={n} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ padding: "4px 11px", borderRadius: 999, border: "2px solid #3fc27a", color: "#3fc27a" }}>{n}</div>
                {i < 5 && <div style={{ color: "#4a4c55" }}>→</div>}
              </div>
            ))}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14, width: w, flexShrink: 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 20, color: "#a3a29a", width: w }}>
            <span style={{ display: "flex", gap: 10 }}><b style={{ color: "#f2f1ec" }}>JTSQUR</b><span>Quits rate</span></span><span>Percent, SA</span>
          </div>
          <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
            <rect x={w * 0.3} y="0" width={w * 0.08} height={h} fill="#2b2d34" />
            <polyline points={pts} fill="none" stroke="#5598e7" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx={lx} cy={ly} r="8" fill="#5598e7" stroke="#15161a" strokeWidth="4" />
          </svg>
          <div style={{ display: "flex", justifyContent: "flex-end", fontSize: 20, color: "#a3a29a", width: w }}>latest 1.9 (JTSQUR, 2026-08-01)</div>
        </div>
      </div>
    ),
    size,
  );
}
