"""Terramon TMA — Reflex app (pure-Python back + front).

Reuses the existing domain: EmbeddingClassifier -> archetype, classify_rarity,
PlayerProgress. One screen: type a thought -> summon -> creature card.

Two worlds (reflex-dev skill):
- BACKEND (Python runtime): TerramonState event handlers call the domain.
- FRONTEND (compiled to JS): the index() component renders State vars.

Telegram Mini App: this same URL is registered as a bot Menu Button. The
Telegram WebApp JS SDK (theme, MainButton, initData) is reached via
rx.call_script when needed — not required for this MVP screen.
"""

from __future__ import annotations

import reflex as rx

from terramon.adapters.embedding_classifier import EmbeddingClassifier
from terramon.domain.progress import PlayerProgress, XP_BY_RARITY
from terramon.domain.rarity import Rarity, classify_rarity

# One classifier instance (prototypes precomputed once).
_CLASSIFIER = EmbeddingClassifier()

# Rarity -> UI color + sigil (mirrors application/feedback.py, but for web).
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
# One-line auto-lore per archetype (Creative Big Idea: card carries the feeling).
_ARCHETYPE_LORE = {
    "Ranger": "Sees what others miss.",
    "Archivist": "Keeper of what was.",
    "Strategist": "Turns fear into a plan.",
    "Mystic": "Speaks with the void.",
    "Wanderer": "At peace with the open road.",
    "Scout": "First to arrive.",
}


class TerramonState(rx.State):
    """Backend state — runs in Python, drives the summon loop."""

    thought: str = ""
    agent: str = ""
    rarity: str = ""
    sigil: str = ""
    color: str = "#9ca3af"
    lore: str = ""
    xp: int = 0
    level: int = 1
    distinct: int = 0
    goal: int = 3
    price_sats: int = 0
    has_summoned: bool = False
    goal_reached: bool = False

    # Persisted progress lives on the state (per-session for the MVP).
    _collection: set[str] = set()

    @rx.event
    def set_thought(self, value: str):
        """Explicit setter (Reflex 0.9.x dropped implicit set_*)."""
        self.thought = value

    @rx.event
    def summon(self):
        """One turn: thought -> archetype + rarity -> card + progress."""
        text = self.thought.strip()
        if not text:
            return
        agent = _CLASSIFIER.classify(text)
        rres = classify_rarity(text)
        rarity = rres.rarity.value

        # progress (session-scoped set)
        self._collection = set(self._collection)
        self._collection.add(agent)
        gained = XP_BY_RARITY[Rarity(rarity)]
        self.xp += gained
        self.level = self.xp // 100 + 1
        self.distinct = len(self._collection)
        self.goal_reached = self.distinct >= self.goal

        self.agent = agent
        self.rarity = rarity
        self.sigil = _RARITY_SIGIL[rarity]
        self.color = _RARITY_COLOR[rarity]
        self.lore = _ARCHETYPE_LORE.get(agent, "A thought made flesh.")
        self.price_sats = rres.price_sats
        self.has_summoned = True


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
            rx.text('"' + TerramonState.thought + '"', font_style="italic", color="#e5e7eb", text_align="center"),
            rx.text(TerramonState.lore, font_size="0.9em", color="#9ca3af"),
            rx.divider(),
            rx.hstack(
                rx.text("Lv." + TerramonState.level.to_string(), color="#e5e7eb"),
                rx.text(TerramonState.distinct.to_string() + "/" + TerramonState.goal.to_string() + " collected", color="#e5e7eb"),
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
                rx.text("✸ GOAL REACHED — you are a Tamer! ✸", color="#f59e0b", font_weight="bold"),
                rx.fragment(),
            ),
            spacing="3",
            align="center",
        ),
        border="1px solid " + "#27272a",
        border_left="4px solid " + TerramonState.color,
        border_radius="16px",
        padding="1.5em",
        background="#141418",
        width="100%",
        max_width="380px",
    )


def index() -> rx.Component:
    """Single-screen TMA: input -> summon -> card."""
    return rx.center(
        rx.vstack(
            rx.heading("🌍 TERRAMON", size="8", color="#f5f5f5"),
            rx.text("Type a thought. Meet the creature it becomes.", color="#9ca3af"),
            rx.input(
                placeholder="i'm afraid of the interview tomorrow...",
                value=TerramonState.thought,
                on_change=TerramonState.set_thought,
                width="100%",
                max_width="380px",
                size="3",
            ),
            rx.button(
                "SUMMON",
                on_click=TerramonState.summon,
                size="3",
                width="100%",
                max_width="380px",
            ),
            rx.cond(TerramonState.has_summoned, creature_card(), rx.fragment()),
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
app.add_page(index, title="Terramon — summon your thoughts")
