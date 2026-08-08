"""OSM static map renderer — self-hosted replacement for dead third-party APIs.

Why this exists:
    staticmap.openstreetmap.de was shut down by OSM (DNS dead since 2024) and the
    hotfix swapped in Yandex Static Maps. This adapter removes the Russian
    dependency entirely: it stitches plain OSM raster tiles (tile.openstreetmap.org)
    into a PNG on our own server, caches tiles + finished maps on disk, and serves
    them from a local endpoint. One map source (OSM) for the whole game: the
    Leaflet global map (I11) and every birthplace thumbnail (G04).

Policy compliance:
    tile.openstreetmap.org requires a descriptive User-Agent and no heavy use.
    We send one, cache aggressively (tiles 30d, maps 7d), and keep the rendered
    images small (<=512px). Attribution is painted on every map.

Usage:
    render_static_map(lat, lon, zoom=14, width=300, height=200) -> bytes (PNG)
    static_map_endpoint_path(lat, lon, zoom, width, height) -> "/static-map?lat=..&.."
"""

from __future__ import annotations

import io
import logging
import math
import os
import time
import urllib.request
from pathlib import Path

log = logging.getLogger("terramon.static_map")

# ── constants ──────────────────────────────────────────────────────────
TILE_SIZE = 256
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "TerramonTMA/1.0 (https://github.com/indrad3v4/Terramon; contact via repo)"
TILE_TTL_S = 30 * 24 * 3600      # cached tiles are valid 30 days
MAP_TTL_S = 7 * 24 * 3600        # finished stitched maps valid 7 days
FETCH_TIMEOUT_S = 8
HTTP_OK = 200

_DATA_DIR = Path(os.environ.get("TERRAMON_DATA_DIR", "data")) / "static_maps"
_TILE_CACHE = _DATA_DIR / "tiles"
_MAP_CACHE = _DATA_DIR / "maps"


def _cache_dir() -> tuple[Path, Path]:
    """Resolve cache dirs (lazy so tests can point TERRAMON_DATA_DIR elsewhere)."""
    data = Path(os.environ.get("TERRAMON_DATA_DIR", "data")) / "static_maps"
    return data / "tiles", data / "maps"


# ── slippy-map math (pure, offline-testable) ───────────────────────────
def lonlat_to_tile(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Exact (fractional) tile coordinates for a lat/lon at zoom (slippy map)."""
    n = 2 ** zoom
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def tile_url(z: int, x: int, y: int) -> str:
    return TILE_URL.format(z=z, x=x, y=y)


# ── tile fetching with disk cache ──────────────────────────────────────
def _fetch_tile(z: int, x: int, y: int) -> bytes | None:
    """Download one OSM tile, caching it on disk for TILE_TTL_S."""
    tiles_dir, _ = _cache_dir()
    tile_path = tiles_dir / f"{z}" / f"{x}" / f"{y}.png"

    if tile_path.exists():
        age = time.time() - tile_path.stat().st_mtime
        if age < TILE_TTL_S:
            return tile_path.read_bytes()

    req = urllib.request.Request(
        tile_url(z, x, y), headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
            if resp.status != HTTP_OK:
                log.warning("OSM tile %s -> HTTP %s", tile_url(z, x, y), resp.status)
                return None
            data = resp.read()
    except Exception as exc:  # network errors must not break the game loop
        log.warning("OSM tile fetch failed %s: %s", tile_url(z, x, y), exc)
        return None

    tile_path.parent.mkdir(parents=True, exist_ok=True)
    tile_path.write_bytes(data)
    return data


# ── rendering ──────────────────────────────────────────────────────────
def _draw_marker(draw, cx: int, cy: int) -> None:
    """Red dot with white ring — the creature's birthplace."""
    r = 6
    draw.ellipse((cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2), fill="white")
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill="#ef4444")


def _draw_attribution(img, draw, text: str = "© OpenStreetMap contributors") -> None:
    """Paint OSM attribution as a small dark bar at the bottom."""
    try:
        from PIL import ImageFont
        font = ImageFont.load_default()
        w, h = img.size
        draw.rectangle((0, h - 14, w, h), fill=(0, 0, 0, 140))
        draw.text((4, h - 12), text, fill="white", font=font)
    except Exception:
        pass  # attribution is best-effort; the Leaflet map already shows it


def render_static_map(
    lat: float,
    lon: float,
    zoom: int = 14,
    width: int = 300,
    height: int = 200,
) -> bytes:
    """Stitch OSM tiles around (lat, lon) into a centered PNG with a marker.

    Returns raw PNG bytes. On total tile failure returns a grey placeholder
    with the marker still drawn (so the TMA never shows a broken image icon).
    """
    from PIL import Image, ImageDraw

    tiles_dir, maps_dir = _cache_dir()
    zoom = max(1, min(int(zoom), 19))
    width = max(64, min(int(width), 512))
    height = max(64, min(int(height), 512))

    # cache key — coarse-coordinate the map so nearby creatures reuse one file
    key_lat, key_lon = round(lat, 3), round(lon, 3)
    map_path = maps_dir / f"{key_lat}_{key_lon}_z{zoom}_{width}x{height}.png"
    if map_path.exists():
        age = time.time() - map_path.stat().st_mtime
        if age < MAP_TTL_S:
            return map_path.read_bytes()

    tx, ty = lonlat_to_tile(lat, lon, zoom)
    max_tile = 2 ** zoom - 1
    tile_x = int(math.floor(tx))
    tile_y = int(math.floor(ty))
    # clamp to the valid WebMercator grid (poles/antimeridian edge cases)
    tile_x = max(0, min(tile_x, max_tile))
    tile_y = max(0, min(tile_y, max_tile))
    off_x = int(round((tx - tile_x) * TILE_SIZE))   # pixel offset of the point
    off_y = int(round((ty - tile_y) * TILE_SIZE))

    # tiles needed around the point to cover width x height
    k = max(1, math.ceil(max(width, height) / 2 / TILE_SIZE) + 1)

    # gather tile pixels in parallel (worst case = one fetch timeout,
    # not N timeouts); missing tiles -> None, filled grey later
    span = 2 * k + 1
    coords = [
        (zoom, tile_x + dx, tile_y + dy)
        for dy in range(-k, k + 1)
        for dx in range(-k, k + 1)
    ]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(8, len(coords))) as pool:
        fetched = list(pool.map(lambda c: _fetch_tile(*c), coords))

    rows: list[list[bytes | None]] = [
        fetched[i * span:(i + 1) * span] for i in range(span)
    ]
    canvas = Image.new("RGB", (span * TILE_SIZE, span * TILE_SIZE), "#e5e7eb")
    draw = ImageDraw.Draw(canvas)
    any_tile = False
    for i, row in enumerate(rows):
        for j, data in enumerate(row):
            if data is None:
                continue
            any_tile = True
            try:
                tile_img = Image.open(io.BytesIO(data)).convert("RGB")
            except Exception:
                continue
            canvas.paste(tile_img, (j * TILE_SIZE, i * TILE_SIZE))

    # center the point inside the canvas, then crop to requested size
    cx = k * TILE_SIZE + off_x
    cy = k * TILE_SIZE + off_y
    left = max(0, min(cx - width // 2, span * TILE_SIZE - width))
    top = max(0, min(cy - height // 2, span * TILE_SIZE - height))
    crop = canvas.crop((left, top, left + width, top + height))
    draw = ImageDraw.Draw(crop)
    _draw_marker(draw, width // 2, height // 2)
    _draw_attribution(crop, draw)

    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    png = buf.getvalue()

    if any_tile:
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_bytes(png)
    return png


def static_map_endpoint_path(
    lat: float, lon: float, zoom: int = 14, width: int = 300, height: int = 200
) -> str:
    """Local URL for the birthplace thumbnail (replaces the Yandex URL)."""
    return f"/static-map?lat={lat}&lon={lon}&zoom={zoom}&w={width}&h={height}"


def clear_cache() -> None:
    """Test helper — wipe all cached tiles/maps."""
    tiles_dir, maps_dir = _cache_dir()
    for d in (tiles_dir, maps_dir):
        if d.exists():
            import shutil
            shutil.rmtree(d, ignore_errors=True)
