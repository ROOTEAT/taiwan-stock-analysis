from twstock_lab.cache import SQLiteCache
from twstock_lab.providers import HybridTaiwanProvider


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
