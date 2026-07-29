from datetime import datetime
from zoneinfo import ZoneInfo

from twstock_lab.market_clock import market_clock


def test_taiwan_market_open_and_after_close():
    zone = ZoneInfo("Asia/Taipei")
    opened = market_clock("台股", datetime(2026, 7, 29, 10, 0, tzinfo=zone))
    assert opened.status == "交易中"
    assert opened.event_label == "距離收盤"
    closed = market_clock("台股", datetime(2026, 7, 29, 14, 0, tzinfo=zone))
    assert closed.status == "已收盤"
    assert closed.target.date().isoformat() == "2026-07-30"


def test_us_market_handles_weekend():
    zone = ZoneInfo("America/New_York")
    clock = market_clock("美股", datetime(2026, 8, 1, 12, 0, tzinfo=zone))
    assert clock.status == "休市"
    assert clock.target.weekday() == 0
