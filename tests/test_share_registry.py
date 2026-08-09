"""Offline tests for the M6 share-funnel registry (shares.jsonl).

The share counter lives in JsonMemory as a third append-only JSONL file
(sibling of the memory path), mirroring the players.jsonl registry:
record_share appends one line, count_shares / count_shares_since read it
back, corrupt lines are skipped, and the file itself is created lazily on
the first recorded share. No network, no TMA imports.
"""

import json
import time

from terramon.adapters.json_memory import JsonMemory

# Deterministic epoch used for the fixed-clock tests (2025-06-15T15:06:40Z).
FIXED_TS = 1_750_000_000.0


def _lines(tmp_path) -> list[str]:
    """Non-empty lines of the shares registry ([] if the file is absent)."""
    shares = tmp_path / "shares.jsonl"
    if not shares.exists():
        return []
    return [ln for ln in shares.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_record_share_appends_exactly_one_line(tmp_path):
    """Each tap adds exactly one JSON line with ts + iso UTC; never overwrites."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    memory.record_share(now=FIXED_TS)

    lines = _lines(tmp_path)
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["ts"] == FIXED_TS
    assert record["iso"].startswith("2025-06-15T")
    assert record["iso"].endswith("+00:00")

    # A second tap appends a second line; the first is untouched.
    memory.record_share(now=FIXED_TS + 100.0)
    lines = _lines(tmp_path)
    assert len(lines) == 2
    assert json.loads(lines[0])["ts"] == FIXED_TS
    assert json.loads(lines[1])["ts"] == FIXED_TS + 100.0


def test_count_shares(tmp_path):
    """count_shares totals valid lines; missing file counts as zero."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    assert memory.count_shares() == 0  # no file yet → zero, no crash

    for i in range(3):
        memory.record_share(now=FIXED_TS + i)
    assert memory.count_shares() == 3

    # A fresh instance reading the same on-disk file sees the same count.
    fresh = JsonMemory(tmp_path / "memory.jsonl")
    assert fresh.count_shares() == 3


def test_count_shares_skips_corrupt_lines(tmp_path):
    """A garbage line is skipped; valid neighbours still count."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    memory.record_share(now=FIXED_TS)
    with (tmp_path / "shares.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
        fh.write('{"ts": 1750000100.0, "iso": "2025-06-15T16:00:00+00:00"}\n')
    assert memory.count_shares() == 2  # corrupt line skipped, 2 valid remain


def test_count_shares_since_window(tmp_path):
    """Only lines with ts >= now - days*86400 count inside the window."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    now = time.time()
    memory.record_share(now=now - 1 * 86400)   # 1 day ago  → inside 7 d
    memory.record_share(now=now - 6 * 86400)   # 6 days ago → inside 7 d
    memory.record_share(now=now - 8 * 86400)   # 8 days ago → outside 7 d
    memory.record_share(now=now - 40 * 86400)  # 40 days ago → outside 7 d

    assert memory.count_shares() == 4
    assert memory.count_shares_since(days=7) == 2
    assert memory.count_shares_since(days=2) == 1
    assert memory.count_shares_since(days=365) == 4

    # Missing file → zero, even for a wide window.
    empty = JsonMemory(tmp_path / "other" / "memory.jsonl")
    assert empty.count_shares_since(days=7) == 0


def test_shares_file_created_lazily(tmp_path):
    """shares.jsonl is not touched until the first share is recorded."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    shares = tmp_path / "shares.jsonl"
    assert not shares.exists()

    # Read paths must work (and must not create the file) before any tap.
    assert memory.count_shares() == 0
    assert memory.count_shares_since(days=7) == 0
    assert not shares.exists()

    memory.record_share(now=FIXED_TS)
    assert shares.exists()
    assert len(_lines(tmp_path)) == 1


def test_share_methods_leave_players_registry_untouched(tmp_path):
    """record_share/count_shares never write to players.jsonl."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    now = time.time()
    memory.record_share(now=now - 3600)
    memory.record_share(now=now - 60)
    assert memory.count_shares() == 2
    assert memory.count_shares_since(days=365) == 2

    players = tmp_path / "players.jsonl"
    assert players.exists()  # created empty by __init__, like the old behaviour
    assert players.read_text(encoding="utf-8") == ""
    assert memory.load_players() == []
    assert memory.count_unique_players() == 0
    assert memory.count_returning_players(days=7) == 0
