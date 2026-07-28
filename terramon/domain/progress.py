"""Player progression — the missing 'visible progress' the roast flagged.

Build-via-learn: Chip Huyen eval-driven loop. This domain object is the STATE
the game loop mutates each turn, so progress is visible (roast Lens #49) and a
goal exists (Lens #25). Pure, no I/O — lives in domain/ like ThoughtSeed.

Failure modes this closes (roast):
- #25 Goals: `goal_distinct` gives a concrete win condition.
- #49 Visible Progress: level/xp/collection change every turn.
- #40 Reward: xp is tiered by rarity, so a rare summon FEELS bigger.

Convex analysis of XP curve (Phase 1 / Convex Optimization):
  Current: XP_PER_LEVEL = 100 (constant). Level = xp // 100 + 1.
  This is a LINEAR curve — each level requires the same absolute effort.
  
  Properties:
  - f(xp) = xp/100 + 1 is affine (linear + constant) → convex and concave
  - Marginal cost per level: constant at 100 XP
  - Scoping: For MAX_LEVEL = 50, total XP = 49 * 100 = 4900 XP.
    At max reward (LEGENDARY = 150 XP), that's ~33 legendary summons.
    At COMMON (10 XP), that's 490 summons. Reasonable for casual play.
  
  Recommendation: LINEAR is appropriate for this game's scope. It's
  transparent (players easily compute "2 more summons = next level")
  and avoids the "grind wall" of exponential curves. If progression
  feels too fast, an XP-per-level that grows as floor(N * 100 * 1.1^(N-1))
  would give gentle convex escalation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from terramon.domain.rarity import Rarity
from terramon.application.math_utils import xp_to_level, level_to_xp

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
        """Level derived from total XP (1-indexed). Uses math_utils for consistency."""
        return xp_to_level(self.xp, XP_PER_LEVEL)

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
