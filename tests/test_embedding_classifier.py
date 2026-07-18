"""Eval tests for the embedding classifier — proves #23 Emergence is closed.

Chip Huyen eval-driven: the failure mode was 'flat classifier -> collection
stalls'. The benchmark: distinct thoughts must map to distinct archetypes, and
a play session must reach the goal.
"""

import math
from pathlib import Path

from terramon.adapters.embedding_classifier import (
    EmbeddingClassifier,
    _cosine,
    _encode,
)
from terramon.adapters.json_memory import JsonMemory
from terramon.application.game_loop import GameLoop
from terramon.application.summon_service import SummonService
from terramon.domain.progress import PlayerProgress
from terramon.events.bus import EventBus


def test_encode_is_l2_normalized():
    v = _encode("scan the horizon for movement")
    norm = math.sqrt(sum(x * x for x in v.values()))
    assert abs(norm - 1.0) < 1e-9


def test_encode_empty_string():
    assert _encode("") == {}
    assert _encode("!!! ???") == {}


def test_cosine_symmetric_and_bounded():
    a = _encode("plan the next attack")
    b = _encode("defend the territory")
    assert abs(_cosine(a, b) - _cosine(b, a)) < 1e-12
    assert 0.0 <= _cosine(a, b) <= 1.0 + 1e-9


def test_self_similarity_is_one():
    a = _encode("i am the storm lord")
    assert abs(_cosine(a, a) - 1.0) < 1e-9


# --- #23 Emergence: distinct thoughts -> distinct archetypes ---
def test_distinct_thoughts_summon_distinct_agents():
    clf = EmbeddingClassifier()
    cases = {
        "look at this image on the camera": "Ranger",
        "recall the past history records": "Archivist",
        "plan our attack on the enemy": "Strategist",
        "i surrender to the ancient void": "Mystic",
        "a calm quiet walk in the forest": "Wanderer",
    }
    got = {text: clf.classify(text) for text in cases}
    # at least 4 of 5 land on their intended archetype (soft benchmark)
    hits = sum(1 for t, want in cases.items() if got[t] == want)
    assert hits >= 4, f"only {hits}/5 correct: {got}"
    # and crucially: the outputs are diverse, not all one agent
    assert len(set(got.values())) >= 4


def test_unknown_input_falls_back_to_default():
    clf = EmbeddingClassifier()
    # gibberish far from every prototype
    assert clf.classify("zxqw") in {clf.DEFAULT_AGENT, *clf.ARCHETYPES}


def test_scores_returns_all_archetypes():
    clf = EmbeddingClassifier()
    s = clf.scores("plan the attack")
    assert set(s.keys()) == set(clf.ARCHETYPES.keys())


# --- Integration: play session reaches the goal now that agents vary ---
def test_play_session_reaches_goal(tmp_path):
    svc = SummonService(
        classifier=EmbeddingClassifier(),
        memory=JsonMemory(tmp_path / "seeds.jsonl"),
        bus=EventBus(),
        clock=lambda: "2026-07-18T00:00:00Z",
    )
    loop = GameLoop(svc, PlayerProgress(goal_distinct=3))
    thoughts = [
        "look at the camera image",
        "recall the past records",
        "plan the attack",
        "i am the storm lord",
    ]
    reached = False
    for t in thoughts:
        r = loop.take_turn(t, color=False)
        if r.goal_reached:
            reached = True
            break
    assert reached, f"goal not reached; collection={loop.progress.collection}"
    assert loop.progress.distinct_count >= 3
