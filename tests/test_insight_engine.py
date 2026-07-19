"""Tests for the Insight Engine (FIX 2 — INSIGHT drives the agent).

Covers money / fear / alone / neutral / empty inputs plus the domain wiring
(ThoughtSeed round-trips an Insight through JSON memory) and that SummonService
attaches an insight to every seed.
"""

from pathlib import Path

import pytest

from terramon.adapters.json_memory import JsonMemory
from terramon.adapters.keyword_classifier import KeywordClassifier
from terramon.application.insight_engine import extract_insight
from terramon.application.summon_service import SummonService
from terramon.domain.insight import Insight
from terramon.events.bus import EventBus


def test_insight_money_barrier() -> None:
    """A money-themed thought yields a money barrier + scarcity driver."""
    insight = extract_insight("I can't pay the rent, I'm broke")
    assert insight.barrier == "money"
    assert "scarcity" in insight.driver
    assert "scarcity" in insight.therefore or "money" in insight.therefore


def test_insight_fear_barrier() -> None:
    """A fear-themed thought yields a fear barrier + 'unafraid' driver."""
    insight = extract_insight("I'm afraid of the interview tomorrow")
    assert insight.barrier == "fear"
    assert "unafraid" in insight.driver
    assert "door" in insight.therefore  # Scouts waits by the door


def test_insight_alone_barrier() -> None:
    """An aloneness-themed thought yields a loneliness barrier + 'met' driver."""
    insight = extract_insight("I feel so alone and isolated lately")
    assert insight.barrier == "loneliness"
    assert "met" in insight.driver
    assert "side" in insight.therefore  # warm weight at your side


def test_insight_neutral_falls_back() -> None:
    """A cue-less but non-empty thought still produces a coherent insight."""
    insight = extract_insight("the river flows gently through the valley")
    assert insight.barrier == "the quiet ordinary"
    assert insight.driver == "to be met where you are"
    assert insight.therefore  # non-empty directive


def test_insight_empty_is_neutral() -> None:
    """Empty input yields a neutral, listen-centred insight (no crash)."""
    insight = extract_insight("")
    assert isinstance(insight, Insight)
    assert insight.barrier == "the quiet ordinary"
    assert "listens" in insight.therefore


def test_summon_attaches_insight(tmp_path: Path) -> None:
    """Every summon now carries an insight on the seed (FIX 2 wiring)."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    service = SummonService(KeywordClassifier(), memory, EventBus(), lambda: "now")

    seed = service.summon("scan the horizon")
    assert seed.insight is not None
    assert isinstance(seed.insight, Insight)
    assert seed.insight.therefore


def test_insight_persists_and_reloads(tmp_path: Path) -> None:
    """Insight survives a save/load round-trip through JSON memory."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    service = SummonService(KeywordClassifier(), memory, EventBus(), lambda: "now")

    service.summon("I'm scared of what comes next")
    reloaded = memory.load_all_seeds()
    assert reloaded[0].insight is not None
    assert reloaded[0].insight.barrier == "fear"
    assert "door" in reloaded[0].insight.therefore


def test_old_seed_without_insight_loads(tmp_path: Path) -> None:
    """Backward compat: a seed record with no insight key loads as insight=None."""
    path = tmp_path / "memory.jsonl"
    path.write_text(
        '{"raw_input": "legacy thought", "summoned_agent": "Scout", '
        '"timestamp": "t", "status": "summoned", "rarity": "common", '
        '"price_sats": 0, "paid": false}\n',
        encoding="utf-8",
    )
    memory = JsonMemory(path)
    seeds = memory.load_all_seeds()
    assert len(seeds) == 1
    assert seeds[0].insight is None
