import pandas as pd

from twstock_lab.backtest import BacktestConfig, run_backtest
from twstock_lab.demo import make_demo_prices
from twstock_lab.indicators import add_indicators
from twstock_lab.statistics import win_rate_test


def test_indicators_are_added():
    result = add_indicators(make_demo_prices(300))
    assert {"ma60", "rsi14", "macd", "kd_k", "atr14"} <= set(result.columns)
    assert result["rsi14"].between(0, 100).all()


def test_backtest_returns_consistent_equity():
    data = make_demo_prices(500)
    result = run_backtest(data, BacktestConfig(require_volume=False, rsi_max=90))
    assert len(result["equity"]) == len(data)
    assert result["metrics"]["final_equity"] > 0
    if not result["trades"].empty:
        assert (result["trades"]["entry_date"] > result["trades"]["signal_date"]).all()


def test_win_rate_test():
    result = win_rate_test(70, 100, 0.60)
    assert 0 < result["lower"] < result["upper"] < 1
    assert result["p_value"] < 0.05


def test_missing_columns_fail():
    try:
        add_indicators(pd.DataFrame({"date": ["2025-01-01"], "close": [1]}))
    except ValueError as exc:
        assert "缺少必要欄位" in str(exc)
    else:
        raise AssertionError("Expected validation error")

