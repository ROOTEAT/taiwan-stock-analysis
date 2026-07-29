from datetime import datetime, timezone

from twstock_lab.cache import SQLiteCache
from twstock_lab.models import StockInfo
from twstock_lab.providers import HybridTaiwanProvider


def test_twse_dividend_events_merge_declared_and_schedule(tmp_path, monkeypatch):
    provider = HybridTaiwanProvider(SQLiteCache(tmp_path / "dividend.sqlite3"))

    def fake_cached(key, url, ttl, refresh=False, tpex=False):
        fetched = datetime.now(timezone.utc)
        if key == "dividend:ex:twse":
            return ([{
                "Date": "1150730", "Code": "2409", "Name": "友達",
                "CashDividend": "0.400000",
            }], fetched, False)
        if key == "dividend:declared:twse":
            return ([{
                "公司代號": "2409", "股利年度": "114",
                "董事會（擬議）股利分派日": "1150301",
                "股東配發-盈餘分配之現金股利(元/股)": "0.4",
                "股東配發-法定盈餘公積發放之現金(元/股)": "0",
                "股東配發-資本公積發放之現金(元/股)": "0",
            }], fetched, False)
        if key.startswith("dividend:yahoo"):
            return ({"chart": {"result": [{"events": {}}]}}, fetched, False)
        raise AssertionError(key)

    monkeypatch.setattr(provider, "_cached_json", fake_cached)
    events = provider.get_dividend_events(StockInfo("2409", "友達", "TWSE"))
    assert len(events) == 1
    assert events[0].cash_per_share == 0.4
    assert events[0].ex_dividend_date.date().isoformat() == "2026-07-30"


def test_etf_historical_dividends_are_kept_by_date(tmp_path, monkeypatch):
    provider = HybridTaiwanProvider(SQLiteCache(tmp_path / "dividend.sqlite3"))
    fetched = datetime.now(timezone.utc)

    def fake_cached(key, url, ttl, refresh=False, tpex=False):
        if key == "dividend:ex:twse":
            return ([], fetched, False)
        if key.startswith("dividend:yahoo"):
            return ({
                "chart": {"result": [{"events": {"dividends": {
                    "1": {"date": 1769011200, "amount": 1.0},
                    "2": {"date": 1784563200, "amount": 1.0},
                }}}]}
            }, fetched, False)
        raise AssertionError(key)

    monkeypatch.setattr(provider, "_cached_json", fake_cached)
    events = provider.get_dividend_events(StockInfo("0050", "元大台灣50", "TWSE", asset_type="ETF"))
    assert len(events) == 2
