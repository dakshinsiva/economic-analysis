"""Chart rendering for the plot_series tool.

Design rules (from the dataviz method):
- Series with different units never share a y-axis: one panel per series,
  stacked, sharing the x-axis (small multiples), never a dual axis.
- Fixed categorical hue order, thin 2px lines, recessive grid, direct label on
  the latest value, recession shading as neutral context.
- Text uses ink colours, not series colours.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
SURFACE, INK, INK_2, GRID, SHADE = "#fcfcfb", "#1f1f1e", "#5f5e58", "#e6e5df", "#d8d7d0"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "chart"


def plot_small_multiples(
    series: dict[str, pd.Series],
    units: dict[str, str],
    titles: dict[str, str],
    out_dir: Path,
    title: str,
    recessions: list[tuple[pd.Timestamp, pd.Timestamp]] | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(series)
    fig, axes = plt.subplots(n, 1, figsize=(10, 2.6 * n + 0.8), sharex=True, squeeze=False,
                             facecolor=SURFACE)
    for ax, (color, (sid, s)) in zip(axes[:, 0], zip(PALETTE, series.items())):
        ax.set_facecolor(SURFACE)
        for a, b in recessions or []:
            ax.axvspan(a, b, color=SHADE, lw=0, zorder=0)
        ax.plot(s.index, s.values, color=color, lw=2, zorder=3)
        last_d, last_v = s.index[-1], float(s.iloc[-1])
        ax.plot([last_d], [last_v], "o", ms=6, color=color, mec=SURFACE, mew=2, zorder=4)
        ax.annotate(f"{last_v:,.2f}".rstrip("0").rstrip("."), (last_d, last_v),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
        ax.set_title(f"{sid}  {titles.get(sid, '')}", loc="left", fontsize=10, color=INK, pad=4)
        ax.set_ylabel(units.get(sid, ""), fontsize=8, color=INK_2)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.tick_params(colors=INK_2, labelsize=8, length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.margins(x=0.02)
    axes[-1, 0].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, color=INK, fontweight="bold")
    fig.text(0.01, 0.005, "Source: FRED, Federal Reserve Bank of St. Louis. Shaded = NBER recession.",
             fontsize=7, color=INK_2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    path = out_dir / f"{_slug(title)}-{date.today().isoformat()}.png"
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path
