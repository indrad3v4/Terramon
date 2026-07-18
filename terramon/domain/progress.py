"""Player progression — the missing 'visible progress' the roast flagged.

Build-via-learn: Chip Huyen eval-driven loop. This domain object is the STATE
the game loop mutates each turn, so progress is visible (roast Lens #49) and a
goal exists (Lens #25). Pure, no I/O — lives in domain/ like ThoughtSeed.

Failure modes this closes (roast):
- #25 Goals: `goal_distinct` gives a concrete win condition.
- #49 Visible Progress: level/xp/collection change every turn.
- #40 Reward: xp is tiered by rarity, so a rare summon FEELS bigger.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from terramon.domain.rarity import Rarity

# XP granted per rarity tier — reward scales with rarity (Lens #40).
XP_BY_RARITY = {
    Rarity.COMMON: 10,
    Rarity.UNCOMMON: 25,
    Rarity.RARE: 60,
    Rarity.LEGENDARY: 150,
}

# XP needed to reach the next level (simple escalating curve).
XP_PER_LEVEL = 100


@dataclass
class PlayerProgress:
    """Mutable player state the loop advances each turn."""

    xp: int = 0
    collection: set[str] = field(default_factory=set)
    goal_distinct: int = 3  # win when you collect this many distinct creatures

    @property
    def level(self) -> int:
        """Level derived from total XP (1-indexed)."""
        return self.xp // XP_PER_LEVEL + 1

    @property
    def xp_into_level(self) -> int:
        """XP progress within the current level (for a progress bar)."""
        return self.xp % XP_PER_LEVEL

    @property
    def distinct_count(self) -> int:
        return len(self.collection)

    @property
    def goal_reached(self) -> bool:
        return self.distinct_count >= self.goal_distinct

    def award(self, creature: str, rarity: Rarity) -> int:
        """Add a creature + its XP. Returns XP gained this turn."""
        gained = XP_BY_RARITY[rarity]
        self.xp += gained
        self.collection.add(creature)
        return gained
