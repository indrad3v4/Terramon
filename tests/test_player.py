"""Offline tests for Terramon player identification (Telegram initData).

Covers the full identity chain without any network: signature verification
(HMAC-SHA256 per Telegram WebApp spec), expiry, the persistent players
registry upsert, returning-player counting, /health exposure, and the
graceful anonymous fallback.
"""

import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

import pytest

from terramon.adapters.json_memory import JsonMemory
from terramon.domain.player import (
    MAX_AUTH_AGE_SECONDS,
    PlayerIdentity,
    PlayerRecord,
    SESSION_WINDOW_SECONDS,
    merge_player_record,
    verify_init_data,
)

TEST_BOT_TOKEN = os.environ.get("TERRAMON_BOT_TOKEN", "") or "123456:TEST-BOT-TOKEN"
TEST_USER = {
    "id": 424242,
    "first_name": "Ivan",
    "username": "ivan_test",
    "language_code": "ru",
    "is_premium": True,
}


def build_init_data(
    bot_token: str = TEST_BOT_TOKEN,
    user: dict | None = None,
    auth_date: int | None = None,
    extra: dict | None = None,
) -> str:
    """Build a Telegram-spec initData string signed with the bot token.

    Mirrors the official algorithm: secret_key = HMAC_SHA256('WebAppData',
    bot_token); hash = HMAC_SHA256(secret_key, sorted 'k=v' lines).
    """
    params: dict[str, str] = {
        "auth_date": str(int(auth_date if auth_date is not None else time.time())),
        "query_id": "AAHd3N6sAAAAAN3c3qzLv1qz",
        "user": json.dumps(user if user is not None else TEST_USER),
    }
    if extra:
        params.update(extra)
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    params["hash"] = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(params)


# ── 1. Signature verification ──────────────────────────────────────────


def test_verify_valid_initdata():
    """A correctly signed initData yields the Telegram user id."""
    verified = verify_init_data(build_init_data(), TEST_BOT_TOKEN)
    assert verified is not None
    assert verified["id"] == 424242
    assert verified["first_name"] == "Ivan"
    assert verified["username"] == "ivan_test"

    identity = PlayerIdentity.from_init_data(build_init_data(), TEST_BOT_TOKEN)
    assert identity is not None
    assert identity.user_id == 424242
    assert identity.platform == "telegram"


def test_verify_invalid_hash_rejected():
    """Tampered data (hash does not match) is rejected, not trusted."""
    tampered = build_init_data()
    # Flip one bit of the payload: swap the username, keep the old hash.
    tampered_params = dict(
        (k, v) for k, v in (p.split("=", 1) for p in tampered.split("&"))
    )
    good_user = tampered_params["user"]
    evil_user = json.dumps({**TEST_USER, "username": "attacker"})
    evil = tampered.replace(good_user, evil_user)
    assert verify_init_data(evil, TEST_BOT_TOKEN) is None
    # Wrong bot token must also fail (signature is token-bound).
    assert verify_init_data(build_init_data(), "999:WRONG-TOKEN") is None
    # Garbage strings must not raise.
    assert verify_init_data("not=an=initdata&hash=deadbeef", TEST_BOT_TOKEN) is None


def test_verify_expired_rejected():
    """initData older than 24 h is stale and must be rejected."""
    stale = build_init_data(auth_date=int(time.time()) - MAX_AUTH_AGE_SECONDS - 10)
    assert verify_init_data(stale, TEST_BOT_TOKEN) is None

    fresh = build_init_data(auth_date=int(time.time()) - 60)
    assert verify_init_data(fresh, TEST_BOT_TOKEN) is not None


# ── 2. Players registry persistence ─────────────────────────────────────


def test_record_player_upsert(tmp_path):
    """Same user twice → session_count increments, first_seen stays stable."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    first = PlayerIdentity(user_id=7, first_name="Ada", username="ada")
    second = PlayerIdentity(user_id=7, first_name="Ada", username="ada")

    rec1 = memory.record_player(first, now=1_000_000.0)
    assert rec1 is not None
    assert rec1.session_count == 1
    assert rec1.first_seen_at == 1_000_000.0

    # Visit inside the 30 min window = same session (reload guard).
    rec2 = memory.record_player(second, now=1_000_000.0 + 60)
    assert rec2.session_count == 1
    assert rec2.first_seen_at == 1_000_000.0

    # Visit well OUTSIDE the window (next day) = a NEW session.
    rec3 = memory.record_player(second, now=1_000_000.0 + SESSION_WINDOW_SECONDS + 86400)
    assert rec3.session_count == 2
    assert rec3.first_seen_at == 1_000_000.0  # first_seen immutable

    loaded = memory.load_players()
    assert len(loaded) == 1  # still ONE line in the registry
    assert loaded[0].session_count == 2
    assert loaded[0].user_id == 7

    # Anonymous identities are never persisted.
    assert memory.record_player(PlayerIdentity.anonymous(), now=1_000_000.0) is None
    assert len(memory.load_players()) == 1


def test_count_returning(tmp_path):
    """2-session player within 7 d counts as returning; 1-session does not."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    now = time.time()

    returning = PlayerIdentity(user_id=101, first_name="R", username="r")
    one_shot = PlayerIdentity(user_id=102, first_name="O", username="o")
    lapsed = PlayerIdentity(user_id=103, first_name="L", username="l")

    memory.record_player(returning, now=now - 3 * 86400)  # first visit 3 d ago
    memory.record_player(returning, now=now - 2 * 86400)  # returned 2 d ago
    memory.record_player(one_shot, now=now - 3600)        # fresh but only 1 session
    memory.record_player(lapsed, now=now - 30 * 86400)    # 2 sessions, long ago
    memory.record_player(lapsed, now=now - 29 * 86400)

    assert memory.count_unique_players() == 3
    assert memory.count_returning_players(days=7) == 1  # only `returning`

    # Pure merge check: 2 sessions far apart => session_count 2.
    merged = merge_player_record(
        None, PlayerIdentity(user_id=1), now=100.0
    )
    merged = merge_player_record(
        merged, PlayerIdentity(user_id=1), now=100.0 + SESSION_WINDOW_SECONDS + 1
    )
    assert merged.session_count == 2


# ── 3. /health exposure ────────────────────────────────────────────────


def test_health_exposes_players(tmp_path):
    """/health JSON must carry player_count + returning_players_7d."""
    from terramon_tma import terramon_tma as tma

    memory = JsonMemory(tmp_path / "memory.jsonl")
    now = time.time()
    memory.record_player(
        PlayerIdentity(user_id=201, first_name="A"), now=now - 86400
    )
    memory.record_player(
        PlayerIdentity(user_id=201, first_name="A"),
        now=now - 3600,
    )

    original = tma._MEMORY
    tma._MEMORY = memory
    try:
        response = tma.health(None)
        payload = json.loads(response.body)
    finally:
        tma._MEMORY = original

    assert payload["status"] == "ok"
    assert payload["player_count"] == 1
    assert payload["returning_players_7d"] == 1


def test_health_source_mentions_player_metrics():
    """Source guard: /health keeps the player KPIs for the cron (no regress)."""
    source = open(
        os.path.join(os.path.dirname(__file__), "..", "terramon_tma", "terramon_tma.py"),
        encoding="utf-8",
    ).read()
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.startswith("def health(")),
        None,
    )
    assert start is not None, "top-level 'def health(' not found in source"
    tail = "\n".join(lines[start:])
    assert "player_count" in tail
    assert "returning_players_7d" in tail
    assert "mint_count" in tail  # pre-existing KPI must stay


# ── 4. Graceful anonymous fallback ─────────────────────────────────────


def test_no_initdata_anon():
    """No initData → anonymous identity, no crash, no registry write."""
    assert verify_init_data(None, TEST_BOT_TOKEN) is None
    assert verify_init_data("", TEST_BOT_TOKEN) is None
    assert PlayerIdentity.from_init_data(None, TEST_BOT_TOKEN) is None
    assert PlayerIdentity.from_init_data("", TEST_BOT_TOKEN) is None

    anon = PlayerIdentity.anonymous()
    assert anon.user_id == 0
    assert anon.platform == "anon"

    # The TMA event path must not raise with an empty result.
    from terramon_tma import terramon_tma as tma

    state = tma.TerramonState()
    assert state.player_identity == ""
    state.on_init_data("")  # no initData (plain browser / headless)
    assert state.player_identity == "anon"
    # The game-critical load_terra still runs (anon session proceeds).
    assert tma._INITDATA_JS  # capture snippet exists
