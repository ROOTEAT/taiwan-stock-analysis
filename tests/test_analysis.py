from datetime import datetime, timezone

import pandas as pd

from twstock_lab.analysis import ETF_WEIGHTS, WEIGHTS, analyze_stock
from twstock_lab.cache import SQLiteCache
from twstock_lab.demo import make_demo_prices
from twstock_lab.models import DataMeta, Quote, StockAnalysisRequest, StockInfo


class FakeProvider:
    def __init__(self, *, missing=False, stale=False):
        self.stock = StockInfo("2330", "測試股票", "TWSE")
        self.missing = missing
        self.stale = stale

    def get_stock(self, code):
        if code != "2330":
            raise ValueError("找不到")
        return self.stock

    def search_stocks(self, query=""):
        return [self.stock] if query in ("", "2330", "測試") else []

    def get_daily_prices(self, stock, refresh=False):
        return make_demo_prices(300), self._meta("歷史")

    def get_latest_quote(self, stock, refresh=False):
        return Quote("2330", 100, 1, 1.01, 5_000_000, self._meta("最新", self.stale))

    def get_valuation(self, stock, refresh=False):
        value = {} if self.missing else {"pe": 15, "pb": 1.8, "yield": 4.5}
        return value, self._meta("估值")

    def get_monthly_revenue(self, stock, refresh=False):
        return ({} if self.missing else {"yoy": 15}), self._meta("營收")

    def get_institutional_trading(self, stock, refresh=False):
        value = {} if self.missing else {"foreign_net": 1000, "investment_trust_net": 300, "dealer_net": -50}
        return value, self._meta("法人")

    @staticmethod
    def _meta(source, stale=False):
        return DataMeta(source, datetime.now(timezone.utc), datetime.now(timezone.utc), stale)


def test_horizon_weights_total_one():
    assert all(abs(sum(weights.values()) - 1) < 1e-9 for weights in WEIGHTS.values())
    assert all(abs(sum(weights.values()) - 1) < 1e-9 for weights in ETF_WEIGHTS.values())


def test_horizons_and_risk_profiles_are_deterministic():
    provider = FakeProvider()
    results = {
        (horizon, risk): analyze_stock(provider, StockAnalysisRequest("2330", horizon, risk))
        for horizon in ("短線", "波段", "中長期")
        for risk in ("保守", "穩健", "積極")
    }
    assert len({r.overall_score for r in results.values()}) > 1
    assert results[("波段", "保守")].max_position_pct == 0.10
    assert results[("波段", "穩健")].max_position_pct == 0.15
    assert results[("波段", "積極")].max_position_pct == 0.20


def test_missing_data_caps_signal_at_wait():
    result = analyze_stock(FakeProvider(missing=True, stale=True), StockAnalysisRequest("2330"))
    assert result.confidence < 60
    assert result.signal == "資料不足，暫時觀望"
    assert result.missing_data


def test_sqlite_cache_ttl_and_stale(tmp_path):
    cache = SQLiteCache(tmp_path / "cache.sqlite3")
    cache.set("key", {"value": 1}, -1)
    assert cache.get("key") is None
    stale = cache.get("key", allow_stale=True)
    assert stale is not None
    assert stale[0] == {"value": 1}
    assert stale[2] is True


def test_etf_does_not_lose_confidence_for_company_data():
    provider = FakeProvider(missing=True)
    provider.stock = StockInfo("2330", "測試 ETF", "TWSE", asset_type="ETF")
    result = analyze_stock(provider, StockAnalysisRequest("2330"))
    assert result.confidence == 100
    assert "法人籌碼資料不完整" not in result.missing_data


def test_legacy_stock_info_without_asset_type_is_supported():
    class LegacyStock:
        code = "2330"
        name = "舊版股票"
        market = "TWSE"
        industry = ""

    provider = FakeProvider()
    provider.stock = LegacyStock()
    result = analyze_stock(provider, StockAnalysisRequest("2330"))
    assert result.stock.code == "2330"
    assert result.confidence > 0


def test_legacy_etf_is_detected_from_code():
    class LegacyETF:
        code = "0050"
        name = "舊版 ETF"
        market = "TWSE"
        industry = ""

    provider = FakeProvider(missing=True)
    provider.stock = LegacyETF()
    result = analyze_stock(provider, StockAnalysisRequest("2330"))
    assert result.confidence == 100
    assert "法人籌碼資料不完整" not in result.missing_data
