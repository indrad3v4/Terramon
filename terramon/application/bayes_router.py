"""Bayesian Router — replaces random MoE router with belief-driven archetype selection.

Lesson 07 (Bayes' Theorem) applied to Terramon:

  P(archetype | thought) ∝ P(thought | archetype) × P(archetype)

  likelihood  = cosine(encode(thought), centroid)  ← EmbeddingClassifier
  prior       = belief counts from player history    ← json_memory
  posterior   = likelihood × prior                   ← Bayes update
  confidence  = max(posterior)                        ← revenue gate

The MoE router is no longer random. Every summon UPDATES the belief state.
Players literally TRAIN the neural network by playing the game.

Player insight (indradev_):
  Terramon IS the neural network. The creatures ARE the MoE experts.
  Players train the model by summoning. They earn by MINTing their
  unique embedding vector — their point in the weight space.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from terramon.adapters.embedding_classifier import EmbeddingClassifier
from terramon.application.insight_engine import encode
from terramon.application.math_utils import softmax, logsumexp, entropy

# Jungian archetype names (must match EmbeddingClassifier)
_ARCHETYPE_NAMES = [
    "Innocent", "Orphan", "Hero", "Caregiver", "Explorer",
    "Rebel", "Lover", "Creator", "Jester", "Sage", "Magician", "Ruler",
]
_N_ARCHETYPES = len(_ARCHETYPE_NAMES)
_NAME_TO_IDX = {name: i for i, name in enumerate(_ARCHETYPE_NAMES)}

# Singleton classifier (lazy init)
_CLASSIFIER: Optional[EmbeddingClassifier] = None

# Default belief state — Dirichlet prior (uniform + weak concentration)
_DEFAULT_PRIOR = [1.0] * _N_ARCHETYPES


def _get_classifier() -> EmbeddingClassifier:
    global _CLASSIFIER
    if _CLASSIFIER is None:
        _CLASSIFIER = EmbeddingClassifier()
    return _CLASSIFIER


def load_belief(player_id: str = "default",
                memory_path: str = "data/beliefs.jsonl") -> list[float]:
    """Load belief counts for a player from persistent memory.

    Returns Dirichlet prior (concentration parameters per archetype).
    """
    path = Path(memory_path)
    if not path.exists():
        return _DEFAULT_PRIOR[:]
    try:
        import json
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("player_id") == player_id:
                return record.get("counts", _DEFAULT_PRIOR[:])
    except (json.JSONDecodeError, OSError):
        pass
    return _DEFAULT_PRIOR[:]


def save_belief(counts: list[float], player_id: str = "default",
                memory_path: str = "data/beliefs.jsonl"):
    """Persist belief counts for a player."""
    import json
    from collections import OrderedDict

    path = Path(memory_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing beliefs, replace this player's entry
    records: list[dict] = []
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                if r.get("player_id") != player_id:
                    records.append(r)
            except json.JSONDecodeError:
                continue

    records.append({"player_id": player_id, "counts": counts})
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )


def bayes_forward(thought: str,
                  prior: Optional[list[float]] = None,
                  temperature: float = 1.0
                  ) -> tuple[int, list[float], list[float]]:
    """Bayesian forward pass: posterior ∝ likelihood × prior.

    Args:
        thought: raw player text
        prior: Dirichlet prior counts (default: uniform)
        temperature: softmax temperature for confidence calibration

    Returns:
        (winner_idx, posterior_probs, likelihood_scores)
    """
    if prior is None:
        prior = _DEFAULT_PRIOR[:]

    # Likelihood = cosine similarity to archetype centroids
    clf = _get_classifier()
    scores_dict = clf.scores(thought)

    likelihood = []
    for name in _ARCHETYPE_NAMES:
        # Map EmbeddingClassifier archetype names to our list
        score = scores_dict.get(name, scores_dict.get(name.lower(), 0.0))
        # Shift negative cosines to positive (cosine range: [-1, 1])
        likelihood_shifted = max(score + 1.0, 1e-10)
        likelihood.append(likelihood_shifted)

    # Posterior = prior × likelihood (element-wise), then normalize
    posterior_raw = [p * l for p, l in zip(prior, likelihood)]

    # Softmax with temperature (stable via log-sum-exp)
    posterior = softmax(posterior_raw, temperature=temperature)

    # Confidence entropy — measure of classifier certainty
    confidence_entropy = entropy(posterior)

    winner = max(range(_N_ARCHETYPES), key=lambda i: posterior[i])
    return winner, posterior, likelihood


def update_belief(counts: list[float], winner_idx: int) -> list[float]:
    """Update Dirichlet prior with new evidence (Bayesian update).

    The winning archetype gets its count incremented.
    Other archetypes get no increment but their relative proportions
    naturally decrease due to normalization.
    """
    new_counts = counts[:]
    new_counts[winner_idx] += 1.0
    return new_counts


def should_gate_payment(posterior: list[float],
                        threshold: float = 0.5) -> bool:
    """Only show MINT button when confidence exceeds threshold.

    Lesson 07: The revenue gate. Players can only mint creatures
    the network is confident about (max posterior > threshold).
    Low-confidence creatures are free — they help train the model.
    """
    return max(posterior) > threshold
