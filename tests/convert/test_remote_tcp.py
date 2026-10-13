# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A stationary tool (robhold FALSE) and a work object the robot holds (robhold TRUE): FANUC Remote TCP (J624).

The stationary tool is a UFRAME (its tframe, in the world), the robot-held work object a UTOOL (uframe x oframe, on
the faceplate), each point the inverse pose, L and C with RTCP, J without (ASBN-092). The faceplate the controller
works out from what is written (UFRAME x P x inverse(UTOOL)) is checked against where RAPID puts it (tframe x
inverse(p) x inverse(uframe x oframe)), with quaternions written here, independently of CrossArm (rtcp probe:
both measured, ROBOGUIDE and RobotStudio)."""

import json
import math
from datetime import datetime

import pytest
from helpers import parse_module

from crossarm.convert import ConversionConfig, build_mapping, convert
from crossarm.convert.blockers import Blocker
from crossarm.convert.setup import build_setup
from crossarm.fanuc.tp import Motion

STAMP = datetime(2026, 1, 1)
NOZZLE = ((1250.0, -80.0, 640.0), (0.9238795, 0.0, 0.0, 0.3826834))  # 45 deg about z, in the world
PANEL = ((15.0, -25.0, 180.0), (0.9961947, 0.0, 0.0, 0.0871557))  # uframe on the faceplate, 10 deg about z
PANEL_O = ((30.0, 5.0, 2.0), (0.9848078, 0.1736482, 0.0, 0.0))  # oframe, 20 deg about x
POINTS = {
    "pA": ((40.0, 30.0, 0.0), (0.0, 0.258819, 0.9659258, 0.0)),
    "pB": ((-60.0, -20.0, 5.0), (0.0, 0.2, 0.97, 0.1)),
    "pC": ((-30.0, 40.0, 0.0), (0.0, 0.0, 1.0, 0.0)),
    "pD": ((-50.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0)),
}


def _pose(p) -> str:
    return f"[[{','.join(f'{v:g}' for v in p[0])}],[{','.join(f'{v:g}' for v in p[1])}]]"


def _target(p) -> str:
    return f"[{_pose(p)[1:-1]},[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]]"


DATA = "\n".join([
    f"PERS tooldata tNozzle:=[FALSE,{_pose(NOZZLE)},[1,[0,0,1],[1,0,0,0],0,0,0]];",
    "PERS tooldata tGrip:=[TRUE,[[0,0,120],[1,0,0,0]],[4,[0,0,60],[1,0,0,0],0,0,0]];",
    f'PERS wobjdata wPanel:=[TRUE,TRUE,"",{_pose(PANEL)},{_pose(PANEL_O)}];',
    'PERS wobjdata wSlide:=[TRUE,FALSE,"STN1",[[0,0,100],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];',
    'PERS wobjdata wTable:=[FALSE,TRUE,"",[[900,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];',
    *(f"CONST robtarget {name}:={_target(p)};" for name, p in POINTS.items()),
    "CONST robtarget pHome:=[[1000,0,1200],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];",
    "VAR robtarget pSeen;",
    ("CONST robtarget pRow{2}:=[[[1,0,0],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],"
     "[[2,0,0],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]]];"),
    "VAR num nAt:=1;",
])  # fmt: skip
BEAD = """MoveJ pHome,v500,fine,tGrip;
MoveJ pA,v500,z10,tNozzle\\WObj:=wPanel;
MoveL pB,v100,z5,tNozzle\\WObj:=wPanel;
MoveC pC,pD,v100,fine,tNozzle\\WObj:=wPanel;
MoveL Offs(pA,0,0,10),v100,fine,tNozzle\\WObj:=wPanel;
MoveJ pHome,v500,fine,tGrip;"""


def run(body: str, procs: str = "", config: ConversionConfig | None = None):
    source = f"MODULE M\n{DATA}\nPROC main()\n{body}\nENDPROC\n{procs}\nENDMODULE\n"
    return convert([parse_module(source)], config or ConversionConfig(timestamp=STAMP),
                   sources={"M": source})  # fmt: skip


def program(result, name: str = "MAIN"):
    return next(info.program for info in result.programs if info.program.name == name)


def lines(result, name: str = "MAIN") -> list[str]:
    out = []
    for line in program(result, name).lines:
        if isinstance(line, Motion):
            via = f" {line.via}" if line.via else ""
            out.append(f"{line.kind}{via} {line.target} {line.speed} {line.termination} {line.options}".rstrip())
        elif not line.text.startswith("!"):
            out.append(line.text)
    return out


def todos(result) -> list[tuple[str, str]]:
    return [(note.category, note.message) for note in result.notes if note.kind == "TODO"]


# -- quaternions (w, x, y, z), written here --------------------------------------------------------------------------


def q_mul(a, b):
    return (a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3], a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
            a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1], a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0])  # fmt: skip


def q_unit(q):
    s = math.sqrt(sum(c * c for c in q))
    return tuple(c / s for c in q)


def turn(q, v):
    w = q_mul(q_mul(q, (0.0, *v)), (q[0], -q[1], -q[2], -q[3]))
    return w[1:]


def mult(a, b):
    return tuple(x + y for x, y in zip(a[0], turn(a[1], b[0]), strict=True)), q_unit(q_mul(a[1], b[1]))


def inv(a):
    conj = (a[1][0], -a[1][1], -a[1][2], -a[1][3])
    return tuple(-c for c in turn(conj, a[0])), conj


def about(axis: int, degrees: float):
    half = math.radians(degrees) / 2
    return (math.cos(half), *(math.sin(half) if i == axis else 0.0 for i in range(3)))


def from_xyzwpr(x, y, z, w, p, r):
    """FANUC: R = Rz(r) Ry(p) Rx(w)."""
    return (x, y, z), q_unit(q_mul(q_mul(about(2, r), about(1, p)), about(0, w)))


def unit(p):
    return p[0], q_unit(p[1])


def gap(a, b) -> tuple[float, float]:
    dot = abs(sum(x * y for x, y in zip(a[1], b[1], strict=True)))
    return math.dist(a[0], b[0]), math.degrees(2 * math.acos(min(1.0, dot)))


def written(frames, number):
    f = next(f for f in frames if f.number == number).frame.pose
    return from_xyzwpr(*(round(v, 3) for v in (*f.pos, *f.wpr())))


# -- the tests ---------------------------------------------------------------------------------------------------------


def test_the_moves_select_the_tool_as_uframe_the_work_object_as_utool_with_rtcp_on_l_and_c():
    result = run(BEAD)
    assert lines(result) == [
        "UFRAME_NUM=0", "UTOOL_NUM=1", "J P[1] 11% FINE",
        "UFRAME_NUM=1", "UTOOL_NUM=2", "J P[2] 11% CNT64",  # J refuses RTCP (ASBN-092): the same point without it
        "L P[3] 100mm/sec CNT100 RTCP", "C P[4] P[5] 100mm/sec FINE RTCP", "L P[6] 100mm/sec FINE RTCP",
        "UFRAME_NUM=0", "UTOOL_NUM=1", "J P[1] 11% FINE",
    ]  # fmt: skip
    assert [(f.number, f.rapid_name) for f in result.uframes] == [(0, "wobj0"), (1, "tNozzle")]
    assert [(f.number, f.rapid_name) for f in result.utools] == [(1, "tGrip"), (2, "wPanel")]
    assert result.remote_tcp == [("tNozzle", "wPanel", 1, 2)]
    said = [n.message for n in result.notes if n.category == Blocker.STATIONARY]
    assert len(said) == 1 and "UFRAME[1] = tNozzle" in said[0] and "UTOOL[2] = wPanel" in said[0] and "J624" in said[0]
    assert not todos(result)


def test_the_faceplate_is_where_rapid_puts_it():
    """UFRAME x P x inverse(UTOOL), from the values as written, = tframe x inverse(p) x inverse(uframe x oframe)."""
    result = run(BEAD)
    gun, part = written(result.uframes, 1), written(result.utools, 2)
    held = mult(unit(PANEL), unit(PANEL_O))
    shown = {pos.number: pos for pos in program(result).positions}
    targets = {2: POINTS["pA"], 3: POINTS["pB"], 4: POINTS["pC"], 5: POINTS["pD"],
               6: ((40.0, 30.0, 10.0), POINTS["pA"][1])}  # fmt: skip
    for number, target in targets.items():
        v = shown[number].value
        assert (shown[number].uf, shown[number].ut) == (1, 2)
        fanuc = mult(mult(gun, from_xyzwpr(v.x, v.y, v.z, v.w, v.p, v.r)), inv(part))
        rapid = mult(mult(unit(NOZZLE), inv(unit(target))), inv(held))
        mm, deg = gap(fanuc, rapid)
        assert mm < 0.01 and deg < 0.01, (number, mm, deg)


def test_setup_frames_sets_the_tool_in_the_world_and_the_work_object_on_the_faceplate():
    cfg = ConversionConfig(timestamp=STAMP)
    setup = build_setup(run(BEAD, config=cfg), cfg, "SETUP_FRAMES")
    assert [(kind, f.rapid_name) for kind, f in setup.written] == [("UTOOL", "tGrip"), ("UTOOL", "wPanel"),
                                                                   ("UFRAME", "tNozzle")]  # fmt: skip
    result = run(BEAD)
    assert gap(written(result.uframes, 1), unit(NOZZLE)) < (0.001, 0.001)
    assert gap(written(result.utools, 2), mult(unit(PANEL), unit(PANEL_O))) < (0.001, 0.001)


def test_the_tool_pin_turns_the_work_object_on_the_faceplate_as_it_turns_a_tool():
    result = run(BEAD, config=ConversionConfig(timestamp=STAMP, tool_pin="+x"))
    half = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    assert gap(written(result.utools, 2), mult(half, mult(unit(PANEL), unit(PANEL_O)))) < (0.001, 0.001)


def test_a_mapping_file_given_back_gives_the_same_numbers(tmp_path):
    first = run(BEAD)
    mapping = json.loads(build_mapping(first, ConversionConfig()))
    assert mapping["uframes"] == {"wobj0": 0, "tNozzle": 1} and mapping["utools"] == {"tGrip": 1, "wPanel": 2}
    mapping["uframes"]["tNozzle"], mapping["utools"]["wPanel"] = 6, 8
    path = tmp_path / "map.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    pinned = run(BEAD, config=ConversionConfig.from_mapping_file(path))
    assert "UFRAME_NUM=6" in lines(pinned) and "UTOOL_NUM=8" in lines(pinned)
    assert pinned.remote_tcp == [("tNozzle", "wPanel", 6, 8)]
    again = json.loads(build_mapping(pinned, ConversionConfig()))
    assert again["uframes"] == mapping["uframes"] and again["utools"] == mapping["utools"]


def test_a_point_passed_to_a_routine_is_passed_inverted():
    procs = "PROC Dab(robtarget p)\nMoveL p,v50,fine,tNozzle\\WObj:=wPanel;\nENDPROC"
    result = run("Dab pB;\nDab Offs(pA,0,0,10);", procs)
    assert not todos(result)
    assert lines(result, "DAB") == ["UFRAME_NUM=1", "UTOOL_NUM=1", "L PR[99] 50mm/sec FINE RTCP"]
    assert lines(result) == ["PR[99]=P[1]", "CALL DAB", "PR[99]=P[2]", "CALL DAB"]
    direct = run(BEAD)
    by_number = {p.number: p.value for p in program(direct).positions}
    passed = {p.number: p.value for p in program(result).positions}
    assert passed[1] == by_number[3] and passed[2] == by_number[6]  # as the moves to pB, Offs(pA,0,0,10)


@pytest.mark.parametrize("body, procs, words", [
    # a point only known at run time: its inverse is not worked out on the robot
    ("Dab pSeen;", "PROC Dab(robtarget p)\nMoveL p,v50,fine,tNozzle\\WObj:=wPanel;\nENDPROC",
     "'pSeen' is only known at run time"),
    ("Dab pB;", "PROC Dab(robtarget p)\nMoveL Offs(p,0,0,5),v50,fine,tNozzle\\WObj:=wPanel;\nENDPROC",
     "to a point only known at run time"),
    ("MoveL pRow{nAt},v50,fine,tNozzle\\WObj:=wPanel;", "", "to a point only known at run time"),
    ("Dab pB;", "PROC Dab(robtarget p)\nMoveL RelTool(p,0,0,5),v50,fine,tNozzle\\WObj:=wPanel;\nENDPROC",
     "to a point only known at run time"),
    # not a remote TCP move: a work object moved by a mechanical unit, a stationary tool alone, a held one alone
    ("MoveL pA,v50,fine,tNozzle\\WObj:=wSlide;", "", "robot-held work object: converted only as a remote TCP move"),
    ("MoveL pA,v50,fine,tNozzle\\WObj:=wTable;", "", "stationary tool (robhold FALSE): converted only as a remote"),
    ("MoveL pA,v50,fine,tGrip\\WObj:=wPanel;", "", "robot-held work object: converted only as a remote TCP move"),
])  # fmt: skip
def test_what_stays_todo(body, procs, words):
    found = todos(run(body, procs))
    assert found and all(cause == Blocker.STATIONARY for cause, _ in found), found
    assert any(words in message for _, message in found), found
