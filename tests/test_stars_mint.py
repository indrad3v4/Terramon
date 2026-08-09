"""Stars rail wired into the F3 monetization gate (M7): the gate's
'⭐ Mint (1 Star)' button must MINT the current creature — not just unlock.

Design decision under test (honest MVP contract, same as mint_creature):
Telegram Stars openInvoice has NO server callback, so buy_stars writes the
mint record OPTIMISTICALLY on click (idempotent _record_mint) and ALWAYS
closes the gate (unlocked=True) — the player keeps their creature even
while _STARS_INVOICE_URL is a placeholder. Lightning stays the BTC-first
primary and mints only on invoice settle (verify_lightning).

Offline: no network, no Reflex runtime, no LLM, no Alby Hub, no Telegram
WebApp. Handlers are driven via EventHandler.fn against a fake state and a
tmp JsonMemory (same harness as test_mint_loop.py); the gate-button wiring
is asserted at source level (rx.cond compiles to JS — the source is the
only place that wiring is observable offline, cf. test_gate_regression.py).
"""

import re
from datetime import datetime
from pathlib import Path

import pytest

from terramon.adapters.json_memory import JsonMemory
from terramon.domain.thought_seed import ThoughtSeed

import terramon_tma.terramon_tma as tma

AGENT = "Sage"
THOUGHT = "a thought worth minting"


class _FakeState:
    """Minimal stand-in for TerramonState carrying only what the Stars
    handlers touch. buy_stars.fn is exercised via EventHandler.fn, so any
    attribute the real code reads/writes must exist here."""

    # Wire the REAL mint-recording logic (plain method — no rx.event
    # wrapper) so buy_stars.fn's `self._record_mint()` runs the real code.
    _record_mint = tma.TerramonState._record_mint

    def __init__(self) -> None:
        self.has_summoned = True
        self.price_sats = 0  # free-tier creature: gate price is FIXED, tier is 0
        self.agent = AGENT
        self.thought = THOUGHT
        self.minted = False
        self.minted_at = ""
        self.mint_count = 0
        self.agent_message = ""
        self.unlocked = False


@pytest.fixture(autouse=True)
def _isolate_globals(monkeypatch, tmp_path: Path):
    """Point the TMA module globals at a tmp memory and reset the shared
    progress counter so tests are order-independent."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    monkeypatch.setattr(tma, "_MEMORY", memory)
    try:
        tma._LOOP.progress.mint_count = 0
    except Exception:
        pass
    return memory


def _save_current_creature(memory: JsonMemory) -> None:
    memory.save_seed(
        ThoughtSeed(raw_input=THOUGHT, summoned_agent=AGENT, timestamp="2026-08-09T00:00:00")
    )


# ── buy_stars is the REAL Stars mint path ─────────────────────────────


def test_buy_stars_mints_optimistically(_isolate_globals):
    """buy_stars records the mint on click even though openInvoice never
    executes (no Telegram.WebApp offline — and no server callback in the
    real TMA either): minted on the seed, counters bumped, message set."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()

    tma.TerramonState.buy_stars.fn(state)

    assert state.minted is True
    assert state.minted_at != ""
    datetime.fromisoformat(state.minted_at)  # valid ISO
    assert state.mint_count == 1
    assert tma._LOOP.progress.mint_count == 1
    assert memory.get_mint_state(AGENT, THOUGHT) == (True, state.minted_at)
    assert "minted" in state.agent_message.lower()


def test_buy_stars_unlocks(_isolate_globals):
    """buy_stars ALWAYS closes the gate (unlocked=True) — the same UX as
    the old MVP fallback, so a placeholder invoice never strands the
    player behind the payment gate."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()
    assert state.unlocked is False

    tma.TerramonState.buy_stars.fn(state)

    assert state.unlocked is True  # gate condition (sc>0) & ~unlocked → False


def test_buy_stars_opens_invoice(_isolate_globals):
    """The returned EventSpec carries the guarded openInvoice call with the
    placeholder _STARS_INVOICE_URL — the JS only fires when
    Telegram.WebApp.openInvoice exists (real TMA)."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()

    result = tma.TerramonState.buy_stars.fn(state)

    assert result is not None, "buy_stars must keep firing the Stars invoice"
    js = str(result)
    assert "openInvoice" in js
    assert tma._STARS_INVOICE_URL in js  # the configured (placeholder) invoice
    assert "if(window.Telegram?.WebApp?.openInvoice)" in js  # guarded


def test_buy_stars_no_telegram_no_crash(_isolate_globals):
    """Without window.Telegram the JS guard no-ops in the browser, and the
    handler itself never touches the DOM — offline call must not raise and
    the mint must still be recorded."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()

    # No window.Telegram exists in this process — this is the no-Telegram run.
    result = tma.TerramonState.buy_stars.fn(state)

    assert result is not None  # no crash, event spec returned
    assert state.minted is True  # optimistic mint still recorded
    assert state.unlocked is True
    # The browser-side guard is what prevents a ReferenceError in the TMA:
    assert "if(window.Telegram?.WebApp?.openInvoice)" in str(result)


# ── Gate wiring + badge (source-level, cf. test_gate_regression.py) ───

SOURCE = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"


@pytest.fixture(scope="module")
def source() -> str:
    """The real TMA source, read fresh from disk on every run (read-only)."""
    return SOURCE.read_text(encoding="utf-8")


def _top_level_func_lines(source: str, name: str) -> str:
    """Body of a top-level function: from its ``def name(`` (column 0) up
    to the next top-level ``def``. Located by NAME, never by line number —
    the file is edited in parallel and offsets may shift."""
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


def test_gate_button_calls_buy_stars(source):
    """The gate's Stars button (the one labelled '⭐ Mint (1 Star)') must
    fire TerramonState.buy_stars — and Lightning must stay the BTC-first
    primary, rendered BEFORE the Stars fallback."""
    gate = _top_level_func_lines(source, "payment_gate")

    # The mint-framed Stars button exists in the gate...
    assert "Mint (1 Star)" in gate, "Stars button label 'Mint (1 Star)' not in payment_gate()"
    # ...and its handler is buy_stars. Prove it is THE Stars button (not the
    # Lightning one): between the Stars label and the footer note, the only
    # on_click must be TerramonState.buy_stars.
    label_idx = gate.index("Mint (1 Star)")
    footer_idx = gate.index("⚡ Bitcoin-first")
    stars_block = gate[label_idx:footer_idx]
    assert "on_click=TerramonState.buy_stars" in stars_block, (
        "Stars button block does not call TerramonState.buy_stars"
    )

    # BTC-first: Lightning button + invoice flow come before the Stars fallback.
    assert gate.index("Pay with Lightning") < gate.index("Mint (1 Star)")
    assert "on_click=TerramonState.pay_lightning" in gate
    assert "on_click=TerramonState.verify_lightning" in gate


def test_mint_badge_after_stars(_isolate_globals):
    """After a Stars mint the 💠 MINTED badge condition is satisfied: the
    state flag the badge renders on (TerramonState.minted) is set, and the
    persisted seed's card dict (what the collection renders) carries
    minted=True."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()

    tma.TerramonState.buy_stars.fn(state)

    assert state.minted is True  # creature_care_panel badge cond
    reloaded = memory.load_all_seeds()
    assert len(reloaded) == 1
    card = tma._seed_to_card(reloaded[0])
    assert card["minted"] is True  # collection card shows the MINTED badge
