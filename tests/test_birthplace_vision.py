"""Offline tests for TERRA vision — describe_birthplace (GPT-4o via OpenRouter).

The API call is monkeypatched — no network in tests. Coverage:
- describe_birthplace returns cleaned text when the LLM replies
- vision messages contain the base64 image (data:image/png) in image_url
- system prompt carries the archetype voice + insight lens
- returns None when no API key is set
- returns None when the LLM call fails (graceful degradation)
"""

from __future__ import annotations

import base64

import pytest

from terramon.domain.creature_agent import CreatureAgent
from terramon.domain.insight import Insight

# Importing llm_behavior monkey-patches CreatureAgent methods at module load
# (talk/feed/play/rest/evolve/tick -> LLM-backed versions). That would pollute
# tests/test_creature_agent.py which tests the ORIGINAL methods. So we save the
# originals BEFORE importing llm_behavior, and restore them in an autouse
# fixture after each test.
from terramon.domain.creature_agent import CreatureAgent as _CA

_ORIGINAL_METHODS = {
    "talk": _CA.talk,
    "feed": _CA.feed,
    "play": _CA.play,
    "rest": _CA.rest,
    "evolve": _CA.evolve,
    "tick": _CA.tick,
}

import terramon.application.llm_behavior as llm  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_creature_methods():
    yield
    for name, original in _ORIGINAL_METHODS.items():
        setattr(CreatureAgent, name, original)


_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64  # minimal PNG-ish payload


def _make_agent() -> CreatureAgent:
    return CreatureAgent(
        agent_id="T-1",
        name="Lumis",
        archetype="Sage",
        place_name="Kraków, Poland",
        insight=Insight(
            driver="to know the truth beneath all things",
            barrier="ignorance and deception",
            therefore="It holds a lantern to the hidden truth.",
            archetype="Sage",
        ),
    )


def test_returns_cleaned_text(monkeypatch) -> None:
    """LLM reply is stripped of quotes/markdown and returned as-is."""
    monkeypatch.setattr(llm, "has_api_key", lambda: True)

    def fake_call(messages, model=None, sampling=None, max_tokens=150):
        assert model == llm.VISION_MODEL
        assert max_tokens == 120
        return '"**The river splits this city like a spine of silver.**"'

    monkeypatch.setattr(llm, "_call_llm", fake_call)
    lore = llm.describe_birthplace(_PNG_BYTES, _make_agent())
    assert lore == "The river splits this city like a spine of silver."


def test_vision_message_contains_base64_image(monkeypatch) -> None:
    """The user message must carry the map as a data:image/png base64 URL."""
    monkeypatch.setattr(llm, "has_api_key", lambda: True)
    captured: dict = {}

    def fake_call(messages, model=None, sampling=None, max_tokens=150):
        captured["messages"] = messages
        return "I see a city between two rivers."

    monkeypatch.setattr(llm, "_call_llm", fake_call)
    llm.describe_birthplace(_PNG_BYTES, _make_agent())

    user = captured["messages"][1]["content"]
    image_part = [c for c in user if c.get("type") == "image_url"][0]
    url = image_part["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    payload = url.split(",", 1)[1]
    assert base64.b64decode(payload) == _PNG_BYTES


def test_system_prompt_carries_voice_and_insight(monkeypatch) -> None:
    """Archetype voice + DRIVER/BARRIER/THEREFORE must be in the system prompt."""
    monkeypatch.setattr(llm, "has_api_key", lambda: True)
    captured: dict = {}

    def fake_call(messages, model=None, sampling=None, max_tokens=150):
        captured["system"] = messages[0]["content"]
        return "I see."

    monkeypatch.setattr(llm, "_call_llm", fake_call)
    llm.describe_birthplace(_PNG_BYTES, _make_agent())

    sys = captured["system"]
    assert "Sage" in sys
    assert "to know the truth beneath all things" in sys
    assert "ignorance and deception" in sys
    assert "It holds a lantern to the hidden truth." in sys


def test_returns_none_without_api_key(monkeypatch) -> None:
    """No OpenRouter key -> None (caller keeps template lore)."""
    monkeypatch.setattr(llm, "has_api_key", lambda: False)
    assert llm.describe_birthplace(_PNG_BYTES, _make_agent()) is None


def test_returns_none_on_llm_failure(monkeypatch) -> None:
    """LLM call returns None (network fail / circuit open) -> None, no crash."""
    monkeypatch.setattr(llm, "has_api_key", lambda: True)
    monkeypatch.setattr(llm, "_call_llm", lambda *a, **k: None)
    assert llm.describe_birthplace(_PNG_BYTES, _make_agent()) is None


def test_fallback_insight_when_missing(monkeypatch) -> None:
    """Creature without insight gets the concept default lens, still renders."""
    monkeypatch.setattr(llm, "has_api_key", lambda: True)
    captured: dict = {}

    def fake_call(messages, model=None, sampling=None, max_tokens=150):
        captured["system"] = messages[0]["content"]
        return "I exist in a place I do not yet know."

    monkeypatch.setattr(llm, "_call_llm", fake_call)
    agent = CreatureAgent(agent_id="T-2", archetype="Orphan", place_name="")
    lore = llm.describe_birthplace(_PNG_BYTES, agent)
    assert lore == "I exist in a place I do not yet know."
    assert "a thought needed to be met" in captured["system"]
