from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MarketClock:
    name: str
    status: str
    event_label: str
    target: datetime
    timezone_name: str


def market_clock(name: str, now: datetime | None = None) -> MarketClock:
    settings = {
        "台股": ("Asia/Taipei", time(9, 0), time(13, 30)),
        "美股": ("America/New_York", time(9, 30), time(16, 0)),
    }
    timezone_name, open_time, close_time = settings[name]
    zone = ZoneInfo(timezone_name)
    local_now = (now or datetime.now(zone)).astimezone(zone)
    day = local_now.date()

    def next_weekday(value):
        value += timedelta(days=1)
        while value.weekday() >= 5:
            value += timedelta(days=1)
        return value

    if local_now.weekday() >= 5:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        return MarketClock(name, "休市", "距離開盤", datetime.combine(day, open_time, zone), timezone_name)
    opening = datetime.combine(day, open_time, zone)
    closing = datetime.combine(day, close_time, zone)
    if local_now < opening:
        return MarketClock(name, "盤前", "距離開盤", opening, timezone_name)
    if local_now < closing:
        return MarketClock(name, "交易中", "距離收盤", closing, timezone_name)
    next_day = next_weekday(day)
    return MarketClock(name, "已收盤", "距離下次開盤", datetime.combine(next_day, open_time, zone), timezone_name)

