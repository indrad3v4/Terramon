"""Tests for M02 Geo-tournament — creatures compete by proximity.

Covers:
  - compute_composite_score() weighting
  - GeoBattle lifecycle (create, accept, decline, resolve, expire)
  - GeoTournamentService orchestration
  - Same-archetype proximity detection
  - GameLoop integration with tournament
  - XP award on resolution
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from terramon.domain.geo_battle import (
    GeoBattle,
    GeoBattleStatus,
    BattleCreature,
    compute_composite_score,
    BOND_WEIGHT,
    EVOLUTION_WEIGHT,
    EMBEDDING_WEIGHT,
    WINNER_XP_BONUS,
    LOSER_XP_BONUS,
)
from terramon.application.geo_tournament import (
    GeoTournamentService,
    find_same_archetype_nearby,
    compute_embedding_cosine_sim,
)
from terramon.domain.thought_seed import ThoughtSeed
from terramon.domain.insight import Insight
from terramon.adapters.json_memory import JsonMemory


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════


@pytest.fixture
def empty_memory(tmp_path: Path) -> JsonMemory:
    return JsonMemory(tmp_path / "geo_memory.jsonl")


@pytest.fixture
def svc() -> GeoTournamentService:
    return GeoTournamentService()


@pytest.fixture
def hero_battle() -> GeoBattle:
    """A ready-to-resolve battle between two Hero archetypes."""
    return GeoBattle(
        battle_id="test-battle-1",
        creature_a=BattleCreature(
            agent_id="ca1", player_id="player_a", archetype="Hero",
            bond_level=20, evolution_stage=1, embedding_cosine_sim=0.7,
            lat=50.06, lon=19.94, place_name="Kraków",
        ),
        creature_b=BattleCreature(
            agent_id="cb1", player_id="player_b", archetype="Hero",
            bond_level=10, evolution_stage=0, embedding_cosine_sim=0.5,
            lat=50.062, lon=19.942, place_name="Kraków",
        ),
        archetype="Hero",
        status=GeoBattleStatus.ACCEPTED,
        accepted_by_a=True,
        accepted_by_b=True,
    )


# ═══════════════════════════════════════════════════════════════════
# Score computation
# ═══════════════════════════════════════════════════════════════════


class TestCompositeScore:
    """Verify composite score formula: bond×0.4 + evolution×0.3 + embedding×0.3."""

    def test_zero_scores(self) -> None:
        score = compute_composite_score(0, 0, 0.0)
        assert score == 0.0

    def test_max_scores(self) -> None:
        score = compute_composite_score(50, 2, 1.0)
        expected = 1.0 * BOND_WEIGHT + 1.0 * EVOLUTION_WEIGHT + 1.0 * EMBEDDING_WEIGHT
        assert score == pytest.approx(expected, rel=1e-9)
        assert score == 1.0  # 0.4 + 0.3 + 0.3 = 1.0

    def test_bond_only(self) -> None:
        """Only bond contributes (evolution=0, embedding=0)."""
        score = compute_composite_score(25, 0, 0.0)
        expected = (25 / 50) * 0.4
        assert score == pytest.approx(expected, rel=1e-9)

    def test_evolution_only(self) -> None:
        """Only evolution contributes (bond=0, embedding=0)."""
        score = compute_composite_score(0, 2, 0.0)
        expected = 1.0 * 0.3
        assert score == pytest.approx(expected, rel=1e-9)

    def test_embedding_only(self) -> None:
        """Only embedding contributes (bond=0, evolution=0)."""
        score = compute_composite_score(0, 0, 0.8)
        expected = 0.8 * 0.3
        assert score == pytest.approx(expected, rel=1e-9)

    def test_creature_a_stronger(self) -> None:
        """Creature A with higher bond + evolution + embedding wins."""
        score_a = compute_composite_score(30, 1, 0.7)
        score_b = compute_composite_score(10, 0, 0.4)
        assert score_a > score_b

    def test_creature_b_stronger(self) -> None:
        """Creature B with higher bond wins despite lower evolution."""
        score_a = compute_composite_score(5, 2, 0.5)
        score_b = compute_composite_score(40, 0, 0.6)
        assert score_b > score_a  # bond weight (0.4) beats evolution (0.3)

    def test_clamping(self) -> None:
        """Values above max are clamped to 1.0."""
        score = compute_composite_score(100, 5, 2.0)
        assert score == 1.0

    def test_negative_embedding(self) -> None:
        """Negative embedding cosine sim is clamped to 0."""
        score = compute_composite_score(10, 1, -0.5)
        assert score >= 0.0
        # bond_norm = 10/50 = 0.2, evo_norm = 1/2 = 0.5, emb_norm = 0.0
        expected = 0.2 * 0.4 + 0.5 * 0.3
        assert score == pytest.approx(expected, rel=1e-9)


# ═══════════════════════════════════════════════════════════════════
# GeoBattle domain
# ═══════════════════════════════════════════════════════════════════


class TestGeoBattle:
    """GeoBattle lifecycle — create, accept, decline, resolve, expire."""

    def test_create_pending(self) -> None:
        """A new battle starts as PENDING with 24h expiry."""
        battle = GeoBattle(
            battle_id="b1",
            creature_a=BattleCreature("ca", "pa", "Hero", 10, 1, 0.6, 0, 0),
            creature_b=BattleCreature("cb", "pb", "Hero", 5, 0, 0.4, 0, 0),
            archetype="Hero",
        )
        assert battle.status == GeoBattleStatus.PENDING
        assert not battle.accepted_by_a
        assert not battle.accepted_by_b
        assert battle.expires_at - battle.created_at == 86400  # 24h
        assert not battle.both_accepted

    def test_accept_by_first_player(self) -> None:
        """First player accept doesn't trigger both_accepted."""
        battle = GeoBattle(
            battle_id="b2",
            creature_a=BattleCreature("ca", "pa", "Hero", 10, 1, 0.6, 0, 0),
            creature_b=BattleCreature("cb", "pb", "Hero", 5, 0, 0.4, 0, 0),
            archetype="Hero",
        )
        result = battle.accept("pa")
        assert result is False  # not both yet
        assert battle.accepted_by_a
        assert not battle.accepted_by_b
        assert battle.status == GeoBattleStatus.PENDING

    def test_both_accept_triggers_accepted(self) -> None:
        """Both players accept -> status becomes ACCEPTED."""
        battle = GeoBattle(
            battle_id="b3",
            creature_a=BattleCreature("ca", "pa", "Hero", 10, 1, 0.6, 0, 0),
            creature_b=BattleCreature("cb", "pb", "Hero", 5, 0, 0.4, 0, 0),
            archetype="Hero",
        )
        battle.accept("pa")
        result = battle.accept("pb")
        assert result is True
        assert battle.status == GeoBattleStatus.ACCEPTED
        assert battle.both_accepted

    def test_decline(self) -> None:
        """Decline sets status to DECLINED."""
        battle = GeoBattle(
            battle_id="b4",
            creature_a=BattleCreature("ca", "pa", "Hero", 10, 1, 0.6, 0, 0),
            creature_b=BattleCreature("cb", "pb", "Hero", 5, 0, 0.4, 0, 0),
            archetype="Hero",
        )
        battle.decline("pa")
        assert battle.status == GeoBattleStatus.DECLINED

    def test_accept_after_decline_noop(self) -> None:
        """Accepting a declined battle does nothing."""
        battle = GeoBattle(
            battle_id="b5",
            creature_a=BattleCreature("ca", "pa", "Hero", 10, 1, 0.6, 0, 0),
            creature_b=BattleCreature("cb", "pb", "Hero", 5, 0, 0.4, 0, 0),
            archetype="Hero",
        )
        battle.decline("pa")
        battle.accept("pb")  # should be ignored
        assert battle.status == GeoBattleStatus.DECLINED

    def test_accept_wrong_player(self) -> None:
        """Unknown player accept does nothing."""
        battle = GeoBattle(
            battle_id="b6",
            creature_a=BattleCreature("ca", "pa", "Hero", 10, 1, 0.6, 0, 0),
            creature_b=BattleCreature("cb", "pb", "Hero", 5, 0, 0.4, 0, 0),
            archetype="Hero",
        )
        result = battle.accept("stranger")
        assert result is False
        assert not battle.accepted_by_a
        assert not battle.accepted_by_b

    def test_resolve_requires_accepted(self) -> None:
        """Resolving a non-ACCEPTED battle raises ValueError."""
        battle = GeoBattle(
            battle_id="b7",
            creature_a=BattleCreature("ca", "pa", "Hero", 10, 1, 0.6, 0, 0),
            creature_b=BattleCreature("cb", "pb", "Hero", 5, 0, 0.4, 0, 0),
            archetype="Hero",
        )
        with pytest.raises(ValueError, match="pending"):
            battle.resolve()

    def test_resolve_stronger_creature_wins(self, hero_battle: GeoBattle) -> None:
        """Creature A (higher bond+evo+emb) beats Creature B."""
        winner, loser = hero_battle.resolve()
        assert winner == hero_battle.creature_a.player_id
        assert loser == hero_battle.creature_b.player_id
        assert hero_battle.score_a > hero_battle.score_b

    def test_resolve_xp_awarded(self, hero_battle: GeoBattle) -> None:
        """Winner gets WINNER_XP_BONUS, loser gets LOSER_XP_BONUS."""
        hero_battle.resolve()
        assert hero_battle.xp_awarded_to_winner == WINNER_XP_BONUS
        assert hero_battle.xp_awarded_to_loser == LOSER_XP_BONUS
        assert hero_battle.xp_awarded_to_winner > hero_battle.xp_awarded_to_loser

    def test_resolve_status_completed(self, hero_battle: GeoBattle) -> None:
        """After resolve, status is COMPLETED and resolved_at is set."""
        hero_battle.resolve()
        assert hero_battle.status == GeoBattleStatus.COMPLETED
        assert hero_battle.resolved_at > 0

    def test_expired_true(self) -> None:
        """A battle created 25h ago is expired."""
        battle = GeoBattle(
            battle_id="b8",
            creature_a=BattleCreature("ca", "pa", "Hero", 10, 1, 0.6, 0, 0),
            creature_b=BattleCreature("cb", "pb", "Hero", 5, 0, 0.4, 0, 0),
            archetype="Hero",
            created_at=time.time() - 90000,  # 25h ago
        )
        # expires_at was computed in __post_init__ using created_at
        assert battle.expired is True

    def test_expired_false_fresh(self) -> None:
        """A brand new battle is not expired."""
        battle = GeoBattle(
            battle_id="b9",
            creature_a=BattleCreature("ca", "pa", "Hero", 10, 1, 0.6, 0, 0),
            creature_b=BattleCreature("cb", "pb", "Hero", 5, 0, 0.4, 0, 0),
            archetype="Hero",
        )
        assert battle.expired is False

    def test_to_dict_roundtrip(self) -> None:
        """Serialisation roundtrip preserves all fields."""
        battle = GeoBattle(
            battle_id="b10",
            creature_a=BattleCreature("ca", "pa", "Hero", 10, 1, 0.6, 50.0, 20.0, "place"),
            creature_b=BattleCreature("cb", "pb", "Sage", 5, 0, 0.4, 51.0, 21.0, "other"),
            archetype="Hero",
            status=GeoBattleStatus.ACCEPTED,
            accepted_by_a=True,
            accepted_by_b=True,
        )
        d = battle.to_dict()
        assert d["battle_id"] == "b10"
        assert d["archetype"] == "Hero"
        assert d["status"] == "accepted"
        assert d["creature_a"]["bond_level"] == 10
        assert d["creature_b"]["archetype"] == "Sage"
        # Reconstruct from dict
        ca = BattleCreature(**d["creature_a"])
        cb = BattleCreature(**d["creature_b"])
        restored = GeoBattle(
            battle_id=d["battle_id"],
            creature_a=ca,
            creature_b=cb,
            archetype=d["archetype"],
            status=GeoBattleStatus(d["status"]),
            created_at=d["created_at"],
            expires_at=d["expires_at"],
            accepted_by_a=d["accepted_by_a"],
            accepted_by_b=d["accepted_by_b"],
            score_a=d["score_a"],
            score_b=d["score_b"],
            winner_id=d["winner_id"],
            loser_id=d["loser_id"],
            xp_awarded_to_winner=d["xp_awarded_to_winner"],
            xp_awarded_to_loser=d["xp_awarded_to_loser"],
            resolved_at=d["resolved_at"],
        )
        assert restored.battle_id == battle.battle_id
        assert restored.creature_a.bond_level == battle.creature_a.bond_level
        assert restored.status == battle.status


# ═══════════════════════════════════════════════════════════════════
# GeoTournamentService
# ═══════════════════════════════════════════════════════════════════


class TestGeoTournamentService:
    """GeoTournamentService orchestration."""

    def test_check_and_offer_no_memory(self, svc: GeoTournamentService, empty_memory: JsonMemory) -> None:
        """No nearby creatures -> no offer."""
        battle = svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=50.06, lon=19.94,
        )
        assert battle is None
        assert svc.battle_count() == 0

    def test_check_and_offer_with_match(self, svc: GeoTournamentService, empty_memory: JsonMemory) -> None:
        """Same-archetype creature nearby creates an offer."""
        # Seed a Hero creature nearby
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.061, lon=19.941,
        ))
        battle = svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=50.06, lon=19.94,
        )
        assert battle is not None
        assert battle.archetype == "Hero"
        assert battle.status == GeoBattleStatus.PENDING
        assert svc.battle_count() == 1

    def test_check_and_offer_no_geo_skipped(self, svc: GeoTournamentService, empty_memory: JsonMemory) -> None:
        """Creature without geo coordinates is skipped."""
        battle = svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=0.0, lon=0.0,
        )
        assert battle is None

    def test_different_archetype_no_match(self, svc: GeoTournamentService, empty_memory: JsonMemory) -> None:
        """Different archetype nearby does not trigger offer."""
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Sage",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.061, lon=19.941,
        ))
        battle = svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=50.06, lon=19.94,
        )
        assert battle is None

    def test_full_flow_accept_and_resolve(self, svc: GeoTournamentService, empty_memory: JsonMemory) -> None:
        """Full tournament lifecycle: offer -> accept -> resolve."""
        # Seed nearby Hero
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.061, lon=19.941,
        ))
        battle = svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=50.06, lon=19.94,
            player_id="player_default",
            bond_level=15,
            evolution_stage=1,
        )
        assert battle is not None
        bid = battle.battle_id

        # Both accept
        svc.accept(bid, "opponent")
        svc.accept(bid, "player_default")

        # Resolve
        resolved = svc.resolve(bid)
        assert resolved is not None
        assert resolved.status == GeoBattleStatus.COMPLETED
        assert resolved.winner_id in ("player_default", "opponent")
        assert resolved.xp_awarded_to_winner == WINNER_XP_BONUS
        assert resolved.xp_awarded_to_loser == LOSER_XP_BONUS

    def test_decline_flow(self, svc: GeoTournamentService, empty_memory: JsonMemory) -> None:
        """Declining a tournament cleans up properly."""
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.061, lon=19.941,
        ))
        battle = svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=50.06, lon=19.94,
        )
        assert battle is not None

        svc.decline(battle.battle_id, "player_default")
        declined = svc.get_battle(battle.battle_id)
        assert declined is not None
        assert declined.status == GeoBattleStatus.DECLINED
        # Should not show as pending
        pending = svc.get_pending_for_player("player_default")
        assert len(pending) == 0

    def test_cleanup_expired(self, svc: GeoTournamentService, empty_memory: JsonMemory) -> None:
        """Expired battles are marked EXPIRED."""
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.061, lon=19.941,
        ))
        battle = svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=50.06, lon=19.94,
        )
        assert battle is not None
        # Force expiry by setting created_at far back
        battle.created_at = time.time() - 90000
        battle.expires_at = battle.created_at + 86400

        count = svc.cleanup_expired()
        assert count == 1
        expired = svc.get_battle(battle.battle_id)
        assert expired is not None
        assert expired.status == GeoBattleStatus.EXPIRED

    def test_pending_per_player(self, svc: GeoTournamentService, empty_memory: JsonMemory) -> None:
        """Pending battles are indexed by player."""
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.061, lon=19.941,
        ))
        svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=50.06, lon=19.94,
            player_id="my_player",
        )
        pending = svc.get_pending_for_player("my_player")
        assert len(pending) == 1
        assert pending[0].archetype == "Hero"

    def test_completed_per_player(self, svc: GeoTournamentService, empty_memory: JsonMemory) -> None:
        """Completed battles appear in get_completed_for_player."""
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.061, lon=19.941,
        ))
        battle = svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=50.06, lon=19.94,
            player_id="player_p",
        )
        svc.accept(battle.battle_id, "opponent")
        svc.accept(battle.battle_id, "player_p")
        svc.resolve(battle.battle_id)

        completed = svc.get_completed_for_player("player_p")
        assert len(completed) == 1

    def test_no_duplicate_offers(self, svc: GeoTournamentService, empty_memory: JsonMemory) -> None:
        """Only one pending offer per player at a time."""
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.061, lon=19.941,
        ))
        # First offer
        b1 = svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=50.06, lon=19.94,
            player_id="dup_player",
        )
        assert b1 is not None

        # Second attempt — should be deduped
        b2 = svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=50.06, lon=19.94,
            player_id="dup_player",
        )
        assert b2 is None

    def test_serialization_roundtrip(self, svc: GeoTournamentService, empty_memory: JsonMemory) -> None:
        """Full serialisation roundtrip preserves all battles."""
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.061, lon=19.941,
        ))
        svc.check_and_offer(
            memory=empty_memory,
            archetype="Hero",
            lat=50.06, lon=19.94,
            player_id="p1",
        )
        data = svc.to_dict()
        assert len(data) == 1

        restored = GeoTournamentService.from_dict(data)
        assert restored.battle_count() == 1
        restored_battle = list(restored.all_battles())[0]
        assert restored_battle.archetype == "Hero"
        assert restored_battle.creature_a.player_id == "opponent"
        assert restored_battle.creature_b.player_id == "p1"


# ═══════════════════════════════════════════════════════════════════
# Proximity matching
# ═══════════════════════════════════════════════════════════════════


class TestProximityMatching:
    """Same-archetype proximity detection."""

    def test_find_same_archetype(self, empty_memory: JsonMemory) -> None:
        """Finds same-archetype creatures nearby."""
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.061, lon=19.941,
        ))
        matches = find_same_archetype_nearby(
            empty_memory, "Hero", 50.06, 19.94, radius_km=1.0,
        )
        assert len(matches) == 1
        assert matches[0][0].summoned_agent == "Hero"

    def test_different_archetype_excluded(self, empty_memory: JsonMemory) -> None:
        """Different archetype is excluded from results."""
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Sage",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.061, lon=19.941,
        ))
        matches = find_same_archetype_nearby(
            empty_memory, "Hero", 50.06, 19.94, radius_km=1.0,
        )
        assert len(matches) == 0

    def test_far_creature_excluded(self, empty_memory: JsonMemory) -> None:
        """Creature outside radius is excluded."""
        empty_memory.save_seed(ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
            lat=50.5, lon=20.5,  # ~70 km from origin
        ))
        matches = find_same_archetype_nearby(
            empty_memory, "Hero", 50.06, 19.94, radius_km=1.0,
        )
        assert len(matches) == 0


# ═══════════════════════════════════════════════════════════════════
# Embedding score
# ═══════════════════════════════════════════════════════════════════


class TestEmbeddingCosineSim:
    """compute_embedding_cosine_sim edge cases."""

    def test_no_insight(self) -> None:
        """Seed without insight returns fallback 0.3."""
        seed = ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
        )
        sim = compute_embedding_cosine_sim(seed, "Hero")
        assert sim == 0.3

    def test_no_embedding_in_insight(self) -> None:
        """Seed with insight but no embedding returns fallback."""
        seed = ThoughtSeed.make(
            raw_input="test",
            summoned_agent="Hero",
            timestamp="2026-07-28T12:00:00Z",
            insight=Insight(driver="d", barrier="b", therefore="t", archetype="Hero"),
        )
        sim = compute_embedding_cosine_sim(seed, "Hero")
        assert sim == 0.3
