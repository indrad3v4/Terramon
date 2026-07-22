"""Agent Service — connects CreatureAgent to the TMA and persistence.

Manages creature lifecycle: creation (from summon), tick (stat decay),
interactions (feed/play/rest/talk/evolve), and persistence.
"""

from __future__ import annotations

import hashlib
import time
from typing import Optional

from terramon.domain.creature_agent import (
    CreatureAgent, AgentMessage,
    MAX_HUNGER, MAX_ENERGY, MAX_HAPPINESS,
)
from terramon.domain.insight import Insight, GeoContext
from terramon.adapters.json_memory import JsonMemory


class AgentService:
    """Service layer for creature agent operations."""

    def __init__(self, memory: JsonMemory):
        self._memory = memory

    def create_agent(self, raw_input: str, archetype: str,
                     insight: Optional[Insight] = None,
                     geo: Optional[GeoContext] = None) -> CreatureAgent:
        """Create a new creature agent from a summon."""
        # Generate unique ID from timestamp + input hash
        raw_hash = hashlib.blake2b(
            (raw_input + str(time.time())).encode(), digest_size=4
        ).hexdigest()
        agent_id = f"CR{archetype[:2].upper()}-{raw_hash[:6]}"

        agent = CreatureAgent(
            agent_id=agent_id,
            name=f"{archetype} #{raw_hash[:4]}",
            archetype=archetype,
            insight=insight,
            lat=geo.lat if geo else 0.0,
            lon=geo.lon if geo else 0.0,
            place_name=geo.place_name if geo else "",
        )
        return agent

    def feed(self, agent: CreatureAgent) -> AgentMessage:
        return agent.feed()

    def play(self, agent: CreatureAgent) -> AgentMessage:
        return agent.play()

    def rest(self, agent: CreatureAgent) -> AgentMessage:
        return agent.rest()

    def talk(self, agent: CreatureAgent) -> AgentMessage:
        return agent.talk()

    def tick(self, agent: CreatureAgent) -> Optional[AgentMessage]:
        return agent.tick()

    def evolve(self, agent: CreatureAgent) -> AgentMessage:
        return agent.evolve()

    def to_dict(self, agent: CreatureAgent) -> dict:
        """Serialize agent to dict for UI transmission."""
        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "archetype": agent.archetype,
            "level": agent.level,
            "xp": agent.xp,
            "xp_into_level": agent.xp_into_level,
            "hunger": agent.hunger,
            "energy": agent.energy,
            "happiness": agent.happiness,
            "evolution_stage": agent.evolution_stage,
            "can_evolve": agent.can_evolve,
            "interaction_count": agent.interaction_count,
            "last_interaction_type": agent.last_interaction_type,
            "last_message": agent.last_message,
            "place_name": agent.place_name,
            "lat": agent.lat,
            "lon": agent.lon,
            "insight_driver": agent.insight.driver if agent.insight else "",
            "insight_barrier": agent.insight.barrier if agent.insight else "",
            "insight_therefore": agent.insight.therefore if agent.insight else "",
            "insight_archetype": agent.insight.archetype if agent.insight else "",
            "insight_confidence": agent.insight.confidence if agent.insight else 0,
        }
