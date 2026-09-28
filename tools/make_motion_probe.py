# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The motion probe: how fast and how round the converted moves are, measured on both simulators.

CrossArm turns RAPID speeds and zones into FANUC ones with two settings, joint_speed_ref_mm_s (MoveJ
v -> J %) and cnt_per_mm (zone radius -> CNT). Neither has an exact equivalent, and both depend on
the robots. This probe measures them, on the same points, on the ABB robot of a RobotStudio station
and on the FANUC robot of a ROBOGUIDE cell:

  joint   one joint move, timed: every RAPID speed on the ABB, J 5 % to 100 % on the FANUC
  linear  600 mm in a straight line, timed, at the same speeds on both
  zones   a right-angle corner passed with every RAPID zone and every CNT, at three speeds: the
          time, and how close the path comes to the corner (the TCP read while it moves)

Step 1, `prep`: the ABB robot moves to each point once (ConfJ\\Off) and reports it as it reached
it, confdata included (MotionPrep.mod, motionprep.txt). Step 2, `write`: MotionProbe.mod and
MOTIONPROBE.LS from those points, the FANUC positions converted by CrossArm. Step 3,
tools/probe_motion.py runs both and fits the settings.

Usage:  python tools/make_motion_probe.py prep | write
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crossarm.geometry import mat_mul, matrix_to_quat, rot_y, rot_z

OUT = ROOT / "tests" / "fixtures" / "probes" / "motion"
# Flange pointing down, turned 45 deg about z: J6 near 45 on the ABB and 135 on the FANUC, away from
# the quadrant and turn boundaries that make a CONFIG ambiguous.
DOWN = mat_mul(rot_y(180), rot_z(45))
START_JOINTS = "[[0,0,0,0,90,45],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]]"
# In reach of both a 2.85 m and a 1.8 m arm (checked on each), in front of them, flange 800 mm above the base.
POINTS = {
    "pCornerA": (1100.0, -200.0, 800.0),
    "pCornerB": (1400.0, -200.0, 800.0),  # the corner
    "pCornerC": (1400.0, 200.0, 800.0),
    "pLineA": (1100.0, -300.0, 800.0),
    "pLineB": (1100.0, 300.0, 800.0),
    "pJointA": (1100.0, -400.0, 600.0),
    "pJointB": (1400.0, 300.0, 1000.0),
    "pSwingA": (1100.0, -500.0, 800.0),  # mostly axis 1
    "pSwingB": (1100.0, 500.0, 800.0),
    "pRiseA": (1250.0, 0.0, 500.0),  # mostly axes 2 and 3
    "pRiseB": (1250.0, 0.0, 1100.0),
}


def _num(value: float, digits: int = 3) -> str:
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _orient() -> str:
    q = matrix_to_quat(DOWN)
    q = q if q[0] >= 0 else tuple(-c for c in q)
    return "[" + ",".join(_num(c, 7) for c in q) + "]"


def prep_module(points: dict | None = None, module: str = "MotionPrep", probe: str = "motion") -> str:
    """Step 1 for the points of a probe (this one's by default): HOME:/<probe>prep.txt."""
    points = POINTS if points is None else points
    file = f"{probe}prep.txt"
    lines = [
        f"MODULE {module}",
        f"    ! CrossArm - {probe} probe, step 1: move to each point once and write it as reached (confdata",
        f"    ! included) to HOME:/{file}. Real motion: RobotStudio only.",
        f"    CONST jointtarget jStart:={START_JOINTS};",
    ]
    for name, pos in points.items():
        lines.append(f"    CONST robtarget {name}:=[[{','.join(_num(c) for c in pos)}],{_orient()},[0,0,0,0],"
                     "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];")  # fmt: skip
    lines += [
        "",
        "    PROC Prep()",
        "        VAR iodev f;",
        f'        Open "HOME:" \\File:="{file}", f \\Write;',
        "        Close f;",
        "        ConfJ\\Off;",
        "        ConfL\\Off;",
        "        MoveAbsJ jStart,v1000,fine,tool0;",
    ]
    for name in points:
        lines += [f"        MoveJ {name},v1000,fine,tool0;", f'        Reached "{name}";']
    lines += [
        "        ConfJ\\On;",
        "        ConfL\\On;",
        "    ENDPROC",
        "",
        "    PROC Reached(string name)",
        "        VAR iodev f;",
        "        VAR robtarget p;",
        "        VAR jointtarget j;",
        "        p:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
        "        j:=CJointT();",
        f'        Open "HOME:" \\File:="{file}", f \\Append;',
        # One Write per part: RAPID strings hold 80 characters, and a longer one stops the program.
        '        Write f, name+" "+ValToStr(p.trans)+" "\\NoNewLine;',
        '        Write f, ValToStr(p.rot)+" "\\NoNewLine;',
        '        Write f, ValToStr(p.robconf)+" "\\NoNewLine;',
        "        Write f, ValToStr(j.robax);",
        "        Close f;",
        "    ENDPROC",
        "ENDMODULE",
        "",
    ]
    return "\r\n".join(lines)


# -- step 2: the probe itself ---------------------------------------------------------------

PREP = OUT / "results" / "motionprep_robotstudio.txt"
TIMER = 1  # TIMER[1] times each run on the FANUC
FIRST_REGISTER = 101  # R[101..]: the time of run i, in seconds
MOVE_TO_START = ("v1000", "30%")  # untimed moves to where a run starts
# The runs, in order: (name, start point, timed moves [(kind, point, speed, zone)]). Speeds and zones
# are RAPID ones on the ABB; the FANUC runs are listed apart (fanuc_runs), same points and order of kinds.
ABB_JOINT_SPEEDS = ["v100", "v200", "v300", "v500", "v800", "v1000", "v1500", "v2000", "v3000", "vmax"]
FANUC_JOINT_PERCENTS = [5, 10, 15, 20, 25, 30, 40, 50, 70, 100]
JOINT_MOVES = {"joint": ("pJointA", "pJointB"), "swing": ("pSwingA", "pSwingB"), "rise": ("pRiseA", "pRiseB")}
LINEAR_SPEEDS = [100, 200, 500, 1000, 1500, 2000]
CORNER_SPEEDS = [200, 500, 1000]
ABB_ZONES = ["fine", "z1", "z5", "z10", "z20", "z30", "z50", "z100", "z150", "z200"]
FANUC_CNTS = ["FINE", "CNT0", "CNT10", "CNT20", "CNT30", "CNT40", "CNT50", "CNT60", "CNT70", "CNT80", "CNT90",
              "CNT100"]  # fmt: skip
# The same corner passed with joint moves: RAPID speed -> the J % that takes as long (measured first).
JOINT_CORNERS = {"v500": "9%", "v1000": "19%"}
Run = tuple[str, str, list[tuple[str, str, str, str]]]


def abb_runs() -> list[Run]:
    runs: list[Run] = []
    for move, (start, end) in JOINT_MOVES.items():
        runs += [(f"{move} {v}", start, [("J", end, v, "fine")]) for v in ABB_JOINT_SPEEDS]
    runs += [(f"linear v{v}", "pLineA", [("L", "pLineB", f"v{v}", "fine")]) for v in LINEAR_SPEEDS]
    for v in CORNER_SPEEDS:
        for z in ABB_ZONES:
            runs.append((f"corner v{v} {z}", "pCornerA", [("L", "pCornerB", f"v{v}", z), ("L", "pCornerC", f"v{v}", "fine")]))
    for v in JOINT_CORNERS:
        for z in ABB_ZONES:
            runs.append((f"jcorner {v} {z}", "pCornerA", [("J", "pCornerB", v, z), ("J", "pCornerC", v, "fine")]))
    return runs


def fanuc_runs() -> list[Run]:
    runs: list[Run] = []
    for move, (start, end) in JOINT_MOVES.items():
        runs += [(f"{move} {pct}%", start, [("J", end, f"{pct}%", "FINE")]) for pct in FANUC_JOINT_PERCENTS]
    runs += [(f"linear {v}mm/sec", "pLineA", [("L", "pLineB", f"{v}mm/sec", "FINE")]) for v in LINEAR_SPEEDS]
    for v in CORNER_SPEEDS:
        for cnt in FANUC_CNTS:
            runs.append((f"corner {v}mm/sec {cnt}", "pCornerA",
                         [("L", "pCornerB", f"{v}mm/sec", cnt), ("L", "pCornerC", f"{v}mm/sec", "FINE")]))  # fmt: skip
    for pct in JOINT_CORNERS.values():
        for cnt in FANUC_CNTS:
            runs.append((f"jcorner {pct} {cnt}", "pCornerA", [("J", "pCornerB", pct, cnt), ("J", "pCornerC", pct, "FINE")]))
    return runs


def corner_runs(runs: list[Run]) -> list[str]:
    """The runs from pCornerA to pCornerC past pCornerB, in order: those the TCP samples measure."""
    return [name for name, start, moves in runs if start == "pCornerA" and moves[-1][1] == "pCornerC"]


def confdata(prep: Path = PREP) -> dict[str, str]:
    """The confdata the ABB robot reached each point with (step 1). J4 sits at 0, where its quadrant
    flickers between -1 and 0: both mean the same turn on the FANUC, 0 is written."""
    out = {}
    for line in prep.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) == 5:
            cf1, _cf4, cf6, cfx = (int(float(v)) for v in parts[3].strip("[]").split(","))
            out[parts[0]] = f"[{cf1},0,{cf6},{cfx}]"
    return out


def abb_module() -> str:
    conf = confdata()
    lines = [
        "MODULE MotionProbe",
        "    ! CrossArm - motion probe. In RobotStudio, PROC Probe times every run (ClkRead \\HighRes) and",
        "    ! writes 'name time' to HOME:/motionprobe.txt. PROC Path is what CrossArm converts. Real motion:",
        "    ! RobotStudio only.",
    ]
    for name, pos in POINTS.items():
        lines.append(f"    CONST robtarget {name}:=[[{','.join(_num(c) for c in pos)}],{_orient()},{conf[name]},"
                     "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];")  # fmt: skip
    lines += ["    VAR clock clk;", "", "    PROC Path()"]
    lines += [f"        Move{'J' if name.startswith('pJoint') else 'L'} {name},v1000,fine,tool0;" for name in POINTS]
    lines += [
        "    ENDPROC",
        "",
        "    PROC Probe()",
        "        VAR iodev f;",
        '        Open "HOME:" \\File:="motionprobe.txt", f \\Write;',
        "        Close f;",
    ]
    for name, start, moves in abb_runs():
        lines.append(f"        MoveJ {start},{MOVE_TO_START[0]},fine,tool0;")
        lines += ["        ClkReset clk;", "        ClkStart clk;"]
        for kind, point, speed, zone in moves:
            lines.append(f"        Move{kind} {point},{speed},{zone},tool0;")
        lines += ["        WaitTime\\InPos,0;", "        ClkStop clk;", f'        Log "{name}";']
    lines += [
        '        TPWrite "motionprobe.txt written in HOME:";',
        "    ENDPROC",
        "",
        "    PROC Log(string name)",
        "        VAR iodev f;",
        '        Open "HOME:" \\File:="motionprobe.txt", f \\Append;',
        '        Write f, name+" "+NumToStr(ClkRead(clk\\HighRes),3);',
        "        Close f;",
        "    ENDPROC",
        "ENDMODULE",
        "",
    ]
    return "\r\n".join(lines)


def fanuc_program(module_text: str) -> str:
    """The FANUC runs on the points CrossArm converted from PROC Path, each timed into R[101..]."""
    from datetime import datetime

    from crossarm.convert import ConversionConfig, convert
    from crossarm.fanuc.ls_writer import write_ls
    from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, Motion, Position, Program
    from crossarm.rapid import parse_text

    parsed = parse_text(module_text, path="MotionProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=["Path"])
    assert not [n for n in result.notes if n.kind == "TODO"], result.notes
    (info,) = result.programs
    motions = [line for line in info.program.lines if isinstance(line, Motion)]
    point = dict(zip(POINTS, (m.target for m in motions), strict=True))  # "pCornerA" -> "P[3]"
    positions = list(info.program.positions)
    (tool,) = result.utools
    assert tool.frame is not None and tool.frame.pose.pos == (0.0, 0.0, 0.0)  # tool0: the faceplate

    data = max(p.number for p in positions) + 1  # the tool frame's value, loaded into UTOOL through PR[20]
    positions.append(Position(data, 0, 1, CartesianPosition(0, 0, 0, 0, 0, 0)))
    lines: list[Instruction | Motion] = [
        Instruction("!CrossArm motion probe"),
        Instruction(f"PR[20]=P[{data}]"), Instruction(f"UTOOL[{tool.number}]=PR[20]"),
        Instruction("UFRAME_NUM=0"), Instruction(f"UTOOL_NUM={tool.number}"),
    ]  # fmt: skip
    for i, (name, start, moves) in enumerate(fanuc_runs()):
        lines += [Instruction(f"!{name}"[:32]), Motion("J", point[start], MOVE_TO_START[1], "FINE"),
                  Instruction(f"TIMER[{TIMER}]=RESET"), Instruction(f"TIMER[{TIMER}]=START")]  # fmt: skip
        lines += [Motion(kind, point[target], speed, zone) for kind, target, speed, zone in moves]
        lines += [Instruction(f"TIMER[{TIMER}]=STOP"), Instruction(f"R[{FIRST_REGISTER + i}]=TIMER[{TIMER}]")]
    attributes = Attributes(comment="motion probe", created=datetime(2026, 1, 1))
    return write_ls(Program("MOTIONPROBE", lines, positions, attributes))


# -- step 4: the check, converted by CrossArm with the settings fitted -------------------------

# RAPID moves at speeds the probe did not measure, converted by CrossArm as a user's would be. Both
# robots run them: the J % should take about as long, the CNT round the corner about as much.
CHECK_RUNS: list[Run] = [
    *[(f"check {move} {v}", start, [("J", end, v, "fine")])
      for move, (start, end) in JOINT_MOVES.items() for v in ("v400", "v600")],
    *[(f"check corner {v} {z}", "pCornerA", [("L", "pCornerB", v, z), ("L", "pCornerC", v, "fine")])
      for v in ("v300", "v600") for z in ("z5", "z10", "z20", "z30")],
    *[(f"check jcorner v600 {z}", "pCornerA", [("J", "pCornerB", "v600", z), ("J", "pCornerC", "v600", "fine")])
      for z in ("z10", "z20")],
]  # fmt: skip


def check_module() -> str:
    """MotionCheck.mod: PROC CheckPath is what CrossArm converts, PROC Check the same moves timed."""
    conf = confdata()
    lines = [
        "MODULE MotionCheck",
        "    ! CrossArm - motion check. PROC CheckPath is converted by CrossArm with its measured settings; in",
        "    ! RobotStudio, PROC Check runs the same moves timed and writes HOME:/motioncheck.txt. Real motion:",
        "    ! RobotStudio only.",
    ]
    for name, pos in POINTS.items():
        lines.append(f"    CONST robtarget {name}:=[[{','.join(_num(c) for c in pos)}],{_orient()},{conf[name]},"
                     "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];")  # fmt: skip
    lines += ["    VAR clock clk;", "", "    PROC CheckPath()"]
    for _, start, moves in CHECK_RUNS:
        lines.append(f"        MoveJ {start},{MOVE_TO_START[0]},fine,tool0;")
        lines += [f"        Move{kind} {point},{speed},{zone},tool0;" for kind, point, speed, zone in moves]
    lines += [
        "    ENDPROC",
        "",
        "    PROC Check()",
        "        VAR iodev f;",
        '        Open "HOME:" \\File:="motioncheck.txt", f \\Write;',
        "        Close f;",
    ]
    for name, start, moves in CHECK_RUNS:
        lines.append(f"        MoveJ {start},{MOVE_TO_START[0]},fine,tool0;")
        lines += ["        ClkReset clk;", "        ClkStart clk;"]
        lines += [f"        Move{kind} {point},{speed},{zone},tool0;" for kind, point, speed, zone in moves]
        lines += ["        WaitTime\\InPos,0;", "        ClkStop clk;", f'        Log "{name}";']
    lines += [
        "    ENDPROC",
        "",
        "    PROC Log(string name)",
        "        VAR iodev f;",
        '        Open "HOME:" \\File:="motioncheck.txt", f \\Append;',
        '        Write f, name+" "+NumToStr(ClkRead(clk\\HighRes),3);',
        "        Close f;",
        "    ENDPROC",
        "ENDMODULE",
        "",
    ]
    return "\r\n".join(lines)


def check_program(module_text: str, profile=None) -> str:
    """CrossArm's conversion of PROC CheckPath, each run timed into R[101..] as on the ABB."""
    from datetime import datetime

    from crossarm.convert import ConversionConfig, convert
    from crossarm.fanuc.ls_writer import write_ls
    from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, Motion, Position, Program
    from crossarm.rapid import parse_text

    parsed = parse_text(module_text, path="MotionCheck.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    if profile is not None:  # measured on another robot: as a mapping file would bring it in
        config.motion_profile, config.joint_speed_ref_mm_s = profile, profile.joint_speed_ref_mm_s
    result = convert([parsed.module], config, routines=["CheckPath"])
    assert not [n for n in result.notes if n.kind == "TODO"], result.notes
    (info,) = result.programs
    (tool,) = result.utools
    positions = list(info.program.positions)
    data = max(p.number for p in positions) + 1
    positions.append(Position(data, 0, 1, CartesianPosition(0, 0, 0, 0, 0, 0)))
    lines: list[Instruction | Motion] = [
        Instruction("!CrossArm motion check"),
        Instruction(f"PR[20]=P[{data}]"), Instruction(f"UTOOL[{tool.number}]=PR[20]"),
    ]  # fmt: skip
    # Motion k of the program is move k of CHECK_RUNS, each run being its move to the start and its timed moves.
    starts, ends, k = {}, {}, 0
    for i, (_, _, moves) in enumerate(CHECK_RUNS):
        starts[k + 1], ends[k + len(moves)] = i, i  # the first and last timed motion of run i
        k += 1 + len(moves)
    index = 0
    for line in info.program.lines:
        if isinstance(line, Motion):
            if index in starts:
                lines += [Instruction(f"TIMER[{TIMER}]=RESET"), Instruction(f"TIMER[{TIMER}]=START")]
            lines.append(line)
            if index in ends:
                lines += [Instruction(f"TIMER[{TIMER}]=STOP"),
                          Instruction(f"R[{FIRST_REGISTER + ends[index]}]=TIMER[{TIMER}]")]  # fmt: skip
            index += 1
        else:
            lines.append(line)
    assert index == k, (index, k)
    attributes = Attributes(comment="motion check", created=datetime(2026, 1, 1))
    return write_ls(Program("MOTIONCHECK", lines, positions, attributes))


def main() -> int:
    if sys.argv[1:] == ["check"]:
        module = check_module()
        (OUT / "MotionCheck.mod").write_bytes(module.encode("ascii"))
        (OUT / "MOTIONCHECK.LS").write_bytes(check_program(module).encode("ascii"))
        print(f"{len(CHECK_RUNS)} check runs written to {OUT}")
        return 0
    if sys.argv[1:] == ["prep"]:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "MotionPrep.mod").write_bytes(prep_module().encode("ascii"))
        print(OUT / "MotionPrep.mod")
        return 0
    if sys.argv[1:] == ["write"]:
        module = abb_module()
        (OUT / "MotionProbe.mod").write_bytes(module.encode("ascii"))
        (OUT / "MOTIONPROBE.LS").write_bytes(fanuc_program(module).encode("ascii"))
        print(f"{len(abb_runs())} ABB runs, {len(fanuc_runs())} FANUC runs written to {OUT}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
