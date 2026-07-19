"""A thought seed is the first persistent record of a summoned agent."""

from dataclasses import dataclass

from terramon.domain.insight import Insight
from terramon.domain.rarity import Rarity


@dataclass
class ThoughtSeed:
    """Raw player input routed to an agent and stored as memory."""

    raw_input: str
    summoned_agent: str
    timestamp: str
    status: str = "summoned"
    rarity: str = "common"
    price_sats: int = 0
    paid: bool = False
    # The INSIGHT (DRIVER + BARRIER -> THEREFORE) that actually drives the
    # agent. Optional for backward compatibility with seeds persisted before
    # FIX 2 — old records deserialise with insight=None.
    insight: Insight | None = None

    @classmethod
    def make(
        cls,
        raw_input: str,
        summoned_agent: str,
        timestamp: str,
        rarity: Rarity = Rarity.COMMON,
        price_sats: int = 0,
        paid: bool = False,
        insight: Insight | None = None,
    ) -> "ThoughtSeed":
        return cls(
            raw_input=raw_input,
            summoned_agent=summoned_agent,
            timestamp=timestamp,
            rarity=rarity.value,
            price_sats=price_sats,
            paid=paid,
            insight=insight,
        )
