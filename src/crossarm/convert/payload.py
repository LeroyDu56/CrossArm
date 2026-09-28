# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""What the robot carries once it grips a part: the tool's load and the part's, as one FANUC payload.

RAPID keeps them apart: the tool's `tload` (centre of gravity in the flange frame, tool0) and the
payload `GripLoad` adds (centre of gravity in the tool frame). A FANUC payload schedule is all the
flange carries, so a tool holding a part is one schedule of its own: the two masses, their common
centre of gravity, and the inertia about it (parallel axis theorem), in the flange axes. The
schedule keeps the moments about the flange axes only (Ix, Iy, Iz): what the products of inertia
would add is reported rather than dropped silently.
"""

from dataclasses import dataclass

from crossarm.convert.values import Frame, Load
from crossarm.geometry import Mat3, Vec3, mat_mul, mat_vec, quat_to_matrix

NO_LOAD = Load(0.0, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


@dataclass(frozen=True, slots=True)
class Payload:
    mass: float  # kg
    cog: Vec3  # mm, in the flange frame (ABB tool0)
    inertia: Vec3  # kg.m2 about the centre of gravity, flange axes
    products: float  # largest product of inertia about those axes, kg.m2: what a FANUC schedule leaves out


def _tensor(load: Load, axes: Mat3) -> list[list[float]]:
    """The load's inertia tensor about its centre of gravity, in the frame `axes` rotates its aom into."""
    turn = mat_mul(axes, quat_to_matrix(load.aom))
    ix, iy, iz = load.inertia
    return [[sum(turn[i][k] * (ix, iy, iz)[k] * turn[j][k] for k in range(3)) for j in range(3)] for i in range(3)]


def combined(tool: Frame, part: Load | None) -> Payload:
    """The tool's own load, plus the part it holds (None: the tool alone), about their common centre."""
    own = tool.load or NO_LOAD
    identity: Mat3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    bodies = [(own.mass, own.cog, _tensor(own, identity))]
    if part is not None:
        turn = quat_to_matrix(tool.pose.rot)
        moved = mat_vec(turn, part.cog)
        cog = (tool.pose.pos[0] + moved[0], tool.pose.pos[1] + moved[1], tool.pose.pos[2] + moved[2])
        bodies.append((part.mass, cog, _tensor(part, turn)))
    mass = sum(m for m, _, _ in bodies)
    if mass <= 0:
        return Payload(0.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 0.0)
    centre = tuple(sum(m * c[i] for m, c, _ in bodies) / mass for i in range(3))
    total = [[0.0] * 3 for _ in range(3)]
    for m, cog, tensor in bodies:
        d = [(cog[i] - centre[i]) / 1000 for i in range(3)]  # mm -> m
        square = sum(v * v for v in d)
        for i in range(3):
            for j in range(3):
                total[i][j] += tensor[i][j] + m * ((square if i == j else 0.0) - d[i] * d[j])
    products = max(abs(total[0][1]), abs(total[0][2]), abs(total[1][2]))
    return Payload(mass, centre, (total[0][0], total[1][1], total[2][2]), products)  # type: ignore[arg-type]


__all__ = ["NO_LOAD", "Payload", "combined"]
