"""Event emitted when a creature is released into the wild.

A tamed creature that has reached evolution_stage ≥ 2 can be released
by its owner. The creature becomes wild — visible to all players on the
global map — and the original player receives a '★ Wild Tamer' badge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from terramon.domain.insight import Insight


@dataclass
class CreatureReleased:
    """Signal that a creature was released into the wild.

    Attributes:
        agent_id: Unique ID of the released creature.
        agent_name: The creature's display name.
        archetype: The archetype of the released creature.
        thought_seed: The original thought seed that summoned the creature.
        lat: Latitude of the creature's birthplace / release location.
        lon: Longitude of the creature's birthplace / release location.
        place_name: Human-readable place name.
        evolution_stage: The creature's evolution stage at release.
        level: The creature's level at release.
        rarity: The creature's rarity tier.
        release_timestamp: When the release occurred (ISO string).
        insight: The creature's Insight at the moment of release.
        previous_owner: The player ID who released the creature.
    """

    agent_id: str
    agent_name: str
    archetype: str = ""
    thought_seed: str = ""
    lat: float = 0.0
    lon: float = 0.0
    place_name: str = ""
    evolution_stage: int = 0
    level: int = 1
    rarity: str = "common"
    release_timestamp: str = ""
    insight: Optional[Insight] = None
    previous_owner: str = ""
