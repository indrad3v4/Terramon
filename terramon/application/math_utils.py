"""Math utilities for Terramon — numerical stability, information theory, vector ops.

Phase 1 (Math Foundations) curriculum applied:
  - Numerical stability: log-sum-exp, log-space softmax, safe sigmoid
  - Information Theory: KL divergence, entropy helpers
  - Vector math: L2 norm, cosine similarity, dot product
  - Statistical ops: logit, Dirichlet-safe softmax

Pure stdlib (math only). No numpy, no autograd.Value.
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Numerical stability helpers
# ---------------------------------------------------------------------------

def logsumexp(x: list[float]) -> float:
    """Log-sum-exp trick for numerical stability.

    log(sum(exp(x_i))) = m + log(sum(exp(x_i - m)))  where m = max(x)

    Handles edge cases: empty list, all -inf, single element.
    """
    if not x:
        return -float("inf")
    m = max(x)
    if not math.isfinite(m):
        return m  # all -inf → propagate
    total = 0.0
    for v in x:
        total += math.exp(v - m)
    return m + math.log(max(total, 1e-300))


def softmax(logits: list[float], temperature: float = 1.0) -> list[float]:
    """Numerically stable softmax with temperature scaling.

    Uses log-sum-exp trick. Handles:
      - Very large/small values (shifted by max)
      - Negative values (natural for logits)
      - Zero-length lists
      - Temperature extreme (near-zero → argmax, very large → uniform)
    """
    if not logits:
        return []
    if temperature <= 0.0:
        # Temperature=0 is argmax — one-hot
        m = max(logits)
        return [1.0 if v == m else 0.0 for v in logits]
    if not math.isfinite(temperature) or temperature > 1e6:
        # Near-infinite temp → uniform
        n = len(logits)
        return [1.0 / n] * n

    scaled = [v / temperature for v in logits]
    lse = logsumexp(scaled)
    return [math.exp(v - lse) for v in scaled]


def softmax_log_space(log_probs: list[float], temperature: float = 1.0) -> list[float]:
    """Softmax operating directly on log-probabilities.

    More numerically stable when inputs are already log-space.
    probs_i = exp(log_p_i / T) / sum(exp(log_p_j / T))

    Edge cases handled:
      - All -inf (zero probability everywhere) → uniform
      - Mixed -inf and finite → probability mass on finite only
    """
    if not log_probs:
        return []
    if temperature <= 0.0:
        m = max(log_probs)
        return [1.0 if v == m else 0.0 for v in log_probs]

    scaled = [v / temperature for v in log_probs]
    m = max(scaled)
    # If everything is -inf, return uniform
    if not math.isfinite(m):
        n = len(log_probs)
        return [1.0 / n] * n
    total = 0.0
    exps = []
    for v in scaled:
        e = math.exp(v - m)
        exps.append(e)
        total += e
    if total <= 0.0:
        # All underflowed — fall back to uniform
        n = len(log_probs)
        return [1.0 / n] * n
    return [e / total for e in exps]


def sigmoid(x: float) -> float:
    """Numerically stable sigmoid.

    Uses the x >= 0 branch to avoid overflow in exp(-x):
      sigmoid(x) = 1 / (1 + exp(-x))  for x >= 0
      sigmoid(x) = exp(x) / (1 + exp(x))  for x < 0

    Returns 0.0 for very negative, 1.0 for very positive.
    """
    if x >= 0.0:
        # Avoid overflow: exp(-x) is safe for large +x
        return 1.0 / (1.0 + math.exp(-x))
    else:
        # Avoid overflow: exp(x) is safe for large -x
        e = math.exp(x)
        return e / (1.0 + e)


def log_sigmoid(x: float) -> float:
    """Log-space sigmoid: log(sigmoid(x)) — avoids underflow.

    log(sigmoid(x)) = -log(1 + exp(-x)) for x >= 0
    log(sigmoid(x)) = x - log(1 + exp(x)) for x < 0
    """
    if x >= 0.0:
        return -math.log1p(math.exp(-x))
    else:
        return x - math.log1p(math.exp(x))


def gelu(x: float) -> float:
    """Gaussian Error Linear Unit — smoother than ReLU.

    GELU(x) = 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))

    Provides non-monotonic 'bend' near zero for better gradient flow.
    """
    c = math.sqrt(2.0 / math.pi) * (x + 0.044715 * x ** 3)
    return 0.5 * x * (1.0 + math.tanh(c))


def logit(p: float) -> float:
    """Logit function (inverse sigmoid).

    logit(p) = log(p / (1 - p))

    Clips to avoid infinities at exactly 0 or 1.
    """
    p = max(1e-15, min(1.0 - 1e-15, p))
    return math.log(p / (1.0 - p))


# ---------------------------------------------------------------------------
# Vector math utilities
# ---------------------------------------------------------------------------

def dot(a: list[float], b: list[float]) -> float:
    """Dot product of two vectors.

    Returns 0.0 for empty vectors.
    """
    return sum(x * y for x, y in zip(a, b))


def l2_norm(v: list[float]) -> float:
    """L2 Euclidean norm. Returns 0.0 for empty or all-zero vectors."""
    s = sum(x * x for x in v)
    return math.sqrt(s) if s > 0.0 else 0.0


def normalize(v: list[float]) -> list[float]:
    """L2-normalize a vector in-place."""
    n = l2_norm(v)
    if n == 0.0:
        return [0.0] * len(v)
    return [x / n for x in v]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two dense vectors.

    Returns 0.0 if either vector is zero-norm (orthogonal to everything).
    Range: [-1, 1] for arbitrary vectors, [0, 1] if both are L2-normalized.
    """
    if not a or not b:
        return 0.0
    an = l2_norm(a)
    bn = l2_norm(b)
    if an == 0.0 or bn == 0.0:
        return 0.0
    return dot(a, b) / (an * bn)


def cosine_similarity_sparse(a: dict[int, float], b: dict[int, float]) -> float:
    """Cosine similarity between two L2-normalized sparse vectors.

    For pre-normalized sparse vectors (like EmbeddingClassifier uses),
    cosine = dot product over shared keys.
    """
    if not a or not b:
        return 0.0
    small, big = (a, b) if len(a) < len(b) else (b, a)
    return sum(w * big.get(k, 0.0) for k, w in small.items())


# ---------------------------------------------------------------------------
# Information Theory
# ---------------------------------------------------------------------------

def entropy(probs: list[float]) -> float:
    """Shannon entropy H(p) = -sum(p_i * log(p_i))

    Measures uncertainty in a probability distribution.
    H=0 for deterministic (one outcome), H=log(N) for uniform.

    Handles zero probabilities (0 * log(0) = 0 convention).
    """
    h = 0.0
    for p in probs:
        if p > 0.0:
            h -= p * math.log(p)
    return h


def kl_divergence(p: list[float], q: list[float]) -> float:
    """Kullback-Leibler divergence D_KL(P || Q) = sum(p_i * log(p_i / q_i))

    Measures how much information is lost when using Q to approximate P.
    D_KL >= 0 with equality iff P == Q.

    Handles zero probabilities:
      - p_i = 0, q_i = 0 → 0 (no contribution)
      - p_i > 0, q_i = 0 → +inf (infinite divergence — Q assigns zero mass
        to an event that P says is possible)
      - p_i = 0, q_i > 0 → 0 (no contribution)
    """
    d = 0.0
    for pi, qi in zip(p, q):
        if pi > 0.0:
            if qi <= 0.0:
                return float("inf")
            d += pi * math.log(pi / qi)
    return d


def cross_entropy(p: list[float], q: list[float]) -> float:
    """Cross-entropy H(P, Q) = -sum(p_i * log(q_i))

    Decomposes as: H(P, Q) = H(P) + D_KL(P || Q)
    """
    ce = 0.0
    for pi, qi in zip(p, q):
        if pi > 0.0:
            if qi <= 0.0:
                return float("inf")
            ce -= pi * math.log(qi)
    return ce


def softmax_entropy(logits: list[float]) -> float:
    """Entropy of the softmax distribution of logits.

    Useful for measuring classifier confidence quality:
      Low entropy = confident (peaked distribution)
      High entropy = uncertain (flat distribution)
    """
    probs = softmax(logits)
    return entropy(probs)


# ---------------------------------------------------------------------------
# Convex optimization helpers
# ---------------------------------------------------------------------------

def xp_to_level(xp: int, xp_per_level: int) -> int:
    """Convert XP to 1-indexed level.

    Convex analysis: linear XP-per-level (level = xp / N + 1) gives
    constant effort per level — no compounding, easy to understand,
    but levels feel faster early and slower late relative to total XP.

    Returns level (1-indexed).
    """
    return xp // xp_per_level + 1


def level_to_xp(level: int, xp_per_level: int) -> int:
    """Convert level back to total XP needed.

    For linear curve: xp = (level - 1) * xp_per_level
    """
    return max(0, level - 1) * xp_per_level
