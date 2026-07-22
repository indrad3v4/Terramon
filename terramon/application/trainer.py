"""Gradient descent trainer for the Insight Engine — build-via-learn Lesson 04
(Calculus for Machine Learning) + Lesson 05 preview (chain rule in code).

Course hook (L04): "Derivatives tell you which way is downhill. That is all a
neural network needs to learn."

Right now insight_engine.py builds W (5 themes x 64) by HARD-SETTING
W[theme][hash(cue)] += 1.0 from a cue table. That is a frozen model. This
module fits W (and bias b) from EXAMPLES using gradient descent:

    loss  = cross-entropy(softmax(W@x + b), one_hot(target))
    dW[i][j] = (pred[i] - target[i]) * x[j]      # chain rule, one layer
    db[i]    = (pred[i] - target[i])
    W -= lr * dW ;  b -= lr * db

After training, W *emerges* from data instead of being hand-written — the
"real weights" payoff from the Lesson 02 refactor. Pure stdlib (math).
"""

from __future__ import annotations

import math
from typing import Sequence

from terramon.application.insight_engine import W as W0, b as b0, encode, _THEMES


def _softmax(scores: Sequence[float]) -> list[float]:
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    z = sum(exps)
    return [e / z for e in exps]


def _cross_entropy(pred: Sequence[float], target_idx: int) -> float:
    # -log pred[target]; clip for stability
    p = max(pred[target_idx], 1e-12)
    return -math.log(p)


def loss_and_grad(
    W: list[list[float]],
    b: list[float],
    x: list[float],
    target_idx: int,
) -> tuple[float, list[list[float]], list[float]]:
    """Return (loss, dW, db) for one example. Chain rule, single layer."""
    scores = [sum(w_ij * x_j for w_ij, x_j in zip(row, x)) + b_i
              for row, b_i in zip(W, b)]
    pred = _softmax(scores)
    loss = _cross_entropy(pred, target_idx)

    # gradient: d score_i / d W[i][j] = x[j] ; d loss / d score_i = (pred_i - tgt_i)
    dW = [[(pred[i] - (1.0 if i == target_idx else 0.0)) * x[j]
           for j, _ in enumerate(x)]
          for i, _ in enumerate(W)]
    db = [(pred[i] - (1.0 if i == target_idx else 0.0)) for i, _ in enumerate(W)]
    return loss, dW, db


def train(
    examples: list[tuple[str, str]],
    lr: float = 0.5,
    epochs: int = 60,
    W: list[list[float]] | None = None,
    b: list[float] | None = None,
    verbose: bool = True,
) -> tuple[list[list[float]], list[float]]:
    """Gradient descent on W,b. Starts from the existing hand-set W (sane init).

    examples: list of (text, theme_name). Returns trained (W, b).
    """
    W = [row[:] for row in (W or W0)]
    b = list(b or b0)
    n_themes = len(W)

    for ep in range(epochs):
        total_loss = 0.0
        # accumulate gradients over the batch
        gW = [[0.0] * len(W[0]) for _ in range(n_themes)]
        gb = [0.0] * n_themes
        for text, theme in examples:
            if theme not in _THEMES:
                continue
            tgt = _THEMES.index(theme)
            x = encode(text)
            loss, dW, db = loss_and_grad(W, b, x, tgt)
            total_loss += loss
            for i in range(n_themes):
                for j in range(len(x)):
                    gW[i][j] += dW[i][j]
                gb[i] += db[i]
        # step
        n = max(len(examples), 1)
        for i in range(n_themes):
            for j in range(len(W[0])):
                W[i][j] -= lr * gW[i][j] / n
            b[i] -= lr * gb[i] / n
        if verbose and (ep % 10 == 0 or ep == epochs - 1):
            print(f"  epoch {ep:3d}  loss {total_loss / n:.4f}")
    return W, b


def accuracy(W: list[list[float]], b: list[float], examples: list[tuple[str, str]]) -> float:
    """Fraction of examples whose argmax theme matches the label."""
    correct = 0
    n = 0
    for text, theme in examples:
        if theme not in _THEMES:
            continue
        n += 1
        x = encode(text)
        scores = [sum(w_ij * x_j for w_ij, x_j in zip(row, x)) + b_i
                  for row, b_i in zip(W, b)]
        pred = _THEMES[max(range(len(scores)), key=lambda i: scores[i])]
        if pred == theme:
            correct += 1
    return correct / n if n else 0.0


# --- training set (hand-labeled: text -> true theme) -------------------------
EXAMPLES: list[tuple[str, str]] = [
    ("i am afraid of the interview tomorrow", "fear"),
    ("terrified and anxious about the call", "fear"),
    ("scared of what comes next", "fear"),
    ("nobody is here with me", "loneliness"),
    ("i feel so alone and isolated", "loneliness"),
    ("abandoned by everyone i knew", "loneliness"),
    ("i cant pay rent this month", "money"),
    ("broke and drowning in debt", "money"),
    ("the bills keep piling up", "money"),
    ("boss gave me burnout again", "work"),
    ("exhausted from the deadline grind", "work"),
    ("tired after another long shift", "work"),
    ("lost and stuck in life", "direction"),
    ("confused about which way to turn", "direction"),
    ("searching for meaning and purpose", "direction"),
]


if __name__ == "__main__":
    print("Training Insight Engine weights via gradient descent (Lesson 04)...")
    Wt, bt = train(EXAMPLES, lr=0.5, epochs=60)
    print(f"Train accuracy: {accuracy(Wt, bt, EXAMPLES):.2%}")
    # held-out style check
    x = encode("worried about the meeting")
    scores = [sum(Wt[i][j] * xj for j, xj in enumerate(x)) + bt[i]
              for i in range(len(Wt))]
    print("Held-out-ish: 'worried about the meeting' ->",
          _THEMES[max(range(len(scores)), key=lambda i: scores[i])])
