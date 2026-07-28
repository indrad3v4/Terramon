"""GeoTournamentService — orchestrates proximity-based creature tournaments.

M02: When two creatures of the same archetype meet on the map (via M01
proximity), this service creates a tournament offer. Both players accept
async (via Nostr), and the winner is determined by composite score:

    score = bond×0.4 + evolution×0.3 + embedding×0.3

Build-via-learn: Chip Huyen's agent loop applied to multi-player interaction.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from typing import Optional

from terramon.domain.geo_battle import (
    GeoBattle,
    GeoBattleStatus,
    BattleCreature,
    compute_composite_score,
    WINNER_XP_BONUS,
    LOSER_XP_BONUS,
)
from terramon.domain.thought_seed import ThoughtSeed
from terramon.ports.memory_port import MemoryPort

log = logging.getLogger("terramon.geo_tournament")

# ── Embedding centroid cache ──────────────────────────────────────

_ARCHETYPE_CENTROIDS: dict[str, dict[int, float]] | None = None


def _get_archetype_centroids() -> dict[str, dict[int, float]]:
    """Lazy-load archetype centroids from the EmbeddingClassifier.

    Returns a dict mapping archetype name -> L2-normalised centroid vector.
    """
    global _ARCHETYPE_CENTROIDS
    if _ARCHETYPE_CENTROIDS is not None:
        return _ARCHETYPE_CENTROIDS

    from terramon.adapters.embedding_classifier import EmbeddingClassifier
    from terramon.adapters.embedding_classifier import _centroid, _encode

    classifier = EmbeddingClassifier()
    centroids: dict[str, dict[int, float]] = {}
    for name, examples in classifier.ARCHETYPES.items():
        vectors = [_encode(ph) for ph in examples]
        centroids[name] = _centroid(vectors)
    _ARCHETYPE_CENTROIDS = centroids
    return centroids


def _cosine_similarity(a: dict[int, float], b: dict[int, float]) -> float:
    """Cosine similarity of two L2-normalised sparse vectors."""
    if not a or not b:
        return 0.0
    small, big = (a, b) if len(a) < len(b) else (b, a)
    return sum(w * big.get(k, 0.0) for k, w in small.items())


def compute_embedding_cosine_sim(seed: ThoughtSeed, archetype: str) -> float:
    """Compute cosine similarity between a creature's embedding and its
    archetype centroid.

    This measures how strongly the creature embodies its archetype —
    higher values mean more archetypically "pure".

    Returns a float in [0, 1].
    """
    centroids = _get_archetype_centroids()
    centroid = centroids.get(archetype)
    if centroid is None:
        return 0.5  # fallback — unknown archetype

    # Get the creature's embedding from its insight
    embedding = seed.insight.embedding if seed.insight else None
    if embedding is None:
        return 0.3  # fallback — no embedding available

    sim = _cosine_similarity(embedding, centroid)
    # Clamp to [0, 1]
    return max(0.0, min(sim, 1.0))


# ── Proximity match detection ─────────────────────────────────────


def find_same_archetype_nearby(
    memory: MemoryPort,
    archetype: str,
    lat: float,
    lon: float,
    radius_km: float = 1.0,
) -> list[tuple[ThoughtSeed, float]]:
    """Find nearby creatures (via proximity search) of the same archetype.

    Args:
        memory: The memory port to search.
        archetype: The archetype to match (e.g. "Hero").
        lat, lon: The location to search from.
        radius_km: Search radius in km.

    Returns:
        List of (seed, distance_km) tuples, closest first.
    """
    nearby = memory.find_nearby(lat, lon, radius_km=radius_km)
    return [
        (seed, dist)
        for seed, dist in nearby
        if seed.summoned_agent == archetype
    ]


def _make_battle_creature(
    seed: ThoughtSeed,
    player_id: str = "player_default",
    bond_level: int = 0,
    evolution_stage: int = 0,
) -> BattleCreature:
    """Create a BattleCreature from a ThoughtSeed."""
    emb_sim = compute_embedding_cosine_sim(seed, seed.summoned_agent)
    return BattleCreature(
        agent_id=seed.timestamp,  # use timestamp as simple unique id
        player_id=player_id,
        archetype=seed.summoned_agent,
        bond_level=bond_level,
        evolution_stage=evolution_stage,
        embedding_cosine_sim=emb_sim,
        lat=seed.lat,
        lon=seed.lon,
        place_name=seed.place_name,
    )


# ── GeoTournamentService ──────────────────────────────────────────


class GeoTournamentService:
    """Orchestrates proximity-based creature tournaments.

    The service:
      1. Checks for same-archetype proximity matches
      2. Creates tournament offers
      3. Manages accept/decline flow
      4. Resolves battles with composite scoring
      5. Awards XP to winner/loser

    Battles are persisted in-memory and can be serialised via to/from dict.
    """

    def __init__(self) -> None:
        self._battles: dict[str, GeoBattle] = {}
        # Index pending offers by (archetype, player_id) to prevent dupes
        self._pending_by_player: dict[str, list[str]] = defaultdict(list)

    # ── Battle lifecycle ─────────────────────────────────────────

    def check_and_offer(
        self,
        memory: MemoryPort,
        archetype: str,
        lat: float,
        lon: float,
        player_id: str = "player_default",
        bond_level: int = 0,
        evolution_stage: int = 0,
        radius_km: float = 1.0,
    ) -> Optional[GeoBattle]:
        """Check for same-archetype creatures nearby and create a battle offer.

        Called after a summon. Looks for creatures of the same archetype
        within `radius_km`. If found and no pending offer exists between
        these players, creates a GeoBattle.

        Args:
            memory: The memory port for proximity search.
            archetype: The summoned creature's archetype.
            lat, lon: Location of the summon.
            player_id: The summoning player's ID.
            bond_level: Current bond level of the creature.
            evolution_stage: Current evolution stage (0, 1, 2).
            radius_km: Proximity radius.

        Returns:
            The created GeoBattle, or None if no match found.
        """
        # Skip if no valid geo coordinates
        if not lat and not lon:
            return None

        # Find nearby same-archetype creatures
        matches = find_same_archetype_nearby(
            memory, archetype, lat, lon, radius_km=radius_km
        )

        if not matches:
            return None

        # Take the closest match
        nearest_seed, distance_km = matches[0]

        # Don't offer against yourself
        if nearest_seed.timestamp == str(time.time()):
            return None

        # Check for existing pending offers for this player
        if player_id in self._pending_by_player:
            for bid in self._pending_by_player[player_id]:
                battle = self._battles.get(bid)
                if battle and battle.status == GeoBattleStatus.PENDING:
                    # There's already a pending offer for this player
                    return None

        # Create the battle offer
        creature_a = _make_battle_creature(
            nearest_seed,
            player_id="opponent",
            bond_level=5,       # reasonable default for opponent
            evolution_stage=0,
        )
        creature_b = _make_battle_creature(
            ThoughtSeed(
                raw_input="",
                summoned_agent=archetype,
                timestamp=str(time.time()),
                lat=lat,
                lon=lon,
                place_name="",
            ),
            player_id=player_id,
            bond_level=bond_level,
            evolution_stage=evolution_stage,
        )

        battle = GeoBattle(
            battle_id=str(uuid.uuid4())[:8],
            creature_a=creature_a,
            creature_b=creature_b,
            archetype=archetype,
        )

        self._battles[battle.battle_id] = battle
        self._pending_by_player[player_id].append(battle.battle_id)
        self._pending_by_player["opponent"].append(battle.battle_id)

        log.info(
            "Geo-tournament offered: %s vs %s (archetype=%s, dist=%.2fkm)",
            creature_a.player_id, creature_b.player_id,
            archetype, distance_km,
        )
        return battle

    def accept(self, battle_id: str, player_id: str) -> Optional[GeoBattle]:
        """Accept a tournament offer.

        Returns the updated battle if both accepted, None if not found.
        """
        battle = self._battles.get(battle_id)
        if battle is None:
            log.warning("Battle %s not found for accept", battle_id)
            return None
        both = battle.accept(player_id)
        log.info(
            "Battle %s accepted by %s (both=%s)",
            battle_id, player_id, both,
        )
        return battle

    def decline(self, battle_id: str, player_id: str) -> Optional[GeoBattle]:
        """Decline a tournament offer."""
        battle = self._battles.get(battle_id)
        if battle is None:
            return None
        battle.decline(player_id)
        self._cleanup_pending(battle_id)
        return battle

    def resolve(self, battle_id: str) -> Optional[GeoBattle]:
        """Resolve an accepted battle: compute scores, determine winner.

        Returns the resolved GeoBattle, or None if not found.
        """
        battle = self._battles.get(battle_id)
        if battle is None:
            log.warning("Battle %s not found for resolve", battle_id)
            return None
        try:
            winner, loser = battle.resolve()
            self._cleanup_pending(battle_id)
            log.info(
                "Battle %s resolved: %s beats %s "
                "(score_a=%.3f, score_b=%.3f, xp_winner=%d, xp_loser=%d)",
                battle_id, winner, loser,
                battle.score_a, battle.score_b,
                battle.xp_awarded_to_winner, battle.xp_awarded_to_loser,
            )
            return battle
        except ValueError as exc:
            log.error("Failed to resolve battle %s: %s", battle_id, exc)
            return None

    def cleanup_expired(self) -> int:
        """Mark all expired pending battles as EXPIRED.

        Returns the number of battles expired.
        """
        count = 0
        expired_ids = []
        for bid, battle in self._battles.items():
            if battle.expired:
                battle.status = GeoBattleStatus.EXPIRED
                expired_ids.append(bid)
                count += 1
        for bid in expired_ids:
            self._cleanup_pending(bid)
        if count:
            log.info("Expired %d pending battle(s)", count)
        return count

    # ── Query ────────────────────────────────────────────────────

    def get_battle(self, battle_id: str) -> Optional[GeoBattle]:
        return self._battles.get(battle_id)

    def get_pending_for_player(self, player_id: str) -> list[GeoBattle]:
        """Return all pending battles for a player."""
        bids = self._pending_by_player.get(player_id, [])
        return [
            self._battles[bid]
            for bid in bids
            if bid in self._battles
            and self._battles[bid].status == GeoBattleStatus.PENDING
        ]

    def get_completed_for_player(self, player_id: str) -> list[GeoBattle]:
        """Return all completed battles for a player."""
        return [
            b
            for b in self._battles.values()
            if b.status == GeoBattleStatus.COMPLETED
            and (b.creature_a.player_id == player_id
                 or b.creature_b.player_id == player_id)
        ]

    def get_active_battles(self) -> list[GeoBattle]:
        """Return all pending or accepted battles."""
        return [
            b for b in self._battles.values()
            if b.status in (
                GeoBattleStatus.PENDING,
                GeoBattleStatus.ACCEPTED,
            )
        ]

    def all_battles(self) -> list[GeoBattle]:
        return list(self._battles.values())

    def battle_count(self) -> int:
        return len(self._battles)

    # ── Internal ─────────────────────────────────────────────────

    def _cleanup_pending(self, battle_id: str) -> None:
        """Remove a battle from all pending indexes."""
        for player_id in list(self._pending_by_player.keys()):
            if battle_id in self._pending_by_player[player_id]:
                self._pending_by_player[player_id].remove(battle_id)
            # Clean up empty lists
            if not self._pending_by_player[player_id]:
                del self._pending_by_player[player_id]

    # ── Persistence ──────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize all battles to a dict for JSON persistence."""
        return {
            bid: b.to_dict()
            for bid, b in self._battles.items()
        }

    @classmethod
    def from_dict(cls, data: dict) -> GeoTournamentService:
        """Deserialize battles from a dict."""
        svc = cls()
        for bid, bdata in data.items():
            ca = BattleCreature(**bdata.pop("creature_a"))
            cb = BattleCreature(**bdata.pop("creature_b"))
            status_str = bdata.pop("status", "pending")
            status = GeoBattleStatus(status_str)
            bdata.pop("battle_id", None)  # use bid from dict key
            battle = GeoBattle(
                battle_id=bid,
                creature_a=ca,
                creature_b=cb,
                archetype=bdata.pop("archetype", ""),
                status=status,
                **bdata,
            )
            svc._battles[bid] = battle
            if status == GeoBattleStatus.PENDING:
                svc._pending_by_player[ca.player_id].append(bid)
                svc._pending_by_player[cb.player_id].append(bid)
        return svc
