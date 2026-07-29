from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import StockAnalysisResult


@dataclass(frozen=True)
class PortfolioItem:
    code: str
    shares: float
    average_cost: float
    note: str = ""


class PortfolioStore:
    def __init__(self, path: str | Path = "data/market_cache.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS portfolio (
                    code TEXT PRIMARY KEY,
                    shares REAL NOT NULL,
                    average_cost REAL NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )"""
            )

    def upsert(self, item: PortfolioItem) -> None:
        if item.shares < 0 or item.average_cost < 0:
            raise ValueError("股數與平均成本不可為負數")
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """INSERT INTO portfolio(code, shares, average_cost, note, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET shares=excluded.shares,
                    average_cost=excluded.average_cost, note=excluded.note,
                    updated_at=excluded.updated_at""",
                (item.code, item.shares, item.average_cost, item.note, datetime.now().isoformat()),
            )

    def delete(self, code: str) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM portfolio WHERE code = ?", (code,))

    def list(self) -> list[PortfolioItem]:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT code, shares, average_cost, note FROM portfolio ORDER BY code"
            ).fetchall()
        return [PortfolioItem(*row) for row in rows]


class SessionPortfolioStore:
    """Per-browser-session portfolio for public deployments."""

    def __init__(self, state) -> None:
        self.state = state
        if "_public_portfolio" not in self.state:
            self.state["_public_portfolio"] = {}

    def upsert(self, item: PortfolioItem) -> None:
        if item.shares < 0 or item.average_cost < 0:
            raise ValueError("股數與平均成本不可為負數")
        records = dict(self.state.get("_public_portfolio", {}))
        records[item.code] = {
            "shares": float(item.shares),
            "average_cost": float(item.average_cost),
            "note": item.note,
        }
        self.state["_public_portfolio"] = records

    def delete(self, code: str) -> None:
        records = dict(self.state.get("_public_portfolio", {}))
        records.pop(code, None)
        self.state["_public_portfolio"] = records

    def list(self) -> list[PortfolioItem]:
        records = self.state.get("_public_portfolio", {})
        return [
            PortfolioItem(code, data["shares"], data["average_cost"], data.get("note", ""))
            for code, data in sorted(records.items())
        ]


def holding_action(result: StockAnalysisResult, average_cost: float) -> tuple[str, str]:
    price = result.quote.price
    gain = price / average_cost - 1 if average_cost > 0 else 0
    if price <= result.invalidation_price:
        return "考慮退出／嚴格控管風險", "現價已接近或跌破策略失效參考價。"
    if price >= result.second_target_price:
        return "考慮分批減碼", "現價已到第二停利參考區，宜保護既有成果。"
    if price >= result.first_target_price:
        return "可分批停利或續抱", "現價已到第一目標區，可依風險承受度減碼。"
    if result.signal.startswith("偏多") and result.watch_low <= price <= result.watch_high:
        return "可評估分批補入", "綜合評分偏多，且現價位於參考布局區。"
    if result.signal.startswith("偏多"):
        return "續抱／等待回到布局區", "趨勢仍偏多，但目前不在理想補入區。"
    if "觀望" in result.signal:
        return "續抱觀察，暫不補入", f"目前訊號為觀望；持有損益約 {gain:+.1%}。"
    return "考慮減碼，暫不補入", "綜合訊號偏弱，新增部位的風險報酬不理想。"
