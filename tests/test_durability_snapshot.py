"""Snapshot/restore durability — offline regression guards (pure adapter).

The durability mechanism carries the /health KPI counters
(mint_count / share_count / seed_count) across Railway redeploys that
wipe data/ (declared volume not attached in the dashboard): the LOOP
snapshots the counters to data/snapshots/latest/health.json at ship time
and commits it to git; on boot, when data/tma_memory.jsonl is MISSING or
EMPTY, the app replays the snapshot and /health reports it transparently
(data_restored_from_snapshot + restored_* fields).

Like test_health_persistence.py / test_mint_lightning.py, the TMA module
is NEVER imported (importing it executes Reflex app construction at
module level) — the wiring guards read terramon_tma.py as TEXT and match
NAME markers, never line numbers.
"""

import json
import re
from pathlib import Path

import pytest

from terramon.adapters.durability import (
    SNAPSHOT_FILENAME,
    capture_health_snapshot,
    read_snapshot,
    restore_counters_if_wiped,
)

TMA_SOURCE = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"

MEMORY_PATH_MARKER = '_MEMORY_PATH = Path("data/tma_memory.jsonl")'
PLAYER_IDENTITY_MARKER = "# ── Player identity (D7 retention cohorts)"

COUNTS = {"mint_count": 3, "share_count": 7, "seed_count": 14}


# ── pure adapter behavior ───────────────────────────────────────────


def test_round_trip_capture_wipe_restore(tmp_path):
    """Capture -> wipe the memory file -> restore replays the counters."""
    captured = capture_health_snapshot(COUNTS, snapshot_dir=tmp_path)
    assert captured is not None and captured.is_file()
    assert captured.name == SNAPSHOT_FILENAME

    # memory file MISSING == wiped volume signature
    result = restore_counters_if_wiped(tmp_path / "tma_memory.jsonl", snapshot_dir=tmp_path)
    assert result["restored"] is True
    assert result["counts"] == COUNTS
    assert isinstance(result["snapshot_ts"], str) and result["snapshot_ts"]

    # empty memory file == wiped volume that JsonMemory already recreated
    mem = tmp_path / "tma_memory.jsonl"
    mem.write_text("", encoding="utf-8")
    result = restore_counters_if_wiped(mem, snapshot_dir=tmp_path)
    assert result["restored"] is True
    assert result["counts"] == COUNTS


def test_data_present_no_restore(tmp_path):
    """A non-empty memory file is the source of truth — no restore."""
    capture_health_snapshot(COUNTS, snapshot_dir=tmp_path)
    mem = tmp_path / "tma_memory.jsonl"
    mem.write_text('{"seed": "real-data"}\n', encoding="utf-8")
    result = restore_counters_if_wiped(mem, snapshot_dir=tmp_path)
    assert result["restored"] is False
    assert result["counts"] == {}
    assert result["snapshot_ts"] is None


def test_no_snapshot_restore_false(tmp_path):
    """Missing snapshot dir -> restored=False, never an exception."""
    result = restore_counters_if_wiped(
        tmp_path / "tma_memory.jsonl", snapshot_dir=tmp_path / "empty"
    )
    assert result["restored"] is False
    assert result["counts"] == {}
    assert result["snapshot_ts"] is None


def test_corrupt_snapshot_reads_none(tmp_path):
    """A corrupt health.json degrades to None, no exception."""
    snap_dir = tmp_path / "snap"
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / SNAPSHOT_FILENAME).write_text("not-json{{{", encoding="utf-8")
    assert read_snapshot(snapshot_dir=snap_dir) is None
    result = restore_counters_if_wiped(tmp_path / "tma_memory.jsonl", snapshot_dir=snap_dir)
    assert result["restored"] is False
    assert result["counts"] == {}


def test_snapshot_contains_ts_key(tmp_path):
    """capture must merge snapshot_ts into the written health.json."""
    capture_health_snapshot({"mint_count": 1}, snapshot_dir=tmp_path)
    data = json.loads((tmp_path / SNAPSHOT_FILENAME).read_text(encoding="utf-8"))
    assert data["mint_count"] == 1
    assert isinstance(data.get("snapshot_ts"), str) and data["snapshot_ts"]


# ── source-level wiring guards (TMA read as TEXT, never imported) ────


@pytest.fixture(scope="module")
def tma_source() -> str:
    """The real TMA source, read fresh from disk as TEXT (read-only)."""
    if not TMA_SOURCE.is_file():
        pytest.fail(f"app source not found: {TMA_SOURCE}")
    return TMA_SOURCE.read_text(encoding="utf-8")


def _restore_hook_region(source: str) -> str:
    """The module-level restore block: text strictly BETWEEN the
    _MEMORY_PATH line and the '# ── Player identity' comment
    (both boundary lines excluded) — same region convention as
    test_health_persistence.py's _boot_marker_region."""
    lines = source.splitlines()
    start = next((i for i, ln in enumerate(lines) if MEMORY_PATH_MARKER in ln), None)
    end = next((i for i, ln in enumerate(lines) if PLAYER_IDENTITY_MARKER in ln), None)
    if start is None:
        pytest.fail(f"'{MEMORY_PATH_MARKER}' not found in source")
    if end is None:
        pytest.fail(f"'{PLAYER_IDENTITY_MARKER}' not found in source")
    if not start < end:
        pytest.fail("'Player identity' marker appears before '_MEMORY_PATH' in source")
    return "\n".join(lines[start + 1 : end])


def _top_level_func_lines(source: str, name: str) -> list[str]:
    """Lines of a top-level function body: from its ``def name(``
    (column 0) up to the next top-level ``def``. Names, not line numbers."""
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.startswith(f"def {name}(")),
        None,
    )
    if start is None:
        pytest.fail(f"top-level function 'def {name}(' not found in source")
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^def ", lines[i])),
        len(lines),
    )
    return lines[start:end]


def test_restore_hook_block_in_module_scope(tma_source):
    """The boot-time restore hook must live in the module-level block
    between _MEMORY_PATH and the '# ── Player identity' comment: it calls
    restore_counters_if_wiped(_MEMORY_PATH) inside try/except and stamps
    _SNAPSHOT_RESTORED / _RESTORED_COUNTS / _SNAPSHOT_TS."""
    region = _restore_hook_region(tma_source)
    assert "restore_counters_if_wiped" in region, (
        "no 'restore_counters_if_wiped' call in the module-level restore block"
    )
    assert "_SNAPSHOT_RESTORED" in region, (
        "no '_SNAPSHOT_RESTORED' module flag in the restore block"
    )
    assert "_RESTORED_COUNTS" in region, (
        "no '_RESTORED_COUNTS' module dict in the restore block"
    )
    assert "_SNAPSHOT_TS" in region, "no '_SNAPSHOT_TS' module var in the restore block"
    assert "try:" in region, "restore hook is not guarded by try:"
    assert "except" in region, "restore hook has no except fallback"


def test_health_reports_snapshot_restore(tma_source):
    """The health() endpoint must surface the restore transparently:
    data_restored_from_snapshot + restored_* counters + snapshot_ts."""
    health = "\n".join(_top_level_func_lines(tma_source, "health"))
    assert "data_restored_from_snapshot" in health, (
        "'data_restored_from_snapshot' not found in health() body"
    )
    assert "restored_mint_count" in health, (
        "'restored_mint_count' not found in health() body"
    )
    assert "restored_seed_count" in health, (
        "'restored_seed_count' not found in health() body"
    )
    assert "restored_share_count" in health, (
        "'restored_share_count' not found in health() body"
    )
    assert "snapshot_ts" in health, "'snapshot_ts' not found in health() body"
