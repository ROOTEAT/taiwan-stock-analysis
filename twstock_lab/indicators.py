from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}


def normalize_prices(data: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize an OHLCV data set."""
    frame = data.copy()
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"缺少必要欄位：{', '.join(sorted(missing))}")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in REQUIRED_COLUMNS - {"date"}:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = (
        frame.dropna(subset=list(REQUIRED_COLUMNS))
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )
    if frame.empty:
        raise ValueError("沒有可使用的價格資料")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("價格必須大於 0")
    return frame


def add_indicators(data: pd.DataFrame) -> pd.DataFrame:
    frame = normalize_prices(data)
    close = frame["close"]
    for period in (5, 20, 60, 120, 240):
        frame[f"ma{period}"] = close.rolling(period).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    frame["rsi14"] = (100 - (100 / (1 + rs))).fillna(50)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    frame["macd"] = ema12 - ema26
    frame["macd_signal"] = frame["macd"].ewm(span=9, adjust=False).mean()

    low9 = frame["low"].rolling(9).min()
    high9 = frame["high"].rolling(9).max()
    rsv = ((close - low9) / (high9 - low9).replace(0, np.nan) * 100).fillna(50)
    frame["kd_k"] = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    frame["kd_d"] = frame["kd_k"].ewm(alpha=1 / 3, adjust=False).mean()

    previous = close.shift(1)
    true_range = pd.concat(
        [(frame["high"] - frame["low"]), (frame["high"] - previous).abs(), (frame["low"] - previous).abs()],
        axis=1,
    ).max(axis=1)
    frame["atr14"] = true_range.ewm(alpha=1 / 14, adjust=False).mean()
    frame["volume_ma20"] = frame["volume"].rolling(20).mean()
    std20 = close.rolling(20).std()
    frame["bollinger_upper"] = frame["ma20"] + 2 * std20
    frame["bollinger_lower"] = frame["ma20"] - 2 * std20
    return frame

