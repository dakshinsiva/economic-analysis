"""Thin, cached wrapper over fredapi.

Design notes (these are interview talking points):
- Tools should never hand a raw DataFrame to the LLM. This client returns
  pandas objects; the *tool* layer formats them into compact text.
- Every network call is cached on disk, keyed by (call, args, today). That
  makes reruns instant, keeps FRED rate limits happy, and lets you replay a
  debugging session offline the same day.
- Errors are normalised to FredError with a message the LLM can act on
  ("series FOO not found; try search_fred"). Raw fredapi/urllib exceptions
  are unhelpful to a model.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from fredapi import Fred

from econ_agent.logging import log_event


class FredError(RuntimeError):
    """Raised for any FRED failure, with an LLM-readable message."""


class FredClient:
    def __init__(self, api_key: str, cache_dir: Path | None = None) -> None:
        if not api_key:
            raise FredError("FRED_API_KEY is not set. Add it to .env (see .env.example).")
        self._fred = Fred(api_key=api_key)
        self._cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    # ---- caching -----------------------------------------------------------
    def _cache_path(self, call: str, *args: Any, **kwargs: Any) -> Path | None:
        if not self._cache_dir:
            return None
        key = json.dumps([call, args, kwargs, date.today().isoformat()], sort_keys=True, default=str)
        digest = hashlib.sha1(key.encode()).hexdigest()[:16]
        return self._cache_dir / f"{call}-{digest}.pkl"

    def _cached(self, call: str, fn, *args: Any, **kwargs: Any) -> Any:
        path = self._cache_path(call, *args, **kwargs)
        if path and path.exists():
            log_event("fred.cache_hit", call=call, args=args, kwargs=kwargs)
            return pickle.loads(path.read_bytes())
        t0 = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
        except ValueError as e:
            # fredapi raises ValueError with FRED's error text (e.g. bad series id).
            raise FredError(self._explain(call, args, str(e))) from e
        except Exception as e:  # network, auth, etc.
            raise FredError(f"FRED {call} failed: {type(e).__name__}: {e}") from e
        log_event("fred.call", call=call, args=args, kwargs=kwargs,
                  latency_ms=round((time.perf_counter() - t0) * 1000))
        if path:
            path.write_bytes(pickle.dumps(result))
        return result

    @staticmethod
    def _explain(call: str, args: tuple, raw: str) -> str:
        if "does not exist" in raw or "Bad Request" in raw:
            return (f"FRED series {args[0]!r} was not found. Series ids are case-sensitive "
                    f"(e.g. 'UNRATE'). Use search_fred to find the right id.")
        return f"FRED {call} failed: {raw}"

    # ---- public API --------------------------------------------------------
    def get_series(self, series_id: str, start: str | None = None, end: str | None = None) -> pd.Series:
        s = self._cached("get_series", self._fred.get_series, series_id.upper(),
                         observation_start=start, observation_end=end)
        if s is None or len(s) == 0:
            raise FredError(f"FRED returned no observations for {series_id!r} in [{start}, {end}].")
        s.name = series_id.upper()
        return s.dropna()

    def get_info(self, series_id: str) -> dict[str, Any]:
        info = self._cached("get_series_info", self._fred.get_series_info, series_id.upper())
        return {k: (None if pd.isna(v) else v) for k, v in info.to_dict().items()}

    def search(self, text: str, limit: int = 10) -> pd.DataFrame:
        df = self._cached("search", self._fred.search, text, limit=limit, order_by="popularity",
                          sort_order="desc")
        if df is None or df.empty:
            raise FredError(f"FRED search for {text!r} returned nothing. Try broader terms.")
        return df[["id", "title", "units_short", "frequency_short", "seasonal_adjustment_short",
                   "observation_end", "popularity"]]
