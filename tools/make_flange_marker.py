# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate flange_marker.stl: a marker to attach, without offset, to the flange of both simulators.

The configuration and pose probes settled every convention CrossArm computes with. One
question is physical and remains: a gripper bolted on the ABB flange and the same gripper
bolted on the FANUC flange, located by the flange's dowel pin, do their tool frames point
the same way? The two makers report their flange frames half a turn apart about z, and the
maths cannot tell whether the pin is half a turn apart too. CrossArm's report says so for
every tool frame and payload.

Attached to tool0 in RobotStudio and to the faceplate in ROBOGUIDE, this marker draws the
flange frame on the robot, next to the pin hole of each maker's flange model:

  long arrow along +X (180 mm, with a head), short bar along +Y (70 mm), 8 mm thick, lying on
  the flange face (+Z out of the flange). Units: millimetres.

Usage:  python tools/make_flange_marker.py [output.stl]   (default tests/fixtures/probes/flange/flange_marker.stl)
"""

import struct
import sys
from pathlib import Path

Vec = tuple[float, float, float]
Triangle = tuple[Vec, Vec, Vec]


def box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> list[Triangle]:
    """A closed box as 12 outward-facing triangles."""
    p = {(i, j, k): (x, y, z) for i, x in enumerate((x0, x1)) for j, y in enumerate((y0, y1))
         for k, z in enumerate((z0, z1))}  # fmt: skip
    quads = [  # counter-clockwise seen from outside
        ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)),  # z0
        ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),  # z1
        ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),  # y0
        ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)),  # y1
        ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)),  # x0
        ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),  # x1
    ]
    out: list[Triangle] = []
    for a, b, c, d in quads:
        out += [(p[a], p[b], p[c]), (p[a], p[c], p[d])]
    return out


def prism(points: list[tuple[float, float]], z0: float, z1: float) -> list[Triangle]:
    """A convex polygon (counter-clockwise, in the XY plane) extruded from z0 to z1."""
    out: list[Triangle] = []
    bottom = [(x, y, z0) for x, y in points]
    top = [(x, y, z1) for x, y in points]
    for i in range(1, len(points) - 1):
        out.append((bottom[0], bottom[i + 1], bottom[i]))
        out.append((top[0], top[i], top[i + 1]))
    for i in range(len(points)):
        j = (i + 1) % len(points)
        out += [(bottom[i], bottom[j], top[j]), (bottom[i], top[j], top[i])]
    return out


def marker() -> list[Triangle]:
    thick = 8.0
    triangles = box(0, 150, -4, 4, 0, thick)  # +X shaft
    triangles += prism([(150, -18), (185, 0), (150, 18)], 0, thick)  # +X head
    triangles += box(-4, 4, 4, 70, 0, thick)  # +Y bar, shorter, no head
    return triangles


def normal(t: Triangle) -> Vec:
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
    u, v = (bx - ax, by - ay, bz - az), (cx - ax, cy - ay, cz - az)
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = sum(c * c for c in n) ** 0.5 or 1.0
    return (n[0] / length, n[1] / length, n[2] / length)


def binary_stl(triangles: list[Triangle]) -> bytes:
    header = b"CrossArm flange marker: +X long arrow, +Y short bar, mm".ljust(80, b" ")
    body = b"".join(struct.pack("<12fH", *normal(t), *t[0], *t[1], *t[2], 0) for t in triangles)
    return header + struct.pack("<I", len(triangles)) + body


def main() -> None:
    default = Path(__file__).resolve().parents[1] / "tests/fixtures/probes/flange/flange_marker.stl"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(binary_stl(marker()))
    print(f"{out} written")


if __name__ == "__main__":
    main()
