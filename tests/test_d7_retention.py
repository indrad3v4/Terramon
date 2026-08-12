"""Offline tests for the M8 D7-retention cohort metrics (JsonMemory).

Covers the pure cohort split (_d7_from_records), the mint-age helper
(_days_since), and the two JsonMemory methods that feed the North Star
Score's D7 half: d7_cohort_stats (eligible/retained/retention_rate over
players.jsonl) and days_since_last_mint (stale-mint age over seeds).
Everything is offline — no network, no Telegram, tmp_path only.
"""

from datetime import datetime, timedelta, timezone

from terramon.adapters.json_memory import (
    JsonMemory,
    _d7_from_records,
    _days_since,
)
from terramon.domain.player import PlayerIdentity, PlayerRecord
from terramon.domain.thought_seed import ThoughtSeed

DAY = 86400
NOW = 2_000_000_000.0  # fixed clock for the pure functions


def _rec(
    user_id: int,
    first_seen_at: float,
    last_seen_at: float | None = None,
    session_count: int = 1,
) -> PlayerRecord:
    """Synthetic PlayerRecord; last_seen defaults to first_seen (one visit)."""
    return PlayerRecord(
        user_id=user_id,
        first_seen_at=first_seen_at,
        last_seen_at=first_seen_at if last_seen_at is None else last_seen_at,
        session_count=session_count,
    )


# ── 1. Pure _d7_from_records: eligible / retained / rate ────────────────


def test_d7_cohort_split_pure():
    """10-days-old cohort: returned-yesterday retained, one-shot not,
    fresh player not eligible yet."""
    records = [
        # First visit 10 d ago, came back yesterday → retained.
        _rec(1, first_seen_at=NOW - 10 * DAY, last_seen_at=NOW - 1 * DAY, session_count=2),
        # First visit 10 d ago, never came back → eligible but NOT retained.
        _rec(2, first_seen_at=NOW - 10 * DAY),
        # First visit only 2 d ago → D7 has not arrived → not eligible.
        _rec(3, first_seen_at=NOW - 2 * DAY),
    ]
    stats = _d7_from_records(records, now=NOW, days=7)
    assert stats == {"eligible": 2, "retained": 1, "retention_rate": 0.5}


def test_d7_cohort_boundaries_inclusive():
    """first_seen exactly at the cutoff is eligible; last_seen exactly at
    first_seen + D7 counts as retained (both bounds inclusive)."""
    records = [
        # first_seen == now - 7d: D7 has just arrived → eligible; returned
        # today (last_seen == now) → retained.
        _rec(1, first_seen_at=NOW - 7 * DAY, last_seen_at=NOW, session_count=2),
        # first_seen one second inside the window → NOT eligible.
        _rec(2, first_seen_at=NOW - 7 * DAY + 1),
        # last_seen == first_seen + 7d exactly → retained (>= is inclusive).
        _rec(3, first_seen_at=NOW - 10 * DAY, last_seen_at=NOW - 3 * DAY, session_count=2),
        # last_seen one second BEFORE first_seen + 7d → not retained.
        _rec(4, first_seen_at=NOW - 10 * DAY, last_seen_at=NOW - 3 * DAY - 1, session_count=2),
    ]
    stats = _d7_from_records(records, now=NOW, days=7)
    assert stats["eligible"] == 3  # ids 1, 3, 4
    assert stats["retained"] == 2  # ids 1, 3
    assert stats["retention_rate"] == 2 / 3


def test_d7_retention_rate_zero_when_no_eligible():
    """No cohort has reached D7 yet → rate must be 0.0, never a crash."""
    # All players are fresh (first visit 2 d ago).
    fresh = [_rec(i, first_seen_at=NOW - 2 * DAY) for i in range(1, 4)]
    assert _d7_from_records(fresh, now=NOW, days=7) == {
        "eligible": 0,
        "retained": 0,
        "retention_rate": 0.0,
    }
    # Empty registry is the same degenerate case.
    assert _d7_from_records([], now=NOW, days=7) == {
        "eligible": 0,
        "retained": 0,
        "retention_rate": 0.0,
    }


def test_d7_skips_broken_records():
    """A corrupt record (non-numeric timestamps) is skipped, never raised."""
    records = [
        _rec(1, first_seen_at=NOW - 10 * DAY, last_seen_at=NOW - 1 * DAY, session_count=2),
        PlayerRecord(user_id=2, first_seen_at="garbage", last_seen_at=None),  # type: ignore[arg-type]
    ]
    stats = _d7_from_records(records, now=NOW, days=7)
    assert stats == {"eligible": 1, "retained": 1, "retention_rate": 1.0}


# ── 2. Pure _days_since helper ──────────────────────────────────────────


def test_days_since_floor_and_clamp():
    """Floor arithmetic: 3 d and 1 s → 3; future ts clamps to 0."""
    assert _days_since(NOW - 3 * DAY, NOW) == 3
    assert _days_since(NOW - 3 * DAY - 1, NOW) == 3  # floor, not ceil
    assert _days_since(NOW - 2 * DAY, NOW) == 2
    assert _days_since(NOW + 5 * DAY, NOW) == 0  # clock skew → 0, not negative


# ── 3. JsonMemory.days_since_last_mint ──────────────────────────────────


def _persist_mint(memory: JsonMemory, raw_input: str, minted_at_iso: str) -> None:
    """Save a seed and record a mint on it the way the app does.

    save_seed alone does NOT persist mint fields (they are storage-only,
    written via update_seed by the real mint loop) — mirror that path so
    load_all_seeds re-attaches minted/minted_at from disk.
    """
    memory.save_seed(
        ThoughtSeed(
            raw_input=raw_input,
            summoned_agent="Sage",
            timestamp="2026-08-09T12:00:00",
        )
    )
    assert (
        memory.update_seed("Sage", raw_input, minted=True, minted_at=minted_at_iso)
        is True
    )


def test_days_since_last_mint_none_on_empty(tmp_path):
    """No seeds / no mints → None, never a crash."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    assert memory.days_since_last_mint() is None

    # A seed that exists but was never minted is still "no mint".
    memory.save_seed(ThoughtSeed(raw_input="x", summoned_agent="Sage", timestamp="2026-08-09T12:00:00"))
    assert memory.days_since_last_mint() is None


def test_days_since_last_mint_takes_newest(tmp_path):
    """minted_at = now-3 d → 3; an older mint must not win."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    _persist_mint(memory, "old-mint", ten_days_ago)
    _persist_mint(memory, "new-mint", three_days_ago)
    memory.save_seed(ThoughtSeed(raw_input="unminted", summoned_agent="Sage", timestamp="2026-08-09T12:00:00"))

    assert memory.days_since_last_mint() == 3  # newest mint wins


def test_days_since_last_mint_skips_broken_timestamps(tmp_path):
    """A minted seed with an unparseable minted_at is skipped, not fatal."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    _persist_mint(memory, "broken-mint", "not-a-timestamp")
    _persist_mint(memory, "good-mint", (datetime.now(timezone.utc) - timedelta(days=2)).isoformat())
    assert memory.days_since_last_mint() == 2


# ── 3b. JsonMemory.days_since_first_seed ────────────────────────────────


def test_days_since_first_seed_none_on_empty(tmp_path):
    """No seeds -> None; a seed with an unparseable timestamp is also None."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    assert memory.days_since_first_seed() is None

    # A broken timestamp must be skipped, never fatal — with no other
    # seeds there is no parseable anchor left -> None.
    memory.save_seed(
        ThoughtSeed(
            raw_input="broken", summoned_agent="Sage", timestamp="not-a-timestamp"
        )
    )
    assert memory.days_since_first_seed() is None


def test_days_since_first_seed_takes_oldest(tmp_path):
    """The EARLIEST summon timestamp wins: 10 d ago beats 2 d ago -> 10."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    memory.save_seed(
        ThoughtSeed(raw_input="young", summoned_agent="Sage", timestamp=two_days_ago)
    )
    memory.save_seed(
        ThoughtSeed(raw_input="old", summoned_agent="Sage", timestamp=ten_days_ago)
    )

    assert memory.days_since_first_seed() == 10  # oldest wins


def test_days_since_first_seed_skips_broken_timestamps(tmp_path):
    """A corrupt timestamp line is skipped; the good seed still anchors."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    memory.save_seed(
        ThoughtSeed(
            raw_input="broken", summoned_agent="Sage", timestamp="not-a-timestamp"
        )
    )
    memory.save_seed(
        ThoughtSeed(
            raw_input="good",
            summoned_agent="Sage",
            timestamp=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        )
    )
    assert memory.days_since_first_seed() == 2


def test_days_since_first_seed_after_mint_anchor_usable(tmp_path):
    """A later-minted seed still anchors on its SUMMON timestamp, and the
    first summon is never newer than the newest mint."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    _persist_mint(
        memory, "creature", (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    )

    first = memory.days_since_first_seed()
    last = memory.days_since_last_mint()
    assert first is not None
    assert last is not None
    assert first >= last  # first summon is never newer than newest mint


# ── 4. JsonMemory.d7_cohort_stats on disk (tmp_path) ────────────────────


def test_d7_cohort_stats_on_disk(tmp_path):
    """d7_cohort_stats reads players.jsonl the same way count_unique_players
    does and returns the classic eligible/retained/rate split."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    now = datetime.now(timezone.utc).timestamp()
    # Retained: first visit 10 d ago, returned yesterday.
    memory.record_player(
        PlayerIdentity(user_id=301, first_name="A"),
        now=now - 10 * DAY,
    )
    memory.record_player(
        PlayerIdentity(user_id=301, first_name="A"),
        now=now - 1 * DAY,
    )
    # Lapsed: first visit 10 d ago, never returned.
    memory.record_player(
        PlayerIdentity(user_id=302, first_name="B"),
        now=now - 10 * DAY,
    )
    # Fresh: first visit 2 d ago → not eligible.
    memory.record_player(
        PlayerIdentity(user_id=303, first_name="C"),
        now=now - 2 * DAY,
    )

    assert memory.count_unique_players() == 3
    stats = memory.d7_cohort_stats(days=7)
    assert stats["eligible"] == 2
    assert stats["retained"] == 1
    assert stats["retention_rate"] == 0.5


def test_d7_cohort_stats_empty_and_corrupt(tmp_path):
    """Empty or corrupt players registry → zeros, never a crash."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    assert memory.d7_cohort_stats() == {
        "eligible": 0,
        "retained": 0,
        "retention_rate": 0.0,
    }
    # A corrupt JSONL line must be skipped by load_players (same as
    # count_unique_players) without breaking the metric; the valid line
    # below (first_seen 1970 → long past D7) is eligible but not retained.
    memory.players_path.write_text(
        "{this is not json}\n"
        + '{"user_id": 401, "first_seen_at": 1.0, "last_seen_at": 1.0, "session_count": 1}\n',
        encoding="utf-8",
    )
    stats = memory.d7_cohort_stats(days=7)
    assert stats == {"eligible": 1, "retained": 0, "retention_rate": 0.0}


def test_d7_and_mint_work_together_on_disk(tmp_path):
    """Both M8 methods are pure offline reads over the same JsonMemory."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    now = datetime.now(timezone.utc).timestamp()

    # One retained player + one minted seed.
    memory.record_player(PlayerIdentity(user_id=501), now=now - 10 * DAY)
    memory.record_player(PlayerIdentity(user_id=501), now=now - 1 * DAY)
    _persist_mint(memory, "creature", (datetime.now(timezone.utc) - timedelta(days=3)).isoformat())

    assert memory.d7_cohort_stats(days=7)["retention_rate"] == 1.0
    assert memory.days_since_last_mint() == 3
