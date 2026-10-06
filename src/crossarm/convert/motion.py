# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID speeds and zones -> FANUC ones, from measurements of both robots.

Neither has an exact equivalent, and both depend on the robots, so CrossArm uses a motion profile
measured by tools/probe_motion.py: the same moves run on an ABB robot in RobotStudio and on a FANUC
robot in ROBOGUIDE.

Joint moves. A MoveJ takes about as long as its TCP path at the RAPID speed; a FANUC J move, its
joint path at a share of the axes' top speed. J % = RAPID TCP speed / joint_speed_ref_mm_s, where the
reference is the TCP speed a J 100 % move would reach. It depends on the move: 3,800 to 5,600 mm/s
on the three moves measured on an M-20iD/25, 4,400 as their centre, where the old default of 2,000
made the FANUC 2 to 2.5 times faster than the ABB.

Zones. A RAPID zone rounds a corner by about the same distance at any speed (z10: 5 mm from the
corner at 200 to 1000 mm/s); a CNT rounds it by a distance that grows with the speed (CNT50: 1.9 mm
at 200 mm/s, 11 mm at 1000). The profile holds both, measured on a right-angle corner: how close the
TCP comes to the corner for each zone radius, and for each CNT at each speed. The CNT written is the
smallest that rounds the corner as much as the RAPID zone does, at the move's speed. When even CNT100
rounds less, CNT100 is written and the report says so: the FANUC path stays closer to the corner.
Linear and circular moves use the linear tables, joint moves the joint ones (FANUC speed in %).

Measured on one right-angle corner with 300 and 400 mm legs, both at the same speed; another FANUC
model has other tables (run the probe on it). Into a faster move the FANUC rounds more than at the
zoned move's speed, into a slower one less: crossarm.convert.translate matches a corner into a faster
move at that move's speed (tools/make_path_probe.py measured approaches, retracts, reversals, other
angles and short moves: the FANUC stays within about 1 mm of the ABB's path, or closer to the points).
"""

from dataclasses import dataclass
from itertools import pairwise

from crossarm.rapid import nodes as n

Table = dict[float, tuple[tuple[float, float], ...]]  # speed -> ((zone radius or CNT, corner cut mm), ...)


@dataclass(frozen=True)
class MotionProfile:
    name: str
    joint_speed_ref_mm_s: float
    abb: dict[str, Table]  # "L" / "J" -> RAPID TCP speed (mm/s) -> (zone radius mm, cut mm)
    fanuc: dict[str, Table]  # "L" -> speed mm/s, "J" -> speed % -> (CNT, cut mm)

    @classmethod
    def from_dict(cls, data: dict) -> "MotionProfile":
        """The JSON tools/probe_motion.py fit writes (keys are strings there)."""

        def tables(side: dict) -> dict[str, Table]:
            return {kind: {float(speed): tuple((float(x), float(cut)) for x, cut in points)
                           for speed, points in by_speed.items()} for kind, by_speed in side.items()}  # fmt: skip

        return cls(str(data["name"]), float(data["joint_speed_ref_mm_s"]), tables(data["abb"]), tables(data["fanuc"]))

    def to_dict(self) -> dict:
        def tables(side: dict[str, Table]) -> dict:
            return {kind: {f"{speed:g}": [list(p) for p in points] for speed, points in by_speed.items()}
                    for kind, by_speed in side.items()}  # fmt: skip

        return {"name": self.name, "joint_speed_ref_mm_s": self.joint_speed_ref_mm_s, "abb": tables(self.abb),
                "fanuc": tables(self.fanuc)}  # fmt: skip


def _interpolate(points: tuple[tuple[float, float], ...], x: float) -> float:
    """Piecewise linear through the points, sorted by x; straight on past the last two at either end."""
    if x <= points[0][0]:
        (x0, y0), (x1, y1) = points[0], points[1]
    elif x >= points[-1][0]:
        (x0, y0), (x1, y1) = points[-2], points[-1]
    else:
        (x0, y0), (x1, y1) = next((a, b) for a, b in pairwise(points) if a[0] <= x <= b[0])
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def abb_cut(profile: MotionProfile, kind: str, radius_mm: float, speed_mm_s: float) -> float:
    """How close the ABB TCP comes to a corner passed with that zone: nearly the same at any speed, so the
    nearest measured speeds are interpolated and never extrapolated."""
    by_speed = profile.abb[kind]
    speeds = sorted(by_speed)
    points = {s: ((0.0, 0.0), *by_speed[s]) for s in speeds}  # radius 0: through the corner
    if speed_mm_s <= speeds[0] or len(speeds) == 1:
        return max(0.0, _interpolate(points[speeds[0]], radius_mm))
    if speed_mm_s >= speeds[-1]:
        return max(0.0, _interpolate(points[speeds[-1]], radius_mm))
    low = max(s for s in speeds if s <= speed_mm_s)
    high = min(s for s in speeds if s >= speed_mm_s)
    a, b = _interpolate(points[low], radius_mm), _interpolate(points[high], radius_mm)
    return max(0.0, a if high == low else a + (b - a) * (speed_mm_s - low) / (high - low))


def fanuc_cut(profile: MotionProfile, kind: str, cnt: float, speed: float) -> float:
    """How close the FANUC TCP comes to the corner with that CNT at that speed (mm/s, or % for J). Between
    measured speeds: interpolated; outside: in proportion to the speed, as measured between them."""
    by_speed = profile.fanuc[kind]
    speeds = sorted(by_speed)
    if speed <= speeds[0]:
        return _interpolate(by_speed[speeds[0]], cnt) * speed / speeds[0]
    if speed >= speeds[-1]:
        return _interpolate(by_speed[speeds[-1]], cnt) * speed / speeds[-1]
    low = max(s for s in speeds if s <= speed)
    high = min(s for s in speeds if s >= speed)
    a, b = _interpolate(by_speed[low], cnt), _interpolate(by_speed[high], cnt)
    return a if high == low else a + (b - a) * (speed - low) / (high - low)


@dataclass(frozen=True)
class Corner:
    cnt: int
    abb_cut: float  # mm: how close the RAPID move comes to the corner
    fanuc_cut: float  # mm: how close the FANUC one does with that CNT
    capped: bool  # CNT100 rounds less than the RAPID zone


def corner(profile: MotionProfile, motion: str, radius_mm: float, rapid_speed_mm_s: float, fanuc_speed: float) -> Corner:
    """The smallest CNT that rounds the corner as much as the RAPID zone does."""
    kind = "J" if motion == "J" else "L"
    target = abb_cut(profile, kind, radius_mm, rapid_speed_mm_s)
    for cnt in range(101):
        cut = fanuc_cut(profile, kind, cnt, fanuc_speed)
        if cut >= target:
            return Corner(cnt, target, cut, False)
    return Corner(100, target, fanuc_cut(profile, kind, 100, fanuc_speed), True)


# Measured 2026-09-25: IRB 6700-140/2.85 (RobotStudio, RobotWare 8.1) and M-20iD/25 (ROBOGUIDE), with
# tools/probe_motion.py; tests/fixtures/probes/motion/results/ holds the runs this is fitted from.
M20ID_25 = MotionProfile.from_dict({
    "name": "M-20iD/25",
    "joint_speed_ref_mm_s": 4500.0,
    "abb": {
        "L": {
            "200": [[1, 1.98], [5, 3.28], [10, 4.62], [20, 7.14], [30, 9.92], [50, 15.76], [100, 30.81], [150, 45.99], [200, 61.21]],
            "500": [[1, 2.54], [5, 3.73], [10, 5.35], [20, 8.55], [30, 11.49], [50, 17.35], [100, 31.85], [150, 46.72], [200, 61.77]],
            "1000": [[1, 2.54], [5, 3.75], [10, 5.36], [20, 8.56], [30, 11.53], [50, 17.71], [100, 32.97], [150, 48.22], [200, 63.34]],
        },
        "J": {
            "500": [[1, 2.5], [5, 3.65], [10, 5.13], [20, 8.0], [30, 10.7], [50, 15.99], [100, 29.14], [150, 42.69], [200, 56.33]],
            "1000": [[1, 2.52], [5, 3.71], [10, 5.14], [20, 8.08], [30, 10.8], [50, 16.41], [100, 30.39], [150, 44.29], [200, 57.85]],
        },
    },
    "fanuc": {
        "L": {
            "200": [[0, 0.0], [10, 0.18], [20, 0.5], [30, 0.91], [40, 1.39], [50, 1.94], [60, 2.57], [70, 3.21], [80, 3.88], [90, 4.37], [100, 4.75]],
            "500": [[0, 0.0], [10, 0.46], [20, 1.25], [30, 2.27], [40, 3.48], [50, 4.86], [60, 6.42], [70, 8.01], [80, 9.69], [90, 10.92], [100, 11.88]],
            "1000": [[0, 0.0], [10, 1.02], [20, 2.82], [30, 5.21], [40, 7.95], [50, 11.07], [60, 14.65], [70, 18.05], [80, 20.49], [90, 23.36], [100, 25.57]],
        },
        "J": {
            "9": [[0, 0.0], [10, 0.26], [20, 0.76], [30, 1.36], [40, 2.12], [50, 2.94], [60, 3.82], [70, 4.86], [80, 5.79], [90, 6.61], [100, 7.25]],
            "19": [[0, 0.0], [10, 0.56], [20, 1.6], [30, 2.87], [40, 4.47], [50, 6.21], [60, 8.07], [70, 10.27], [80, 12.22], [90, 13.96], [100, 15.31]],
        },
    },
})  # fmt: skip


# Measured 2026-09-25 the same way on an R-2000iC/190S: axes 2.25 times slower than the M-20iD/25's for
# the same TCP path, corners rounded 2 to 2.4 times more by the same CNT at the same speed.
R2000IC_190S = MotionProfile.from_dict({
    "name": "R-2000iC/190S",
    "joint_speed_ref_mm_s": 2000.0,
    "abb": {
        "L": {
            "200": [[1, 1.98], [5, 3.28], [10, 4.62], [20, 7.14], [30, 9.92], [50, 15.76], [100, 30.81], [150, 45.99], [200, 61.21]],
            "500": [[1, 2.54], [5, 3.73], [10, 5.35], [20, 8.55], [30, 11.49], [50, 17.35], [100, 31.85], [150, 46.72], [200, 61.77]],
            "1000": [[1, 2.54], [5, 3.75], [10, 5.36], [20, 8.56], [30, 11.53], [50, 17.71], [100, 32.97], [150, 48.22], [200, 63.34]],
        },
        "J": {
            "500": [[1, 2.5], [5, 3.65], [10, 5.13], [20, 8.0], [30, 10.7], [50, 15.99], [100, 29.14], [150, 42.69], [200, 56.33]],
            "1000": [[1, 2.52], [5, 3.71], [10, 5.14], [20, 8.08], [30, 10.8], [50, 16.41], [100, 30.39], [150, 44.29], [200, 57.85]],
        },
    },
    "fanuc": {
        "L": {
            "200": [[0, 0.0], [10, 0.35], [20, 0.96], [30, 1.77], [40, 2.71], [50, 3.79], [60, 4.75], [70, 5.56], [80, 6.47], [90, 7.33], [100, 8.1]],
            "500": [[0, 0.0], [10, 1.05], [20, 2.96], [30, 5.42], [40, 8.23], [50, 11.45], [60, 14.13], [70, 16.73], [80, 19.29], [90, 21.83], [100, 24.21]],
            "1000": [[0, 0.0], [10, 2.38], [20, 6.74], [30, 12.31], [40, 18.88], [50, 26.19], [60, 33.94], [70, 42.2], [80, 48.5], [90, 55.0], [100, 58.3]],
        },
        "J": {
            "9": [[0, 0.0], [10, 0.18], [20, 0.51], [30, 0.94], [40, 1.44], [50, 2.0], [60, 2.64], [70, 3.32], [80, 4.04], [90, 4.84], [100, 5.6]],
            "19": [[0, 0.0], [10, 0.39], [20, 1.09], [30, 1.99], [40, 3.03], [50, 4.22], [60, 5.56], [70, 7.01], [80, 8.52], [90, 10.22], [100, 11.8]],
        },
    },
})  # fmt: skip


# Measured 2026-09-26 on an R-1000iA/80F: J 100 % = 3,400 mm/s of TCP; corners as the M-20iD/25's up
# to 500 mm/s, about 1.3 times rounder at 1,000.
R1000IA_80F = MotionProfile.from_dict({
    "name": "R-1000iA/80F",
    "joint_speed_ref_mm_s": 3400.0,
    "abb": {
        "L": {
            "200": [[1, 1.98], [5, 3.28], [10, 4.62], [20, 7.14], [30, 9.92], [50, 15.76], [100, 30.81], [150, 45.99], [200, 61.21]],
            "500": [[1, 2.54], [5, 3.73], [10, 5.35], [20, 8.55], [30, 11.49], [50, 17.35], [100, 31.85], [150, 46.72], [200, 61.77]],
            "1000": [[1, 2.54], [5, 3.75], [10, 5.36], [20, 8.56], [30, 11.53], [50, 17.71], [100, 32.97], [150, 48.22], [200, 63.34]],
        },
        "J": {
            "500": [[1, 2.5], [5, 3.65], [10, 5.13], [20, 8.0], [30, 10.7], [50, 15.99], [100, 29.14], [150, 42.69], [200, 56.33]],
            "1000": [[1, 2.52], [5, 3.71], [10, 5.14], [20, 8.08], [30, 10.8], [50, 16.41], [100, 30.39], [150, 44.29], [200, 57.85]],
        },
    },
    "fanuc": {
        "L": {
            "200": [[0, 0.0], [10, 0.18], [20, 0.51], [30, 0.94], [40, 1.44], [50, 1.98], [60, 2.64], [70, 3.32], [80, 4.04], [90, 4.52], [100, 4.95]],
            "500": [[0, 0.0], [10, 0.46], [20, 1.28], [30, 2.34], [40, 3.6], [50, 4.95], [60, 6.6], [70, 8.3], [80, 10.11], [90, 11.28], [100, 12.37]],
            "1000": [[0, 0.0], [10, 1.51], [20, 4.37], [30, 7.89], [40, 12.12], [50, 16.58], [60, 20.07], [70, 23.64], [80, 26.91], [90, 30.31], [100, 33.56]],
        },
        "J": {
            "9": [[0, 0.0], [10, 0.33], [20, 0.91], [30, 1.65], [40, 2.55], [50, 3.54], [60, 4.64], [70, 5.89], [80, 7.15], [90, 8.14], [100, 8.97]],
            "19": [[0, 0.0], [10, 0.68], [20, 1.92], [30, 3.47], [40, 5.38], [50, 7.47], [60, 9.79], [70, 12.4], [80, 15.08], [90, 17.14], [100, 18.91]],
        },
    },
})  # fmt: skip


PROFILES = (M20ID_25, R2000IC_190S, R1000IA_80F)
# Robots sold under another name with the same arm.
TWINS = {"ARC MATE 120ID": "M-20iD"}


def family(model: str) -> str:
    """'R-2000iC/165F' -> 'R-2000IC': the arm series, before the payload and reach variant."""
    name = model.strip().upper().split("/")[0].strip()
    for twin, series in TWINS.items():
        if name.startswith(twin):
            return series.upper()
    return name


def profile_for(model: str | None) -> tuple[MotionProfile, str]:
    """The measured profile closest to the target robot, and how it was chosen, for the report."""
    if model:
        for profile in PROFILES:
            if profile.name.upper() == model.strip().upper():
                return profile, f"measured on this model, the {profile.name}"
        for profile in PROFILES:
            if family(profile.name) == family(model):
                return profile, f"measured on the {profile.name}, of the same series as the {model}"
    return M20ID_25, ""


# Statements a zoned move blends past: the next move after them is the one the corner leads into.
_BLENDED_PAST = frozenset({"SET", "RESET", "SETDO", "SETGO", "SETAO", "PULSEDO", "INVERTDO"})


def next_move(stmts: tuple[n.Stmt, ...], i: int) -> n.Move | None:
    """The move the corner of stmts[i] leads into, past what the robot does not stop for; None when stmts[i]
    is not a move or no move follows it in its block."""
    if not isinstance(stmts[i], n.Move):
        return None
    following = next((s for s in stmts[i + 1 :] if not _passed_through(s)), None)
    return following if isinstance(following, n.Move) else None


def _passed_through(stmt: n.Stmt) -> bool:
    return isinstance(stmt, n.Comment) or (isinstance(stmt, n.ProcCall) and stmt.name.upper() in _BLENDED_PAST)


__all__ = [
    "M20ID_25", "PROFILES", "R1000IA_80F", "R2000IC_190S", "Corner", "MotionProfile", "abb_cut", "corner", "family", "fanuc_cut",
    "next_move", "profile_for",
]  # fmt: skip
