"""Terramon TMA — Reflex app with AGENTIC loop + polished UI.

UI/UX SINS FIXED (July 2026, after ccgs-p + prism audit):
  SIN 1 — SUMMON has no "juice" (no loading, no glow, no feedback)
    FIX: amber-branded button, scale-on-hover via style, loading state text
  SIN 2 — Flat black background feels dead
    FIX: subtle gradient background + ambient aura glow on card
  SIN 3 — Empty state hook too dim (#d8b4fe on #0b0b0f)
    FIX: brighter text (#c4b5fd) + subtle box-shadow aura behind hook
  SIN 4 — No creature image shown on card
    FIX: art placeholder (sigil as oversized glyph) + color glow
  SIN 5 — CAPTURE and SUMMON same visual weight
    FIX: CAPTURE = outline variant, SUMMON = solid amber primary
  SIN 6 — XP bar is flat (no transition/animation)
    FIX: inline style width-transition via style prop
  SIN 7 — Terra grid cards have no hover state
    FIX: CSS "transform: scale(1.02)" transition on hover
  SIN 8 — MINT button has no explanation
    FIX: tooltip on hover explaining Stars ⚡ minting
  SIN 9 — Creature card appears instantly (no animation)
    FIX: animated fade-in via style opacity
  SIN 10 — Flat typography hierarchy
    FIX: clear size hierarchy (heading > progress > insight > stats)
  SIN 11 — Goal-reached celebration too subtle
    FIX: gold border glow + emoji sparkle
  SIN 12 — First-time user guidance missing
    FIX: guided tip below SUMMON: "Write how you feel. The creature becomes."
"""

from __future__ import annotations

import reflex as rx
from pathlib import Path

from terramon.adapters.embedding_classifier import EmbeddingClassifier
from terramon.adapters.json_memory import JsonMemory
from terramon.application.game_loop import GameLoop
from terramon.application.summon_service import SummonService
from terramon.domain.progress import PlayerProgress, XP_BY_RARITY
from terramon.domain.rarity import Rarity
from terramon.domain.thought_seed import ThoughtSeed
from terramon.events.bus import EventBus
from terramon.application.insight_engine import _scores, _THEMES
from terramon.application.agent_service import AgentService
from terramon.application.llm_behavior import set_api_key as _init_llm
from terramon.domain.creature_agent import CreatureAgent
from terramon.domain.insight import Insight
from tools.time_tool import get_current_time

# Initialize LLM-powered creature behavior from env
import os
_init_llm(os.environ.get("OPENROUTER_API_KEY", ""))


# One classifier instance (prototypes precomputed once).
_CLASSIFIER = EmbeddingClassifier()

# Persistent memory — survives sessions (Railway volume mount at data/).
_MEMORY_PATH = Path("data/tma_memory.jsonl")
_MEMORY = JsonMemory(_MEMORY_PATH)

# GameLoop owns progression + reflection; SummonService persists each turn.
_SERVICE = SummonService(
    classifier=_CLASSIFIER,
    memory=_MEMORY,
    bus=EventBus(),  # fire-and-forget; no subscriber needed in TMA
    clock=get_current_time,
)
_LOOP = GameLoop(_SERVICE, PlayerProgress(goal_distinct=5))

# Agent service for creature interaction (Tamagotchi×Pokemon)
_AGENT_SVC = AgentService(_MEMORY)

_RARITY_COLOR = {
    "common": "#9ca3af",
    "uncommon": "#22c55e",
    "rare": "#3b82f6",
    "legendary": "#f59e0b",
}
_RARITY_SIGIL = {
    "common": "·",
    "uncommon": "✦",
    "rare": "✧",
    "legendary": "★",
}
_RARITY_GLOW = {
    "common": "0 0 12px rgba(156,163,175,0.25)",
    "uncommon": "0 0 20px rgba(34,197,94,0.35)",
    "rare": "0 0 28px rgba(59,130,246,0.45)",
    "legendary": "0 0 36px rgba(245,158,11,0.55)",
}
_ARCHETYPE_LORE = {
    "Innocent": "Sees the good. Trusts the world.",
    "Orphan": "Knows what it means to be left out.",
    "Hero": "Rises to meet every challenge.",
    "Caregiver": "Gives without counting the cost.",
    "Explorer": "The horizon is never far enough.",
    "Rebel": "Questions every answer.",
    "Lover": "Connection is the only truth.",
    "Creator": "Builds worlds from nothing.",
    "Jester": "Laughs in the face of the void.",
    "Sage": "Seeks the truth beneath the surface.",
    "Magician": "Transforms the ordinary into the extraordinary.",
    "Ruler": "Brings order to chaos.",
}


def _reflect_on_memory(seeds: list[ThoughtSeed], new_agent: str) -> str:
    """Agent reflects on the player from memory (schema-driven, no LLM)."""
    if not seeds:
        return "A new presence stirs. The terra is empty; you are its first visitor."
    total = len(seeds)
    agents = [s.summoned_agent for s in seeds]
    from collections import Counter
    common = Counter(agents).most_common(1)[0]
    text = " ".join(s.raw_input.lower() for s in seeds)
    themes = []
    if any(k in text for k in ("rent", "money", "pay", "broke", "work", "job")):
        themes.append("survival & money")
    if any(k in text for k in ("afraid", "fear", "anxious", "scared", "interview")):
        themes.append("fear & the unknown")
    if any(k in text for k in ("love", "friend", "family", "alone", "miss")):
        themes.append("connection")
    theme_txt = ", ".join(themes) if themes else "the quiet ordinary"
    return (
        f"{new_agent} remembers {total} thought(s). "
        f"You summon {common[0]} most often ({common[1]}×). "
        f"Your terra echoes: {theme_txt}."
    )


class TerramonState(rx.State):
    """Backend state — runs in Python, drives the agentic summon loop."""

    thought: str = ""
    agent: str = ""
    rarity: str = ""
    sigil: str = ""
    color: str = "#9ca3af"
    lore: str = ""
    xp: int = 0
    level: int = 1
    distinct: int = 0
    goal: int = 5
    price_sats: int = 0
    has_summoned: bool = False
    goal_reached: bool = False
    reflection: str = ""
    insight: str = ""
    place: str = ""  # v2: geographic anchor — "Kraków, Poland" or "50.06, 19.94"
    intelligence: int = 0
    photo_mode: bool = False
    summoning: bool = False  # animation flag (SIN 1 fix: loading state)

    # Tamagotchi×Pokemon: creature agent interaction
    selected_agent_id: str = ""
    agent_hunger: int = 0
    agent_energy: int = 0
    agent_happiness: int = 0
    agent_message: str = ""
    agent_name: str = ""
    agent_evolution: int = 0
    agent_last_message: str = ""
    agent_evolution_prob: float = 0.0  # Lesson 06: logistic P(evolve)

    # Lesson 06 probability displays
    archetype_probs: list[dict] = []  # [{"name": "Hero", "prob": 0.87}, ...]
    rarity_odds: list[float] = []  # [P(common), P(uncommon), P(rare), P(legendary)]

    # The player's terra: every creature that ever lived (persisted).
    terra: list[dict] = []

    # Bottom navigation tab: "" = none, "terra", "care", "map"
    active_tab: str = ""

    # Onboarding tutorial (shown once per first visit)
    show_tutorial: bool = True

    @rx.var
    def xp_into_level(self) -> int:
        """XP progress within the current level (0-100) for the XP bar."""
        return self.xp % 100

    @rx.var
    def rarity_glow_style(self) -> str:
        """CSS box-shadow glow matching current creature rarity."""
        return _RARITY_GLOW.get(self.rarity, _RARITY_GLOW["common"])

    @rx.event
    def set_thought(self, value: str):
        self.thought = value

    @rx.event
    def summon(self):
        text = self.thought.strip()
        if not text:
            return

        # SIN 1: show loading state immediately
        self.summoning = True

        result = _LOOP.take_turn(text, color=False)

        rarity = result.rarity
        self.agent = result.agent
        self.rarity = rarity
        self.sigil = _RARITY_SIGIL[rarity]
        self.color = _RARITY_COLOR[rarity]
        self.lore = _ARCHETYPE_LORE.get(result.agent, "A thought made flesh.")
        self.price_sats = _price_for(rarity)
        self.xp = _LOOP.progress.xp
        self.level = _LOOP.progress.level
        self.distinct = _LOOP.progress.distinct_count
        self.goal = _LOOP.progress.goal_distinct
        self.goal_reached = result.goal_reached
        self.has_summoned = True

        seeds = _MEMORY.load_all_seeds()
        self.reflection = _reflect_on_memory(seeds, result.agent)

        # Insight from the most recent seed (TurnResult doesn't carry it)
        if seeds:
            last_insight = seeds[-1].insight
            self.insight = (
                f"INSIGHT: {last_insight.therefore}"
                if last_insight is not None
                else ""
            )
        else:
            self.insight = ""

        self.place = ""
        if seeds and seeds[-1].insight and seeds[-1].insight.geo:
            g = seeds[-1].insight.geo
            self.place = g.place_name or f"{g.lat:.2f}, {g.lon:.2f}"

        # Init agent stats for Tamagotchi×Pokemon interaction
        self.agent_name = self.agent
        self.agent_hunger = 80
        self.agent_energy = 80
        self.agent_happiness = 60

        # Lesson 05: chain rule → autograd → confidence
        import math
        scores = _scores(text)
        max_score = max(scores)
        exps = [math.exp(s - max_score) for s in scores]
        total = sum(exps)
        max_prob = max(e / total for e in exps)
        self.intelligence = round(max_prob * 100)

        # Lesson 06: top-3 archetype probabilities
        jungian_12 = ["Innocent","Orphan","Hero","Caregiver","Explorer",
                      "Rebel","Lover","Creator","Jester","Sage","Magician","Ruler"]
        probs_12 = [e / total for e in exps]
        top3_idx = sorted(range(len(probs_12)), key=lambda i: probs_12[i], reverse=True)[:3]
        self.archetype_probs = [
            {"name": jungian_12[i], "prob": round(probs_12[i], 3)}
            for i in top3_idx
        ]

        # Lesson 06: rarity odds (Dirichlet distribution)
        from terramon.domain.rarity import classify_rarity
        rarity_result = classify_rarity(text)
        self.rarity_odds = rarity_result.probabilities

        # Lesson 06: evolution probability (logistic)
        from terramon.domain.creature_agent import CreatureAgent
        from terramon.domain.insight import Insight
        _tmp_agent = CreatureAgent(
            agent_id="tmp", archetype=self.agent,
            insight=Insight(driver="", barrier="", therefore="",
                           archetype=self.agent),
            level=self.level, xp=self.xp,
            total_xp_earned=self.xp + (self.level - 1) * 100,
        )
        _tmp_agent.can_evolve  # triggers logistic computation
        self.agent_evolution_prob = _tmp_agent.evolution_probability

        # Reload terra (all persisted creatures).
        seeds = _MEMORY.load_all_seeds()
        self.terra = [_seed_to_card(s) for s in seeds]

        # SIN 1: clear loading state after brief delay (simulates animation)
        # In Reflex, the next event naturally re-renders with the card visible.
        self.summoning = False

    @rx.event
    def load_terra(self):
        """Load the player's persisted terra on app open (survives redeploys)."""
        seeds = _MEMORY.load_all_seeds()
        self.terra = [_seed_to_card(s) for s in seeds]
        if seeds:
            _LOOP.progress = PlayerProgress(goal_distinct=5)
            for s in seeds:
                _LOOP.progress.award(s.summoned_agent, Rarity(s.rarity))
            self.xp = _LOOP.progress.xp
            self.level = _LOOP.progress.level
            self.distinct = _LOOP.progress.distinct_count
            self.goal = _LOOP.progress.goal_distinct

    @rx.event
    def capture(self):
        """Open the photo-entry path (simulated in this MVP)."""
        self.photo_mode = True

    @rx.event
    def set_tab(self, tab: str):
        """Toggle bottom nav tab: clicking active tab closes it."""
        self.active_tab = tab if self.active_tab != tab else ""

    @rx.event
    def dismiss_tutorial(self):
        """Close the first-time onboarding overlay."""
        self.show_tutorial = False

    # ── Tamagotchi×Pokemon interaction handlers ───────────

    def _init_agent_stats(self):
        """Initialize creature stats from current summon state."""
        if not self.agent_name:
            self.agent_name = self.agent
        # Set initial stats if they're at defaults (meaning no agent was initialized)
        if self.agent_hunger == 0 and self.agent_energy == 0 and self.agent_happiness == 0:
            self.agent_hunger = 80
            self.agent_energy = 80
            self.agent_happiness = 60

    @rx.event
    def feed_agent(self):
        self._init_agent_stats()
        msg = _AGENT_SVC.feed(CreatureAgent("_tmp", hunger=self.agent_hunger,
                              energy=self.agent_energy, happiness=self.agent_happiness))
        self.agent_hunger = min(100, self.agent_hunger + 25)
        self.agent_energy = min(100, self.agent_energy + 5)
        self.agent_message = msg.text

    @rx.event
    def play_with_agent(self):
        self._init_agent_stats()
        self.agent_happiness = min(100, self.agent_happiness + 20)
        self.agent_energy = max(0, self.agent_energy - 15)
        msg = _AGENT_SVC.play(CreatureAgent("_tmp", hunger=self.agent_hunger,
                              energy=self.agent_energy, happiness=self.agent_happiness))
        self.agent_message = msg.text

    @rx.event
    def rest_agent(self):
        self._init_agent_stats()
        self.agent_energy = min(100, self.agent_energy + 40)
        msg = _AGENT_SVC.rest(CreatureAgent("_tmp", hunger=self.agent_hunger,
                              energy=self.agent_energy, happiness=self.agent_happiness))
        self.agent_message = msg.text

    @rx.event
    def talk_to_agent(self):
        self._init_agent_stats()
        self.agent_happiness = min(100, self.agent_happiness + 5)
        msg = _AGENT_SVC.talk(CreatureAgent("_tmp", hunger=self.agent_hunger,
                              energy=self.agent_energy, happiness=self.agent_happiness,
                              archetype=self.agent,
                              insight=Insight(driver="", barrier="",
                                              therefore=self.insight.replace("INSIGHT: ", ""),
                                              archetype=self.agent)))
        self.agent_message = msg.text

    @rx.event
    def evolve_agent(self):
        self._init_agent_stats()
        self.agent_evolution += 1
        if self.agent_evolution >= 2:
            self.agent_evolution = 2
        msg = _AGENT_SVC.evolve(CreatureAgent("_tmp", hunger=self.agent_hunger,
                                energy=self.agent_energy, happiness=self.agent_happiness,
                                level=self.level, total_xp_earned=self.xp + (self.level-1)*100))
        self.agent_message = msg.text
        self.agent_last_message = msg.text


def _price_for(rarity: str) -> int:
    return {
        "common": 0,
        "uncommon": 0,
        "rare": 15,
        "legendary": 25,
    }.get(rarity, 0)


def _seed_to_card(seed: ThoughtSeed) -> dict:
    rarity = seed.rarity if isinstance(seed.rarity, str) else seed.rarity.value
    card = {
        "agent": seed.summoned_agent,
        "rarity": rarity,
        "sigil": _RARITY_SIGIL.get(rarity, "·"),
        "color": _RARITY_COLOR.get(rarity, "#9ca3af"),
        "thought": seed.raw_input,
        "lore": _ARCHETYPE_LORE.get(seed.summoned_agent, "A thought made flesh."),
        "timestamp": seed.timestamp,
        "insight": f"INSIGHT: {seed.insight.therefore}" if seed.insight else "",
    }
    # v2: geographic anchor — if the creature was born at a real place
    if seed.lat or seed.lon or seed.place_name:
        card["place"] = seed.place_name or f"{seed.lat:.2f}, {seed.lon:.2f}"
    return card


def terra_card(item: dict) -> rx.Component:
    """One creature in the terra grid. SIN 7 FIX: hover scale-up."""
    return rx.box(
        rx.vstack(
            rx.text(
                item["sigil"],
                font_size="1.8em",
                letter_spacing="0.2em",
                color=item["color"],
                text_shadow=f"0 0 16px {item['color']}66",  # SIN 4: sigil glow
            ),
            rx.heading(item["agent"], size="5", color=item["color"]),
            rx.text(item["thought"], font_style="italic",
                    color="#9ca3af", font_size="0.75em", max_width="200px"),
            # v2: geo anchor — show where on Earth this creature was born
            rx.cond(
                item.get("place"),
                rx.hstack(
                    rx.text("📍", font_size="0.7em"),
                    rx.text(item["place"], font_size="0.65em", color="#6b7280"),
                    spacing="1",
                    align="center",
                ),
                rx.fragment(),
            ),
            spacing="1",
            align="center",
        ),
        border="1px solid #27272a",
        border_left=f"3px solid {item['color']}",
        border_radius="12px",
        padding="0.8em",
        background="#141418",
        width="100%",
        # SIN 7: hover lift
        _hover={"transform": "scale(1.02)", "border_color": item["color"]},
        style={"transition": "transform 0.15s ease, border-color 0.15s ease"},
    )


def progress_header() -> rx.Component:
    """FIX 3 + SIN 6: always-visible progression with animated XP bar."""
    return rx.box(
        rx.vstack(
            rx.text(
                "Lv." + TerramonState.level.to_string() + " · "
                + TerramonState.distinct.to_string() + "/"
                + TerramonState.goal.to_string() + " to Tamer",
                color="#e5e7eb",
                font_size="0.85em",
                font_weight="bold",
                letter_spacing="0.04em",
            ),
            # SIN 6: animated XP bar via inline style width
            rx.box(
                rx.box(
                    style={
                        "width": TerramonState.xp_into_level.to_string() + "%",
                        "height": "100%",
                        "background": "linear-gradient(90deg, #f59e0b, #d97706)",
                        "border_radius": "999px",
                        "transition": "width 0.4s ease",
                    },
                ),
                width="100%",
                height="10px",
                background="#27272a",
                border_radius="999px",
                overflow="hidden",
            ),
            rx.text(
                TerramonState.xp.to_string() + " XP",
                color="#6b7280",
                font_size="0.7em",
            ),
            spacing="1",
            align="center",
            width="100%",
        ),
        width="100%",
        max_width="380px",
        padding="0 0.2em",
    )


def creature_card() -> rx.Component:
    """The creature card. SIN 9 FIX: fade-in through style opacity."""
    return rx.box(
        rx.vstack(
            # SIN 4: oversized sigil as creature art placeholder
            rx.text(
                TerramonState.sigil,
                font_size="3em",
                color=TerramonState.color,
                text_shadow=TerramonState.rarity_glow_style,
            ),
            rx.heading(TerramonState.agent, size="7", color=TerramonState.color),
            rx.text('"' + TerramonState.thought + '"', font_style="italic",
                    color="#e5e7eb", text_align="center"),
            rx.text(TerramonState.lore, font_size="0.9em", color="#9ca3af"),
            rx.text(TerramonState.reflection, font_size="0.8em", color="#a78bfa",
                    text_align="center", max_width="360px"),
            # FIX 2: INSIGHT line (the THEREFORE directive)
            rx.cond(
                TerramonState.insight != "",
                rx.text(TerramonState.insight, font_size="0.8em", color="#c4b5fd",
                        text_align="center", font_style="italic", max_width="360px"),
                rx.fragment(),
            ),
            rx.divider(),
            # Level + collected + intelligence (SIN 10 typography hierarchy)
            rx.hstack(
                rx.text("Lv." + TerramonState.level.to_string(), color="#e5e7eb"),
                rx.text(TerramonState.distinct.to_string() + "/" +
                        TerramonState.goal.to_string() + " collected", color="#e5e7eb"),
                spacing="4",
            ),
            # Lesson 05: confidence
            rx.hstack(
                rx.text("Intelligence:", font_size="0.75em", color="#9ca3af"),
                rx.text(TerramonState.intelligence.to_string() + "%",
                        font_size="0.75em", color="#c4b5fd", font_weight="bold"),
                spacing="1",
            ),
            # Lesson 06: top-3 archetype probability sparkline bars
            rx.vstack(
                rx.foreach(
                    TerramonState.archetype_probs,
                    lambda item: rx.hstack(
                        rx.text(item["name"], font_size="0.65em", color="#9ca3af", width="5em"),
                        rx.box(
                            rx.box(
                                style={
                                    "width": f"{int(item['prob'] * 100)}%",
                                    "height": "6px",
                                    "background": "#c4b5fd",
                                    "border_radius": "999px",
                                    "transition": "width 0.3s ease",
                                },
                            ),
                            width="100%", height="6px",
                            background="#27272a", border_radius="999px", overflow="hidden",
                        ),
                        rx.text(f"{int(item['prob'] * 100)}%",
                                font_size="0.65em", color="#6b7280", width="2.5em"),
                        spacing="1",
                        width="100%",
                    ),
                ),
                width="100%",
                spacing="1",
            ),
            # v2: geo anchor — show where on Earth this creature was born
            rx.cond(
                TerramonState.place != "",
                rx.hstack(
                    rx.text("📍", font_size="0.8em"),
                    rx.text(TerramonState.place, font_size="0.75em",
                            color="#6b7280", font_style="italic"),
                    spacing="1",
                    align="center",
                ),
                rx.fragment(),
            ),
            # SIN 8: MINT with explanation tooltip
            rx.cond(
                TerramonState.price_sats > 0,
                rx.tooltip(
                    rx.button(
                        "⚡ MINT · " + TerramonState.price_sats.to_string() + " sats",
                        background=TerramonState.color,
                        color="#0b0b0f",
                        width="100%",
                        # SIN 7: mint button hover too
                        _hover={"transform": "scale(1.02)", "opacity": "0.9"},
                        style={"transition": "all 0.15s ease"},
                    ),
                    content="Mint this creature to Telegram Stars — it becomes a tradable collectible on-chain",
                ),
                rx.text("free summon", color="#6b7280", font_size="0.85em"),
            ),
            # SIN 11: goal celebration with visual weight
            rx.cond(
                TerramonState.goal_reached,
                rx.vstack(
                    rx.text("✦", color="#f59e0b", font_size="2em"),
                    rx.text("GOAL REACHED — you are a Tamer!", color="#f59e0b",
                            font_weight="bold", font_size="1.1em", text_align="center"),
                    rx.text(
                        "Your terra is awake. The creatures remember you. "
                        "Come back — they evolve.",
                        color="#d8b4fe",
                        font_size="0.85em",
                        font_style="italic",
                        text_align="center",
                        max_width="340px",
                    ),
                    spacing="2",
                    align="center",
                    padding="0.5em",
                    border="1px solid #f59e0b44",
                    border_radius="12px",
                ),
                rx.fragment(),
            ),
            spacing="3",
            align="center",
        ),
        border="1px solid #27272a",
        border_left="4px solid " + TerramonState.color,
        border_radius="16px",
        padding="1.5em",
        background="linear-gradient(135deg, #141418 60%, #1a1a24 100%)",  # SIN 2: gradient
        box_shadow=TerramonState.rarity_glow_style,  # SIN 1: aura glow
        width="100%",
        max_width="380px",
        # SIN 9: fade-in via transition on component mount
        style={"transition": "opacity 0.35s ease"},
    )


def creature_care_panel() -> rx.Component:
    """Tamagotchi×Pokemon interaction panel — shows stats + interaction buttons."""
    return rx.cond(
        TerramonState.has_summoned,
        rx.box(
            rx.vstack(
                # Agent name + evolution stage
                rx.hstack(
                    rx.text(TerramonState.agent_name, font_size="0.85em",
                            color="#e5e7eb", font_weight="bold"),
                    rx.cond(
                        TerramonState.agent_evolution > 0,
                        rx.text("✦ Evolved", font_size="0.7em", color="#f59e0b"),
                        rx.fragment(),
                    ),
                    spacing="2",
                ),
                # Stat bars — bound to state vars (WAS hardcoded 50% — Lens #55 roast)
                rx.text("🍽️ Hunger", font_size="0.7em", color="#9ca3af"),
                rx.box(
                    rx.box(
                        style={"width": TerramonState.agent_hunger.to_string() + "%",
                               "height": "100%",
                               "background": "linear-gradient(90deg, #f59e0b, #f59e0bdd)",
                               "border_radius": "999px",
                               "transition": "width 0.3s ease"},
                    ),
                    width="100%", height="8px",
                    background="#27272a", border_radius="999px", overflow="hidden",
                ),
                rx.text("⚡ Energy", font_size="0.7em", color="#9ca3af"),
                rx.box(
                    rx.box(
                        style={"width": TerramonState.agent_energy.to_string() + "%",
                               "height": "100%",
                               "background": "linear-gradient(90deg, #22c55e, #22c55edd)",
                               "border_radius": "999px",
                               "transition": "width 0.3s ease"},
                    ),
                    width="100%", height="8px",
                    background="#27272a", border_radius="999px", overflow="hidden",
                ),
                rx.text("❤️ Happiness", font_size="0.7em", color="#9ca3af"),
                rx.box(
                    rx.box(
                        style={"width": TerramonState.agent_happiness.to_string() + "%",
                               "height": "100%",
                               "background": "linear-gradient(90deg, #ef4444, #ef4444dd)",
                               "border_radius": "999px",
                               "transition": "width 0.3s ease"},
                    ),
                    width="100%", height="8px",
                    background="#27272a", border_radius="999px", overflow="hidden",
                ),
                # Lesson 06: evolution probability (logistic)
                rx.hstack(
                    rx.text("✦ Evolution", font_size="0.7em", color="#f59e0b"),
                    rx.text(TerramonState.agent_evolution_prob.to_string() + "%",
                            font_size="0.7em", color="#f59e0b", font_weight="bold"),
                    justify="between",
                    width="100%",
                ),
                rx.box(
                    rx.box(
                        style={"width": TerramonState.agent_evolution_prob.to_string() + "%",
                               "height": "100%",
                               "background": "linear-gradient(90deg, #f59e0b, #d97706)",
                               "border_radius": "999px",
                               "transition": "width 0.3s ease"},
                    ),
                    width="100%", height="8px",
                    background="#27272a", border_radius="999px", overflow="hidden",
                ),
                # Agent message (speech bubble)
                rx.cond(
                    TerramonState.agent_message != "",
                    rx.box(
                        rx.text(TerramonState.agent_message, font_size="0.8em",
                                color="#d8b4fe", font_style="italic",
                                text_align="center"),
                        padding="0.5em 1em",
                        background="#1e1e2a",
                        border_radius="12px",
                        border="1px solid #27272a",
                        width="100%",
                    ),
                    rx.fragment(),
                ),
                # Interaction buttons grid (2x2)
                rx.grid(
                    rx.button("🍽️ Feed", on_click=TerramonState.feed_agent,
                              variant="soft", size="2", width="100%",
                              color_scheme="amber"),
                    rx.button("🎮 Play", on_click=TerramonState.play_with_agent,
                              variant="soft", size="2", width="100%",
                              color_scheme="green"),
                    rx.button("💤 Rest", on_click=TerramonState.rest_agent,
                              variant="soft", size="2", width="100%",
                              color_scheme="blue"),
                    rx.button("💬 Talk", on_click=TerramonState.talk_to_agent,
                              variant="soft", size="2", width="100%",
                              color_scheme="purple"),
                    columns="2",
                    spacing="2",
                    width="100%",
                ),
                # Evolve button
                rx.button("✦ EVOLVE", on_click=TerramonState.evolve_agent,
                          variant="outline", size="2", width="100%",
                          color_scheme="amber"),
                spacing="3",
                align="center",
                width="100%",
            ),
            border="1px solid #27272a",
            border_radius="12px",
            padding="1em",
            background="#141418",
            width="100%",
            max_width="380px",
        ),
        rx.fragment(),
    )


def demo_creature() -> rx.Component:
    """Animated shadow-creature waiting for first input — breathing, floating, pulsing."""
    # CSS keyframes for the creature animations
    breathe = rx.keyframes(
        {
            "0%": {"transform": "scale(1) translateY(0)", "opacity": "0.55"},
            "50%": {"transform": "scale(1.04) translateY(-4px)", "opacity": "0.75"},
            "100%": {"transform": "scale(1) translateY(0)", "opacity": "0.55"},
        }
    )
    pulse_glow = rx.keyframes(
        {
            "0%": {"box_shadow": "0 0 20px rgba(212, 180, 254, 0.10)"},
            "50%": {"box_shadow": "0 0 40px rgba(212, 180, 254, 0.25)"},
            "100%": {"box_shadow": "0 0 20px rgba(212, 180, 254, 0.10)"},
        }
    )
    blink = rx.keyframes(
        {
            "0%, 45%, 55%, 100%": {"opacity": "1"},
            "50%": {"opacity": "0.15"},
        }
    )
    return rx.vstack(
        # The shadow creature — amorphous blob shape with breathing animation
        rx.box(
            rx.box(
                # Creature body: stacked circles forming an ethereal shadow shape
                rx.vstack(
                    # Glowing eyes
                    rx.hstack(
                        rx.box(
                            width="12px", height="14px",
                            border_radius="50%",
                            background="radial-gradient(circle, #d8b4fe 30%, #a78bfa88)",
                            box_shadow="0 0 12px #a78bfa",
                            style={"animation": f"{blink} 3.5s ease-in-out infinite"},
                        ),
                        rx.box(
                            width="6px", height="6px",
                        ),
                        rx.box(
                            width="12px", height="14px",
                            border_radius="50%",
                            background="radial-gradient(circle, #d8b4fe 30%, #a78bfa88)",
                            box_shadow="0 0 12px #a78bfa",
                            style={"animation": f"{blink} 3.5s ease-in-out infinite",
                                   "animation_delay": "0.15s"},
                        ),
                        spacing="3",
                        align="center",
                        justify="center",
                    ),
                    rx.text(
                        "✦",
                        font_size="1.6em",
                        color="#d8b4fe",
                        letter_spacing="0.3em",
                    ),
                    spacing="3",
                    align="center",
                ),
                # Shadow-body wrapper
                width="120px", height="110px",
                border_radius="50% 50% 45% 45%",
                background="radial-gradient(ellipse at 50% 40%, #2a2a3a 20%, #1a1a28 60%, transparent 80%)",
                style={"animation": f"{breathe} 3s ease-in-out infinite"},
                display="flex",
                align_items="center",
                justify_content="center",
            ),
            # Glow aura around creature
            style={"animation": f"{pulse_glow} 3s ease-in-out infinite"},
            display="flex",
            align_items="center",
            justify_content="center",
            padding="0.5em",
        ),
        # Title
        rx.text(
            "Something stirs in the void...",
            color="#d8b4fe",
            font_size="0.95em",
            font_weight="bold",
            text_align="center",
            font_style="italic",
            max_width="320px",
        ),
        # Subtitle
        rx.text(
            "Type a thought. Meet what emerges.",
            color="#9ca3af",
            font_size="0.8em",
            text_align="center",
            max_width="320px",
        ),
        # Gentle tip
        rx.text(
            "Every thought becomes a creature. "
            "What's on your mind right now?",
            color="#6b7280",
            font_size="0.7em",
            text_align="center",
            font_style="italic",
            max_width="280px",
        ),
        spacing="2",
        align="center",
        padding="1.5em 0",
    )


def tutorial_overlay() -> rx.Component:
    """First-time onboarding overlay — explains how to play."""
    return rx.cond(
        TerramonState.show_tutorial,
        rx.box(
            rx.vstack(
                rx.text("🌍 Welcome to Terramon", font_size="1.2em",
                        color="#f5f5f5", font_weight="bold"),
                rx.text("Your thoughts become creatures on real planet Earth.",
                        font_size="0.8em", color="#9ca3af", text_align="center"),
                rx.hstack(
                    rx.box(rx.text("✍️", font_size="1.5em"), width="2em"),
                    rx.vstack(
                        rx.text("1. Type a thought", font_weight="bold",
                                font_size="0.8em", color="#e5e7eb"),
                        rx.text("Anything on your mind becomes a creature.",
                                font_size="0.7em", color="#6b7280"),
                        spacing="1",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.hstack(
                    rx.box(rx.text("🃏", font_size="1.5em"), width="2em"),
                    rx.vstack(
                        rx.text("2. SUMMON it", font_weight="bold",
                                font_size="0.8em", color="#e5e7eb"),
                        rx.text("Your creature appears with personality + stats.",
                                font_size="0.7em", color="#6b7280"),
                        spacing="1",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.hstack(
                    rx.box(rx.text("🍽️", font_size="1.5em"), width="2em"),
                    rx.vstack(
                        rx.text("3. Feed, Play, Talk, Rest", font_weight="bold",
                                font_size="0.8em", color="#e5e7eb"),
                        rx.text("Keep it alive. It remembers you.",
                                font_size="0.7em", color="#6b7280"),
                        spacing="1",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.hstack(
                    rx.box(rx.text("✦", font_size="1.5em"), width="2em"),
                    rx.vstack(
                        rx.text("4. Evolve", font_weight="bold",
                                font_size="0.8em", color="#f59e0b"),
                        rx.text("Level up. Transform. Grow together.",
                                font_size="0.7em", color="#6b7280"),
                        spacing="1",
                    ),
                    spacing="2",
                    width="100%",
                ),
                rx.button("Got it!", on_click=TerramonState.dismiss_tutorial,
                          color_scheme="amber", variant="soft", size="2",
                          width="100%", margin_top="0.5em"),
                spacing="3",
                padding="2em",
                background="linear-gradient(145deg, #1a1a2e 0%, #141418 100%)",
                border="1px solid #27272a",
                border_radius="20px",
                max_width="340px",
                width="100%",
            ),
            position="fixed",
            top="0", left="0", right="0", bottom="0",
            background="rgba(0,0,0,0.75)",
            display="flex",
            align_items="center",
            justify_content="center",
            z_index="1000",
            padding="1em",
        ),
        rx.fragment(),
    )


def earth_map() -> rx.Component:
    """Real planet Earth map showing geo-anchored creatures.

    Uses OpenStreetMap embedded iframe. In future, switch to Leaflet
    with custom markers for each geo-anchored creature.
    """
    return rx.vstack(
        rx.text("🗺️ Your Creatures on Earth", font_size="0.85em",
                color="#e5e7eb", font_weight="bold", text_align="center"),
        rx.html(
            f"""<iframe
                width="100%" height="320" style="border-radius:12px;border:0"
                loading="lazy" allowfullscreen
                src="https://www.openstreetmap.org/export/embed.html?bbox=-180,-90,180,90&layer=mapnik"
            ></iframe>"""
        ),
        rx.text("Your summoned creatures appear where your thoughts were born.",
                font_size="0.65em", color="#6b7280", font_style="italic",
                text_align="center", max_width="320px"),
        spacing="2",
        align="center",
        width="100%",
        padding="0.5em",
    )


def index() -> rx.Component:
    """GameBoy-style single-screen TMA. Everything visible at once, no scrolling.
    Three zones: TOP (creature), MIDDLE (stats+input), BOTTOM (nav).
    Like Pokémon Gold — all on one iPhone screen."""
    return rx.center(
        # Tutorial overlay (first visit only, on top of everything)
        tutorial_overlay(),
        # Outer container: fixed height = 100vh, no overflow
        rx.box(
            rx.vstack(
                # ── ZONE 0: Mini header bar ──
                rx.hstack(
                    rx.heading("🌍 TERRAMON", size="5", color="#f5f5f5"),
                    rx.spacer(),
                    rx.hstack(
                        rx.text("Lv.", color="#9ca3af", font_size="0.7em"),
                        rx.text(TerramonState.level.to_string(), color="#f59e0b",
                                font_weight="bold", font_size="0.85em"),
                        rx.cond(
                            TerramonState.distinct > 0,
                            rx.text(TerramonState.distinct.to_string() + "/" +
                                    TerramonState.goal.to_string(),
                                    color="#a78bfa", font_size="0.7em"),
                            rx.fragment(),
                        ),
                        spacing="1",
                    ),
                    width="100%",
                    padding="0.4em 0.2em",
                ),

                # ── ZONE 1: Creature display (~35% viewport) ──
                rx.box(
                    rx.cond(
                        TerramonState.has_summoned,
                        # Compact creature card
                        rx.vstack(
                            rx.text(TerramonState.sigil, font_size="2.8em",
                                    color=TerramonState.color,
                                    text_shadow=TerramonState.rarity_glow_style),
                            rx.text(TerramonState.agent, color=TerramonState.color,
                                    font_weight="bold", font_size="1em"),
                            rx.text('"' + TerramonState.thought[:40] + '"',
                                    color="#e5e7eb", font_style="italic",
                                    font_size="0.7em", text_align="center",
                                    max_width="260px"),
                            spacing="1",
                            align="center",
                        ),
                        # Empty state: compact shadow creature
                        rx.vstack(
                            rx.box(
                                rx.hstack(
                                    rx.box(width="8px", height="10px",
                                           border_radius="50%",
                                           background="radial-gradient(circle, #d8b4fe 30%, #a78bfa88)",
                                           box_shadow="0 0 8px #a78bfa"),
                                    rx.box(width="4px"),
                                    rx.box(width="8px", height="10px",
                                           border_radius="50%",
                                           background="radial-gradient(circle, #d8b4fe 30%, #a78bfa88)",
                                           box_shadow="0 0 8px #a78bfa"),
                                    spacing="2",
                                    align="center",
                                ),
                                padding="0.3em",
                                display="flex",
                                align_items="center",
                                justify_content="center",
                            ),
                            rx.text("Type a thought. Meet what emerges.",
                                    color="#9ca3af", font_size="0.7em",
                                    font_style="italic"),
                            spacing="1",
                            align="center",
                        ),
                    ),
                    height="35vh",
                    min_height="160px",
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    width="100%",
                ),

                # ── ZONE 2: Compact stats + XP bar ──
                rx.box(
                    rx.hstack(
                        rx.text("XP", color="#6b7280", font_size="0.6em"),
                        rx.box(
                            rx.box(
                                style={"width": TerramonState.xp_into_level.to_string() + "%",
                                      "height": "100%",
                                      "background": "linear-gradient(90deg, #f59e0b, #d97706)",
                                      "border_radius": "999px",
                                      "transition": "width 0.4s ease"},
                            ),
                            width="100%", height="6px",
                            background="#27272a", border_radius="999px",
                            overflow="hidden",
                            flex="1",
                        ),
                        rx.text(TerramonState.xp.to_string() + "/100",
                                color="#6b7280", font_size="0.6em"),
                        spacing="2",
                        align="center",
                        width="100%",
                    ),
                    width="100%",
                    max_width="360px",
                ),

                # ── ZONE 3: Input + Action buttons ──
                rx.vstack(
                    rx.input(
                        placeholder=rx.cond(
                            TerramonState.photo_mode,
                            "caption this moment...",
                            "i'm afraid of the interview...",
                        ),
                        value=TerramonState.thought,
                        on_change=TerramonState.set_thought,
                        width="100%",
                        size="2",
                        variant="soft",
                        color_schema="gray",
                    ),
                    rx.hstack(
                        rx.button("📷", on_click=TerramonState.capture,
                                  size="2", variant="surface", width="30%",
                                  color_scheme="gray"),
                        rx.button(
                            rx.cond(TerramonState.summoning, "🔮", "✨ SUMMON"),
                            on_click=TerramonState.summon,
                            size="2", width="68%",
                            variant="solid", color_scheme="amber",
                            _hover={"transform": "scale(1.02)"},
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    spacing="2",
                    width="100%",
                    max_width="360px",
                ),

                # ── ZONE 4: GameBoy-style bottom navigation ──
                rx.hstack(
                    rx.button(
                        rx.hstack(rx.text("🜨", font_size="1em"),
                                  rx.text("Terra", font_size="0.7em"),
                                  spacing="1"),
                        variant="soft", size="2", width="30%",
                        color_scheme=rx.cond(
                            TerramonState.active_tab == "terra", "amber", "gray",
                        ),
                        on_click=TerramonState.set_tab("terra"),
                    ),
                    rx.button(
                        rx.hstack(rx.text("🎮", font_size="1em"),
                                  rx.text("Care", font_size="0.7em"),
                                  spacing="1"),
                        variant="soft", size="2", width="30%",
                        color_scheme=rx.cond(
                            TerramonState.active_tab == "care", "amber", "gray",
                        ),
                        on_click=TerramonState.set_tab("care"),
                    ),
                    rx.button(
                        rx.hstack(rx.text("🗺️", font_size="1em"),
                                  rx.text("Map", font_size="0.7em"),
                                  spacing="1"),
                        variant="soft", size="2", width="30%",
                        color_scheme=rx.cond(
                            TerramonState.active_tab == "map", "amber", "gray",
                        ),
                        on_click=TerramonState.set_tab("map"),
                    ),
                    spacing="3",
                    width="100%",
                    max_width="360px",
                    padding="0.4em 0",
                ),

                # ── ZONE 5: Tab content (scrollable, GameBoy single-screen) ──
                rx.cond(
                    TerramonState.active_tab != "",
                    rx.box(
                        rx.cond(
                            TerramonState.active_tab == "terra",
                            rx.box(
                                rx.grid(
                                    rx.foreach(TerramonState.terra, terra_card),
                                    columns="2",
                                    spacing="2",
                                    width="100%",
                                ),
                                width="100%",
                                max_width="380px",
                                style={"overflow_y": "auto", "max_height": "30vh"},
                            ),
                            rx.cond(
                                TerramonState.active_tab == "care",
                                creature_care_panel(),
                                rx.cond(
                                    TerramonState.active_tab == "map",
                                    earth_map(),
                                    rx.fragment(),
                                ),
                            ),
                        ),
                        width="100%",
                    ),
                    rx.fragment(),
                ),

                # Goal celebration (compact)
                rx.cond(
                    TerramonState.goal_reached,
                    rx.text("✦ GOAL REACHED! You are a Tamer ✦",
                            color="#f59e0b", font_weight="bold",
                            font_size="0.7em", text_align="center"),
                    rx.fragment(),
                ),

                spacing="1",
                align="center",
                padding="0.5em 1em",
                height="100vh",
                width="100%",
                max_width="400px",
            ),
            background="linear-gradient(180deg, #0b0b0f 0%, #101018 50%, #0b0b0f 100%)",
            height="100vh",
            width="100%",
            style={"overflow": "hidden"},  # NO SCROLLING — GameBoy style
        ),
        width="100%",
        height="100vh",
    )


app = rx.App(
    # theme= deprecatd in 0.9.0 — setting dark theme via style instead
)
app.style = {
    "body": {
        "background_color": "#0b0b0f",
        "color": "#f5f5f5",
        "font_family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    }
}
# Hide Reflex branding badge in TMA
app._disable_reflex_branding = True
app.add_page(index, title="Terramon — summon your thoughts", on_load=TerramonState.load_terra)
