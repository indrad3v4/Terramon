"""Iter-29 win-path re-anchor — honest contract tests (owner directive 2026-08-13).

The win path («монета в фонтан») REQUIRES a real geo anchor: a creature
that was born with a location re-anchors its `agent_lat` / `agent_lon` /
`place` whenever fresh coordinates arrive (`_apply_coords`), and persists
that anchor back onto the seed via `_MEMORY.update_seed(lat=..., lon=...,
place_name=...)`. Without the anchor, `release_creature` can only take the
free legacy path — words never reach the world, the depth win never counts.

This file locks that contract two ways:
  * source guards (A) — `_apply_coords` must re-anchor the creature and
    persist the anchor, skipping the re-anchor while a first-summon geo
    capture is still pending; `release_dialog` must surface the geo hint
    and the ⟳ capture button; `json_memory.update_seed` must accept and
    persist lat/lon/place_name;
  * functional tests (B) — with fake _LOOP/_MEMORY/_ALBY ports, a real
    `_apply_coords` call moves the creature anchor and records the seed
    update; denied / creature-less captures persist nothing; an anchored
    creature with final words opens the PAID ritual panel.

All tests are fully offline: no network, no Reflex runtime, no LLM, no
Alby Hub.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

_TMA = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"
_TMA_SRC = _TMA.read_text(encoding="utf-8")

_JSON_MEM = (
    Path(__file__).resolve().parents[1]
    / "terramon" / "adapters" / "json_memory.py"
)
_JSON_MEM_SRC = _JSON_MEM.read_text(encoding="utf-8")


def _method_body(src: str, def_name: str) -> str:
    """Slice one class-level (4-space indented) method body: from
    `def <name>(` up to the next method definition."""
    start = src.index(f"def {def_name}(")
    rest = src[start:]
    nxt = rest.find("\n    def ", len(f"def {def_name}("))
    if nxt == -1:
        return rest
    return rest[:nxt]


# ── A. Source guards: the re-anchor must exist and stay gated ─────────

def test_reanchor_updates_creature_anchor() -> None:
    """`_apply_coords` must re-anchor the current creature and persist the
    anchor onto its seed: agent_lat/agent_lon assignment + an
    `update_seed` call carrying lat= / lon=."""
    body = _method_body(_TMA_SRC, "_apply_coords")
    assert "self.agent_lat, self.agent_lon = lat, lon" in body
    assert "_MEMORY.update_seed(" in body
    assert "lat=lat, lon=lon" in body


def test_reanchor_skips_first_summon() -> None:
    """While a first-summon geo capture is pending (pending_thought set),
    incoming coords must NOT re-anchor the (not-yet-born) creature."""
    body = _method_body(_TMA_SRC, "_apply_coords")
    assert "not self.pending_thought" in body


def test_release_dialog_geo_hint() -> None:
    """The release dialog must tell the player a real location is needed
    for the ritual and offer the ⟳ re-capture button wired to
    capture_location."""
    body = _method_body(_TMA_SRC, "release_dialog")
    assert "📍 Нужна геолокация для ритуала" in body
    assert "on_click=TerramonState.capture_location" in body


def test_reanchor_update_seed_supports_geo() -> None:
    """json_memory.update_seed must accept lat/lon/place_name and persist
    them onto the record."""
    sig = _method_body(_JSON_MEM_SRC, "update_seed")
    assert "lat: float | None = None" in sig
    assert 'record["lat"] = lat' in _JSON_MEM_SRC


# ── B. Functional: re-anchor behaviour with fake ports ────────────────

class _FakeMemory:
    """Memory port fake: load_all_seeds -> [], update_seed records calls."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def load_all_seeds(self):
        return []

    def update_seed(self, agent, thought, **kwargs):
        self.calls.append({"agent": agent, "thought": thought, **kwargs})


def _state_with_ports(monkeypatch: pytest.MonkeyPatch):
    """Fake _LOOP/_MEMORY ports + a bare state with the creature fields
    primed for geo capture (agent set, no anchor yet)."""
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
    state.agent_lat = 0.0
    state.agent_lon = 0.0
    state.geo_place = "Kraków, Poland"
    return tma, state, memory


def test_apply_coords_persists_anchor(monkeypatch) -> None:
    """Fresh coordinates re-anchor the creature (agent_lat/agent_lon/place)
    and persist the anchor onto the seed with lat= / lon= / place_name=."""
    _, state, memory = _state_with_ports(monkeypatch)

    state._apply_coords({"lat": 50.06, "lon": 19.94})

    assert state.geo_status == "granted"
    assert state.agent_lat == 50.06
    assert state.agent_lon == 19.94
    assert state.place == "Kraków, Poland"
    assert memory.calls, "an anchored creature must persist its anchor"
    last = memory.calls[-1]
    assert last["lat"] == 50.06
    assert last["lon"] == 19.94
    assert last["place_name"] == "Kraków, Poland"


def test_apply_coords_skips_when_no_creature(monkeypatch) -> None:
    """With no creature (agent empty), coords must NOT re-anchor anything
    and must NOT touch the memory port."""
    _, state, memory = _state_with_ports(monkeypatch)
    state.agent = ""

    state._apply_coords({"lat": 50.06, "lon": 19.94})

    assert state.geo_status == "granted"
    assert state.agent_lat == 0.0
    assert state.agent_lon == 0.0
    assert memory.calls == []


def test_apply_coords_denied_no_persist(monkeypatch) -> None:
    """Denied/absent coordinates set geo_status='denied' and never record
    a real lat on the seed (update_seed may be reached, but only with
    lat=None — json_memory only persists record['lat'] for non-None)."""
    _, state, memory = _state_with_ports(monkeypatch)

    state._apply_coords({"lat": None, "lon": None})

    assert state.geo_status == "denied"
    # The task contract: no update_seed call with a lat recorded.
    assert all(call.get("lat") is None for call in memory.calls)


def test_reanchor_enables_ritual_gate(monkeypatch) -> None:
    """With the creature anchored (re-anchor applied), final words open
    the PAID ritual panel instead of the free legacy path."""
    import terramon_tma.terramon_tma as tma

    _, state, memory = _state_with_ports(monkeypatch)

    state._apply_coords({"lat": 50.06, "lon": 19.94})
    assert (
        state.agent_lat not in (None, 0)
        and state.agent_lon not in (None, 0)
    ), "the re-anchor must leave a real geo anchor on the creature"

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
    state.agent_evolution = 2
    state.final_words = "Прощай"

    state.release_creature()

    # The paid ritual gate, not the free legacy path:
    assert state.show_ritual_payment is True
    assert state.pending_words == "Прощай"
    assert state.release_ritual_invoice == "lnbc1"  # invoice was created
    assert state.release_ritual_ref == "ref"
    # The free legacy path would have persisted status='released' — the
    # ritual gate must NOT have released anything yet (still unpaid).
    assert all(call.get("status") != "released" for call in memory.calls)
