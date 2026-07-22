"""Embedding-lite classifier — a real vector-space model, no API, no deps.

Build-via-learn: Phase 5/10 (NLP / LLMs) of the course, scaled down honestly.
This is a *bi-encoder in miniature*:

  1. ENCODE text -> a sparse term-frequency vector in a hashed feature space
     (the "hashing trick": token -> hash % DIM, so vocab is unbounded but the
     vector is fixed-width). Word unigrams + bigrams capture a little context.
  2. NORMALIZE (L2) so length doesn't bias similarity.
  3. Each ARCHETYPE has a prototype = the L2-normalized mean (centroid) of its
     example phrases' vectors — exactly how a nearest-centroid / prototype
     classifier works.
  4. CLASSIFY = argmax cosine(query, prototype). Cosine of L2-normed vectors is
     just their dot product.

Why this beats KeywordClassifier (roast Lens #23 Emergence): the flat keyword
map returned the same agent for anything off-list. Here, *any* input lands
somewhere in the vector space and pulls the nearest archetype, so semantically
different thoughts summon different creatures -> the collection actually grows.

Pure stdlib (math, hashlib) to honor the repo's stdlib-first rule. Deterministic:
hashing uses blake2b with a fixed key, not Python's salted hash().
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict

from terramon.ports.classifier_port import ClassifierPort

DIM = 512  # hashed feature space width


def _tokens(text: str) -> list[str]:
    """Lowercase word unigrams + adjacent bigrams (a little context)."""
    words = re.findall(r"[a-z']+", text.lower())
    grams = list(words)
    grams += [f"{a}_{b}" for a, b in zip(words, words[1:])]
    return grams


def _hash(token: str) -> int:
    """Deterministic token -> bucket in [0, DIM). blake2b avoids hash() salting."""
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % DIM


def _encode(text: str) -> dict[int, float]:
    """Text -> L2-normalized sparse TF vector (dict bucket->weight)."""
    vec: dict[int, float] = defaultdict(float)
    for tok in _tokens(text):
        vec[_hash(tok)] += 1.0
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: v / norm for k, v in vec.items()}


def _centroid(vectors: list[dict[int, float]]) -> dict[int, float]:
    """Mean of vectors, then L2-normalized -> an archetype prototype."""
    acc: dict[int, float] = defaultdict(float)
    for vec in vectors:
        for k, v in vec.items():
            acc[k] += v
    n = len(vectors) or 1
    acc = {k: v / n for k, v in acc.items()}
    norm = math.sqrt(sum(v * v for v in acc.values()))
    if norm == 0:
        return {}
    return {k: v / norm for k, v in acc.items()}


def _cosine(a: dict[int, float], b: dict[int, float]) -> float:
    """Cosine of two L2-normed sparse vectors = dot product over shared keys."""
    if not a or not b:
        return 0.0
    small, big = (a, b) if len(a) < len(b) else (b, a)
    return sum(w * big.get(k, 0.0) for k, w in small.items())


class EmbeddingClassifier(ClassifierPort):
    """Nearest-centroid classifier over hashed TF vectors."""

    DEFAULT_AGENT = "Innocent"

    # Each archetype defined by example thought seeds (its "training set").
    # v3: Jung's 12 archetypes (replaces 24 made-up names).
    # Grounded in Jungian psychology — every creature is a real psychological
    # pattern, not shower thoughts. The 512-dim embedding space still captures
    # unique nuance within each archetype (C option: start with Jung, expand
    # with continuous embedding).
    ARCHETYPES: dict[str, list[str]] = {
        "Innocent": [
            "i just want to be safe",
            "everything will be okay",
            "i trust that this is right",
            "keep me from harm",
            "i believe in the good of people",
        ],
        "Orphan": [
            "i don't belong anywhere",
            "nobody understands me",
            "we are all in this together",
            "i just want to fit in",
            "why am i always left out",
        ],
        "Hero": [
            "i will overcome this",
            "nothing can stop me now",
            "i have to be strong",
            "face the challenge head on",
            "this is my trial to overcome",
        ],
        "Caregiver": [
            "let me help you",
            "i need to take care of them",
            "your pain matters to me",
            "i give because i care",
            "protect the vulnerable",
        ],
        "Explorer": [
            "i want to see what's out there",
            "don't fence me in",
            "the road is calling me",
            "i need to find my own path",
            "freedom is everything",
        ],
        "Rebel": [
            "rules are meant to be broken",
            "i won't follow their system",
            "tear it all down",
            "they can't tell me what to do",
            "revolution starts now",
        ],
        "Lover": [
            "i want to be close to you",
            "love is all that matters",
            "i give you my whole heart",
            "being with you is enough",
            "i crave connection and intimacy",
        ],
        "Creator": [
            "i will build something new",
            "make something from nothing",
            "my imagination is limitless",
            "create what has never been seen",
            "art is how i breathe",
        ],
        "Jester": [
            "life is a joke enjoy it",
            "make them laugh",
            "don't take it so seriously",
            "joy in every moment",
            "laughter is the best medicine",
        ],
        "Sage": [
            "the truth will set me free",
            "i seek wisdom and understanding",
            "knowledge is power",
            "let me understand why",
            "enlighten me with your wisdom",
        ],
        "Magician": [
            "transform this situation",
            "i can make things happen",
            "believe and it will come",
            "the universe is on my side",
            "turn lead into gold",
        ],
        "Ruler": [
            "take charge of this situation",
            "i must be in control",
            "lead the people",
            "order from chaos",
            "power and responsibility",
        ],
    }

    # Below this cosine, the input is too far from every archetype -> default.
    MIN_CONFIDENCE = 0.05

    def __init__(self) -> None:
        """Precompute one prototype centroid per archetype."""
        self._prototypes: dict[str, dict[int, float]] = {
            name: _centroid([_encode(ex) for ex in examples])
            for name, examples in self.ARCHETYPES.items()
        }

    def classify(self, thought_seed: str) -> str:
        """Return the archetype whose prototype is closest (cosine) to input."""
        query = _encode(thought_seed)
        if not query:
            return self.DEFAULT_AGENT
        best_name, best_score = self.DEFAULT_AGENT, self.MIN_CONFIDENCE
        for name, proto in self._prototypes.items():
            score = _cosine(query, proto)
            if score > best_score:
                best_name, best_score = name, score
        return best_name

    def scores(self, thought_seed: str) -> dict[str, float]:
        """Expose cosine scores per archetype (for eval/debug/transparency)."""
        query = _encode(thought_seed)
        return {
            name: round(_cosine(query, proto), 4)
            for name, proto in self._prototypes.items()
        }
