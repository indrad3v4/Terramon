"""Event emitted when an agent is summoned from a thought seed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from terramon.domain.insight import Insight


@dataclass
class AgentSummoned:
    """Signal that an intent was routed to a specific agent.

    Attributes:
        thought_seed: The raw input text that triggered the summon.
        agent_name: The agent identifier.
        timestamp: When the summon occurred.
        safety_flagged: Whether the thought seed contains potentially harmful
            content (set by the EventBus safety middleware).
        safety_reason: Human-readable explanation if flagged.
        # Lens #86: Community hooks — seeds for future social features
        share_code: Unique code for sharing this creature with others.
        archetype: The archetype assigned by the insight engine.
        geo_hint: Rough location hint (city/country) for the terra map.
        insight: The derived Insight (driver/barrier/therefore) that drives the agent.
        rarity: The rarity tier of the summoned creature.
    """

    thought_seed: str
    agent_name: str
    timestamp: str
    safety_flagged: bool = False
    safety_reason: str = ""
    # Lens #86: Community seeding
    share_code: str = ""
    archetype: str = ""
    geo_hint: str = ""
    insight: Optional[Insight] = None
    rarity: str = ""
