"""Portrait generation — FAL.ai adapter for creature portrait images.

Phase 4 (Computer Vision): delegates to terramon.adapters.fal_art.FalArtGenerator
which provides retry logic, caching, metadata registry, PIL augmentation,
and local SVG fallback.

Phase 13 (Multimodal): the multimodal pipeline is:
  text → FAL.ai (flux/schnell text-to-image) → image → thumbnail → registry
The text prompt is assembled from game state (thought seed + archetype + rarity)
and the generated image is augmented (resize, auto-contrast) then saved alongside
a 128×128 thumbnail. The registry tracks metadata for every generated portrait.

This file retains the backward-compatible generate_portrait() function
so existing callers (TMA, etc.) don't need to change their imports.
"""

from __future__ import annotations

from terramon.adapters.fal_art import generate_portrait
from pathlib import Path


def get_portrait(thought: str, archetype: str, rarity: str) -> str | None:
    """Look up a cached portrait from the image registry.

    Returns the full portrait path if a cached version exists, None otherwise.
    This lets the TMA display the portrait without regenerating it.
    """
    try:
        from terramon.adapters.fal_art import _cache_key, _load_registry
        key = _cache_key(thought, archetype, rarity)
        registry_path = Path("data/creatures/images.json")
        registry = _load_registry(registry_path)
        entry = registry.get(key)
        if entry:
            fp = entry.get("full_path")
            if fp and Path(fp).exists():
                return fp
            tp = entry.get("thumb_path")
            if tp and Path(tp).exists():
                return tp
    except Exception:
        pass
    return None


__all__ = ["generate_portrait", "get_portrait"]
