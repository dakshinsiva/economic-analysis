from econ_agent.tools import (compare_series, compute_change, get_series, list_known_series,
                              recession_periods, search_fred, yield_curve_snapshot)


def test_list_known_series_filters_by_topic():
    out = list_known_series.invoke({"topic": "rates"})
    assert "DGS10" in out and "JTSQUR" not in out
    assert "Unknown topic" in list_known_series.invoke({"topic": "nope"})


def test_get_series_cites_id_units_and_dates(fake_fred):
    out = get_series.invoke({"series_id": "jtsqur", "last_n": 2})
    assert out.startswith("JTSQUR: Quits Rate")
    assert "[Percent, SA]" in out and "2026-08-01" in out
    assert fake_fred.calls[0][1] == "JTSQUR"


def test_get_series_error_is_returned_not_raised(fake_fred):
    out = get_series.invoke({"series_id": "BOGUS"})
    assert out.startswith("ERROR") and "search_fred" in out


def test_compute_change_absolute_for_rates(fake_fred):
    out = compute_change.invoke({"series_id": "UNRATE", "periods": 1, "pct": False})
    assert "change over 1 obs (Percent, SA)" in out


def test_compare_series_reports_partial_failures(fake_fred):
    out = compare_series.invoke({"series_ids": ["JTSJOL", "BOGUS"], "last_n": 2})
    assert "JTSJOL" in out and "WARNINGS" in out and "BOGUS" in out


def test_yield_curve_snapshot_has_spreads_and_flag(fake_fred):
    out = yield_curve_snapshot.invoke({"as_of": "2026-10-08"})
    assert "10y-2y spread" in out and ("INVERTED" in out or "normal" in out)


def test_recession_periods(fake_fred):
    out = recession_periods.invoke({"since": "2000-01-01"})
    assert "2020-03-01" in out


def test_search_fred_formats_rows(fake_fred):
    assert "JTSQUR" in search_fred.invoke({"query": "quits"})


def test_plot_series_writes_png(fake_fred, tmp_path, monkeypatch):
    from econ_agent import tools
    monkeypatch.setattr(tools, "PROJECT_ROOT", tmp_path)
    out = tools.plot_series.invoke({"series_ids": ["JTSJOL", "JTSQUR", "BOGUS"], "title": "JOLTS test"})
    assert "Chart saved to" in out and "WARNINGS" in out
    png = next((tmp_path / "outputs").glob("*.png"))
    assert png.stat().st_size > 10_000
