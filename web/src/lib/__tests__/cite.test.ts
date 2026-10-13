import { describe, expect, it } from "vitest";
import { citedSeries, followUps, linkCitations } from "../cite";
import { chartToCsv } from "../export";

describe("citations", () => {
  it("links (SERIES, date) to FRED and collects unique series", () => {
    const md = "Unemployment is 4.2% (UNRATE, 2026-09-01), quits 1.9% (JTSQUR, 2026-08-01), again (UNRATE, 2026-08-01).";
    expect(linkCitations(md)).toContain("[UNRATE](https://fred.stlouisfed.org/series/UNRATE), 2026-09-01");
    expect(citedSeries(md)).toEqual(["UNRATE", "JTSQUR"]);
  });
  it("suggests a chart follow-up only when the question did not ask for one", () => {
    const md = "x (UNRATE, 2026-09-01)";
    expect(followUps(md, "how is unemployment?").some((f) => f.startsWith("Plot"))).toBe(true);
    expect(followUps(md, "plot unemployment").some((f) => f.startsWith("Plot"))).toBe(false);
  });
});

describe("chart export", () => {
  it("writes one row per date with a column per panel", () => {
    const csv = chartToCsv({ title: "t", recessions: [], panels: [
      { id: "A", title: "", units: "pct", points: [{ d: "2026-01-01", v: 1 }, { d: "2026-02-01", v: 2 }] },
      { id: "B", title: "", units: "k", points: [{ d: "2026-02-01", v: 5 }] },
    ] });
    expect(csv.split("\n")).toEqual(["date,A (pct),B (k)", "2026-01-01,1,", "2026-02-01,2,5"]);
  });
});
