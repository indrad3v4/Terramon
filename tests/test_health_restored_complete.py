"""/health complete_releases restore — honest additive merge tests (offline).

The North Star win is a PAID complete release (final words + real geo
anchor + settled Lightning ritual). The durability pipeline replays the
git-committed /health snapshot when the Railway volume wipe destroys
data/tma_memory.jsonl; /health must surface the restored
complete_releases count additively (scan + restored) and transparently
(restored_complete_releases + data_restored_from_snapshot), and must
NEVER restore anything when the snapshot was not replayed.

Like tests/test_ritual_stars_honest.py, the TMA module is imported
DEFERRED inside test functions (module-level import runs Reflex app
construction). Fully offline: fake _MEMORY/_ALBY ports, no network.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

_TMA_PATH = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"


class _FakeMemory:
    """Memory port fake: one released seed WITH final words + real geo
    anchor (so the scan yields complete_releases == 1) and zeroed
    player/share counters."""

    def __init__(self) -> None:
        self._seed = SimpleNamespace(
            status="released",
            final_words="Прощай, страх.",
            lat=50.06,
            lon=19.94,
            minted=False,
        )

    def load_all_seeds(self):
        return [self._seed]

    def count_unique_players(self):
        return 0

    def count_returning_players(self, days):
        return 0

    def count_shares(self):
        return 0

    def count_shares_since(self, days):
        return 0


def _health_json(monkeypatch: pytest.MonkeyPatch, snapshot_restored: bool):
    """Run health() with fakes; return the parsed JSON dict."""
    import terramon_tma.terramon_tma as tma

    monkeypatch.setattr(tma, "_MEMORY", _FakeMemory())
    monkeypatch.setattr(
        tma, "_ALBY", SimpleNamespace(url="https://alby.example", api_key="k")
    )
    monkeypatch.setattr(tma, "_SNAPSHOT_RESTORED", snapshot_restored)
    monkeypatch.setattr(
        tma,
        "_RESTORED_COUNTS",
        {"complete_releases": 1, "mint_count": 0, "seed_count": 0, "share_count": 0},
    )
    resp = tma.health(None)  # health() ignores the request argument
    return json.loads(bytes(resp.body).decode("utf-8"))


def test_health_additive_merge_scan_plus_restored(monkeypatch) -> None:
    """Snapshot restored: complete_releases == scan(1) + restored(1) == 2,
    surfaced transparently via restored_complete_releases and
    data_restored_from_snapshot."""
    data = _health_json(monkeypatch, snapshot_restored=True)

    assert data["complete_releases"] == 2
    assert data["restored_complete_releases"] == 1
    assert data["data_restored_from_snapshot"] is True


def test_health_no_restore_pure_scan(monkeypatch) -> None:
    """Snapshot NOT restored: restored_complete_releases == 0 and
    complete_releases is the pure seed scan (1) — nothing is ever
    fabricated or optimistically counted."""
    data = _health_json(monkeypatch, snapshot_restored=False)

    assert data["restored_complete_releases"] == 0
    assert data["complete_releases"] == 1
    assert data["data_restored_from_snapshot"] is False


def test_health_restored_complete_source_markers() -> None:
    """Source-level guard (TMA read as TEXT, never imported): health()
    must expose restored_complete_releases in the JSON and merge the
    restored win additively onto the scan result."""
    src = _TMA_PATH.read_text(encoding="utf-8")
    assert '"restored_complete_releases"' in src
    assert "complete_releases += _restored_complete" in src
