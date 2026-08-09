"""M4: redeploy-safe hydration + dedup guard (offline tests).

Regression for the duplicate-creature bug: the TMA collection lived
in-memory (TerramonState / GameLoop._LOOP) and reset on every Railway
redeploy, while the creature seeds survived on the volume. The next
summon of the same thought then appended a duplicate seed (observed:
4× duplicate Hero "Wawel castle").

Fix under test:
- hydrate_from_memory() derives ALL collection counters from seeds
  (terra, summon_count, distinct, released_count, goal_reached).
- JsonMemory.find_seed() is the dedup guard: same thought => same
  creature (deterministic router), no new seed is appended.
"""

import pytest

from terramon.adapters.json_memory import JsonMemory
from terramon.domain.progress import PlayerProgress
from terramon.domain.thought_seed import ThoughtSeed
from terramon_tma.terramon_tma import hydrate_from_memory


def _save(memory, agent: str, thought: str, ts: str, status: str = "summoned") -> None:
    """Persist one seed exactly as the summon flow does (JSONL append)."""
    memory.save_seed(
        ThoughtSeed(
            raw_input=thought,
            summoned_agent=agent,
            timestamp=ts,
            status=status,
        )
    )


def test_hydrate_restores_collection(tmp_path):
    memory = JsonMemory(tmp_path / "mem.jsonl")
    _save(memory, "Hero", "wawel castle", "2026-08-01T10:00:00")
    _save(memory, "Sage", "quiet insight", "2026-08-02T10:00:00")
    _save(memory, "Rebel", "break the rules", "2026-08-03T10:00:00")

    state = hydrate_from_memory(memory)

    # terra list fully restored from persisted seeds
    assert len(state["terra"]) == 3
    assert [c["agent"] for c in state["terra"]] == ["Hero", "Sage", "Rebel"]
    # distinct count = distinct agents, not seed count
    assert state["distinct"] == 3
    assert state["has_summoned"] is True


def test_hydrate_restores_summon_count(tmp_path):
    memory = JsonMemory(tmp_path / "mem.jsonl")
    # 4 seeds, only 2 distinct agents — summon_count is seed count
    _save(memory, "Hero", "wawel castle", "2026-08-01T10:00:00")
    _save(memory, "Hero", "the grail quest", "2026-08-02T10:00:00")
    _save(memory, "Sage", "quiet insight", "2026-08-03T10:00:00")
    _save(memory, "Sage", "the library", "2026-08-04T10:00:00")

    state = hydrate_from_memory(memory)

    assert state["summon_count"] == 4
    assert state["distinct"] == 2  # duplicates never inflate distinct

    # empty memory -> fresh-player defaults (gate stays closed, no summon)
    empty = hydrate_from_memory(JsonMemory(tmp_path / "empty.jsonl"))
    assert empty["summon_count"] == 0
    assert empty["has_summoned"] is False
    assert empty["terra"] == []


def test_dedup_same_thought_no_duplicate(tmp_path):
    memory = JsonMemory(tmp_path / "mem.jsonl")
    _save(memory, "Hero", "wawel castle", "2026-08-01T10:00:00")

    # dedup guard: the repeated thought resolves to the EXISTING creature
    existing = memory.find_seed("wawel castle")
    assert existing is not None
    assert existing.summoned_agent == "Hero"

    # the guard path must NOT append anything — file and counters unchanged
    assert len(memory.load_all_seeds()) == 1
    state = hydrate_from_memory(memory)
    assert state["summon_count"] == 1
    assert state["distinct"] == 1

    # agent filter: same thought, wrong agent -> no match (future-proof)
    assert memory.find_seed("wawel castle", summoned_agent="Sage") is None


def test_different_thought_creates_new(tmp_path):
    memory = JsonMemory(tmp_path / "mem.jsonl")
    _save(memory, "Hero", "wawel castle", "2026-08-01T10:00:00")

    # a different thought is a NEW creature — guard lets it through
    assert memory.find_seed("a brand new thought") is None
    _save(memory, "Sage", "a brand new thought", "2026-08-02T10:00:00")

    seeds = memory.load_all_seeds()
    assert len(seeds) == 2
    state = hydrate_from_memory(memory)
    assert state["summon_count"] == 2  # count advanced by exactly +1
    assert state["distinct"] == 2


def test_progress_derived_from_seeds(tmp_path):
    memory = JsonMemory(tmp_path / "mem.jsonl")
    agents = ["Hero", "Hero", "Sage", "Rebel", "Sage", "Sage"]
    for i, agent in enumerate(agents):
        _save(memory, agent, f"thought {i}", f"2026-08-0{i + 1}T10:00:00")

    progress = PlayerProgress.from_seeds(memory.load_all_seeds())

    # distinct == set of archetypes in seeds, summon count == len(seeds)
    assert progress.distinct_count == len(set(agents)) == 3
    assert progress.distinct_count == 3
    assert len(memory.load_all_seeds()) == 6

    state = hydrate_from_memory(memory)
    assert state["distinct"] == 3
    assert state["summon_count"] == 6
    # released counter derives from seed status
    _save(memory, "Innocent", "a released creature", "2026-08-10T10:00:00",
          status="released")
    state = hydrate_from_memory(memory)
    assert state["released_count"] == 1
