# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Rigid-body math shared by all brands. Pure Python, no numpy.

Conventions
-----------
* Quaternions are ABB order, scalar first: (q1, q2, q3, q4) = (w, x, y, z).
* Rotation matrices are 3x3 row-major tuples, acting on column vectors.
* FANUC W, P, R (degrees) are rotations about the FIXED X, Y, Z axes, applied
  in that order:  R = Rz(r) . Ry(p) . Rx(w)
  (equivalently: intrinsic Z, then Y', then X'').

This is the part of the converter most exposed to silent errors: every
function here is covered by property tests (round trips over random
rotations) in tests/test_geometry.py.
"""

import math
from dataclasses import dataclass

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]
Mat3 = tuple[Vec3, Vec3, Vec3]

# Below this, cos(P) is treated as 0: gimbal lock, W and R are not separable.
_GIMBAL_EPS = 1e-9


def normalise(q: Quat) -> Quat:
    norm = math.sqrt(sum(c * c for c in q))
    if norm < 1e-12:
        raise ValueError("zero-length quaternion")
    w, x, y, z = (c / norm for c in q)
    return (w, x, y, z)


def quat_to_matrix(q: Quat) -> Mat3:
    w, x, y, z = normalise(q)
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)),
        (2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)),
        (2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)),
    )


def matrix_to_quat(m: Mat3) -> Quat:
    """Shepperd's method: numerically stable for every rotation."""
    (m00, m01, m02), (m10, m11, m12), (m20, m21, m22) = m
    trace = m00 + m11 + m22
    if trace > 0:
        s = 2 * math.sqrt(trace + 1)
        q = (s / 4, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s)
    elif m00 > m11 and m00 > m22:
        s = 2 * math.sqrt(1 + m00 - m11 - m22)
        q = ((m21 - m12) / s, s / 4, (m01 + m10) / s, (m02 + m20) / s)
    elif m11 > m22:
        s = 2 * math.sqrt(1 + m11 - m00 - m22)
        q = ((m02 - m20) / s, (m01 + m10) / s, s / 4, (m12 + m21) / s)
    else:
        s = 2 * math.sqrt(1 + m22 - m00 - m11)
        q = ((m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, s / 4)
    q = normalise(q)
    return q if q[0] >= 0 else (-q[0], -q[1], -q[2], -q[3])


def matrix_to_wpr(m: Mat3) -> Vec3:
    """Rotation matrix -> FANUC (W, P, R) in degrees, each in (-180, 180]."""
    (r11, r12, _), (r21, r22, _), (r31, r32, r33) = m
    cos_p = math.hypot(r11, r21)
    p = math.atan2(-r31, cos_p)
    if cos_p > _GIMBAL_EPS:
        w = math.atan2(r32, r33)
        r = math.atan2(r21, r11)
    else:
        # P = +/-90 deg: only W -/+ R is defined. Convention: W = 0.
        w = 0.0
        r = math.atan2(-r12, r22)
    return (_wrap_deg(math.degrees(w)), _wrap_deg(math.degrees(p)), _wrap_deg(math.degrees(r)))


def wpr_to_matrix(w_deg: float, p_deg: float, r_deg: float) -> Mat3:
    return mat_mul(rot_z(r_deg), mat_mul(rot_y(p_deg), rot_x(w_deg)))


def quat_to_wpr(q: Quat) -> Vec3:
    return matrix_to_wpr(quat_to_matrix(q))


def rot_x(deg: float) -> Mat3:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))


def rot_y(deg: float) -> Mat3:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


def rot_z(deg: float) -> Mat3:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def mat_mul(a: Mat3, b: Mat3) -> Mat3:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))  # type: ignore[return-value]


def mat_vec(m: Mat3, v: Vec3) -> Vec3:
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))  # type: ignore[return-value]


def _wrap_deg(angle: float) -> float:
    """Wrap to (-180, 180], and turn -0.0 / 1e-15 noise into a clean 0.0."""
    angle = math.fmod(angle, 360.0)
    if angle <= -180.0:
        angle += 360.0
    elif angle > 180.0:
        angle -= 360.0
    return 0.0 if abs(angle) < 1e-9 else angle


@dataclass(frozen=True, slots=True)
class Pose:
    """Position (mm) + orientation (unit quaternion, ABB order)."""

    pos: Vec3
    rot: Quat

    def compose(self, other: "Pose") -> "Pose":
        """self * other: `other` expressed in the frame `self`."""
        m = quat_to_matrix(self.rot)
        moved = mat_vec(m, other.pos)
        pos = (self.pos[0] + moved[0], self.pos[1] + moved[1], self.pos[2] + moved[2])
        return Pose(pos, matrix_to_quat(mat_mul(m, quat_to_matrix(other.rot))))

    def inverse(self) -> "Pose":
        """The pose that composes with this one to the identity."""
        m = quat_to_matrix(self.rot)
        mt = tuple(tuple(m[j][i] for j in range(3)) for i in range(3))
        moved = mat_vec(mt, self.pos)  # type: ignore[arg-type]
        return Pose((-moved[0], -moved[1], -moved[2]), matrix_to_quat(mt))  # type: ignore[arg-type]

    def offs(self, dx: float, dy: float, dz: float) -> "Pose":
        """ABB Offs(): translation along the work object axes, orientation kept."""
        return Pose((self.pos[0] + dx, self.pos[1] + dy, self.pos[2] + dz), self.rot)

    def rel_tool(self, dx: float, dy: float, dz: float, rx: float = 0.0, ry: float = 0.0, rz: float = 0.0) -> "Pose":
        """ABB RelTool(): displacement and rotations in the TOOL frame.

        Per the RAPID manual, rotations are applied about the tool's own axes,
        first x, then y, then z  ->  R_new = R . Rx . Ry . Rz
        """
        m = quat_to_matrix(self.rot)
        moved = mat_vec(m, (dx, dy, dz))
        pos = (self.pos[0] + moved[0], self.pos[1] + moved[1], self.pos[2] + moved[2])
        rot = mat_mul(m, mat_mul(rot_x(rx), mat_mul(rot_y(ry), rot_z(rz))))
        return Pose(pos, matrix_to_quat(rot))

    def wpr(self) -> Vec3:
        return quat_to_wpr(self.rot)
