"""Insight Engine — what actually drives the agent (v3: Jungian archetypes).

BUILD-VIA-LEARN (Lesson 02 → 06): this started as a 5-theme W@x+b linear layer,
then became a K3-inspired MoE with 12 Jungian archetypes, softmax probability
distributions, and confidence calibration (Lesson 06: Probability).

Now acts as a thin public-API shim over the K3 engine. The old 5-theme tables
are removed (TRIZ ideality: one path, not two).
"""

from __future__ import annotations

import math

from terramon.domain.insight import Insight
from terramon.application.k3_insight_engine import (
    _THEME_NAMES,
    _DRIVER_BY_THEME,
    _BARRIER_BY_THEME,
    _BEHAVIOR_BY_BARRIER,
)

# Re-export for backward compat (imported by TMA and summon_service)
_THEMES = _THEME_NAMES  # the 12 Jungian archetypes


def encode(text: str) -> list[float]:
    """Text -> L2-normalized 64-dim vector (hashing trick).

    Same interface as v1. Used by k3_insight_engine for input encoding.
    """
    import hashlib
    from collections import defaultdict

    def _tokens(t: str) -> list[str]:
        import re
        words = re.findall(r"[a-z']+", t.lower())
        grams = list(words)
        grams += [f"{a}_{b}" for a, b in zip(words, words[1:])]
        return grams

    def _hash(tok: str) -> int:
        digest = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % 64

    vec = defaultdict(float)
    for tok in _tokens(text):
        vec[_hash(tok)] += 1.0
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return [0.0] * 64
    return [vec.get(i, 0.0) / norm for i in range(64)]


def _scores(text: str) -> list[float]:
    """Return theme scores (used by TMA for confidence computation).

    Delegates to k3_insight_engine's MoE router for the probability
    distribution over 12 Jungian archetypes.
    """
    from terramon.application.k3_insight_engine import _get_net
    net = _get_net()
    encoded = encode(text)
    _, probs, _ = net.forward(encoded)
    return probs


def extract_insight(raw_input: str,
                    geo=None,
                    thinking_steps: int = 3) -> Insight:
    """Derive the INSIGHT from raw player text.

    Now delegates to the K3 MoE engine (12 Jungian archetypes, softmax
    probability distribution, confidence score).

    Args:
        raw_input: player's thought text
        geo: optional GeoContext (where on Earth the thought was born)
        thinking_steps: iterative refinement steps

    Returns:
        Insight with driver, barrier, therefore, archetype, nuance,
        geo (if provided), confidence (0-100%)
    """
    from terramon.application.k3_insight_engine import extract_insight as k3_extract
    return k3_extract(raw_input, geo=geo)

