"""Rarity — what makes a summoned creature cost sats.

Build-via-learn: Phase 11 (LLM Engineering) advanced RAG / guardrails framing
reused here as an economy gate. A creature's rarity is derived from the nature
of the thought seed (specific patterns -> legendary), per ROADMAP_2027 Day 59.

Keep this pure (no I/O) so it stays in `domain/` like ThoughtSeed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Rarity(str, Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    LEGENDARY = "legendary"


# Sats price per rarity tier (free tier = first 5 summons/day, per roadmap).
RARITY_PRICE_SATS = {
    Rarity.COMMON: 0,
    Rarity.UNCOMMON: 0,
    Rarity.RARE: 1000,
    Rarity.LEGENDARY: 5000,
}

# Thought patterns that upgrade a summon to a paid tier (Day 59 mechanic).
_LEGENDARY_PATTERNS = ("i am the", "command the", "ascend", "i surrender")
_RARE_PATTERNS = ("rare", "lost", "alone", "shadow", "break", "truth")


@dataclass
class RarityResult:
    rarity: Rarity
    price_sats: int


def classify_rarity(thought_seed: str) -> RarityResult:
    """Map a thought seed to a rarity tier and its sats price."""
    lowered = thought_seed.lower()
    if any(p in lowered for p in _LEGENDARY_PATTERNS):
        rarity = Rarity.LEGENDARY
    elif any(p in lowered for p in _RARE_PATTERNS):
        rarity = Rarity.RARE
    else:
        rarity = Rarity.COMMON
    return RarityResult(rarity=rarity, price_sats=RARITY_PRICE_SATS[rarity])
