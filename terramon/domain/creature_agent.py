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

Phase 6 (Sequence Modeling): Creature state management over time — state
machine with EMA decay, state history, day/night cycle, mood, and gradient
clipping. Each tick is like one RNN time step: the creature's "hidden state"
(hunger/energy/happiness) evolves non-linearly, gated by the current state.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from terramon.domain.insight import Insight
from terramon.application.math_utils import sigmoid


# ---------------------------------------------------------------------------
# Stat ranges and limits
# ---------------------------------------------------------------------------

MAX_HUNGER = 100      # full
MAX_ENERGY = 100      # rested
MAX_HAPPINESS = 100   # delighted
MAX_XP_PER_LEVEL = 100
MAX_LEVEL = 50

# Phase 6: EMA decay factor (3% loss per tick — smooth, non-linear)
DECAY_FACTOR = 0.97

# Phase 6: Gradient clipping — max absolute stat change per tick
MAX_DELTA_PER_TICK = 15

# Phase 6: State history window for mood computation
MOOD_HISTORY_LENGTH = 10

# Tick decay rates — Phase 6 state machine (per-state additive deltas on top of EMA)
DECAY_HUNGER = 5      # legacy linear decay (kept for reference; replaced by EMA + state machine)
DECAY_ENERGY = 3
DECAY_HAPPINESS = 2

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


# ---------------------------------------------------------------------------
# Phase 6: State machine types
# ---------------------------------------------------------------------------

class CreatureState(Enum):
    """The creature's current behavioral state (like an RNN hidden state gate).

    Each state applies different decay modifiers to the EMA base decay,
    analogous to how an LSTM's forget/input gates control what information
    flows through at each time step.
    """
    HAPPY = "happy"       # All stats healthy — normal decay
    HUNGRY = "hungry"     # Hunger < 30 — accelerated hunger decay
    TIRED = "tired"       # Energy < 30 — accelerated energy decay
    EVOLVING = "evolving" # Evolution-ready — slightly boosted happiness
    SICK = "sick"         # Any stat < 10 — accelerated decay across all stats


@dataclass
class StateSnapshot:
    """One record in the creature's state_history (like an RNN hidden state trace).

    Captures the full state vector at a point in time, enabling mood computation
    (a smoothed "context vector" over recent history) and temporal analysis.
    """
    timestamp: str
    state: str
    hunger: int
    energy: int
    happiness: int
    mood: str = "content"


# ---------------------------------------------------------------------------
# Phase 6: State-specific additive decay rates (on top of EMA base)
# Each state specifies extra hunger/energy/happiness loss per tick.
# ---------------------------------------------------------------------------

STATE_DECAY = {
    CreatureState.HAPPY:     {"hunger": 0, "energy": 0, "happiness": 0},
    CreatureState.HUNGRY:    {"hunger": 3, "energy": 0, "happiness": 0},
    CreatureState.TIRED:     {"hunger": 0, "energy": 2, "happiness": 0},
    CreatureState.EVOLVING:  {"hunger": 0, "energy": 0, "happiness": -1},  # happiness bonus
    CreatureState.SICK:      {"hunger": 2, "energy": 2, "happiness": 2},
}

# Phase 6: Day/night modifiers for additive decay rates
# morning/afternoon = active phase (faster happiness decay, slower energy decay)
# evening = neutral
# night = restful (slower happiness decay, faster energy recovery)
DAY_PHASE_MOD = {
    "morning":   {"hunger": 1.0, "energy": 0.5, "happiness": 1.5},
    "afternoon": {"hunger": 1.0, "energy": 0.3, "happiness": 2.0},
    "evening":   {"hunger": 1.0, "energy": 1.0, "happiness": 1.0},
    "night":     {"hunger": 1.0, "energy": 1.5, "happiness": 0.3},
}


@dataclass
class AgentMessage:
    """A message from the creature to the player."""
    text: str
    message_type: str = "ambient"  # ambient | need | evolution | response
    urgency: int = 0  # 0-10; 10 = critical (starving, exhausted)


@dataclass
class MessageEntry:
    """A structured message entry in the creature's KV-cache memory.

    Analogous to a single (key, value) pair in a transformer's KV cache.
    Replaces raw string storage with structured, time-aware entries.
    """
    role: str = "creature"       # "creature" | "player" | "system"
    content: str = ""
    msg_type: str = "response"   # response | need | evolution | ambient | level_up
    timestamp: float = 0.0


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

    Phase 6: The tick system is now a stateless-observation model:
      - state[t] = f(state[t-1], day_phase)  (state machine)
      - stat[t] = stat[t-1] * decay_factor + state_decay  (EMA + gated additive)
      - mood[t] = g(history[-N:])  (smoothed context over recent time steps)
      - delta capped by gradient clipping
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
    message_history: list[MessageEntry] = field(default_factory=list)

    # Needs for evolution
    evolution_requirement: EvolutionRequirement = field(
        default_factory=EvolutionRequirement
    )

    # Phase 6: State machine
    state: CreatureState = CreatureState.HAPPY
    state_history: list[StateSnapshot] = field(default_factory=list)
    mood: str = "content"

    @property
    def xp_into_level(self) -> int:
        return self.xp % MAX_XP_PER_LEVEL

    @property
    def can_evolve(self) -> bool:
        """Logistic probability of evolution (smooth, not cliff)."""
        # Sigmoid centered at min_level with temperature = 3
        level_z = (self.level - self.evolution_requirement.min_level) / 3.0
        happiness_z = (self.happiness - self.evolution_requirement.min_happiness) / 10.0
        xp_z = (self.total_xp_earned - self.evolution_requirement.min_xp_total) / 200.0
        # Combined logistic: P(evolve) = sigmoid(level_contrib + happiness_contrib + xp_contrib)
        z = level_z + happiness_z + xp_z
        self.evolution_probability = round(sigmoid(z), 4)
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

    # -- Phase 6: Core tick logic --

    def tick(self, day_phase: Optional[str] = None) -> Optional[AgentMessage]:
        """Public tick — delegates to _apply_tick() for core logic.

        `_patched_tick` in llm_behavior.py replaces this at runtime to
        inject LLM-generated messages, but calls _apply_tick() directly
        so the core decay logic is shared.
        """
        return self._apply_tick(day_phase)

    def _apply_tick(self, day_phase: Optional[str] = None) -> Optional[AgentMessage]:
        """Core tick logic: state machine, EMA decay, day/night, gradient clipping, mood.

        This is the canonical implementation that both the base tick() and the
        LLM-enhanced _patched_tick() call into. Think of it as the forward pass
        of one RNN time step: hidden_state[t] = f(hidden_state[t-1], input[t]).

        Args:
            day_phase: One of "morning", "afternoon", "evening", "night".
                       Auto-detects from time_tool if None.
        """
        # Auto-detect day phase if not provided
        if day_phase is None:
            from tools.time_tool import get_day_phase
            day_phase = get_day_phase()

        # Save old values for gradient clipping
        old_hunger, old_energy, old_happiness = self.hunger, self.energy, self.happiness

        # ---------------------------------------------------------------
        # 1. EMA decay: stat(t) = stat(t-1) * decay_factor
        #    Smooth, non-linear decay that naturally decelerates at low
        #    values (3% loss is smaller in absolute terms when stat is low).
        # ---------------------------------------------------------------
        self.hunger = max(0, int(self.hunger * DECAY_FACTOR))
        self.energy = max(0, int(self.energy * DECAY_FACTOR))
        self.happiness = max(0, int(self.happiness * DECAY_FACTOR))

        # ---------------------------------------------------------------
        # 2. State-specific additive decay (gated by current CreatureState)
        #    Each state applies different extra decay on top of EMA,
        #    analogous to how LSTM gates modulate information flow.
        # ---------------------------------------------------------------
        state_decay = STATE_DECAY.get(self.state, STATE_DECAY[CreatureState.HAPPY])
        phase_mod = DAY_PHASE_MOD.get(day_phase, DAY_PHASE_MOD["afternoon"])

        hunger_delta = int(state_decay["hunger"] * phase_mod["hunger"])
        energy_delta = int(state_decay["energy"] * phase_mod["energy"])
        happiness_delta = int(state_decay["happiness"] * phase_mod["happiness"])

        self.hunger = max(0, self.hunger - hunger_delta)
        self.energy = max(0, self.energy - energy_delta)
        self.happiness = max(0, self.happiness - happiness_delta)

        # ---------------------------------------------------------------
        # 3. Gradient clipping: cap max stat change per tick at 15
        #    Prevents extreme swings from bugs or edge cases.
        # ---------------------------------------------------------------
        h_delta = old_hunger - self.hunger
        e_delta = old_energy - self.energy
        ha_delta = old_happiness - self.happiness

        if h_delta > MAX_DELTA_PER_TICK:
            self.hunger = old_hunger - MAX_DELTA_PER_TICK
        if e_delta > MAX_DELTA_PER_TICK:
            self.energy = old_energy - MAX_DELTA_PER_TICK
        if ha_delta > MAX_DELTA_PER_TICK:
            self.happiness = old_happiness - MAX_DELTA_PER_TICK

        # ---------------------------------------------------------------
        # 4. State machine transition
        # ---------------------------------------------------------------
        self.state = self._compute_state()

        # ---------------------------------------------------------------
        # 5. Mood computation from state history
        # ---------------------------------------------------------------
        self.mood = self._compute_mood()

        # ---------------------------------------------------------------
        # 6. Record state history snapshot
        # ---------------------------------------------------------------
        from tools.time_tool import get_current_time
        snapshot = StateSnapshot(
            timestamp=get_current_time(),
            state=self.state.value,
            hunger=self.hunger,
            energy=self.energy,
            happiness=self.happiness,
            mood=self.mood,
        )
        self.state_history.append(snapshot)
        # Keep last 50 entries to bound memory
        if len(self.state_history) > 50:
            self.state_history = self.state_history[-50:]

        # ---------------------------------------------------------------
        # 7. Check for urgent needs (mood-aware messages)
        # ---------------------------------------------------------------
        return self._check_urgent_needs()

    def _compute_state(self) -> CreatureState:
        """Determine current state based on stat thresholds.

        Priority: SICK > HUNGRY > TIRED > EVOLVING > HAPPY.
        """
        if any(s < 10 for s in (self.hunger, self.energy, self.happiness)):
            return CreatureState.SICK
        if self.hunger < 30:
            return CreatureState.HUNGRY
        if self.energy < 30:
            return CreatureState.TIRED
        if self.can_evolve:
            return CreatureState.EVOLVING
        if all(s > 50 for s in (self.hunger, self.energy, self.happiness)):
            return CreatureState.HAPPY
        return CreatureState.HAPPY

    def _compute_mood(self) -> str:
        """Compute mood from moving average of recent state history.

        Uses the last MOOD_HISTORY_LENGTH (10) snapshots. If fewer exist,
        uses what's available plus current stats.

        Returns: "cheerful", "content", or "distressed"
        """
        if len(self.state_history) >= 3:
            # Use last N history entries
            recent = self.state_history[-MOOD_HISTORY_LENGTH:]
            avg = sum(
                (s.hunger + s.energy + s.happiness) / 3.0
                for s in recent
            ) / len(recent)
        else:
            # Fall back to current stats
            avg = (self.hunger + self.energy + self.happiness) / 3.0

        if avg > 70:
            return "cheerful"
        elif avg >= 40:
            return "content"
        else:
            return "distressed"

    # -- Evolve --

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
            self.message_history.append(MessageEntry(
                role="system",
                content=f"★ Level {self.level}! The creature grows stronger.",
                msg_type="level_up",
                timestamp=time.time(),
            ))

    def _make_message(self, text: str, msg_type: str, urgency: int) -> AgentMessage:
        self.last_message = text
        self.message_history.append(MessageEntry(
            role="creature",
            content=text,
            msg_type=msg_type,
            timestamp=time.time(),
        ))
        return AgentMessage(text=text, message_type=msg_type, urgency=urgency)

    def _check_urgent_needs(self) -> Optional[AgentMessage]:
        """Check stat thresholds and return mood-influenced need messages.

        Returns a need message if any stat is critically low, an ambient
        message with 10% chance, or None.
        """
        mood_prefix = ""
        if self.mood == "cheerful":
            mood_prefix = "✨ "
        elif self.mood == "distressed":
            mood_prefix = "💫 "

        if self.hunger < 20:
            return self._make_message(
                f"{mood_prefix}A soft rumble. It's hungry. Feed me?",
                "need", 8
            )
        if self.energy < 20:
            return self._make_message(
                f"{mood_prefix}Its glow is dim. So tired... let me rest.",
                "need", 7
            )
        if self.happiness < 20:
            return self._make_message(
                f"{mood_prefix}It looks at you with quiet longing.",
                "need", 6
            )

        # Random ambient message (10% chance) — mood-influenced
        if random.random() < 0.1:
            if self.mood == "cheerful":
                ambients = [
                    f"It chirps happily and gazes at the {self._random_terrain()}.",
                    f"A bright {self._archetype_sound()} fills the air.",
                    f"It dances lightly, tracing joy in the space around it.",
                ]
            elif self.mood == "distressed":
                ambients = [
                    f"It stares at the {self._random_terrain()} with hollow eyes.",
                    f"A faint, worried {self._archetype_sound()} trembles.",
                    f"It curls inward, a soft shiver running through it.",
                ]
            else:
                ambients = [
                    f"It gazes at the {self._random_terrain()}.",
                    f"A soft {self._archetype_sound()} echoes.",
                    f"It traces patterns in the air with its {self._archetype_feeling()}.",
                    f"'{self._archetype_verb()}.' It says to itself.",
                    f"The creature hums. The terra hums back.",
                ]
            return self._make_message(random.choice(ambients), "ambient", 1)

        return None

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
