"""Tests for the thought-seed summon loop."""

from pathlib import Path

import pytest

from terramon.adapters.json_memory import JsonMemory
from terramon.adapters.keyword_classifier import KeywordClassifier
from terramon.application.summon_service import SummonService
from terramon.events.agent_summoned import AgentSummoned
from terramon.events.bus import EventBus


def test_summon_routes_to_ranger(tmp_path: Path) -> None:
    """A visual request summons the Ranger."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now")

    seed = service.summon("scan the north district")

    assert seed.summoned_agent == "Innocent"  # default (no keyword matched)
    assert seed.status == "summoned"
    assert memory.load_all_seeds() == [seed]


def test_summon_emits_event(tmp_path: Path) -> None:
    """A summon publishes an AgentSummoned event."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    received: list[AgentSummoned] = []
    bus.subscribe(AgentSummoned, received.append)
    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now")

    service.summon("help me take care of this")

    assert len(received) == 1
    assert received[0].agent_name == "Caregiver"


def test_summon_defaults_to_scout(tmp_path: Path) -> None:
    """An unmatched input falls back to Scout."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now")

    seed = service.summon("hello world")

    assert seed.summoned_agent == "Innocent"
