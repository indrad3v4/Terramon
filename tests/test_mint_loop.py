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


class _FakeAlby:
    """Minimal AlbyHubAdapter stand-in: settles or not on demand."""

    url = "https://fake.alby.hub"
    api_key = "fake-key"
    settled = True

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
