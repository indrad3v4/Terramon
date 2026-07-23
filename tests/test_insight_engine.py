"""Tests for the Insight Engine v3 (Jungian 12 archetypes + K3 MoE).

v3 changes:
- Old 5-theme barriers (money/fear/loneliness) replaced by Jungian 12
  (innocent/orphan/hero/caregiver/explorer/rebel/lover/creator/jester/sage/magician/ruler)
- Insight now has: driver, barrier, therefore, archetype, nuance, geo, confidence
- The MoE router is untrained (random), so exact barrier values vary per run
- Tests check STRUCTURE not exact barrier names
"""

from pathlib import Path

import pytest

from terramon.adapters.json_memory import JsonMemory
from terramon.adapters.keyword_classifier import KeywordClassifier
from terramon.application.insight_engine import extract_insight
from terramon.application.summon_service import SummonService
from terramon.domain.insight import Insight
from terramon.events.bus import EventBus


def test_insight_returns_jungian_structure() -> None:
    """Every insight now has the v3 Jungian fields: driver, barrier, therefore,
    archetype, nuance, confidence."""
    insight = extract_insight("I can't pay the rent, I'm broke")
    assert isinstance(insight, Insight)
    assert insight.driver
    assert insight.barrier
    assert insight.therefore
    # v3 new fields
    assert insight.archetype  # one of 12 Jungian archetypes
    assert isinstance(insight.confidence, int)
    assert 0 <= insight.confidence <= 100


def test_insight_archetype_is_from_jungian_12() -> None:
    """The archetype field must be one of Jung's 12."""
    insight = extract_insight("I'm afraid of the interview tomorrow")
    jungian_12 = {
        "Innocent", "Orphan", "Hero", "Caregiver", "Explorer", "Rebel",
        "Lover", "Creator", "Jester", "Sage", "Magician", "Ruler",
    }
    assert insight.archetype.title() in jungian_12, f"{insight.archetype} not in Jungian 12"


def test_insight_therefore_describes_behavior() -> None:
    """THEREFORE is a complete sentence describing creature behavior."""
    insight = extract_insight("I feel so alone and isolated lately")
    assert insight.therefore
    assert len(insight.therefore) > 20  # not a stub
    assert insight.therefore[0].isupper()  # starts with capital


def test_insight_neutral_falls_back() -> None:
    """A cue-less but non-empty thought still produces a coherent insight."""
    insight = extract_insight("the river flows gently through the valley")
    assert insight.driver
    assert insight.therefore
    assert insight.archetype
    assert isinstance(insight, Insight)


def test_insight_empty_is_neutral() -> None:
    """Empty input yields a neutral insight (no crash)."""
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
    # v3: barrier is Jungian, not the old 5-theme barriers
    assert reloaded[0].insight.barrier in [
        "fear of the unknown", "being abandoned", "weakness and failure",
        "being unable to help", "being trapped", "oppression and injustice",
        "rejection and solitude", "emptiness and irrelevance",
        "boredom and meaninglessness", "ignorance and deception",
        "powerlessness", "chaos and disorder", "the quiet ordinary",
    ]
    assert reloaded[0].insight.therefore


def test_old_seed_without_insight_loads(tmp_path: Path) -> None:
    """Backward compat: a seed record with no insight key loads as insight=None."""
    path = tmp_path / "memory.jsonl"
    path.write_text(
        '{"raw_input": "legacy thought", "summoned_agent": "Innocent", '
        '"timestamp": "t", "status": "summoned", "rarity": "common", '
        '"price_sats": 0, "paid": false}\n',
        encoding="utf-8",
    )
    memory = JsonMemory(path)
    seeds = memory.load_all_seeds()
    assert len(seeds) == 1
    assert seeds[0].insight is None
