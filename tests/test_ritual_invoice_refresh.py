"""Ritual invoice lifecycle escape hatch — honest contract tests (2026-08-13).

The Lightning ritual poller is BOUNDED: the hidden rx.moment auto-tick
verifies payment up to RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS (~30 × 6s ≈
3 min), then hands control back to the player — release_ritual_auto_verify
flips False and the manual «✅ I've paid — verify» button becomes
reachable. A new «🔄 Новый инвойс» button (refresh_ritual_invoice)
regenerates the BOLT11/QR and RE-ARMS auto-verify. Refresh NEVER
regenerates over a settled payment: a final verify of the OLD ref that
returns True completes the ritual (complete release) instead of minting
a fresh invoice.

This file locks that contract two ways:
  * source guards (A) — the bounded constant (30, ~3 min) with its
    «manual verify + invoice refresh fallback» comment, the cap branch
    (`>= RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS` + `release_ritual_auto_verify
    = False`) inside verify_release_ritual, the refresh event, and the
    two escape-hatch buttons + «Инвойс жив ~1 час» hint in
    ritual_payment_panel;
  * functional tests (B) — with fake _LOOP/_MEMORY/_ALBY ports, the
    poller caps at exactly RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS ticks, the
    manual verify after the cap shows the «не подтверждён» hint, refresh
    regenerates a fresh BOLT11 and re-arms auto-verify, refresh over a
    settled payment completes the release without a second
    create_payment, and an unconfigured Alby leaves the invoice empty.

All tests are fully offline: no network, no Reflex runtime, no LLM, no
Alby Hub.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

_TMA = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"
_TMA_SRC = _TMA.read_text(encoding="utf-8")


def _method_body(src: str, def_name: str) -> str:
    """Slice one class-level (4-space indented) method body: from
    `def <name>(` up to the next method definition."""
    start = src.index(f"def {def_name}(")
    rest = src[start:]
    nxt = rest.find("\n    def ", len(f"def {def_name}("))
    if nxt == -1:
        return rest
    return rest[:nxt]


# ── A. Source guards: bounded poller + refresh escape hatch ───────────

def test_tma_constant_bounds_ritual_auto_verify() -> None:
    """The poller must be bounded by a module-level constant of exactly
    30 attempts (~3 min at 6 s/interval), documented as the manual
    verify + invoice refresh fallback."""
    assert "RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS = 30" in _TMA_SRC
    assert "manual verify + invoice refresh fallback" in _TMA_SRC


def test_verify_release_ritual_caps_at_max_attempts() -> None:
    """verify_release_ritual must stop the auto poller at the bound:
    a `>= RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS` guard that flips
    release_ritual_auto_verify off (→ manual button reachable)."""
    body = _method_body(_TMA_SRC, "verify_release_ritual")
    assert ">= RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS" in body
    assert "release_ritual_auto_verify = False" in body


def test_refresh_ritual_invoice_event_defined() -> None:
    """A refresh_ritual_invoice event must exist on TerramonState —
    the «🔄 Новый инвойс» button's handler."""
    assert "def refresh_ritual_invoice" in _TMA_SRC


def test_ritual_panel_escape_hatch_buttons() -> None:
    """The ritual panel's non-auto branch must offer BOTH the manual
    «✅ I've paid — verify» button and the «🔄 Новый инвойс» refresh
    button, plus the ~1 hour invoice-lifetime hint."""
    body = _method_body(_TMA_SRC, "ritual_payment_panel")
    assert '"✅ I\'ve paid — verify"' in body
    assert "TerramonState.verify_release_ritual" in body
    assert '"🔄 Новый инвойс"' in body
    assert "TerramonState.refresh_ritual_invoice" in body
    assert "Инвойс жив ~1 час" in body


# ── B. Functional: bounded poller + refresh with fake ports ───────────

class _FakeMemory:
    """Memory port fake: load_all_seeds -> [], update_seed records calls."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def load_all_seeds(self):
        return []

    def update_seed(self, agent, thought, **kwargs):
        self.calls.append({"agent": agent, "thought": thought, **kwargs})


def _state_with_ports(monkeypatch: pytest.MonkeyPatch):
    """Fake _LOOP/_MEMORY ports + a state primed for the PAID ritual
    gate: creature evolved (2), geo-anchored, final words ready."""
    import terramon_tma.terramon_tma as tma

    progress = SimpleNamespace(
        record_release=lambda agent: None,
        record_complete_release=lambda words, lat, lon: True,
        complete_releases=0,
        released_count=lambda: 0,
    )
    memory = _FakeMemory()
    monkeypatch.setattr(tma, "_LOOP", SimpleNamespace(progress=progress))
    monkeypatch.setattr(tma, "_MEMORY", memory)

    state = tma.TerramonState()
    state.agent = "Sage"
    state.thought = "thought"
    state.agent_evolution = 2
    state.agent_lat = 50.06
    state.agent_lon = 19.94
    state.place = "Kraków, Poland"
    state.geo_place = "Kraków, Poland"
    state.final_words = "Прощай"
    return tma, state, memory


def _configured_alby():
    """Fake Alby Hub port: url + api_key set, create_payment returns a
    BOLT11 destination ('lnbc1'), verify_payment always False."""
    return SimpleNamespace(
        url="x",
        api_key="y",
        create_payment=lambda amt, memo: SimpleNamespace(
            destination="lnbc1", verification_ref="ref"
        ),
        verify_payment=lambda req: False,
    )


def _cap_the_poller(state, max_attempts: int) -> None:
    """Drive exactly `max_attempts` auto ticks (datetime _tick, like the
    hidden rx.moment poller) — the bounded poller must flip
    release_ritual_auto_verify off at the cap."""
    for _ in range(max_attempts):
        state.verify_release_ritual(_tick="2026-08-13T00:00:00")


def test_poller_caps_at_max_attempts(monkeypatch) -> None:
    """The auto-verify poller is BOUNDED: after exactly
    RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS unanswered auto ticks it stops
    (auto_verify False), pins the attempt counter to the max, and tells
    the player the manual «✅ I've paid — verify» button is the way."""
    import terramon_tma.terramon_tma as tma
    from terramon_tma.terramon_tma import RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS

    _, state, _ = _state_with_ports(monkeypatch)
    monkeypatch.setattr(tma, "_ALBY", _configured_alby())

    state.release_creature()

    assert state.show_ritual_payment is True
    assert state.release_ritual_auto_verify is True

    _cap_the_poller(state, RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS)

    assert state.release_ritual_auto_verify is False
    assert (
        state.release_ritual_verify_attempts
        == RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS
    )
    assert "✅ I've paid — verify" in state.agent_message


def test_manual_verify_after_cap_shows_unconfirmed(monkeypatch) -> None:
    """Once the poller is capped, the manual button (no _tick arg) must
    answer with the «⏳ Ритуал не подтверждён» hint while the invoice
    is still unpaid."""
    import terramon_tma.terramon_tma as tma
    from terramon_tma.terramon_tma import RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS

    _, state, _ = _state_with_ports(monkeypatch)
    monkeypatch.setattr(tma, "_ALBY", _configured_alby())

    state.release_creature()
    _cap_the_poller(state, RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS)
    assert state.release_ritual_auto_verify is False

    state.verify_release_ritual()  # manual — no datetime tick

    assert "Ритуал не подтверждён" in state.agent_message


def test_refresh_regenerates_invoice_and_rearms(monkeypatch) -> None:
    """«🔄 Новый инвойс» (refresh_ritual_invoice) over an unpaid capped
    invoice must mint a FRESH BOLT11 (lnbc2), reset the attempt counter
    and re-arm auto-verify — the panel stays open."""
    import terramon_tma.terramon_tma as tma
    from terramon_tma.terramon_tma import RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS

    counter = {"n": 0}

    def create_payment(amt, memo):
        counter["n"] += 1
        return SimpleNamespace(
            destination=f"lnbc{counter['n']}",
            verification_ref=f"ref{counter['n']}",
        )

    _, state, _ = _state_with_ports(monkeypatch)
    monkeypatch.setattr(
        tma,
        "_ALBY",
        SimpleNamespace(
            url="x",
            api_key="y",
            create_payment=create_payment,
            verify_payment=lambda req: False,
        ),
    )

    state.release_creature()
    _cap_the_poller(state, RITUAL_RELEASE_VERIFY_MAX_ATTEMPTS)
    assert state.release_ritual_invoice == "lnbc1"
    assert state.release_ritual_auto_verify is False

    state.refresh_ritual_invoice()

    assert state.release_ritual_invoice == "lnbc2"
    assert state.release_ritual_auto_verify is True
    assert state.release_ritual_verify_attempts == 0
    assert state.show_ritual_payment is True


def test_refresh_over_settled_payment_completes_release(monkeypatch) -> None:
    """Refresh NEVER regenerates over a settled payment: when a final
    verify of the OLD ref returns True, the ritual COMPLETES (paid,
    panel closed, complete release recorded) — create_payment is never
    called a second time."""
    import terramon_tma.terramon_tma as tma

    create_calls = []
    complete_calls = {"n": 0}

    def create_payment(amt, memo):
        create_calls.append(1)
        return SimpleNamespace(destination="lnbc1", verification_ref="ref")

    _, state, _ = _state_with_ports(monkeypatch)
    monkeypatch.setattr(
        tma,
        "_ALBY",
        SimpleNamespace(
            url="x",
            api_key="y",
            create_payment=create_payment,
            verify_payment=lambda req: True,  # the old ref settles
        ),
    )
    # Safety: the complete-release path imports NostrPublisher — stub it
    # so the test stays fully offline regardless of NOSTR_SECKEY.
    monkeypatch.setattr(
        "terramon.adapters.nostr_publisher.NostrPublisher",
        lambda: SimpleNamespace(
            seckey_hex="", on_creature_released=lambda e: None
        ),
    )
    # Count complete-release invocations on the fake loop port.
    progress = tma._LOOP.progress

    def _record_complete_release(words, lat, lon):
        complete_calls["n"] += 1
        return True

    monkeypatch.setattr(progress, "record_complete_release", _record_complete_release)

    state.release_creature()
    state.pending_words = "Прощай"
    state.refresh_ritual_invoice()

    assert state.release_ritual_paid is True
    assert state.show_ritual_payment is False
    assert len(create_calls) == 1  # the original invoice, never a refresh
    assert complete_calls["n"] == 1  # the depth win was recorded


def test_refresh_unconfigured_alby_keeps_invoice_empty(monkeypatch) -> None:
    """With Alby unconfigured (url='') refresh must not blow up: it
    falls back to create_ritual_invoice's «не настроен» branch and the
    invoice stays empty."""
    import terramon_tma.terramon_tma as tma

    _, state, _ = _state_with_ports(monkeypatch)
    monkeypatch.setattr(
        tma,
        "_ALBY",
        SimpleNamespace(
            url="",
            api_key="y",
            create_payment=lambda amt, memo: SimpleNamespace(
                destination="lnbc1", verification_ref="ref"
            ),
            verify_payment=lambda req: False,
        ),
    )

    state.release_creature()
    state.refresh_ritual_invoice()

    assert state.release_ritual_invoice == ""
