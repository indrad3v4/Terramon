"""M7 mint reachability — iter-14 regression guards (offline, source-level).

Iter-14 fixed two real defects that made the honest M7 mint loop
unreachable:

  (a) Home compact card (terramon_tma.py, ZONE 1): the mint area
      ('⚡ MINT · N sats' + '⚡ Mint via Lightning') was overlapped by the
      thought input in the fixed-height no-scroll layout, so the Lightning
      button could never be clicked. Fixed by capping the ZONE 1 compact
      creature card (max_height="100%" + overflow_y="auto") and adding
      -webkit-line-clamp styles to the lore / creature greeting / memory
      greeting texts so the card can never grow over the input.

  (b) KPI probe (scripts/kpi/play_to_win.py): the old probe blind-clicked
      locator(...).first on '⚡ Mint via Lightning', which targets the
      COVERED home-card button -> Playwright hit-target actionability
      timeout -> invoice_ok=null. Fixed with the _button_is_covered(page,
      locator) helper (document.elementFromPoint at the button's bounding-
      box center) and iterating .count()/.nth(i) to click the first
      visible, uncovered button (the Care-panel one).

These guards lock the contract. Like test_gate_regression.py, the app
module is NEVER imported: importing terramon_tma executes Reflex app
construction at module level. Everything here is pure offline: pathlib
text reading of the sources, located by NAME markers — never by line
number, because the files are edited in parallel and offsets shift.
"""

import re
from pathlib import Path

import pytest

TMA_SOURCE = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"
KPI_SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "kpi" / "play_to_win.py"

ZONE1_MARKER = "ZONE 1: Creature display"
ZONE2_MARKER = "ZONE 2: Compact stats"
M7_MARKER = "# ── M7-funnel: home compact card mint area"
LIGHTNING_LOCATOR = "has-text('⚡ Mint via Lightning')"
PROXIMITY = 80


@pytest.fixture(scope="module")
def source() -> str:
    """The real TMA source, read fresh from disk as TEXT on every run (read-only)."""
    if not TMA_SOURCE.is_file():
        pytest.fail(f"app source not found: {TMA_SOURCE}")
    return TMA_SOURCE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def kpi_source() -> str:
    """The real KPI probe script, read fresh from disk as TEXT (read-only)."""
    if not KPI_SOURCE.is_file():
        pytest.fail(f"KPI script not found: {KPI_SOURCE}")
    return KPI_SOURCE.read_text(encoding="utf-8")


def _zone_region(source: str) -> str:
    """The home-view ZONE 1 block: lines strictly BETWEEN the 'ZONE 1:
    Creature display' and 'ZONE 2: Compact stats' marker comments
    (both marker lines excluded)."""
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ZONE1_MARKER in ln),
        None,
    )
    end = next(
        (i for i, ln in enumerate(lines) if ZONE2_MARKER in ln),
        None,
    )
    if start is None:
        pytest.fail(f"'{ZONE1_MARKER}' marker not found in source")
    if end is None:
        pytest.fail(f"'{ZONE2_MARKER}' marker not found in source")
    if not start < end:
        pytest.fail("'ZONE 2' marker appears before 'ZONE 1' marker in source")
    return "\n".join(lines[start + 1 : end])


# ── 1: the ZONE 1 compact card is capped + scrollable (fix a) ──────────


def test_zone1_card_caps_overflow(source):
    """The ZONE 1 compact creature card rx.box carries BOTH
    max_height='100%' and overflow_y='auto', so the mint area can never be
    overlapped by the thought input in the fixed-height no-scroll layout."""
    region = _zone_region(source)
    assert 'max_height="100%"' in region, (
        'max_height="100%" not found in ZONE 1 region — the compact card '
        "can grow over the thought input and cover the mint buttons"
    )
    assert 'overflow_y="auto"' in region, (
        'overflow_y="auto" not found in ZONE 1 region — the compact card '
        "cannot scroll its overflow, the mint area stays unreachable"
    )


# ── 2: lore / greeting / memory texts are line-clamped (fix a) ─────────


def test_zone1_text_line_clamped(source):
    """The compact card's text block is line-clamped: '-webkit-line-clamp'
    appears at least 2 times in ZONE 1 (lore + greeting/memory), keeping
    the card height bounded under the thought input."""
    region = _zone_region(source)
    clamps = region.count("-webkit-line-clamp")
    assert clamps >= 2, (
        "expected >= 2 '-webkit-line-clamp' styles in ZONE 1 region "
        f"(lore + greeting/memory), found {clamps} — the compact card text "
        "can grow unbounded and push the mint area out of reach"
    )


# ── 3: the KPI probe never blind-clicks .first (fix b) ─────────────────


def test_kpi_probe_never_clicks_first(kpi_source):
    """The probe must NEVER blind-click .first on the '⚡ Mint via Lightning'
    locator (that match is the COVERED home-card button -> Playwright
    hit-target timeout -> invoice_ok=null). Every match must be iterated
    via .count()/.nth(i) with the elementFromPoint coverage check."""
    matches = list(re.finditer(re.escape(LIGHTNING_LOCATOR), kpi_source))
    assert matches, (
        f"no `{LIGHTNING_LOCATOR}` locator found in play_to_win.py — "
        "the Lightning mint probe loop is gone"
    )
    for m in matches:
        after = kpi_source[m.end() : m.end() + PROXIMITY]
        assert ".first" not in after, (
            f"`{LIGHTNING_LOCATOR}` is followed by '.first' within "
            f"{PROXIMITY} chars — the probe blind-clicks the COVERED "
            "home-card button (hit-target timeout -> invoice_ok=null)"
        )
    assert "elementFromPoint" in kpi_source, (
        "elementFromPoint not found in play_to_win.py — the "
        "_button_is_covered hit-target coverage check helper is missing"
    )
    assert "def _button_is_covered(" in kpi_source, (
        "_button_is_covered helper not defined in play_to_win.py"
    )


# ── 4: the home-card mint funnel labels survive (fix a, no regression) ─


def test_home_funnel_labels_preserved(source):
    """The home-card mint funnel must not be removed by the caps/clamp
    work: both rail labels ('⚡ MINT ·' stars + '⚡ Mint via Lightning')
    still live in ZONE 1, and the M7-funnel marker comment still sits
    between the two ZONE markers."""
    region = _zone_region(source)
    assert "⚡ MINT ·" in region, (
        "'⚡ MINT ·' stars rail label not found in ZONE 1 region — the "
        "home-card mint funnel was removed"
    )
    assert "⚡ Mint via Lightning" in region, (
        "'⚡ Mint via Lightning' lightning rail label not found in ZONE 1 "
        "region — the home-card mint funnel was removed"
    )
    assert any(ln.strip().startswith(M7_MARKER) for ln in region.splitlines()), (
        "M7-funnel marker comment not found between 'ZONE 1: Creature "
        "display' and 'ZONE 2: Compact stats'"
    )
