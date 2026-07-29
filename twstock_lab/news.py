from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus

import requests

from .cache import SQLiteCache

POSITIVE = {
    "growth", "record", "surge", "beat", "upgrade", "profit", "innovation", "demand",
    "合作", "成長", "創高", "優於預期", "獲利", "擴產", "訂單",
}
NEGATIVE = {
    "decline", "drop", "cut", "risk", "warning", "loss", "sanction", "investigation",
    "下滑", "衰退", "虧損", "制裁", "調查", "風險", "下修",
}


@dataclass(frozen=True)
class NewsSentiment:
    score: float
    article_count: int
    positive_count: int
    negative_count: int
    headlines: list[str]
    source: str
    warning: str | None = None


class GDELTNewsProvider:
    def __init__(self, cache: SQLiteCache | None = None, timeout: int = 15) -> None:
        self.cache = cache or SQLiteCache()
        self.timeout = timeout

    def analyze(self, query: str) -> NewsSentiment:
        key = f"news:gdelt:{query.lower()}"
        cached = self.cache.get(key)
        if cached:
            return NewsSentiment(**cached[0])
        url = (
            "https://api.gdeltproject.org/api/v2/doc/doc?"
            f"query={quote_plus(query)}&mode=artlist&format=json&maxrecords=25&timespan=7d"
        )
        try:
            response = requests.get(url, timeout=self.timeout, headers={"User-Agent": "TaiwanStockResearch/1.0"})
            response.raise_for_status()
            articles = response.json().get("articles", [])
            titles = [str(item.get("title", "")).strip() for item in articles if item.get("title")]
            positive = sum(any(word in title.lower() for word in POSITIVE) for title in titles)
            negative = sum(any(word in title.lower() for word in NEGATIVE) for title in titles)
            scored = positive + negative
            score = 50 if not scored else 50 + (positive - negative) / scored * 35
            result = NewsSentiment(
                round(max(0, min(100, score)), 1), len(titles), positive, negative,
                titles[:8], "GDELT DOC 2.0",
            )
            self.cache.set(key, result.__dict__, 3600)
            return result
        except Exception as exc:
            stale = self.cache.get(key, allow_stale=True)
            if stale:
                payload = dict(stale[0])
                payload["warning"] = f"新聞來源暫時不可用，採用舊快取：{exc}"
                return NewsSentiment(**payload)
            return NewsSentiment(50, 0, 0, 0, [], "GDELT DOC 2.0", f"新聞情緒未納入：{exc}")
