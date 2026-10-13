/** (SERIES_ID, YYYY-MM-DD) -> markdown link to the FRED series page. */
const CITE = /\(([A-Z0-9]{3,20}),\s*(\d{4}-\d{2}-\d{2})\)/g;

export function linkCitations(md: string): string {
  return md.replace(CITE, (_m, id: string, d: string) => `([${id}](https://fred.stlouisfed.org/series/${id}), ${d})`);
}

export function citedSeries(md: string): string[] {
  const ids = new Set<string>();
  for (const m of md.matchAll(CITE)) ids.add(m[1]);
  return [...ids];
}

export function followUps(md: string, question: string): string[] {
  const ids = citedSeries(md);
  const list = ids.slice(0, 3).join(", ");
  const out: string[] = [];
  if (ids.length && !/plot|chart|graph/i.test(question)) out.push(`Plot ${list} since 2015 with recession shading.`);
  if (ids.length) out.push(`Compare the latest ${list} readings with their 2019 pre-pandemic averages.`);
  out.push("Does this reading look like a pre-recession pattern? Use the yield curve and initial claims as cross-checks.");
  if (!/inflation|cpi|pce/i.test(question)) out.push("How does this interact with core PCE inflation and the fed funds rate?");
  return out.slice(0, 4);
}
