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
