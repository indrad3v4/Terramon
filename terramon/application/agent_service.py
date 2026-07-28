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

    # ── Bond persistence helpers ───────────────────────────────────────

    def bond_data_from_agent(self, agent: CreatureAgent) -> dict:
        """Extract bond fields from a CreatureAgent as a dict for persistence."""
        return {
            "bond_level": agent.bond_level,
            "player_affinity": agent.player_affinity,
            "milestone_memory": agent.milestone_memory,
            "player_journal": agent.player_journal,
            "interaction_count": agent.interaction_count,
            "last_interaction_type": agent.last_interaction_type,
        }

    def apply_bond_data(self, agent: CreatureAgent, bond_data: dict) -> None:
        """Apply persisted bond data onto an existing CreatureAgent (in-place)."""
        if not bond_data:
            return
        agent.bond_level = bond_data.get("bond_level", agent.bond_level)
        raw = bond_data.get("player_affinity")
        if raw:
            agent.player_affinity = list(raw) if isinstance(raw, list) else agent.player_affinity
        raw = bond_data.get("milestone_memory")
        if raw:
            agent.milestone_memory = list(raw) if isinstance(raw, list) else agent.milestone_memory
        agent.player_journal = bond_data.get("player_journal", agent.player_journal)
        agent.interaction_count = bond_data.get("interaction_count", agent.interaction_count)
        agent.last_interaction_type = bond_data.get("last_interaction_type", agent.last_interaction_type)

    def save_agent_bond(self, agent: CreatureAgent) -> None:
        """Persist bond data for a CreatureAgent to JsonMemory."""
        bond_data = self.bond_data_from_agent(agent)
        self._memory.save_bond(agent.agent_id, bond_data)

    def make_agent_with_bond(self, agent_id: str, **kwargs) -> CreatureAgent:
        """Create a CreatureAgent and populate it with persisted bond data.

        Usage:
            agent = _AGENT_SVC.make_agent_with_bond(
                self.agent,
                archetype=self.agent,
                hunger=self.agent_hunger,
                ...
            )
        """
        bond_data = self._memory.load_bond(agent_id)
        agent = CreatureAgent(agent_id=agent_id, **kwargs)
        self.apply_bond_data(agent, bond_data)

        # If bond data has a higher interaction_count (from persisted state),
        # use it. Otherwise the freshly created agent starts at 0 which is wrong.
        if bond_data:
            agent.bond_level = bond_data.get("bond_level", 0)
        return agent

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
            # Phase 6: state machine, mood, and history summary
            "state": agent.state.value if hasattr(agent, 'state') else "happy",
            "mood": agent.mood if hasattr(agent, 'mood') else "content",
            "state_history_count": len(agent.state_history) if hasattr(agent, 'state_history') else 0,
            # Lens #65/#75: Story machine & avatar agency
            "journey_phase": agent.journey_phase if hasattr(agent, 'journey_phase') else "call",
            "bond_level": agent.bond_level if hasattr(agent, 'bond_level') else 0,
            "player_affinity": agent.player_affinity if hasattr(agent, 'player_affinity') else [],
            # Lens #84: Shared memories
            "milestone_memory_count": len(agent.milestone_memory) if hasattr(agent, 'milestone_memory') else 0,
            "milestone_memory": agent.milestone_memory[-3:] if hasattr(agent, 'milestone_memory') and agent.milestone_memory else [],
            # Lens #85: Player expression
            "player_journal": agent.player_journal if hasattr(agent, 'player_journal') else "",
            # Lens #73: Grace / absence
            "ticks_without_interaction": agent.ticks_without_interaction if hasattr(agent, 'ticks_without_interaction') else 0,
            # Lens #86: Community sharing
            "share_code": agent.share_code if hasattr(agent, 'share_code') else "",
        }
