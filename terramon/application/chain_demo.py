"""Chain demo — shows the full path from math to player confidence.

The chain:
  1. MATH: ∂L/∂W = (pred − target) · x                           (chain rule)
  2. AUTOGRAD: backward() traces the graph, multiplies local gradients  (Value class)
  3. NETWORK: MLP on thought vectors                                    (Neuron/Layer/MLP)
  4. TRAINING: forward → backward → W -= lr·∂L/∂W                     (gradient descent)
  5. ACCURACY: softmax confidence rises → insight matches better       (cross-entropy)
  6. INSIGHT: theme → DRIVER + BARRIER → THEREFORE                    (insight_engine)
  7. UI CARD: confidence % shown on the creature card                  (TMA)
  8. PLAYER: trusts the agent → summons more → tells friends          (growth loop)

Run: python -m terramon.application.chain_demo
"""

from __future__ import annotations

import os
import sys

# Ensure root is on the path for terramon imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from terramon.application.autograd import MLP, cross_entropy_loss, softmax, Value
from terramon.application.insight_engine import encode, _THEMES, _DRIVER_BY_THEME, _BARRIER_BY_THEME, _BEHAVIOR_BY_BARRIER

# ---- Step 1-3: Build a 2-layer MLP that learns thought→theme mapping ----
# One-hot vocabulary for our theme words
VOCAB = ["afraid", "nobody", "rent", "boss", "lost", "interview", "money", "alone", "work", "stuck"]

def encode_simple(text: str) -> list[float]:
    vec = [0.0] * len(VOCAB)
    for w in text.lower().split():
        if w in VOCAB:
            vec[VOCAB.index(w)] += 1.0
    import math
    norm = math.sqrt(sum(v*v for v in vec))
    return [v/norm for v in vec] if norm else vec

# Training data: 10 examples mapping thought texts → theme indices
TRAIN_DATA = [
    ("i am afraid of the interview", 2),    # fear
    ("nobody is here with me", 3),          # loneliness
    ("i can't pay the rent money", 0),      # money
    ("boss gave me more work", 1),          # work
    ("lost and stuck again", 4),            # direction
    ("scared and terrified alone", 2),      # fear
    ("broke with no money left", 0),        # money
    ("exhausted from work burnout", 1),     # work
    ("lonely and isolated nobody", 3),      # loneliness
    ("confused no purpose lost", 4),        # direction
]

print("=" * 75)
print("  THE CHAIN: math → autograd → insight → TMA card → player confidence")
print("=" * 75)

# Build & train the MLP
model = MLP(len(VOCAB), 8, len(_THEMES))
lr = 0.5

print("\n▸ STEP 1: Training MLP on 10 thought→theme examples...")
for epoch in range(80):
    total_loss = 0.0
    for text, yi in TRAIN_DATA:
        x = encode_simple(text)
        logits = model(x)
        loss = cross_entropy_loss(logits, yi)
        total_loss += loss.data
        model.zero_grad()
        loss.backward()
        for p in model.parameters():
            p.data -= lr * p.grad
    if epoch % 20 == 0:
        print(f"  epoch {epoch:3d}  loss {total_loss/len(TRAIN_DATA):.4f}")

# ---- Step 4-5: Test a player thought and measure confidence ----
print("\n▸ STEP 2: A player types a thought...")
test_thought = "i am broken and alone in this city nobody cares"
print(f"  \"{test_thought}\"")

x = encode_simple(test_thought)
logits = model(x)
probs = softmax(logits)

# ---- Step 6: Map to insight ----
theme_idx = max(range(len(probs)), key=lambda i: probs[i].data)
confidence = probs[theme_idx].data
theme = _THEMES[theme_idx]
driver = _DRIVER_BY_THEME[theme]
barrier = _BARRIER_BY_THEME[theme]
therefore = _BEHAVIOR_BY_BARRIER.get(barrier, _BEHAVIOR_BY_BARRIER["the quiet ordinary"])

print(f"\n▸ STEP 3: Autograd forward pass computes theme scores...")
for i, t in enumerate(_THEMES):
    bar = "← best" if i == theme_idx else ""
    print(f"  {t:11}  {logits[i].data:+.3f}  (softmax: {probs[i].data:.1%})  {bar}")

print(f"\n▸ STEP 4: Chain rule + backward deposits ∂loss/∂W on every weight...")
sample_weight = model.layers[0].neurons[0].W[0]
print(f"  Example: weight[0][0] before update = {sample_weight.data:.4f}, grad = {sample_weight.grad:.4f}")
print(f"  The gradient ∂L/∂W[{theme}][word0] = (pred − target) · x[word0]")
print(f"  → if pred > target → grad is positive → weight DECREASES (less confident in wrong theme)")
print(f"  → if pred < target → grad is negative → weight INCREASES (more confident in correct theme)")

# ---- Step 7-8: The insight that drives the agent ----
print(f"\n▸ STEP 5: The INSIGHT emerges (theme = {theme}, confidence = {confidence:.1%})")
print(f"  DRIVER:    {driver}")
print(f"  BARRIER:   {barrier}")
print(f"  THEREFORE: {therefore}")

print(f"\n▸ STEP 6: The creature card shows this to the player...")
print(f"  ┌─────────────────────────────────────────────┐")
print(f"  │  ⟡ BROKEN ⟡                                │")
print(f"  │  \"i am broken and alone in this city...\"    │")
print(f"  │                                             │")
print(f"  │  INSIGHT: It stays close, a warm weight     │")
print(f"  │  at your side.                              │")
print(f"  │  Intelligence: {confidence:.0%}                              │")
print(f"  │  Lv.3 · 4/5 to Tamer                        │")
print(f"  └─────────────────────────────────────────────┘")

print(f"\n▸ STEP 7: The player sees {confidence:.0%} confidence → trusts the agent →")
print(f"           summons more → tells friends → growth loop.")

print("\n" + "=" * 75)
print("  The chain is closed. Every link is the chain rule.")
print("  That is how every neural network learns.")
print("=" * 75)
