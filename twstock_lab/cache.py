from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SQLiteCache:
    def __init__(self, path: str | Path = "data/market_cache.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def get(self, key: str, *, allow_stale: bool = False) -> tuple[Any, datetime, bool] | None:
        now = datetime.now(timezone.utc)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload, fetched_at, expires_at FROM cache WHERE cache_key = ?", (key,)
            ).fetchone()
        if not row:
            return None
        fetched = datetime.fromisoformat(row[1])
        expired = datetime.fromisoformat(row[2]) <= now
        if expired and not allow_stale:
            return None
        return json.loads(row[0]), fetched, expired

    def set(self, key: str, value: Any, ttl_seconds: int) -> datetime:
        now = datetime.now(timezone.utc)
        expires = datetime.fromtimestamp(now.timestamp() + ttl_seconds, timezone.utc)
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO cache(cache_key, payload, fetched_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload=excluded.payload,
                    fetched_at=excluded.fetched_at,
                    expires_at=excluded.expires_at""",
                (key, json.dumps(value, ensure_ascii=False), now.isoformat(), expires.isoformat()),
            )
        return now

    def delete(self, key: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM cache WHERE cache_key = ?", (key,))

