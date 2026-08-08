"""Release mechanic + progress reframe — offline domain tests.

Win concept "Встреча, а не коллекция": a creature is RELEASED, not
collected; release is a reward (liberation), not death. These tests
verify the domain layer only — no network, no I/O, no mocks.
"""

import pytest

from terramon.domain.creature_agent import CreatureAgent, CreatureState
from terramon.domain.progress import GOAL_TIERS, PlayerProgress
from terramon.domain.rarity import Rarity


# ---------------------------------------------------------------------------
# Release mechanic
# ---------------------------------------------------------------------------


def test_release_sets_status_and_freezes_needs():
    agent = CreatureAgent(agent_id="rel-001", name="Mia", hunger=50, energy=50, happiness=50)
    agent.release("Прощай")

    assert agent.status == "released"
    assert agent.released is True
    assert agent.released_at != ""
    assert agent.final_words == "Прощай"

    before = (agent.hunger, agent.energy, agent.happiness)
    agent.tick(day_phase="afternoon")
    agent.tick(day_phase="night")
    # Needs are frozen — no decay after release (burden of care lifted)
    assert (agent.hunger, agent.energy, agent.happiness) == before


def test_release_does_not_kill():
    # Critically low stats — the old decay path would push toward
    # dormancy. Release must NOT kill or sadden: it liberates.
    agent = CreatureAgent(agent_id="rel-002", name="Mia", hunger=5, energy=5, happiness=3)
    msg = agent.release("Будь свободен")

    assert agent.status == "released"   # not dead, not gone
    assert agent.released is True
    assert agent.happiness == 3         # stats untouched by release
    # Neutral/positive wording — no death vocabulary
    assert "die" not in msg.text.lower()
    assert "dead" not in msg.text.lower()
    # Even at near-zero stats, release freezes the decay
    before = (agent.hunger, agent.energy, agent.happiness)
    agent.tick(day_phase="night")
    assert (agent.hunger, agent.energy, agent.happiness) == before


def test_release_twice_is_noop():
    agent = CreatureAgent(agent_id="rel-003", name="Mia")
    agent.release("Пока")
    first_at = agent.released_at
    first_ts = agent.release_timestamp

    agent.release("Ещё раз")

    assert agent.status == "released"
    assert agent.released_at == first_at
    assert agent.release_timestamp == first_ts
    assert agent.final_words == "Пока"  # first goodbye is kept


# ---------------------------------------------------------------------------
# Progress reframe
# ---------------------------------------------------------------------------


def test_progress_counts_released_only():
    progress = PlayerProgress()
    progress.award("Hero", Rarity.COMMON)
    progress.award("Sage", Rarity.COMMON)
    progress.award("Rebel", Rarity.COMMON)
    assert progress.distinct_count == 3  # legacy counter: 3 distinct summoned

    progress.record_release("Hero")

    assert progress.released_distinct_count == 1  # reframed win counter
    assert progress.released_count() == 1         # helper alias
    assert progress.distinct_count == 3           # legacy still works

    # Duplicate release of the same archetype does not double-count
    progress.record_release("Hero")
    assert progress.released_distinct_count == 1


def test_badge_renamed():
    names = [t["name"] for t in GOAL_TIERS]
    assert "Встретивший" in names
    for tier in GOAL_TIERS:
        label = tier["name"]
        assert "Tamer" not in label
        assert "tame" not in label.lower()
    # Structure preserved: same 5-slot first tier, keys intact
    assert GOAL_TIERS[0]["distinct"] == 5
    assert {"name", "distinct", "badge", "unlock"} <= set(GOAL_TIERS[0])
