/** Detect date-indexed rows in a tool result and split it into prose + a table. */
export type ParsedEvidence = { pre: string; header: string[] | null; rows: string[][]; post: string } | null;

const DATE_ROW = /^(\d{4}-\d{2}-\d{2})\s+(.+)$/;

export function parseEvidence(text: string): ParsedEvidence {
  const lines = text.split("\n");
  const idx = lines.map((l, i) => (DATE_ROW.test(l.trim()) ? i : -1)).filter((i) => i >= 0);
  if (idx.length < 2) return null;
  const first = idx[0], last = idx[idx.length - 1];
  const rows = lines.slice(first, last + 1).map((l) => l.trim()).filter((l) => DATE_ROW.test(l))
    .map((l) => { const m = l.match(DATE_ROW)!; return [m[1], ...m[2].trim().split(/\s{2,}/)]; });
  const cols = Math.max(...rows.map((r) => r.length));
  const maybeHeader = lines[first - 1]?.trim() ?? "";
  const headerCells = maybeHeader.split(/\s{2,}/);
  const header = headerCells.length === cols && /^date/i.test(maybeHeader) ? headerCells : null;
  const pre = lines.slice(0, header ? first - 1 : first).join("\n").trim();
  const post = lines.slice(last + 1).join("\n").trim();
  return { pre, header, rows: rows.map((r) => [...r, ...Array(cols - r.length).fill("")]), post };
}
