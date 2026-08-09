"""⚡ Mint via Lightning — M7 honest mint-on-settle path + shared invoice panel.

The Lightning rail invoices on the self-custodial Alby Hub node
(_ALBY.create_payment) and mints ONLY when verify_lightning sees the invoice
SETTLE (unlike Stars, which mints optimistically on click — openInvoice has
no server callback). The KPI probe (scripts/kpi/play_to_win.py) parses the
exact agent_message markers from mint_lightning, so those strings are locked
byte-identical to pay_lightning's wording — do not reword them.

Design lock-ins under test:
- mint_lightning() keeps the same SILENT guards as mint_creature
  (has_summoned/price_sats), plus an already-minted early return and an
  Alby-not-configured early return.
- The creature card's can_mint branch offers BOTH rails: the unchanged
  Stars tooltip button AND '⚡ Mint via Lightning' (mint_lightning).
- verify_lightning verifies the INVOICED amount (lightning_price), falling
  back to price_sats — never the stale creature price alone
  (pay_lightning invoices at GATE_SUMMON_PRICE_SATS while a free-tier
  creature has price_sats == 0).
- _lightning_invoice_panel() is the single shared invoice UI (QR + BOLT11 +
  verify + new invoice), self-gating on lightning_invoice != '', used by
  BOTH payment_gate() and creature_care_panel().

Offline: no network, no Reflex runtime. Handlers and UI wiring are asserted
at source level (rx.cond compiles to JS — the source is the only place this
wiring is observable offline, cf. test_gate_regression.py / test_stars_mint.py).
"""

import re
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"


@pytest.fixture(scope="module")
def source() -> str:
    """The real TMA source, read fresh from disk on every run (read-only)."""
    return SOURCE.read_text(encoding="utf-8")


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


def _top_level_func_lines(source: str, name: str) -> str:
    """Body of a top-level function (column-0 def) up to the next top-level
    def. Located by NAME, never by line number."""
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
    return "\n".join(lines[start:end])


def test_mint_lightning_handler_contract(source):
    """(a) mint_lightning exists with: the same silent guard as
    mint_creature, an already-minted early return, an Alby-not-configured
    early return, a creature-price invoice via _ALBY.create_payment, and
    the three KPI-parsed ⚡ markers (byte-identical to pay_lightning)."""
    body = _method_body(source, "mint_lightning")

    # Same silent guard as mint_creature (no message, no invoice).
    assert "if not self.has_summoned or self.price_sats <= 0:" in body, (
        "mint_lightning missing the has_summoned/price_sats silent guard"
    )
    # Already-minted: no double invoice, no double mint.
    assert "💠 This creature is already minted." in body, (
        "mint_lightning missing the already-minted early return"
    )
    # Alby config early return — exact KPI marker wording (byte-identical).
    assert "⚡ Lightning not configured yet — use Stars for now." in body, (
        "mint_lightning missing the not-configured marker"
    )
    assert "_ALBY.url" in body and "_ALBY.api_key" in body
    # Invoice creation at the CREATURE price (not the fixed gate price).
    assert "_ALBY.create_payment(" in body, (
        "mint_lightning does not call _ALBY.create_payment"
    )
    assert "self.lightning_price = price" in body, (
        "mint_lightning does not persist lightning_price"
    )
    assert "req.destination" in body and "req.verification_ref" in body
    assert "self.lightning_checking = False" in body
    # The remaining two KPI markers — byte-identical to pay_lightning.
    assert "⚡ Invoice ready:" in body, "mint_lightning missing the invoice-ready marker"
    assert "⚡ Invoice failed:" in body, "mint_lightning missing the invoice-failed marker"
    assert "getattr(e, 'message', e)" in body


def test_card_lightning_mint_button(source):
    """(b) The creature card wires the Lightning mint button + handler, and
    keeps the unchanged Stars MINT tooltip button as its sibling."""
    panel = _top_level_func_lines(source, "creature_care_panel")
    assert "⚡ Mint via Lightning" in panel, (
        "Lightning mint button label not inside creature_care_panel()"
    )
    assert "on_click=TerramonState.mint_lightning" in panel, (
        "mint_lightning handler not wired inside creature_care_panel()"
    )
    # The Stars rail stays (unchanged sibling in the same can_mint vstack).
    assert "⚡ MINT · " in panel
    assert "on_click=TerramonState.mint_creature" in panel
    # Locked branch texts untouched.
    assert "locked · train more" in panel
    assert "free summon" in panel


def test_card_invoice_panel_before_share(source):
    """The card's invoice panel call sits after the MINT area and before the
    '📤 Share' button (the share button must not be disturbed)."""
    panel = _top_level_func_lines(source, "creature_care_panel")
    mint_idx = panel.index("on_click=TerramonState.mint_lightning")
    panel_idx = panel.index("_lightning_invoice_panel()")
    share_idx = panel.index("📤 Share")
    assert mint_idx < panel_idx < share_idx, (
        "card invoice panel must sit between the mint button and the Share button"
    )


def test_verify_lightning_uses_invoiced_amount(source):
    """(c) verify_lightning verifies the INVOICED amount (lightning_price),
    falling back to price_sats — never the stale creature price alone."""
    body = _method_body(source, "verify_lightning")
    assert "amount_sats=self.lightning_price or self.price_sats" in body, (
        "verify_lightning does not verify lightning_price"
    )
    assert "amount_sats=self.price_sats" not in body, (
        "verify_lightning still hardcodes amount_sats=self.price_sats"
    )


def test_lightning_invoice_panel_shared(source):
    """(d) _lightning_invoice_panel is defined exactly once and referenced by
    BOTH payment_gate() and creature_care_panel(); it self-gates on
    lightning_invoice != '' and carries the full invoice UI (QR + verify +
    new invoice)."""
    assert source.count("def _lightning_invoice_panel(") == 1, (
        "_lightning_invoice_panel must be defined exactly once"
    )
    # def line + payment_gate() call + creature_care_panel() call.
    assert source.count("_lightning_invoice_panel()") >= 3, (
        "panel must be referenced by both the gate and the card"
    )
    gate = _top_level_func_lines(source, "payment_gate")
    assert "_lightning_invoice_panel()" in gate, (
        "payment_gate() does not call _lightning_invoice_panel()"
    )
    card = _top_level_func_lines(source, "creature_care_panel")
    assert "_lightning_invoice_panel()" in card, (
        "creature_care_panel() does not call _lightning_invoice_panel()"
    )
    panel = _top_level_func_lines(source, "_lightning_invoice_panel")
    assert 'TerramonState.lightning_invoice != ""' in panel, (
        "panel is not self-gating on lightning_invoice"
    )
    assert "api.qrserver.com" in panel, "panel lost the BOLT11 QR image"
    assert "on_click=TerramonState.verify_lightning" in panel
    assert "on_click=TerramonState.pay_lightning" in panel


def test_gate_keeps_lightning_wiring(source):
    """The gate keeps its no-invoice fallback button (fixed gate price) and
    the full Lightning wiring inside payment_gate() — the Stars fallback
    stays AFTER Lightning (BTC-first ordering)."""
    gate = _top_level_func_lines(source, "payment_gate")
    assert "Pay with Lightning" in gate
    assert "on_click=TerramonState.pay_lightning" in gate
    assert "on_click=TerramonState.verify_lightning" in gate
    assert gate.index("Pay with Lightning") < gate.index("Mint (1 Star)"), (
        "Lightning must render before the Stars fallback in the gate"
    )


def test_health_tests_count(source):
    """(e) /health reports the synced pytest count."""
    assert '"tests": 390' in source, (
        "health endpoint pytest count not synced to 390"
    )
