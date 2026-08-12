"""Boot-baked snapshot fallback tests (Lesson 14 shape contract).

The Railway volume mounts AT /app/data, shadowing the image-baked
data/snapshots on the first boot with a fresh (empty) volume — so
restore_counters_if_wiped had no baseline (restored=False). The fix:
read_snapshot falls back to /app/boot_snapshots (baked outside the
volume by the Dockerfile).
"""

from __future__ import annotations

import json

import pytest

import terramon.adapters.durability as dur


def _write_snapshot(dir_path, counts: dict) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    payload = dict(counts)
    payload["snapshot_ts"] = "2026-08-10T05:49:34+00:00"
    (dir_path / dur.SNAPSHOT_FILENAME).write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_read_snapshot_falls_back_to_boot_dir(tmp_path, monkeypatch) -> None:
    """Primary dir empty (volume-shadowed) -> boot-baked snapshot wins."""
    boot = tmp_path / "boot_snapshots" / "latest"
    _write_snapshot(boot, {"seed_count": 40, "mint_count": 7})
    monkeypatch.setattr(dur, "BOOT_SNAPSHOT_DIR", boot)

    empty_primary = tmp_path / "data" / "snapshots" / "latest"
    snap = dur.read_snapshot(empty_primary)

    assert snap is not None
    assert snap["seed_count"] == 40
    assert snap["mint_count"] == 7


def test_read_snapshot_primary_wins(tmp_path, monkeypatch) -> None:
    """A real (volume-persisted) snapshot beats the boot-baked one."""
    boot = tmp_path / "boot" / "latest"
    _write_snapshot(boot, {"seed_count": 40})
    monkeypatch.setattr(dur, "BOOT_SNAPSHOT_DIR", boot)

    primary = tmp_path / "data" / "snapshots" / "latest"
    _write_snapshot(primary, {"seed_count": 99, "mint_count": 3})

    snap = dur.read_snapshot(primary)
    assert snap is not None
    assert snap["seed_count"] == 99  # primary is the source of truth


def test_restore_uses_boot_snapshot_when_memory_wiped(tmp_path, monkeypatch) -> None:
    """Memory missing + primary snapshots shadowed -> restore from boot dir."""
    boot = tmp_path / "boot" / "latest"
    _write_snapshot(boot, {"seed_count": 40, "mint_count": 7, "share_count": 2})
    monkeypatch.setattr(dur, "BOOT_SNAPSHOT_DIR", boot)

    data_dir = tmp_path / "data"
    primary = data_dir / "snapshots" / "latest"
    memory = data_dir / "tma_memory.jsonl"  # does NOT exist -> wiped

    result = dur.restore_counters_if_wiped(memory, primary)

    assert result["restored"] is True
    assert result["counts"]["seed_count"] == 40
    assert result["counts"]["mint_count"] == 7
    assert result["snapshot_ts"] == "2026-08-10T05:49:34+00:00"


def test_restore_skips_when_memory_has_data(tmp_path, monkeypatch) -> None:
    """Real memory data = source of truth; no restore, no boot fallback."""
    boot = tmp_path / "boot" / "latest"
    _write_snapshot(boot, {"seed_count": 40})
    monkeypatch.setattr(dur, "BOOT_SNAPSHOT_DIR", boot)

    data_dir = tmp_path / "data"
    primary = data_dir / "snapshots" / "latest"
    memory = data_dir / "tma_memory.jsonl"
    memory.parent.mkdir(parents=True, exist_ok=True)
    memory.write_text('{"some": "real data"}', encoding="utf-8")

    result = dur.restore_counters_if_wiped(memory, primary)
    assert result["restored"] is False


def test_read_snapshot_none_when_both_missing(tmp_path, monkeypatch) -> None:
    """Neither dir has a snapshot -> None (never raises)."""
    monkeypatch.setattr(
        dur, "BOOT_SNAPSHOT_DIR", tmp_path / "no_such_boot" / "latest"
    )
    assert dur.read_snapshot(tmp_path / "no_such_primary") is None


@pytest.fixture(autouse=True)
def _restore_constants():
    """Keep module constants intact across tests (monkeypatch safety)."""
    yield
