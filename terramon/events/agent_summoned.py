"""Event emitted when an agent is summoned from a thought seed."""

from dataclasses import dataclass


@dataclass
class AgentSummoned:
    """Signal that an intent was routed to a specific agent."""

    thought_seed: str
    agent_name: str
    timestamp: str
