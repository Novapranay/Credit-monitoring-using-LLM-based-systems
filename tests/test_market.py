"""A failed price download must fall back to the last good cached prices, not silently drop them."""
import pandas as pd
import requests

from aicm import market


def test_failed_download_keeps_cached_prices(tmp_path, monkeypatch):
    monkeypatch.setattr(market, "RAW", tmp_path)
    (tmp_path / "prices").mkdir()
    pd.DataFrame({"date": ["2026-11-19", "2026-11-20"], "close": [100.0, 90.0]}).to_csv(market.price_path("XYZ"), index=False)

    def boom(*a, **k):
        raise requests.ConnectionError("blocked")

    monkeypatch.setattr(market.requests, "get", boom)
    monkeypatch.setattr(market.time, "sleep", lambda s: None)
    got = market.fetch_prices("XYZ", force=True)
    assert got is not None and got.iloc[-1] == 90.0


def test_failed_download_without_cache_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(market, "RAW", tmp_path)
    monkeypatch.setattr(market.requests, "get", lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("blocked")))
    monkeypatch.setattr(market.time, "sleep", lambda s: None)
    assert market.fetch_prices("XYZ", force=True) is None
