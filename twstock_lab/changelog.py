from __future__ import annotations

from dataclasses import dataclass
import re


VERSION_PATTERN = re.compile(r"^Ver-\d{8}-\d{6}-\d{3}$")


@dataclass(frozen=True)
class ReleaseNote:
    version: str
    title: str
    changes: tuple[str, ...]


CHANGELOG: tuple[ReleaseNote, ...] = (
    ReleaseNote(
        version="Ver-20260731-143547-784",
        title="盤中排行資料與版面修正",
        changes=(
            "盤中排行改用完整上市、上櫃 MIS 快照計算最新價、成交量及相較昨收漲跌幅。",
            "修正官方盤後舊資料可能被誤認為今日盤中漲跌的問題。",
            "排行卡片重新排版，清楚顯示名次、股票、產業、現價、行情時間與漲跌幅。",
        ),
    ),
    ReleaseNote(
        version="Ver-20260731-143004-991",
        title="密碼安全提醒",
        changes=(
            "登入與註冊頁新增醒目的密碼安全提醒。",
            "提醒使用者為本站另設至少 8 個字元、好記且不重複使用的密碼。",
        ),
    ),
    ReleaseNote(
        version="Ver-20260731-142817-768",
        title="市場排行盤中更新",
        changes=(
            "成交量、漲幅與跌幅排行在台股交易中每 10 秒更新。",
            "排行更新採獨立區塊執行，不會重跑或中斷目前頁面操作。",
            "介面新增排行更新時間與盤前、盤後狀態提示。",
        ),
    ),
    ReleaseNote(
        version="Ver-20260731-141045-844",
        title="作者簽名彩蛋",
        changes=(
            "在頁面右下角加入 Rooteat 手寫草寫作者簽名。",
            "簽名支援滑鼠懸停發光與點擊展開彩蛋訊息。",
        ),
    ),
    ReleaseNote(
        version="Ver-20260731-140525-086",
        title="更新日誌上線",
        changes=(
            "在頁面右上角新增可展開的「更新日誌」。",
            "版本編號統一使用日期、時間與毫秒格式。",
            "可依版本查看功能調整與修正內容。",
        ),
    ),
    ReleaseNote(
        version="Ver-20260731-135900-000",
        title="登入狀態延長",
        changes=(
            "登入狀態改為 24 小時滑動效期。",
            "重新整理頁面後仍會保留登入狀態。",
            "連續 24 小時未使用才會自動登出。",
        ),
    ),
)

CURRENT_VERSION = CHANGELOG[0].version
