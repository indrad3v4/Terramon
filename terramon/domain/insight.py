"""Insight domain model — the psychological mechanism that drives the agent.

Lives in the domain layer so ThoughtSeed can carry it without depending on
the application layer.

Per docs/dvizhok/phase1-strategy.md §3 INSIGHT ENGINE:

    DRIVER   = what the player WANTS
    BARRIER  = what BLOCKS it
    THEREFORE = the creature's hidden behavior directive (what the agent DOES)

v2 (July 2026): expanded past 5 reductive themes. Every thought is unique.
The creature's identity comes from its position in a continuous 512-dim
embedding space, its nearest archetype, its geographic anchor, and the
player's memory. 7+ billion people with thousands of thoughts each cannot
be squeezed into 5 buckets — so we don't try.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GeoContext:
    """Where on Earth this thought was born.

    Populated from the photo capture path (CAPTURE in TMA). When a player
    snaps a photo, the creature is anchored to that real place — so Terra
    becomes the actual planet Earth, with mons living at real coordinates.
    """
    lat: float = 0.0
    lon: float = 0.0
    place_name: str = ""  # e.g. "Kraków, Poland" — reverse geocoded later


@dataclass
class Insight:
    """A derived psychological mechanism that drives the agent.

    v2: replaces the old 5-theme reductive model with a richer representation
    that captures nuance, archetype, and geography.

    driver     — what the player wants (the pull).
    barrier    — what blocks it (the friction).
    therefore  — the creature's hidden behavior directive.
    archetype  — the nearest archetype in the embedding classifier (e.g. Ranger,
                 Mystic, ...) — a soft reference point, NOT a hard bucket.
    nuance     — a short phrase capturing what makes THIS thought unique
                 within its archetype cluster (derived from the embedding
                 vector's distinctive features).
    geo        — where on Earth this thought was born (lat/lon/place).
    confidence — softmax probability of the nearest archetype (0-100).
    """
    driver: str
    barrier: str
    therefore: str
    archetype: str = ""          # nearest embedding archetype
    nuance: str = ""             # what makes THIS thought unique
    geo: Optional[GeoContext] = None
    confidence: int = 0          # 0-100
