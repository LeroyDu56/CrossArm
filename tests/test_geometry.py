# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Quaternion / WPR math: hand-checked cases + property tests on random rotations."""

import math
import random

import pytest

from crossarm.geometry import (
    Pose,
    mat_mul,
    matrix_to_quat,
    matrix_to_wpr,
    quat_to_matrix,
    quat_to_wpr,
    rot_x,
    rot_y,
    rot_z,
    wpr_to_matrix,
)

S = math.sqrt(0.5)


def assert_matrix_close(a, b, tol=1e-9):
    for row_a, row_b in zip(a, b, strict=True):
        assert row_a == pytest.approx(row_b, abs=tol)


def random_quats(n, seed=1234):
    rng = random.Random(seed)
    for _ in range(n):
        q = [rng.gauss(0, 1) for _ in range(4)]
        norm = math.sqrt(sum(c * c for c in q))
        yield tuple(c / norm for c in q)


# ---------------------------------------------------------------------------
# Hand-checked cases (values an FSE sees on a pendant every day)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("quat", "wpr"),
    [
        ((1, 0, 0, 0), (0, 0, 0)),
        ((S, S, 0, 0), (90, 0, 0)),  # +90 about X
        ((S, 0, S, 0), (0, 90, 0)),  # +90 about Y (gimbal lock: W forced to 0)
        ((S, 0, 0, S), (0, 0, 90)),  # +90 about Z
        ((S, 0, 0, -S), (0, 0, -90)),
        ((0, 1, 0, 0), (180, 0, 0)),  # tool pointing down, 180 about X
        ((0, 0, 1, 0), (180, 0, 180)),  # 180 about Y == W=180, R=180
        ((0, 0, 0, 1), (0, 0, 180)),
    ],
)
def test_known_orientations(quat, wpr):
    assert quat_to_wpr(quat) == pytest.approx(wpr, abs=1e-9)


def test_order_is_fixed_xyz():
    # W=90 then P=90 about FIXED axes must equal Ry(90).Rx(90), not Rx(90).Ry(90).
    assert_matrix_close(wpr_to_matrix(90, 90, 0), mat_mul(rot_y(90), rot_x(90)))
    assert_matrix_close(wpr_to_matrix(10, 20, 30), mat_mul(rot_z(30), mat_mul(rot_y(20), rot_x(10))))


def test_quaternion_is_normalised_first():
    # RAPID stores 6 decimals: slightly off-unit quaternions are the norm.
    assert quat_to_wpr((2, 0, 0, 0)) == pytest.approx((0, 0, 0))
    with pytest.raises(ValueError):
        quat_to_wpr((0, 0, 0, 0))


# ---------------------------------------------------------------------------
# Properties over random rotations (fixed seeds: reproducible)
# ---------------------------------------------------------------------------


def test_quat_wpr_round_trip():
    for q in random_quats(2000):
        w, p, r = quat_to_wpr(q)
        assert all(-180 < a <= 180 for a in (w, p, r)), q
        assert -90 <= p <= 90, q
        assert_matrix_close(wpr_to_matrix(w, p, r), quat_to_matrix(q))


def test_matrix_quat_round_trip():
    for q in random_quats(500, seed=99):
        back = matrix_to_quat(quat_to_matrix(q))
        sign = 1 if q[0] >= 0 else -1  # q and -q are the same rotation
        assert back == pytest.approx(tuple(sign * c for c in q), abs=1e-9), q


@pytest.mark.parametrize("p", [90.0, -90.0, 89.9999999999, -89.9999999999])
def test_gimbal_lock_still_reproduces_rotation(p):
    m = wpr_to_matrix(35.0, p, -120.0)
    w2, p2, r2 = matrix_to_wpr(m)
    assert_matrix_close(wpr_to_matrix(w2, p2, r2), m, tol=1e-6)


# ---------------------------------------------------------------------------
# Offs / RelTool
# ---------------------------------------------------------------------------


def test_offs_translates_in_workobject_frame():
    p = Pose((100, 200, 300), (0, 1, 0, 0))
    assert p.offs(0, 0, 50) == Pose((100, 200, 350), (0, 1, 0, 0))


def test_reltool_translates_along_tool_z():
    # Tool pointing down (180 about X): +Z tool = -Z work object.
    p = Pose((100, 200, 300), (0, 1, 0, 0)).rel_tool(0, 0, 50)
    assert p.pos == pytest.approx((100, 200, 250))


def test_reltool_rotations_are_about_tool_axes_x_then_y_then_z():
    base = Pose((0, 0, 0), (1, 0, 0, 0))
    moved = base.rel_tool(0, 0, 0, rx=90, rz=90)
    assert_matrix_close(quat_to_matrix(moved.rot), mat_mul(rot_x(90), rot_z(90)))


def test_compose_matches_matrix_product():
    a = Pose((10, 0, 0), (S, 0, 0, S))  # 90 about Z
    b = Pose((5, 0, 0), (1, 0, 0, 0))
    c = a.compose(b)
    assert c.pos == pytest.approx((10, 5, 0))
