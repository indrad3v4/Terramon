#!/usr/bin/env python3
"""Snapshot the /health KPI counters to data/snapshots/latest/health.json.

The LOOP (orchestrator) runs this at ship time so the app's REAL counters
(mint_count / share_count / seed_count) survive Railway redeploys that
wipe the data/ dir (declared volume not attached in the dashboard). The
snapshot is git-committed (.gitignore negations keep data/snapshots/
trackable; .dockerignore only excludes data/*.jsonl, so the snapshot
also survives into the Docker image) and the app replays it on boot via
restore_counters_if_wiped() when data/tma_memory.jsonl is missing/empty.

Usage:  /tmp/reflex_venv/bin/python scripts/kpi/snapshot_data.py
Env:    TERRAMON_URL (default https://terramon-tma-production.up.railway.app)

Never raises: hard failures print an error to stderr and exit 1.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

# Make the repo root importable regardless of the cwd the script is run from.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from terramon.adapters.durability import capture_health_snapshot  # noqa: E402

HEALTH_URL = (
    os.environ.get("TERRAMON_URL", "https://terramon-tma-production.up.railway.app")
    .rstrip("/")
    + "/health"
)
FETCH_TIMEOUT_S = 20
USER_AGENT = "TerramonKPI/1.0 (snapshot_data; durability checkpoint)"


def main() -> int:
    """Fetch /health and checkpoint its counters. Returns the exit code."""
    try:
        req = urllib.request.Request(HEALTH_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"snapshot_data: failed to fetch {HEALTH_URL}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(payload, dict):
        print(
            f"snapshot_data: {HEALTH_URL} returned a non-JSON-object payload: {payload!r}",
            file=sys.stderr,
        )
        return 1

    path = capture_health_snapshot(payload)
    if path is None or not path.is_file():
        print("snapshot_data: failed to write snapshot", file=sys.stderr)
        return 1

    counters = {
        k: payload.get(k, 0)
        for k in ("mint_count", "share_count", "seed_count", "complete_releases")
    }
    print(f"snapshot_data: snapshot written to {path}")
    print(f"snapshot_data: restorable counters: {json.dumps(counters)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
