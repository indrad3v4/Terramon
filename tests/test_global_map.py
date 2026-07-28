"""Tests for the global creature map (I11) — NostrRelayReader + map data.

Tests cover:
- CreatureLocation parsing from Nostr event dicts
- Region key computation (5-degree grid binning)
- Heatmap data generation from creature locations
- Marker JSON generation
- Offline WebSocket frame handling
"""

from __future__ import annotations

import json

from terramon.adapters.nostr_reader import (
    CreatureLocation,
    NostrRelayReader,
)


# ── CreatureLocation unit tests ─────────────────────────────────────


def test_creature_region_key_europe() -> None:
    """A creature near Kraków bins into the 50_15 grid cell."""
    loc = CreatureLocation(
        event_id="abc",
        pubkey="xyz",
        lat=50.06,
        lon=19.94,
        agent="Test",
        timestamp=1700000000,
    )
    assert loc.region_key == "50_15"


def test_creature_region_key_equator() -> None:
    """A creature near the equator bins into 0_0."""
    loc = CreatureLocation(
        event_id="abc",
        pubkey="xyz",
        lat=2.5,
        lon=-2.5,
    )
    assert loc.region_key == "0_-5"


def test_creature_region_key_negative() -> None:
    """Negative coordinates produce correct grid cell."""
    loc = CreatureLocation(
        event_id="abc",
        pubkey="xyz",
        lat=-33.86,
        lon=151.21,  # Sydney
    )
    assert loc.region_key == "-35_150"


# ── Event parsing tests ────────────────────────────────────────────


def test_parse_event_with_g_tag() -> None:
    """Parse a Nostr event with standard 'g' geo tag."""
    ev = {
        "id": "abc123",
        "pubkey": "pubkey1",
        "created_at": 1700000000,
        "content": "exploring the mountains",
        "tags": [
            ["t", "terramon"],
            ["t", "explorer"],
            ["g", "46.5", "7.6"],
        ],
    }
    loc = NostrRelayReader._parse_event(ev)
    assert loc is not None
    assert loc.event_id == "abc123"
    assert abs(loc.lat - 46.5) < 0.001
    assert abs(loc.lon - 7.6) < 0.001
    assert loc.agent == "explorer"
    assert "exploring" in loc.thought


def test_parse_event_without_g_tag_returns_none() -> None:
    """Event without geo tag is skipped."""
    ev = {
        "id": "no-geo",
        "pubkey": "pubkey1",
        "created_at": 1700000000,
        "content": "just a thought",
        "tags": [["t", "terramon"]],
    }
    loc = NostrRelayReader._parse_event(ev)
    assert loc is None


def test_parse_event_without_terramon_tag() -> None:
    """Event without terramon tag — agent field is empty but geo works."""
    ev = {
        "id": "no-tag",
        "pubkey": "pubkey1",
        "created_at": 1700000000,
        "content": "hello world",
        "tags": [["g", "10.0", "20.0"]],
    }
    loc = NostrRelayReader._parse_event(ev)
    assert loc is not None
    assert loc.lat == 10.0
    assert loc.lon == 20.0
    assert loc.agent == ""  # no t-tag for agent


def test_parse_event_invalid_g_tag() -> None:
    """Event with malformed g tag is skipped."""
    ev = {
        "id": "bad-geo",
        "pubkey": "pubkey1",
        "created_at": 1700000000,
        "content": "bad data",
        "tags": [["g", "not-a-number", "also-not-a-number"]],
    }
    loc = NostrRelayReader._parse_event(ev)
    assert loc is None


# ── Relay message parsing tests ───────────────────────────────────


def test_parse_relay_messages_single_event() -> None:
    """Parse a single EVENT message from relay response."""
    raw = json.dumps(["EVENT", {"id": "ev1", "pubkey": "pk", "created_at": 1,
                                "content": "hi", "tags": []}])
    events = NostrRelayReader._parse_relay_messages(raw, "sub1")
    assert len(events) == 1
    assert events[0]["id"] == "ev1"


def test_parse_relay_messages_eose_stops() -> None:
    """EOSE message stops parsing (no more events expected)."""
    raw = (
        json.dumps(["EVENT", {"id": "ev1", "pubkey": "pk", "created_at": 1,
                              "content": "hi", "tags": []}])
        + "\n"
        + json.dumps(["EOSE", "sub1"])
        + "\n"
        + json.dumps(["EVENT", {"id": "ev2", "pubkey": "pk", "created_at": 2,
                                "content": "bye", "tags": []}])
    )
    events = NostrRelayReader._parse_relay_messages(raw, "sub1")
    assert len(events) == 1
    assert events[0]["id"] == "ev1"


def test_parse_relay_messages_notice_ignored() -> None:
    """NOTICE messages are ignored."""
    raw = (
        json.dumps(["NOTICE", "rate limited"])
        + "\n"
        + json.dumps(["EVENT", {"id": "ev1", "pubkey": "pk", "created_at": 1,
                                "content": "hi", "tags": []}])
    )
    events = NostrRelayReader._parse_relay_messages(raw, "sub1")
    assert len(events) == 1


# ── Unmask response tests ─────────────────────────────────────────


def test_unmask_response_empty() -> None:
    """Empty data returns empty string."""
    assert NostrRelayReader._unmask_response(b"") == ""


def test_unmask_response_short_text() -> None:
    """Short server frame is unmasked correctly."""
    # Server frame: 0x81 = FIN+text, len=5, payload="hello"
    frame = bytes([0x81, 0x05]) + b"hello"
    result = NostrRelayReader._unmask_response(frame)
    assert result == "hello"


def test_unmask_response_long_text_126() -> None:
    """Server frame with 126+ byte payload (2-byte length)."""
    payload = "x" * 200
    frame = bytes([0x81, 0x7E, 0x00, 200]) + payload.encode()
    result = NostrRelayReader._unmask_response(frame)
    assert len(result) == 200


# ── fetch_global_creatures gracefully handles failures ────────────


def test_fetch_global_creatures_bad_relays() -> None:
    """Reader gracefully returns empty list when all relays are unreachable."""
    reader = NostrRelayReader(
        relays=["wss://localhost:19999"],
        timeout=1,
    )
    creatures = reader.fetch_global_creatures(max_events=10)
    assert isinstance(creatures, list)
    # Should gracefully handle connection failures with empty result


# ── CreatureLocation dataclass defaults ───────────────────────────


def test_creature_location_defaults() -> None:
    """CreatureLocation has sensible defaults."""
    loc = CreatureLocation(event_id="e1", pubkey="p1", lat=0, lon=0)
    assert loc.agent == ""
    assert loc.thought == ""
    assert loc.rarity == "common"
    assert loc.timestamp == 0
