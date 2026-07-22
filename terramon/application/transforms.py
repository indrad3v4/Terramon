"""Matrix transformations — build-via-learn Lesson 03 (Matrix Transformations).

Course hook: "A matrix is a machine that reshapes space. Learn what it does to
every point, and you understand the whole transformation."

In Terramon, the same idea powers the Insight Engine: a thought is ENCODED
into a vector `x`, then a weight matrix `W` TRANSFORMS it from word-space into
theme-space (`W @ x + b`). That `W @ x` is not arithmetic trivia — it is a
SPACE WARP. This module makes that visible with plain 2D transforms
(rotate / scale / shear / compose) you can print, plus `transform_vector`
which reuses the exact Insight Engine matmul to show a real thought being
warped into theme-space.

Pure stdlib (math). No external deps.
"""

from __future__ import annotations

import math
from typing import Sequence

# A 2D point is [x, y].
Point = list[float]
Matrix2 = list[list[float]]  # 2x2


# ---------------------------------------------------------------------------
# Basic 2x2 transforms — each one is a matrix that warps every point
# ---------------------------------------------------------------------------

def rotation(theta_deg: float) -> Matrix2:
    """Rotate the plane by theta degrees (counter-clockwise)."""
    t = math.radians(theta_deg)
    c, s = math.cos(t), math.sin(t)
    return [[c, -s], [s, c]]


def scale(sx: float, sy: float) -> Matrix2:
    """Scale x by sx, y by sy."""
    return [[sx, 0.0], [0.0, sy]]


def shear(k: float) -> Matrix2:
    """Shear: x' = x + k*y (slant the vertical axis)."""
    return [[1.0, k], [0.0, 1.0]]


def compose(a: Matrix2, b: Matrix2) -> Matrix2:
    """Matrix product A @ B (apply B first, then A)."""
    return [
        [
            a[0][0] * b[0][0] + a[0][1] * b[1][0],
            a[0][0] * b[0][1] + a[0][1] * b[1][1],
        ],
        [
            a[1][0] * b[0][0] + a[1][1] * b[1][0],
            a[1][0] * b[0][1] + a[1][1] * b[1][1],
        ],
    ]


def apply(m: Matrix2, p: Point) -> Point:
    """m @ p — transform a single point. This IS the warp."""
    return [
        m[0][0] * p[0] + m[0][1] * p[1],
        m[1][0] * p[0] + m[1][1] * p[1],
    ]


# ---------------------------------------------------------------------------
# Terramon tie-in: reuse the Insight Engine's real matmul (Lesson 02 W @ x)
# ---------------------------------------------------------------------------

def transform_vector(W: Sequence[Sequence[float]], x: Sequence[float]) -> list[float]:
    """Project a thought-vector from word-space into theme-space via W @ x.

    This is the literal matrix-transformation view of what extract_insight does:
    the weight matrix W warps the encoded thought `x` so that each output
    coordinate is "how strongly this thought expresses theme i". Identical
    math to insight_engine._matvec — imported there, mirrored here for teaching.
    """
    return [sum(w_ij * x_j for w_ij, x_j in zip(row, x)) for row in W]
