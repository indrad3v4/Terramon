"""Offline tests for the terramon.agents package (AgentCore).

All 9 tests are pure-stdlib and network-free: llm_call is always a fake
function injected into the reflection / planning / GameMaster code paths
— nothing is ever imported from an LLM provider.
"""

from datetime import date

from terramon.agents.memory_stream import MemoryStream
from terramon.agents.planner import DailyPlan, make_daily_plan, simulate_offline
from terramon.agents.reflection import generate_reflection
from terramon.agents.world_gm import GameMaster, nearby_creatures

INSIGHT = "Я понял(а), что боюсь не одиночества, а того, что меня забудут."


def _fake_llm(prompt, system):
    return INSIGHT


class _GeoCreature:
    """Object-shaped creature (dicts are also supported by nearby_creatures)."""

    def __init__(self, name, lat, lon):
        self.name = name
        self.lat = lat
        self.lon = lon


def test_memory_add_and_retrieve():
    stream = MemoryStream()
    texts = [
        "the creature ate a berry",
        "a cat crossed the road",
        "rain fell all night",
        "the moon was full",
        "a fox visited the garden",
    ]
    for text in texts:
        stream.add(text, importance=5)

    top = stream.retrieve("a fox visited the garden", k=5)[0]
    assert top.text == texts[-1]  # exact lexical match wins on relevance


def test_memory_importance_boost():
    stream = MemoryStream()
    stream.add("the wind blew through the pines", importance=3)
    stream.add("a river carried old leaves downstream", importance=10)

    # Weak query: no lexical overlap with either entry -> relevance ~ 0,
    # so the 10-importance entry must outrank the 3-importance one.
    top = stream.retrieve("zzz qqq xyzzy", k=2)[0]
    assert top.importance == 10


def test_reflection_generated_and_stored():
    stream = MemoryStream()
    for i in range(5):
        stream.add(f"наблюдение {i}: птицы улетели на юг", importance=6)

    text = stream.maybe_reflect(llm_call=_fake_llm)
    assert text == INSIGHT

    reflections = [e for e in stream.entries if e.kind == "reflection"]
    assert len(reflections) == 1
    assert reflections[0].importance >= 8


def test_reflection_fallback_on_failure():
    stream = MemoryStream()
    stream.add("я потерял(а) свой единственный тёплый шарф", importance=9)
    stream.add("кто-то оставил следы у порога", importance=2)

    def _bad_llm(prompt, system):
        raise RuntimeError("no network")

    # LLM raises -> deterministic fallback from the highest-importance entry.
    text = generate_reflection(stream, _bad_llm)
    assert text == "Мне важно помнить: я потерял(а) свой единственный тёплый шарф"

    # LLM returns None -> same fallback, no crash.
    text2 = generate_reflection(stream, lambda p, s: None)
    assert text2.startswith("Мне важно помнить:")


def test_planner_makes_plan():
    stream = MemoryStream()
    plan = make_daily_plan(stream, "fear", llm_call=_fake_llm)

    assert isinstance(plan, DailyPlan)
    assert 3 <= len(plan.activities) <= 5
    assert plan.summary
    assert plan.date == date.today().isoformat()
    assert "искать безопасное место" in plan.activities  # fear -> innocent pool


def test_simulate_offline_diary():
    stream = MemoryStream()
    lines = simulate_offline(stream, 2.5, "loneliness")

    assert len(lines) >= 2  # ceil(2.5) = 3 diary lines
    assert all(isinstance(line, str) and line.strip() for line in lines)
    assert any("не было" in line for line in lines)  # 'пока тебя не было' voice


def test_gm_validates_release_irreversible():
    gm = GameMaster()

    allowed, outcome = gm.validate("release the creature", {"already_released": True})
    assert allowed is False
    assert outcome

    allowed2, _ = gm.validate("release the creature", {"already_released": False})
    assert allowed2 is True


def test_gm_geo_radius():
    anchor_lat, anchor_lon = 55.7558, 37.6173  # Москва
    creatures = [
        {"name": "близко", "lat": 55.85, "lon": 37.55},            # ~11 км
        _GeoCreature("на границе", 55.99, 37.99),                  # ~35 км
        {"name": "далеко", "lat": 59.93, "lon": 30.33},            # ~630 км
    ]

    near = nearby_creatures(anchor_lat, anchor_lon, creatures, radius_km=50)
    names = [c["name"] if isinstance(c, dict) else c.name for c in near]

    assert len(near) == 2
    assert "далеко" not in names


def test_persist_roundtrip(tmp_path):
    stream = MemoryStream()
    stream.add("первая мысль", importance=4)
    stream.add("вторая мысль", importance=7, kind="reflection", mood="calm")

    path = tmp_path / "memory.jsonl"
    stream.persist(path)
    loaded = MemoryStream.load(path)

    assert len(loaded.entries) == 2
    for original, restored in zip(stream.entries, loaded.entries):
        assert original.text == restored.text
        assert original.importance == restored.importance
        assert original.kind == restored.kind
        assert original.timestamp == restored.timestamp
        assert original.extra == restored.extra
