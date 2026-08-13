"""Ritual deeplink (1-tap wallet open) — honest contract tests (2026-08-13).

The release ritual's Lightning rail must open the player's wallet in ONE
tap: `create_ritual_invoice` builds the BOLT11 invoice and exposes a
`lightning:` deep link (`release_ritual_lightning_uri`) that
`ritual_payment_panel` renders as a «⚡ Открыть кошелёк» link
(`rx.link(href=...)`). When Alby is not configured the URI must be
cleared — no stale/ghost deep link, no double prefix.

This file locks that contract two ways:
  * source guards (A) — the state field, the `"lightning:" + destination`
    assignment in `create_ritual_invoice`, its «не настроен» clearing
    branch, and the wallet link in `ritual_payment_panel`;
  * functional tests (B) — with fake _LOOP/_MEMORY/_ALBY ports, a real
    `release_creature` call opens the paid ritual panel and sets the
    deeplink to exactly `lightning:<bolt11>`; an unconfigured Alby
    leaves both invoice and URI empty; the free legacy path never sets
    a deeplink.

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


# ── A. Source guards: the deeplink must exist and stay gated ──────────

def test_tma_state_has_lightning_uri_field() -> None:
    """TerramonState must carry the 1-tap deeplink field, empty by
    default, documented as a lightning deep link."""
    assert 'release_ritual_lightning_uri: str = ""' in _TMA_SRC
    assert "# lightning: deep link (1-tap wallet open)" in _TMA_SRC


def test_create_ritual_invoice_sets_lightning_uri() -> None:
    """The invoice builder must expose the BOLT11 destination as a
    `lightning:` deep link — exactly one prefix."""
    body = _method_body(_TMA_SRC, "create_ritual_invoice")
    assert 'self.release_ritual_lightning_uri = "lightning:" + req.destination' in body


def test_create_ritual_invoice_clears_uri_when_unconfigured() -> None:
    """The «не настроен» branch must clear the deeplink along with the
    invoice — no stale wallet link on the panel."""
    body = _method_body(_TMA_SRC, "create_ritual_invoice")
    assert "self.release_ritual_lightning_uri = \"\"" in body


def test_ritual_panel_wallet_deeplink() -> None:
    """The ritual panel must render a 1-tap «⚡ Открыть кошелёк» link
    wired to the state's lightning URI."""
    body = _method_body(_TMA_SRC, "ritual_payment_panel")
    assert '"⚡ Открыть кошелёк"' in body
    assert "rx.link(" in body
    assert "href=TerramonState.release_ritual_lightning_uri" in body


# ── B. Functional: deeplink behaviour with fake ports ─────────────────

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


def test_create_ritual_invoice_sets_deeplink(monkeypatch) -> None:
    """A complete release (words + geo anchor + evolution 2) opens the
    PAID ritual panel and exposes the 1-tap deeplink with EXACTLY one
    `lightning:` prefix."""
    import terramon_tma.terramon_tma as tma

    _, state, _ = _state_with_ports(monkeypatch)
    monkeypatch.setattr(tma, "_ALBY", _configured_alby())

    state.release_creature()

    assert state.show_ritual_payment is True
    assert state.release_ritual_invoice == "lnbc1"
    assert state.release_ritual_lightning_uri == "lightning:lnbc1"


def test_ritual_deeplink_empty_when_alby_unconfigured(monkeypatch) -> None:
    """With Alby not configured (url=''), the ritual must produce NO
    invoice and NO deeplink — the panel falls back to Stars."""
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

    assert state.show_ritual_payment is True
    assert state.release_ritual_invoice == ""
    assert state.release_ritual_lightning_uri == ""


def test_ritual_deeplink_no_prefix_duplication(monkeypatch) -> None:
    """The deeplink is built from the raw BOLT11 destination — even when
    the destination already starts with 'lightning:', the URI must never
    gain a second prefix."""
    import terramon_tma.terramon_tma as tma

    _, state, _ = _state_with_ports(monkeypatch)
    monkeypatch.setattr(
        tma,
        "_ALBY",
        SimpleNamespace(
            url="x",
            api_key="y",
            create_payment=lambda amt, memo: SimpleNamespace(
                destination="lnbc1", verification_ref="ref"
            ),
            verify_payment=lambda req: False,
        ),
    )
    state.pending_words = "Прощай"

    state.create_ritual_invoice()

    assert state.release_ritual_invoice == "lnbc1"
    assert state.release_ritual_lightning_uri == "lightning:lnbc1"
    assert not state.release_ritual_lightning_uri.startswith(
        "lightning:lightning:"
    )


def test_free_path_no_deeplink(monkeypatch) -> None:
    """Without final words the release takes the free legacy path — no
    ritual panel, and no deeplink may be left behind."""
    import terramon_tma.terramon_tma as tma

    _, state, _ = _state_with_ports(monkeypatch)
    monkeypatch.setattr(tma, "_ALBY", _configured_alby())
    state.final_words = ""  # no words → free legacy path

    state.release_creature()

    assert state.show_ritual_payment is False
    assert state.release_ritual_lightning_uri == ""
