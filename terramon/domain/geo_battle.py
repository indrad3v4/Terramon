"""Geo-battle domain model — same-archetype proximity tournament.

M02: Two creatures of the same archetype meet on the map → tournament offer
→ both accept → winner by composite score → XP bonus.

Build-via-learn: Trophy (Lens #36), Triangularity (Lens #33), 
Rapture (Lens #80), Envy (Lens #30).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GeoBattleStatus(Enum):
    """Lifecycle of a geo-tournament offer."""
    PENDING = "pending"        # offered, waiting for accept
    ACCEPTED = "accepted"      # both players accepted, ready to resolve
    DECLINED = "declined"      # one player declined
    COMPLETED = "completed"    # resolved with a winner
    EXPIRED = "expired"        # 24h passed without both accepting


# ── Score computation ──────────────────────────────────────────────

# Weights for the composite score (from acceptance criteria).
BOND_WEIGHT = 0.4
EVOLUTION_WEIGHT = 0.3
EMBEDDING_WEIGHT = 0.3

# XP rewards
WINNER_XP_BONUS = 50
LOSER_XP_BONUS = 15


def compute_composite_score(
    bond_level: int,
    evolution_stage: int,
    embedding_cosine_sim: float,
    *,
    max_bond: int = 50,
    max_evolution: int = 2,
) -> float:
    """Compute the composite tournament score for one creature.

    Each component is normalized to [0, 1] before weighting:

        score = bond×0.4 + evolution×0.3 + embedding×0.3

    Args:
        bond_level: The creature's bond level (0 .. max_bond).
        evolution_stage: The creature's evolution stage (0, 1, 2).
        embedding_cosine_sim: Cosine similarity of the creature's thought
            embedding to its archetype centroid [0, 1]. Higher = more
            archetypically "pure" = stronger.
        max_bond: Maximum bond level for normalization.
        max_evolution: Maximum evolution stage for normalization.

    Returns:
        Composite score in [0, 1].
    """
    bond_norm = min(bond_level / max(max_bond, 1), 1.0)
    evo_norm = min(evolution_stage / max(max_evolution, 1), 1.0)
    emb_norm = max(0.0, min(embedding_cosine_sim, 1.0))

    return (
        bond_norm * BOND_WEIGHT
        + evo_norm * EVOLUTION_WEIGHT
        + emb_norm * EMBEDDING_WEIGHT
    )


# ── Domain dataclasses ─────────────────────────────────────────────


@dataclass
class BattleCreature:
    """A creature's entry in a geo-battle — its stats at offer time."""
    agent_id: str
    player_id: str
    archetype: str
    bond_level: int
    evolution_stage: int
    embedding_cosine_sim: float
    lat: float
    lon: float
    place_name: str = ""


@dataclass
class GeoBattle:
    """A tournament between two same-archetype creatures that met on the map.

    Created automatically when proximity detects two creatures of the
    same archetype within 1 km of each other.
    """
    battle_id: str
    creature_a: BattleCreature
    creature_b: BattleCreature
    archetype: str
    status: GeoBattleStatus = GeoBattleStatus.PENDING
    created_at: float = 0.0
    expires_at: float = 0.0          # created_at + 24h
    accepted_by_a: bool = False
    accepted_by_b: bool = False
    score_a: float = 0.0             # composite score before resolution
    score_b: float = 0.0
    winner_id: str = ""              # player_id of the winner
    loser_id: str = ""               # player_id of the loser
    xp_awarded_to_winner: int = 0
    xp_awarded_to_loser: int = 0
    resolved_at: float = 0.0

    def __post_init__(self) -> None:
        now = self.created_at or time.time()
        self.created_at = now
        self.expires_at = now + 86400  # 24 hours

    @property
    def expired(self) -> bool:
        """True if 24h have passed and battle is still pending."""
        return (
            self.status == GeoBattleStatus.PENDING
            and time.time() > self.expires_at
        )

    @property
    def both_accepted(self) -> bool:
        return self.accepted_by_a and self.accepted_by_b

    def accept(self, player_id: str) -> bool:
        """Record an acceptance. Returns True if now both accepted."""
        if self.status != GeoBattleStatus.PENDING:
            return False
        if player_id == self.creature_a.player_id:
            self.accepted_by_a = True
        elif player_id == self.creature_b.player_id:
            self.accepted_by_b = True
        else:
            return False

        if self.both_accepted:
            self.status = GeoBattleStatus.ACCEPTED
        return self.both_accepted

    def decline(self, player_id: str) -> None:
        """One player declines → battle is declined."""
        if self.status != GeoBattleStatus.PENDING:
            return
        self.status = GeoBattleStatus.DECLINED

    def resolve(self) -> tuple[str, str]:
        """Compute composite scores and determine winner/loser.

        Returns:
            (winner_player_id, loser_player_id)

        Raises:
            ValueError: If battle is not in ACCEPTED status.
        """
        if self.status != GeoBattleStatus.ACCEPTED:
            raise ValueError(
                f"Cannot resolve battle in status {self.status.value}"
            )

        self.score_a = compute_composite_score(
            bond_level=self.creature_a.bond_level,
            evolution_stage=self.creature_a.evolution_stage,
            embedding_cosine_sim=self.creature_a.embedding_cosine_sim,
        )
        self.score_b = compute_composite_score(
            bond_level=self.creature_b.bond_level,
            evolution_stage=self.creature_b.evolution_stage,
            embedding_cosine_sim=self.creature_b.embedding_cosine_sim,
        )

        if self.score_a >= self.score_b:
            self.winner_id = self.creature_a.player_id
            self.loser_id = self.creature_b.player_id
        else:
            self.winner_id = self.creature_b.player_id
            self.loser_id = self.creature_a.player_id

        self.xp_awarded_to_winner = WINNER_XP_BONUS
        self.xp_awarded_to_loser = LOSER_XP_BONUS
        self.status = GeoBattleStatus.COMPLETED
        self.resolved_at = time.time()

        return self.winner_id, self.loser_id

    def to_dict(self) -> dict:
        """Serialize to a plain dict for persistence."""
        return {
            "battle_id": self.battle_id,
            "archetype": self.archetype,
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "accepted_by_a": self.accepted_by_a,
            "accepted_by_b": self.accepted_by_b,
            "score_a": self.score_a,
            "score_b": self.score_b,
            "winner_id": self.winner_id,
            "loser_id": self.loser_id,
            "xp_awarded_to_winner": self.xp_awarded_to_winner,
            "xp_awarded_to_loser": self.xp_awarded_to_loser,
            "resolved_at": self.resolved_at,
            "creature_a": {
                "agent_id": self.creature_a.agent_id,
                "player_id": self.creature_a.player_id,
                "archetype": self.creature_a.archetype,
                "bond_level": self.creature_a.bond_level,
                "evolution_stage": self.creature_a.evolution_stage,
                "embedding_cosine_sim": self.creature_a.embedding_cosine_sim,
                "lat": self.creature_a.lat,
                "lon": self.creature_a.lon,
                "place_name": self.creature_a.place_name,
            },
            "creature_b": {
                "agent_id": self.creature_b.agent_id,
                "player_id": self.creature_b.player_id,
                "archetype": self.creature_b.archetype,
                "bond_level": self.creature_b.bond_level,
                "evolution_stage": self.creature_b.evolution_stage,
                "embedding_cosine_sim": self.creature_b.embedding_cosine_sim,
                "lat": self.creature_b.lat,
                "lon": self.creature_b.lon,
                "place_name": self.creature_b.place_name,
            },
        }
