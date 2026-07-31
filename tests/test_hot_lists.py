from datetime import datetime

from twstock_lab.cache import SQLiteCache
from twstock_lab.models import DataMeta, Quote
from twstock_lab.providers import HybridTaiwanProvider, TAIPEI


def test_hot_lists_use_mis_snapshot_during_refresh(tmp_path, monkeypatch):
    provider = HybridTaiwanProvider(SQLiteCache(tmp_path / "hot.sqlite3"))
    official_rows = [{"Date": "1150730", "Code": "0050", "Name": "元大台灣50", "ClosingPrice": "93.50", "Change": "-0.2000", "TradeVolume": "297963128"}]
    monkeypatch.setattr(provider, "_daily_rows", lambda market, refresh=False: (official_rows if market == "TWSE" else [], None, False))
    monkeypatch.setattr(provider, "_industry_map", lambda: {})
    monkeypatch.setattr(provider, "_json", lambda url: {"msgArray": [{"c": "0050", "z": "102.8500", "y": "93.5000", "v": "334568", "d": "20260731", "t": "13:30:00"}]})

    quote = provider.get_hot_lists(refresh=True)["gainers"][0]
    assert quote["code"] == "0050"
    assert round(quote["change_pct"], 2) == 10.00
    assert quote["price"] == 102.85
    assert quote["volume"] == 334_568_000
    assert quote["source"] == "TWSE MIS 盤中行情"
    assert quote["market_time"].strftime("%Y-%m-%d %H:%M:%S") == "2026-07-31 13:30:00"


def test_hot_lists_keep_official_close_without_refresh(tmp_path, monkeypatch):
    provider = HybridTaiwanProvider(SQLiteCache(tmp_path / "hot.sqlite3"))
    official_rows = [{"Date": "1150730", "Code": "0050", "Name": "元大台灣50", "ClosingPrice": "93.50", "Change": "-0.2000", "TradeVolume": "297963128"}]
    monkeypatch.setattr(provider, "_daily_rows", lambda market, refresh=False: (official_rows if market == "TWSE" else [], None, False))
    monkeypatch.setattr(provider, "_industry_map", lambda: {})

    quote = provider.get_hot_lists(refresh=False)["volume"][0]
    assert round(quote["change_pct"], 2) == -0.21
    assert quote["source"] == "TWSE 官方盤後行情"


def test_hot_lists_fall_back_to_latest_symbol_quote_when_mis_fails(tmp_path, monkeypatch):
    provider = HybridTaiwanProvider(SQLiteCache(tmp_path / "hot.sqlite3"))
    official_rows = [{"Date": "1150730", "Code": "0050", "Name": "元大台灣50", "ClosingPrice": "93.50", "Change": "-0.2000", "TradeVolume": "297963128"}]
    monkeypatch.setattr(provider, "_daily_rows", lambda market, refresh=False: (official_rows if market == "TWSE" else [], None, False))
    monkeypatch.setattr(provider, "_industry_map", lambda: {})
    monkeypatch.setattr(provider, "_json", lambda url: (_ for _ in ()).throw(RuntimeError("MIS unavailable")))
    market_time = datetime(2026, 7, 31, 13, 30, tzinfo=TAIPEI)
    monkeypatch.setattr(provider, "get_latest_quote", lambda stock, refresh=False: Quote(stock.code, 102.85, 9.35, 10.0, 334_568_000, DataMeta("Yahoo Finance 最新報價", market_time, market_time)))
    quote = provider.get_hot_lists(refresh=True)["gainers"][0]
    assert quote["code"] == "0050"
    assert quote["change_pct"] == 10.0
    assert quote["market_time"] == market_time
    assert quote["source"] == "Yahoo Finance 最新報價"


def test_hot_lists_retry_visible_candidates_with_compact_mis_request(tmp_path, monkeypatch):
    provider = HybridTaiwanProvider(SQLiteCache(tmp_path / "hot.sqlite3"))
    official_rows = [{"Date": "1150730", "Code": "0050", "Name": "元大台灣50", "ClosingPrice": "93.50", "Change": "-0.2000", "TradeVolume": "297963128"}]
    monkeypatch.setattr(provider, "_daily_rows", lambda market, refresh=False: (official_rows if market == "TWSE" else [], None, False))
    monkeypatch.setattr(provider, "_industry_map", lambda: {})
    calls = {"count": 0}
    def mis_response(url):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("large batch rejected")
        return {"msgArray": [{"c": "0050", "z": "102.8500", "y": "93.5000", "v": "334568", "d": "20260731", "t": "13:30:00"}]}
    monkeypatch.setattr(provider, "_json", mis_response)
    monkeypatch.setattr(provider, "get_latest_quote", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Yahoo should not be needed")))
    quote = provider.get_hot_lists(refresh=True)["gainers"][0]
    assert calls["count"] == 2
    assert quote["code"] == "0050"
    assert round(quote["change_pct"], 2) == 10.0
    assert quote["source"] == "TWSE MIS 盤中行情"
