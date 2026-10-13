"""LangChain tools exposed to the agent.

Rules that make tools LLM-friendly (and testable):
1. Return short, structured text - never a DataFrame repr with 500 rows.
2. Put the series id, units and observation dates in every output so the
   model can cite them.
3. Raise/return clear errors; the agent loop feeds the message back to the
   model, which then self-corrects (e.g. calls search_fred).
4. Keep the FRED client behind a module-level factory so tests can swap it.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

import pandas as pd
from langchain_core.tools import tool

from econ_agent.charts import plot_small_multiples
from econ_agent.config import PROJECT_ROOT, get_settings
from econ_agent.fred.client import FredClient, FredError
from econ_agent.fred.series import REGISTRY, TOPICS, by_topic


@lru_cache(maxsize=1)
def _client() -> FredClient:
    s = get_settings()
    return FredClient(s.fred_api_key, s.cache_dir)


def _fmt(v: float) -> str:
    return f"{v:,.2f}" if abs(v) < 1e6 else f"{v:,.0f}"


def _tail_table(s: pd.Series, n: int) -> str:
    rows = [f"{d.date()}  {_fmt(v)}" for d, v in s.tail(n).items()]
    return "\n".join(rows)


def _units(series_id: str) -> str:
    if series_id in REGISTRY:
        return REGISTRY[series_id].units
    try:
        return _client().get_info(series_id).get("units_short", "?")
    except FredError:
        return "?"


# --------------------------------------------------------------------------- #
@tool
def list_known_series(topic: str = "all") -> str:
    """List curated FRED series the agent knows well, with units and how to read them.

    Call this FIRST before searching FRED. topic is one of: labor, growth,
    inflation, rates, other, or 'all'.
    """
    items = by_topic(topic)
    if not items:
        return f"Unknown topic {topic!r}. Choose from: {', '.join(TOPICS)} or 'all'."
    lines = [f"{s.id:16} {s.frequency}  {s.title} [{s.units}] - {s.reading}" for s in items]
    return "\n".join(lines)


@tool
def search_fred(query: str, limit: int = 8) -> str:
    """Search FRED for series not in the curated list. Returns id, title, units, frequency.

    Prefer seasonally adjusted (SA) series. Use the returned id with get_series.
    """
    try:
        df = _client().search(query, limit=limit)
    except FredError as e:
        return f"ERROR: {e}"
    lines = [
        f"{r.id:16} {r.frequency_short} {r.seasonal_adjustment_short:4} {r.title} [{r.units_short}] (latest {r.observation_end})"
        for r in df.itertuples()
    ]
    return "\n".join(lines)


@tool
def get_series(series_id: str, start: Optional[str] = None, end: Optional[str] = None, last_n: int = 12) -> str:
    """Fetch observations for one FRED series id (e.g. 'UNRATE', 'JTSQUR', 'DGS10').

    Dates are YYYY-MM-DD. If start is omitted, fetches the last ~3 years.
    Returns the last `last_n` observations plus min/max/mean over the window.
    Always cite the series id and the observation date of the value you use.
    """
    sid = series_id.upper()
    if start is None:
        start = (date.today() - timedelta(days=3 * 365)).isoformat()
    try:
        s = _client().get_series(sid, start, end)
    except FredError as e:
        return f"ERROR: {e}"
    title = REGISTRY[sid].title if sid in REGISTRY else sid
    return (
        f"{sid}: {title} [{_units(sid)}]\n"
        f"window {s.index[0].date()} to {s.index[-1].date()} ({len(s)} obs); "
        f"min {_fmt(s.min())}, max {_fmt(s.max())}, mean {_fmt(s.mean())}\n"
        f"latest {last_n}:\n{_tail_table(s, last_n)}"
    )


@tool
def compute_change(series_id: str, periods: int = 12, pct: bool = True) -> str:
    """Change in a series over `periods` observations (e.g. 12 for YoY on monthly data,
    1 for MoM, 4 for YoY on quarterly). Returns the last 6 changes.
    Set pct=False for absolute (percentage-point) change, which is right for rates like UNRATE.
    """
    sid = series_id.upper()
    start = (date.today() - timedelta(days=5 * 365)).isoformat()
    try:
        s = _client().get_series(sid, start)
    except FredError as e:
        return f"ERROR: {e}"
    chg = (s.pct_change(periods) * 100) if pct else s.diff(periods)
    chg = chg.dropna()
    if chg.empty:
        return f"ERROR: not enough observations of {sid} to compute a {periods}-period change."
    label = f"% change over {periods} obs" if pct else f"change over {periods} obs ({_units(sid)})"
    return f"{sid} {label}, last 6:\n{_tail_table(chg, 6)}"


@tool
def compare_series(series_ids: list[str], start: Optional[str] = None, last_n: int = 8) -> str:
    """Side-by-side table of several series (same frequency works best).
    Example: ['JTSJOL', 'JTSQUR', 'UNRATE'] for a labor-market dashboard.
    """
    if start is None:
        start = (date.today() - timedelta(days=2 * 365)).isoformat()
    frames, errors = {}, []
    for sid in series_ids:
        try:
            frames[sid.upper()] = _client().get_series(sid, start)
        except FredError as e:
            errors.append(str(e))
    if not frames:
        return "ERROR: " + " | ".join(errors)
    df = pd.DataFrame(frames).dropna(how="all").tail(last_n)
    header = "date        " + "  ".join(f"{c:>12}" for c in df.columns)
    rows = [f"{d.date()}  " + "  ".join(f"{(_fmt(v) if pd.notna(v) else '-'):>12}" for v in r)
            for d, r in zip(df.index, df.values)]
    out = header + "\n" + "\n".join(rows)
    units = "; ".join(f"{c}: {_units(c)}" for c in df.columns)
    if errors:
        out += "\nWARNINGS: " + " | ".join(errors)
    return f"units -> {units}\n{out}"


@tool
def yield_curve_snapshot(as_of: Optional[str] = None) -> str:
    """Treasury yields (3mo, 2y, 10y, 30y) on the latest available date (or `as_of`),
    with 10y-2y and 10y-3m spreads and an inversion flag. Use for 'is the curve inverted?'.
    """
    ids = ["DGS3MO", "DGS2", "DGS10", "DGS30"]
    end = as_of
    start = (pd.Timestamp(as_of or date.today()) - pd.Timedelta(days=30)).date().isoformat()
    try:
        df = pd.DataFrame({i: _client().get_series(i, start, end) for i in ids}).dropna()
    except FredError as e:
        return f"ERROR: {e}"
    if df.empty:
        return "ERROR: no overlapping yield observations in the last 30 days."
    row = df.iloc[-1]
    d = df.index[-1].date()
    s10_2, s10_3m = row.DGS10 - row.DGS2, row.DGS10 - row.DGS3MO
    flag = "INVERTED (10y<2y)" if s10_2 < 0 else "normal (10y>2y)"
    prev = df.iloc[0]
    return (
        f"Yield curve as of {d} (percent):\n"
        f"  3mo {row.DGS3MO:.2f}  2y {row.DGS2:.2f}  10y {row.DGS10:.2f}  30y {row.DGS30:.2f}\n"
        f"  10y-2y spread {s10_2:+.2f}  |  10y-3m spread {s10_3m:+.2f}  ->  {flag}\n"
        f"  30 days earlier ({df.index[0].date()}): 10y-2y {prev.DGS10 - prev.DGS2:+.2f}, "
        f"10y-3m {prev.DGS10 - prev.DGS3MO:+.2f}"
    )


@tool
def recession_periods(since: str = "1990-01-01") -> str:
    """NBER recession date ranges (from USREC) since a date. Use to contextualise
    whether current readings resemble pre-recession patterns.
    """
    try:
        s = _client().get_series("USREC", since)
    except FredError as e:
        return f"ERROR: {e}"
    periods, start = [], None
    for d, v in s.items():
        if v == 1 and start is None:
            start = d
        elif v == 0 and start is not None:
            periods.append(f"{start.date()} to {d.date()}")
            start = None
    if start is not None:
        periods.append(f"{start.date()} to present")
    return "NBER recessions: " + ("; ".join(periods) if periods else "none in window")


@tool
def plot_series(series_ids: list[str], start: Optional[str] = None, title: Optional[str] = None) -> str:
    """Render a PNG line chart of one or more FRED series (one panel per series, shared time axis)
    with NBER recession shading. Returns the file path to tell the user, plus what was plotted.
    Use when the user asks to graph, chart, plot, or visualise. Max 6 series.
    """
    ids = [i.upper() for i in series_ids][:6]
    if start is None:
        start = (date.today() - timedelta(days=5 * 365)).isoformat()
    data, errors = {}, []
    for sid in ids:
        try:
            data[sid] = _client().get_series(sid, start)
        except FredError as e:
            errors.append(str(e))
    if not data:
        return "ERROR: " + " | ".join(errors)
    try:
        rec = _client().get_series("USREC", start)
        spans, a = [], None
        for d, v in rec.items():
            if v == 1 and a is None:
                a = d
            elif v == 0 and a is not None:
                spans.append((a, d)); a = None
        if a is not None:
            spans.append((a, rec.index[-1]))
    except FredError:
        spans = []
    units = {sid: _units(sid) for sid in data}
    titles = {sid: (REGISTRY[sid].title if sid in REGISTRY else "") for sid in data}
    path = plot_small_multiples(data, units, titles, PROJECT_ROOT / "outputs",
                                title or ", ".join(data), spans)
    summary = "; ".join(f"{sid} {s.index[0].date()}..{s.index[-1].date()} latest {_fmt(float(s.iloc[-1]))} {units[sid]}"
                        for sid, s in data.items())
    out = f"Chart saved to {path}\nPlotted: {summary}"
    if errors:
        out += "\nWARNINGS: " + " | ".join(errors)
    return out


ALL_TOOLS = [list_known_series, search_fred, get_series, compute_change, compare_series,
             yield_curve_snapshot, recession_periods, plot_series]
