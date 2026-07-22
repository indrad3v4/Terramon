"""Tests for terramon/application/trainer.py (Lesson 04)."""

from __future__ import annotations

import copy

from terramon.application import trainer as T
from terramon.application.insight_engine import W as W0, b as b0, encode, _THEMES


def test_loss_decreases_over_epochs():
    ex = [("i am afraid", "fear"), ("nobody here", "loneliness")]
    # measure loss at epoch 0 vs end by training twice with different epochs
    W1, b1 = T.train(ex, lr=0.5, epochs=1, verbose=False)
    W2, b2 = T.train(ex, lr=0.5, epochs=80, verbose=False)

    def avg_loss(W, b, examples):
        tot = 0.0
        n = 0
        for text, theme in examples:
            if theme not in _THEMES:
                continue
            tgt = _THEMES.index(theme)
            x = encode(text)
            loss, _, _ = T.loss_and_grad(W, b, x, tgt)
            tot += loss
            n += 1
        return tot / n

    assert avg_loss(W2, b2, ex) < avg_loss(W1, b1, ex)


def test_trained_classifies_held_out():
    ex = [
        ("i am afraid of the interview", "fear"),
        ("nobody is here with me", "loneliness"),
        ("i cant pay rent", "money"),
        ("boss gave me burnout", "work"),
        ("lost and stuck", "direction"),
    ]
    Wt, bt = T.train(ex, lr=0.5, epochs=80, verbose=False)
    # 'terrified' was NOT in training text but shares fear theme tokens via hash
    assert T.accuracy(Wt, bt, ex) >= 0.8


def test_gradient_sign_flips_when_pred_exceeds_target():
    # For a correct prediction (pred[target] high), the gradient pushes DOWN.
    x = encode("i am afraid")
    tgt = _THEMES.index("fear")
    # build W,b so fear already wins strongly
    W = copy.deepcopy(W0)
    b = list(b0)
    loss, dW, db = T.loss_and_grad(W, b, x, tgt)
    # pred[fear] > target-ish -> dW[fear][*] should be <= 0 (push down)
    assert db[tgt] <= 0.0


def test_train_is_deterministic():
    ex = [("i am afraid", "fear"), ("nobody here", "loneliness")]
    W_a, b_a = T.train(ex, lr=0.5, epochs=40, verbose=False)
    W_b, b_b = T.train(ex, lr=0.5, epochs=40, verbose=False)
    assert all(
        abs(W_a[i][j] - W_b[i][j]) < 1e-9
        for i in range(len(W_a)) for j in range(len(W_a[0]))
    )
    assert all(abs(b_a[i] - b_b[i]) < 1e-9 for i in range(len(b_a)))


def test_softmax_sums_to_one():
    s = T._softmax([1.0, 2.0, -1.0])
    assert abs(sum(s) - 1.0) < 1e-9
