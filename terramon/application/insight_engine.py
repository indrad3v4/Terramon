"""Insight Engine — what actually drives the agent (v3: Jungian archetypes).

BUILD-VIA-LEARN (Lesson 02 → 06): this started as a 5-theme W@x+b linear layer,
then became a K3-inspired MoE with 12 Jungian archetypes, softmax probability
distributions, and confidence calibration (Lesson 06: Probability).

Now acts as a thin public-API shim over the K3 engine. The old 5-theme tables
are removed (TRIZ ideality: one path, not two).
"""

from __future__ import annotations

from terramon.domain.insight import Insight
from terramon.application.k3_insight_engine import (
    _THEME_NAMES,
    _DRIVER_BY_THEME,
    _BARRIER_BY_THEME,
    _BEHAVIOR_BY_BARRIER,
)
from terramon.application.math_utils import l2_norm, normalize

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
    dense = [vec.get(i, 0.0) for i in range(64)]
    return normalize(dense)


def _scores(text: str) -> list[float]:
    """Return theme scores using Bayesian router (Lesson 07).

    P(archetype | thought) ∝ P(thought | archetype) × P(archetype)

    Likelihood = cosine similarity to archetype centroids.
    Prior = uniform (default). Updated per-player via bayes_router.
    """
    from terramon.application.bayes_router import bayes_forward, _ARCHETYPE_NAMES
    winner, posterior, likelihood = bayes_forward(text)
    return posterior


def extract_insight(raw_input: str,
                    geo=None,
                    thinking_steps: int = 3,
                    top_k: int | None = None,
                    use_reasoning_chain: bool = False,
                    use_attention: bool = True) -> Insight:
    """Derive the INSIGHT from raw player text.

    Delegates to the K3 MoE engine (12 Jungian archetypes, softmax
    probability distribution, confidence score).

    Args:
        raw_input: player's thought text
        geo: optional GeoContext (where on Earth the thought was born)
        thinking_steps: iterative refinement steps
        top_k: sparse MoE expert count (None=dense, 3=Mixtral-style)
        use_reasoning_chain: iterative re-ranking of experts
        use_attention: attention-weighted archetype scoring (Phase 5)
    """
    from terramon.application.k3_insight_engine import extract_insight as k3_extract
    return k3_extract(
        raw_input, geo=geo,
        top_k=top_k,
        thinking_steps=thinking_steps,
        use_reasoning_chain=use_reasoning_chain,
        use_attention=use_attention,
    )

