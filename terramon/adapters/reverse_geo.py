"""Nominatim reverse geocoding adapter — city/country for a captured point.

G03: the photo-capture path (CAPTURE in TMA) hands the summon flow raw
lat/lon; this adapter turns them into a human place name ("Kraków, Polska")
that flows into ThoughtSeed.lat/lon/place_name -> insight.geo -> the terra
map and the birthplace vision prompt.

Design (mirrors static_map.py):
  - one Nominatim request per ~1 km cell: cache key is 3-decimal lat/lon,
    entries live 30 days on disk — OSM usage policy requires restraint;
  - descriptive User-Agent, 5 s timeout;
  - NEVER raises: any failure (network, JSON, missing fields) degrades to
    "50.0647, 19.9450" coordinate text so the summon loop cannot crash.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from pathlib import Path

log = logging.getLogger("terramon.reverse_geo")

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/reverse"
    "?format=jsonv2&lat={lat:.6f}&lon={lon:.6f}&zoom=10&accept-language=ru"
)
USER_AGENT = "TerramonTMA/1.0 (github.com/indrad3v4/Terramon)"
FETCH_TIMEOUT_S = 5
CACHE_TTL_S = 30 * 24 * 3600  # cached reverse-geocode entries valid 30 days
_CACHE_KEY_DP = 3             # ~111 m per cell at the equator — plenty for a place name


def _cache_path(cache: str | Path | None) -> Path:
    """Resolve the cache JSON path (lazy so tests can pass their own)."""
    if cache is not None:
        return Path(cache)
    return Path(os.environ.get("TERRAMON_DATA_DIR", "data")) / "reverse_geo_cache.json"


def _load_cache(path: Path) -> dict:
    """Read the cache dict; corrupt/missing files degrade to {} — never raise."""
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        log.warning("reverse_geo: cache %s unreadable, starting fresh", path)
    return {}


def _save_cache(path: Path, cache: dict) -> None:
    """Best-effort disk write — a failed write must never break the caller."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except Exception:
        log.warning("reverse_geo: cache write failed for %s", path)


def _format_place(data: dict) -> str:
    """Human place name from a Nominatim jsonv2 payload.

    Prefers the address.city/town/village + country pair ("Kraków, Polska");
    falls back to display_name truncated to the first 3 comma-separated
    parts; finally to raw coordinates.
    """
    address = data.get("address") or {}
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("hamlet")
        or ""
    )
    country = address.get("country", "")
    if city and country:
        return f"{city}, {country}"
    if city:
        return city
    display_name = data.get("display_name") or ""
    if display_name:
        parts = [p.strip() for p in display_name.split(",") if p.strip()]
        return ", ".join(parts[:3])
    return ""


def reverse_geocode(lat: float, lon: float, cache: str | Path | None = None) -> str:
    """Resolve (lat, lon) to a place name, e.g. "Kraków, Polska".

    Args:
        lat, lon: WGS84 coordinates.
        cache: optional JSON cache file path. Defaults to
            data/reverse_geo_cache.json (TERRAMON_DATA_DIR aware).

    Returns:
        A place name if Nominatim answered, otherwise "lat, lon" formatted
        to 4 decimals. NEVER raises.
    """
    key = f"{lat:.{_CACHE_KEY_DP}f},{lon:.{_CACHE_KEY_DP}f}"
    path = _cache_path(cache)
    cache_dict = _load_cache(path)

    entry = cache_dict.get(key)
    if entry is not None and isinstance(entry, dict):
        try:
            age = time.time() - float(entry.get("ts", 0))
            place = entry.get("place", "")
            if age < CACHE_TTL_S and place:
                return place
        except Exception:
            pass  # stale/corrupt entry — refetch

    url = NOMINATIM_URL.format(lat=lat, lon=lon)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        place = _format_place(payload)
    except Exception as exc:  # network/JSON failures must never crash the summon
        log.warning("reverse_geo: Nominatim lookup failed for %s: %s", key, exc)
        place = ""

    if not place:
        return f"{lat:.4f}, {lon:.4f}"

    cache_dict[key] = {"place": place, "ts": time.time()}
    _save_cache(path, cache_dict)
    return place


def clear_cache(cache: str | Path | None = None) -> None:
    """Test helper — wipe the reverse-geocode cache file."""
    path = _cache_path(cache)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
