"""FAL.ai adapter — generates creature portraits from thought seeds.

Implements the ArtPort protocol (terramon.ports.art_port).

Phase 4 (Computer Vision) features:
  - Retry logic with exponential backoff (2 retries)
  - Content-addressable caching (blake2b hash of thought+archetype)
  - Image metadata tracking via JSON registry
  - PIL-based augmentation: thumbnail 128×128, format validation, auto-contrast
  - Local SVG/PNG placeholder fallback when FAL.ai is unavailable
  - Rarity-based style guidance in prompt (via ArtRequest.to_prompt)

Compatible with the existing portrait_gen.generate_portrait() interface.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFilter

from terramon.application.circuit_breaker import CircuitBreaker
from terramon.ports.art_port import ArtPort, ArtRequest, ArtResult
from terramon.domain.rarity import Rarity

# Module-level circuit breaker for FAL.ai API calls
_fal_circuit_breaker = CircuitBreaker(max_failures=3, cooldown=60.0, name="FAL")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FAL_API_URL = "https://fal.run/fal-ai/flux/schnell"
_FAL_TIMEOUT = 30
_MAX_RETRIES = 2
_BACKOFF_BASE = 1.0  # seconds
_CACHE_DIGEST_SIZE = 16  # blake2b digest bytes → 32 hex chars
_FULL_SIZE = 256
_THUMB_SIZE = 128

_RARITY_COLORS = {
    Rarity.COMMON: "#9ca3af",
    Rarity.UNCOMMON: "#22c55e",
    Rarity.RARE: "#3b82f6",
    Rarity.LEGENDARY: "#f59e0b",
}

_RARITY_SIGIL = {
    Rarity.COMMON: "·",
    Rarity.UNCOMMON: "✦",
    Rarity.RARE: "✧",
    Rarity.LEGENDARY: "★",
}

# Archetype → sigil shape for SVG fallback
_ARCHETYPE_SIGILS = {
    "Ranger": "circle",
    "Archivist": "diamond",
    "Strategist": "triangle",
    "Mystic": "hexagon",
    "Wanderer": "wave",
    "Scout": "circle",
    "Courage": "triangle",
    "Comfort": "wave",
    "Healer": "diamond",
    "Sage": "hexagon",
}


# ---------------------------------------------------------------------------
# Cache key
# ---------------------------------------------------------------------------


def _cache_key(thought: str, archetype: str, rarity: str | None = None) -> str:
    """Content-addressable cache key from thought + archetype + rarity.

    Same (thought, archetype, rarity) triple always maps to the same key,
    so repeated summons with matching parameters reuse the cached portrait.

    Phase 13 (Multimodal): rarity is included so creatures of the same
    thought+archetype but different rarities get distinct portraits.
    """
    raw = f"{thought}::{archetype}::{rarity or ''}".encode("utf-8")
    return hashlib.blake2b(raw, digest_size=_CACHE_DIGEST_SIZE).hexdigest()


# ---------------------------------------------------------------------------
# SVG placeholder
# ---------------------------------------------------------------------------


def _make_placeholder_svg(
    key: str,
    rarity: Rarity,
    archetype: str,
) -> str:
    """Generate an inline SVG placeholder with rarity colour + archetype sigil.

    This is converted to PNG by the fallback pipeline when FAL.ai is down.
    """
    color = _RARITY_COLORS.get(rarity, "#9ca3af")
    sigil = _RARITY_SIGIL.get(rarity, "·")
    shape = _ARCHETYPE_SIGILS.get(archetype, "circle")

    # Build a simple geometric SVG
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">',
        f'  <rect width="256" height="256" rx="12" fill="#1a1a2e"/>',
        f'  <rect x="4" y="4" width="248" height="248" rx="10" fill="none" stroke="{color}" stroke-width="2" opacity="0.3"/>',
    ]

    cx, cy = 128, 128
    r_inner = 40
    r_outer = 80

    if shape == "circle":
        lines.append(f'  <circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="none" stroke="{color}" stroke-width="3" opacity="0.6"/>')
        lines.append(f'  <circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="{color}" opacity="0.15"/>')
    elif shape == "diamond":
        pts = f"{cx},{cy - r_outer} {cx + r_outer},{cy} {cx},{cy + r_outer} {cx - r_outer},{cy}"
        lines.append(f'  <polygon points="{pts}" fill="none" stroke="{color}" stroke-width="3" opacity="0.6"/>')
        pts_inner = f"{cx},{cy - r_inner} {cx + r_inner},{cy} {cx},{cy + r_inner} {cx - r_inner},{cy}"
        lines.append(f'  <polygon points="{pts_inner}" fill="{color}" opacity="0.15"/>')
    elif shape == "triangle":
        pts = f"{cx},{cy - r_outer} {cx + r_outer},{cy + r_outer * 0.75} {cx - r_outer},{cy + r_outer * 0.75}"
        lines.append(f'  <polygon points="{pts}" fill="none" stroke="{color}" stroke-width="3" opacity="0.6"/>')
    elif shape == "hexagon":
        pts = " ".join(
            f"{cx + r_outer * math.cos(math.radians(a))},{cy + r_outer * math.sin(math.radians(a))}"
            for a in range(0, 360, 60)
        )
        lines.append(f'  <polygon points="{pts}" fill="none" stroke="{color}" stroke-width="3" opacity="0.6"/>')
    elif shape == "wave":
        lines.append(f'  <path d="M 48,128 Q 80,80 128,128 T 208,128" fill="none" stroke="{color}" stroke-width="3" opacity="0.6"/>')
        lines.append(f'  <path d="M 48,148 Q 80,100 128,148 T 208,148" fill="none" stroke="{color}" stroke-width="2" opacity="0.3"/>')

    # Centered sigil character
    lines.append(f'  <text x="128" y="145" text-anchor="middle" font-size="48" fill="{color}" font-family="serif">{sigil}</text>')

    # Archetype label at bottom
    lines.append(f'  <text x="128" y="230" text-anchor="middle" font-size="14" fill="{color}" opacity="0.7" font-family="sans-serif">{archetype}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def _svg_to_png(svg_text: str, size: int = 256) -> bytes:
    """Convert SVG text to PNG bytes using Pillow's primitive SVG support.

    Pillow can render basic SVG via Image.open(BytesIO(svg_bytes)).
    Falls back to a solid-colour Rectangle if SVG rendering fails.
    """
    try:
        svg_bytes = svg_text.encode("utf-8")
        # Pillow's SVG parser needs the SVG as file-like
        from PIL import Image
        img = Image.open(BytesIO(svg_bytes))
        img = img.convert("RGBA")
        # Resize to exact size (Pillow's SVG reader may vary)
        img = img.resize((size, size), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        # Ultimate fallback: solid colour square
        color_map = {
            Rarity.COMMON: (156, 163, 175),
            Rarity.UNCOMMON: (34, 197, 94),
            Rarity.RARE: (59, 130, 246),
            Rarity.LEGENDARY: (245, 158, 11),
        }
        img = Image.new("RGBA", (size, size), (26, 26, 46, 255))
        draw = ImageDraw.Draw(img)
        # Draw a cross in the rarity color
        rarity_col = color_map.get(Rarity.COMMON, (156, 163, 175))
        center = size // 2
        draw.ellipse(
            [center - 40, center - 40, center + 40, center + 40],
            outline=rarity_col, width=3,
        )
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


# ---------------------------------------------------------------------------
# PIL augmentation pipeline
# ---------------------------------------------------------------------------


def _augment_and_save(
    image_bytes: bytes,
    full_path: Path,
    thumb_path: Path,
) -> tuple[int, int]:
    """Run the PIL augmentation pipeline on downloaded image bytes.

    Steps:
      1. Open & validate (must be a valid image)
      2. Convert to RGB (strip alpha)
      3. Auto-contrast (colour adjustment)
      4. Save full-size 256×256
      5. Generate & save 128×128 thumbnail

    Returns (full_bytes, thumb_bytes) — file sizes in bytes.
    Returns (0, 0) if image is invalid.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        img.verify()  # quick structural check
        # Re-open after verify (verify closes the file)
        img = Image.open(BytesIO(image_bytes))
    except Exception:
        return 0, 0

    try:
        # Convert to RGB
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        elif img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (0, 0, 0))
            bg.paste(img, mask=img.split()[3])
            img = bg

        # Resize to exact full size if different
        if img.size != (_FULL_SIZE, _FULL_SIZE):
            img = img.resize((_FULL_SIZE, _FULL_SIZE), Image.LANCZOS)

        # Auto-contrast (colour adjustment)
        from PIL import ImageOps
        img = ImageOps.autocontrast(img, cutoff=2)

        # Save full size
        full_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(full_path, format="PNG", optimize=True)
        full_size = full_path.stat().st_size

        # Generate and save thumbnail
        thumb = img.copy()
        thumb.thumbnail((_THUMB_SIZE, _THUMB_SIZE), Image.LANCZOS)
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        thumb.save(thumb_path, format="PNG", optimize=True)
        thumb_size = thumb_path.stat().st_size

        return full_size, thumb_size
    except Exception:
        # If augmentation fails, save raw bytes as-is
        full_path.parent.mkdir(parents=True, exist_ok=True)
        Path(full_path).write_bytes(image_bytes)
        full_size = full_path.stat().st_size
        thumb_size = 0
        return full_size, thumb_size


# ---------------------------------------------------------------------------
# Image registry
# ---------------------------------------------------------------------------


def _load_registry(registry_path: Path) -> dict:
    """Load the image registry JSON from disk."""
    if registry_path.exists():
        try:
            return json.loads(registry_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_registry(registry_path: Path, registry: dict) -> None:
    """Atomically write the image registry to disk."""
    tmp = registry_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(registry, indent=2, sort_keys=True))
    tmp.rename(registry_path)


def _register_image(
    registry_path: Path,
    key: str,
    prompt: str,
    archetype: str,
    rarity: str,
    full_path: str,
    thumb_path: str,
    full_size: int,
    thumb_size: int,
    source: str = "api",
) -> None:
    """Add or update an entry in the image registry."""
    registry = _load_registry(registry_path)
    registry[key] = {
        "cache_key": key,
        "prompt": prompt,
        "archetype": archetype,
        "rarity": rarity,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "full_path": full_path,
        "thumb_path": thumb_path,
        "full_size": full_size,
        "thumb_size": thumb_size,
        "source": source,  # "api" for FAL.ai, "placeholder" for local fallback
    }
    _save_registry(registry_path, registry)


# ---------------------------------------------------------------------------
# Exponential backoff retry
# ---------------------------------------------------------------------------


def _fal_request(
    api_key: str,
    prompt: str,
    seed: int,
) -> bytes:
    """Call FAL.ai with retries, exponential backoff, and circuit breaker.

    Circuit breaker behaviour:
      - If the circuit is OPEN (3 consecutive failures, 60s cooldown),
        raises RuntimeError immediately without calling the API.
      - A successful call resets the counter and closes the circuit (CLOSED).
      - Exhausting all retries increments the failure counter.

    Returns raw image bytes on success.
    Raises RuntimeError after exhausting retries or if circuit is OPEN.
    """
    # ── Circuit breaker fast-fail ────────────────────────────────────
    if not _fal_circuit_breaker.is_available:
        raise RuntimeError(
            "FAL.ai circuit breaker is OPEN — fast-fail (will retry after cooldown)"
        )

    last_error = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            req = Request(
                _FAL_API_URL,
                data=json.dumps({
                    "prompt": prompt,
                    "image_size": "square_hd" if "square" else "square",
                    "num_images": 1,
                    "seed": seed,
                }).encode(),
                headers={
                    "Authorization": f"Key {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            resp = json.loads(urlopen(req, timeout=_FAL_TIMEOUT).read().decode())
            images = resp.get("images", [])
            if not isinstance(images, list) or not images:
                raise RuntimeError("FAL.ai returned empty images list")

            image_url = images[0].get("url", "")
            if not image_url:
                raise RuntimeError("FAL.ai response missing image URL")

            # Download the image
            img_req = Request(image_url, headers={"User-Agent": "Terramon/1.0"})
            img_data = urlopen(img_req, timeout=_FAL_TIMEOUT).read()
            if not img_data:
                raise RuntimeError("Downloaded empty image data")

            # Success — reset circuit breaker
            _fal_circuit_breaker.on_success()
            return img_data

        except (URLError, json.JSONDecodeError, KeyError, IndexError, RuntimeError, OSError) as e:
            last_error = e
            if attempt < _MAX_RETRIES:
                delay = _BACKOFF_BASE * (2 ** attempt)
                time.sleep(delay)
                continue

    # All retries exhausted — notify circuit breaker
    _fal_circuit_breaker.on_failure()
    raise RuntimeError(f"FAL.ai request failed after {_MAX_RETRIES + 1} attempts: {last_error}")


# ---------------------------------------------------------------------------
# FalArtGenerator
# ---------------------------------------------------------------------------


class FalArtGenerator:
    """Image generator backed by FAL.ai flux/schnell with local fallback.

    Implements the ArtPort protocol (ArtPort.generate).
    """

    def __init__(
        self,
        client=None,
        out_dir: str | Path = "data/creatures",
        api_key: str | None = None,
    ) -> None:
        self._out_dir = Path(out_dir)
        self._cache_dir = self._out_dir / ".cache"
        self._thumb_dir = self._out_dir / "thumbnails"
        self._placeholder_dir = self._out_dir / "placeholders"
        self._registry_path = self._out_dir / "images.json"

        # Allow injecting a fake client for testing
        self._client = client
        self._api_key = api_key or os.environ.get("FAL_KEY", "")

    def generate(self, request: ArtRequest) -> ArtResult:
        """Generate a creature portrait from an ArtRequest.

        Returns ArtResult with path, prompt, seed, bytes_len.
        Never returns an empty path — falls back to placeholder on failure.
        """
        # 1. Deterministic seed (blake2b — not Python's salted hash())
        seed_bytes = hashlib.blake2b(
            (request.thought + request.archetype).encode(), digest_size=4
        ).digest()
        seed = int.from_bytes(seed_bytes, "big") & 0x7FFFFFFF

        # 2. Assemble prompt from game state
        prompt = request.to_prompt()

        # 3. Check cache
        key = _cache_key(request.thought, request.archetype, request.rarity.value)
        cached = self._check_cache(key)
        if cached:
            return ArtResult(
                path=cached["full_path"],
                prompt=prompt,
                seed=seed,
                bytes_len=cached.get("full_size", 0),
            )

        # 4. Generate image (try FAL.ai first, fallback to placeholder)
        full_path = self._full_path(key)
        thumb_path = self._thumb_path(key)

        if not self._api_key and self._client is None:
            # No API key and no fake client — generate placeholder
            img_bytes = self._generate_placeholder(key, request.rarity, request.archetype)
            source = "placeholder"
        elif self._client is not None:
            # Test mode: use injected fake client
            try:
                result = self._client.subscribe("fal-ai/flux/schnell", {
                    "prompt": prompt,
                    "image_size": "square",
                    "num_images": 1,
                    "seed": seed,
                })
                images = result.get("images", [])
                if isinstance(images, list) and images:
                    image_url = images[0].get("url", "")
                    if image_url:
                        img_req = Request(image_url, headers={"User-Agent": "Terramon/1.0"})
                        img_bytes = urlopen(img_req, timeout=_FAL_TIMEOUT).read()
                        source = "api"
                    else:
                        img_bytes = self._generate_placeholder(key, request.rarity, request.archetype)
                        source = "placeholder"
                else:
                    img_bytes = self._generate_placeholder(key, request.rarity, request.archetype)
                    source = "placeholder"
            except Exception:
                img_bytes = self._generate_placeholder(key, request.rarity, request.archetype)
                source = "placeholder"
        else:
            # Production mode: call FAL.ai with retries
            try:
                img_bytes = _fal_request(self._api_key, prompt, seed)
                source = "api"
            except RuntimeError:
                img_bytes = self._generate_placeholder(key, request.rarity, request.archetype)
                source = "placeholder"

        # 5. Augment and save
        full_size, thumb_size = _augment_and_save(img_bytes, Path(full_path), Path(thumb_path))

        # 6. Register metadata
        _register_image(
            self._registry_path, key, prompt,
            request.archetype, request.rarity.value,
            full_path, str(thumb_path),
            full_size, thumb_size,
            source=source,
        )

        return ArtResult(
            path=full_path,
            prompt=prompt,
            seed=seed,
            bytes_len=full_size,
        )

    # -- internal helpers ---------------------------------------------------

    def _check_cache(self, key: str) -> dict | None:
        """Return cached registry entry if the image file exists on disk."""
        registry = _load_registry(self._registry_path)
        entry = registry.get(key)
        if entry and Path(entry.get("full_path", "")).exists():
            return entry
        return None

    def _full_path(self, key: str) -> str:
        return str(self._out_dir / f"portrait_{key}.png")

    def _thumb_path(self, key: str) -> str:
        self._thumb_dir.mkdir(parents=True, exist_ok=True)
        return str(self._thumb_dir / f"thumb_{key}.png")

    def _generate_placeholder(
        self, key: str, rarity: Rarity, archetype: str
    ) -> bytes:
        """Generate a local placeholder image when FAL.ai is unavailable."""
        svg = _make_placeholder_svg(key, rarity, archetype)
        return _svg_to_png(svg)


# ---------------------------------------------------------------------------
# Convenience function — compatible with the existing portrait_gen interface
# ---------------------------------------------------------------------------


def generate_portrait(
    thought: str,
    archetype: str,
    rarity: str,
    out_dir: str = "data/creatures",
) -> str:
    """Generate a creature portrait (backward-compatible interface).

    Wraps FalArtGenerator for callers that use the old function signature.
    The old portrait_gen.py used uuid-based filenames; this version uses
    content-addressable cache keys, so repeated calls return the same path.
    """
    rarity_enum = Rarity(rarity) if isinstance(rarity, str) else rarity
    request = ArtRequest(thought=thought, archetype=archetype, rarity=rarity_enum)
    gen = FalArtGenerator(out_dir=out_dir)
    result = gen.generate(request)
    return result.path
