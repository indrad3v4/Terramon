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

# LENS #17: Progressive goal tiers — infinite horizon.
# Tamer (5) → Master (12) → Legend (36 = 12×3 continents).
# Each tier unlocks a new game feature.
# Post-goal shows next tier requirements, not a dead end.
GOAL_TIERS = [
    {"name": "Tamer",  "distinct": 5,  "badge": "★",   "unlock": "Scout"},
    {"name": "Master", "distinct": 12, "badge": "★★",  "unlock": "Map"},
    {"name": "Legend", "distinct": 36, "badge": "★★★", "unlock": "Squad"},
]


# LENS #4: Cross-creature resonance pairs — owning both archetypes
# unlocks a bonus insight and deepens the terra story.
# Format: (archetype_a, archetype_b) -> resonance message
CREATURE_RESONANCES = [
    ("Hero", "Rebel", "The Rebel questions every path the Hero calls 'right'. They sharpen each other."),
    ("Sage", "Jester", "The Sage seeks truth; the Jester finds it in laughter. Together they see everything."),
    ("Creator", "Magician", "The Creator builds the stage. The Magician makes the audience gasp."),
    ("Lover", "Caregiver", "The Lover feels deeply. The Caregiver acts on that feeling. An unbreakable pair."),
    ("Explorer", "Innocent", "The Explorer goes where no one has gone. The Innocent sees it all anew."),
    ("Ruler", "Orphan", "The Ruler builds order from chaos. The Orphan remembers what chaos feels like."),
    ("Innocent", "Rebel", "The Innocent trusts. The Rebel asks why. Together they find a better way."),
    ("Sage", "Orphan", "The Sage knows. The Orphan understands. Wisdom and pain are old friends."),
]


def check_resonances(collection: set[str]) -> list[str]:
    """LENS #4: Return resonance messages unlocked by the player's current collection."""
    found = []
    for a, b, msg in CREATURE_RESONANCES:
        if a in collection and b in collection:
            found.append(f"✦ {a} + {b}: {msg}")
    return found


# ---------------------------------------------------------------------------
# I04: Squad system — up to 3 creatures, cross-creature resonances
# ---------------------------------------------------------------------------

# LENS #4: Squad resonance pairs — when both archetypes are in the active squad,
# each affected stat gets +5 bonus.
# Format: (archetype_a, archetype_b, stat_bonuses)
# Each pair grants +5 to relevant stats.
SQUAD_RESONANCES = [
    ("Hero", "Rebel", {"energy": 5}),
    ("Sage", "Jester", {"happiness": 5}),
    ("Lover", "Caregiver", {"hunger": 5}),
    ("Explorer", "Innocent", {"happiness": 5}),
    ("Creator", "Magician", {"energy": 5}),
    ("Orphan", "Ruler", {"hunger": 5}),
    ("Hero", "Lover", {"happiness": 5}),
    ("Explorer", "Rebel", {"energy": 5}),
]


@dataclass
class SquadSlot:
    """One creature slot in a squad."""
    agent_id: str
    archetype: str
    name: str = ""


@dataclass
class Squad:
    """A player's active squad of up to 3 creatures.

    Squad members have cross-creature resonances that grant passive
    stat bonuses when certain archetype pairs are both present.
    """

    slots: list[SquadSlot] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.slots)

    @property
    def full(self) -> bool:
        return len(self.slots) >= 3

    @property
    def archetypes(self) -> set[str]:
        return {s.archetype for s in self.slots}

    def add(self, slot: SquadSlot) -> bool:
        """Add a creature to the squad. Returns False if squad is full or duplicate."""
        if self.full:
            return False
        if any(s.agent_id == slot.agent_id for s in self.slots):
            return False
        self.slots.append(slot)
        return True

    def remove(self, agent_id: str) -> bool:
        """Remove a creature from the squad by agent_id."""
        for i, s in enumerate(self.slots):
            if s.agent_id == agent_id:
                self.slots.pop(i)
                return True
        return False

    def clear(self) -> None:
        self.slots.clear()

    def contains_archetype(self, archetype: str) -> bool:
        return archetype in self.archetypes

    def active_resonances(self) -> list[tuple[str, str, dict[str, int]]]:
        """Return all active resonance pairs with their stat bonuses."""
        active = []
        archetypes = self.archetypes
        for a, b, bonuses in SQUAD_RESONANCES:
            if a in archetypes and b in archetypes:
                active.append((a, b, bonuses))
        return active

    def total_stat_bonus(self) -> dict[str, int]:
        """Aggregate all active resonance stat bonuses."""
        bonus = {"hunger": 0, "energy": 0, "happiness": 0}
        for _a, _b, bns in self.active_resonances():
            for stat, val in bns.items():
                bonus[stat] = bonus.get(stat, 0) + val
        return bonus


@dataclass
class PlayerProgress:
    """Mutable player state the loop advances each turn.

    LENS #17: Progressive goal tiers — infinite horizon.
    Tamer (5) → Master (12) → Legend (36). Each tier unlocks a feature.
    After reaching one tier, the player pushes toward the next.
    Post-goal shows next tier requirements, not a dead end.

    LENS #68: journey_phase tracks the Hero's Journey arc — the player
    advances through call → threshold → transformation → return as their
    collection grows, unlocking narrative rewards at each stage.
    """

    xp: int = 0
    collection: set[str] = field(default_factory=set)
    goal_distinct: int = 5  # default — matches first tier (Tamer)
    goal_tier_index: int = 0  # LENS #17: current tier index in GOAL_TIERS
    journey_phase: str = "call"  # LENS #68: call | threshold | transformation | return
    # Last reached tier info (for celebration display — cleared on dismiss)
    last_reached_tier_name: str = ""
    last_reached_tier_badge: str = ""
    last_reached_tier_unlock: str = ""

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
    def current_tier_name(self) -> str:
        """LENS #17: Name of the highest tier the player has reached."""
        if self.goal_tier_index >= len(GOAL_TIERS):
            return GOAL_TIERS[-1]["name"]
        return GOAL_TIERS[self.goal_tier_index]["name"]

    @property
    def current_tier_badge(self) -> str:
        """LENS #17: Badge emoji for the current tier."""
        if self.goal_tier_index >= len(GOAL_TIERS):
            return GOAL_TIERS[-1]["badge"]
        return GOAL_TIERS[self.goal_tier_index]["badge"]

    @property
    def tier_unlock(self) -> str:
        """LENS #17: Feature unlocked by the current tier."""
        if self.goal_tier_index >= len(GOAL_TIERS):
            return "—"
        return GOAL_TIERS[self.goal_tier_index].get("unlock", "")

    @property
    def next_tier_name(self) -> str:
        """Name of the next tier, or empty string if all tiers complete."""
        next_idx = self.goal_tier_index + 1
        if next_idx >= len(GOAL_TIERS):
            return ""
        return GOAL_TIERS[next_idx]["name"]

    @property
    def next_tier_requirement(self) -> int:
        """Distinct requirement for the next tier, or current goal if max."""
        next_idx = self.goal_tier_index + 1
        if next_idx >= len(GOAL_TIERS):
            return self.goal_distinct
        return GOAL_TIERS[next_idx]["distinct"]

    @property
    def next_tier_unlock(self) -> str:
        """Feature unlocked by the next tier."""
        next_idx = self.goal_tier_index + 1
        if next_idx >= len(GOAL_TIERS):
            return ""
        return GOAL_TIERS[next_idx].get("unlock", "")

    @property
    def goal_reached(self) -> bool:
        """LENS #17: True if current tier's distinct threshold is met.
        Advances to next tier automatically. At max tier (Legend), stays
        there and still returns True — infinite horizon, not a dead end.
        LENS #68: Also advances journey_phase on milestone tiers."""
        if self.goal_tier_index >= len(GOAL_TIERS):
            return True  # Beyond max — all tiers complete
        current_goal = GOAL_TIERS[self.goal_tier_index]["distinct"]
        if self.distinct_count >= current_goal:
            tier = GOAL_TIERS[self.goal_tier_index]
            self.last_reached_tier_name = tier["name"]
            self.last_reached_tier_badge = tier["badge"]
            self.last_reached_tier_unlock = tier.get("unlock", "")
            if self.goal_tier_index < len(GOAL_TIERS) - 1:
                # Advance to next tier
                self.goal_tier_index += 1
                self.goal_distinct = GOAL_TIERS[self.goal_tier_index]["distinct"]
                # LENS #68: Journey phase advances at milestone tiers
                self._update_journey_phase()
                return True
            # At max tier (Legend) — goal reached, stay here
            return True
        return False

    def recalculate_tier(self) -> None:
        """Sync tier state with current collection (used after replaying awards
        in load_terra). Finds the highest tier the player qualifies for without
        triggering goal_reached side-effects."""
        idx = 0
        for i, tier in enumerate(GOAL_TIERS):
            if self.distinct_count >= tier["distinct"]:
                idx = i
            else:
                break
        self.goal_tier_index = idx
        self.goal_distinct = GOAL_TIERS[idx]["distinct"]
        if idx == len(GOAL_TIERS) - 1 and self.distinct_count >= GOAL_TIERS[idx]["distinct"]:
            self.last_reached_tier_name = GOAL_TIERS[idx]["name"]
            self.last_reached_tier_badge = GOAL_TIERS[idx]["badge"]
            self.last_reached_tier_unlock = GOAL_TIERS[idx].get("unlock", "")

    def _update_journey_phase(self) -> None:
        """LENS #68: Advance journey phase based on collection size.

        call (0-2 distinct) → threshold (3-5) → transformation (6-11) → return (12+)
        Mirrors the creature's _update_journey_phase but uses collection
        progression instead of creature level.
        """
        if self.distinct_count >= 12:
            self.journey_phase = "return"
        elif self.distinct_count >= 6:
            self.journey_phase = "transformation"
        elif self.distinct_count >= 3:
            self.journey_phase = "threshold"

    def award(self, creature: str, rarity: Rarity) -> int:
        """Add a creature + its XP. Returns XP gained this turn."""
        gained = XP_BY_RARITY[rarity]
        self.xp += gained
        self.collection.add(creature)
        return gained
