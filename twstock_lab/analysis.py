from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from .indicators import add_indicators
from .models import StockAnalysisRequest, StockAnalysisResult
from .news import GDELTNewsProvider
from .providers import MarketDataProvider

WEIGHTS = {
    "短線": {"technical": 0.50, "fundamental": 0.10, "chip": 0.30, "risk": 0.10},
    "波段": {"technical": 0.35, "fundamental": 0.25, "chip": 0.25, "risk": 0.15},
    "中長期": {"technical": 0.15, "fundamental": 0.50, "chip": 0.10, "risk": 0.25},
}
ETF_WEIGHTS = {
    "短線": {"technical": 0.65, "fundamental": 0.05, "chip": 0.00, "risk": 0.30},
    "波段": {"technical": 0.50, "fundamental": 0.10, "chip": 0.00, "risk": 0.40},
    "中長期": {"technical": 0.30, "fundamental": 0.20, "chip": 0.00, "risk": 0.50},
}
RISK_SETTINGS = {
    "保守": {"penalty": 1.4, "position": 0.10},
    "穩健": {"penalty": 1.0, "position": 0.15},
    "積極": {"penalty": 0.7, "position": 0.20},
}


def _clip(value: float) -> float:
    return round(float(np.clip(value, 0, 100)), 1)


def _valid(value) -> bool:
    return value is not None and pd.notna(value)


def _technical_score(prices: pd.DataFrame) -> tuple[float, list[str], list[str]]:
    row = prices.iloc[-1]
    score = 50.0
    positive, negative = [], []
    if _valid(row.ma20) and row.close > row.ma20:
        score += 10
        positive.append("股價站上月線，短期趨勢偏多")
    else:
        score -= 10
        negative.append("股價位於月線下方，短期趨勢偏弱")
    if _valid(row.ma60) and row.close > row.ma60:
        score += 12
        positive.append("股價站上季線，中期趨勢有支撐")
    else:
        score -= 12
        negative.append("股價未站穩季線")
    if row.macd > row.macd_signal:
        score += 8
        positive.append("MACD 位於訊號線上方")
    else:
        score -= 6
        negative.append("MACD 動能偏弱")
    if 45 <= row.rsi14 <= 70:
        score += 8
        positive.append(f"RSI {row.rsi14:.0f}，動能健康且未明顯過熱")
    elif row.rsi14 > 75:
        score -= 10
        negative.append(f"RSI {row.rsi14:.0f}，短線可能過熱")
    elif row.rsi14 < 35:
        score -= 6
        negative.append(f"RSI {row.rsi14:.0f}，走勢仍偏弱")
    if _valid(row.volume_ma20) and row.volume > row.volume_ma20:
        score += 7
        positive.append("成交量高於 20 日均量")
    high20 = prices["high"].rolling(20).max().iloc[-1]
    if _valid(high20) and row.close >= high20 * 0.98:
        score += 5
        positive.append("股價接近 20 日高點")
    return _clip(score), positive, negative


def _fundamental_score(valuation: dict, revenue: dict) -> tuple[float, list[str], list[str], int]:
    score, available = 50.0, 0
    positive, negative = [], []
    pe, pb, yield_rate, yoy = valuation.get("pe"), valuation.get("pb"), valuation.get("yield"), revenue.get("yoy")
    if _valid(pe):
        available += 1
        if 0 < pe <= 18:
            score += 12; positive.append(f"本益比 {pe:.1f} 倍，估值相對合理")
        elif pe > 35:
            score -= 12; negative.append(f"本益比 {pe:.1f} 倍，估值偏高")
    if _valid(pb):
        available += 1
        if 0 < pb <= 2:
            score += 7; positive.append(f"股價淨值比 {pb:.2f} 倍")
        elif pb > 6:
            score -= 8; negative.append(f"股價淨值比 {pb:.2f} 倍，需留意評價風險")
    if _valid(yield_rate):
        available += 1
        if yield_rate >= 4:
            score += 7; positive.append(f"殖利率約 {yield_rate:.1f}%")
    if _valid(yoy):
        available += 1
        if yoy > 10:
            score += 18; positive.append(f"最新月營收年增 {yoy:.1f}%")
        elif yoy > 0:
            score += 8; positive.append(f"最新月營收年增 {yoy:.1f}%")
        else:
            score -= 18; negative.append(f"最新月營收年減 {abs(yoy):.1f}%")
    return _clip(score), positive, negative, available


def _etf_fundamental_score(valuation: dict) -> tuple[float, list[str], list[str]]:
    yield_rate = valuation.get("yield")
    if not _valid(yield_rate):
        return 50.0, [], []
    if yield_rate >= 5:
        return 70.0, [f"ETF 參考殖利率約 {yield_rate:.1f}%"], []
    if yield_rate >= 3:
        return 60.0, [f"ETF 參考殖利率約 {yield_rate:.1f}%"], []
    return 50.0, [], ["ETF 殖利率不高；仍需依追蹤指數與總報酬評估"]


def _chip_score(institutional: dict) -> tuple[float, list[str], list[str], int]:
    values = [institutional.get(k) for k in ("foreign_net", "investment_trust_net", "dealer_net")]
    available_values = [float(x) for x in values if _valid(x)]
    if not available_values:
        return 50.0, [], [], 0
    total = sum(available_values)
    if total > 0:
        return _clip(50 + min(30, np.log1p(total) * 4)), ["可取得的法人資料呈現買超"], [], len(available_values)
    if total < 0:
        return _clip(50 - min(30, np.log1p(abs(total)) * 4)), [], ["可取得的法人資料呈現賣超"], len(available_values)
    return 50.0, [], [], len(available_values)


def _risk_score(prices: pd.DataFrame, valuation: dict, profile: str) -> tuple[float, list[str]]:
    daily = prices["close"].pct_change().dropna()
    volatility = daily.tail(60).std() * np.sqrt(252) if len(daily) else 0
    drawdown = prices["close"] / prices["close"].cummax() - 1
    max_dd = abs(float(drawdown.tail(252).min()))
    avg_value = (prices["close"] * prices["volume"]).tail(20).mean()
    penalty = volatility * 70 + max_dd * 45
    reasons: list[str] = []
    if volatility > 0.4:
        reasons.append(f"年化波動約 {volatility:.0%}，價格震盪較大")
    if max_dd > 0.25:
        reasons.append(f"近一年最大回撤約 {max_dd:.0%}")
    if avg_value < 20_000_000:
        penalty += 12
        reasons.append("近期成交金額偏低，需留意流動性")
    if _valid(valuation.get("pe")) and valuation["pe"] > 40:
        penalty += 8
    score = 100 - penalty * RISK_SETTINGS[profile]["penalty"]
    return _clip(score), reasons


def analyze_stock(provider: MarketDataProvider, request: StockAnalysisRequest, *, refresh: bool = False) -> StockAnalysisResult:
    stock = provider.get_stock(request.stock_code)  # type: ignore[attr-defined]
    prices_raw, price_meta = provider.get_daily_prices(stock, refresh)
    prices = add_indicators(prices_raw)
    quote = provider.get_latest_quote(stock, refresh)
    valuation, valuation_meta = provider.get_valuation(stock, refresh)
    revenue, revenue_meta = provider.get_monthly_revenue(stock, refresh)
    institutional, institution_meta = provider.get_institutional_trading(stock, refresh)

    technical, tech_pos, tech_neg = _technical_score(prices)
    asset_type = getattr(stock, "asset_type", "ETF" if stock.code.startswith("00") else "STOCK")
    if asset_type == "ETF":
        fundamental, fund_pos, fund_neg = _etf_fundamental_score(valuation)
        fundamental_fields = 3
        chip, chip_pos, chip_neg, chip_fields = 50.0, [], [], 2
    else:
        fundamental, fund_pos, fund_neg, fundamental_fields = _fundamental_score(valuation, revenue)
        chip, chip_pos, chip_neg, chip_fields = _chip_score(institutional)
    risk, risk_reasons = _risk_score(prices, valuation, request.risk_profile)
    weights = ETF_WEIGHTS[request.horizon] if asset_type == "ETF" else WEIGHTS[request.horizon]
    overall = _clip(
        technical * weights["technical"] + fundamental * weights["fundamental"]
        + chip * weights["chip"] + risk * weights["risk"]
    )
    news_score = None
    news_headlines: list[str] = []
    news_warning = None
    if request.include_news:
        news = GDELTNewsProvider(getattr(provider, "cache", None)).analyze(f'"{stock.name}" Taiwan stock')
        news_score, news_headlines, news_warning = news.score, news.headlines, news.warning
        if news.article_count:
            overall = _clip(overall * 0.95 + news.score * 0.05)

    missing: list[str] = []
    confidence = 100.0
    if len(prices) < 60:
        missing.append("歷史行情少於 60 個交易日"); confidence -= 30
    if asset_type != "ETF" and fundamental_fields < 3:
        missing.append("部分基本面或估值資料缺漏"); confidence -= (3 - fundamental_fields) * 8
    if asset_type != "ETF" and chip_fields < 2:
        missing.append("法人籌碼資料不完整"); confidence -= (2 - chip_fields) * 10
    if quote.meta.is_stale:
        missing.append("最新報價已降級為盤後或快取資料"); confidence -= 10
    confidence = _clip(confidence)

    if confidence < 60:
        signal = "資料不足，暫時觀望"
    elif overall >= 75:
        signal = "偏多，可列入分批布局觀察"
    elif overall >= 55:
        signal = "觀望，等待條件改善"
    else:
        signal = "偏空／暫不適合"

    latest = prices.iloc[-1]
    atr = latest.atr14 if _valid(latest.atr14) else latest.close * 0.03
    watch_low = max(0, min(latest.ma20 if _valid(latest.ma20) else latest.close, latest.close) - atr * 0.5)
    watch_high = latest.close + atr * 0.5
    invalidation = min(latest.ma60 if _valid(latest.ma60) else latest.close * 0.92, latest.close - atr * 1.5)
    resistance20 = float(prices["high"].tail(20).max())
    resistance60 = float(prices["high"].tail(60).max())
    first_target = max(float(latest.close + atr * 1.5), resistance20)
    second_target = max(float(latest.close + atr * 3), resistance60, first_target + float(atr))
    return StockAnalysisResult(
        stock=stock, quote=quote, technical_score=technical, fundamental_score=fundamental,
        chip_score=chip, risk_score=risk, overall_score=overall, confidence=confidence, signal=signal,
        positive_reasons=tech_pos + fund_pos + chip_pos,
        negative_reasons=tech_neg + fund_neg + chip_neg + risk_reasons,
        missing_data=missing, watch_low=float(watch_low), watch_high=float(watch_high),
        invalidation_price=float(max(0, invalidation)),
        first_target_price=first_target, second_target_price=second_target,
        max_position_pct=RISK_SETTINGS[request.risk_profile]["position"],
        news_score=news_score, news_headlines=news_headlines, news_warning=news_warning,
        prices=prices, valuation=valuation, revenue=revenue, institutional=institutional,
        data_status=[quote.meta, price_meta, valuation_meta, revenue_meta, institution_meta],
    )
