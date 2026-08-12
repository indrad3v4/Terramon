"""A thought seed is the first persistent record of a summoned agent."""

from dataclasses import dataclass

from terramon.domain.insight import Insight, GeoContext
from terramon.domain.rarity import Rarity


@dataclass
class ThoughtSeed:
    """Raw player input routed to an agent and stored as memory.

    v2: every creature carries its geo-coordinates (where on Earth it was
    born) and its unique embedding nuance — 7+ billion people with thousands
    of thoughts each cannot be squeezed into 5 reductive buckets. Every
    summon is a unique point in the embedding space, anchored to a real place.
    """

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
    # v2: geographic anchor — where on Earth this thought was born.
    # When the player captures a photo (Kraków, etc.), the creature lives
    # at that real place. Terra = actual planet Earth.
    lat: float = 0.0
    lon: float = 0.0
    place_name: str = ""  # e.g. "Kraków, Poland"

    # I03: Embedding drift tracking — the first summon's embedding is stored
    # as birth_embedding so we can measure how much the creature has evolved
    # over time via cosine distance between birth and current embeddings.
    birth_embedding: dict[int, float] | None = None

    # Candle ritual: the creature's new line written after the player lights
    # a 500-sat WebLN candle at its birthplace. Persisted on the seed so the
    # memorial survives reloads. Empty string = candle never lit.
    candle_lore: str = ""

    # Release ritual (Lens #97 depth win): the player's goodbye at release —
    # persisted on the seed so /health complete_releases can count it.
    # Empty string = never released with words.
    final_words: str = ""

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
        lat: float = 0.0,
        lon: float = 0.0,
        place_name: str = "",
        birth_embedding: dict[int, float] | None = None,
        final_words: str = "",
    ) -> "ThoughtSeed":
        return cls(
            raw_input=raw_input,
            summoned_agent=summoned_agent,
            timestamp=timestamp,
            rarity=rarity.value,
            price_sats=price_sats,
            paid=paid,
            insight=insight,
            lat=lat,
            lon=lon,
            place_name=place_name,
            birth_embedding=birth_embedding,
            final_words=final_words,
        )
