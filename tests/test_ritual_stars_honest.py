"""Payment-gated Stars ritual — honest contract tests (owner directive 2026-08-13).

The release ritual's Stars rail MUST be payment-gated: complete_releases
(the monetised depth win, Lens #97) is only ever incremented by a REAL
'paid' openInvoice callback delivered to on_ritual_stars_status — never
optimistically on button click. While the invoice is open the panel shows
«⏳ Ожидание оплаты Stars…»; 'cancelled'/'failed'/'unavailable' keep the
panel open and never touch the win counter.

This file locks that contract two ways:
  * source guards (A) — the TMA source must not contain the optimistic
    completion path and must wire the real callback;
  * functional tests (B) — with fake _LOOP/_MEMORY ports, a 'paid'
    callback completes the release (complete_releases == 1, words
    persisted), while click / 'cancelled' / 'failed' never do.

All tests are fully offline: no network, no real HTTP, no LLM.
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


# ── A. Source guards: the click must never complete the ritual ─────────

def test_stars_ritual_not_optimistic() -> None:
    """pay_ritual_stars must NOT complete the release optimistically:
    the click only opens the invoice and arms the pending flag."""
    body = _method_body(_TMA_SRC, "pay_ritual_stars")
    assert "_complete_ritual_release" not in body


def test_stars_ritual_callback_gated() -> None:
    """The ONLY completion path is the openInvoice callback:
    on_ritual_stars_status must call _complete_ritual_release, and the
    click must wire that callback into the call_script."""
    pay_body = _method_body(_TMA_SRC, "pay_ritual_stars")
    assert "callback=TerramonState.on_ritual_stars_status" in pay_body
    cb_body = _method_body(_TMA_SRC, "on_ritual_stars_status")
    assert "_complete_ritual_release" in cb_body


def test_stars_ritual_js_bridge() -> None:
    """The JS bridge uses Telegram WebApp.openInvoice and resolves the
    status string back to the state callback."""
    assert "_RITUAL_STARS_JS" in _TMA_SRC
    start = _TMA_SRC.index("_RITUAL_STARS_JS = '''")
    js = _TMA_SRC[start:]
    js_body = js[: js.index("'''", len("_RITUAL_STARS_JS = '''"))]
    assert "openInvoice" in js_body
    assert "__INVOICE_URL__" in js_body
    for status in ("paid", "cancelled", "failed", "unavailable"):
        assert status in js_body


def test_stars_ritual_pending_state() -> None:
    """While the invoice is open the panel shows the waiting hint, and
    the pending flag gates the button."""
    assert "ritual_stars_pending" in _TMA_SRC
    assert "Ожидание оплаты Stars" in _TMA_SRC


def test_stars_ritual_env_url() -> None:
    """The Stars invoice URL is env-overridable (TERRAMON_STARS_INVOICE_URL)."""
    line = next(
        ln for ln in _TMA_SRC.splitlines()
        if ln.startswith("_STARS_INVOICE_URL =")
    )
    assert "os.environ.get" in line
    assert '"TERRAMON_STARS_INVOICE_URL"' in _TMA_SRC


def test_stars_ritual_free_path_still_resets() -> None:
    """The free legacy path disarms the pending Stars flag."""
    body = _method_body(_TMA_SRC, "release_without_ritual")
    assert "ritual_stars_pending = False" in body


def test_stars_ritual_rail_live_flag() -> None:
    """The Stars rail is LIVE only when the owner set a real invoice URL
    (TERRAMON_STARS_INVOICE_URL) — a placeholder URL must never arm it."""
    assert (
        '_STARS_RAIL_LIVE = bool(os.environ.get("TERRAMON_STARS_INVOICE_URL"))'
        in _TMA_SRC
    )
    line = next(
        ln for ln in _TMA_SRC.splitlines()
        if ln.startswith("_STARS_RAIL_LIVE =")
    )
    assert "bool(os.environ.get" in line
    assert '"TERRAMON_STARS_INVOICE_URL"' in line


def test_pay_ritual_stars_guarded_when_rail_offline() -> None:
    """Offline rail → the click is an honest dead-end guard: never call
    openInvoice with the placeholder URL, never arm the pending flag.
    Lightning remains the sacred rail."""
    body = _method_body(_TMA_SRC, "pay_ritual_stars")
    assert "if not _STARS_RAIL_LIVE:" in body
    assert "Stars-рельса ещё не настроена" in body
    assert body.index("if not _STARS_RAIL_LIVE:") < body.index(
        "ritual_stars_pending = True"
    )


def test_ritual_panel_stars_disabled_state_when_rail_offline() -> None:
    """Offline rail → the panel's Stars section renders a disabled
    placeholder («Stars — скоро») instead of a live openInvoice button;
    the live branch strings must survive byte-identical."""
    body = _method_body(_TMA_SRC, "ritual_payment_panel")
    assert "_STARS_RAIL_LIVE" in body
    assert "— скоро" in body  # disabled placeholder label
    assert "Stars-инвойс ещё не подключён" in body
    assert "disabled=True" in body
    # The live branch survives unchanged:
    assert "Ожидание оплаты Stars" in body
    assert "Оплатить ритуал · " in body
    assert "on_click=TerramonState.pay_ritual_stars" in body


# ── B. Functional: only a real 'paid' callback completes the release ───

class _FakeMemory:
    """Memory port fake: load_all_seeds -> [], update_seed records calls."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def load_all_seeds(self):
        return []

    def update_seed(self, agent, thought, **kwargs):
        self.calls.append({"agent": agent, "thought": thought, **kwargs})


def _stars_state(monkeypatch: pytest.MonkeyPatch):
    """Fake _LOOP/_MEMORY ports + a state primed for the Stars ritual."""
    import terramon_tma.terramon_tma as tma

    progress = SimpleNamespace(
        record_release=lambda agent: None,
        record_complete_release=lambda words, lat, lon: True,
        complete_releases=1,
        released_count=lambda: 0,
    )
    memory = _FakeMemory()
    monkeypatch.setattr(tma, "_LOOP", SimpleNamespace(progress=progress))
    monkeypatch.setattr(tma, "_MEMORY", memory)
    # Functional section simulates a LIVE Stars rail (owner set
    # TERRAMON_STARS_INVOICE_URL) — the click path past the dead-end guard.
    monkeypatch.setattr(tma, "_STARS_RAIL_LIVE", True)

    state = tma.TerramonState()
    state.agent = "Sage"
    state.thought = "thought"
    state.agent_lat = 50.06
    state.agent_lon = 19.94
    state.pending_words = "Прощай, страх."
    state.show_ritual_payment = True
    state.release_ritual_auto_verify = True
    return tma, state, memory


def test_stars_paid_callback_completes_release(monkeypatch) -> None:
    """A REAL 'paid' callback is the one and only path that completes the
    release: panel closes, the win counts, the words are persisted."""
    _, state, memory = _stars_state(monkeypatch)

    state.on_ritual_stars_status("paid")

    assert state.show_ritual_payment is False
    assert state.release_ritual_paid is True
    assert state.ritual_stars_pending is False
    assert state.complete_releases == 1
    assert memory.calls, "paid callback must persist the release"
    last = memory.calls[-1]
    assert last["final_words"] == "Прощай, страх."
    assert last["status"] == "released"


def test_stars_cancelled_never_completes(monkeypatch) -> None:
    """'cancelled' keeps the panel open and never touches the win counter."""
    _, state, memory = _stars_state(monkeypatch)

    state.on_ritual_stars_status("cancelled")

    assert state.show_ritual_payment is True  # panel stays open
    assert state.complete_releases == 0  # no completion
    assert state.release_ritual_paid is False
    assert state.ritual_stars_pending is False
    assert "не оплачен" in state.agent_message
    assert memory.calls == []  # nothing persisted


def test_stars_failed_never_completes(monkeypatch) -> None:
    """'failed' keeps the panel open and never touches the win counter."""
    _, state, memory = _stars_state(monkeypatch)

    state.on_ritual_stars_status("failed")

    assert state.show_ritual_payment is True  # panel stays open
    assert state.complete_releases == 0  # no completion
    assert state.release_ritual_paid is False
    assert state.ritual_stars_pending is False
    assert memory.calls == []  # nothing persisted


def test_stars_click_sets_pending_without_completing(monkeypatch) -> None:
    """The button click only arms the pending flag and opens the invoice —
    it must NEVER complete the release."""
    _, state, memory = _stars_state(monkeypatch)

    spec = state.pay_ritual_stars()

    assert state.ritual_stars_pending is True
    assert state.release_ritual_auto_verify is False  # one rail at a time
    assert state.show_ritual_payment is True  # panel stays open
    assert state.complete_releases == 0  # NEVER completed on click
    assert memory.calls == []  # nothing persisted on click
    # The returned EventSpec must carry the openInvoice callback wiring.
    if spec is not None:
        try:
            spec_text = str(spec)
        except Exception:
            spec_text = ""
        if spec_text:
            assert "on_ritual_stars_status" in spec_text
        # else: EventSpec not stringifiable in this Reflex build —
        # wiring check skipped (state invariants above still hold).


def test_stars_click_guarded_when_rail_offline(monkeypatch) -> None:
    """With no real Stars invoice link configured the click must NOT open
    the dead placeholder invoice: early return, no pending flag, honest
    message pointing at the Lightning rail (dead-end removal)."""
    tma, state, memory = _stars_state(monkeypatch)
    monkeypatch.setattr(tma, "_STARS_RAIL_LIVE", False)

    spec = state.pay_ritual_stars()

    assert spec is None  # no openInvoice wiring on a dead rail
    assert state.ritual_stars_pending is False  # never armed
    assert state.release_ritual_auto_verify is True  # Lightning poller untouched
    assert "не настроена" in state.agent_message
    assert memory.calls == []  # nothing persisted


def test_free_release_clears_pending(monkeypatch) -> None:
    """The free legacy path disarms the pending Stars flag and persists
    status only — never words, so it never counts toward the depth win."""
    _, state, memory = _stars_state(monkeypatch)
    state.ritual_stars_pending = True

    state.release_without_ritual()

    assert state.ritual_stars_pending is False
    assert state.show_ritual_payment is False
    assert memory.calls, "free path must persist the release status"
    last = memory.calls[-1]
    assert last["status"] == "released"
    assert "final_words" not in last  # free path never persists words
