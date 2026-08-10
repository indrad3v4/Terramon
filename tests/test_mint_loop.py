"""Mint loop (M7) — closing the loop: a REAL mint record on the seed,
a mint counter for analytics, optimistic Stars mint vs settle-based
Lightning mint.

Offline: no network, no Reflex runtime, no LLM, no Alby Hub. The handler
tests drive the REAL event code (TerramonState.mint_creature / .verify_lightning
via EventHandler.fn) against a fake state object and a tmp JsonMemory, so the
mint wiring is tested, not just a re-implementation.
"""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from terramon.adapters.json_memory import JsonMemory
from terramon.domain.thought_seed import ThoughtSeed

import terramon_tma.terramon_tma as tma


AGENT = "Sage"
THOUGHT = "a thought worth minting"


class _FakeState:
    """Minimal stand-in for TerramonState carrying only what the mint
    handlers touch. The handlers are exercised via EventHandler.fn, so any
    attribute the real code reads/writes must exist here."""

    # Wire the REAL mint-recording logic (plain method — no rx.event wrapper)
    # so verify_lightning.fn's `self._record_mint()` call runs the real code.
    _record_mint = tma.TerramonState._record_mint

    def __init__(self) -> None:
        self.lightning_auto_verify = False
        self.lightning_verify_attempts = 0
        self.has_summoned = True
        self.price_sats = 3000
        self.agent = AGENT
        self.thought = THOUGHT
        self.minted = False
        self.minted_at = ""
        self.mint_count = 0
        self.agent_message = ""
        self.unlocked = False
        self.lightning_invoice = ""
        self.lightning_ref = ""
        self.lightning_checking = False
        self.lightning_price = 0
        self.lightning_qr = ""


class _FakeAlby:
    """Minimal AlbyHubAdapter stand-in: settles or not on demand, and
    issues a fake BOLT11 invoice with a verification ref."""

    url = "https://fake.alby.hub"
    api_key = "fake-key"
    settled = True

    def create_payment(self, amount_sats, memo):
        return SimpleNamespace(
            destination=f"lnbc{amount_sats}...",
            verification_ref=f"ref-auto-{amount_sats}",
        )

    def verify_payment(self, request) -> bool:
        return self.settled


@pytest.fixture(autouse=True)
def _isolate_globals(monkeypatch, tmp_path: Path):
    """Point the TMA module globals at a tmp memory and a fake Alby hub,
    and reset the shared progress counter so tests are order-independent."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    monkeypatch.setattr(tma, "_MEMORY", memory)
    monkeypatch.setattr(tma, "_ALBY", _FakeAlby())
    try:
        tma._LOOP.progress.mint_count = 0
    except Exception:
        pass
    return memory


def _save_current_creature(memory: JsonMemory) -> None:
    memory.save_seed(
        ThoughtSeed(raw_input=THOUGHT, summoned_agent=AGENT, timestamp="2026-08-09T00:00:00")
    )


# ── The real mint record on the seed ──────────────────────────────────


def test_mint_records_on_seed(_isolate_globals):
    """mint_creature → the seed record carries minted=True + minted_at ISO,
    and the mint record survives a full memory reload."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()

    tma.TerramonState.mint_creature.fn(state)

    minted, minted_at = memory.get_mint_state(AGENT, THOUGHT)
    assert minted is True
    assert minted_at  # ISO timestamp set
    datetime.fromisoformat(minted_at)  # valid ISO

    reloaded = memory.load_all_seeds()
    assert len(reloaded) == 1  # in-place update — no duplicate record
    assert getattr(reloaded[0], "minted", False) is True
    assert getattr(reloaded[0], "minted_at", "") == minted_at


def test_mint_counter_increments(_isolate_globals):
    """A successful mint bumps BOTH the state counter and the persisted
    PlayerProgress counter (the one /health exposes)."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()

    tma.TerramonState.mint_creature.fn(state)

    assert state.mint_count == 1
    assert tma._LOOP.progress.mint_count == 1
    # The state badge flag follows the record
    assert state.minted is True
    assert state.minted_at != ""


def test_health_exposes_mint_count(_isolate_globals):
    """/health JSON carries mint_count computed from the PERSISTED seeds
    (survives reloads — the KPI cron reads it without a browser session)."""
    memory = _isolate_globals
    # Two DIFFERENT creatures minted
    for i, (agent, thought) in enumerate(
        [("Sage", "thought one"), ("Hero", "thought two")]
    ):
        memory.save_seed(ThoughtSeed(raw_input=thought, summoned_agent=agent, timestamp=f"2026-08-09T00:0{i}:00"))
        assert memory.update_seed(agent, thought, minted=True, minted_at="2026-08-09T12:00:00") is True
    # One creature NOT minted — must not count
    memory.save_seed(ThoughtSeed(raw_input="plain", summoned_agent="Rebel", timestamp="2026-08-09T00:03:00"))

    resp = tma.health(None)
    body = json.loads(resp.body)
    assert body["status"] == "ok"
    assert body["mint_count"] == 2


# ── The two rails ─────────────────────────────────────────────────────


def test_stars_mint_optimistic(_isolate_globals):
    """Stars path (mint_creature): the mint record is written on CLICK —
    no invoice, no Alby hub, no settlement required (openInvoice has no
    server callback in this MVP)."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()

    result = tma.TerramonState.mint_creature.fn(state)

    assert state.minted is True
    assert state.mint_count == 1
    assert state.mint_count == tma._LOOP.progress.mint_count
    assert memory.get_mint_state(AGENT, THOUGHT)[0] is True
    assert "minted" in state.agent_message.lower()
    # The Stars rail itself is kept — openInvoice still fires (call_script)
    assert result is not None


def test_lightning_mint_on_settle(_isolate_globals):
    """Lightning path (verify_lightning): a SETTLED invoice mints the
    creature; an unsettled one does NOT."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()
    state.lightning_ref = "invoice-1"
    state.lightning_invoice = "lnbc1..."

    tma.TerramonState.verify_lightning.fn(state)

    assert state.unlocked is True
    assert state.minted is True
    assert state.mint_count == 1
    assert tma._LOOP.progress.mint_count == 1
    assert memory.get_mint_state(AGENT, THOUGHT)[0] is True

    # Unsettled invoice → no mint record, counter untouched
    state2 = _FakeState()
    state2.lightning_ref = "invoice-2"
    state2.lightning_invoice = "lnbc2..."
    tma._ALBY.settled = False
    tma.TerramonState.verify_lightning.fn(state2)
    assert state2.minted is False
    assert state2.mint_count == 0


# ── Lightning auto-verify (auto-poll settle) ─────────────────────────


def test_lightning_auto_verify_armed_on_invoice(_isolate_globals):
    """Creating a Lightning mint invoice ARMS the auto-verify poller: the
    hidden rx.moment timer starts ticking, the attempt counter resets, and
    the KPI-parsed invoice-ready marker is set — no click required."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()

    tma.TerramonState.mint_lightning.fn(state)

    assert state.lightning_auto_verify is True
    assert state.lightning_verify_attempts == 0
    assert state.lightning_invoice != ""
    assert state.lightning_ref != ""
    assert "⚡ Invoice ready" in state.agent_message


def test_lightning_auto_verify_settle_records_mint(_isolate_globals):
    """Auto-poll SETTLE path: when the Alby hub reports the invoice settled,
    verify_lightning auto-records the mint (no manual click), disarms the
    poller, and shows the byte-identical payment-received marker."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()
    state.lightning_ref = "invoice-1"
    state.lightning_invoice = "lnbc1..."
    state.lightning_auto_verify = True
    tma._ALBY.settled = True

    tma.TerramonState.verify_lightning.fn(state)

    assert state.minted is True
    assert state.mint_count == 1
    assert state.unlocked is True
    assert state.lightning_auto_verify is False
    assert state.lightning_verify_attempts == 0
    assert "✅ Payment received" in state.agent_message
    assert memory.get_mint_state(AGENT, THOUGHT)[0] is True


def test_lightning_auto_verify_poll_does_not_clobber_invoice_marker(_isolate_globals):
    """An UNSETTLED auto-poll tick must NOT touch agent_message: the KPI
    probe parses the '⚡ Invoice ready: ...' marker within seconds of the
    mint click, so polling keeps it intact while counting attempts."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()
    state.lightning_ref = "invoice-1"
    state.lightning_invoice = "lnbc1..."
    state.lightning_auto_verify = True
    state.agent_message = "⚡ Invoice ready: 3000 sats. Pay with any Lightning wallet."
    tma._ALBY.settled = False

    tma.TerramonState.verify_lightning.fn(state)

    assert state.agent_message.startswith("⚡ Invoice ready"), (
        "auto-poll clobbered the invoice-ready marker"
    )
    assert state.lightning_verify_attempts == 1
    assert state.lightning_auto_verify is True
    assert state.minted is False


def test_lightning_auto_verify_gives_up_to_manual(_isolate_globals):
    """Bounded polling: at LIGHTNING_VERIFY_MAX_ATTEMPTS the poller gives up
    gracefully with the exact manual-fallback marker, and the manual
    «✅ I've paid — verify» path still records the mint afterwards."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()
    state.lightning_ref = "invoice-1"
    state.lightning_invoice = "lnbc1..."
    state.lightning_auto_verify = True
    state.lightning_verify_attempts = tma.LIGHTNING_VERIFY_MAX_ATTEMPTS - 1
    tma._ALBY.settled = False

    tma.TerramonState.verify_lightning.fn(state)

    assert state.lightning_auto_verify is False
    assert "Payment not detected" in state.agent_message
    assert state.minted is False

    # Manual fallback still works: once the invoice settles, the click path
    # (lightning_auto_verify is now False) records the mint.
    tma._ALBY.settled = True
    tma.TerramonState.verify_lightning.fn(state)
    assert state.minted is True
    assert state.mint_count == 1
    assert memory.get_mint_state(AGENT, THOUGHT)[0] is True


def test_lightning_manual_verify_message_byte_identical(_isolate_globals):
    """The MANUAL verify click (no auto-verify armed) keeps the existing
    not-settled marker byte-identical — the KPI probe and the panel both
    key on that exact wording."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()
    state.lightning_ref = "invoice-1"
    state.lightning_invoice = "lnbc1..."
    state.lightning_auto_verify = False
    tma._ALBY.settled = False

    tma.TerramonState.verify_lightning.fn(state)

    assert state.agent_message == "⏳ Not settled yet — waiting for the payment to confirm."
    assert state.lightning_verify_attempts == 0
    assert state.minted is False


def test_mint_twice_noop(_isolate_globals):
    """A second mint on the SAME creature is a no-op: no double-count, no
    second record, the original minted_at is preserved."""
    memory = _isolate_globals
    _save_current_creature(memory)
    state = _FakeState()

    tma.TerramonState.mint_creature.fn(state)
    first_minted_at = state.minted_at
    assert state.mint_count == 1

    tma.TerramonState.mint_creature.fn(state)

    assert state.mint_count == 1  # no double-count
    assert state.minted_at == first_minted_at
    assert tma._LOOP.progress.mint_count == 1
    # Exactly one persisted record, still a single mint record
    reloaded = memory.load_all_seeds()
    assert len(reloaded) == 1
    assert getattr(reloaded[0], "minted", False) is True
    assert memory.get_mint_state(AGENT, THOUGHT)[0] is True


# ── Adapter contract (pure persistence layer) ─────────────────────────


def test_update_seed_mint_fields_roundtrip(tmp_path: Path):
    """JsonMemory.update_seed(minted=..., minted_at=...) persists both fields
    and get_mint_state reads them back; no matching seed → no crash."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    memory.save_seed(ThoughtSeed(raw_input="x", summoned_agent="Sage", timestamp="2026-08-09"))

    assert memory.update_seed("Sage", "x", minted=True, minted_at="2026-08-09T12:00:00") is True
    assert memory.get_mint_state("Sage", "x") == (True, "2026-08-09T12:00:00")
    assert memory.get_mint_state("Ghost", "x") == (False, "")  # no match
    assert memory.get_mint_state("Sage", "nope") == (False, "")  # no match
