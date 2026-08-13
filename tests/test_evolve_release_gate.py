"""Regression traps: the EVOLVE → release-ritual win path (I08 v2 / I12).

Bug class (confirmed on prod by Playwright probe):
    evolve_agent was a GENERATOR handler — after `self.agent_evolution += 1`
    it `yield`ed rx.call_script('setTimeout(...reflex.sendEvent(
    "clear_evolution_animation")...)'). Yielding suspends the handler and
    delays the state delta; under load the second EVOLVE click read a stale
    state, so its increment was LOST and agent_evolution stuck at 1. The UI
    gate `rx.cond(TerramonState.agent_evolution >= 2, rx.button("💨
    Отпустить", ...))` never opened → the release ritual and its Lightning
    payment panel were unreachable on prod → complete_releases (the North
    Star win metric) could never increment.

Fix under test:
    1. evolve_agent is now a PLAIN (non-generator) handler: it increments
       agent_evolution synchronously, sets evolve_animating = True and
       returns None — every click increments exactly once, immediately.
    2. A NEW gated rx.moment inside creature_care_panel() auto-clears the
       animation flag ~1.6s later (interval=1600,
       on_change=TerramonState.clear_evolution_animation) — no JS
       setTimeout/sendEvent round-trip remains.

Behavioral traps run the REAL TerramonState against monkeypatched
_LOOP/_MEMORY/_AGENT_SVC (offline). Source traps read terramon_tma.py as
text via pathlib (rx.cond compiles to JS, so the gate/moment are only
observable offline in the source) and locate functions by NAME, never by
line number — the file is edited in parallel and offsets may shift.
"""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "terramon_tma" / "terramon_tma.py"


@pytest.fixture(scope="module")
def source() -> str:
    """The real TMA source, read fresh from disk on every run (read-only)."""
    return SOURCE.read_text(encoding="utf-8")


@pytest.fixture
def tma_env(monkeypatch):
    """Offline TMA environment: real TerramonState class, fake globals.

    _LOOP / _MEMORY are trivial stand-ins (evolve_agent does not touch
    them); _AGENT_SVC.evolve(...) returns a canned success message so the
    handler's full body runs deterministically.
    """
    import terramon_tma.terramon_tma as tma

    class _FakeAgentSvc:
        def evolve(self, agent):
            return SimpleNamespace(text="evolved")

    monkeypatch.setattr(tma, "_LOOP", SimpleNamespace())
    monkeypatch.setattr(tma, "_MEMORY", SimpleNamespace())
    monkeypatch.setattr(tma, "_AGENT_SVC", _FakeAgentSvc())
    return tma


def _class_method_lines(source: str, name: str) -> list[str]:
    """Lines of a class method INCLUDING its decorator block: from the
    ``@rx.event`` / ``@rx.var`` lines directly above ``def name(self):`` up
    to the next ``    def `` / ``    @rx.event`` at the same 4-space indent
    (the start of the next method). Matches by NAME, not line number."""
    lines = source.splitlines()
    start = next(
        (
            i
            for i, ln in enumerate(lines)
            if re.match(rf"^\s*def {re.escape(name)}\(self\):", ln)
        ),
        None,
    )
    if start is None:
        pytest.fail(f"class method 'def {name}(self):' not found in source")
    # Walk back over the decorator lines that sit directly above the def.
    while start > 0 and re.match(r"^\s{4}@", lines[start - 1]):
        start -= 1
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].startswith("    def ") or lines[i].startswith("    @rx.event")
        ),
        len(lines),
    )
    return lines[start:end]


def _top_level_func_lines(source: str, name: str) -> list[str]:
    """Lines of a top-level function body: from its ``def name(`` (column 0)
    up to the next top-level ``def``. Function names, not line numbers."""
    lines = source.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if re.match(rf"^def {re.escape(name)}\b", ln)),
        None,
    )
    if start is None:
        pytest.fail(f"top-level function 'def {name}(' not found in source")
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^def ", lines[i])),
        len(lines),
    )
    return lines[start:end]


# ── Behavioral: the real TerramonState, offline ──────────────────────────


def test_evolve_agent_is_plain_handler_not_generator(tma_env):
    """evolve_agent must be a PLAIN handler: a bare call executes the body
    (a generator call would return an unexecuted generator — the old bug,
    where rapid EVOLVE clicks lost their increments). Two plain calls must
    land agent_evolution at exactly 2, and the call must return None."""
    state = tma_env.TerramonState()

    # Plain call: body runs NOW (a generator would need list()/iteration).
    result = state.evolve_agent()
    assert result is None, "plain handler must return None, not a generator"
    assert state.agent_evolution == 1
    assert state.evolve_animating is True
    assert state.agent_message == "evolved"

    # Second EVOLVE click must NOT be lost — this is the prod bug.
    state.evolve_agent()
    assert state.agent_evolution == 2, (
        "second EVOLVE click lost its increment — handler is still a generator"
    )
    assert state.agent_evolution == 2  # capped, not 3


def test_show_release_opens_dialog_at_stage_2(tma_env):
    """The release ritual gate must open at evolution stage 2 and stay
    locked below it: show_release() at stage 2 opens the dialog; at stage 1
    it refuses with the 'not matured' message (the prod symptom: '💨
    Отпустить' never rendered because agent_evolution never reached 2)."""
    state = tma_env.TerramonState()
    state.evolve_agent()
    state.evolve_agent()
    assert state.agent_evolution == 2

    state.show_release()
    assert state.show_release_dialog is True

    # Below the gate: dialog stays closed, player is told to evolve first.
    fresh = tma_env.TerramonState()
    fresh.agent_evolution = 1
    fresh.show_release()
    assert fresh.show_release_dialog is False
    assert "stage 2" in fresh.agent_message, (
        f"stage-1 refusal message missing 'stage 2': {fresh.agent_message!r}"
    )


# ── Source-level: read-only pathlib traps on the real source ─────────────


def test_evolve_agent_source_has_no_yield(source):
    """The whole evolve_agent slice (decorator + body) must contain no
    `yield` — a generator body suspends the handler, which is exactly the
    stale-state increment-loss bug. The JS setTimeout/sendEvent reset is
    replaced by the gated rx.moment; nothing in this handler may yield."""
    method = "\n".join(_class_method_lines(source, "evolve_agent"))
    for ln in method.splitlines():
        assert not ln.strip().startswith("yield"), (
            f"evolve_agent still contains a yield: {ln.strip()!r}"
        )


def test_evolve_animation_autoclear_moment_exists(source):
    """The gated rx.moment inside creature_care_panel() must exist: it is
    the auto-clear that replaced the JS setTimeout/sendEvent round-trip.
    cond(TerramonState.evolve_animating) mounts rx.moment(interval=1600,
    on_change=TerramonState.clear_evolution_animation) — the flag clears
    ~1.6s after an evolve and the cond unmounts the timer."""
    panel = "\n".join(_top_level_func_lines(source, "creature_care_panel"))
    assert "TerramonState.evolve_animating" in panel, (
        "evolve_animating cond gate not found in creature_care_panel()"
    )
    assert "interval=1600" in panel, (
        "rx.moment interval=1600 auto-clear not found in creature_care_panel()"
    )
    assert "on_change=TerramonState.clear_evolution_animation" in panel, (
        "rx.moment on_change auto-clear not wired in creature_care_panel()"
    )


def test_no_js_timeout_animation_reset_remains(source):
    """The old JS-based animation reset must be GONE from the source: the
    generator's rx.call_script('setTimeout(...reflex.sendEvent(
    "clear_evolution_animation")...)') was the root cause of the lost
    increment — no trace of that round-trip may remain anywhere."""
    assert 'sendEvent("clear_evolution_animation"' not in source, (
        "old JS setTimeout→sendEvent animation reset still present"
    )
