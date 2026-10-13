export type Indicator = {
  id: string; label: string; units: string; freq: "D" | "W" | "M" | "Q";
  latest: number; date: string; change: number; changeLabel: string; points: number[];
};

export const INDICATORS: { id: string; label: string; units: string; freq: Indicator["freq"]; changeLabel: string }[] = [
  { id: "UNRATE", label: "Unemployment", units: "%", freq: "M", changeLabel: "vs 12m ago" },
  { id: "JTSQUR", label: "Quits rate", units: "%", freq: "M", changeLabel: "vs 12m ago" },
  { id: "JTSJOL", label: "Job openings", units: "k", freq: "M", changeLabel: "vs 12m ago" },
  { id: "T10Y2Y", label: "10y–2y spread", units: "pp", freq: "D", changeLabel: "vs 3m ago" },
  { id: "PCEPILFE", label: "Core PCE YoY", units: "%", freq: "M", changeLabel: "vs 12m ago" },
  { id: "A191RL1Q225SBEA", label: "Real GDP (ann.)", units: "%", freq: "Q", changeLabel: "vs prev qtr" },
];
