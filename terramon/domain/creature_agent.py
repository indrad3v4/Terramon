"""Creature Agent — Tamagotchi × Pokemon AI agent that lives in the player's terra.

Every summoned creature is an AI agent with:
- Stats: hunger, energy, happiness, xp, level
- Needs: decays over time (tick), requires player interaction
- Behavior: autonomous messages based on archetype + insight + history
- Evolution: transforms when conditions met
- Memory: remembers past interactions and evolves its responses

This is what the enduser operates — like a tamagotchi they care for
and a pokemon they grow. The creature is a REAL AI AGENT, not a label.

v2 (July 2026): replaces the 5-theme reduction with a rich continuous
embedding + archetype soft-reference system. 7+ billion people deserve
agents that capture their unique thought patterns, not 5 buckets.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

from terramon.domain.insight import Insight


# ---------------------------------------------------------------------------
# Stat ranges and limits
# ---------------------------------------------------------------------------

MAX_HUNGER = 100      # full
MAX_ENERGY = 100      # rested
MAX_HAPPINESS = 100   # delighted
MAX_XP_PER_LEVEL = 100
MAX_LEVEL = 50

# Tick decay rates (per tick)
DECAY_HUNGER = 5      # gets hungrier
DECAY_ENERGY = 3      # gets tired
DECAY_HAPPINESS = 2   # gets bored (slower)

# Interaction deltas
FEED_HUNGER = +25
FEED_ENERGY = +5
FEED_XP = +3

PLAY_ENERGY = -15
PLAY_HAPPINESS = +20
PLAY_XP = +5

REST_ENERGY = +40
REST_HUNGER = +3      # resting makes you a bit hungry

TALK_HAPPINESS = +5
TALK_XP = +2


@dataclass
class AgentMessage:
    """A message from the creature to the player."""
    text: str
    message_type: str = "ambient"  # ambient | need | evolution | response
    urgency: int = 0  # 0-10; 10 = critical (starving, exhausted)


@dataclass
class EvolutionRequirement:
    """Conditions required for evolution."""
    min_level: int = 10
    min_happiness: int = 70
    min_xp_total: int = 500
    insight_diversity: int = 3  # number of different archetypes experienced


@dataclass
class CreatureAgent:
    """A living AI agent in the player's terra.

    Each creature has needs that decay, stats that grow, and a unique
    behavioral profile shaped by its archetype + insight + geography.
    """

    # Identity (immutable after summon)
    agent_id: str  # unique ID (UUID or timestamp hash)
    name: str = ""  # auto-generated from archetype + timestamp
    archetype: str = "Scout"
    insight: Optional[Insight] = None

    # Geography (where on Earth this creature was born)
    lat: float = 0.0
    lon: float = 0.0
    place_name: str = ""

    # Stats
    level: int = 1
    xp: int = 0
    hunger: int = 80     # starts a bit hungry (more realistic)
    energy: int = 80
    happiness: int = 60  # starts content
    evolution_stage: int = 0  # 0=basic, 1=evolved, 2=final
    evolution_probability: float = 0.0  # Lesson 06: logistic P(evolve) — 0.0 to 1.0

    # History
    interaction_count: int = 0
    total_xp_earned: int = 0
    last_interaction_type: str = ""
    last_message: str = ""
    message_history: list[str] = field(default_factory=list)

    # Needs for evolution
    evolution_requirement: EvolutionRequirement = field(
        default_factory=EvolutionRequirement
    )

    @property
    def xp_into_level(self) -> int:
        return self.xp % MAX_XP_PER_LEVEL

    @property
    def can_evolve(self) -> bool:
        """Logistic probability of evolution (smooth, not cliff)."""
        # Sigmoid centered at min_level with temperature = 3
        import math as _m
        level_z = (self.level - self.evolution_requirement.min_level) / 3.0
        happiness_z = (self.happiness - self.evolution_requirement.min_happiness) / 10.0
        xp_z = (self.total_xp_earned - self.evolution_requirement.min_xp_total) / 200.0
        # Combined logistic: P(evolve) = sigmoid(level_contrib + happiness_contrib + xp_contrib)
        z = level_z + happiness_z + xp_z
        self.evolution_probability = round(1.0 / (1.0 + _m.exp(-z)), 4)
        return self.evolution_probability > 0.5 and self.evolution_stage < 2

    # -- Interaction methods --

    def feed(self) -> AgentMessage:
        """Feed the creature — increases hunger, small XP."""
        self.hunger = min(MAX_HUNGER, self.hunger + FEED_HUNGER)
        self.energy = min(MAX_ENERGY, self.energy + FEED_ENERGY)
        self._award_xp(FEED_XP)
        self.last_interaction_type = "feed"
        self.interaction_count += 1
        texts = [
            "Munch munch... that hit the spot.",
            "You offer a thought-nugget. The creature accepts gratefully.",
            "It nibbles slowly, savouring the moment.",
            f"'{self._archetype_verb()}.' It feeds on your attention.",
        ]
        return self._make_message(random.choice(texts), "response", 3)

    def play(self) -> AgentMessage:
        """Play with the creature — increases happiness, costs energy."""
        if self.energy < 20:
            return self._make_message(
                f"Too tired to play. It curls up and sighs.",
                "response", 7
            )
        self.happiness = min(MAX_HAPPINESS, self.happiness + PLAY_HAPPINESS)
        self.energy = max(0, self.energy + PLAY_ENERGY)
        self._award_xp(PLAY_XP)
        self.last_interaction_type = "play"
        self.interaction_count += 1
        texts = [
            "It darts around you in excited circles!",
            "A game of chase. You lose. It laughs without sound.",
            f"It {self._archetype_verb()} playfully, inviting you to follow.",
            "For a moment, the thought that birthed it feels light again.",
        ]
        return self._make_message(random.choice(texts), "response", 3)

    def rest(self) -> AgentMessage:
        """Let the creature rest — restores energy."""
        self.energy = min(MAX_ENERGY, self.energy + REST_ENERGY)
        self.hunger = max(0, self.hunger - REST_HUNGER)  # rest burns hunger
        self.last_interaction_type = "rest"
        self.interaction_count += 1
        texts = [
            "It settles into a warm glow and closes its eyes.",
            "Soft hum. Slow pulse. The creature dreams.",
            f"It rests near you. You feel its {self._archetype_feeling()}.",
            "Stillness. The terra breathes with you.",
        ]
        return self._make_message(random.choice(texts), "response", 2)

    def talk(self) -> AgentMessage:
        """Talk to the creature — it responds based on its insight."""
        self.happiness = min(MAX_HAPPINESS, self.happiness + TALK_HAPPINESS)
        self._award_xp(TALK_XP)
        self.last_interaction_type = "talk"
        self.interaction_count += 1

        if self.insight and self.insight.therefore:
            return self._make_message(
                self.insight.therefore,
                "response", 1
            )
        return self._make_message(
            f"It listens. The quiet between you says enough.",
            "response", 1
        )

    def tick(self) -> Optional[AgentMessage]:
        """One time tick — stats decay. Returns a message if something urgent.

        Call this periodically (e.g., every hour in real time, or
        every few interactions in game time).
        """
        self.hunger = max(0, self.hunger - DECAY_HUNGER)
        self.energy = max(0, self.energy - DECAY_ENERGY)
        self.happiness = max(0, self.happiness - DECAY_HAPPINESS)

        # Check for urgent needs
        if self.hunger < 20:
            return self._make_message(
                "A soft rumble. It's hungry. Feed me?",
                "need", 8
            )
        if self.energy < 20:
            return self._make_message(
                "Its glow is dim. So tired... let me rest.",
                "need", 7
            )
        if self.happiness < 20:
            return self._make_message(
                "It looks at you with quiet longing.",
                "need", 6
            )

        # Random ambient message (10% chance)
        if random.random() < 0.1:
            ambients = [
                f"It gazes at the {self._random_terrain()}.",
                f"A soft {self._archetype_sound()} echoes.",
                f"It traces patterns in the air with its {self._archetype_feeling()}.",
                f"'{self._archetype_verb()}.' It says to itself.",
                f"The creature hums. The terra hums back.",
            ]
            return self._make_message(random.choice(ambients), "ambient", 1)

        return None

    def evolve(self) -> AgentMessage:
        """Trigger evolution if conditions are met."""
        if not self.can_evolve:
            return self._make_message(
                "Not ready yet. More growth needed.",
                "response", 2
            )
        self.evolution_stage += 1
        self.level += 3  # bonus levels on evolution
        self.happiness = MAX_HAPPINESS  # evolution is exciting!
        self.energy = MAX_ENERGY

        evolution_names = ["Evolved", "Transcended"]
        stage_name = evolution_names[min(self.evolution_stage - 1, 1)]

        return self._make_message(
            f"✦ {stage_name}! It shimmers and transforms. "
            f"A deeper knowing fills its eyes.",
            "evolution", 10
        )

    # -- Internal --

    def _award_xp(self, amount: int) -> None:
        self.xp += amount
        self.total_xp_earned += amount
        while self.xp >= MAX_XP_PER_LEVEL and self.level < MAX_LEVEL:
            self.xp -= MAX_XP_PER_LEVEL
            self.level += 1
            self.message_history.append(
                f"★ Level {self.level}! The creature grows stronger."
            )

    def _make_message(self, text: str, msg_type: str, urgency: int) -> AgentMessage:
        self.last_message = text
        self.message_history.append(text)
        return AgentMessage(text=text, message_type=msg_type, urgency=urgency)

    def _archetype_verb(self) -> str:
        verbs = {
            "Innocent": "trusts", "Orphan": "longs", "Hero": "fights",
            "Caregiver": "nurtures", "Explorer": "seeks", "Rebel": "defies",
            "Lover": "embraces", "Creator": "shapes", "Jester": "laughs",
            "Sage": "contemplates", "Magician": "transforms", "Ruler": "commands",
        }
        return verbs.get(self.archetype, "watches")

    def _archetype_feeling(self) -> str:
        feelings = {
            "Innocent": "trust", "Orphan": "longing", "Hero": "courage",
            "Caregiver": "compassion", "Explorer": "wanderlust", "Rebel": "defiance",
            "Lover": "passion", "Creator": "inspiration", "Jester": "levity",
            "Sage": "wisdom", "Magician": "wonder", "Ruler": "authority",
        }
        return feelings.get(self.archetype, "presence")

    def _archetype_sound(self) -> str:
        sounds = {
            "Innocent": "bell", "Orphan": "wind through hollow", "Hero": "war drum",
            "Caregiver": "soft hum", "Explorer": "footstep on gravel", "Rebel": "shatter",
            "Lover": "heartbeat", "Creator": "chisel on stone", "Jester": "chime",
            "Sage": "page turn", "Magician": "crystal resonance", "Ruler": "gavel",
        }
        return sounds.get(self.archetype, "breath")

    def _random_terrain(self) -> str:
        return random.choice([
            "horizon", "distant star", "memory of rain",
            "edge of the terra", "space between thoughts",
            "glowing crystal", "ancient tree",
            "place where you first summoned it",
        ])
