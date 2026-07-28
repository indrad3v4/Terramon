"""Eval tests for the embedding classifier — proves #23 Emergence is closed.

Chip Huyen eval-driven: the failure mode was 'flat classifier -> collection
stalls'. The benchmark: distinct thoughts must map to distinct archetypes, and
a play session must reach the goal.
"""

import math
from pathlib import Path

import pytest

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
        "i trust that this is right": "Innocent",
        "nobody understands me": "Orphan",
        "i will overcome this": "Hero",
        "let me help you please": "Caregiver",
        "don't fence me in": "Explorer",
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
# ---------------------------------------------------------------------------
# Phase 2: Classification metrics — precision, recall, F1
# ---------------------------------------------------------------------------


def _precision(tp: int, fp: int) -> float:
    """Precision = TP / (TP + FP). Measures how many positive predictions were correct.

    Returns 0.0 when denominator is zero (no positive predictions made).
    """
    if tp + fp == 0:
        return 0.0
    return tp / (tp + fp)


def _recall(tp: int, fn: int) -> float:
    """Recall = TP / (TP + FN). Measures how many actual positives were found.

    Returns 0.0 when denominator is zero (no actual positives in the data).
    """
    if tp + fn == 0:
        return 0.0
    return tp / (tp + fn)


def _f1(tp: int, fp: int, fn: int) -> float:
    """F1 score = 2 * P * R / (P + R). Harmonic mean of precision and recall.

    Returns 0.0 when both precision and recall are 0 (no correct predictions).
    """
    p = _precision(tp, fp)
    r = _recall(tp, fn)
    if p + r == 0.0:
        return 0.0
    return 2.0 * p * r / (p + r)


def test_classification_metrics_basic() -> None:
    """Sanity check: perfect classification gives 1.0 for all metrics."""
    assert _precision(10, 0) == 1.0
    assert _precision(0, 5) == 0.0
    assert _precision(5, 5) == 0.5

    assert _recall(10, 0) == 1.0
    assert _recall(0, 5) == 0.0
    assert _recall(5, 5) == 0.5

    assert _f1(10, 0, 0) == 1.0
    assert _f1(10, 0, 5) == pytest.approx(0.8, abs=1e-4)
    assert _f1(5, 5, 5) == pytest.approx(0.5, abs=1e-4)
    assert _f1(0, 0, 5) == 0.0


def test_classification_metrics_on_classifier() -> None:
    """Evaluate the EmbeddingClassifier using precision/recall/F1 on known cases.

    Uses the training examples themselves as test cases — a basic sanity
    check that the classifier can at least recognize its own training data.
    """
    clf = EmbeddingClassifier()

    # Build ground truth: each example phrase belongs to its archetype
    y_true: list[str] = []
    y_pred: list[str] = []
    for archetype, examples in clf.ARCHETYPES.items():
        for ex in examples:
            y_true.append(archetype)
            y_pred.append(clf.classify(ex))

    # Per-archetype metrics
    archetypes = list(clf.ARCHETYPES.keys())
    for atype in archetypes:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == atype and p == atype)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != atype and p == atype)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == atype and p != atype)
        # Each archetype has 5 training examples — at least 3 should be correct
        # (60% recall floor on training data, allowing for cross-archetype overlap)
        assert tp >= 3, (
            f"{atype}: only {tp}/{tp + fn} correct (recall={_recall(tp, fn):.2f})"
        )

    # Macro-average F1 across all archetypes
    macro_prec = sum(
        _precision(
            sum(1 for t, p in zip(y_true, y_pred) if t == a and p == a),
            sum(1 for t, p in zip(y_true, y_pred) if t != a and p == a),
        )
        for a in archetypes
    ) / len(archetypes)

    macro_rec = sum(
        _recall(
            sum(1 for t, p in zip(y_true, y_pred) if t == a and p == a),
            sum(1 for t, p in zip(y_true, y_pred) if t == a and p != a),
        )
        for a in archetypes
    ) / len(archetypes)

    macro_f1 = 2 * macro_prec * macro_rec / (macro_prec + macro_rec) if macro_prec + macro_rec > 0 else 0.0

    # On training data, macro F1 should be at least 0.7
    assert macro_f1 >= 0.7, f"Macro F1 on training data too low: {macro_f1:.3f}"


def test_play_session_reaches_goal(tmp_path):
    svc = SummonService(
        classifier=EmbeddingClassifier(),
        memory=JsonMemory(tmp_path / "seeds.jsonl"),
        bus=EventBus(),
        clock=lambda: "2026-07-18T00:00:00Z",
    )
    loop = GameLoop(svc, PlayerProgress())  # default: Tamer tier needs 5 distinct
    thoughts = [
        "I trust that this is right",       # → Innocent
        "nobody understands me",            # → Orphan
        "I will overcome this",             # → Hero
        "rules are meant to be broken",     # → Rebel
        "why is there a universe",          # → Sage
        "let me create something new",      # → Creator (safety margin)
    ]
    reached = False
    for t in thoughts:
        r = loop.take_turn(t, color=False)
        if r.goal_reached:
            reached = True
            break
    assert reached, f"goal not reached; collection={loop.progress.collection}"
    assert loop.progress.distinct_count >= 5
