"""Offline tests: summon anti-stall (hard LLM timeout + summon-event guard).

KPI incident: 'after 01:27 summon-path hung (event goes out → ACK 200,
state-update never arrives, console clean) — server-side stall of the LLM
path'. A hung LLM HTTP call (DNS/connect/read) blocked the synchronous
summon event; the UI froze on summoning=True forever.

These tests lock in the fix:
  1. _call_llm has a HARD wall-clock timeout and degrades to None (never
     raises, never hangs) → the fallback chain (Qwen → template) completes.
  2. The timeout value is present and >= 20s.
  3. A failing greeting LLM still births the creature with a graceful
     template greeting and clears summoning.
  4. ANY exception inside the summon event clears summoning and returns a
     graceful result.

All tests are fully offline: no network, no real HTTP.
"""

import socket
import urllib.error

import pytest

from terramon.application import llm_behavior as lb
from terramon.application.circuit_breaker import CircuitBreaker
from terramon.domain.creature_agent import CreatureAgent
from terramon.domain.insight import Insight


@pytest.fixture
def llm_ready(monkeypatch):
    """Deterministic LLM environment: key present, fresh circuit breaker,
    retry sleeps disabled (offline + fast)."""
    monkeypatch.setattr(lb, "_API_KEY", "test-key")
    monkeypatch.setattr(
        lb, "_llm_circuit_breaker",
        CircuitBreaker(max_failures=3, cooldown=60.0, name="LLM"),
    )
    monkeypatch.setattr("time.sleep", lambda _: None)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    yield


def _sage_agent() -> CreatureAgent:
    return CreatureAgent(
        agent_id="llm-timeout-test",
        archetype="Sage",
        insight=Insight(driver="", barrier="", therefore="", archetype="Sage"),
    )


def test_call_llm_timeout_returns_fallback(monkeypatch, llm_ready):
    """A timed-out LLM HTTP call must not raise and must fall back to the
    deterministic template response — the summon always completes."""

    def _boom(req, timeout=None):
        raise urllib.error.URLError(socket.timeout("timed out"))

    monkeypatch.setattr("urllib.request.urlopen", _boom)

    # _call_llm itself degrades to None on timeout — never raises.
    assert lb._call_llm([{"role": "user", "content": "hi"}]) is None

    # The full generate_response chain lands on the template fallback.
    msg = lb.generate_response(_sage_agent(), "summon", "hello")
    assert msg is not None
    assert getattr(msg, "text", "")
    assert msg.message_type == "response"


def test_call_llm_timeout_seconds_set(monkeypatch, llm_ready):
    """The hard timeout must exist and be >= 20s, and must be threaded into
    the HTTP call (not just declared)."""

    assert lb.LLM_HTTP_TIMEOUT >= 20

    captured: dict = {}

    class _FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return (
                b'{"choices":[{"message":{"content":'
                b'"{\\"emotion\\":\\"curious\\",\\"message\\":\\"hello\\"}"}}]}'
            )

    def _fake_urlopen(req, timeout=None):
        captured["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    out = lb._call_llm([{"role": "user", "content": "hi"}])
    assert out is not None
    assert captured.get("timeout") == lb.LLM_HTTP_TIMEOUT
    assert captured.get("timeout", 0) >= 20


def test_summon_completes_on_llm_failure(monkeypatch):
    """A failing greeting LLM must not break the summon: the creature is
    still born, the greeting falls back to the graceful template and the
    summoning flag is cleared."""

    import terramon_tma.terramon_tma as tma
    from terramon.application.game_loop import TurnResult

    class _FakeProgress:
        xp = 10
        level = 1
        distinct_count = 1
        goal_distinct = 5
        summon_streak = 1
        current_tier_name = ""
        current_tier_badge = ""
        next_tier_name = ""
        next_tier_requirement = 0

    class _FakeLoop:
        progress = _FakeProgress()

        def take_turn(self, raw_input, color=True, today=None, geo=None):
            return TurnResult(
                agent="Sage", rarity="common", xp_gained=10,
                reveal="", goal_reached=False,
            )

    class _FakeMemory:
        def load_all_seeds(self):
            return []

        def find_seed(self, raw_input):
            return None

        def compute_embedding_drift(self, agent):
            return 0.0

    def _boom(*a, **k):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(tma, "_LOOP", _FakeLoop())
    monkeypatch.setattr(tma, "_MEMORY", _FakeMemory())
    monkeypatch.setattr(lb, "generate_response", _boom)

    state = tma.TerramonState()
    state.thought = "hello"
    state.summon_count = 1
    state.unlocked = True
    state.geo_status = "granted"

    list(state.summon())  # run the event to completion

    assert state.agent == "Sage"
    assert state.has_summoned is True
    assert state.summoning is False
    assert state.creature_greeting == tma._SUMMON_GREETING_FALLBACK


def test_summoning_flag_cleared_on_exception(monkeypatch):
    """ANY exception inside take_turn must clear summoning and return a
    graceful result — never leave the UI frozen on summoning=True."""

    import terramon_tma.terramon_tma as tma

    class _BoomLoop:
        def take_turn(self, *a, **k):
            raise RuntimeError("take_turn exploded")

    monkeypatch.setattr(tma, "_LOOP", _BoomLoop())

    state = tma.TerramonState()
    state.thought = "hello"
    state.summon_count = 1
    state.unlocked = True
    state.geo_status = "granted"

    list(state.summon())

    assert state.summoning is False
    assert state.agent_message == tma._SUMMON_FAILURE_MESSAGE
