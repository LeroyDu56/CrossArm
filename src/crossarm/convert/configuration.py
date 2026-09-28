# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""ABB confdata -> FANUC CONFIG string.

Both conventions were MEASURED, not assumed: the same 16 joint sets were
evaluated by RobotStudio (CalcRobT, IRB 6700) and ROBOGUIDE (joint -> cartesian
conversion), see tools/make_config_probes.py and tests/fixtures/probes/results/.
Fitting the measured orientations gives, for axes at the same physical posture:

    J1_fanuc = J1_abb
    J4_fanuc = -J4_abb          (axis direction reversed)
    J5_fanuc = -J5_abb          (axis direction reversed)
    J6_fanuc = 180 - J6_abb     (reversed, and the flange frames differ by 180 deg
                                 about z when the ABB tframe is reused as UTOOL)

ABB confdata [cf1, cf4, cf6, cfx]: cf1/cf4/cf6 are the quadrants of axes 1, 4, 6
(quadrant q = angle in [q*90, q*90 + 90)); cfx for a 6-axis arm is
    bit 0: axis 5 negative          bit 1: wrist centre behind the lower arm
    bit 2: wrist centre behind axis 1
FANUC CONFIG 'F/N U/D T/B, t1, t4, t6':
    F when J5 > 0; D elbow down; B wrist behind axis 1; turn numbers of J1, J4, J6
    (turn t = angle in (-180 + 360t, 180 + 360t]).

Quadrant boundaries (multiples of 90) fall on turn boundaries (odd multiples
of 180), so each ABB quadrant maps to exactly one FANUC turn number, but for one
angle: FANUC turn 0 is (-180, 180), open at both ends (measured on ROBOGUIDE: at
J6 = 180 exactly the controller says turn 1, and refuses a point written with 0).
ABB quadrant 0 is [0, 90), closed at 0, and J6_abb = 0 exactly - a tool pointing
straight down in front of the robot, the most common orientation there is - is
J6_fanuc = 180 exactly. confdata cannot tell it from J6 slightly above 0, so the
pose does (j6_on_turn_boundary), and the turn is then 1.

How the tool sits on the flange, from the makers' manuals: the IRB 6700 guide pin
hole points up at the calibration position, which is -x of tool0; the M-20iD/25
faceplate has two pin holes, on +x and -x of its frame, and ISO 9409-1 puts the
pin of a standard flange on +x. The flanges differ, so an adapter plate decides.
With the pin in the FANUC -x hole (TOOL_PIN_DEFAULT), the pin stays where it was
for the same TCP pose: the ABB tframe is the UTOOL as it is, J6 = 180 - J6_abb.
With it in the +x hole (ISO), the tool is half a turn about z from the flange frame:
the UTOOL is the tframe turned, J6 = -J6_abb.
"""

import math
from dataclasses import replace

from crossarm.convert.values import Frame
from crossarm.geometry import Pose, quat_to_matrix

TOOL_PIN_DEFAULT = "-x"
TOOL_PINS = ("-x", "+x")
_HALF_TURN_Z = Pose((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))


class UnsupportedConfdata(ValueError):
    """confdata outside the 6-axis serial-arm convention (e.g. 7-axis or parallel robots)."""


def fanuc_config(conf: tuple[int, int, int, int], tool_pin: str = TOOL_PIN_DEFAULT, j6_boundary: bool = False) -> str:
    """CONFIG for that confdata. `j6_boundary`: the FANUC J6 is exactly 180 (j6_on_turn_boundary)."""
    cf1, cf4, cf6, cfx = conf
    if not 0 <= cfx <= 7:
        raise UnsupportedConfdata(f"cfx={cfx} is not a 6-axis arm configuration (expected 0-7)")
    flip = "F" if cfx & 1 else "N"  # ABB axis 5 negative == FANUC J5 positive
    elbow = "D" if cfx & 2 else "U"
    side = "B" if cfx & 4 else "T"
    # FANUC angle ranges per ABB quadrant: J1 same, J4 = -angle, J6 = 180 - angle (-angle, tool pin on +x).
    turn_j1 = (cf1 + 2) // 4
    turn_j4 = (1 - cf4) // 4
    turn_j6 = (3 - cf6) // 4 if tool_pin == TOOL_PIN_DEFAULT else (1 - cf6) // 4
    if j6_boundary and turn_j6 == 0:  # exactly +180, which FANUC counts in turn 1
        turn_j6 = 1
    return f"{flip} {elbow} {side}, {turn_j1}, {turn_j4}, {turn_j6}"


def j6_on_turn_boundary(faceplate: Pose, conf: tuple[int, int, int, int], tolerance: float = 1e-5) -> bool:
    """Whether the FANUC J6 is exactly +/-180 for that faceplate pose (world frame, as written).

    Works for any 6-axis arm with axis 1 in the plane of the arm: J1 points the arm at the wrist, and
    with J4 at 0 (or 180) the tool axis stays in the arm's vertical plane, while J5 turns about the
    horizontal axis across it. J6 is then 180 exactly when the faceplate y axis lies along the J5 axis,
    one way (J4 near 0) or the other (J4 near 180), whatever the arm's lengths.

    The controller has a tolerance of its own, measured on ROBOGUIDE: within 0.0004 deg of 180 it
    wants turn 1 and refuses 0, from 0.0007 deg on it takes 0; the tolerance here, 1e-5 rad
    (0.00057 deg), sits between. With J4 off the arm's plane, J6 depends on the arm's lengths and is
    not checked: a target that puts J6 exactly on 180 there is not found.
    """
    x, y, _ = faceplate.pos
    if math.hypot(x, y) < 1e-6:  # above axis 1: J1 is not set by the position
        return False
    phi = math.atan2(y, x) + (math.pi if conf[3] & 4 else 0.0)  # behind axis 1: the arm points away
    across = (-math.sin(phi), math.cos(phi), 0.0)  # the J5 axis direction with J4 at 0
    m = quat_to_matrix(faceplate.rot)
    y_axis, z_axis = (m[0][1], m[1][1], m[2][1]), (m[0][2], m[1][2], m[2][2])
    if abs(sum(a * b for a, b in zip(z_axis, across, strict=True))) > tolerance:
        return False  # the tool axis leaves the arm's plane: J4 is neither 0 nor 180
    sign = 1.0 if conf[1] % 4 in (0, 3) else -1.0  # J4 near 0 (quadrants 0, -1) or near 180
    return all(abs(a - sign * b) <= tolerance for a, b in zip(y_axis, across, strict=True))


def fanuc_joints(abb_joints: tuple[float, ...], tool_pin: str = TOOL_PIN_DEFAULT) -> tuple[float, ...]:
    """ABB robax J1..J6 -> FANUC J1..J6 for the same arm and wrist posture.

    Measured conventions: J1 and J2 turn the same way; FANUC J3 is absolute (forearm
    angle to the horizontal, = -(J2 + J3) ABB); J4, J5, J6 are reversed and the flange
    frames differ by 180 deg about z (the tool too, with its pin on +x: J6 = -J6_abb).
    The TCP still lands elsewhere on another robot model (different link lengths): the
    posture is preserved, not the position.
    """
    j1, j2, j3, j4, j5, j6 = abb_joints[:6]
    return (j1, j2, -(j2 + j3), -j4, -j5, 180 - j6 if tool_pin == TOOL_PIN_DEFAULT else -j6)


def tool_on_flange(frame: Frame, tool_pin: str = TOOL_PIN_DEFAULT) -> Frame:
    """The ABB tool as the FANUC UTOOL, for its pin in that hole of the faceplate.

    In the +x hole the tool is half a turn about z from where the flange frame had it:
    x and y of the TCP and of the centre of gravity change sign, z and the mass do not,
    and the inertia about x, y, z is the same.
    """
    if tool_pin == TOOL_PIN_DEFAULT:
        return frame
    load = frame.load
    if load is not None:
        (cx, cy, cz) = load.cog
        # Inertia axes turned too. Axes along the flange's stay so: a half turn about z leaves
        # a diagonal inertia as it is.
        aom = load.aom
        if tuple(aom) != (1, 0, 0, 0):
            aom = _HALF_TURN_Z.compose(Pose((0.0, 0.0, 0.0), aom)).compose(_HALF_TURN_Z).rot
        load = replace(load, cog=(-cx, -cy, cz), aom=aom)
    return replace(frame, pose=_HALF_TURN_Z.compose(frame.pose), load=load)
