"""G03 geo-capture pipeline tests — offline, zero network.

Covers: geo threading through summon -> seed -> insight -> event,
reverse-geocoding with disk cache + coordinate fallback, GameLoop geo
pass-through, and coordinate validation. All network I/O is monkeypatched.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import terramon.adapters.reverse_geo as reverse_geo
from terramon.adapters.json_memory import JsonMemory
from terramon.adapters.keyword_classifier import KeywordClassifier
from terramon.application.game_loop import GameLoop
from terramon.application.geo_utils import _validate_coords
from terramon.application.summon_service import SummonService
from terramon.domain.insight import GeoContext
from terramon.domain.thought_seed import ThoughtSeed
from terramon.events.agent_summoned import AgentSummoned
from terramon.events.bus import EventBus


# ── summon → seed → insight → event ─────────────────────────────────────

def test_summon_with_geo_anchors_seed(tmp_path: Path) -> None:
    """A summon with a GeoContext anchors lat/lon/place on seed, insight, event."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    received: list[AgentSummoned] = []
    bus.subscribe(AgentSummoned, received.append)
    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now")

    geo = GeoContext(50.06, 19.94, "Kraków, Poland")
    seed = service.summon("help me take care of this", geo=geo)

    # seed anchored
    assert seed.lat == 50.06
    assert seed.lon == 19.94
    assert seed.place_name == "Kraków, Poland"
    # insight carries the same geo
    assert seed.insight is not None and seed.insight.geo is not None
    assert seed.insight.geo.lat == 50.06
    assert seed.insight.geo.lon == 19.94
    assert seed.insight.geo.place_name == "Kraków, Poland"
    # event carries the geo hint for the terra map
    assert len(received) == 1
    assert received[0].geo_hint == "Kraków, Poland"
    assert memory.load_all_seeds() == [seed]


def test_summon_without_geo_degrades(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No geo -> zero anchor, seed saved, proximity skipped, event still fires."""
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    received: list[AgentSummoned] = []
    bus.subscribe(AgentSummoned, received.append)

    # spy: find_nearby must NOT be called when the seed has no coordinates
    calls: list = []
    original_find_nearby = memory.find_nearby
    memory.find_nearby = lambda *a, **k: calls.append(a) or original_find_nearby(*a, **k)

    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now")
    seed = service.summon("hello world")

    assert seed.lat == 0.0
    assert seed.lon == 0.0
    assert seed.place_name == ""
    assert memory.load_all_seeds() == [seed]
    assert calls == []  # _check_proximity early-returns on (0, 0)
    assert len(received) == 1  # summon still publishes its event


# ── reverse_geocode adapter ─────────────────────────────────────────────

class _FakeResponse:
    """Minimal context-manager response stand-in for urllib.urlopen."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def test_reverse_geocode_success_and_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """First call hits Nominatim, second call is served from the disk cache."""
    payload = {
        "display_name": "Kraków, Polska, Polska",
        "address": {"city": "Kraków", "country": "Polska"},
    }
    urls: list[str] = []

    def fake_urlopen(req, timeout=None):
        urls.append(req.full_url)
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(reverse_geo.urllib.request, "urlopen", fake_urlopen)

    cache_file = tmp_path / "reverse_geo_cache.json"
    first = reverse_geo.reverse_geocode(50.0617, 19.9372, cache=cache_file)
    second = reverse_geo.reverse_geocode(50.0617, 19.9372, cache=cache_file)

    assert first == "Kraków, Polska"
    assert second == "Kraków, Polska"
    assert len(urls) == 1  # cache served the second call
    assert "lat=50.061700" in urls[0]
    assert "accept-language=ru" in urls[0]
    assert cache_file.exists()


def test_reverse_geocode_fallback_on_network_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Network failure degrades to coordinates — summon keeps working."""
    def boom(req, timeout=None):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(reverse_geo.urllib.request, "urlopen", boom)

    place = reverse_geo.reverse_geocode(50.0647, 19.9450, cache=tmp_path / "c.json")
    assert place == "50.0647, 19.9450"

    # and the summon flow survives it too
    memory = JsonMemory(tmp_path / "memory.jsonl")
    bus = EventBus()
    service = SummonService(KeywordClassifier(), memory, bus, lambda: "now")
    seed = service.summon("hello world", geo=GeoContext(50.0647, 19.9450))

    assert seed.lat == 50.0647
    assert seed.lon == 19.9450
    assert seed.place_name == "50.0647, 19.9450"
    assert seed.insight is not None and seed.insight.geo is not None
    assert seed.insight.geo.place_name == "50.0647, 19.9450"


# ── GameLoop geo pass-through ───────────────────────────────────────────

def test_game_loop_passes_geo_through() -> None:
    """take_turn(geo=...) hands the exact GeoContext to service.summon."""
    service = MagicMock()
    seed = ThoughtSeed.make(
        raw_input="hello world",
        summoned_agent="Innocent",
        timestamp="2026-08-09T00:00:00",
    )
    service.summon.return_value = seed
    loop = GameLoop(service=service)

    geo = GeoContext(50.06, 19.94, "Kraków, Poland")
    result = loop.take_turn("hello world", geo=geo)

    service.summon.assert_called_once_with("hello world", rare_boost=0.0, geo=geo)
    assert result.agent == "Innocent"


# ── coordinate validation ───────────────────────────────────────────────

def test_validate_coords_rejects_out_of_range() -> None:
    """Only finite in-range WGS84 pairs become tuples; everything else is None."""
    assert _validate_coords(91, 200) is None          # both out of range
    assert _validate_coords(50.0, 200) is None        # lon out of range
    assert _validate_coords(91, 20.0) is None         # lat out of range
    assert _validate_coords(None, None) is None
    assert _validate_coords(float("nan"), 0.0) is None
    assert _validate_coords(50.06, 19.94) == (50.06, 19.94)
    assert _validate_coords(-90.0, -180.0) == (-90.0, -180.0)  # boundary ok
    assert _validate_coords("50.06", "19.94") == (50.06, 19.94)  # strings parse
