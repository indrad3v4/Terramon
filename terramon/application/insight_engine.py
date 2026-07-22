"""Insight Engine — what actually drives the agent (FIX 2, PLAYER_JOURNEY_MAP).

The surface text a player types is only a *symptom*. Behind it lives an INSIGHT,
the hidden behavioral mechanism that MOVES the creature (per
docs/dvizhok/phase1-strategy.md §3 INSIGHT ENGINE):

    DRIVER  = what the player WANTS
    BARRIER = what BLOCKS it
    THEREFORE = the creature's behavior directive — this is what the agent
                actually DOES, not the rarity label.

BUILD-VIA-LEARN (Lesson 02 -> 03): this module is the literal textbook example
of a *weighted* layer. Text is ENCODED into a vector, then TRANSFORMED by a
weight matrix W (matmul) into theme-scores, then argmax picks the theme. That is
exactly `layer(W, b, x)` from the lesson — no if/elif, just linear algebra.

Pure stdlib (no API, no deps). Deterministic.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict

from terramon.domain.insight import Insight

# ---------------------------------------------------------------------------
# 1. ENCODE — text -> vector (hashing trick, same idea as EmbeddingClassifier)
# ---------------------------------------------------------------------------

_DIM = 64  # small, human-readable weight space for the insight themes


def _tokens(text: str) -> list[str]:
    import re
    words = re.findall(r"[a-z']+", text.lower())
    grams = list(words)
    grams += [f"{a}_{b}" for a, b in zip(words, words[1:])]
    return grams


def _hash(token: str) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % _DIM


def encode(text: str) -> list[float]:
    """Text -> L2-normalized vector (the 'x' that gets multiplied by W)."""
    vec = defaultdict(float)
    for tok in _tokens(text):
        vec[_hash(tok)] += 1.0
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return [0.0] * _DIM
    return [vec.get(i, 0.0) / norm for i in range(_DIM)]


# ---------------------------------------------------------------------------
# 2. WEIGHTS — W (the learned matrix) + b (bias)
#    Each ROW of W is one theme. W[i] @ x = how strongly text x expresses theme i.
#    Values are hand-set "expert priors" (a real model would LEARN them via
#    gradient descent — see Lesson 03). Positive = supports theme, negative =
#    suppresses it. This IS the concept of "weights": a learned map from
#    signal -> meaning.
# ---------------------------------------------------------------------------

_THEMES = ["money", "work", "fear", "loneliness", "direction"]

# Row i of W lights up for tokens that signal theme i. We set a few buckets
# per theme by hashing the cue words once and writing the weight there.
_CUE_TO_THEME = {
    "money": "money", "rent": "money", "broke": "money", "pay": "money",
    "payment": "money", "debt": "money", "bills": "money", "poor": "money",
    "work": "work", "job": "work", "boss": "work", "burnout": "work",
    "deadline": "work", "tired": "work", "exhausted": "work",
    "afraid": "fear", "fear": "fear", "scared": "fear", "anxious": "fear",
    "anxiety": "fear", "terrified": "fear", "worried": "fear",
    "alone": "loneliness", "lonely": "loneliness", "isolated": "loneliness",
    "nobody": "loneliness", "no one": "loneliness", "abandoned": "loneliness",
    "lost": "direction", "stuck": "direction", "confused": "direction",
    "purpose": "direction", "meaning": "direction", "which way": "direction",
    "interview": "fear", "tomorrow": "fear",
}

# Build W (len(_THEMES) x _DIM) from the cue table. This is the "training data"
# of a trivial model: we DECLARE which words mean which theme, and the matrix
# stores that as weights.
W: list[list[float]] = [[0.0] * _DIM for _ in range(len(_THEMES))]
_theme_index = {t: i for i, t in enumerate(_THEMES)}
for cue, theme in _CUE_TO_THEME.items():
    W[_theme_index[theme]][_hash(cue)] += 1.0

# bias b: a small prior so a totally empty text doesn't argmax to noise.
b: list[float] = [0.0] * len(_THEMES)


# ---------------------------------------------------------------------------
# 3. FORWARD PASS — exactly layer(W, b, x) = W @ x + b  (Lesson 02)
# ---------------------------------------------------------------------------

def _matvec(Wm: list[list[float]], x: list[float]) -> list[float]:
    """W @ x: each row of W dotted with x. This is the dot product from L02."""
    return [sum(w_ij * x_j for w_ij, x_j in zip(row, x)) for row in Wm]


def _scores(text: str) -> list[float]:
    """Theme scores = W @ encode(text) + b."""
    x = encode(text)
    return [s + b_i for s, b_i in zip(_matvec(W, x), b)]


def _argmax_theme(scores: list[float]) -> str:
    best = max(range(len(scores)), key=lambda i: scores[i])
    # If the strongest signal is ~0, the text carries no theme -> neutral.
    if scores[best] <= 0.0:
        return "neutral"
    return _THEMES[best]


# ---------------------------------------------------------------------------
# 4. DRIVER / BARRIER / THEREFORE — the insight the agent is driven by
# ---------------------------------------------------------------------------

_DRIVER_BY_THEME: dict[str, str] = {
    "money": "to be safe and free of scarcity",
    "work": "rest and a life outside the grind",
    "fear": "to be unafraid of what comes next",
    "loneliness": "to be met and held",
    "direction": "to know which way to turn",
    "neutral": "to be met where you are",
}

_BARRIER_BY_THEME: dict[str, str] = {
    "money": "money",
    "work": "work",
    "fear": "fear",
    "loneliness": "loneliness",
    "direction": "direction",
    "neutral": "the quiet ordinary",
}

_BEHAVIOR_BY_BARRIER: dict[str, str] = {
    "money": "It sits with you in the scarcity and does not look away.",
    "work": "It clears a small space so you can breathe.",
    "fear": "It waits by the door so you are not facing it alone.",
    "loneliness": "It stays close, a warm weight at your side.",
    "direction": "It walks a little ahead, showing the next step only.",
    "the quiet ordinary": "It settles beside you and listens to what the quiet is saying.",
}


def extract_insight(raw_input: str) -> Insight:
    """Derive the INSIGHT (DRIVER + BARRIER -> THEREFORE) from raw player text.

    Forward pass: encode -> W@x+b -> argmax theme. The detected theme becomes
    the BARRIER; its paired driver becomes the DRIVER; the behavior template
    becomes THEREFORE (what the agent DOES). No if/elif on the text itself —
    the weights W decide.
    """
    text = (raw_input or "").strip()
    theme = _argmax_theme(_scores(text))
    barrier = _BARRIER_BY_THEME[theme]
    driver = _DRIVER_BY_THEME[theme]
    therefore = _BEHAVIOR_BY_BARRIER[barrier]
    return Insight(driver=driver, barrier=barrier, therefore=therefore)
