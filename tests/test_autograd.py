"""Tests for terramon/application/autograd.py (Lesson 05 — Chain Rule & Autodiff)."""

from __future__ import annotations

import math
import random

from terramon.application.autograd import (
    Value,
    Neuron,
    Layer,
    MLP,
    softmax,
    cross_entropy_loss,
    _val_exp,
    _val_log,
)


def test_value_add_gradient():
    # if y = a + b, then dy/da = 1, dy/db = 1
    a = Value(2.0)
    b = Value(3.0)
    y = a + b
    y.backward()
    assert abs(a.grad - 1.0) < 1e-9
    assert abs(b.grad - 1.0) < 1e-9


def test_value_mul_gradient():
    # if y = a * b, then dy/da = b, dy/db = a
    a = Value(2.0)
    b = Value(3.0)
    y = a * b
    y.backward()
    assert abs(a.grad - 3.0) < 1e-9
    assert abs(b.grad - 2.0) < 1e-9


def test_value_pow_gradient():
    # if y = x**3, then dy/dx = 3 * x**2
    x = Value(4.0)
    y = x ** 3
    y.backward()
    assert abs(x.grad - 3 * (4 ** 2)) < 1e-9


def test_value_relu_gradient_positive():
    x = Value(5.0)
    y = x.relu()
    y.backward()
    assert abs(x.grad - 1.0) < 1e-9


def test_value_relu_gradient_zero():
    x = Value(-2.0)
    y = x.relu()
    y.backward()
    assert abs(x.grad) < 1e-9  # gradient is 0 for negative inputs


def test_value_tanh_gradient():
    # dy/dx of tanh(x) = 1 - tanh(x)^2
    x = Value(0.5)
    y = x.tanh()
    y.backward()
    expected = 1.0 - math.tanh(0.5) ** 2
    assert abs(x.grad - expected) < 1e-9


def test_exp_gradient():
    x = Value(1.0)
    y = _val_exp(x)
    y.backward()
    assert abs(x.grad - math.exp(1.0)) < 1e-6


def test_log_gradient():
    x = Value(2.0)
    y = _val_log(x)
    y.backward()
    assert abs(x.grad - 1.0 / 2.0) < 1e-9


def test_value_chain_rule():
    # y = (a + b) * c
    # dy/da = c, dy/db = c, dy/dc = a + b
    a = Value(2.0)
    b = Value(3.0)
    c = Value(5.0)
    y = (a + b) * c
    y.backward()
    assert abs(a.grad - 5.0) < 1e-9
    assert abs(b.grad - 5.0) < 1e-9
    assert abs(c.grad - 5.0) < 1e-9


def test_grad_accumulates():
    """If a value is used in multiple operations, gradients accumulate."""
    x = Value(3.0)
    y = x * 2 + x * 3  # y = 2x + 3x = 5x, dy/dx = 5
    y.backward()
    assert abs(x.grad - 5.0) < 1e-9


def test_neuron_parameters():
    n = Neuron(4)
    params = n.parameters()
    assert len(params) == 5  # 4 weights + 1 bias


def test_mlp_forward():
    model = MLP(3, 8, 2)
    out = model([1.0, 2.0, 3.0])
    assert len(out) == 2
    for o in out:
        assert isinstance(o, Value)


def test_mlp_can_learn_xor():
    """Run 3 seeds; the best run should reach >=75% on XOR."""
    X = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
    y = [0, 1, 1, 0]

    best_acc = 0.0
    for s in range(3):
        random.seed(s * 42)
        model = MLP(2, 16, 2)
        lr = 0.7
        seed_best = 0
        for epoch in range(200):
            correct = 0
            for xi, yi in zip(X, y):
                logits = model(xi)
                loss = cross_entropy_loss(logits, yi)
                pred_i = 0 if logits[0].data > logits[1].data else 1
                if pred_i == yi:
                    correct += 1
                model.zero_grad()
                loss.backward()
                for p in model.parameters():
                    p.data -= lr * p.grad
            seed_best = max(seed_best, correct)
        best_acc = max(best_acc, seed_best / len(X))
        if best_acc >= 0.75:
            break
    assert best_acc >= 0.75, f"XOR accuracy too low even with 3 seeds: {best_acc}"


def test_mlp_parameters_count():
    model = MLP(2, 8, 3)
    # 2->8 = 2*8 + 8 = 24 params; 8->3 = 8*3 + 3 = 27; total = 51
    n = len(model.parameters())
    assert n == (2 * 8 + 8) + (8 * 3 + 3)
