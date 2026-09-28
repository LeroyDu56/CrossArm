# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the pose probe: does a converted program put the robot where the RAPID one does?

The configuration probes measured how each controller names an arm posture. This one
checks the arithmetic in between, end to end: tool and work object frames, quaternions
to W,P,R, Offs() and RelTool(), all composed. A module of test moves is converted by
CrossArm itself, then each controller works out where the robot flange ends up for every
move, in the world frame:

  ABB (RobotStudio, no motion): PoseProbe.mod, PROC Probe, computes
      uframe * oframe * target * inverse(tframe) with PoseMult / PoseInv and writes it
      to HOME:/poseprobe.txt.
  FANUC (ROBOGUIDE, simulated motion): POSEPROBE.LS loads the UTOOL / UFRAME values
      CrossArm derived, moves to each converted point, then records the faceplate pose
      (a zero UTOOL, UFRAME 0) in PR[51..]. The controller's posreg.va is the result.

The same flange pose on both sides, move by move, means the conversion is right. The
tool offsets are asymmetric on purpose: an orientation convention error cannot hide
behind a symmetric tool. Positions are compared without any convention at all.

tests/fixtures/probes/pin checks the tool's pin in the +x hole of the faceplate ("tool_pin":
"+x"): the same moves with every ABB flange half a turn about z (J6 near 0 on the ABB, the
usual [0,0,1,0] orientation pointing down), converted with the tool frames turned. The
faceplate must end up half a turn about z from the ABB flange, at the same place, which is
where POSEPROBE puts it. RobotStudio runs PinProbe.mod like PoseProbe.mod (pinprobe.txt).

Usage:  python tools/make_pose_probe.py [output_dir]   (default tests/fixtures/probes)
        python tools/make_pose_probe.py compare poseprobe.txt posreg.va
"""

import math
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.configuration import TOOL_PIN_DEFAULT
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, JointPosition, Motion, Position, Program
from crossarm.geometry import Pose, mat_mul, mat_vec, matrix_to_quat, quat_to_matrix, rot_x, rot_y, rot_z
from crossarm.rapid import parse_text

ZERO_TOOL = 9  # UTOOL loaded with zeros: its TCP is the faceplate
FRAME_PR = 20  # PR[21..] hold the frame values on their way to UTOOL[] / UFRAME[]
FLANGE_PR = 50  # PR[51..]: faceplate pose in the world frame after move i
JOINTS_PR = 70  # PR[71..]: joint angles after move i, to diagnose a point out of reach
# Flange pointing down as a FANUC arm holds it with J4 = J6 = 0 (W -180, R 0, measured on the M-20iD/25).
# Rotations about z are kept well inside J6 = +/-180: at exactly 180 the turn number is ambiguous.
DOWN = rot_x(180)
HOME_JOINTS = (0.0, 0.0, 0.0, 0.0, -90.0, 0.0)  # the known start: flange down in front of the robot

# name -> (x, y, z, rotation). Offsets deliberately asymmetric, two tools rotated.
TOOLS = {
    "tProbeA": ((30.0, -50.0, 180.0), rot_z(0)),
    "tProbeB": ((-40.0, 25.0, 220.0), rot_y(30)),
    "tProbeC": ((15.0, 60.0, 150.0), mat_mul(rot_z(90), rot_x(-20))),
}
# name -> (uframe, oframe), each (x, y, z, rotation): rotated user frames with an object frame on top.
WOBJS = {
    "wProbe1": (((800.0, -350.0, 150.0), rot_z(30)), ((60.0, 25.0, 0.0), rot_z(0))),
    "wProbe2": (((950.0, 250.0, 300.0), mat_mul(rot_z(-25), rot_x(4))), ((0.0, 0.0, 40.0), rot_z(15))),
}
# Base targets: name -> (wobj, tool, flange position in the world, flange rotation). The robtarget is
# worked back from the flange pose, so every move stays in reach of a 1.8 m robot, pointing down.
TARGETS = {
    "pProbe1": ("wobj0", "tProbeA", (1100.0, 0.0, 700.0), DOWN),
    "pProbe2": ("wobj0", "tProbeB", (1000.0, -300.0, 600.0), mat_mul(rot_z(20), DOWN)),
    "pProbe3": ("wProbe1", "tProbeA", (1150.0, -200.0, 500.0), mat_mul(rot_z(-15), mat_mul(DOWN, rot_x(10)))),
    "pProbe4": ("wProbe1", "tProbeC", (1050.0, -400.0, 450.0), mat_mul(rot_z(40), mat_mul(DOWN, rot_y(-10)))),
    "pProbe5": ("wProbe2", "tProbeB", (1000.0, 300.0, 650.0), mat_mul(rot_z(-30), DOWN)),
    "pProbe6": ("wProbe2", "tProbeC", (1200.0, 100.0, 550.0), mat_mul(DOWN, rot_y(-12))),
    "pProbe7": ("wProbe1", "tProbeB", (1250.0, -100.0, 400.0), mat_mul(rot_z(10), mat_mul(DOWN, rot_x(-8)))),
    "pProbe8": ("wProbe2", "tProbeA", (900.0, 450.0, 750.0), mat_mul(rot_z(55), DOWN)),
}
# The probed moves: (RAPID target expression, tool, wobj). Offs / RelTool on top of the base targets.
MOVES = [
    ("pProbe1", "tProbeA", "wobj0"),
    ("pProbe2", "tProbeB", "wobj0"),
    ("pProbe3", "tProbeA", "wProbe1"),
    ("pProbe4", "tProbeC", "wProbe1"),
    ("pProbe5", "tProbeB", "wProbe2"),
    ("pProbe6", "tProbeC", "wProbe2"),
    ("pProbe7", "tProbeB", "wProbe1"),
    ("pProbe8", "tProbeA", "wProbe2"),
    ("Offs(pProbe3,60,-40,30)", "tProbeA", "wProbe1"),
    ("Offs(pProbe5,-50,20,-35)", "tProbeB", "wProbe2"),
    ("RelTool(pProbe5,20,-30,40)", "tProbeB", "wProbe2"),
    ("RelTool(pProbe6,0,0,-50\\Rz:=35)", "tProbeC", "wProbe2"),
    ("RelTool(pProbe2,10,10,10\\Rx:=12\\Ry:=-8\\Rz:=20)", "tProbeB", "wobj0"),
    ("RelTool(pProbe4,0,0,0\\Rx:=-15)", "tProbeC", "wProbe1"),
    ("Offs(RelTool(pProbe1,0,0,-40\\Ry:=10),0,80,0)", "tProbeA", "wobj0"),
    ("pProbe1", "tProbeC", "wobj0"),  # the same target with another tool: the flange must move
]


def _pose(pos: tuple[float, float, float], rot) -> Pose:
    return Pose(pos, matrix_to_quat(rot))


def inverse(pose: Pose) -> Pose:
    m = quat_to_matrix(pose.rot)
    mt = tuple(tuple(m[j][i] for j in range(3)) for i in range(3))
    moved = mat_vec(mt, pose.pos)  # type: ignore[arg-type]
    return Pose((-moved[0], -moved[1], -moved[2]), matrix_to_quat(mt))  # type: ignore[arg-type]


def wobj_pose(name: str) -> Pose:
    if name == "wobj0":
        return Pose((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))
    (upos, urot), (opos, orot) = WOBJS[name]
    return _pose(upos, urot).compose(_pose(opos, orot))


def target_pose(name: str, pin: bool = False) -> Pose:
    """The robtarget, in its work object, that puts the flange where TARGETS says with that tool
    (turned half a turn about its z for the pin probe)."""
    wobj, tool, flange_pos, flange_rot = TARGETS[name]
    if pin:
        flange_rot = mat_mul(flange_rot, rot_z(180))
    tcp_world = _pose(flange_pos, flange_rot).compose(_pose(*TOOLS[tool]))
    return inverse(wobj_pose(wobj)).compose(tcp_world)


def _num(value: float, digits: int) -> str:
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _quat(q) -> str:
    q = q if q[0] >= 0 else tuple(-c for c in q)  # same rotation, the sign RobotStudio shows
    return "[" + ",".join(_num(c, 7) for c in q) + "]"


def _frame(pos, rot) -> str:
    return f"[[{','.join(_num(c, 3) for c in pos)}],{_quat(matrix_to_quat(rot))}]"


def abb_module(pin: bool = False) -> str:
    name, output = ("PinProbe", "pinprobe.txt") if pin else ("PoseProbe", "poseprobe.txt")
    lines = [
        f"MODULE {name}",
        "    ! CrossArm - pose probe. In RobotStudio, run PROC Probe (no motion): for every move of",
        f"    ! PROC Path it writes the flange pose in the world frame to HOME:/{output},",
        "    ! as i x y z q1 q2 q3 q4. PROC Path is what CrossArm converts: never run it on a robot.",
    ]
    for name, (pos, rot) in TOOLS.items():
        lines.append(f"    PERS tooldata {name}:=[TRUE,{_frame(pos, rot)},[1,[0,0,50],[1,0,0,0],0,0,0]];")
    for name, (uframe, oframe) in WOBJS.items():
        lines.append(f'    PERS wobjdata {name}:=[FALSE,TRUE,"",{_frame(*uframe)},{_frame(*oframe)}];')
    for name in TARGETS:
        t = target_pose(name, pin)
        conf = "[-1,0,0,0]" if t.pos[1] < 0 and TARGETS[name][0] == "wobj0" else "[0,0,0,0]"
        lines.append(
            f"    CONST robtarget {name}:=[[{','.join(_num(c, 3) for c in t.pos)}],{_quat(t.rot)},{conf},"
            "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];"
        )
    lines += ["", "    PROC Path()"]
    for expr, tool, wobj in MOVES:
        lines.append(f"        MoveJ {expr},v200,fine,{tool}\\WObj:={wobj};")
    lines += [
        "    ENDPROC",
        "",
        "    PROC Probe()",
        "        VAR iodev f;",
        f'        Open "HOME:" \\File:="{output}", f \\Write;',
        "        Close f;",
    ]
    for i, (expr, tool, wobj) in enumerate(MOVES, start=1):
        lines.append(f"        WriteFlange {i},{expr},{tool},{wobj};")
    lines += [
        f'        TPWrite "{output} written in HOME:";',
        "        Stop;",
        "    ENDPROC",
        "",
        "    PROC WriteFlange(num i,robtarget target,PERS tooldata tool,PERS wobjdata wobj)",
        "        VAR iodev f;",
        "        VAR pose tcp;",
        "        VAR pose flange;",
        "        tcp.trans:=target.trans;",
        "        tcp.rot:=target.rot;",
        "        flange:=PoseMult(PoseMult(PoseMult(wobj.uframe,wobj.oframe),tcp),PoseInv(tool.tframe));",
        f'        Open "HOME:" \\File:="{output}", f \\Append;',
        (
            '        Write f, NumToStr(i,0)+" "+NumToStr(flange.trans.x,3)+" "+NumToStr(flange.trans.y,3)+" "'
            '+NumToStr(flange.trans.z,3)\\NoNewLine;'
        ),
        (
            '        Write f, " "+NumToStr(flange.rot.q1,6)+" "+NumToStr(flange.rot.q2,6)+" "+NumToStr(flange.rot.q3,6)'
            '+" "+NumToStr(flange.rot.q4,6);'
        ),
        "        Close f;",
        "    ENDPROC",
        "ENDMODULE",
        "",
    ]
    return "\r\n".join(lines)


PIN_PROGRAM = "POSEPIN"  # the path with "tool_pin": "+x"


def fanuc_program(module_text: str, tool_pin: str = TOOL_PIN_DEFAULT) -> str:
    """CrossArm's own conversion of PROC Path, wrapped with frame loading and measurements."""
    parsed = parse_text(module_text, path="PoseProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1), tool_pin=tool_pin)
    result = convert([parsed.module], config, routines=["Path"])
    assert not [n for n in result.notes if n.kind == "TODO"], result.notes
    (info,) = result.programs
    by_number = {p.number: p for p in info.program.positions}
    motions = [line for line in info.program.lines if isinstance(line, Motion)]
    assert len(motions) == len(MOVES)

    lines: list[Instruction | Motion] = [Instruction("!CrossArm pose probe")]
    positions = list(info.program.positions)
    data = max(by_number) + 1  # P[n] used as data only: the frame values, never moved to

    def load(kind: str, number: int, pose: Pose) -> None:
        nonlocal data
        (x, y, z), (w, p, r) = pose.pos, pose.wpr()
        positions.append(Position(data, 0, 1, CartesianPosition(x, y, z, w, p, r)))
        register = FRAME_PR + (number if kind == "UTOOL" else 5 + number)
        lines.append(Instruction(f"PR[{register}]=P[{data}]"))
        lines.append(Instruction(f"{kind}[{number}]=PR[{register}]"))
        data += 1

    lines.append(Instruction("!load the frames"))
    for frame in result.utools:
        assert frame.frame is not None
        load("UTOOL", frame.number, frame.frame.pose)
    load("UTOOL", ZERO_TOOL, Pose((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)))
    for frame in result.uframes:
        if frame.number and frame.frame is not None:
            load("UFRAME", frame.number, frame.frame.pose)

    # A joint move first, which is always reachable, and its pose in PR[50]: if a probed move fails,
    # this still tells whether the robot and its world frame are the ones the probe was built for.
    positions.append(Position(data, 0, ZERO_TOOL, JointPosition(HOME_JOINTS)))
    lines += [Instruction("!known start"), Instruction("UFRAME_NUM=0"), Instruction(f"UTOOL_NUM={ZERO_TOOL}"),
              Motion("J", f"P[{data}]", "10%", "FINE"),
              Instruction(f"PR[{FLANGE_PR}]=LPOS"), Instruction(f"PR[{JOINTS_PR}]=JPOS")]  # fmt: skip

    for i, motion in enumerate(motions, start=1):
        target = by_number[int(motion.target[2:-1])]
        lines += [Instruction(f"!move {i}"), Instruction(f"UFRAME_NUM={target.uf}"),
                  Instruction(f"UTOOL_NUM={target.ut}"), motion,
                  Instruction("UFRAME_NUM=0"), Instruction(f"UTOOL_NUM={ZERO_TOOL}"),
                  Instruction(f"PR[{FLANGE_PR + i}]=LPOS"), Instruction(f"PR[{JOINTS_PR + i}]=JPOS")]  # fmt: skip
    name = "POSEPROBE" if tool_pin == TOOL_PIN_DEFAULT else PIN_PROGRAM
    attributes = Attributes(comment="pose probe", created=datetime(2026, 1, 1))
    return write_ls(Program(name, lines, positions, attributes))


def expected_flanges(pin: bool = False) -> list[Pose]:
    """The flange pose of every move, worked out here with quaternions (ABB's own convention)."""
    from crossarm.convert.values import Evaluator, Symbols

    module = parse_text(abb_module(pin), path="PoseProbe.mod").module
    assert module is not None
    evaluator = Evaluator(Symbols.from_modules([module]))
    out = []
    for expr, tool, wobj in MOVES:
        target = evaluator.robtarget(parse_text(f"MODULE M\nPROC p()\nMoveJ {expr},v10,fine,tool0;\nENDPROC\nENDMODULE")
                                     .module.routines[0].body[0].to_point)  # type: ignore[union-attr]
        tframe = evaluator.tool(_name(tool)).pose
        out.append(wobj_pose(wobj).compose(target.pose).compose(inverse(tframe)))
    return out


def _name(text: str):
    from crossarm.rapid import nodes as n

    return n.Name(n.Span(1, 0), text)


# -- reading the results ------------------------------------------------------------


def read_robotstudio(text: str) -> dict[int, Pose]:
    """poseprobe.txt: 'i x y z q1 q2 q3 q4' per move."""
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 8:
            i, *values = parts
            x, y, z, q1, q2, q3, q4 = (float(v) for v in values)
            out[int(i)] = Pose((x, y, z), (q1, q2, q3, q4))
    return out


def read_posreg(text: str) -> dict[int, tuple[float, ...]]:
    """Cartesian position registers of a posreg.va dump: number -> (x, y, z, w, p, r).

    Read loosely, field by field ('X:', 'Y:', ... possibly with '=' and units), so that the
    listing ROBOGUIDE shows and the file the controller writes are both accepted.
    """
    out = {}
    for block in re.split(r"(?=\[\s*1\s*,\s*\d+\s*\])", text):
        head = re.match(r"\[\s*1\s*,\s*(\d+)\s*\]", block)
        if not head:
            continue
        values = []
        for axis in "XYZWPR":
            found = re.search(rf"\b{axis}\s*[:=]\s*(-?\d*\.?\d+)", block)
            if not found:
                break
            values.append(float(found.group(1)))
        if len(values) == 6:
            out[int(head.group(1))] = tuple(values)
    return out


def angle_between(a, b) -> float:
    """Angle (degrees) of the rotation taking matrix a to matrix b."""
    trace = sum(a[k][i] * b[k][i] for i in range(3) for k in range(3))  # trace(a^T b)
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1) / 2))))


def compare(abb: dict[int, Pose], fanuc: dict[int, tuple[float, ...]],
            tool_pin: str = TOOL_PIN_DEFAULT) -> list[tuple[int, float, float]]:  # fmt: skip
    """(move, position gap mm, orientation gap deg) for every move measured on both sides.

    With the tool's pin in the +x hole, the faceplate is expected half a turn about its z from the
    ABB flange: the tool frames were turned the other way, so the TCP is where RAPID puts it."""
    from crossarm.geometry import wpr_to_matrix

    turn = Pose((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0) if tool_pin == TOOL_PIN_DEFAULT else (0.0, 0.0, 0.0, 1.0))
    rows = []
    for i in sorted(abb):
        if FLANGE_PR + i not in fanuc:
            continue
        x, y, z, w, p, r = fanuc[FLANGE_PR + i]
        ref = abb[i].compose(turn)
        gap = math.dist(ref.pos, (x, y, z))
        rows.append((i, gap, angle_between(quat_to_matrix(ref.rot), wpr_to_matrix(w, p, r))))
    return rows


def main() -> None:
    if len(sys.argv) == 4 and sys.argv[1] == "compare":
        abb = read_robotstudio(Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace"))
        fanuc = read_posreg(Path(sys.argv[3]).read_text(encoding="utf-8", errors="replace"))
        rows = compare(abb, fanuc)
        for i, gap, turn in rows:
            print(f"move {i:2d}: {gap:8.3f} mm  {turn:7.3f} deg")
        print(f"{len(rows)} of {len(MOVES)} moves measured on both sides")
        return
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "tests/fixtures/probes"
    (out / "pose").mkdir(parents=True, exist_ok=True)
    (out / "pin").mkdir(parents=True, exist_ok=True)
    module = abb_module()
    (out / "pose" / "PoseProbe.mod").write_bytes(module.encode("ascii"))
    (out / "pose" / "POSEPROBE.LS").write_bytes(fanuc_program(module).encode("ascii"))
    pin = abb_module(pin=True)
    (out / "pin" / "PinProbe.mod").write_bytes(pin.encode("ascii"))
    (out / "pin" / f"{PIN_PROGRAM}.LS").write_bytes(fanuc_program(pin, "+x").encode("ascii"))
    for i, flange in enumerate(expected_flanges(), start=1):
        reach = math.hypot(flange.pos[0], flange.pos[1])
        print(f"move {i:2d}: flange at {', '.join(f'{c:8.1f}' for c in flange.pos)}  (radius {reach:6.0f} mm)")
    print(f"probe written to {out}")


if __name__ == "__main__":
    main()
