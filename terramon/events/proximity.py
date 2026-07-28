"""Event emitted when a summoned creature is near another creature on the global map.

I11: Cross-player proximity events. After a summon, the proximity check queries
both local memory and Nostr relays for nearby creatures. If any are found within
1 km, a ProximityEvent is emitted with details about both creatures so the game
loop can notify both players and apply a bond level bonus.
"""

from __future__ import annotations

from dataclasses import dataclass

from terramon.domain.insight import Insight


@dataclass
class ProximityEvent:
    """Signal that a newly summoned creature is near another creature.

    Attributes:
        agent_name: The summoned creature's agent name.
        other_agent_name: The nearby creature's agent name.
        other_agent_pubkey: The Nostr pubkey of the nearby creature's owner
            (empty string if from local memory).
        lat: Latitude of the proximity location.
        lon: Longitude of the proximity location.
        distance_km: Distance between the two creatures in kilometres.
        timestamp: When the summon occurred (ISO string).
        other_archetype: Archetype of the nearby creature (if available).
        other_rarity: Rarity of the nearby creature.
        other_insight: Insight of the nearby creature (if available).
        bond_bonus_applied: Whether a bond level bonus was already applied.
        is_cross_player: True if the nearby creature is from another player
            (discovered via Nostr relay). False if local memory.
    """

    agent_name: str
    other_agent_name: str
    other_agent_pubkey: str = ""
    lat: float = 0.0
    lon: float = 0.0
    distance_km: float = 0.0
    timestamp: str = ""
    other_archetype: str = ""
    other_rarity: str = "common"
    other_insight: "Insight | None" = None
    bond_bonus_applied: bool = False
    is_cross_player: bool = False
