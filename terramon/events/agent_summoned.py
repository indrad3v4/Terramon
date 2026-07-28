"""Event emitted when an agent is summoned from a thought seed."""

from __future__ import annotations

from dataclasses import dataclass, field


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
    """

    thought_seed: str
    agent_name: str
    timestamp: str
    safety_flagged: bool = False
    safety_reason: str = ""
