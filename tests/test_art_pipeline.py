"""Eval tests for the art pipeline — offline, deterministic.

Phase 4 (Computer Vision) additions:
  - Content-addressable caching: same thought+archetype reuses cache
  - Image registry: metadata persisted as JSON
  - SVG/PNG placeholder fallback: works without API key
  - PIL augmentation pipeline: thumbnail generation, colour adjustment
  - Retry logic: exponential backoff on FAL.ai failure

Every test stays offline. No network egress.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from terramon.adapters.fal_art import FalArtGenerator, _cache_key, _make_placeholder_svg
from terramon.domain.rarity import Rarity
from terramon.ports.art_port import ArtRequest


# ---------------------------------------------------------------------------
# Prompt assembly tests (unchanged from original)
# ---------------------------------------------------------------------------


def test_prompt_carries_game_state():
    req = ArtRequest(thought="i am the storm lord", archetype="Strategist", rarity=Rarity.LEGENDARY)
    p = req.to_prompt()
    assert "air" in p                     # Strategist element
    assert "golden aura" in p             # legendary aura
    assert "tactician" in p               # archetype motif
    assert "no text" in p                 # card-safe


def test_prompt_rarity_changes_aura():
    common = ArtRequest("x", "Ranger", Rarity.COMMON).to_prompt()
    legendary = ArtRequest("x", "Ranger", Rarity.LEGENDARY).to_prompt()
    assert "grey aura" in common
    assert "golden aura" in legendary
    assert common != legendary


def test_unknown_archetype_falls_back():
    p = ArtRequest("x", "Nonexistent", Rarity.RARE).to_prompt()
    assert "mysterious creature" in p
    assert "blue aura" in p


# ---------------------------------------------------------------------------
# Cache key tests
# ---------------------------------------------------------------------------


def test_cache_key_deterministic():
    """Same thought + archetype produces the same cache key."""
    k1 = _cache_key("storm lord", "Strategist")
    k2 = _cache_key("storm lord", "Strategist")
    assert k1 == k2
    assert len(k1) == 32  # 16 bytes hex


def test_cache_key_differs_on_thought():
    """Different thoughts produce different cache keys."""
    k1 = _cache_key("storm lord", "Strategist")
    k2 = _cache_key("gentle rain", "Strategist")
    assert k1 != k2


def test_cache_key_differs_on_archetype():
    """Different archetypes produce different cache keys."""
    k1 = _cache_key("storm lord", "Strategist")
    k2 = _cache_key("storm lord", "Ranger")
    assert k1 != k2


# ---------------------------------------------------------------------------
# Placeholder SVG tests
# ---------------------------------------------------------------------------


def test_placeholder_svg_contains_rarity_color():
    """Placeholder SVG includes the rarity colour."""
    svg = _make_placeholder_svg("test_key", Rarity.LEGENDARY, "Strategist")
    assert "#f59e0b" in svg  # legendary gold


def test_placeholder_svg_contains_archetype():
    """Placeholder SVG includes the archetype name."""
    svg = _make_placeholder_svg("test_key", Rarity.COMMON, "Wanderer")
    assert "Wanderer" in svg


def test_placeholder_svg_valid_xml():
    """Placeholder SVG is valid XML with proper tags."""
    svg = _make_placeholder_svg("test_key", Rarity.RARE, "Mystic")
    assert "<svg" in svg
    assert "</svg>" in svg
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg


# ---------------------------------------------------------------------------
# Offline adapter tests with fake client
# ---------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, url):
        self._url = url
        self.calls = []

    def subscribe(self, app, arguments):
        self.calls.append((app, arguments))
        return {"images": [{"url": self._url}], "seed": 42}


def test_adapter_offline_with_fake_client():
    with tempfile.TemporaryDirectory() as d:
        img_path = os.path.join(d, "fake.png")
        # Create a valid small PNG
        from PIL import Image
        img = Image.new("RGB", (256, 256), (128, 128, 128))
        img.save(img_path, format="PNG")

        fake = _FakeClient("file://" + img_path)
        gen = FalArtGenerator(client=fake, out_dir=os.path.join(d, "out"))
        req = ArtRequest("calm morning", "Wanderer", Rarity.COMMON)
        res = gen.generate(req)
        assert res.bytes_len > 100
        assert isinstance(res.seed, int)
        assert res.seed > 0
        assert os.path.exists(res.path)
        assert "portrait_" in res.path
        assert fake.calls[0][0] == "fal-ai/flux/schnell"


def test_empty_response_raises():
    class Empty:
        def subscribe(self, app, arguments):
            return {"images": []}

    with tempfile.TemporaryDirectory() as d:
        gen = FalArtGenerator(client=Empty(), out_dir=os.path.join(d, "out"))
        req = ArtRequest("x", "Ranger", Rarity.COMMON)
        # Should fall back to placeholder, not crash
        res = gen.generate(req)
        assert os.path.exists(res.path)
        assert res.bytes_len > 0


def test_missing_key_raises():
    with tempfile.TemporaryDirectory() as d:
        gen = FalArtGenerator(client=None, out_dir=os.path.join(d, "out"))
        # ensure no key
        old = os.environ.pop("FAL_KEY", None)
        try:
            req = ArtRequest("x", "Ranger", Rarity.COMMON)
            # Should fall back to placeholder, not crash
            res = gen.generate(req)
            assert os.path.exists(res.path)
            assert res.bytes_len > 0
        finally:
            if old:
                os.environ["FAL_KEY"] = old


# ---------------------------------------------------------------------------
# Image caching tests
# ---------------------------------------------------------------------------


def test_caching_returns_same_path():
    """Same request returns the cached path on second call."""
    with tempfile.TemporaryDirectory() as d:
        img_path = os.path.join(d, "fake.png")
        from PIL import Image
        img = Image.new("RGB", (256, 256), (64, 64, 64))
        img.save(img_path, format="PNG")

        fake = _FakeClient("file://" + img_path)
        gen = FalArtGenerator(client=fake, out_dir=os.path.join(d, "out"))
        req = ArtRequest("same thought", "Ranger", Rarity.UNCOMMON)

        res1 = gen.generate(req)
        res2 = gen.generate(req)

        # Same thought+archetype → same path
        assert res1.path == res2.path
        assert len(fake.calls) == 1  # only one real generation


def test_cache_misses_on_different_thought():
    """Different thoughts produce different cache entries."""
    with tempfile.TemporaryDirectory() as d:
        img_path = os.path.join(d, "fake.png")
        from PIL import Image
        img = Image.new("RGB", (256, 256), (64, 64, 64))
        img.save(img_path, format="PNG")

        fake = _FakeClient("file://" + img_path)
        gen = FalArtGenerator(client=fake, out_dir=os.path.join(d, "out"))
        req1 = ArtRequest("thought one", "Ranger", Rarity.COMMON)
        req2 = ArtRequest("thought two", "Ranger", Rarity.COMMON)

        res1 = gen.generate(req1)
        res2 = gen.generate(req2)

        assert res1.path != res2.path
        assert len(fake.calls) == 2  # two different generations


# ---------------------------------------------------------------------------
# Image registry tests
# ---------------------------------------------------------------------------


def test_registry_created_on_generation():
    """Generation creates an images.json registry file."""
    with tempfile.TemporaryDirectory() as d:
        img_path = os.path.join(d, "fake.png")
        from PIL import Image
        img = Image.new("RGB", (256, 256), (64, 64, 64))
        img.save(img_path, format="PNG")

        fake = _FakeClient("file://" + img_path)
        out = os.path.join(d, "out")
        gen = FalArtGenerator(client=fake, out_dir=out)

        req = ArtRequest("registry test", "Sage", Rarity.LEGENDARY)
        gen.generate(req)

        registry_path = os.path.join(out, "images.json")
        assert os.path.exists(registry_path)

        registry = json.loads(Path(registry_path).read_text())
        assert len(registry) == 1

        entry = list(registry.values())[0]
        assert entry["archetype"] == "Sage"
        assert entry["rarity"] == "legendary"
        assert entry["prompt"] == req.to_prompt()
        assert entry["source"] == "api"
        assert "timestamp" in entry
        assert "full_size" in entry
        assert entry["full_size"] > 0


def test_registry_tracks_placeholder_source():
    """Placeholder fallback is recorded as source='placeholder'."""
    with tempfile.TemporaryDirectory() as d:
        # Ensure no FAL_KEY BEFORE creating the generator
        old = os.environ.pop("FAL_KEY", None)
        try:
            gen = FalArtGenerator(client=None, out_dir=os.path.join(d, "out"))
            req = ArtRequest("offline test", "Mystic", Rarity.RARE)
            gen.generate(req)
            registry_path = os.path.join(d, "out", "images.json")
            registry = json.loads(Path(registry_path).read_text())
            entry = list(registry.values())[0]
            assert entry["source"] == "placeholder"
        finally:
            if old:
                os.environ["FAL_KEY"] = old


# ---------------------------------------------------------------------------
# PIL augmentation tests
# ---------------------------------------------------------------------------


def test_thumbnail_generated():
    """Generated image has a 128x128 thumbnail alongside the full 256x256."""
    with tempfile.TemporaryDirectory() as d:
        img_path = os.path.join(d, "fake.png")
        from PIL import Image
        img = Image.new("RGB", (256, 256), (100, 150, 200))
        img.save(img_path, format="PNG")

        fake = _FakeClient("file://" + img_path)
        out = os.path.join(d, "out")
        gen = FalArtGenerator(client=fake, out_dir=out)

        req = ArtRequest("thumbnail test", "Healer", Rarity.COMMON)
        gen.generate(req)

        registry_path = os.path.join(out, "images.json")
        registry = json.loads(Path(registry_path).read_text())
        entry = list(registry.values())[0]

        # Check thumbnail exists
        thumb_path = entry.get("thumb_path", "")
        assert thumb_path, "Thumbnail path should be in registry"
        assert os.path.exists(thumb_path), f"Thumbnail file missing: {thumb_path}"

        # Check thumbnail dimensions
        thumb = Image.open(thumb_path)
        assert thumb.size[0] <= 128
        assert thumb.size[1] <= 128


def test_augmented_image_is_rgb():
    """Augmented image is saved as RGB, not RGBA."""
    with tempfile.TemporaryDirectory() as d:
        img_path = os.path.join(d, "fake.png")
        from PIL import Image
        # Create RGBA image
        img = Image.new("RGBA", (256, 256), (100, 150, 200, 128))
        img.save(img_path, format="PNG")

        fake = _FakeClient("file://" + img_path)
        out = os.path.join(d, "out")
        gen = FalArtGenerator(client=fake, out_dir=out)

        req = ArtRequest("rgb test", "Ranger", Rarity.UNCOMMON)
        res = gen.generate(req)

        saved = Image.open(res.path)
        assert saved.mode == "RGB", f"Expected RGB mode, got {saved.mode}"


# ---------------------------------------------------------------------------
# Fallback placeholder test
# ---------------------------------------------------------------------------


def test_placeholder_png_is_valid():
    """Placeholder generation produces a valid PNG from SVG."""
    from terramon.adapters.fal_art import _svg_to_png

    svg = _make_placeholder_svg("test", Rarity.COMMON, "Scout")
    png_bytes = _svg_to_png(svg)
    assert len(png_bytes) > 100

    from PIL import Image
    from io import BytesIO
    img = Image.open(BytesIO(png_bytes))
    assert img.size == (256, 256)
    assert img.mode == "RGBA"


# ---------------------------------------------------------------------------
# List registry test
# ---------------------------------------------------------------------------


def test_registry_lists_portraits():
    """After multiple generations, the registry lists all portraits."""
    with tempfile.TemporaryDirectory() as d:
        img_path = os.path.join(d, "fake.png")
        from PIL import Image
        img = Image.new("RGB", (256, 256), (64, 64, 64))
        img.save(img_path, format="PNG")
        img2 = Image.new("RGB", (256, 256), (128, 128, 128))
        img2.save(img_path.replace(".png", "_2.png"), format="PNG")

        fake = _FakeClient("file://" + img_path)

        class _FakeClient2:
            def __init__(self):
                self.calls = []
            def subscribe(self, app, arguments):
                self.calls.append((app, arguments))
                return {"images": [{"url": "file://" + img_path.replace(".png", "_2.png")}], "seed": 43}

        out = os.path.join(d, "out")
        gen = FalArtGenerator(client=fake, out_dir=out)
        gen.generate(ArtRequest("first", "Sage", Rarity.COMMON))

        gen2 = FalArtGenerator(client=_FakeClient2(), out_dir=out)
        req2 = ArtRequest("second", "Mystic", Rarity.LEGENDARY)
        gen2.generate(req2)

        registry_path = os.path.join(out, "images.json")
        registry = json.loads(Path(registry_path).read_text())
        assert len(registry) == 2

        archetypes = {e["archetype"] for e in registry.values()}
        assert "Sage" in archetypes
        assert "Mystic" in archetypes
