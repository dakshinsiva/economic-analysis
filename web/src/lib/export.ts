import type { Chart } from "./types";

export function chartToCsv(chart: Chart): string {
  const dates = Array.from(new Set(chart.panels.flatMap((p) => p.points.map((pt) => pt.d)))).sort();
  const header = ["date", ...chart.panels.map((p) => `${p.id} (${p.units})`)].join(",");
  const rows = dates.map((d) => [d, ...chart.panels.map((p) => p.points.find((pt) => pt.d === d)?.v ?? "")].join(","));
  return [header, ...rows].join("\n");
}

export function download(name: string, content: string | Blob, type = "text/plain") {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name; a.click();
  URL.revokeObjectURL(a.href);
}

/** Rasterise an inline SVG (Recharts) to PNG at 2x. */
export async function svgToPng(svg: SVGSVGElement, scale = 2): Promise<Blob> {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const { width, height } = svg.getBoundingClientRect();
  clone.setAttribute("width", String(width)); clone.setAttribute("height", String(height));
  const bg = getComputedStyle(document.body).backgroundColor;
  const xml = new XMLSerializer().serializeToString(clone);
  const img = new Image();
  await new Promise<void>((res, rej) => { img.onload = () => res(); img.onerror = () => rej(new Error("svg load")); img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml); });
  const canvas = document.createElement("canvas");
  canvas.width = width * scale; canvas.height = height * scale;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = bg; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return new Promise((res) => canvas.toBlob((b) => res(b!), "image/png"));
}
