"""Art port — how Terramon turns a summoned creature into an image.

Build-via-learn mapping (AI Engineering from Scratch):
- Phase 8 (Generative Models): text-to-image diffusion is the concrete
  generative model; the prompt is assembled from game state.
- Phase 13 (Tools & Protocols): the image provider (FAL / Comet / local) is a
  Tool behind a port — swap without touching game logic.

Closes the dvizhok/PRISM roast blocker #1: "without art, a rare creature is
just an ordinary creature with a label." Art makes rarity real.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from terramon.domain.rarity import Rarity

# Each archetype maps to an element + visual motif for prompt assembly.
ARCHETYPE_VISUAL = {
    "Ranger": ("earth", "a keen-eyed scout beast, mossy hide, alert stance"),
    "Archivist": ("light", "an ancient keeper spirit, glowing runes, robed form"),
    "Strategist": ("air", "a sharp tactician creature, angular armor, calm eyes"),
    "Mystic": ("void", "a shadowy void-touched entity, star-flecked mist, third eye"),
    "Wanderer": ("water", "a serene drifting spirit, flowing form, soft currents"),
    "Scout": ("earth", "a small swift creature, first to arrive, bright eyes"),
    "Courage": ("fire", "a fierce fire spirit born of fear turned brave, ember aura"),
    "Comfort": ("water", "a calming water spirit, gentle glow, soothing form"),
    "Healer": ("earth", "a restorative earth spirit, blooming vines, warm light"),
    "Sage": ("light", "a wise luminous being, halo of understanding"),
}

# Rarity -> aura style injected into the prompt (visual scarcity signal).
RARITY_AURA = {
    Rarity.COMMON: "subtle grey aura, simple",
    Rarity.UNCOMMON: "green aura, refined detail",
    Rarity.RARE: "vivid blue aura, ornate, glowing particles",
    Rarity.LEGENDARY: "radiant golden aura, epic, intense glow, masterpiece",
}


@dataclass
class ArtRequest:
    """Everything needed to render a creature image."""

    thought: str
    archetype: str
    rarity: Rarity

    def to_prompt(self) -> str:
        """Assemble a text-to-image prompt from game state (no artist needed)."""
        element, motif = ARCHETYPE_VISUAL.get(
            self.archetype, ("earth", "a mysterious creature")
        )
        aura = RARITY_AURA[self.rarity]
        return (
            f"{motif}, {element} element, {aura}, "
            f"trading-card game creature art, dark background, "
            f"centered portrait, high detail, digital fantasy illustration, no text"
        )


@dataclass
class ArtResult:
    """The rendered image."""

    path: str
    prompt: str
    seed: int = 0
    bytes_len: int = 0


class ArtPort(Protocol):
    """Secondary port: a pluggable text-to-image provider."""

    def generate(self, request: ArtRequest) -> ArtResult:
        """Render the creature image and return where it was saved."""
        ...
