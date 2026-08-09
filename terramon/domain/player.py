"""Player identity — Telegram Mini App initData verification (pure stdlib).

D7 retention cohorts need a stable player identity. The TMA ships a signed
``initData`` string (Telegram WebApp spec) that carries the Telegram user id;
we verify its HMAC-SHA256 signature with the bot token and, only when the
signature is valid and fresh, attribute the session to a real player.

This module is deliberately dependency-free (hmac/hashlib/urllib only) so it
runs in any context — tests, the TMA backend, offline scripts.

Telegram WebApp validation algorithm (official spec):
  1. secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
  2. data_check_string = sorted params "k=v" joined with "\n"
  3. hash_check = HMAC_SHA256(key=secret_key, msg=data_check_string)
  4. accept only when hash_check == hash AND auth_date is fresh.

Auth is ADDITIVE: no initData / invalid signature / expired auth_date all
return ``None`` and the caller falls back to the anonymous player. The game
never breaks without initData.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

# Telegrams' official HMAC key label for the secret key derivation.
_WEBAPP_DATA_KEY = b"WebAppData"
# initData older than this is rejected (Telegram bots often re-issue
# initData on every WebApp open; 24 h is the commonly used freshness bound).
MAX_AUTH_AGE_SECONDS = 86400


def _derive_secret_key(bot_token: str) -> bytes:
    """secret_key = HMAC_SHA256(key='WebAppData', msg=bot_token)."""
    return hmac.new(
        _WEBAPP_DATA_KEY, bot_token.encode("utf-8"), hashlib.sha256
    ).digest()


def verify_init_data(init_data: str | None, bot_token: str) -> dict | None:
    """Verify a Telegram WebApp initData string against the bot token.

    Returns a plain dict with the verified user fields on success::

        {"id": 123456789, "first_name": "...", "username": "..."}

    Returns ``None`` when initData is absent, malformed, tampered (bad
    signature), or stale (auth_date older than MAX_AUTH_AGE_SECONDS). Never
    raises — invalid input is a rejection, not a crash.
    """
    if not init_data or not bot_token:
        return None
    try:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = params.get("hash", "")
        auth_date = params.get("auth_date", "")
        user_raw = params.get("user", "")
        if not received_hash or not auth_date or not user_raw:
            return None

        # Freshness: auth_date is a unix epoch (seconds).
        try:
            if int(time.time()) - int(auth_date) > MAX_AUTH_AGE_SECONDS:
                return None
        except (TypeError, ValueError):
            return None

        # data_check_string: all params except hash, sorted, "k=v", "\n"-joined.
        data_check_string = "\n".join(
            f"{k}={v}"
            for k, v in sorted(params.items())
            if k != "hash"
        )
        secret_key = _derive_secret_key(bot_token)
        expected = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            return None

        # user is a URL-encoded JSON object (parse_qsl already decoded it).
        user = json.loads(user_raw)
        if not isinstance(user, dict):
            return None
        return {
            "id": user.get("id"),
            "first_name": user.get("first_name") or "",
            "username": user.get("username") or "",
        }
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


@dataclass(frozen=True)
class PlayerIdentity:
    """A verified player. ``user_id`` is the Telegram account id."""

    user_id: int
    first_name: str = ""
    username: str = ""
    platform: str = "telegram"

    @classmethod
    def from_init_data(cls, init_data: str | None, bot_token: str) -> "PlayerIdentity | None":
        """Build a PlayerIdentity from raw initData, or None when unverifiable."""
        verified = verify_init_data(init_data, bot_token)
        if verified is None or verified.get("id") is None:
            return None
        return cls(
            user_id=int(verified["id"]),
            first_name=verified.get("first_name", "") or "",
            username=verified.get("username", "") or "",
        )

    @classmethod
    def anonymous(cls) -> "PlayerIdentity":
        """Fallback identity used when initData is absent/invalid.

        Kept as a real object (not None) so downstream code can always call
        ``record_player`` without branching; the registry ignores None ids.
        """
        return cls(user_id=0, first_name="", username="", platform="anon")


@dataclass
class PlayerRecord:
    """Persisted per-player session bookkeeping (one JSONL line per player)."""

    user_id: int
    first_seen_at: float
    last_seen_at: float
    session_count: int = 1
    first_name: str = ""
    username: str = ""
    platform: str = "telegram"

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "session_count": self.session_count,
            "first_name": self.first_name,
            "username": self.username,
            "platform": self.platform,
        }

    @classmethod
    def from_dict(cls, record: dict) -> "PlayerRecord":
        return cls(
            user_id=int(record["user_id"]),
            first_seen_at=float(record.get("first_seen_at", 0.0)),
            last_seen_at=float(record.get("last_seen_at", 0.0)),
            session_count=int(record.get("session_count", 1)),
            first_name=record.get("first_name", "") or "",
            username=record.get("username", "") or "",
            platform=record.get("platform", "telegram") or "telegram",
        )


def _now() -> float:
    """Test-friendly clock hook (monkeypatched in tests)."""
    return time.time()


# Two opens of the same TMA within this window count as ONE session (a page
# reload / tab switch must not inflate session_count into a fake "return").
SESSION_WINDOW_SECONDS = 1800  # 30 min


def merge_player_record(
    existing: PlayerRecord | None,
    identity: PlayerIdentity,
    now: float,
) -> PlayerRecord:
    """Upsert semantics for one player visit. Pure function (no I/O)."""
    if existing is None:
        return PlayerRecord(
            user_id=identity.user_id,
            first_seen_at=now,
            last_seen_at=now,
            session_count=1,
            first_name=identity.first_name,
            username=identity.username,
            platform=identity.platform,
        )
    # Same session (reload within the window): refresh last_seen only.
    if now - existing.last_seen_at < SESSION_WINDOW_SECONDS:
        existing.last_seen_at = now
        return existing
    # New session: count it, keep first_seen stable.
    existing.last_seen_at = now
    existing.session_count += 1
    if identity.first_name:
        existing.first_name = identity.first_name
    if identity.username:
        existing.username = identity.username
    return existing
