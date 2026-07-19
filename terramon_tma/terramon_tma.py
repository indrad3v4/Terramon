"""Terramon TMA — Reflex app (pure-Python back + front) with AGENTIC loop.

Build-via-learn: the roast said 'vending machine, not story machine' — summoned
thought ≠ agent. This version closes that: every summon is a GameLoop turn
(ACT -> OBSERVE -> REWARD -> REFLECT) that persists to JsonMemory, so the
creature SURVIVES the session and lives in the player's 'terra'. The agent
remembers past thoughts and reflects on them (no LLM needed — schema-driven).

Two worlds (reflex-dev skill):
- BACKEND (Python runtime): TerramonState event handlers call the domain.
- FRONTEND (compiled to JS): the index() component renders State vars.
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
from tools.time_tool import get_current_time


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
_ARCHETYPE_LORE = {
    "Ranger": "Sees what others miss.",
    "Archivist": "Keeper of what was.",
    "Strategist": "Turns fear into a plan.",
    "Mystic": "Speaks with the void.",
    "Wanderer": "At peace with the open road.",
    "Scout": "First to arrive.",
}


def _reflect_on_memory(seeds: list[ThoughtSeed], new_agent: str) -> str:
    """Agent reflects on the player from memory (schema-driven, no LLM).

    The creature is not a label — it knows the player's history.
    """
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
    photo_mode: bool = False  # photo-entry path (FIX 1; see capture())

    # The player's terra: every creature that ever lived (persisted).
    terra: list[dict] = []

    @rx.var
    def xp_into_level(self) -> int:
        """XP progress within the current level (0-100) for the FIX 3 XP bar."""
        return self.xp % 100

    @rx.event
    def set_thought(self, value: str):
        """Explicit setter (Reflex 0.9.x dropped implicit set_*)."""
        self.thought = value

    @rx.event
    def summon(self):
        """One agentic turn: thought -> ACT/OBSERVE/REWARD/REFLECT -> persist."""
        text = self.thought.strip()
        if not text:
            return

        # GameLoop.take_turn: SummonService.summon -> JsonMemory.save_seed,
        # PlayerProgress.award, juicy reveal.
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

        # Reflection: the creature knows the player's history (memory).
        seeds = _MEMORY.load_all_seeds()
        self.reflection = _reflect_on_memory(seeds, result.agent)

        # FIX 2: the agent is driven by the INSIGHT (DRIVER + BARRIER -> THEREFORE),
        # not by the rarity label. Show the THEREFORE directive on the card.
        self.insight = (
            f"INSIGHT: {result.insight.therefore}"
            if result.insight is not None
            else ""
        )

        # Reload terra (all persisted creatures).
        self.terra = [_seed_to_card(s) for s in seeds]

    @rx.event
    def load_terra(self):
        """Load the player's persisted terra on app open (survives redeploys)."""
        seeds = _MEMORY.load_all_seeds()
        self.terra = [_seed_to_card(s) for s in seeds]
        if seeds:
            # Recompute progress from persisted memory (don't lose XP on reload).
            _LOOP.progress = PlayerProgress(goal_distinct=5)
            for s in seeds:
                _LOOP.progress.award(s.summoned_agent, Rarity(s.rarity))
            self.xp = _LOOP.progress.xp
            self.level = _LOOP.progress.level
            self.distinct = _LOOP.progress.distinct_count
            self.goal = _LOOP.progress.goal_distinct

    @rx.event
    def capture(self):
        """Open the photo-entry path (simulated in this MVP).

        Sets ``photo_mode`` so the thought field accepts a caption-like seed
        instead of a free-text thought — the lowest-friction "thought" is a
        photo (see docs/PLAYER_JOURNEY_MAP.md, FIX 1).

        REAL WIRING (future): a real Telegram WebApp photo input would hook in
        here via ``window.Telegram.WebApp`` — open the native camera/picker,
        read the chosen image, and feed its caption / the player's felt sense
        into ``self.thought`` (then call ``summon``). No camera is needed for
        the MVP, so we only flip the mode flag and let the user type a caption.
        """
        self.photo_mode = True


def _price_for(rarity: str) -> int:
    """Map rarity -> sats price (mirrors domain/rarity.py)."""
    return {
        "common": 0,
        "uncommon": 0,
        "rare": 15,
        "legendary": 25,
    }.get(rarity, 0)


def _seed_to_card(seed: ThoughtSeed) -> dict:
    """Flatten a persisted seed into a renderable terra card (dict for rx.foreach)."""
    rarity = seed.rarity if isinstance(seed.rarity, str) else seed.rarity.value
    return {
        "agent": seed.summoned_agent,
        "rarity": rarity,
        "sigil": _RARITY_SIGIL.get(rarity, "·"),
        "color": _RARITY_COLOR.get(rarity, "#9ca3af"),
        "thought": seed.raw_input,
        "lore": _ARCHETYPE_LORE.get(seed.summoned_agent, "A thought made flesh."),
        "timestamp": seed.timestamp,
        # FIX 2: persist the THEREFORE insight so the creature still shows it
        # on reload (older seeds without insight fall back to empty string).
        "insight": f"INSIGHT: {seed.insight.therefore}" if seed.insight else "",
    }


def terra_card(item: dict) -> rx.Component:
    """One creature in the terra grid. `item` is a Var[dict] during compile.

    Reflex 0.9.x Var dict items: pass `item["key"]` directly into rx.text —
    do NOT string-concatenate (ObjectItemOperation has no __add__).
    """
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(item["sigil"], font_size="0.7em", letter_spacing="0.15em"),
                rx.text(item["rarity"], font_size="0.7em", letter_spacing="0.15em"),
                spacing="2",
                color=item["color"],
            ),
            rx.heading(item["agent"], size="5", color=item["color"]),
            rx.text(item["thought"], font_style="italic",
                    color="#9ca3af", font_size="0.8em", max_width="220px"),
            spacing="1",
            align="center",
        ),
        border="1px solid #27272a",
        border_left=item["color"],
        border_radius="12px",
        padding="0.8em",
        background="#141418",
        width="100%",
    )


def progress_header() -> rx.Component:
    """FIX 3 — always-visible progression, rendered BELOW the SUMMON button.

    Shows 'Lv.1 · 0/5 to Tamer' + an XP bar on first open (State inits
    level=1, distinct=0, goal=5), so the goal is never hidden until reached.
    """
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
            rx.progress(
                value=TerramonState.xp_into_level,
                max=100,
                color_scheme="amber",
                size="2",
                radius="full",
                width="100%",
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
    """The shareable creature card — the growth-loop artifact."""
    return rx.box(
        rx.vstack(
            rx.text(
                TerramonState.sigil + " " + TerramonState.rarity.upper() + " " + TerramonState.sigil,
                font_size="0.8em",
                letter_spacing="0.2em",
                color=TerramonState.color,
            ),
            rx.heading(TerramonState.agent, size="7", color=TerramonState.color),
            rx.text('"' + TerramonState.thought + '"', font_style="italic",
                    color="#e5e7eb", text_align="center"),
            rx.text(TerramonState.lore, font_size="0.9em", color="#9ca3af"),
            rx.text(TerramonState.reflection, font_size="0.8em", color="#a78bfa",
                    text_align="center", max_width="360px"),
            # FIX 2: the agent is driven by the INSIGHT (DRIVER + BARRIER ->
            # THEREFORE), not by the rarity label. Show the THEREFORE directive
            # in purple, alongside the existing reflection.
            rx.cond(
                TerramonState.insight != "",
                rx.text(TerramonState.insight, font_size="0.8em", color="#c4b5fd",
                        text_align="center", font_style="italic", max_width="360px"),
                rx.fragment(),
            ),
            rx.divider(),
            rx.hstack(
                rx.text("Lv." + TerramonState.level.to_string(), color="#e5e7eb"),
                rx.text(TerramonState.distinct.to_string() + "/" + TerramonState.goal.to_string()
                        + " collected", color="#e5e7eb"),
                spacing="4",
            ),
            rx.cond(
                TerramonState.price_sats > 0,
                rx.button(
                    "⚡ MINT · " + TerramonState.price_sats.to_string() + " sats",
                    background=TerramonState.color,
                    color="#0b0b0f",
                    width="100%",
                ),
                rx.text("free summon", color="#6b7280", font_size="0.85em"),
            ),
            rx.cond(
                TerramonState.goal_reached,
                rx.vstack(
                    rx.text("✸ GOAL REACHED — you are a Tamer! ✸", color="#f59e0b", font_weight="bold"),
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
        background="#141418",
        width="100%",
        max_width="380px",
    )


def index() -> rx.Component:
    """Single-screen TMA: input -> summon -> card + terra grid."""
    return rx.center(
        rx.vstack(
            rx.heading("🌍 TERRAMON", size="8", color="#f5f5f5"),
            rx.text("Type a thought. Meet the creature it becomes.", color="#9ca3af"),
            rx.input(
                placeholder=rx.cond(
                    TerramonState.photo_mode,
                    "caption this moment — what did you see, and feel?",
                    "i'm afraid of the interview tomorrow...",
                ),
                value=TerramonState.thought,
                on_change=TerramonState.set_thought,
                width="100%",
                max_width="380px",
                size="3",
            ),
            rx.hstack(
                rx.button(
                    "📷 CAPTURE",
                    on_click=TerramonState.capture,
                    size="3",
                    width="100%",
                ),
                rx.button(
                    "SUMMON",
                    on_click=TerramonState.summon,
                    size="3",
                    width="100%",
                ),
                spacing="3",
                width="100%",
                max_width="380px",
            ),
            rx.cond(
                TerramonState.terra.length() == 0,
                rx.text(
                    "Tip: a photo works too. Capture a moment, "
                    "meet what it becomes.",
                    color="#9ca3af",
                    font_size="0.8em",
                    text_align="center",
                    max_width="340px",
                ),
                rx.fragment(),
            ),
            progress_header(),
            rx.cond(TerramonState.has_summoned, creature_card(), rx.fragment()),
            rx.tooltip(
                rx.button(
                    "🗺️ MAP MODE",
                    disabled=True,
                    width="100%",
                    max_width="380px",
                    variant="soft",
                    color_scheme="amber",
                ),
                content="Unlock at Tamer",
            ),
            rx.divider(),
            rx.heading("🜨 YOUR TERRA", size="5", color="#a78bfa"),
            rx.text(TerramonState.distinct.to_string() + " creatures live here",
                    color="#a78bfa", font_size="0.85em"),
            rx.cond(
                TerramonState.terra.length() > 0,
                rx.grid(
                    rx.foreach(TerramonState.terra, terra_card),
                    columns="2",
                    spacing="3",
                    width="100%",
                    max_width="380px",
                ),
                rx.vstack(
                    rx.text(
                        "Your world is quiet. Show me what you see — "
                        "and who you are when you see it.",
                        color="#d8b4fe",
                        font_size="0.95em",
                        text_align="center",
                        max_width="320px",
                    ),
                    spacing="2",
                    align="center",
                ),
            ),
            spacing="4",
            align="center",
            padding="2em 1em",
        ),
        background="#0b0b0f",
        min_height="100vh",
        width="100%",
    )


app = rx.App(
    theme=rx.theme(appearance="dark", accent_color="amber"),
)
app.add_page(index, title="Terramon — summon your thoughts", on_load=TerramonState.load_terra)
