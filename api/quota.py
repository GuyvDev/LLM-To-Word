"""
api/quota.py
============
Supabase-backed quota enforcement.

Database schema (run once in Supabase SQL editor — see migrations/001_quota.sql):

  CREATE TABLE api_keys (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash      text UNIQUE NOT NULL,   -- SHA-256 of the raw key
    tier          text NOT NULL DEFAULT 'free',   -- 'anonymous'|'free'|'pro'|'team'
    email         text,
    created_at    timestamptz DEFAULT now()
  );

  CREATE TABLE usage (
    id            bigserial PRIMARY KEY,
    key_hash      text NOT NULL,
    period        text NOT NULL,   -- 'YYYY-MM'
    count         int  NOT NULL DEFAULT 0,
    UNIQUE (key_hash, period)
  );

Environment variables (set in Railway or .env):
  SUPABASE_URL       https://<project>.supabase.co
  SUPABASE_KEY       <service-role key>

Running without Supabase (SUPABASE_URL unset):
  The service falls back to an in-memory store — fine for local dev / testing.
  All IP-based identities get the anonymous limit (5/month).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# Optional dependency — only used when Supabase env vars are present.
try:
    from supabase import create_client, Client as SupabaseClient
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False


# ── Constants ─────────────────────────────────────────────────────────────────

LIMITS: dict[str, int] = {
    "anonymous": 5,
    "free":      25,
    "pro":       999_999,   # effectively unlimited
    "team":      999_999,
}


class QuotaExceeded(Exception):
    pass


@dataclass
class QuotaInfo:
    used:      int
    limit:     int
    remaining: int
    tier:      str
    resets_at: str   # ISO date string of first day of next month


# ── Service ───────────────────────────────────────────────────────────────────

class QuotaService:
    """
    Wraps quota check + increment logic.

    Prefers Supabase when configured; falls back to in-memory dict so the
    API can run locally without any external dependency.
    """

    def __init__(self) -> None:
        url  = os.getenv("SUPABASE_URL")
        key  = os.getenv("SUPABASE_KEY")
        self._db: Optional[SupabaseClient] = None

        if url and key and _SUPABASE_AVAILABLE:
            self._db = create_client(url, key)
            print("[quota] Using Supabase backend.")
        else:
            print("[quota] Supabase not configured — using in-memory fallback.")

        # In-memory fallback: { key_hash: { period: count } }
        self._mem: dict[str, dict[str, int]] = {}

    # ── Public methods ────────────────────────────────────────────────────────

    async def check_and_consume(self, identity: str, raw_key: str) -> QuotaInfo:
        """
        Verify *identity* hasn't exceeded its quota, then increment the counter.
        Raises QuotaExceeded if the limit is reached.
        """
        key_hash = _hash(identity)
        period   = _current_period()
        tier     = await self._get_tier(key_hash, raw_key)
        limit    = LIMITS.get(tier, LIMITS["anonymous"])

        used = await self._get_count(key_hash, period)

        if tier not in ("pro", "team") and used >= limit:
            raise QuotaExceeded(
                f"You have used {used}/{limit} free conversions this month. "
                f"Upgrade to Pro for unlimited access."
            )

        await self._increment(key_hash, period)
        new_used  = used + 1
        remaining = max(0, limit - new_used) if tier not in ("pro", "team") else limit
        return QuotaInfo(
            used=new_used,
            limit=limit,
            remaining=remaining,
            tier=tier,
            resets_at=_next_period_start(),
        )

    async def get_status(self, identity: str, raw_key: str) -> QuotaInfo:
        """Return current quota status without consuming a count."""
        key_hash = _hash(identity)
        period   = _current_period()
        tier     = await self._get_tier(key_hash, raw_key)
        limit    = LIMITS.get(tier, LIMITS["anonymous"])
        used     = await self._get_count(key_hash, period)
        remaining = max(0, limit - used) if tier not in ("pro", "team") else limit
        return QuotaInfo(
            used=used,
            limit=limit,
            remaining=remaining,
            tier=tier,
            resets_at=_next_period_start(),
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _get_tier(self, key_hash: str, raw_key: str) -> str:
        if raw_key == "anonymous":
            return "anonymous"
        if self._db:
            res = (
                self._db.table("api_keys")
                .select("tier")
                .eq("key_hash", key_hash)
                .maybe_single()
                .execute()
            )
            if res.data:
                return res.data["tier"]
        return "free"   # unknown key → treat as free account

    async def _get_count(self, key_hash: str, period: str) -> int:
        if self._db:
            res = (
                self._db.table("usage")
                .select("count")
                .eq("key_hash", key_hash)
                .eq("period", period)
                .maybe_single()
                .execute()
            )
            return res.data["count"] if res.data else 0
        # In-memory fallback
        return self._mem.get(key_hash, {}).get(period, 0)

    async def _increment(self, key_hash: str, period: str) -> None:
        if self._db:
            self._db.rpc(
                "upsert_usage",
                {"p_key_hash": key_hash, "p_period": period},
            ).execute()
            return
        # In-memory fallback
        self._mem.setdefault(key_hash, {})
        self._mem[key_hash][period] = self._mem[key_hash].get(period, 0) + 1


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _current_period() -> str:
    now = datetime.now(tz=timezone.utc)
    return now.strftime("%Y-%m")


def _next_period_start() -> str:
    now = datetime.now(tz=timezone.utc)
    if now.month == 12:
        return f"{now.year + 1}-01-01"
    return f"{now.year}-{now.month + 1:02d}-01"
