# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""SETUP_FRAMES.LS: the frames of a conversion, set on the robot by a program rather than typed in.

The PR[i]=P[j] / UTOOL[n]=PR[i] route it uses was run on ROBOGUIDE by the pose probe. What is
checked here is the part that is CrossArm's own: which frames it writes, with which values, and
the ones it must never touch.
"""

import math
import sys
from datetime import datetime
from pathlib import Path

import pytest
from helpers import FIXTURES
from test_translate import HOME, TOOL, WOBJ, run

from crossarm.convert import ConversionConfig
from crossarm.convert.setup import START_MESSAGE, build_setup, scratch_register
from crossarm.fanuc.ls_parser import parse_ls
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import CartesianPosition
from crossarm.geometry import quat_to_matrix, wpr_to_matrix
from crossarm.pipeline import _setup_name

MOVES = "MoveL pHome,v500,fine,tGrip\\WObj:=wFix;"


def config(**kwargs) -> ConversionConfig:
    return ConversionConfig(timestamp=datetime(2026, 1, 1), **kwargs)


def texts(program) -> list[str]:
    return [line.text for line in program.lines]


def test_every_frame_is_set_with_the_value_in_the_report():
    cfg = config()
    result = run(MOVES, HOME + TOOL + WOBJ, cfg)
    setup = build_setup(result, cfg, "SETUP_FRAMES")
    program = setup.program
    assert program is not None and program.name == "SETUP_FRAMES"
    # A message and a pause first: it overwrites frames the robot may be using.
    assert texts(program)[3:5] == [f"MESSAGE[{START_MESSAGE}]", "PAUSE"]
    assert texts(program)[5:] == [
        "!UTOOL[1] tGrip", "PR[100]=P[1]", "UTOOL[1]=PR[100]",
        "!UFRAME[1] wFix", "PR[100]=P[2]", "UFRAME[1]=PR[100]",
    ]  # fmt: skip
    tool, frame = (p.value for p in program.positions)
    assert tool == CartesianPosition(0, 0, 185.5, 0, 0, 0)
    (x, y, z), (w, p, r) = result.uframes[0].frame.pose.pos, result.uframes[0].frame.pose.wpr()
    assert frame == CartesianPosition(x, y, z, w, p, r)  # uframe x oframe, as in the report
    assert [(kind, f.number) for kind, f in setup.written] == [("UTOOL", 1), ("UFRAME", 1)]


def test_the_program_is_valid_ls_text():
    cfg = config()
    text = write_ls(build_setup(run(MOVES, HOME + TOOL + WOBJ, cfg), cfg, "SETUP_FRAMES").program)
    assert write_ls(parse_ls(text)) == text


def test_frames_it_must_not_write_are_left_out_and_said():
    """Unknown, unusable, beyond the controller, or already the robot's own: never overwritten."""
    held = 'PERS wobjdata wHeld:=[TRUE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];'
    var_tool = "VAR tooldata tVar:=[TRUE,[[0,0,100],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];"
    body = "tVar.tframe.trans.z:=120;\nMoveL pHome,v500,fine,tVar;\n" + MOVES + "\nMoveL pHome,v500,fine,tool0;\nMoveL pHome,v500,fine,tool0\\WObj:=wHeld;"
    cfg = config(utools={"TGRIP": 12}, uframes={"WOBJ0": 0, "WFIX": 4}, reserved={"UFRAME": {4: ("PICK",)}})
    setup = build_setup(run(body, HOME + TOOL + WOBJ + held + var_tool, cfg), cfg, "SETUP_FRAMES")
    reasons = {f.rapid_name: why for _, f, why in setup.skipped}
    assert "assigned at run time" in reasons["tVar"]
    assert reasons["tGrip"] == "number above the 10 the controller holds"
    assert reasons["wFix"] == "already used on the robot by PICK: not overwritten"
    assert "robot-held" in reasons["wHeld"]
    assert [f.rapid_name for _, f in setup.written] == ["tool0"]
    assert "!UFRAME[4] wFix: not set" in texts(setup.program)


def test_nothing_to_set_means_no_program():
    cfg = config()
    setup = build_setup(run("Stop;"), cfg, "SETUP_FRAMES")
    assert setup.program is None and not setup.written


def test_the_scratch_register_is_one_the_robot_does_not_use():
    assert scratch_register(config()) == (100, False)  # robot unknown: said in the report
    assert scratch_register(config(reserved={"PR": {}})) == (100, True)
    assert scratch_register(config(reserved={"PR": {100: ("A",), 99: ("B",)}})) == (98, True)


def test_its_name_fits_the_controller_and_replaces_nothing():
    assert _setup_name(config(), set()) == "SETUP_FRAMES"
    assert _setup_name(config(), {"SETUP_FRAMES"}) == "SETUP_FRAMES_2"
    assert _setup_name(config(program_name_max_length=8), set()) == "SETFRAME"
    assert _setup_name(config(program_name_max_length=8), {"SETFRAME"}) == "SETFRA_2"


# ---------------------------------------------------------------------------
# On the controller: tools/make_setup_probe.py, run on ROBOGUIDE
# ---------------------------------------------------------------------------

PROBE = FIXTURES / "probes" / "setup"


def _probe():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import make_pose_probe
    import make_setup_probe

    return make_setup_probe, make_pose_probe


def test_the_setup_probe_files_are_those_the_generator_writes():
    probe, _ = _probe()
    frames = probe.setup()
    assert (PROBE / "SETUP_FRAMES.LS").read_bytes() == write_ls(frames.program).encode("ascii")
    assert (PROBE / "FRAMECHK.LS").read_bytes() == write_ls(probe.check_program(frames)).encode("ascii")


@pytest.mark.skipif(not (PROBE / "results").exists(), reason="setup probe not run on ROBOGUIDE yet")
def test_the_robot_is_left_with_the_frames_of_the_report():
    probe, pose = _probe()
    registers = pose.read_posreg((PROBE / "results" / "posreg_roboguide.va").read_text(encoding="utf-8"))
    frames = probe.setup()
    assert len(frames.written) == 5
    for kind, frame in frames.written:
        base = probe.TOOL_PR if kind == "UTOOL" else probe.FRAME_PR
        x, y, z, w, p, r = registers[base + frame.number]
        expected = frame.frame.pose
        assert math.dist((x, y, z), expected.pos) < 0.01, f"{kind}[{frame.number}]"
        turn = pose.angle_between(quat_to_matrix(expected.rot), wpr_to_matrix(w, p, r))
        assert turn < 0.01, f"{kind}[{frame.number}]"


def test_frames_above_the_limit_are_stored_in_their_registers():
    tools = "".join(f"PERS tooldata t{i}:=[TRUE,[[0,0,{10 * i}],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];\n"
                    for i in range(4))  # fmt: skip
    cfg = config(limits={"UTOOL": 3, "UFRAME": 9, "PR": 100})
    result = run("".join(f"MoveL pHome,v500,fine,t{i};\n" for i in range(4)), HOME + tools, cfg)
    setup = build_setup(result, cfg, "SETUP_FRAMES")
    lines = texts(setup.program)
    # t0, t1 set directly; t2, t3 (past UTOOL 3, which is kept for them) stored in PR[99] and PR[98].
    assert "UTOOL[1]=PR[100]" in lines and "UTOOL[2]=PR[100]" in lines
    assert lines[-4:] == ["!t2: PR[99], UTOOL[3] when used", "PR[99]=P[3]", "!t3: PR[98], UTOOL[3] when used",
                          "PR[98]=P[4]"]  # fmt: skip
    assert setup.program.positions[3].value.z == pytest.approx(30)
