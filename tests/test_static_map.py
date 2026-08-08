"""Offline tests for the self-hosted OSM static map renderer (G04).

The renderer must not touch the network in tests — OSM tile fetches are
monkeypatched to return a solid-color PNG. Coverage:

- Slippy-map math: lonlat_to_tile invariants (equator, poles, range)
- tile_url formatting
- static_map_endpoint_path (the URL that replaces Yandex Static Maps)
- render_static_map returns a valid PNG of the requested size
- disk cache: second render returns cached bytes, cache file created
- graceful fallback when every tile fetch fails (grey placeholder, still a PNG)
"""

from __future__ import annotations

import io
import os

os.environ.setdefault("TERRAMON_DATA_DIR", "/tmp/terramon_test_data")

import pytest
from PIL import Image

from terramon.adapters import static_map as sm


# ── math ───────────────────────────────────────────────────────────────

def test_lonlat_to_tile_equator_prime_meridian() -> None:
    """(0, 0) at any zoom is exactly the center of the tile grid."""
    for z in (1, 5, 14):
        x, y = sm.lonlat_to_tile(0.0, 0.0, z)
        half = 2 ** (z - 1)
        assert x == pytest.approx(half, abs=1e-6)
        assert y == pytest.approx(half, abs=1e-6)


def test_lonlat_to_tile_north_pole_top() -> None:
    """Lat 85.05 (WebMercator max) is row ~0 at the top of the world."""
    x, y = sm.lonlat_to_tile(85.05, 0.0, 14)
    assert y == pytest.approx(0.0, abs=1.0)


def test_lonlat_to_tile_range() -> None:
    """Real-world coordinates stay inside [0, 2**z)."""
    for lat, lon in [(50.06, 19.94), (-33.87, 151.21), (35.68, 139.69), (0.0, 179.9)]:
        x, y = sm.lonlat_to_tile(lat, lon, 14)
        assert 0.0 <= x < 2 ** 14
        assert 0.0 <= y < 2 ** 14


def test_tile_url_format() -> None:
    assert sm.tile_url(14, 8409, 5588) == (
        "https://tile.openstreetmap.org/14/8409/5588.png"
    )


# ── endpoint path ──────────────────────────────────────────────────────

def test_endpoint_path_replaces_yandex() -> None:
    """The TMA image src must be our local endpoint, not a Yandex URL."""
    url = sm.static_map_endpoint_path(50.0619, 19.9369, zoom=14, width=280, height=160)
    assert url.startswith("/static-map?")
    assert "lat=50.0619" in url and "lon=19.9369" in url
    assert "w=280" in url and "h=160" in url
    assert "yandex" not in url.lower()


# ── rendering (offline, mocked tiles) ──────────────────────────────────

@pytest.fixture()
def solid_tile_png():
    """A 256x256 blue tile encoded as PNG bytes."""
    img = Image.new("RGB", (256, 256), "#2a6fdb")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _clean_cache():
    sm.clear_cache()
    yield
    sm.clear_cache()


def test_render_returns_png_of_requested_size(monkeypatch, solid_tile_png) -> None:
    monkeypatch.setattr(sm, "_fetch_tile", lambda z, x, y: solid_tile_png)
    png = sm.render_static_map(50.0619, 19.9369, zoom=14, width=300, height=200)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.size == (300, 200)
    assert img.mode == "RGB"


def test_render_caches_and_hits_cache(monkeypatch, solid_tile_png) -> None:
    calls = {"n": 0}

    def counting_fetch(z, x, y):
        calls["n"] += 1
        return solid_tile_png

    monkeypatch.setattr(sm, "_fetch_tile", counting_fetch)
    first = sm.render_static_map(50.06, 19.94, zoom=14, width=300, height=200)
    fetched_first = calls["n"]

    # second render must come from the disk cache — no new tile fetches
    second = sm.render_static_map(50.06, 19.94, zoom=14, width=300, height=200)
    assert calls["n"] == fetched_first
    assert first == second


def test_render_falls_back_to_placeholder_on_total_failure(monkeypatch) -> None:
    """All tiles fail -> still a valid PNG (grey + marker), never a broken img."""

    def failing_fetch(z, x, y):
        return None

    monkeypatch.setattr(sm, "_fetch_tile", failing_fetch)
    png = sm.render_static_map(0.0, 0.0, zoom=14, width=200, height=150)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(png))
    assert img.size == (200, 150)


def test_zoom_clamped() -> None:
    """Zoom outside [1,19] must clamp, not crash."""
    assert sm.render_static_map(0, 0, zoom=99, width=128, height=128)[:8] == b"\x89PNG\r\n\x1a\n"
    assert sm.render_static_map(0, 0, zoom=0, width=128, height=128)[:8] == b"\x89PNG\r\n\x1a\n"


def test_marker_and_attribution_present(monkeypatch, solid_tile_png) -> None:
    """The rendered map must contain the red marker pixels and attribution bar."""
    monkeypatch.setattr(sm, "_fetch_tile", lambda z, x, y: solid_tile_png)
    png = sm.render_static_map(50.0619, 19.9369, zoom=14, width=300, height=200)
    img = Image.open(io.BytesIO(png)).convert("RGB")
    px = img.load()
    cx, cy = 150, 100  # center = marker position
    # red marker core (allow for antialiasing tolerance: scan a small patch)
    reds = sum(
        1
        for dx in range(-4, 5)
        for dy in range(-4, 5)
        if px[cx + dx, cy + dy][0] > 200 and px[cx + dx, cy + dy][1] < 100
    )
    assert reds > 4, "marker not found at image center"
    # attribution bar: bottom row darkened (dark bar over blue tile)
    bottom = px[150, 195]
    assert bottom[0] < 100 and bottom[1] < 100 and bottom[2] < 100
