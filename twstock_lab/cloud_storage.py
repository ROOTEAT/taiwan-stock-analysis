from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from .portfolio import PortfolioItem


USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,32}$")
AUTH_SESSION_SECONDS = 24 * 60 * 60


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    normalized = normalize_username(username)
    if not USERNAME_RE.fullmatch(normalized):
        raise ValueError("帳號需為 3–32 個英文字母、數字、底線、句點或連字號")
    return normalized


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("密碼至少需要 8 個字元")
    if len(password) > 128:
        raise ValueError("密碼不可超過 128 個字元")


def hash_password(password: str, salt: bytes | None = None) -> str:
    validate_password(password)
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return "pbkdf2_sha256$310000$%s$%s" % (
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def sign_session_token(
    user_id: str,
    username: str,
    secret: str,
    *,
    now: int | None = None,
) -> str:
    if len(secret) < 32:
        raise ValueError("Cookie 加密金鑰至少需要 32 個字元")
    payload = {
        "uid": str(uuid.UUID(user_id)),
        "usr": validate_username(username),
        "active": int(time.time() if now is None else now),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=")
    signature = hmac.new(secret.encode("utf-8"), encoded, hashlib.sha256).digest()
    return (
        encoded.decode("ascii")
        + "."
        + base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    )


def verify_session_token(
    token: str,
    secret: str,
    *,
    now: int | None = None,
    max_idle_seconds: int = AUTH_SESSION_SECONDS,
) -> dict[str, str | int] | None:
    try:
        payload_text, signature_text = token.split(".", 1)
        payload_bytes = payload_text.encode("ascii")
        supplied = base64.urlsafe_b64decode(
            signature_text + "=" * (-len(signature_text) % 4)
        )
        expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            return None
        payload = json.loads(
            base64.urlsafe_b64decode(payload_text + "=" * (-len(payload_text) % 4))
        )
        current = int(time.time() if now is None else now)
        active = int(payload["active"])
        if active > current + 300 or current - active > max_idle_seconds:
            return None
        return {
            "id": str(uuid.UUID(payload["uid"])),
            "username": validate_username(payload["usr"]),
            "active": active,
        }
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


@dataclass(frozen=True)
class CloudUser:
    id: str
    username: str


class SupabaseClient:
    """Small server-side Supabase REST client.

    The service-role key must only live in Streamlit secrets. Tables use RLS with
    no public policies, so browser visitors cannot query data directly.
    """

    def __init__(self, url: str, service_role_key: str, timeout: float = 12.0) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, table: str, **kwargs):
        response = requests.request(
            method,
            f"{self.url}/rest/v1/{table}",
            headers={**self.headers, **kwargs.pop("headers", {})},
            timeout=self.timeout,
            **kwargs,
        )
        if response.status_code >= 400:
            detail = response.text[:300]
            raise RuntimeError(f"雲端資料庫錯誤（{response.status_code}）：{detail}")
        if not response.content:
            return None
        return response.json()

    def register(self, username: str, password: str) -> CloudUser:
        username = validate_username(username)
        validate_password(password)
        existing = self._request(
            "GET", "app_users", params={"select": "id", "username": f"eq.{username}"}
        )
        if existing:
            raise ValueError("此帳號已有人使用")
        user_id = str(uuid.uuid4())
        try:
            rows = self._request(
                "POST",
                "app_users",
                params={"select": "id,username"},
                headers={"Prefer": "return=representation"},
                json={
                    "id": user_id,
                    "username": username,
                    "password_hash": hash_password(password),
                },
            )
        except RuntimeError as exc:
            if "duplicate" in str(exc).lower():
                raise ValueError("此帳號已有人使用") from exc
            raise
        return CloudUser(rows[0]["id"], rows[0]["username"])

    def authenticate(self, username: str, password: str) -> CloudUser | None:
        username = normalize_username(username)
        rows = self._request(
            "GET",
            "app_users",
            params={
                "select": "id,username,password_hash",
                "username": f"eq.{username}",
                "limit": "1",
            },
        )
        if not rows or not verify_password(password, rows[0]["password_hash"]):
            return None
        return CloudUser(rows[0]["id"], rows[0]["username"])

    def get_user(self, user_id: str, username: str) -> CloudUser | None:
        rows = self._request(
            "GET",
            "app_users",
            params={
                "select": "id,username",
                "id": f"eq.{user_id}",
                "username": f"eq.{normalize_username(username)}",
                "limit": "1",
            },
        )
        if not rows:
            return None
        return CloudUser(rows[0]["id"], rows[0]["username"])


class SupabasePortfolioStore:
    def __init__(self, client: SupabaseClient, user_id: str) -> None:
        self.client = client
        self.user_id = user_id

    def upsert(self, item: PortfolioItem) -> None:
        if item.shares < 0 or item.average_cost < 0:
            raise ValueError("股數與平均成本不可為負數")
        self.client._request(
            "POST",
            "portfolio_items",
            params={"on_conflict": "user_id,code"},
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            json={
                "user_id": self.user_id,
                "code": item.code,
                "shares": float(item.shares),
                "average_cost": float(item.average_cost),
                "note": item.note,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def delete(self, code: str) -> None:
        self.client._request(
            "DELETE",
            "portfolio_items",
            params={"user_id": f"eq.{self.user_id}", "code": f"eq.{code}"},
        )

    def list(self) -> list[PortfolioItem]:
        rows = self.client._request(
            "GET",
            "portfolio_items",
            params={
                "select": "code,shares,average_cost,note",
                "user_id": f"eq.{self.user_id}",
                "order": "code.asc",
            },
        )
        return [
            PortfolioItem(
                row["code"],
                float(row["shares"]),
                float(row["average_cost"]),
                row.get("note", ""),
            )
            for row in rows
        ]


SUPABASE_SCHEMA_SQL = """
create extension if not exists pgcrypto;

create table if not exists public.app_users (
  id uuid primary key default gen_random_uuid(),
  username text not null unique,
  password_hash text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.portfolio_items (
  user_id uuid not null references public.app_users(id) on delete cascade,
  code text not null,
  shares double precision not null default 0 check (shares >= 0),
  average_cost double precision not null default 0 check (average_cost >= 0),
  note text not null default '',
  updated_at timestamptz not null default now(),
  primary key (user_id, code)
);

alter table public.app_users enable row level security;
alter table public.portfolio_items enable row level security;
revoke all on public.app_users from anon, authenticated;
revoke all on public.portfolio_items from anon, authenticated;
grant select, insert, update, delete on public.app_users to service_role;
grant select, insert, update, delete on public.portfolio_items to service_role;
""".strip()
