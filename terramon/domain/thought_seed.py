"""A thought seed is the first persistent record of a summoned agent."""

from dataclasses import dataclass


@dataclass
class ThoughtSeed:
    """Raw player input routed to an agent and stored as memory."""

    raw_input: str
    summoned_agent: str
    timestamp: str
    status: str = "summoned"
