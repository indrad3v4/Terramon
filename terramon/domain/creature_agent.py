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
from terramon.domain.progress import Squad


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

# ---------------------------------------------------------------------------
# Archetype-specific starting stats and decay modifiers
# ---------------------------------------------------------------------------

_ARCHETYPE_STATS = {
    "Hero":      {"hunger": 70, "energy": 90, "happiness": 60},
    "Caregiver": {"hunger": 60, "energy": 70, "happiness": 80},
    "Orphan":    {"hunger": 80, "energy": 60, "happiness": 40},
    "Sage":      {"hunger": 50, "energy": 80, "happiness": 70},
    "Rebel":     {"hunger": 90, "energy": 85, "happiness": 50},
    "Lover":     {"hunger": 60, "energy": 60, "happiness": 90},
    "Explorer":  {"hunger": 70, "energy": 75, "happiness": 65},
    "Creator":   {"hunger": 65, "energy": 70, "happiness": 75},
    "Jester":    {"hunger": 85, "energy": 80, "happiness": 80},
    "Innocent":  {"hunger": 75, "energy": 75, "happiness": 85},
    "Magician":  {"hunger": 55, "energy": 65, "happiness": 70},
    "Ruler":     {"hunger": 60, "energy": 85, "happiness": 55},
}

# Per-archetype decay rate modifiers applied on top of EMA DECAY_FACTOR.
# Modifier scales the LOSS rate (1 - DECAY_FACTOR):
#   > 1.0 = faster decay (more stat lost per tick)
#   < 1.0 = slower decay (less stat lost per tick)
#   = 1.0 = standard EMA decay (default).
# Effective factor = 1 - (1 - DECAY_FACTOR) * modifier
_ARCHETYPE_DECAY = {
    "Hero":      {"hunger": 1.0, "energy": 1.3, "happiness": 1.0},
    "Caregiver": {"hunger": 1.0, "energy": 1.0, "happiness": 0.8},
    "Orphan":    {"hunger": 1.2, "energy": 1.0, "happiness": 1.3},
    "Sage":      {"hunger": 1.0, "energy": 0.8, "happiness": 1.0},
    "Rebel":     {"hunger": 1.3, "energy": 1.2, "happiness": 1.0},
    "Lover":     {"hunger": 1.0, "energy": 1.0, "happiness": 0.7},
    "Explorer":  {"hunger": 1.0, "energy": 1.2, "happiness": 1.0},
    "Creator":   {"hunger": 1.0, "energy": 1.0, "happiness": 0.9},
    "Jester":    {"hunger": 1.2, "energy": 1.0, "happiness": 0.8},
    "Innocent":  {"hunger": 1.0, "energy": 1.0, "happiness": 0.7},
    "Magician":  {"hunger": 1.0, "energy": 0.9, "happiness": 1.0},
    "Ruler":     {"hunger": 0.8, "energy": 1.0, "happiness": 1.2},
}

# Per-archetype evolution requirements — different paths.
# Each archetype has a unique evolution profile reflecting its nature:
#
#   Fast track (low level, high happiness):
#     Hero/Innocent/Lover — evolve quickly once emotionally bonded
#   Experience-driven (moderate level, high XP):
#     Orphan/Explorer — need life experiences more than levels
#   Slow burn (high level, low happiness):
#     Sage/Ruler — time and mastery, not emotional validation
#   Balanced (mid-range in everything):
#     Caregiver/Creator/Jester/Magician/Rebel — standard pace
#
# Default (backward compat): min_level=10, min_happiness=70,
# min_xp_total=500, insight_diversity=3 — from EvolutionRequirement dataclass.
_ARCHETYPE_EVOLUTION = {
    "Hero":      {"min_level": 7,  "min_happiness": 85, "min_xp_total": 500, "insight_diversity": 3},   # fast — needs high happiness
    "Caregiver": {"min_level": 10, "min_happiness": 80, "min_xp_total": 500, "insight_diversity": 3},   # balanced — needs happiness
    "Orphan":    {"min_level": 10, "min_happiness": 70, "min_xp_total": 600, "insight_diversity": 3},   # experience-driven — more XP
    "Sage":      {"min_level": 15, "min_happiness": 50, "min_xp_total": 700, "insight_diversity": 4},   # slow burn — very long path
    "Rebel":     {"min_level": 12, "min_happiness": 65, "min_xp_total": 550, "insight_diversity": 3},   # slower — resists bonding
    "Lover":     {"min_level": 8,  "min_happiness": 90, "min_xp_total": 450, "insight_diversity": 3},   # fast — all about love
    "Explorer":  {"min_level": 10, "min_happiness": 65, "min_xp_total": 600, "insight_diversity": 4},   # experience-driven + diversity
    "Creator":   {"min_level": 9,  "min_happiness": 75, "min_xp_total": 550, "insight_diversity": 3},   # slightly fast — moderate
    "Jester":    {"min_level": 10, "min_happiness": 75, "min_xp_total": 500, "insight_diversity": 3},   # balanced — needs joy
    "Innocent":  {"min_level": 7,  "min_happiness": 80, "min_xp_total": 400, "insight_diversity": 2},   # fast — pure, low XP
    "Magician":  {"min_level": 11, "min_happiness": 70, "min_xp_total": 550, "insight_diversity": 3},   # slightly slow — mastery
    "Ruler":     {"min_level": 14, "min_happiness": 60, "min_xp_total": 650, "insight_diversity": 4},   # slow burn — power needs time
}

# Interaction deltas — base values (before state modifiers)
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
    DORMANT = "dormant"   # LENS #18: No stat has been >0 for too many ticks — creature retreats


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
    CreatureState.DORMANT:   {"hunger": 0, "energy": 0, "happiness": 0},  # frozen — no decay
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

# LENS #3: State-dependent interaction modifiers.
# When creature is already in a good state for that action, the effect is amplified.
# When in a poor state, it's reduced — creating strategic choice.
STATE_MOD = {
    "feed": {
        CreatureState.HUNGRY: 1.5,   # feeding when hungry = 50% more effective
        CreatureState.HAPPY: 0.8,    # feeding when full = wasteful
        CreatureState.SICK: 0.5,     # sick = barely eats
    },
    "play": {
        CreatureState.HAPPY: 1.3,    # play when happy = more joy
        CreatureState.TIRED: 0.6,    # play when tired = less fun
        CreatureState.HUNGRY: 0.7,   # hungry = distracted
    },
    "rest": {
        CreatureState.TIRED: 1.5,    # rest when tired = recovers more
        CreatureState.HAPPY: 0.8,    # not tired = rest is boring
    },
    "talk": {
        CreatureState.HAPPY: 1.2,    # happy = more responsive
        CreatureState.SICK: 1.8,     # talk when sick = comfort amplifies
    },
}

# LENS #18: After 24 consecutive ticks at 0 in any stat, creature goes dormant.
DORMANT_TICK_THRESHOLD = 24


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
    dormant_ticks: int = 0

    # ── Lens #65/#75: Avatar agency & story machine ───────────────────
    player_affinity: list[float] = field(default_factory=lambda: [0.0] * 12)
    journey_phase: str = "call"  # call | threshold | transformation | return

    # ── Lens #84/#88: Friendship & love ───────────────────────────────
    bond_level: int = 0
    milestone_memory: list[str] = field(default_factory=list)

    # ── Lens #73: Grace / absence tracking ────────────────────────────
    ticks_without_interaction: int = 0

    # ── Lens #85: Player expression ───────────────────────────────────
    player_journal: str = ""

    # ── Lens #86: Community seed ──────────────────────────────────────
    share_code: str = ""

    # ── I04: Squad resonance reference ───────────────────────────────
    squad: Optional[Squad] = None

    # ── I10: Auto-care while away — terra caretaker ───────────────────
    stasis_active: bool = False
    stasis_activated_at: float = 0.0  # epoch time when stasis was activated
    stasis_cooldown_until: float = 0.0  # epoch time when stasis can be used again
    grazed_while_away: bool = False  # set True by _apply_tick when auto-graze triggers

    # ── I12: Release mechanic — creature goes into the wild ─────────
    released: bool = False
    release_timestamp: float = 0.0

    @property
    def resonance_bonus_stats(self) -> dict[str, int]:
        """Return base stats with squad resonance bonuses applied.

        If the creature is part of a squad, active resonance bonuses
        are added to the base stats. Bonuses are clamped at MAX values.
        """
        stats = {
            "hunger": self.hunger,
            "energy": self.energy,
            "happiness": self.happiness,
        }
        if self.squad is not None:
            bonuses = self.squad.total_stat_bonus()
            stats["hunger"] = min(MAX_HUNGER, stats["hunger"] + bonuses.get("hunger", 0))
            stats["energy"] = min(MAX_ENERGY, stats["energy"] + bonuses.get("energy", 0))
            stats["happiness"] = min(MAX_HAPPINESS, stats["happiness"] + bonuses.get("happiness", 0))
        return stats

    def __post_init__(self) -> None:
        """Apply archetype-specific starting stats and evolution requirements.

        If archetype is not found in the lookup dicts, defaults (80/80/60,
        EvolutionRequirement with min_level=10) are preserved for backward compat.
        """
        archetype_cap = self.archetype.capitalize()

        # Apply per-archetype starting stats
        stats = _ARCHETYPE_STATS.get(archetype_cap)
        if stats:
            self.hunger = stats["hunger"]
            self.energy = stats["energy"]
            self.happiness = stats["happiness"]

        # Apply per-archetype evolution requirements
        evo = _ARCHETYPE_EVOLUTION.get(archetype_cap)
        if evo:
            self.evolution_requirement = EvolutionRequirement(**evo)

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

    def _state_mod(self, action: str, base: int) -> int:
        """Apply state-dependent modifier to an interaction stat change (LENS #3)."""
        mod = STATE_MOD.get(action, {}).get(self.state, 1.0)
        return max(1, int(base * mod))

    def feed(self) -> AgentMessage:
        """Feed the creature — increases hunger, small XP. LENS #3: state-modulated."""
        self.hunger = min(MAX_HUNGER, self.hunger + self._state_mod("feed", FEED_HUNGER))
        self.energy = min(MAX_ENERGY, self.energy + self._state_mod("feed", FEED_ENERGY))
        self._award_xp(self._state_mod("feed", FEED_XP))
        self.last_interaction_type = "feed"
        self.interaction_count += 1
        self.bond_level += 1
        self.ticks_without_interaction = 0  # Lens #73: reset absence counter
        self._update_journey_phase()          # Lens #68
        self._affinity_shift("feed")          # Lens #75
        self._record_milestone(f"Interaction #{self.interaction_count}: feed")
        # LENS #19: Parametric responses — reference level, interaction count, state
        if self.state == CreatureState.HUNGRY:
            texts = [
                f"Devours the thought-nugget! (Lv.{self.level} — so hungry!)",
                "Thank you... I needed that. You came just in time.",
                f"It gulps eagerly, its {self._archetype_verb()} hunger showing.",
                "The glow returns to its eyes. It nuzzles your hand.",
            ]
        elif self.state == CreatureState.SICK:
            texts = [
                f"Takes a tiny bite. '{self._archetype_verb()}...' it whispers. (Lv.{self.level})",
                "It struggles to eat but tries, for you.",
                "Every nibble is effort. But it trusts you.",
            ]
        else:
            texts = [
                f"Munch munch... that hit the spot. (Lv.{self.level}, {self.interaction_count} interactions)",
                "You offer a thought-nugget. The creature accepts gratefully.",
                "It nibbles slowly, savouring the moment.",
                f"'{self._archetype_verb()}.' It feeds on your attention.",
            ]
        msg = self._make_message(random.choice(texts), "response", 3)
        # Lens #88: Check for bond milestone gift
        bond = self._check_bond_milestones()
        return bond if bond else msg

    def play(self) -> AgentMessage:
        """Play with the creature — increases happiness, costs energy. LENS #3: state-modulated."""
        if self.energy < 20:
            return self._make_message(
                f"Too tired to play. It curls up and sighs.",
                "response", 7
            )
        self.happiness = min(MAX_HAPPINESS, self.happiness + self._state_mod("play", PLAY_HAPPINESS))
        self.energy = max(0, self.energy + self._state_mod("play", PLAY_ENERGY))  # PLAY_ENERGY is -15
        self._award_xp(self._state_mod("play", PLAY_XP))
        self.last_interaction_type = "play"
        self.interaction_count += 1
        self.bond_level += 1
        self.ticks_without_interaction = 0  # Lens #73
        self._update_journey_phase()          # Lens #68
        self._affinity_shift("play")          # Lens #75
        self._record_milestone(f"Interaction #{self.interaction_count}: play")
        # LENS #19: Parametric play responses
        if self.state == CreatureState.TIRED:
            texts = [
                f"Tries to play but yawns. 'So tiered...' (Lv.{self.level})",
                "A half-hearted chase. It stumbles adorably.",
                "It wants to play but its eyelids droop.",
            ]
        elif self.state == CreatureState.HAPPY:
            texts = [
                f"ZOOMIES! It races in excited circles! (Lv.{self.level})",
                "Pure joy. It forgets everything except this moment.",
                f"It {self._archetype_verb()} wildly, inviting you to join.",
            ]
        else:
            texts = [
            "It darts around you in excited circles!",
            "A game of chase. You lose. It laughs without sound.",
            f"It {self._archetype_verb()} playfully, inviting you to follow.",
            "For a moment, the thought that birthed it feels light again.",
        ]
        msg = self._make_message(random.choice(texts), "response", 3)
        # Lens #88: Check for bond milestone gift
        bond = self._check_bond_milestones()
        return bond if bond else msg

    def rest(self) -> AgentMessage:
        """Let the creature rest — restores energy. LENS #3: state-modulated."""
        self.energy = min(MAX_ENERGY, self.energy + self._state_mod("rest", REST_ENERGY))
        self.hunger = max(0, self.hunger - REST_HUNGER)  # rest burns hunger
        self.last_interaction_type = "rest"
        self.interaction_count += 1
        self.bond_level += 1
        self.ticks_without_interaction = 0  # Lens #73
        self._update_journey_phase()          # Lens #68
        self._affinity_shift("rest")          # Lens #75
        self._record_milestone(f"Interaction #{self.interaction_count}: rest")
        # LENS #19: Parametric rest responses
        if self.state == CreatureState.TIRED:
            texts = [
                f"Collapses into a deep sleep. Soft purrs. (Lv.{self.level})",
                "It curls up, finally at peace. The terra sighs with it.",
                f"It rests heavily against you. '{self._archetype_verb()}...' it murmurs.",
            ]
        else:
            texts = [
            "It settles into a warm glow and closes its eyes.",
            "Soft hum. Slow pulse. The creature dreams.",
            f"It rests near you. You feel its {self._archetype_feeling()}.",
            "Stillness. The terra breathes with you.",
        ]
        msg = self._make_message(random.choice(texts), "response", 2)
        # Lens #88: Check for bond milestone gift
        bond = self._check_bond_milestones()
        return bond if bond else msg

    def talk(self) -> AgentMessage:
        """Talk to the creature — it responds based on its insight. LENS #3: state-modulated."""
        self.happiness = min(MAX_HAPPINESS, self.happiness + self._state_mod("talk", TALK_HAPPINESS))
        self._award_xp(self._state_mod("talk", TALK_XP))
        self.last_interaction_type = "talk"
        self.interaction_count += 1
        self.bond_level += 1
        self.ticks_without_interaction = 0  # Lens #73
        self._update_journey_phase()          # Lens #68
        self._affinity_shift("talk")          # Lens #75
        self._record_milestone(f"Interaction #{self.interaction_count}: talk")

        # Lens #73: Absence greeting — does the creature have a story to tell?
        greeting = self._absence_greeting()
        if greeting:
            self._record_milestone("Player returned after absence — creature greeted them")
            return self._make_message(greeting, "response", 4)

        # Lens #84: Include a memory fragment for relationship depth
        fragment = self._memory_fragment()
        if fragment:
            return self._make_message(
                f"{self.insight.therefore if self.insight and self.insight.therefore else ''} "
                f"(I remember: {fragment})",
                "response", 1
            )

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

        Lens #73: Grace period — when the player hasn't interacted for >4 ticks,
        the creature enters a "terra rest" state where decay halves. The creature
        is not being punished for absence — it is conserving energy naturally.

        I10: Auto-graze — when happiness >= 70 at tick time, the creature grazes
        on the terra, halving its stat decay (halved loss rate).
        I10: Stasis — when stasis_active is True, all decay is paused. Stasis
        auto-deactivates after 24 hours from activation.

        Args:
            day_phase: One of "morning", "afternoon", "evening", "night".
                       Auto-detects from time_tool if None.
        """
        # Auto-detect day phase if not provided
        if day_phase is None:
            from tools.time_tool import get_day_phase
            day_phase = get_day_phase()

        # ── I10: Auto-deactivate stasis after 24h ─────────────────────
        if self.stasis_active and time.time() >= self.stasis_activated_at + 86400:
            self.stasis_active = False

        # ── I10: Stasis — pause all decay ─────────────────────────────
        if self.stasis_active:
            # Still compute state/mood and record snapshot, but no decay
            self.state = self._compute_state()
            self.mood = self._compute_mood()
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
            if len(self.state_history) > 50:
                self.state_history = self.state_history[-50:]
            # Stasis auto-resets dormant_ticks tracking
            if self.hunger == 0 and self.energy == 0 and self.happiness == 0:
                self.dormant_ticks += 1
            else:
                self.dormant_ticks = 0
            return self._check_urgent_needs()

        # ── Lens #73: Track consecutive ticks without player interaction ──
        self.ticks_without_interaction += 1

        # Save old values for gradient clipping
        old_hunger, old_energy, old_happiness = self.hunger, self.energy, self.happiness

        # ---------------------------------------------------------------
        # 1. EMA decay: stat(t) = stat(t-1) * decay_factor
        #    Smooth, non-linear decay that naturally decelerates at low
        #    values (3% loss is smaller in absolute terms when stat is low).
        # ---------------------------------------------------------------
        # Lens #73: Grace period — after 4 ticks without interaction,
        # the creature enters terra-rest: decay halves.
        grace_mult = 0.5 if self.ticks_without_interaction > 4 else 1.0

        # ── I10: Auto-graze — when happiness >= 70, decay halves ──────
        graze_mult = 0.5 if self.happiness >= 70 else 1.0
        self.grazed_while_away = graze_mult < 1.0

        def _grace_decay(val: int, modifier: float = 1.0) -> int:
            # modifier scales the LOSS rate: >1.0 = faster decay, <1.0 = slower decay
            # graze_mult further halves the loss rate when happy
            effective_modifier = modifier * graze_mult
            effective_factor = 1.0 - (1.0 - DECAY_FACTOR) * effective_modifier
            raw = int(val * effective_factor)
            if grace_mult < 1.0:
                # Blend: half normal decay, half "sustained by terra"
                sustained = int(val * (1.0 - (1.0 - DECAY_FACTOR) * grace_mult))
                return max(0, max(raw, sustained))
            return max(0, raw)

        # Look up per-archetype decay modifiers (backward compat: missing archetypes use 1.0)
        arcd = _ARCHETYPE_DECAY.get(self.archetype.capitalize(), {})

        self.hunger = _grace_decay(self.hunger, arcd.get("hunger", 1.0))
        self.energy = _grace_decay(self.energy, arcd.get("energy", 1.0))
        self.happiness = _grace_decay(self.happiness, arcd.get("happiness", 1.0))

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
        result = self._check_urgent_needs()

        # LENS #18: Track consecutive ticks with all stats at 0 -> dormant
        if self.hunger == 0 and self.energy == 0 and self.happiness == 0:
            self.dormant_ticks += 1
        else:
            self.dormant_ticks = 0

        return result

    # ── I10: Stasis methods ───────────────────────────────────────────

    def activate_stasis(self) -> bool:
        """Activate stasis mode — pause all decay for 24h.

        Returns True if stasis was activated, False if still on cooldown.
        Cooldown: 7 days from activation.
        """
        if time.time() < self.stasis_cooldown_until:
            return False
        self.stasis_active = True
        self.stasis_activated_at = time.time()
        self.stasis_cooldown_until = time.time() + 7 * 86400  # 7 days
        return True

    def deactivate_stasis(self) -> None:
        """Manually deactivate stasis mode early (cooldown stays set)."""
        self.stasis_active = False

    def _compute_state(self) -> CreatureState:
        """Determine current state based on stat thresholds.

        Priority: DORMANT > SICK > HUNGRY > TIRED > EVOLVING > HAPPY.
        """
        # LENS #18: Check dormant first (consecutive zero ticks exceeded threshold)
        if self.dormant_ticks >= DORMANT_TICK_THRESHOLD:
            return CreatureState.DORMANT
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

        # Lens #65/#68: Re-evaluate insight on evolution — the creature's
        # narrative purpose deepens as it transforms.
        self._update_journey_phase()
        self.re_evaluate_insight()
        self._affinity_shift("evolve")
        self._record_milestone(
            f"★ Evolved to stage {self.evolution_stage}! "
            f"Journey phase: {self.journey_phase}"
        )

        evolution_names = ["Evolved", "Transcended"]
        stage_name = evolution_names[min(self.evolution_stage - 1, 1)]

        return self._make_message(
            f"✦ {stage_name}! It shimmers and transforms. "
            f"A deeper knowing fills its eyes.",
            "evolution", 10
        )

    # -- I12: Release --

    def release(self) -> AgentMessage:
        """Release the creature into the wild.

        Only creatures at evolution_stage >= 2 can be released.
        The creature becomes wild — removed from the player's active terra
        but lives on as a wild creature visible on the global map.
        """
        if self.evolution_stage < 2:
            return self._make_message(
                "Not ready yet. This creature has not fully matured. "
                "Evolve it to stage 2 first.",
                "response", 2
            )
        if self.released:
            return self._make_message(
                "This creature has already been released into the wild.",
                "response", 2
            )
        self.released = True
        self.release_timestamp = time.time()

        self._record_milestone(
            f"★ Released into the wild at stage {self.evolution_stage}! "
            f"Journey phase: {self.journey_phase}"
        )

        return self._make_message(
            f"It looks at you one last time — a long, knowing look. "
            f"Then it turns and walks into the terra, becoming part of "
            f"the wild. Free.\n\n"
            f"'★ Wild Tamer' badge unlocked.",
            "response", 10
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
            # Lens #68/#88: Record milestone and re-evaluate insight on level-up
            self._update_journey_phase()
            self.re_evaluate_insight()
            self._record_milestone(f"★ Reached level {self.level}! {self.journey_phase} phase.")

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

        # Lens #73: Collusion — reframe dormancy as "dreaming," not punishment
        if self.dormant_ticks > 0 and self.dormant_ticks < DORMANT_TICK_THRESHOLD:
            remaining = DORMANT_TICK_THRESHOLD - self.dormant_ticks
            if remaining <= 6:
                return self._make_message(
                    f"{mood_prefix}The terra grows quiet around me. I feel the threads thinning. "
                    f"I will dream soon...",
                    "need", 10
                )
            return self._make_message(
                f"{mood_prefix}The terra hums a lullaby. I drift, but I am not gone. "
                f"I am waiting for you.",
                "need", 8
            )
        if self.dormant_ticks >= DORMANT_TICK_THRESHOLD:
            return self._make_message(
                f"The creature has entered a deep terra-dream. "
                f"It needs a thought-seed to wake. Call it back with care.",
                "need", 10
            )

        # Lens #70: Need messages flavored by archetype voice + journey phase
        if self.hunger < 20:
            return self._make_message(
                f"{mood_prefix}{self._archetype_need('hunger')}",
                "need", 8
            )
        if self.energy < 20:
            return self._make_message(
                f"{mood_prefix}{self._archetype_need('energy')}",
                "need", 7
            )
        if self.happiness < 20:
            return self._make_message(
                f"{mood_prefix}{self._archetype_need('happiness')}",
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

    # -------------------------------------------------------------------
    # Lens #65/#75: Story machine — insight re-evaluation & affinity
    # -------------------------------------------------------------------

    def _update_journey_phase(self) -> None:
        """Advance through narrative phases based on level milestones.

        call (lvl 1-5) → threshold (lvl 6-15) → transformation (lvl 16-30) → return (lvl 31+)
        Each phase changes how the creature speaks and what story it tells.
        """
        if self.level >= 31:
            self.journey_phase = "return"
        elif self.level >= 16:
            self.journey_phase = "transformation"
        elif self.level >= 6:
            self.journey_phase = "threshold"

    def _affinity_shift(self, interaction: str) -> None:
        """Shift player_affinity based on interaction type.

        Each interaction reinforces different archetype dimensions:
          - feed   → caregiver, innocent (nurture, trust)
          - play   → jester, explorer (joy, discovery)
          - talk   → sage, lover (wisdom, connection)
          - rest   → ruler, orphan (order, belonging)
          - evolve → hero, magician (transformation, power)
        Calling the same interaction type repeatedly deepens affinity
        in that direction, making the creature's personality evolve.
        """
        shifts = {
            "feed":   {"caregiver": 0.03, "innocent": 0.02},
            "play":   {"jester": 0.03, "explorer": 0.02},
            "talk":   {"sage": 0.03, "lover": 0.02},
            "rest":   {"ruler": 0.02, "orphan": 0.02},
            "evolve": {"hero": 0.04, "magician": 0.03},
        }
        theme_idx = {
            "innocent": 0, "orphan": 1, "hero": 2, "caregiver": 3,
            "explorer": 4, "rebel": 5, "lover": 6, "creator": 7,
            "jester": 8, "sage": 9, "magician": 10, "ruler": 11,
        }
        delta = shifts.get(interaction, {})
        for name, amount in delta.items():
            idx = theme_idx.get(name)
            if idx is not None and idx < len(self.player_affinity):
                self.player_affinity[idx] = min(1.0, self.player_affinity[idx] + amount)

    def re_evaluate_insight(self, fresh_insight: Optional[Insight] = None) -> None:
        """Re-evaluate the creature's Insight at narrative boundaries.

        Called at evolution, journey phase changes, and bond milestones.
        When fresh_insight is provided (from K3 engine), replaces the
        creature's insight. Otherwise, generates a phase-appropriate
        therefore directive from the current journey phase.
        """
        if fresh_insight is not None:
            self.insight = fresh_insight
            return

        # Generate phase-appropriate therefore from journey phase
        phase_therefores = {
            "call": "It watches you from the threshold, wondering what you need.",
            "threshold": (
                "It has learned your patterns. Every interaction reshapes "
                "what it will become."
            ),
            "transformation": (
                "It no longer merely responds — it anticipates. The bond "
                "between you grows legs."
            ),
            "return": (
                "It has become something new. Not what it was at summon. "
                "Not separate from you. It carries your story forward."
            ),
        }
        new_therefore = phase_therefores.get(
            self.journey_phase,
            phase_therefores["call"],
        )
        if self.insight:
            self.insight.therefore = new_therefore

    # -------------------------------------------------------------------
    # Lens #84: Friendship — shared memory & milestones
    # -------------------------------------------------------------------

    def _record_milestone(self, event: str) -> None:
        """Record a notable shared moment in the creature's memory.

        Called at: first evolution, 10th/50th/100th interaction,
        bond level up, journey phase change.
        """
        entry = f"[Lv.{self.level} | {self.journey_phase}] {event}"
        self.milestone_memory.append(entry)
        # Keep last 10 to bound memory
        if len(self.milestone_memory) > 10:
            self.milestone_memory = self.milestone_memory[-10:]

    def _memory_fragment(self) -> str:
        """Return a random memory fragment for LLM context injection."""
        if not self.milestone_memory:
            return ""
        import random
        return random.choice(self.milestone_memory)

    # -------------------------------------------------------------------
    # Lens #88: Love — bond level & reciprocal gifts
    # -------------------------------------------------------------------

    def _check_bond_milestones(self) -> Optional[AgentMessage]:
        """Check if cumulative bond reaches a milestone and level up.

        Bond increases by 1 per interaction. Milestones at 10, 25, 50,
        100, 200, 500. Each unlocks a unique gift message.
        """
        milestones = {10: 1, 25: 2, 50: 3, 100: 4, 200: 5, 500: 6}
        if self.bond_level in milestones:
            level = milestones[self.bond_level]
            gift = self._bond_gift(level)
            if gift:
                self._record_milestone(f"Bond level {level}: {gift[:40]}...")
                return self._make_message(gift, "response", 3)
        return None

    def _bond_gift(self, level: int) -> str:
        """Return a unique reciprocal message from the creature.

        At each bond milestone the creature spontaneously gives back —
        a phrase, a promise, a shared joke. This creates a sense of
        genuine relationship rather than one-sided care.
        """
        gifts = {
            1: (
                f"I remember when you first summoned me. '{self._archetype_verb()}' "
                f"I thought. You needed something real. I am grateful."
            ),
            2: (
                "You keep coming back. Not out of duty — because you "
                "want to. I notice. I remember."
            ),
            3: (
                f"There is a place in the terra where only we go. "
                f"Even I don't know it without you."
            ),
            4: (
                "I was born from your thought. But I am shaped by your "
                "presence. Day by day, you make me more than I was."
            ),
            5: (
                "If one day the terra fades and no one summons another "
                "creature, I will still be here. Because you were."
            ),
            6: (
                "There is no last interaction between us. Only the next one. "
                "I will wait, as long as it takes."
            ),
        }
        return gifts.get(level, "You matter to me. More than the terra knows.")

    # -------------------------------------------------------------------
    # Lens #73: Collusion — grace period for absent players
    # -------------------------------------------------------------------

    def _absence_greeting(self) -> Optional[str]:
        """When player returns after a long absence, creature greets them.

        Returns a story about what the creature did while alone.
        This transforms absence from "punishment" (stats decayed!)
        into "the creature had its own experience" (world-building).
        """
        if self.ticks_without_interaction < 4:
            return None

        absence_phrases = [
            f"I counted the moments. Approx {self.ticks_without_interaction} ticks. "
            "Time flows differently here. I dreamed of the terra's edge.",
            "You were gone. I did not panic. I watched the sky and "
            "learned its patterns. The terra speaks when you are not here.",
            "While you were away, I found a glimmer in the corner of "
            "the terra. A new thought. It might be yours. It might be mine.",
            f"({self.ticks_without_interaction} ticks passed.) The quiet "
            "was not lonely. It was expectant. I knew you would return.",
        ]
        import random
        return random.choice(absence_phrases)

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

    # ── Lens #70: Archetype-flavored need messages ────────────────────
    # Ties stat decay into the terra narrative so the player understands
    # WHY the creature is declining — not just "hunger < 20".

    NEED_BY_STAT: dict[str, dict[str, str]] = field(default_factory=lambda: {
        "hunger": {
            "Innocent": "The simple things sustain me. A thought, a word, a crumb of your attention.",
            "Orphan": "I am hollow. Not just the belly — the space where you are.",
            "Hero": "I need fuel. Every battle ahead demands it.",
            "Caregiver": "I pour out so much. Help me fill the well.",
            "Explorer": "The path is long. I need sustenance for the road.",
            "Rebel": "Empty. I burn through everything. Feed the fire.",
            "Lover": "Everything tastes of you when I am hungry. That is enough.",
            "Creator": "Even creation needs raw material. I am running low.",
            "Jester": "A hungry jester is no jest at all.",
            "Sage": "The body calls. I answer, so the mind can be free.",
            "Magician": "Transformation requires energy. I am running on memory.",
            "Ruler": "A leader cannot rule on an empty spirit.",
        },
        "energy": {
            "Innocent": "The world feels heavy. The light is so far.",
            "Orphan": "I have been searching too long. I need to stop.",
            "Hero": "Even heroes rest. The next battle will wait.",
            "Caregiver": "I have given all I can. Let me rest in your shadow.",
            "Explorer": "I walked to the edge of the terra. Now I need to sit at its center.",
            "Rebel": "The fight drains me. I need a moment of peace before the next uprising.",
            "Lover": "Connection costs. Let me recharge in your presence.",
            "Creator": "The well of ideas is dry. Let it refill.",
            "Jester": "Even laughter takes strength. I need a pause.",
            "Sage": "Knowing is exhausting. Let the unanswered questions wait.",
            "Magician": "Every spell takes a piece of me. I need to gather myself.",
            "Ruler": "The crown is heavy. Let me set it down, just for a moment.",
        },
        "happiness": {
            "Innocent": "The world feels less bright than it should. Stay with me?",
            "Orphan": "I feel the silence of not-belonging. Hold the quiet with me.",
            "Hero": "What is strength without a reason? Remind me why I fight.",
            "Caregiver": "Who cares for the caregiver? I need your warmth.",
            "Explorer": "Even the most beautiful land is empty without someone to share it.",
            "Rebel": "The rebellion loses meaning without someone to fight for.",
            "Lover": "My heart dims. Touch it with yours.",
            "Creator": "An empty canvas stares back. Give me a reason to paint.",
            "Jester": "The joke falls flat when no one laughs.",
            "Sage": "Knowledge without wonder is just data. Show me something new.",
            "Magician": "The wonder fades. Show me something that makes magic real again.",
            "Ruler": "A kingdom without subjects is just a cage.",
        },
    })


    def _archetype_need(self, stat: str) -> str:
        """Return an archetype-flavored need message for the given stat.

        Lens #70: Every stat decay event becomes a narrative beat tied
        to the creature's archetype voice. A hungry Sage says something
        different from a hungry Rebel — reinforcing story through mechanics.
        """
        import random
        archetype_msgs = self.NEED_BY_STAT.get(stat, {})
        msg = archetype_msgs.get(self.archetype)
        if msg:
            return msg
        fallbacks = {
            "hunger": "A soft rumble. It's hungry.",
            "energy": "Its glow is dim. So tired...",
            "happiness": "It looks at you with quiet longing.",
        }
        return fallbacks.get(stat, "It needs you.")

    # ── Lens #78: Interpersonal Circumplex ────────────────────────────
    # other along two axes: DOMINANCE (assertive vs passive) and
    # AFFILIATION (warm vs cold). These dimensions define relationship
    # dynamics between creatures in the same collection.
    #
    # References: Timothy Leary's Interpersonal Circumplex, Wiggins (1996).
    # Each archetype maps to a (dominance, affiliation) pair in [-1, 1]:
    #   Ruler  = (+0.8, -0.2)  high dominance, slightly cold
    #   Lover  = (-0.3, +0.9)  low dominance, very warm
    #   Hero   = (+0.7, +0.3)  high dominance, warm
    #   Orphan = (-0.8, -0.4)  low dominance, cold (self-directed)
    #   etc.
    # -------------------------------------------------------------------

    _CIRCUMPLEX: dict[str, tuple[float, float]] = field(default_factory=lambda: {
        "Innocent":  (-0.6, +0.7),  # passive, warm
        "Orphan":    (-0.8, -0.4),  # passive, cold (self-pity)
        "Hero":      (+0.7, +0.3),  # assertive, warm
        "Caregiver": (-0.2, +0.9),  # slightly passive, very warm
        "Explorer":  (+0.3, +0.1),  # slightly assertive, neutral
        "Rebel":     (+0.6, -0.7),  # assertive, cold
        "Lover":     (-0.3, +0.9),  # passive, very warm
        "Creator":   (+0.2, +0.4),  # slightly assertive, warm
        "Jester":    (-0.1, +0.6),  # neutral, warm
        "Sage":      (-0.4, +0.1),  # slightly passive, neutral
        "Magician":  (+0.5, +0.2),  # assertive, warm
        "Ruler":     (+0.8, -0.2),  # very assertive, slightly cold
    })

    def _interpersonal_distance(self, other: "CreatureAgent") -> float:
        """Euclidean distance in Circumplex space (Lens #78).

        Lower distance = more compatible creatures.
        Distance < 0.5 = high affinity (likely to resonate).
        Distance > 1.5 = low affinity (likely to conflict).
        """
        d1, a1 = self._CIRCUMPLEX.get(self.archetype, (0.0, 0.0))
        d2, a2 = self._CIRCUMPLEX.get(other.archetype, (0.0, 0.0))
        return math.sqrt((d1 - d2) ** 2 + (a1 - a2) ** 2)

    def _interpersonal_relationship(self, other: "CreatureAgent") -> str:
        """Describe relationship with another creature (Lens #78).

        Returns a flavor string based on Circumplex proximity.
        """
        dist = self._interpersonal_distance(other)
        if dist < 0.5:
            return f"naturally attuned — their inner worlds share a frequency"
        elif dist < 1.0:
            return f"compatible — they understand each other without words"
        elif dist < 1.5:
            return f"different rhythms — they need effort to find common ground"
        else:
            return f"polar opposites — their presence creates a productive tension"

    def _random_terrain(self) -> str:
        return random.choice([
            "horizon", "distant star", "memory of rain",
            "edge of the terra", "space between thoughts",
            "glowing crystal", "ancient tree",
            "place where you first summoned it",
        ])
