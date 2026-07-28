"""Tests for proximity search (G03) — Haversine-based find_nearby.

Tests both JsonMemory and SqliteMemory implementations.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from terramon.adapters.json_memory import JsonMemory, SqliteMemory
from terramon.domain.thought_seed import ThoughtSeed


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def json_mem(tmp_path: Path) -> JsonMemory:
    return JsonMemory(tmp_path / "memory.jsonl")


@pytest.fixture
def sqlite_mem(tmp_path: Path) -> SqliteMemory:
    return SqliteMemory(tmp_path / "memory.db")


def _inject(
    mem: JsonMemory | SqliteMemory,
    agent: str,
    lat: float,
    lon: float,
    *,
    thought: str = "test thought",
) -> None:
    """Insert a seed at the given coordinates."""
    mem.save_seed(ThoughtSeed.make(
        raw_input=thought,
        summoned_agent=agent,
        timestamp="2026-07-28T12:00:00Z",
        lat=lat,
        lon=lon,
    ))


# ── Shared test inputs ──────────────────────────────────────────────────

# Clean origin for deterministic Haversine (purely N-S distance)
_ORIGIN_LAT = 50.0
_ORIGIN_LON = 20.0

# Kraków coordinates for empty-memory test lookups
_KRAKOW_LAT = 50.06
_KRAKOW_LON = 19.94

# ~0.3 km north  (Δlat = 0.0027,  d = 0.3 km)
_NEAR_LAT = 50.0027
_NEAR_LON = 20.0

# ~0.7 km north  (Δlat = 0.0063,  d = 0.7 km)
_MID_LAT = 50.0063
_MID_LON = 20.0

# ~2.5 km north  (Δlat = 0.0225,  d = 2.5 km)
_FAR_LAT = 50.0225
_FAR_LON = 20.0


# ── JsonMemory tests ──────────────────────────────────────────────────


class TestJsonMemoryProximity:
    """Proximity search on the file-based JsonMemory adapter."""

    def test_empty_memory(self, json_mem: JsonMemory) -> None:
        result = json_mem.find_nearby(_KRAKOW_LAT, _KRAKOW_LON, radius_km=1.0)
        assert result == []

    def test_exact_point_found(self, json_mem: JsonMemory) -> None:
        _inject(json_mem, "Ranger", _ORIGIN_LAT, _ORIGIN_LON)
        result = json_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=1.0)
        assert len(result) == 1
        seed, dist = result[0]
        assert seed.summoned_agent == "Ranger"
        assert dist == 0.0

    def test_nearby_point_found(self, json_mem: JsonMemory) -> None:
        _inject(json_mem, "Mage", _NEAR_LAT, _NEAR_LON)
        result = json_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=1.0)
        assert len(result) == 1
        _, dist = result[0]
        assert 0.25 < dist < 0.35

    def test_far_point_excluded(self, json_mem: JsonMemory) -> None:
        _inject(json_mem, "Dragon", _FAR_LAT, _FAR_LON)
        result = json_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=1.0)
        assert result == []

    def test_mixed_distances_sorted(self, json_mem: JsonMemory) -> None:
        """Closest creature should appear first."""
        _inject(json_mem, "Far", _FAR_LAT, _FAR_LON)        # ~2.5 km
        _inject(json_mem, "Close", _MID_LAT, _MID_LON)      # ~0.7 km
        _inject(json_mem, "Here", _ORIGIN_LAT, _ORIGIN_LON) # 0.0 km
        result = json_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=1.0)
        assert len(result) == 2  # Far is excluded
        assert result[0][0].summoned_agent == "Here"
        assert result[1][0].summoned_agent == "Close"

    def test_seed_without_geo_skipped(self, json_mem: JsonMemory) -> None:
        """Seeds with lat=0, lon=0 should not appear in results."""
        _inject(json_mem, "Ghost", 0.0, 0.0)
        _inject(json_mem, "Real", _NEAR_LAT, _NEAR_LON)
        result = json_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=1.0)
        assert len(result) == 1
        assert result[0][0].summoned_agent == "Real"

    def test_larger_radius_includes_far(self, json_mem: JsonMemory) -> None:
        _inject(json_mem, "Far", _FAR_LAT, _FAR_LON)
        result_1km = json_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=1.0)
        result_3km = json_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=3.0)
        assert len(result_1km) == 0
        assert len(result_3km) == 1


# ── SqliteMemory tests ────────────────────────────────────────────────


class TestSqliteMemoryProximity:
    """Proximity search on the SQLite-based SqliteMemory adapter."""

    def test_empty_memory(self, sqlite_mem: SqliteMemory) -> None:
        result = sqlite_mem.find_nearby(_KRAKOW_LAT, _KRAKOW_LON, radius_km=1.0)
        assert result == []

    def test_exact_point_found(self, sqlite_mem: SqliteMemory) -> None:
        _inject(sqlite_mem, "Ranger", _ORIGIN_LAT, _ORIGIN_LON)
        result = sqlite_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=1.0)
        assert len(result) == 1
        seed, dist = result[0]
        assert seed.summoned_agent == "Ranger"
        assert dist == 0.0

    def test_nearby_point_found(self, sqlite_mem: SqliteMemory) -> None:
        _inject(sqlite_mem, "Mage", _NEAR_LAT, _NEAR_LON)
        result = sqlite_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=1.0)
        assert len(result) == 1
        _, dist = result[0]
        assert 0.25 < dist < 0.35

    def test_far_point_excluded(self, sqlite_mem: SqliteMemory) -> None:
        _inject(sqlite_mem, "Dragon", _FAR_LAT, _FAR_LON)
        result = sqlite_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=1.0)
        assert result == []

    def test_mixed_distances_sorted(self, sqlite_mem: SqliteMemory) -> None:
        _inject(sqlite_mem, "Far", _FAR_LAT, _FAR_LON)
        _inject(sqlite_mem, "Close", _MID_LAT, _MID_LON)
        _inject(sqlite_mem, "Here", _ORIGIN_LAT, _ORIGIN_LON)
        result = sqlite_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=1.0)
        assert len(result) == 2
        assert result[0][0].summoned_agent == "Here"
        assert result[1][0].summoned_agent == "Close"

    def test_seed_without_geo_skipped(self, sqlite_mem: SqliteMemory) -> None:
        _inject(sqlite_mem, "Ghost", 0.0, 0.0)
        _inject(sqlite_mem, "Real", _NEAR_LAT, _NEAR_LON)
        result = sqlite_mem.find_nearby(_ORIGIN_LAT, _ORIGIN_LON, radius_km=1.0)
        assert len(result) == 1
        assert result[0][0].summoned_agent == "Real"
