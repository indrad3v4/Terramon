"""Depth-win tests (prism roast 2026-08-13, Lens #97 Transformation).

The win was breadth ("Встречено X из 5" — distinct archetypes), which
felt meaningless: a counter pretending to be a meeting. The reframe: the
win is DEPTH — ONE thought lived all the way through (released WITH final
words AND a real geo anchor). These tests lock the depth contract.
"""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from terramon.domain.progress import PlayerProgress, _is_complete_release

_TMA = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"
_TMA_SRC = _TMA.read_text(encoding="utf-8")


def _seed(archetype="Hero", status="released", final_words="Прощай", lat=50.0619, lon=19.9368):
    return SimpleNamespace(
        summoned_agent=archetype,
        rarity="common",
        status=status,
        final_words=final_words,
        lat=lat,
        lon=lon,
    )


def test_complete_release_counts_with_words_and_geo() -> None:
    p = PlayerProgress()
    assert p.record_complete_release("Прощай, страх", 50.06, 19.94) is True
    assert p.complete_releases == 1
    assert p.depth_win_reached is True


def test_complete_release_needs_final_words() -> None:
    p = PlayerProgress()
    assert p.record_complete_release("   ", 50.06, 19.94) is False
    assert p.complete_releases == 0
    assert p.depth_win_reached is False


def test_complete_release_needs_real_geo() -> None:
    p = PlayerProgress()
    assert p.record_complete_release("Прощай", 0.0, 0.0) is False
    assert p.record_complete_release("Прощай", None, 19.94) is False
    assert p.complete_releases == 0


def test_is_complete_release_contract() -> None:
    assert _is_complete_release(_seed()) is True
    assert _is_complete_release(_seed(final_words="")) is False
    assert _is_complete_release(_seed(lat=0.0)) is False
    # NOTE: status is checked by the CALLER (from_seeds only asks for
    # released seeds); _is_complete_release judges words + geo only.


def test_from_seeds_counts_complete_releases() -> None:
    seeds = [
        _seed("Hero", final_words="Прощай, тревога", lat=50.06, lon=19.94),  # complete
        _seed("Rebel", final_words="", lat=50.06, lon=19.94),                # no words
        _seed("Sage", final_words="Без места", lat=0.0, lon=0.0),            # no geo
        _seed("Orphan", status="active", final_words="Ещё живёт"),           # not released
    ]
    p = PlayerProgress.from_seeds(seeds)
    assert p.complete_releases == 1
    assert p.depth_win_reached is True
    # legacy counters still work (breadth untouched for compatibility)
    assert p.released_count() == 3
    assert p.distinct_count == 4


def test_legacy_release_counter_untouched() -> None:
    """record_release still fills the breadth set; depth is additive."""
    p = PlayerProgress()
    p.record_release("Hero")
    p.record_release("Rebel")
    assert p.released_count() == 2
    assert p.complete_releases == 0  # depth needs words + geo, not a call


# ── UI source guards (same convention as test_iter6_regression.py) ─────────

def test_tma_shows_depth_counter_not_breadth() -> None:
    assert "Отпущено в мир: " in _TMA_SRC
    # the old breadth UI concat is gone (comments may still mention it)
    assert '"Встречено " + TerramonState.released_count.to_string()' not in _TMA_SRC


def test_tma_badge_from_one_complete_release() -> None:
    assert "TerramonState.complete_releases >= 1" in _TMA_SRC


def test_tma_hydrates_complete_releases() -> None:
    assert "complete_releases" in _TMA_SRC
    assert '"complete_releases": progress.complete_releases' in _TMA_SRC
