"""Shared fixtures. No network, no API keys: the FRED client is replaced by a
fake that serves recorded data from tests/fixtures/*.json."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from econ_agent import tools
from econ_agent.fred.client import FredError

FIXTURES = Path(__file__).parent / "fixtures"


class FakeFred:
    """Mimics FredClient's public surface using recorded JSON fixtures."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self._data = json.loads((FIXTURES / "series.json").read_text())

    def get_series(self, series_id: str, start=None, end=None) -> pd.Series:
        sid = series_id.upper()
        self.calls.append(("get_series", sid, start, end))
        if sid not in self._data:
            raise FredError(f"FRED series {sid!r} was not found. Use search_fred to find the right id.")
        s = pd.Series(self._data[sid]["values"], index=pd.to_datetime(self._data[sid]["dates"]), name=sid)
        if start:
            s = s[s.index >= pd.Timestamp(start)]
        if end:
            s = s[s.index <= pd.Timestamp(end)]
        return s

    def get_info(self, series_id: str) -> dict:
        return {"units_short": self._data.get(series_id.upper(), {}).get("units", "?")}

    def search(self, text: str, limit: int = 10) -> pd.DataFrame:
        self.calls.append(("search", text))
        return pd.DataFrame([{
            "id": "JTSQUR", "title": "Quits: Total Nonfarm", "units_short": "Rate",
            "frequency_short": "M", "seasonal_adjustment_short": "SA",
            "observation_end": "2026-08-01", "popularity": 60,
        }])


@pytest.fixture
def fake_fred(monkeypatch) -> FakeFred:
    fake = FakeFred()
    monkeypatch.setattr(tools, "_client", lambda: fake)
    return fake
