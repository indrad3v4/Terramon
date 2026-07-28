"""LoRA-style adaptation — low-rank matrix pairs for MoE network finetuning.

Phase 10 (Finetuning): LoRA adapters let us finetune the MoE network in
k3_insight_engine without modifying its original weights. Each adapter is a
pair of low-rank matrices (A, B) that produce a delta weight ΔW = B @ A.

This module is purely additive — it does NOT modify k3_insight_engine.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class LoRAConfig:
    """Configuration for a single LoRA adapter.

    Attributes:
        rank: Low-rank dimension r (typically 1-8).
        alpha: Scaling factor. The update is scaled by alpha / rank.
        target_modules: Which weight matrices to adapt.
                         "all" adapts every module; a list ("W1", "W2") picks specific ones.
        init_scale: Standard deviation for initializing A (B is zero-initialized).
    """
    rank: int = 4
    alpha: float = 1.0
    target_modules: str | list[str] = "all"
    init_scale: float = 0.02


@dataclass
class LoRALinear:
    """A LoRA low-rank pair for one linear layer.

    For a frozen weight W ∈ ℝ^(d×k), the adaptation is:
        h = Wx + (α / r) * (B @ A) @ x
    where B ∈ ℝ^(d×r), A ∈ ℝ^(r×k), α = alpha, r = rank.

    Attributes:
        A: Random-initialized matrix  (r × k).
        B: Zero-initialized matrix    (d × r).
        config: The LoRAConfig used to build this pair.
    """
    A: list[list[float]]
    B: list[list[float]]
    config: LoRAConfig = field(default_factory=LoRAConfig)

    @property
    def rank(self) -> int:
        return len(self.A) if self.A else 0

    def scale(self) -> float:
        """Return the LoRA scaling factor: alpha / rank."""
        return self.config.alpha / max(self.rank, 1)

    def delta_weight(self) -> list[list[float]] | None:
        """Compute ΔW = B @ A as a dense matrix, or None if empty."""
        if not self.A or not self.B or not self.A[0]:
            return None
        k = len(self.A[0])     # input dimension
        d = len(self.B)        # output dimension
        s = self.scale()
        delta = [[0.0] * k for _ in range(d)]
        for i in range(d):
            for j in range(k):
                total = 0.0
                for r_ in range(self.rank):
                    total += self.B[i][r_] * self.A[r_][j]
                delta[i][j] = total * s
        return delta

    def apply(self, weights: list[list[float]]) -> list[list[float]]:
        """Return adapted weights: W + ΔW (in-place copy)."""
        delta = self.delta_weight()
        if delta is None:
            return [row[:] for row in weights]
        d = len(weights)
        k = len(weights[0]) if weights else 0
        adapted = [row[:] for row in weights]
        for i in range(min(d, len(delta))):
            for j in range(min(k, len(delta[i]))):
                adapted[i][j] += delta[i][j]
        return adapted


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_lora_adapter(
    out_dim: int,
    in_dim: int,
    config: LoRAConfig | None = None,
    seed: int = 42,
) -> LoRALinear:
    """Create a LoRA low-rank pair (A, B) for a weight matrix of shape (out_dim, in_dim).

    A is random-normal (init_scale), B is zero-initialized so ΔW = 0 initially
    (training starts from the frozen base weights).

    Args:
        out_dim: Output dimension of the target linear layer (d).
        in_dim:  Input dimension of the target linear layer (k).
        config:  LoRA hyperparameters (rank, alpha, …).
        seed:    Random seed for reproducibility.

    Returns:
        A LoRALinear instance that can be applied via .apply(weights).
    """
    cfg = config or LoRAConfig()
    rng = random.Random(seed)

    # A: (rank, in_dim) — random normal
    A = [[rng.gauss(0.0, cfg.init_scale) for _ in range(in_dim)] for _ in range(cfg.rank)]

    # B: (out_dim, rank) — all zeros
    B = [[0.0] * cfg.rank for _ in range(out_dim)]

    return LoRALinear(A=A, B=B, config=cfg)


def create_expert_lora_adapters(
    config: LoRAConfig | None = None,
    seed: int = 100,
) -> dict[str, LoRALinear]:
    """Create LoRA adapters for the MoE FastExpert layers (W1: 64×8, W2: 8×1).

    Returns a dict keyed by layer name: {"expert_W1": LoRALinear, "expert_W2": LoRALinear}.
    These can be applied to each expert's W1 and W2 during forward pass.

    Applies to the raw-math dimensions from k3_insight_engine:
        FastExpert.W1: shape (64, 8)  — 64 in, 8 hidden
        FastExpert.W2: shape (8, 1)   — 8 in, 1 out  (stored as list[float] length 8)
    """
    cfg = config or LoRAConfig(rank=2, alpha=1.0)
    return {
        "expert_W1": create_lora_adapter(out_dim=64, in_dim=8, config=cfg, seed=seed),
        "expert_W2": create_lora_adapter(out_dim=8, in_dim=1, config=cfg, seed=seed + 1),
    }


def apply_lora_to_expert(
    W1: list[list[float]],
    W2: list[float],
    adapters: dict[str, LoRALinear],
) -> tuple[list[list[float]], list[float]]:
    """Apply LoRA adapters to an expert's weight matrices.

    Args:
        W1: Expert input weight matrix (64 × 8).
        W2: Expert output weight vector  (8, stored as list of 8 floats).
        adapters: Dict from create_expert_lora_adapters() containing
                  "expert_W1" and "expert_W2" adapters.

    Returns:
        (adapted_W1, adapted_W2) — new lists that can replace the originals.
    """
    adapted_W1 = adapters["expert_W1"].apply(W1)

    # W2 is (8,) — reshape to (8×1) for the generic apply, then flatten back
    W2_as_matrix = [[w] for w in W2]
    adapted_W2_matrix = adapters["expert_W2"].apply(W2_as_matrix)
    adapted_W2 = [row[0] for row in adapted_W2_matrix]

    return adapted_W1, adapted_W2


# ---------------------------------------------------------------------------
# Adapter stack (for applying LoRA to all experts at once)
# ---------------------------------------------------------------------------


@dataclass
class MoELoRAStack:
    """Manages LoRA adapters for all experts in the MoE network.

    Usage:
        stack = MoELoRAStack(num_experts=12)
        adapted_w1, adapted_w2 = stack.apply_to_expert(0, raw_w1, raw_w2)
    """

    adapters_per_expert: list[dict[str, LoRALinear]]
    config: LoRAConfig = field(default_factory=lambda: LoRAConfig(rank=2, alpha=1.0))

    def __init__(self, num_experts: int = 12, config: LoRAConfig | None = None) -> None:
        self.config = config or LoRAConfig(rank=2, alpha=1.0)
        self.adapters_per_expert = [
            create_expert_lora_adapters(self.config, seed=100 + i)
            for i in range(num_experts)
        ]

    def apply_to_expert(
        self,
        expert_idx: int,
        W1: list[list[float]],
        W2: list[float],
    ) -> tuple[list[list[float]], list[float]]:
        """Apply LoRA to a single expert's weights.

        Args:
            expert_idx: Index of the expert (0-based).
            W1: Expert W1 matrix.
            W2: Expert W2 vector.

        Returns:
            (adapted_W1, adapted_W2)
        """
        return apply_lora_to_expert(
            W1, W2, self.adapters_per_expert[expert_idx],
        )

    def merge_all(self, experts: list) -> None:
        """Merge all LoRA deltas into expert weights in-place.

        Args:
            experts: List of FastExpert-like objects with .W1 and .W2 attributes.
        """
        for i, expert in enumerate(experts):
            adapted_W1, adapted_W2 = self.apply_to_expert(
                i, expert.W1, expert.W2
            )
            expert.W1 = adapted_W1
            expert.W2 = adapted_W2
