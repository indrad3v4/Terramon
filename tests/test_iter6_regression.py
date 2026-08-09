"""Iter-6 regression traps (offline, source-level).

Four parallel fixes land in terramon_tma/terramon_tma.py; these guards
lock the AGREED contract strings so a future refactor cannot silently
revert any of them. Same style as test_gate_regression.py: the source is
read as TEXT (pathlib, read-only) — rx.cond / rx.call_script compile to
JS, so the post-fix behaviour is only observable offline in the source
itself. The Reflex app module is deliberately NOT imported.

Fix 1 — celebration overlay is session-pending only:
    Old: `celebration_dismissed` was an in-memory state var, so every
    page reload resurrected the overlay and dismissal never persisted.
    New: `celebration_pending` gates the render, dismissal writes
    localStorage('terramon_celebration_dismissed','1'), and
    `on_celebration_restore` re-shows the overlay when the flag is unset.

Fix 2 — per-session geo capture on ANY summon:
    Old: capture only fired on the very first summon
    (`self.summon_count == 0 and self.geo_status == ""`) — a session
    that started without permission never re-asked for geo.
    New: any summon with unknown geo captures location
    (`if self.geo_status == "":`); the old first-summon-only condition
    is dead and must be gone.

Fix 3 — main-card geo backfill falls back to seed lat/lon:
    The creature card coordinates must degrade gracefully: insight geo
    -> last seed's lat/lon -> empty — never 0/NaN-only.

Fix 4 — /health carries seed_count:
    The KPI endpoint must expose the persisted seed count so monitoring
    can distinguish "no players" from "no seeds".

The functional test at the bottom replicates the backfill precedence
contract in pure Python (no app import).
"""

from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"


@pytest.fixture(scope="module")
def source() -> str:
    """The real TMA source, read fresh from disk on every run (read-only)."""
    if not SOURCE.is_file():
        pytest.fail(f"TMA source not found: {SOURCE}")
    return SOURCE.read_text(encoding="utf-8")


# ── Fix 1: celebration overlay persistence ─────────────────────────────


def test_celebration_overlay_session_pending(source):
    """Celebration overlay must be gated by a session-pending flag that
    persists its dismissal to localStorage, with a restore callback."""
    # The pending flag drives the overlay state machine.
    assert "celebration_pending" in source, (
        "celebration_pending missing — overlay flag renamed/removed?"
    )
    # The render condition must branch on the pending flag (not on the
    # old in-memory dismissed var that resets on every page load).
    assert "TerramonState.celebration_pending" in source, (
        "render condition must read TerramonState.celebration_pending"
    )
    # Dismissal persists to localStorage so a reload keeps it dismissed.
    assert "localStorage.setItem('terramon_celebration_dismissed','1')" in source, (
        "dismissal must persist via "
        "localStorage.setItem('terramon_celebration_dismissed','1')"
    )
    # A restore callback exists to re-show the overlay when the flag is cleared.
    assert "on_celebration_restore" in source, (
        "on_celebration_restore callback missing"
    )


# ── Fix 2: per-session geo capture ─────────────────────────────────────


def test_geo_capture_on_any_summon(source):
    """Geo capture must fire on ANY summon with unknown geo, not only the
    first; the old first-summon-only condition is dead code and gone."""
    # The summon capture branch: unknown geo -> request coordinates.
    assert 'if self.geo_status == "":' in source, (
        "summon geo-capture branch 'if self.geo_status == \"\":' not found"
    )
    # Old condition `self.summon_count == 0 and self.geo_status == ""`
    # gated capture on the FIRST summon only — a session that started
    # without permission never re-asked. It must be fully removed.
    assert "summon_count == 0 and self.geo_status" not in source, (
        "old first-summon-only geo condition still present — "
        "capture is dead for later summons"
    )


# ── Fix 3: main-card geo backfill ──────────────────────────────────────


def test_main_card_geo_backfill_seed_fallback(source):
    """Main-card geo backfill must fall back to the last seed's lat/lon.

    Tolerant contract: both ``seeds[-1].lat`` and ``seeds[-1].lon`` must
    appear in the summon backfill region — the implementer may keep them
    on one line as ``self.agent_lat, self.agent_lon = seeds[-1].lat,
    seeds[-1].lon`` or split them across two assignments.
    """
    assert "seeds[-1].lat" in source, (
        "seed lat fallback (seeds[-1].lat) missing from backfill"
    )
    assert "seeds[-1].lon" in source, (
        "seed lon fallback (seeds[-1].lon) missing from backfill"
    )


# ── Fix 4: /health seed_count ──────────────────────────────────────────


def test_health_carries_seed_count(source):
    """/health JSON must expose the 'seed_count' key so monitoring can
    tell "no players" from "no seeds"."""
    assert '"seed_count"' in source, (
        'health endpoint must return the "seed_count" key'
    )


# ── Functional: backfill precedence contract (pure Python, no import) ──


# The "last persisted seed" the backfill degrades to when insight geo is
# empty — mirrors the real fix reading seeds[-1] in the app source.
_SEED_FALLBACK = (50.0619, 19.9368, "Краков")


def _fallback(lat, lon, place_name, _seed=_SEED_FALLBACK):
    """Replica of the main-card geo backfill precedence contract.

    Returns (lat, lon, place) choosing, in order:
      1. non-zero insight geo (the args) — wins over everything;
      2. else seed lat/lon/place (``_seed``) — the fallback;
      3. else empty strings.
    Mirrors the real chain: insight.geo -> seeds[-1] -> "".
    """
    if lat and lon:
        return (lat, lon, place_name)
    seed_lat, seed_lon, seed_place = _seed
    if seed_lat and seed_lon:
        return (seed_lat, seed_lon, seed_place)
    return ("", "", "")


@pytest.mark.parametrize(
    "args, expected",
    [
        # Non-zero insight geo wins even though a seed fallback exists.
        ((48.8566, 2.3522, "Париж"), (48.8566, 2.3522, "Париж")),
        # Empty insight geo degrades to the seed's lat/lon/place.
        ((0.0, 0.0, ""), _SEED_FALLBACK),
    ],
)
def test_backfill_precedence(args, expected):
    """Backfill precedence: insight geo > seed lat/lon > empty."""
    assert _fallback(*args) == expected


def test_backfill_empty_when_no_source():
    """No insight geo AND no seed values -> empty tuple, never 0/NaN."""
    assert _fallback(0.0, 0.0, "", _seed=(0.0, 0.0, "")) == ("", "", "")
