"""A thought seed is the first persistent record of a summoned agent."""

from dataclasses import dataclass

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

    @classmethod
    def make(
        cls,
        raw_input: str,
        summoned_agent: str,
        timestamp: str,
        rarity: Rarity = Rarity.COMMON,
        price_sats: int = 0,
        paid: bool = False,
    ) -> "ThoughtSeed":
        return cls(
            raw_input=raw_input,
            summoned_agent=summoned_agent,
            timestamp=timestamp,
            rarity=rarity.value,
            price_sats=price_sats,
            paid=paid,
        )
