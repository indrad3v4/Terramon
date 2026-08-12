"""Snapshot/restore durability adapter — KPI counters survive data-dir wipes.

Problem: railway.json declares a volume at /app/data but it is NOT
attached in the Railway dashboard, so every redeploy wipes data/ and the
/health counters (mint_count / share_count / seed_count) reset to 0.
That erases NSS evidence (a future real Lightning mint record) and
confuses the kill-condition monitor.

Fix pattern (grounded in OSS references): LNbits
(github.com/lnbits/lnbits) treats the payment ledger as the durable
source of truth; git-based backup tooling (borg/git-annex) uses
'checkpoint the truth, replay on restore'. We do exactly that:

  - the LOOP (orchestrator) snapshots the /health COUNTERS to
    data/snapshots/latest/health.json at ship time via
    capture_health_snapshot() and commits it to git (data/ is gitignored
    -> .gitignore negations keep data/snapshots/ trackable; .dockerignore
    only excludes data/*.jsonl so the snapshot survives into the image);
  - on boot, if data/tma_memory.jsonl is MISSING or EMPTY (wiped
    volume), restore_counters_if_wiped() replays the snapshot counters
    and /health reports them transparently
    (data_restored_from_snapshot: true + restored_* fields).

No fabricated data: only the app's own real counters carried across
infra wipes, clearly labeled.

Design (mirrors reverse_geo.py):
  - pure stdlib, NO Reflex imports, importable in offline tests;
  - NEVER raises: any failure (missing dir, corrupt JSON, unwritable
    disk) degrades to None / empty result / restored=False.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("terramon.durability")

SNAPSHOT_DIR = Path(os.environ.get("TERRAMON_DATA_DIR", "data")) / "snapshots" / "latest"
# Boot-baked fallback: the Railway volume mounts AT /app/data, shadowing the
# image-baked data/snapshots on the first boot with a fresh (empty) volume —
# so restore_counters_if_wiped found nothing and reported restored=False.
# The Dockerfile copies data/snapshots to /app/boot_snapshots (outside the
# volume) so a wiped boot still has a ship-time baseline to replay.
BOOT_SNAPSHOT_DIR = Path(
    os.environ.get("TERRAMON_BOOT_SNAPSHOT_DIR", "/app/boot_snapshots/latest")
)
SNAPSHOT_FILENAME = "health.json"
# The only counters the app replays additively into /health (spec: the
# restore is a baseline for mint/share/seed evidence; player cohorts are
# recomputed from the memory file itself).
RESTORE_COUNTER_KEYS = ("mint_count", "share_count", "seed_count")


def _resolve_dir(snapshot_dir: str | Path | None) -> Path:
    """Resolve the snapshot directory (None -> the default SNAPSHOT_DIR)."""
    if snapshot_dir is not None:
        return Path(snapshot_dir)
    return SNAPSHOT_DIR


def capture_health_snapshot(counts: dict, snapshot_dir: str | Path | None = None) -> Path | None:
    """Persist the /health counters (plus an ISO-8601 UTC snapshot_ts).

    The snapshot file is written atomically (tmp file + os.replace) so a
    crash mid-write can never leave a half-written health.json, and the
    call is idempotent (re-running overwrites the previous snapshot).
    The merged dict (counts + snapshot_ts) is built here in code.

    Returns the written Path on success, None on any failure. NEVER raises.
    """
    out_dir = _resolve_dir(snapshot_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        merged = dict(counts or {})
        merged["snapshot_ts"] = datetime.now(timezone.utc).isoformat()
        target = out_dir / SNAPSHOT_FILENAME
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, target)
        return target
    except Exception as exc:
        log.warning("durability: snapshot write failed for %s: %s", out_dir, exc)
        return None


def _snapshot_candidates(snapshot_dir: str | Path | None):
    """Primary snapshot dir, then the boot-baked dir (volume-shadow safe).

    The primary dir is where the app writes snapshots (data/snapshots, on
    the Railway volume once attached). The boot dir is baked into the image
    at /app/boot_snapshots — it survives the volume shadowing /app/data on
    the first boot after a wipe, giving the restore a real baseline.
    """
    primary = _resolve_dir(snapshot_dir)
    yield primary
    if str(primary.resolve()) != str(BOOT_SNAPSHOT_DIR.resolve()):
        yield BOOT_SNAPSHOT_DIR


def read_snapshot(snapshot_dir: str | Path | None = None) -> dict | None:
    """Read the latest snapshot dict; None on missing/corrupt. NEVER raises.

    Tries the primary dir first (volume-persisted snapshots), then the
    boot-baked /app/boot_snapshots dir. This is the shape-contract fix
    (Lesson 14): the restore pipeline expected the snapshot at data/… but
    a fresh volume changed the filesystem shape — the fallback re-matches
    the contract.
    """
    for out_dir in _snapshot_candidates(snapshot_dir):
        try:
            path = out_dir / SNAPSHOT_FILENAME
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            return data
        except Exception as exc:
            log.warning("durability: snapshot %s unreadable: %s", out_dir, exc)
    return None


def _extract_counter_counts(snapshot: dict) -> dict:
    """Pull the restorable counters out of a snapshot dict, int-coerced."""
    counts: dict = {}
    for key in RESTORE_COUNTER_KEYS:
        if key not in snapshot:
            continue
        try:
            counts[key] = int(snapshot[key])
        except (TypeError, ValueError):
            continue  # non-numeric junk in the snapshot -> skip that counter
    return counts


def restore_counters_if_wiped(
    memory_path: Path, snapshot_dir: str | Path | None = None
) -> dict:
    """Replay the snapshot counters when the memory file was wiped.

    Restore ONLY if the memory file is MISSING or EMPTY (size == 0) —
    that is exactly the 'Railway redeploy without an attached volume'
    signature (JsonMemory.__init__ recreates an empty file). When real
    data exists, the app's own memory is the source of truth and no
    restore happens.

    Returns a dict with keys:
      restored    (bool)  — True iff memory was wiped AND a snapshot was read
      counts      (dict)  — {counter_key: int} replayed from the snapshot
      snapshot_ts (str | None) — the snapshot's ISO-8601 timestamp
    NEVER raises.
    """
    try:
        mem = Path(memory_path)
        wiped = not mem.exists() or mem.stat().st_size == 0
        if not wiped:
            return {"restored": False, "counts": {}, "snapshot_ts": None}
        snapshot = read_snapshot(snapshot_dir)
        if not snapshot:
            return {"restored": False, "counts": {}, "snapshot_ts": None}
        ts = snapshot.get("snapshot_ts")
        return {
            "restored": True,
            "counts": _extract_counter_counts(snapshot),
            "snapshot_ts": ts if isinstance(ts, str) else None,
        }
    except Exception as exc:
        log.warning("durability: restore check failed for %s: %s", memory_path, exc)
        return {"restored": False, "counts": {}, "snapshot_ts": None}
