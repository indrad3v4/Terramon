"""Autograd engine — build-via-learn Lesson 05 (Chain Rule & Automatic Differentiation).

A miniature autograd engine that records operations in a computational graph
and computes gradients via reverse-mode autodiff (backpropagation).

Course hook: "The chain rule is the engine behind every neural network that learns."

In Terramon, this connects:
  1. MATH: local gradients (∂L/∂W = (pred−target)·x)
  2. AUTOGRAD: Value class records graphs; backward() propagates gradients
  3. NETWORK: MLP built from Value nodes
  4. TRAINING: forward→backward→update on labeled thoughts
  5. ACCURACY: improves → insight matches player better
  6. UI: shows confidence % on creature card
  7. PLAYER: trusts the agent → summons more → growth loop

Pure stdlib.
"""

from __future__ import annotations

import math
import random
from typing import Callable


# ---------------------------------------------------------------------------
# 1. Value — a scalar wrapped in a computational graph node
# ---------------------------------------------------------------------------

class Value:
    def __init__(self, data: float, children: tuple[Value, ...] = (), op: str = ""):
        self.data = data
        self.grad = 0.0
        self._backward: Callable[[], None] = lambda: None
        self._prev: set[Value] = set(children)
        self._op = op

    def __repr__(self) -> str:
        return f"Value(data={self.data:.4f}, grad={self.grad:.4f})"

    # --- forward ops ---

    def __add__(self, other: Value | float) -> Value:
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data + other.data, (self, other), "+")
        def _bw(): self.grad += out.grad; other.grad += out.grad
        out._backward = _bw
        return out

    def __mul__(self, other: Value | float) -> Value:
        other = other if isinstance(other, Value) else Value(other)
        out = Value(self.data * other.data, (self, other), "*")
        def _bw():
            self.grad += out.grad * other.data
            other.grad += out.grad * self.data
        out._backward = _bw
        return out

    def __radd__(self, other: float) -> Value: return self + other
    def __rmul__(self, other: float) -> Value: return self * other
    def __neg__(self) -> Value: return self * -1.0
    def __sub__(self, other: Value | float) -> Value: return self + (-other)

    def __truediv__(self, other: Value | float) -> Value:
        return self * (other ** -1.0) if isinstance(other, Value) else self * (Value(other) ** -1.0)

    def __pow__(self, other: int | float) -> Value:
        assert isinstance(other, (int, float)), "pow needs int/float exponent"
        out = Value(self.data ** other, (self,), f"**{other}")
        def _bw(): self.grad += out.grad * other * (self.data ** (other - 1))
        out._backward = _bw
        return out

    def relu(self) -> Value:
        d = self.data if self.data > 0 else 0.0
        out = Value(d, (self,), "relu")
        def _bw(): self.grad += out.grad * (1.0 if self.data > 0 else 0.0)
        out._backward = _bw
        return out

    def tanh(self) -> Value:
        t = math.tanh(self.data)
        out = Value(t, (self,), "tanh")
        def _bw(): self.grad += out.grad * (1.0 - t * t)
        out._backward = _bw
        return out

    # --- backward ---

    def backward(self) -> None:
        topo, visited = [], set()
        def build(v):
            if v not in visited:
                visited.add(v)
                for c in v._prev:
                    build(c)
                topo.append(v)
        build(self)
        self.grad = 1.0
        for v in reversed(topo):
            v._backward()


# --- Free functions for exp / log (used by softmax / cross-entropy) ----------

def _val_exp(v: Value) -> Value:
    out = Value(math.exp(v.data), (v,), "exp")
    def _bw(): v.grad += out.grad * math.exp(v.data)
    out._backward = _bw
    return out

def _val_log(v: Value) -> Value:
    clipped = max(v.data, 1e-12)
    out = Value(math.log(clipped), (v,), "log")
    def _bw(): v.grad += out.grad / clipped
    out._backward = _bw
    return out


# ---------------------------------------------------------------------------
# 2. Neuron + Layer + MLP (built from Value)
# ---------------------------------------------------------------------------

class Neuron:
    def __init__(self, n_inputs: int):
        self.W = [Value(random.uniform(-1.0, 1.0)) for _ in range(n_inputs)]
        self.b = Value(0.0)

    def __call__(self, x: list[Value]) -> Value:
        acc = Value(0.0)
        for wi, xi in zip(self.W, x):
            acc = acc + wi * xi
        return (acc + self.b).tanh()  # tanh preserves negative gradients

    def parameters(self) -> list[Value]:
        return self.W + [self.b]


class Layer:
    def __init__(self, n_inputs: int, n_outputs: int):
        self.neurons = [Neuron(n_inputs) for _ in range(n_outputs)]

    def __call__(self, x: list[Value]) -> list[Value]:
        return [n(x) for n in self.neurons]

    def parameters(self) -> list[Value]:
        return [p for n in self.neurons for p in n.parameters()]


class MLP:
    def __init__(self, n_inputs: int, n_hidden: int, n_outputs: int):
        self.layers = [Layer(n_inputs, n_hidden), Layer(n_hidden, n_outputs)]

    def __call__(self, x: list[float]) -> list[Value]:
        out = [Value(v) for v in x]
        for layer in self.layers:
            out = layer(out)
        return out

    def parameters(self) -> list[Value]:
        return [p for layer in self.layers for p in layer.parameters()]

    def zero_grad(self) -> None:
        for p in self.parameters():
            p.grad = 0.0


# ---------------------------------------------------------------------------
# 3. Cross-entropy loss (softmax + log)
# ---------------------------------------------------------------------------

def softmax(scores: list[Value]) -> list[Value]:
    m = max(s.data for s in scores)
    exps = [_val_exp(s - Value(m)) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]


def cross_entropy_loss(logits: list[Value], target_idx: int) -> Value:
    probs = softmax(logits)
    return -_val_log(probs[target_idx])


# ---------------------------------------------------------------------------
# 4. XOR demo (canonical test for any autograd engine)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 65)
    print("  Lesson 05: Chain Rule & Automatic Differentiation")
    print("  Training an MLP on XOR (all from scratch)")
    print("=" * 65)

    X = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
    y = [0, 1, 1, 0]  # XOR labels

    model = MLP(2, 16, 2)  # 2 inputs -> 16 hidden -> 2 outputs
    lr = 0.7

    for epoch in range(200):
        total_loss = 0.0
        correct = 0

        for xi, yi in zip(X, y):
            logits = model(xi)
            loss = cross_entropy_loss(logits, yi)
            total_loss += loss.data

            # Accuracy
            pred_i = 0 if logits[0].data > logits[1].data else 1
            if pred_i == yi:
                correct += 1

            # Backward + update (per-example SGD)
            model.zero_grad()
            loss.backward()
            for p in model.parameters():
                p.data -= lr * p.grad

        acc = correct / len(X)
        if epoch % 20 == 0 or epoch == 119:
            print(f"  epoch {epoch:3d}  loss {total_loss/len(X):.4f}  acc {acc:.0%}")

    print("\nFinal predictions:")
    for xi, yi in zip(X, y):
        logits = model(xi)
        p0, p1 = logits[0].data, logits[1].data
        pred_i = 0 if p0 > p1 else 1
        print(f"  XOR{xi} -> class {pred_i} (logits: {p0:.3f}, {p1:.3f})  {'✅' if pred_i == yi else '❌'}")

    print(f"\nTotal parameters: {len(model.parameters())} Value nodes in the graph.")
    print("backward() traced every operation, multiplied local gradients,")
    print("and deposited ∂loss/∂each weight. That is the chain rule.")
    print("That is how every neural network learns.")
