"""Publish port — how Terramon shares a summoned creature to the world.

Build-via-learn mapping (AI Engineering from Scratch):
- Phase 13 (Tools & Protocols): a port IS a protocol boundary. Nostr is
  literally "Notes and Other Stuff Transmitted by Relays" — an open protocol,
  so it slots behind a port exactly like PaymentPort/ClassifierPort.
- Phase 17 (Infrastructure): publishing is a cross-cutting side effect,
  isolated behind a port so the game engine stays pure and testable.

The growth loop (dvizhok Media phase): a minted creature card is published as a
Nostr note -> Lightning-native audience zaps it -> discovery. This port is the
seam where that loop plugs in, without touching summon logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ShareCard:
    """A creature card ready to broadcast.

    Mirrors what the TMA renders: the player's own words become the creature's
    body, tagged with archetype + rarity. `content` is the human-readable note;
    `tags` are protocol hashtags for discovery.
    """

    thought: str
    agent: str
    rarity: str
    lore: str = ""
    tags: list[str] = field(default_factory=lambda: ["terramon"])

    def to_note(self) -> str:
        """Render the note body a follower actually sees."""
        sigil = {"common": "·", "uncommon": "✦", "rare": "✧", "legendary": "★"}.get(self.rarity, "·")
        lines = [
            f"{sigil} {self.rarity.upper()} — {self.agent} {sigil}",
            f'"{self.thought}"',
        ]
        if self.lore:
            lines.append(self.lore)
        lines.append("")
        lines.append(" ".join(f"#{t}" for t in self.tags))
        return "\n".join(lines)


@dataclass
class PublishResult:
    """Outcome of a broadcast."""

    event_id: str
    relays_ok: list[str] = field(default_factory=list)
    relays_failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.relays_ok)


class PublishPort(Protocol):
    """Secondary port: a pluggable place to publish a creature card.

    Any adapter (Nostr, Telegram channel, X, a local file) that implements
    `publish` satisfies this port. The game never depends on Nostr directly.
    """

    def publish(self, card: ShareCard) -> PublishResult:
        """Broadcast the card; return where it landed."""
        ...
