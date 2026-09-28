# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Does a converted program put the robot flange where the RAPID program does?

tools/make_pose_probe.py converts a module of test moves (rotated tools and work objects,
Offs, RelTool) with CrossArm and wraps it so that each controller works out the flange pose
of every move in the world frame. Two levels of evidence:

  * here, without a controller: the numbers written in POSEPROBE.LS (W,P,R at 3 decimals,
    frames loaded through PR[]) describe the same flange as the RAPID data, read with
    quaternions. Catches a composition or rounding error in CrossArm itself.
  * with tests/fixtures/probes/pose/results/ (RobotStudio's poseprobe.txt, ROBOGUIDE's
    posreg.va): both controllers agree. Catches a wrong reading of either controller's
    conventions — the one thing no test written from the manuals alone can rule out.
"""

import re
import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_parser import read_ls
from crossarm.fanuc.tp import CartesianPosition
from crossarm.geometry import Pose, matrix_to_quat, quat_to_matrix, wpr_to_matrix

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_pose_probe import (
    FLANGE_PR,
    HOME_JOINTS,
    MOVES,
    PIN_PROGRAM,
    TARGETS,
    ZERO_TOOL,
    abb_module,
    angle_between,
    compare,
    expected_flanges,
    fanuc_program,
    inverse,
    read_posreg,
    read_robotstudio,
)

PROBE = FIXTURES / "probes" / "pose"
RESULTS = PROBE / "results"
PIN = FIXTURES / "probes" / "pin"
HALF_TURN_Z = Pose((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))


def test_the_probe_files_are_those_the_generator_writes():
    """Regenerated from the current CrossArm: a change in the conversion shows up here first."""
    module = abb_module()
    assert (PROBE / "PoseProbe.mod").read_bytes() == module.encode("ascii")
    assert (PROBE / "POSEPROBE.LS").read_bytes() == fanuc_program(module).encode("ascii")
    pin = abb_module(pin=True)
    assert (PIN / "PinProbe.mod").read_bytes() == pin.encode("ascii")
    assert (PIN / f"{PIN_PROGRAM}.LS").read_bytes() == fanuc_program(pin, "+x").encode("ascii")


def _pose(value: CartesianPosition) -> Pose:
    return Pose((value.x, value.y, value.z), matrix_to_quat(wpr_to_matrix(value.w, value.p, value.r)))


def fanuc_flanges(path: Path = PROBE / "POSEPROBE.LS") -> list[Pose]:
    """The flange of every move as the written .LS describes it, read with FANUC's W,P,R convention:
    UFRAME[uf] * P[n] * inverse(UTOOL[ut])."""
    program = read_ls(path)
    points = {p.number: p for p in program.positions}
    registers: dict[int, int] = {}
    frames: dict[tuple[str, int], Pose] = {("UFRAME", 0): Pose((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))}
    uf = ut = 0
    out = []
    for line in program.lines:
        text = getattr(line, "text", "")
        if m := re.fullmatch(r"PR\[(\d+)\]=P\[(\d+)\]", text):
            registers[int(m[1])] = int(m[2])
        elif m := re.fullmatch(r"(UTOOL|UFRAME)\[(\d+)\]=PR\[(\d+)\]", text):
            frames[(m[1], int(m[2]))] = _pose(points[registers[int(m[3])]].value)  # type: ignore[arg-type]
        elif m := re.fullmatch(r"UFRAME_NUM=(\d+)", text):
            uf = int(m[1])
        elif m := re.fullmatch(r"UTOOL_NUM=(\d+)", text):
            ut = int(m[1])
        elif not text:  # a motion
            point = points[int(line.target[2:-1])]  # type: ignore[union-attr]
            assert (point.uf, point.ut) == (uf, ut), "the point must be taught in the active frames"
            if not isinstance(point.value, CartesianPosition):
                assert point.value.joints == HOME_JOINTS  # the known start, not a probed move
                continue
            tcp = _pose(point.value)  # type: ignore[arg-type]
            out.append(frames[("UFRAME", uf)].compose(tcp).compose(inverse(frames[("UTOOL", ut)])))
    assert frames[("UTOOL", ZERO_TOOL)].pos == (0.0, 0.0, 0.0)
    return out


def test_the_converted_program_describes_the_same_flange_as_the_rapid_one():
    written, expected = fanuc_flanges(), expected_flanges()
    assert len(written) == len(expected) == len(MOVES)
    for i, (w, e) in enumerate(zip(written, expected, strict=True), start=1):
        # W,P,R and positions are written with 3 decimals: a few micrometres over a 250 mm tool.
        assert max(abs(a - b) for a, b in zip(w.pos, e.pos, strict=True)) < 0.01, f"move {i}"
        assert angle_between(quat_to_matrix(w.rot), quat_to_matrix(e.rot)) < 0.002, f"move {i}"


def test_with_the_pin_on_plus_x_the_faceplate_is_the_abb_flange_turned():
    """Tools turned half a turn about z ("tool_pin": "+x"): the TCP lands where RAPID puts it, the
    faceplate half a turn about z from the ABB flange. And that is where the pose probe puts it."""
    written, expected = fanuc_flanges(PIN / f"{PIN_PROGRAM}.LS"), expected_flanges(pin=True)
    for i, (w, e, original) in enumerate(zip(written, expected, expected_flanges(), strict=True), start=1):
        turned = e.compose(HALF_TURN_Z)
        assert max(abs(a - b) for a, b in zip(w.pos, turned.pos, strict=True)) < 0.01, f"move {i}"
        assert angle_between(quat_to_matrix(w.rot), quat_to_matrix(turned.rot)) < 0.002, f"move {i}"
        expr, tool, _ = MOVES[i - 1]
        # Where the ABB target was worked out for that tool, and not turned about its TCP (RelTool).
        if "RelTool" not in expr and TARGETS[re.findall(r"pProbe\d", expr)[0]][1] == tool:
            assert angle_between(quat_to_matrix(turned.rot), quat_to_matrix(original.rot)) < 0.001, f"move {i}"


def test_the_moves_are_all_different():
    """16 moves that each probe something: no two land the flange on the same pose."""
    flanges = expected_flanges()
    for i, a in enumerate(flanges):
        for b in flanges[i + 1 :]:
            assert max(abs(x - y) for x, y in zip(a.pos, b.pos, strict=True)) > 1


def test_results_are_read_loosely():
    abb = read_robotstudio("1 1100.000 0.000 700.000 0.000000 0.000000 1.000000 0.000000\r\nnoise\r\n")
    assert abb[1].pos == (1100.0, 0.0, 700.0)
    posreg = (
        "[1,51] = ''\r\n  Group: 1   Config: N U T, 0, 0, 0\r\n"
        "  X:  1100.000   Y:     0.000   Z:   700.000\r\n  W:  -180.000   P:     0.000   R:   180.000\r\n"
        "[1,71] = ''\r\n  J1 = 0.000 deg  J2 = 10.000 deg\r\n"
    )
    assert read_posreg(posreg) == {51: (1100.0, 0.0, 700.0, -180.0, 0.0, 180.0)}
    (row,) = compare(abb, read_posreg(posreg))
    assert row[0] == 1 and row[1] < 1e-9 and row[2] < 1e-6  # W=-180,R=180 is the same flange as q=[0,0,1,0]


@pytest.mark.skipif(not RESULTS.exists(), reason="pose probe not run on the controllers yet")
def test_both_controllers_put_the_flange_in_the_same_place():
    abb = read_robotstudio((RESULTS / "poseprobe_robotstudio.txt").read_text(encoding="utf-8", errors="replace"))
    fanuc = read_posreg((RESULTS / "posreg_roboguide.va").read_text(encoding="utf-8", errors="replace"))
    assert len(abb) == len(MOVES), "RobotStudio must have written every move"
    rows = compare(abb, fanuc)
    assert len(rows) == len(MOVES), f"moves missing on ROBOGUIDE: PR[{FLANGE_PR + 1}..] not all set"
    bad = [(i, round(gap, 3), round(turn, 3)) for i, gap, turn in rows if gap > 0.05 or turn > 0.01]
    assert not bad, f"moves where the flange differs (move, mm, deg): {bad}"


@pytest.mark.skipif(not (PIN / "results").exists(), reason="pin probe not run on the controllers yet")
def test_with_the_pin_on_plus_x_roboguide_puts_the_flange_half_a_turn_from_the_abb_one():
    abb = read_robotstudio((PIN / "results" / "pinprobe_robotstudio.txt").read_text(encoding="utf-8", errors="replace"))
    assert len(abb) == len(MOVES), "RobotStudio must have written every move"
    for i, flange in enumerate(expected_flanges(pin=True), start=1):  # RobotStudio agrees with CrossArm's arithmetic
        assert max(abs(a - b) for a, b in zip(abb[i].pos, flange.pos, strict=True)) < 0.01, f"move {i}"
    fanuc = read_posreg((PIN / "results" / "posreg_roboguide.va").read_text(encoding="utf-8", errors="replace"))
    rows = compare(abb, fanuc, tool_pin="+x")
    assert len(rows) == len(MOVES), f"moves missing on ROBOGUIDE: PR[{FLANGE_PR + 1}..] not all set"
    bad = [(i, round(gap, 3), round(turn, 3)) for i, gap, turn in rows if gap > 0.05 or turn > 0.01]
    assert not bad, f"moves where the flange differs (move, mm, deg): {bad}"
