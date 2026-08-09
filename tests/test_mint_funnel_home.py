"""Home-card M7 mint-funnel regression guards (offline, source-level).

A parallel change is adding a mint funnel to the HOME view's compact
creature card (ZONE 1, between the 'ZONE 1: Creature display' and
'ZONE 2: Compact stats' marker comments): a '⚡ MINT · N sats' stars button
(on_click=TerramonState.mint_creature) and a '⚡ Mint via Lightning' button
(on_click=TerramonState.mint_lightning), marked by the exact comment line
'# ── M7-funnel: home compact card mint area (same gate as Care panel) ──'.

These guards lock the contract:

  1. The exact M7-funnel marker comment sits BETWEEN the two ZONE markers
     (i.e. inside the home compact card, not anywhere else in the file).
  2. Lightning rail — the '⚡ Mint via Lightning' label is wired to
     mint_lightning within ~300 chars.
  3. Stars rail — the '⚡ MINT ·' label is wired to mint_creature within
     ~300 chars.
  4. The 'free summon' gate stays EXCLUSIVE to the Care panel — the home
     card funnel must NOT duplicate it.
  5. The Care panel's own mint area ('⚡ MINT' inside creature_care_panel())
     survives the funnel work.

Like test_gate_regression.py, the app module is NEVER imported: importing
terramon_tma executes Reflex app construction at module level (app
assembly / page registration with browser-side effects). Everything here
is pure offline: pathlib text reading of the source, located by NAME
markers — never by line number, because the file is edited in parallel
and offsets shift.
"""

import re
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"

ZONE1_MARKER = "ZONE 1: Creature display"
ZONE2_MARKER = "ZONE 2: Compact stats"
M7_MARKER = "# ── M7-funnel: home compact card mint area (same gate as Care panel) ──"
PROXIMITY = 300


@pytest.fixture(scope="module")
def source() -> str:
    """The real TMA source, read fresh from disk as TEXT on every run (read-only)."""
    if not SOURCE.is_file():
        pytest.fail(f"app source not found: {SOURCE}")
    return SOURCE.read_text(encoding="utf-8")


def _top_level_func_lines(source: str, name: str) -> list[str]:
    """Lines of a top-level function body: from its ``def name(`` (column 0)
    up to the next top-level ``def``. Function names, not line numbers."""
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


def _label_followed_by(region: str, label: str, needle: str) -> bool:
    """True if *label* appears in *region* and *needle* (the on_click handler
    wired to the button) appears within PROXIMITY chars after it."""
    idx = region.find(label)
    if idx == -1:
        return False
    after = region[idx + len(label) : idx + len(label) + PROXIMITY]
    return needle in after


# ── 1: the M7-funnel marker sits between the two ZONE markers ───────────


def test_home_card_mint_funnel_marker(source):
    """The exact M7-funnel marker comment must sit between 'ZONE 1: Creature
    display' and 'ZONE 2: Compact stats' — i.e. inside the home compact card."""
    region = _zone_region(source)
    assert any(ln.strip() == M7_MARKER for ln in region.splitlines()), (
        "M7-funnel marker comment not found between 'ZONE 1: Creature display' "
        "and 'ZONE 2: Compact stats'"
    )


# ── 2: Lightning rail — '⚡ Mint via Lightning' wired to mint_lightning ──


def test_home_card_lightning_rail(source):
    """The home card's '⚡ Mint via Lightning' button must be wired to
    mint_lightning within ~300 chars (the on_click handler on the same rail)."""
    region = _zone_region(source)
    assert "⚡ Mint via Lightning" in region, (
        "'⚡ Mint via Lightning' button label not found in ZONE 1 region"
    )
    assert _label_followed_by(region, "⚡ Mint via Lightning", "mint_lightning"), (
        "'mint_lightning' not found within ~300 chars after '⚡ Mint via "
        "Lightning' in ZONE 1 region"
    )


# ── 3: Stars rail — '⚡ MINT ·' wired to mint_creature ──────────────────


def test_home_card_stars_rail(source):
    """The home card's '⚡ MINT ·' stars button must be wired to mint_creature
    within ~300 chars (the on_click handler on the same rail)."""
    region = _zone_region(source)
    assert "⚡ MINT ·" in region, (
        "'⚡ MINT ·' button label not found in ZONE 1 region"
    )
    assert _label_followed_by(region, "⚡ MINT ·", "mint_creature"), (
        "'mint_creature' not found within ~300 chars after '⚡ MINT ·' "
        "in ZONE 1 region"
    )


# ── 4: 'free summon' gate stays exclusive to the Care panel ─────────────


def test_home_card_no_free_summon_duplicate(source):
    """The 'free summon' gate belongs to the Care panel ONLY — the home-card
    funnel must not duplicate it in ZONE 1."""
    region = _zone_region(source)
    assert "free summon" not in region, (
        "'free summon' found between ZONE 1 and ZONE 2 — the free-summon gate "
        "must stay exclusive to the Care panel"
    )


# ── 5: Care panel mint area survives the funnel work ────────────────────


def test_care_panel_mint_still_present(source):
    """The Care panel's own mint area ('⚡ MINT' inside creature_care_panel())
    must survive the home-card funnel work."""
    panel = "\n".join(_top_level_func_lines(source, "creature_care_panel"))
    assert "⚡ MINT" in panel, (
        "'⚡ MINT' button not inside creature_care_panel() — Care panel mint "
        "area was removed"
    )
