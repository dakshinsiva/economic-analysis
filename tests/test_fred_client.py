from pathlib import Path

import pandas as pd
import pytest

from econ_agent.fred.client import FredClient, FredError


class StubFred:
    """Stand-in for fredapi.Fred to test caching and error normalisation."""

    def __init__(self) -> None:
        self.n = 0

    def get_series(self, series_id, observation_start=None, observation_end=None):
        self.n += 1
        if series_id == "BAD":
            raise ValueError("Bad Request.  The series does not exist.")
        return pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-01-01", "2026-02-01"]))

    def get_series_info(self, series_id):
        return pd.Series({"title": "x", "units_short": "u"})

    def search(self, text, limit=1000, order_by=None, sort_order=None, filter=None):
        return pd.DataFrame()


@pytest.fixture
def client(tmp_path: Path) -> FredClient:
    c = FredClient("dummy", tmp_path)
    c._fred = StubFred()  # type: ignore[assignment]
    return c


def test_missing_key_is_clear_error(tmp_path):
    with pytest.raises(FredError, match="FRED_API_KEY"):
        FredClient("", tmp_path)


def test_bad_series_id_is_llm_readable(client):
    with pytest.raises(FredError, match="not found.*search_fred"):
        client.get_series("BAD")


def test_disk_cache_prevents_second_network_call(client):
    client.get_series("UNRATE", "2026-01-01")
    client.get_series("UNRATE", "2026-01-01")
    assert client._fred.n == 1


def test_empty_search_raises(client):
    with pytest.raises(FredError, match="returned nothing"):
        client.search("zzz")
