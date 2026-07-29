from __future__ import annotations

import math

from scipy.stats import binomtest, norm


def win_rate_test(wins: int, total: int, target: float = 0.60, confidence: float = 0.95) -> dict:
    if total <= 0:
        return {"lower": 0.0, "upper": 0.0, "p_value": 1.0, "significant": False}
    rate = wins / total
    z = norm.ppf(1 - (1 - confidence) / 2)
    denominator = 1 + z**2 / total
    center = (rate + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / total + z**2 / (4 * total**2)) / denominator
    p_value = float(binomtest(wins, total, target, alternative="greater").pvalue)
    return {"lower": center - margin, "upper": center + margin, "p_value": p_value, "significant": p_value < 1 - confidence}

