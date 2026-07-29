from __future__ import annotations

import numpy as np
import pandas as pd


def make_demo_prices(periods: int = 900, seed: int = 2330) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=periods)
    returns = rng.normal(0.00035, 0.017, periods)
    close = 100 * np.exp(np.cumsum(returns))
    overnight = rng.normal(0, 0.004, periods)
    open_ = np.r_[close[0], close[:-1]] * (1 + overnight)
    spread = rng.uniform(0.002, 0.018, periods)
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    volume = rng.lognormal(np.log(7_000_000), 0.55, periods).astype(int)
    return pd.DataFrame({"date": dates, "open": open_, "high": high, "low": low, "close": close, "volume": volume})

