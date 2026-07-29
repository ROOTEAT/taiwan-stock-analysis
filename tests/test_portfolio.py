from twstock_lab.analysis import analyze_stock
from twstock_lab.models import StockAnalysisRequest
from twstock_lab.portfolio import PortfolioItem, PortfolioStore, SessionPortfolioStore, holding_action

from .test_analysis import FakeProvider


def test_portfolio_store_round_trip(tmp_path):
    store = PortfolioStore(tmp_path / "portfolio.sqlite3")
    store.upsert(PortfolioItem("0050", 1000, 180.5, "核心"))
    assert store.list() == [PortfolioItem("0050", 1000, 180.5, "核心")]
    store.upsert(PortfolioItem("0050", 2000, 175, "加碼"))
    assert store.list()[0].shares == 2000
    store.delete("0050")
    assert store.list() == []


def test_session_portfolio_store_isolates_visitors():
    first_state, second_state = {}, {}
    first = SessionPortfolioStore(first_state)
    second = SessionPortfolioStore(second_state)
    first.upsert(PortfolioItem("2330", 1000, 900, "測試"))
    assert first.list() == [PortfolioItem("2330", 1000, 900, "測試")]
    assert second.list() == []


def test_holding_action_respects_invalidation_and_targets():
    result = analyze_stock(FakeProvider(), StockAnalysisRequest("2330"))
    result.quote = result.quote.__class__(
        result.quote.code, result.invalidation_price - 1, 0, 0, result.quote.volume, result.quote.meta
    )
    action, _ = holding_action(result, 100)
    assert "退出" in action

    result.quote = result.quote.__class__(
        result.quote.code, result.second_target_price + 1, 0, 0, result.quote.volume, result.quote.meta
    )
    action, _ = holding_action(result, 100)
    assert "減碼" in action
