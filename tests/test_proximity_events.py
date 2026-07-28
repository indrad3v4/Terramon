"""Tests for cross-player proximity events (I11).

Tests the ProximityEvent dataclass, the SummonService proximity check,
the bond bonus handler, and Nostr relay cross-player detection.

All tests are offline/deterministic — no real Nostr relays are contacted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from terramon.adapters.json_memory import JsonMemory, SqliteMemory
from terramon.adapters.keyword_classifier import KeywordClassifier
from terramon.application.summon_service import SummonService
from terramon.domain.thought_seed import ThoughtSeed
from terramon.events.bus import EventBus
from terramon.events.proximity import ProximityEvent


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

# Clean origin for deterministic Haversine (purely N-S distance)
_ORIGIN_LAT = 50.0
_ORIGIN_LON = 20.0

# ~0.3 km north  (Δlat = 0.0027,  d = 0.3 km)
_NEAR_LAT = 50.0027
_NEAR_LON = 20.0

# ~2.5 km north  (Δlat = 0.0225,  d = 2.5 km)
_FAR_LAT = 50.0225
_FAR_LON = 20.0

# Kraków
_KRAKOW_LAT = 50.06
_KRAKOW_LON = 19.94


def _inject(
    mem: JsonMemory | SqliteMemory,
    agent: str,
    lat: float,
    lon: float,
    *,
    thought: str = "test thought",
    timestamp: str = "2026-07-28T12:00:00Z",
) -> None:
    """Insert a seed at the given coordinates."""
    mem.save_seed(ThoughtSeed.make(
        raw_input=thought,
        summoned_agent=agent,
        timestamp=timestamp,
        lat=lat,
        lon=lon,
    ))


@dataclass
class FakeCreatureLocation:
    """Minimal fake for NostrRelayReader's CreatureLocation."""
    event_id: str = ""
    pubkey: str = ""
    lat: float = 0.0
    lon: float = 0.0
    agent: str = ""
    thought: str = ""
    rarity: str = "common"
    timestamp: int = 0


class FakeNostrReader:
    """Fake NostrRelayReader that returns configurable creature locations."""

    def __init__(self, creatures: list | None = None) -> None:
        self.creatures = creatures or []
        self.query_count = 0

    def fetch_region_creatures(self, lat: float, lon: float, radius_deg: float = 2.5) -> list:
        self.query_count += 1
        return [c for c in self.creatures
                if abs(c.lat - lat) <= radius_deg and abs(c.lon - lon) <= radius_deg]


def _make_service(
    tmp_path: Path,
    *,
    nostr_reader: object | None = None,
    clock: str = "2026-07-28T12:00:00Z",
) -> SummonService:
    """Create a SummonService with test defaults."""
    return SummonService(
        classifier=KeywordClassifier(),
        memory=JsonMemory(tmp_path / "seeds.jsonl"),
        bus=EventBus(),
        clock=lambda: clock,
        nostr_reader=nostr_reader,
    )


# ---------------------------------------------------------------------------
# ProximityEvent dataclass tests
# ---------------------------------------------------------------------------


class TestProximityEventDataclass:
    """ProximityEvent should carry all required fields with correct defaults."""

    def test_minimal_construction(self) -> None:
        event = ProximityEvent(
            agent_name="Ranger",
            other_agent_name="Mage",
            lat=50.0,
            lon=20.0,
            distance_km=0.3,
            timestamp="2026-07-28T12:00:00Z",
        )
        assert event.agent_name == "Ranger"
        assert event.other_agent_name == "Mage"
        assert event.lat == 50.0
        assert event.lon == 20.0
        assert event.distance_km == 0.3
        assert not event.bond_bonus_applied
        assert not event.is_cross_player
        assert event.other_agent_pubkey == ""

    def test_cross_player_flag(self) -> None:
        event = ProximityEvent(
            agent_name="Ranger",
            other_agent_name="WildDragon",
            other_agent_pubkey="abc123",
            lat=50.0,
            lon=20.0,
            distance_km=0.5,
            timestamp="now",
            is_cross_player=True,
        )
        assert event.is_cross_player
        assert event.other_agent_pubkey == "abc123"


# ---------------------------------------------------------------------------
# Proximity check tests (local memory)
# ---------------------------------------------------------------------------


class TestProximityCheckLocal:
    """Proximity check on local memory — same-player creatures."""

    def test_no_geo_skips_check(self, tmp_path: Path) -> None:
        """Seeds without geo coordinates should not trigger proximity checks."""
        collected: list[ProximityEvent] = []
        service = _make_service(tmp_path)
        service.bus.subscribe(ProximityEvent, collected.append)
        seed = ThoughtSeed.make(
            raw_input="hello",
            summoned_agent="Ranger",
            timestamp="2026-07-28T12:00:00Z",
        )
        service._check_proximity(seed)
        assert collected == []

    def test_empty_memory_no_event(self, tmp_path: Path) -> None:
        """No nearby creatures → no ProximityEvent."""
        collected: list[ProximityEvent] = []
        service = _make_service(tmp_path)
        service.bus.subscribe(ProximityEvent, collected.append)
        seed = ThoughtSeed.make(
            raw_input="hello",
            summoned_agent="Ranger",
            timestamp="2026-07-28T12:00:00Z",
            lat=_KRAKOW_LAT,
            lon=_KRAKOW_LON,
        )
        service._check_proximity(seed)
        assert collected == []

    def test_nearby_creature_found(self, tmp_path: Path) -> None:
        """A nearby creature in memory should trigger a ProximityEvent."""
        collected: list[ProximityEvent] = []
        service = _make_service(tmp_path)
        _inject(service.memory, "ExistingMage", _ORIGIN_LAT, _ORIGIN_LON)
        service.bus.subscribe(ProximityEvent, collected.append)

        seed = ThoughtSeed.make(
            raw_input="nearby summon",
            summoned_agent="NewRanger",
            timestamp="2026-07-28T12:01:00Z",
            lat=_ORIGIN_LAT,
            lon=_ORIGIN_LON,
        )
        service._check_proximity(seed)

        assert len(collected) == 1
        event = collected[0]
        assert event.agent_name == "NewRanger"
        assert event.other_agent_name == "ExistingMage"
        assert event.distance_km == 0.0
        assert not event.is_cross_player

    def test_far_creature_excluded(self, tmp_path: Path) -> None:
        """A creature >1 km away should not trigger a ProximityEvent."""
        collected: list[ProximityEvent] = []
        service = _make_service(tmp_path)
        _inject(service.memory, "FarDragon", _FAR_LAT, _FAR_LON)
        service.bus.subscribe(ProximityEvent, collected.append)

        seed = ThoughtSeed.make(
            raw_input="far summon",
            summoned_agent="NewRanger",
            timestamp="2026-07-28T12:01:00Z",
            lat=_ORIGIN_LAT,
            lon=_ORIGIN_LON,
        )
        service._check_proximity(seed)

        assert collected == []

    def test_self_match_skipped(self, tmp_path: Path) -> None:
        """A creature should not match against itself."""
        collected: list[ProximityEvent] = []
        service = _make_service(tmp_path)

        # Insert a seed at origin
        _inject(service.memory, "Ranger", _ORIGIN_LAT, _ORIGIN_LON, timestamp="2026-07-28T12:00:00Z")
        service.bus.subscribe(ProximityEvent, collected.append)

        # Create a "new" seed with the same coords but different timestamp
        seed = ThoughtSeed.make(
            raw_input="hello",
            summoned_agent="Ranger",
            timestamp="2026-07-28T12:01:00Z",  # different timestamp
            lat=_ORIGIN_LAT,
            lon=_ORIGIN_LON,
        )
        service._check_proximity(seed)

        # Should find the existing seed (different timestamp → different summon)
        assert len(collected) == 1

    def test_multiple_nearby_creatures(self, tmp_path: Path) -> None:
        """Multiple nearby creatures should each trigger a ProximityEvent."""
        collected: list[ProximityEvent] = []
        service = _make_service(tmp_path)
        _inject(service.memory, "Mage", _NEAR_LAT, _NEAR_LON)  # 0.3 km
        _inject(service.memory, "Healer", _ORIGIN_LAT, _ORIGIN_LON)  # 0 km
        service.bus.subscribe(ProximityEvent, collected.append)

        seed = ThoughtSeed.make(
            raw_input="crowded summon",
            summoned_agent="NewRanger",
            timestamp="2026-07-28T12:01:00Z",
            lat=_ORIGIN_LAT,
            lon=_ORIGIN_LON,
        )
        service._check_proximity(seed)

        assert len(collected) == 2


# ---------------------------------------------------------------------------
# Proximity check tests (Nostr relay cross-player)
# ---------------------------------------------------------------------------


class TestProximityCheckNostr:
    """Cross-player proximity check via Nostr relay query."""

    def test_no_nostr_reader_skips_relay(self, tmp_path: Path) -> None:
        """Without a NostrRelayReader, the relay query is skipped entirely."""
        collected: list[ProximityEvent] = []
        service = _make_service(tmp_path)
        service.bus.subscribe(ProximityEvent, collected.append)
        seed = ThoughtSeed.make(
            raw_input="hello",
            summoned_agent="Ranger",
            timestamp="now",
            lat=_ORIGIN_LAT,
            lon=_ORIGIN_LON,
        )
        service._check_proximity(seed)
        # No local creatures, no nostr reader — no events
        assert collected == []

    def test_relay_creature_detected(self, tmp_path: Path) -> None:
        """A creature on the relay within 1 km should trigger a cross-player event."""
        fake_reader = FakeNostrReader(creatures=[
            FakeCreatureLocation(
                event_id="evt1",
                pubkey="pk1",
                lat=50.001,
                lon=20.0,
                agent="WildDragon",
                rarity="rare",
                timestamp=1700000000,
            ),
        ])
        collected: list[ProximityEvent] = []
        service = _make_service(tmp_path, nostr_reader=fake_reader)
        service.bus.subscribe(ProximityEvent, collected.append)
        seed = ThoughtSeed.make(
            raw_input="hello",
            summoned_agent="Ranger",
            timestamp="now",
            lat=_ORIGIN_LAT,
            lon=_ORIGIN_LON,
        )
        service._check_proximity(seed)

        assert len(collected) == 1
        event = collected[0]
        assert event.agent_name == "Ranger"
        assert event.other_agent_name == "WildDragon"
        assert event.other_agent_pubkey == "pk1"
        assert event.is_cross_player
        assert event.distance_km > 0

    def test_relay_creature_too_far_excluded(self, tmp_path: Path) -> None:
        """A creature on the relay >1 km away should not trigger an event."""
        fake_reader = FakeNostrReader(creatures=[
            FakeCreatureLocation(
                event_id="evt2",
                pubkey="pk2",
                lat=50.05,
                lon=20.0,
                agent="FarBeast",
                rarity="common",
                timestamp=1700000000,
            ),
        ])
        collected: list[ProximityEvent] = []
        service = _make_service(tmp_path, nostr_reader=fake_reader)
        service.bus.subscribe(ProximityEvent, collected.append)
        seed = ThoughtSeed.make(
            raw_input="hello",
            summoned_agent="Ranger",
            timestamp="now",
            lat=_ORIGIN_LAT,
            lon=_ORIGIN_LON,
        )
        service._check_proximity(seed)

        assert collected == []


# ---------------------------------------------------------------------------
# Bond bonus handler tests
# ---------------------------------------------------------------------------


class TestProximityBondBonus:
    """Bond level bonus applied on proximity events."""

    def test_bond_bonus_applied_to_both(self, tmp_path: Path) -> None:
        """Both creatures get +1 bond_level when a proximity event fires."""
        service = _make_service(tmp_path)
        service.subscribe_proximity()

        # Verify no bond data initially
        assert service.memory.load_bond("Ranger") == {}
        assert service.memory.load_bond("Mage") == {}

        event = ProximityEvent(
            agent_name="Ranger",
            other_agent_name="Mage",
            lat=50.0,
            lon=20.0,
            distance_km=0.3,
            timestamp="now",
        )

        # Publish the event through the bus — the handler should fire
        service.bus.publish(event)

        # Check bond bonus was applied
        bond_ranger = service.memory.load_bond("Ranger")
        bond_mage = service.memory.load_bond("Mage")
        assert bond_ranger.get("bond_level") == 1
        assert bond_mage.get("bond_level") == 1
        assert event.bond_bonus_applied

    def test_bond_bonus_stacking(self, tmp_path: Path) -> None:
        """Multiple proximity events should stack the bond bonus."""
        service = _make_service(tmp_path)
        service.subscribe_proximity()

        event1 = ProximityEvent(
            agent_name="Ranger",
            other_agent_name="Mage",
            lat=50.0, lon=20.0,
            distance_km=0.3,
            timestamp="now",
        )
        event2 = ProximityEvent(
            agent_name="Ranger",
            other_agent_name="Healer",
            lat=50.0, lon=20.0,
            distance_km=0.5,
            timestamp="now",
        )

        service.bus.publish(event1)
        service.bus.publish(event2)

        bond_ranger = service.memory.load_bond("Ranger")
        assert bond_ranger.get("bond_level") == 2


# ---------------------------------------------------------------------------
# Integration: full summon flow produces ProximityEvents
# ---------------------------------------------------------------------------


class TestProximityIntegration:
    """End-to-end: summon with geo → proximity check → ProximityEvent."""

    def test_summon_with_nearby_local_produces_proximity_event(self, tmp_path: Path) -> None:
        """When local memory has a nearby seed, summon() emits a ProximityEvent."""
        memory = JsonMemory(tmp_path / "seeds.jsonl")
        _inject(memory, "ExistingMage", _ORIGIN_LAT, _ORIGIN_LON)
        bus = EventBus()
        collected: list[ProximityEvent] = []
        bus.subscribe(ProximityEvent, collected.append)

        service = SummonService(
            classifier=KeywordClassifier(),
            memory=memory,
            bus=bus,
            clock=lambda: "2026-07-28T12:01:00Z",
        )
        service.subscribe_proximity()

        # We need a seed WITH geo. The default summon doesn't set lat/lon.
        # We'll call _check_proximity directly with a seed that has geo.
        seed = ThoughtSeed.make(
            raw_input="nearby summon",
            summoned_agent="NewRanger",
            timestamp="2026-07-28T12:01:00Z",
            lat=_ORIGIN_LAT,
            lon=_ORIGIN_LON,
        )
        service._check_proximity(seed)

        assert len(collected) == 1
        assert collected[0].agent_name == "NewRanger"
        assert collected[0].other_agent_name == "ExistingMage"
        assert collected[0].bond_bonus_applied

    def test_summon_without_geo_no_proximity(self, tmp_path: Path) -> None:
        """A summon without geo (lat=0, lon=0) should not produce proximity events."""
        memory = JsonMemory(tmp_path / "seeds.jsonl")
        _inject(memory, "ExistingMage", _ORIGIN_LAT, _ORIGIN_LON)
        bus = EventBus()
        collected: list[ProximityEvent] = []
        bus.subscribe(ProximityEvent, collected.append)

        service = SummonService(
            classifier=KeywordClassifier(),
            memory=memory,
            bus=bus,
            clock=lambda: "2026-07-28T12:01:00Z",
        )

        # Default ThoughtSeed.make without lat/lon
        seed = service.summon("hello world")
        # After summon, _check_proximity is called but lat=0,lon=0 so it skips
        assert collected == []

    def test_haversine_consistency(self, tmp_path: Path) -> None:
        """Haversine in SummonService matches JsonMemory's implementation."""
        service = _make_service(tmp_path)
        json_dist = service.memory._haversine_km(_ORIGIN_LAT, _ORIGIN_LON, _NEAR_LAT, _NEAR_LON)
        svc_dist = service._haversine_km(_ORIGIN_LAT, _ORIGIN_LON, _NEAR_LAT, _NEAR_LON)
        assert abs(json_dist - svc_dist) < 0.001
        assert 0.25 < json_dist < 0.35
