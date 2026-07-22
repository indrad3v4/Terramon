"""Tests for terramon/application/transforms.py (Lesson 03)."""

from __future__ import annotations

import math

from terramon.application import transforms as T
from terramon.application.insight_engine import extract_insight, W, encode, _THEMES


def test_rotation_90_maps_x_axis_to_y():
    # (1,0) rotated 90 CCW -> (0,1)
    r = T.rotation(90)
    out = T.apply(r, [1.0, 0.0])
    assert abs(out[0]) < 1e-9 and abs(out[1] - 1.0) < 1e-9


def test_scale_doubles_x_only():
    s = T.scale(2.0, 1.0)
    out = T.apply(s, [3.0, 5.0])
    assert out == [6.0, 5.0]


def test_shear_slants_y_into_x():
    sh = T.shear(2.0)
    out = T.apply(sh, [1.0, 3.0])  # x' = 1 + 2*3 = 7
    assert out == [7.0, 3.0]


def test_compose_matches_manual_multiply():
    a = T.scale(2.0, 1.0)
    b = T.rotation(90)
    composed = T.compose(a, b)
    manual = [[0.0, -2.0], [1.0, 0.0]]  # scale @ rotation
    for i in range(2):
        for j in range(2):
            assert abs(composed[i][j] - manual[i][j]) < 1e-9


def test_compose_is_associative_style_apply():
    # compose(scale, rotation) applied to a point == scale(rotation(point))
    p = [1.0, 0.0]
    c = T.compose(T.scale(2.0, 1.0), T.rotation(90))
    out_compose = T.apply(c, p)
    out_step = T.apply(T.scale(2.0, 1.0), T.apply(T.rotation(90), p))
    assert all(abs(a - b) < 1e-9 for a, b in zip(out_compose, out_step))


def test_transform_vector_matches_extract_insight_argmax():
    # The warp W @ x must push a fear-themed thought to the 'fear' theme.
    text = "i am afraid of the interview tomorrow"
    x = encode(text)
    scores = T.transform_vector(W, x)
    # argmax of the warp == extract_insight's chosen theme
    best = max(range(len(scores)), key=lambda i: scores[i])
    assert _THEMES[best] == extract_insight(text).barrier or _THEMES[best] == "neutral"


def test_transform_vector_shape():
    x = encode("money rent broke")
    out = T.transform_vector(W, x)
    assert len(out) == len(W)  # one score per theme row
