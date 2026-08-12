"""Mint UX honesty guards — Stars unit, honest Lightning price, BOLT11 copy.

Change set under test (terramon_tma.py):

  1. The Stars-rail MINT button prices in Telegram STARS, not sats:
     '⚡ MINT · N Stars' in BOTH mint areas (creature_care_panel and the
     home compact card funnel). The '⚡ MINT ·' prefix is load-bearing —
     the KPI probe's mint_button_presence ('⚡ MINT ·' in body) keys on it.
     (RARITY_PRICE in terramon/domain/rarity.py documents the unit switch:
     'the field remains price_sats for backward compatibility ... but the
     unit is now Stars'.)
  2. The '⚡ Mint via Lightning' button shows the REAL invoiced sats price
     via the computed var TerramonState.lightning_button_label
     (lightning_mint_price lifts the Stars-typed price_sats to the Alby
     Hub JIT floor, LIGHTNING_MIN_MINT_SATS = 3000). The '⚡ Mint via
     Lightning' prefix must stay at the START of the rendered label — the
     KPI probe's button:has-text('⚡ Mint via Lightning') locator (and
     test_kpi_geo_gate.py's count == 1) keys on it.
  3. The shared _lightning_invoice_panel gains a '📋 Copy BOLT11' button
     using the SAME rx.set_clipboard pattern as share_creature, with an
     invoice_copied feedback flag (mark_invoice_copied) and a
     '✓ Инвойс скопирован' confirmation. mark_invoice_copied never touches
     agent_message — the KPI probe parses the '⚡ Invoice ready' marker
     from it. The flag resets to False whenever a fresh invoice is created
     (mint_lightning AND pay_lightning).

Offline: no network, no Reflex runtime. The app module is NEVER imported
(module-level Reflex app construction); the source is read as TEXT
(pathlib, read-only) and the pure-domain lightning_mint_price is imported
from terramon.domain.rarity — cf. test_gate_regression.py /
test_mint_lightning.py.
"""

import re
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"

MINT_LABEL_STARS = '"⚡ MINT · " + TerramonState.price_sats.to_string() + " Stars"'
MINT_LABEL_SATS = '"⚡ MINT · " + TerramonState.price_sats.to_string() + " sats"'
LIGHTNING_LABEL_FMT = (
    'f"⚡ Mint via Lightning · {lightning_mint_price(self.price_sats)} sats"'
)


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


def _method_body(source: str, name: str) -> str:
    """Body of a 4-space-indented TerramonState method: from its
    ``    def name(`` line up to the next method-level ``def``. Located by
    NAME, never by line number — the file is edited in parallel."""
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if re.match(rf"^    def {re.escape(name)}\(", ln)),
        None,
    )
    if start is None:
        pytest.fail(f"method 'def {name}(' not found in source")
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^    def ", lines[i])),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _state_class_region(source: str) -> str:
    """Body of the TerramonState class: from its ``class TerramonState(``
    line up to the next top-level def. Located by NAME, never by line
    number (the file is edited in parallel)."""
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.startswith("class TerramonState(")),
        None,
    )
    if start is None:
        pytest.fail("class 'TerramonState(' not found in source")
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^def ", lines[i])),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _home_card_region(source: str) -> str:
    """The home-view ZONE 1 block (compact creature card): lines strictly
    BETWEEN the 'ZONE 1: Creature display' and 'ZONE 2: Compact stats'
    marker comments (both marker lines excluded)."""
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if "ZONE 1: Creature display" in ln),
        None,
    )
    end = next(
        (i for i, ln in enumerate(lines) if "ZONE 2: Compact stats" in ln),
        None,
    )
    if start is None or end is None or not start < end:
        pytest.fail("ZONE 1 / ZONE 2 markers not found in order in source")
    return "\n".join(lines[start + 1 : end])


# ── 1: Stars rail prices in Telegram Stars (not sats) ──────────────────


def test_mint_label_stars_unit_both_blocks(source):
    """Both mint areas (Care panel + home card funnel) price the Stars
    rail in Stars; the legacy sats unit on the MINT label is gone."""
    assert source.count(MINT_LABEL_STARS) == 2, (
        "Stars-unit MINT label must appear in BOTH mint areas (care panel "
        "+ home compact card funnel)"
    )
    assert MINT_LABEL_SATS not in source, (
        "MINT label still priced in sats — the Stars rail is Telegram Stars "
        "(price_sats is a Stars-typed price, see RARITY_PRICE in rarity.py)"
    )


def test_mint_label_prefix_preserved_for_kpi(source):
    """The '⚡ MINT ·' prefix survives unchanged — the KPI probe's
    mint_button_presence ('⚡ MINT ·' in body) and the mint-area presence
    tests key on it."""
    assert source.count('"⚡ MINT · "') == 2, (
        "the '⚡ MINT ·' prefix must stay byte-identical on both MINT buttons"
    )


# ── 2: Lightning button — honest sats price via computed label ─────────


def test_lightning_button_uses_computed_label(source):
    """Both '⚡ Mint via Lightning' buttons render the computed label
    (honest JIT-floor sats price), not a hardcoded string."""
    assert source.count("TerramonState.lightning_button_label,") == 2, (
        "both Lightning buttons must use TerramonState.lightning_button_label"
    )
    assert 'rx.button("⚡ Mint via Lightning"' not in source, (
        "hardcoded '⚡ Mint via Lightning' label still used as a button arg"
    )


def test_lightning_button_label_var(source):
    """The computed var starts with the KPI-probe prefix and shows the
    REAL invoiced sats price via lightning_mint_price(self.price_sats)."""
    state = _state_class_region(source)
    assert "def lightning_button_label(self) -> str:" in state, (
        "computed var lightning_button_label missing from TerramonState"
    )
    assert LIGHTNING_LABEL_FMT in state, (
        "lightning_button_label must format the honest sats price via "
        "lightning_mint_price"
    )


def test_lightning_button_label_price_mapping():
    """Behavioral lock: lightning_mint_price lifts Stars prices to the Alby
    JIT floor (>= LIGHTNING_MIN_MINT_SATS = 3000) and keeps free tiers at
    0 — the button shows the real invoiced amount, never the Stars price."""
    from terramon.domain.rarity import lightning_mint_price

    def label(price: int) -> str:
        return f"⚡ Mint via Lightning · {lightning_mint_price(price)} sats"

    assert label(15) == "⚡ Mint via Lightning · 3000 sats"
    assert label(0) == "⚡ Mint via Lightning · 0 sats"


# ── 3: BOLT11 copy affordance (rx.set_clipboard pattern) ───────────────


def test_copy_bolt11_button_in_panel(source):
    """The shared invoice panel offers '📋 Copy BOLT11' wired to the SAME
    rx.set_clipboard pattern share_creature uses, plus mark_invoice_copied
    and the '✓ Инвойс скопирован' feedback."""
    panel = "\n".join(_top_level_func_lines(source, "_lightning_invoice_panel"))
    assert "📋 Copy BOLT11" in panel, "Copy BOLT11 button missing from panel"
    assert "rx.set_clipboard(TerramonState.lightning_invoice)" in panel, (
        "Copy BOLT11 must use the rx.set_clipboard pattern (cf. share_creature)"
    )
    assert "TerramonState.mark_invoice_copied" in panel, (
        "Copy BOLT11 must chain mark_invoice_copied for feedback"
    )
    assert "✓ Инвойс скопирован" in panel, (
        "copy feedback text missing from the invoice panel"
    )
    assert "TerramonState.invoice_copied" in panel, (
        "copy feedback cond not wired to TerramonState.invoice_copied"
    )


def test_mark_invoice_copied_handler(source):
    """mark_invoice_copied flips ONLY the feedback flag — it must never
    ASSIGN agent_message (the KPI probe parses the '⚡ Invoice ready'
    marker from it, cf. test_mint_lightning.py)."""
    body = _method_body(source, "mark_invoice_copied")
    assert "self.invoice_copied = True" in body
    assert "self.agent_message" not in body, (
        "mark_invoice_copied must not assign agent_message"
    )


def test_invoice_copied_state_var(source):
    """invoice_copied is a declared bool state var (default False)."""
    state = _state_class_region(source)
    assert "invoice_copied: bool = False" in state, (
        "TerramonState missing the 'invoice_copied: bool = False' state var"
    )


# ── 4: feedback flag resets on a fresh invoice ─────────────────────────


def test_invoice_copied_reset_on_new_invoice(source):
    """A fresh invoice clears the copy feedback: both mint_lightning and
    pay_lightning reset invoice_copied = False when they create one."""
    for name in ("mint_lightning", "pay_lightning"):
        body = _method_body(source, name)
        assert "self.invoice_copied = False" in body, (
            f"{name} does not reset invoice_copied on a new invoice"
        )


# ── 5: KPI prefix contract on the rendered Lightning label ─────────────


def test_lightning_label_prefix_kept(source):
    """The '⚡ Mint via Lightning' substring must stay in BOTH button
    regions and the computed label must START with it — the KPI probe's
    button:has-text('⚡ Mint via Lightning') locator
    (test_kpi_geo_gate.py: count == 1) depends on the rendered prefix."""
    assert LIGHTNING_LABEL_FMT in source
    panel = "\n".join(_top_level_func_lines(source, "creature_care_panel"))
    assert "⚡ Mint via Lightning" in panel, (
        "Lightning label prefix missing from creature_care_panel()"
    )
    home = _home_card_region(source)
    assert "⚡ Mint via Lightning" in home, (
        "Lightning label prefix missing from the home compact card funnel"
    )
