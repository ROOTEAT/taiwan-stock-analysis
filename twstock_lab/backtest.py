from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

from .indicators import add_indicators


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 1_000_000
    position_pct: float = 1.0
    take_profit: float = 0.15
    stop_loss: float = 0.08
    max_holding_days: int = 20
    fee_rate: float = 0.001425
    tax_rate: float = 0.003
    slippage: float = 0.001
    min_fee: float = 20
    entry_ma: int = 60
    exit_ma: int = 20
    rsi_max: float = 70
    require_volume: bool = True


def _fee(value: float, rate: float, minimum: float) -> float:
    return max(value * rate, minimum)


def run_backtest(data: pd.DataFrame, config: BacktestConfig) -> dict:
    """Long-only single-position backtest; signals use close and fill next open."""
    frame = add_indicators(data)
    entry_ma = f"ma{config.entry_ma}"
    exit_ma = f"ma{config.exit_ma}"
    if entry_ma not in frame or exit_ma not in frame:
        raise ValueError("均線參數僅支援 5、20、60、120、240 日")

    cash = float(config.initial_capital)
    shares = 0
    entry_price = entry_value = entry_cost = 0.0
    entry_index = -1
    entry_date = signal_date = None
    pending_entry = False
    pending_exit_reason: str | None = None
    trades: list[dict] = []
    equity_rows: list[dict] = []

    for i, row in frame.iterrows():
        # Orders decided after yesterday's close fill at today's open.
        if pending_exit_reason and shares:
            fill = float(row["open"]) * (1 - config.slippage)
            value = shares * fill
            sell_cost = _fee(value, config.fee_rate, config.min_fee) + value * config.tax_rate
            cash += value - sell_cost
            net_return = (value - sell_cost - entry_value - entry_cost) / (entry_value + entry_cost)
            window = frame.iloc[entry_index : i + 1]
            trades.append(
                {
                    "signal_date": signal_date,
                    "entry_date": entry_date,
                    "entry_price": entry_price,
                    "exit_date": row["date"],
                    "exit_price": fill,
                    "quantity": shares,
                    "net_return": net_return,
                    "holding_days": i - entry_index,
                    "exit_reason": pending_exit_reason,
                    "mfe": window["high"].max() / entry_price - 1,
                    "mae": window["low"].min() / entry_price - 1,
                }
            )
            shares = 0
            pending_exit_reason = None

        if pending_entry and not shares:
            fill = float(row["open"]) * (1 + config.slippage)
            budget = cash * config.position_pct
            estimated = _fee(budget, config.fee_rate, config.min_fee)
            shares = max(int((budget - estimated) // fill), 0)
            if shares:
                entry_value = shares * fill
                entry_cost = _fee(entry_value, config.fee_rate, config.min_fee)
                cash -= entry_value + entry_cost
                entry_price, entry_date, entry_index = fill, row["date"], i
            pending_entry = False

        market_value = shares * float(row["close"])
        total = cash + market_value
        equity_rows.append({"date": row["date"], "cash": cash, "market_value": market_value, "equity": total})

        if shares:
            change = float(row["close"]) / entry_price - 1
            held = i - entry_index + 1
            if change >= config.take_profit:
                pending_exit_reason = "停利"
            elif change <= -config.stop_loss:
                pending_exit_reason = "停損"
            elif pd.notna(row[exit_ma]) and row["close"] < row[exit_ma]:
                pending_exit_reason = "跌破均線"
            elif held >= config.max_holding_days:
                pending_exit_reason = "持有到期"
        elif i + 1 < len(frame):
            volume_ok = (row["volume"] > row["volume_ma20"]) if config.require_volume else True
            if pd.notna(row[entry_ma]) and row["close"] > row[entry_ma] and row["rsi14"] < config.rsi_max and volume_ok:
                signal_date = row["date"]
                pending_entry = True

    if shares:
        row = frame.iloc[-1]
        value = shares * float(row["close"]) * (1 - config.slippage)
        sell_cost = _fee(value, config.fee_rate, config.min_fee) + value * config.tax_rate
        cash += value - sell_cost
        trades.append(
            {
                "signal_date": signal_date, "entry_date": entry_date, "entry_price": entry_price,
                "exit_date": row["date"], "exit_price": value / shares, "quantity": shares,
                "net_return": (value - sell_cost - entry_value - entry_cost) / (entry_value + entry_cost),
                "holding_days": len(frame) - entry_index, "exit_reason": "回測結束",
                "mfe": frame.iloc[entry_index:]["high"].max() / entry_price - 1,
                "mae": frame.iloc[entry_index:]["low"].min() / entry_price - 1,
            }
        )
        equity_rows[-1] = {"date": row["date"], "cash": cash, "market_value": 0, "equity": cash}

    equity = pd.DataFrame(equity_rows)
    equity["daily_return"] = equity["equity"].pct_change().fillna(0)
    equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1
    trade_frame = pd.DataFrame(trades)
    returns = trade_frame["net_return"] if not trade_frame.empty else pd.Series(dtype=float)
    years = max((frame["date"].iloc[-1] - frame["date"].iloc[0]).days / 365.25, 1 / 365.25)
    total_return = equity["equity"].iloc[-1] / config.initial_capital - 1
    volatility = equity["daily_return"].std() * sqrt(252)
    sharpe = equity["daily_return"].mean() / equity["daily_return"].std() * sqrt(252) if equity["daily_return"].std() else 0
    wins = int((returns > 0).sum())
    metrics = {
        "initial_capital": config.initial_capital,
        "final_equity": float(equity["equity"].iloc[-1]),
        "total_return": float(total_return),
        "annual_return": float((1 + total_return) ** (1 / years) - 1) if total_return > -1 else -1,
        "max_drawdown": float(equity["drawdown"].min()),
        "volatility": float(volatility or 0),
        "sharpe": float(sharpe or 0),
        "trade_count": len(trade_frame),
        "wins": wins,
        "win_rate": float(wins / len(trade_frame)) if len(trade_frame) else 0,
        "profit_factor": float(returns[returns > 0].sum() / abs(returns[returns < 0].sum())) if (returns < 0).any() else float("inf"),
    }
    return {"prices": frame, "equity": equity, "trades": trade_frame, "metrics": metrics}


def monte_carlo(trade_returns: pd.Series, initial_capital: float, simulations: int = 2000, seed: int = 42) -> np.ndarray:
    values = pd.Series(trade_returns).dropna().to_numpy(dtype=float)
    if not len(values):
        return np.array([])
    rng = np.random.default_rng(seed)
    sampled = rng.choice(values, size=(simulations, len(values)), replace=True)
    return initial_capital * np.prod(1 + sampled, axis=1)

