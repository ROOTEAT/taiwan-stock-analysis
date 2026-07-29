from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import pandas as pd

Market = Literal["TWSE", "TPEx"]
Horizon = Literal["短線", "波段", "中長期"]
RiskProfile = Literal["保守", "穩健", "積極"]


@dataclass(frozen=True)
class DataMeta:
    source: str
    market_time: datetime | None
    fetched_at: datetime
    is_stale: bool = False
    warning: str | None = None


@dataclass(frozen=True)
class StockInfo:
    code: str
    name: str
    market: Market
    industry: str = ""
    asset_type: Literal["STOCK", "ETF"] = "STOCK"


@dataclass(frozen=True)
class Quote:
    code: str
    price: float
    change: float
    change_pct: float
    volume: float
    meta: DataMeta


@dataclass(frozen=True)
class DividendEvent:
    code: str
    cash_per_share: float
    ex_dividend_date: datetime | None
    payment_date: datetime | None
    source: str
    status: str
    fiscal_year: str = ""


@dataclass(frozen=True)
class StockAnalysisRequest:
    stock_code: str
    horizon: Horizon = "波段"
    risk_profile: RiskProfile = "穩健"
    analysis_date: datetime | None = None
    include_news: bool = False


@dataclass
class StockAnalysisResult:
    stock: StockInfo
    quote: Quote
    technical_score: float
    fundamental_score: float
    chip_score: float
    risk_score: float
    overall_score: float
    confidence: float
    signal: str
    positive_reasons: list[str] = field(default_factory=list)
    negative_reasons: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    watch_low: float = 0
    watch_high: float = 0
    invalidation_price: float = 0
    first_target_price: float = 0
    second_target_price: float = 0
    max_position_pct: float = 0
    news_score: float | None = None
    news_headlines: list[str] = field(default_factory=list)
    news_warning: str | None = None
    prices: pd.DataFrame = field(default_factory=pd.DataFrame)
    valuation: dict = field(default_factory=dict)
    revenue: dict = field(default_factory=dict)
    institutional: dict = field(default_factory=dict)
    data_status: list[DataMeta] = field(default_factory=list)
