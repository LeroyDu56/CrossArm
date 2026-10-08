# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the KAREL pose probe (--karel): PoseInv, RelTool, DefFrame by CrossArm's KAREL library.

Two parts, on ROBOGUIDE, the library compiled as a conversion compiles it (crossarm.fanuc.ktrans):

- KPRAW.LS, written by hand: poses and points set in position registers, then CA_POSEINV, CA_RELTOOL (constant
  arguments, negative ones in parentheses, registers R[i] holding a whole and a real number, angles past 180
  and a pitch past 90), CA_DEFFRAME with each origin, CA_POSEMULT of a pose and its inverse. The registers are
  compared with RAPID's PoseInv, RelTool and DefFrame worked out here from quaternions and vectors, without
  CrossArm's geometry (RobotStudio computes these the same as CrossArm: compute and pose probes).
- error cases, each a TP program calling the library wrongly then setting a register that must stay 0:
  DefFrame of two points closer than 10 mm, DefFrame \\Origin 4 (ROUT-035), RelTool given a string (ROUT-043).
- KPCONV.LS, converted by CrossArm from KarelPoseProbe.mod with --karel: three points read on the robot
  (CRobT after a move, PR[k]=LPOS), a work object's uframe set to DefFrame of them and a move in it, a tool's
  tframe set to PoseMult(tframe, PoseInv(pose)) (tframe read back, PR[k]=UTOOL[n]) and a move with it, RelTool of
  a point read on the robot (orientation only known at run time) and a move to it; after each move the robot's flange is read in the
  world frame (CRobT(\\Tool:=tool0 \\WObj:=wobj0): PR[k]=LPOS, tool0 and UFRAME 0 selected), and compared with
  where RAPID puts it, worked out here from the points read. SETUP_FRAMES.LS runs first: the work object as
  saved is 50 mm and 37 deg away from the one DefFrame makes, so only the frame KAREL loads puts the flange
  there. KPPREP makes CrossArm's registers Cartesian first (another probe may leave joints in them).

  python tools/make_karel_pose_probe.py write    the module and the programs, in tests/fixtures/probes/karelpose
  python tools/make_karel_pose_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results stored
  python tools/make_karel_pose_probe.py check    the stored results against what was measured
"""

import math
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_karel_probe import _ftp, alarm, q_from_wpr, q_mul, q_turn, q_unit, read_pr

from crossarm.fanuc.ktrans import KarelRequest, export
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program

PROBE = ROOT / "tests" / "fixtures" / "probes" / "karelpose"
RESULT = PROBE / "results" / "karelpose_roboguide.txt"
STAMP = datetime(2026, 1, 1)
LIBRARY = ["CA_POSEMULT", "CA_POSEINV", "CA_RELTOOL", "CA_DEFFRAME"]
RAW = "KPRAW"
DONE = 81  # R[81] = 1 at the end of KPRAW
ARGS = {82: "10", 83: "2.5"}  # R[i] given to CA_RELTOOL: a whole and a real number
# Inputs (PR, X Y Z W P R)
A = (100.0, -50.0, 300.0, 30.0, -20.0, 45.0)
Q1, Q2, Q3 = (600.0, 100.0, 400.0), (800.0, 250.0, 420.0), (650.0, 300.0, 380.0)
CLOSE = (603.0, 100.0, 400.0)  # 3 mm from Q1
INPUTS = {81: A, 84: (*Q1, 0.0, 0.0, 0.0), 85: (*Q2, 0.0, 0.0, 0.0), 86: (*Q3, 0.0, 0.0, 0.0),
          87: (*CLOSE, 0.0, 0.0, 0.0)}  # fmt: skip
CALLS = {  # result PR: the CALL, and RAPID's value (worked out below)
    88: "CALL CA_POSEINV(81,88)",
    89: "CALL CA_RELTOOL(81,89,R[82],20,R[83],30,(-20),45)",
    90: "CALL CA_RELTOOL(81,90,0,0,(-15),0,0,(-90))",
    91: "CALL CA_RELTOOL(81,91,5,0,0,200,120,0)",
    92: "CALL CA_DEFFRAME(84,85,86,92,1)",
    93: "CALL CA_DEFFRAME(84,85,86,93,2)",
    94: "CALL CA_DEFFRAME(84,85,86,94,3)",
    95: "CALL CA_POSEMULT(81,88,95)",
}
ERRORS = {  # program: its CALL, the alarm, the R set after it
    "KPERRCLS": ("CALL CA_DEFFRAME(84,87,86,92,1)", "ROUT-035", 86),
    "KPERRORG": ("CALL CA_DEFFRAME(84,85,86,92,4)", "ROUT-035", 87),
    "KPERRSTR": ("CALL CA_RELTOOL(81,89,'X',0,0,0,0,0)", "ROUT-043", 88),
}
# The converted part: three points the robot is moved to (tool0, wobj0, tool down), read back with CRobT
CONV = "KPCONV"
TARGETS = ((900.0, -100.0, 800.0), (1100.0, 50.0, 820.0), (950.0, 150.0, 780.0))
DOWN = (0.0, 0.0, 1.0, 0.0)  # a half turn about y: the tool's z down
IN_WOBJ = ((100.0, 50.0, -50.0), DOWN)  # kpP, in the work object DefFrame of the points makes
BASE = ((0.0, 0.0, 150.0), (0.9659258, 0.0, 0.258819, 0.0))  # kpTool as saved: 150 mm out, 30 deg about y
SHIFT = (0.0, 5.0, 0.0)  # kpCor: worked out at run time from kpM1 (kpT1 + 5 mm in y)
TURN = ((0.0, 0.0, -30.0), -90.0)  # RelTool(kpM2, 0, 0, -30 \Rz:=-90)
SEEN = ("kpF1", "kpF2", "kpF3")  # the flange read after each move (CRobT(\Tool:=tool0 \WObj:=wobj0))


def _pose(p: tuple) -> str:
    return f"[[{','.join(f'{v:g}' for v in p[0])}],[{','.join(f'{v:.7g}' for v in p[1])}]]"


def _robtarget(xyz: tuple, q: tuple = DOWN) -> str:
    return f"[[{','.join(f'{v:g}' for v in xyz)}],[{','.join(f'{v:.7g}' for v in q)}],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]]"


MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE KarelPoseProbe",
    "    ! CrossArm - KAREL pose probe: see tools/make_karel_pose_probe.py.",
    f"    PERS tooldata kpTool:=[TRUE,{_pose(BASE)},[5,[0,0,50],[1,0,0,0],0,0,0]];",
    "    PERS wobjdata kpWobj:=[FALSE,TRUE,\"\",[[1000,0,800],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];",
    *(f"    CONST robtarget kpT{i}:={_robtarget(t)};" for i, t in enumerate(TARGETS, 1)),
    f"    CONST robtarget kpP:={_robtarget(IN_WOBJ[0])};",
    "    VAR robtarget kpM1;",
    "    VAR robtarget kpM2;",
    "    VAR robtarget kpM3;",
    "    VAR robtarget kpTurn;",
    *(f"    VAR robtarget {name};" for name in SEEN),
    "    VAR pose kpCor;",
    "    VAR num kpDone:=0;",
    "",
    "    PROC KpConv()",
    "        kpDone:=0;",
    "        MoveJ kpT1,v500,fine,tool0;",
    "        kpM1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        MoveL kpT2,v500,fine,tool0;",
    "        kpM2:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        MoveL kpT3,v500,fine,tool0;",
    "        kpM3:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        kpWobj.uframe:=DefFrame(kpM1,kpM2,kpM3\\Origin:=3);",
    "        MoveL kpP,v500,fine,tool0\\WObj:=kpWobj;",
    "        kpF1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    f"        kpTurn:=RelTool(kpM2,0,0,{TURN[0][2]:g}\\Rz:={TURN[1]:g});",
    "        MoveL kpTurn,v500,fine,tool0;",
    "        kpF2:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    f"        kpCor:=[[kpM1.trans.x-{TARGETS[0][0]:g},kpM1.trans.y-({TARGETS[0][1]:g})+{SHIFT[1]:g},0],[1,0,0,0]];",
    "        kpTool.tframe:=PoseMult(kpTool.tframe,PoseInv(kpCor));",
    "        MoveL kpT1,v500,fine,kpTool;",
    "        kpF3:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        kpDone:=1;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip


# -- RAPID's semantics, with quaternions (w, x, y, z) and vectors, independently of CrossArm ------------------------


def _about(axis: int, degrees: float) -> tuple[float, ...]:
    half = math.radians(degrees) / 2
    return (math.cos(half), *(math.sin(half) if i == axis else 0.0 for i in range(3)))


def pose(values: tuple[float, ...]) -> tuple:
    """A PR's X, Y, Z, W, P, R as ((x, y, z), q)."""
    return tuple(values[:3]), q_unit(q_from_wpr(*values[3:]))


def pose_inv(p: tuple) -> tuple:
    """RAPID PoseInv."""
    t, q = p
    conj = (q[0], -q[1], -q[2], -q[3])
    return tuple(-c for c in q_turn(conj, t)), conj


def pose_mult(a: tuple, b: tuple) -> tuple:
    """RAPID PoseMult: b expressed in the frame a."""
    (ta, qa), (tb, qb) = a, b
    return tuple(x + y for x, y in zip(ta, q_turn(qa, tb), strict=True)), q_unit(q_mul(qa, qb))


def rel_tool(p: tuple, d: tuple, rx: float = 0.0, ry: float = 0.0, rz: float = 0.0) -> tuple:
    """RAPID RelTool: displaced along the point's own axes, then turned about its x, then y, then z."""
    t, q = p
    turned = q_mul(q_mul(q_mul(q, _about(0, rx)), _about(1, ry)), _about(2, rz))
    return tuple(x + y for x, y in zip(t, q_turn(q, d), strict=True)), q_unit(turned)


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b, strict=True))


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(v):
    norm = math.sqrt(_dot(v, v))
    return tuple(c / norm for c in v)


def def_frame(p1, p2, p3, origin: int) -> tuple:
    """RAPID DefFrame: x from p1 towards p2, p3 on the positive y side; origin p1, p2, or on the line p1-p2
    where y passes through p3."""
    x = _unit(_sub(p2, p1))
    z = _unit(_cross(x, _sub(p3, p1)))
    y = _cross(z, x)
    o = {1: p1, 2: p2, 3: tuple(a + _dot(_sub(p3, p1), x) * c for a, c in zip(p1, x, strict=True))}[origin]
    m = [[x[i], y[i], z[i]] for i in range(3)]  # columns x, y, z
    w = math.sqrt(max(0.0, 1 + m[0][0] + m[1][1] + m[2][2])) / 2
    if w > 1e-6:
        q = (w, (m[2][1] - m[1][2]) / (4 * w), (m[0][2] - m[2][0]) / (4 * w), (m[1][0] - m[0][1]) / (4 * w))
    else:  # a half turn: from the largest diagonal term
        i = max(range(3), key=lambda k: m[k][k])
        j, k = (i + 1) % 3, (i + 2) % 3
        s = math.sqrt(max(0.0, 1 + m[i][i] - m[j][j] - m[k][k])) * 2
        v = [0.0, 0.0, 0.0]
        v[i], v[j], v[k] = s / 4, (m[j][i] + m[i][j]) / s, (m[k][i] + m[i][k]) / s
        q = ((m[k][j] - m[j][k]) / s, *v)
    return tuple(o), q_unit(q)


def expected_raw() -> dict[int, tuple]:
    a = pose(A)
    inverse = pose_inv(a)
    return {
        88: inverse,
        89: rel_tool(a, (10.0, 20.0, 2.5), 30.0, -20.0, 45.0),
        90: rel_tool(a, (0.0, 0.0, -15.0), rz=-90.0),
        91: rel_tool(a, (5.0, 0.0, 0.0), 200.0, 120.0),
        92: def_frame(Q1, Q2, Q3, 1),
        93: def_frame(Q1, Q2, Q3, 2),
        94: def_frame(Q1, Q2, Q3, 3),
        95: pose_mult(a, inverse),
    }


# -- the programs ---------------------------------------------------------------------------------------------------


def _fmt(v: float) -> str:
    text = f"{v:.3f}".rstrip("0").rstrip(".")
    return f"({text})" if v < 0 else text


def _set(register: int, values: tuple[float, ...]) -> list[str]:
    """PR[k] made Cartesian (LPOS), then its six values."""
    return [f"PR[{register}]=LPOS"] + [f"PR[{register},{i}]={_fmt(v)}" for i, v in enumerate(values, 1)]


def _program(name: str, lines: list[str], comment: str) -> Program:
    return Program(name, [Instruction(text) for text in lines], attributes=Attributes(comment=comment, created=STAMP))


def raw_programs() -> list[Program]:
    lines = ["UFRAME_NUM=0", "UTOOL_NUM=1", f"R[{DONE}]=0"]
    lines += [f"R[{k}]={v}" for k, v in ARGS.items()]
    for register, values in INPUTS.items():
        lines += _set(register, values)
    lines += list(CALLS.values()) + [f"R[{DONE}]=1"]
    programs = [_program(RAW, lines, "KAREL pose probe")]
    for name, (call, _code, flag) in ERRORS.items():
        programs.append(_program(name, [call, f"R[{flag}]=1"], "KAREL error case"))
    return programs


def conversion(folder: Path):
    """KarelPoseProbe.mod converted with --karel as `crossarm convert` does: KPCONV.LS, SETUP_FRAMES.LS."""
    from crossarm import pipeline
    from crossarm.convert import ConversionConfig

    (PROBE / "KarelPoseProbe.mod").write_bytes(MODULE.encode("ascii"))
    run = pipeline.run([PROBE / "KarelPoseProbe.mod"], folder, ConversionConfig(timestamp=STAMP, karel=True),
                       log=lambda _: None)  # fmt: skip
    result = run.tasks[0].result
    assert result is not None and not [n for n in result.notes if n.kind == "TODO"], result and result.notes
    assert result.karel_programs == LIBRARY, result.karel_programs
    return result


def kept(result) -> dict[str, int]:
    """kpM1... CROSSARM.FRAME -> the PR CrossArm keeps it in; kpDone -> its R."""
    found = {a.rapid_name.upper(): a.number for a in result.point_registers}
    found["KPDONE"] = next(a.number for a in result.registers if a.rapid_name == "kpDone")
    return found


def prep_program(numbers: dict[str, int]) -> Program:
    """KPPREP: the registers CrossArm keeps poses in made Cartesian first (another probe may leave joints there)."""
    lines = ["UFRAME_NUM=0", "UTOOL_NUM=1"] + [f"PR[{k}]=LPOS" for name, k in sorted(numbers.items()) if name != "KPDONE"]
    return _program("KPPREP", lines, "KAREL pose probe prep")


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="crossarm_karelpose_") as temp:
        result = conversion(Path(temp))
        for name in (CONV, "SETUP_FRAMES"):
            (PROBE / f"{name}.LS").write_bytes((Path(temp) / f"{name}.LS").read_bytes())
    for program in [*raw_programs(), prep_program(kept(result))]:
        (PROBE / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
        print(f"{program.name}.LS")
    for name, number in kept(result).items():
        print(f"  {'R' if name == 'KPDONE' else 'PR'}[{number}] {name}")
    print(f"probe written to {PROBE}")


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------


def config_of(posreg: str, number: int) -> str:
    block = re.search(rf"\[1,{number}\] =[^\n]*\n\s*Group: \d+\s+Config: ([^\n]*)", posreg)
    return block[1].strip().replace(" ", "") if block else "missing"


def measure() -> dict[str, str]:
    import make_maketp_probe
    import roboguide

    write()
    with tempfile.TemporaryDirectory(prefix="crossarm_karelpose_") as temp:
        numbers = kept(conversion(Path(temp)))
    names = [RAW, *ERRORS, "KPPREP", "SETUP_FRAMES", CONV]
    pcs = [name.lower() for name in LIBRARY]
    found: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="crossarm_karelpose_") as temp:
        work = Path(temp)
        out = export(LIBRARY, work, KarelRequest(make_maketp_probe.robot()), log=print)
        if len(out.compiled) != len(LIBRARY):
            raise RuntimeError(f"library not compiled: {out.problem or out.refused}")
        found["version"] = out.version
        for name in names:
            roboguide.release(name)
        roboguide.select()
        for name in names:
            _ftp(f"DELE {name.lower()}.tp")
        try:
            for name in pcs:
                found[f"{name}_load"] = _ftp("STOR", work / f"{name}.pc") or "loaded"
            # 1. By hand: each program, its values.
            found["raw_load"] = roboguide.load(PROBE / f"{RAW}.LS") or "loaded"
            roboguide.zero([DONE])
            found["raw_run"] = roboguide.run(RAW, 90)
            found["raw_done"] = f"{roboguide.numreg().get(DONE, float('nan')):g}"
            posreg = roboguide.page("md/POSREG.VA")
            for register in [*INPUTS, *CALLS]:
                found[f"PR{register}"] = read_pr(posreg, register)
            roboguide.release(RAW)
            # 2. The error cases.
            for program, (_call, code, flag) in ERRORS.items():
                found[f"{program}_load"] = roboguide.load(PROBE / f"{program}.LS") or "loaded"
                roboguide.zero([flag])
                before = roboguide._alarms() or set()
                found[f"{program}_run"] = roboguide.run(program, 60)
                found[f"{program}_alarm"] = alarm(roboguide.page("md/ERRALL.LS"), code, before)
                found[f"{program}_after"] = f"{roboguide.numreg().get(flag, float('nan')):g}"
                roboguide.release(program)
            # 3. Converted: the frames as saved (SETUP_FRAMES), then the program.
            for name in ("KPPREP", "SETUP_FRAMES", CONV):
                found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
            found["KPPREP_run"] = roboguide.run("KPPREP", 60)
            found["SETUP_FRAMES_run"] = roboguide.run("SETUP_FRAMES", 60, resumes=1)
            roboguide.zero([numbers["KPDONE"]])
            found["conv_run"] = roboguide.run(CONV, 180)
            found["conv_done"] = f"{roboguide.numreg().get(numbers['KPDONE'], float('nan')):g}"
            posreg = roboguide.page("md/POSREG.VA")
            for name in ("KPM1", "KPM2", "KPM3", "KPTURN", "CROSSARM.FRAME", *(s.upper() for s in SEEN)):
                found[name] = read_pr(posreg, numbers[name])
            for name in ("KPM2", "KPTURN"):
                found[f"{name}_config"] = config_of(posreg, numbers[name])
            return found
        finally:
            roboguide.select()
            for name in names:
                roboguide.release(name)
            roboguide.select()
            for name in names:
                _ftp(f"DELE {name.lower()}.tp")
            for name in pcs:
                _ftp(f"DELE {name}.pc")
                _ftp(f"DELE {name}.vr")


def gap(found: str, expected: tuple) -> tuple[float, float]:
    """(mm, deg) between a PR read and a pose."""
    numbers = [float(v) for v in found.split()]
    t, q = expected
    dot = abs(_dot(q_unit(q_from_wpr(*numbers[3:])), q))
    return math.dist(numbers[:3], t), math.degrees(2 * math.acos(min(1.0, dot)))


def expected_conv(found: dict[str, str]) -> dict[str, tuple]:
    """Where RAPID puts the flange after each move, from the points the robot read (kpM1...): the work object
    DefFrame makes of them, RelTool of kpM2, the tool PoseMult(kpTool.tframe, PoseInv(kpCor)) makes."""
    measured = [pose(tuple(float(v) for v in found[f"KPM{i}"].split())) for i in (1, 2, 3)]
    frame = def_frame(*(m[0] for m in measured), 3)
    m1 = measured[0][0]
    cor = ((m1[0] - TARGETS[0][0], m1[1] - TARGETS[0][1] + SHIFT[1], 0.0), (1.0, 0.0, 0.0, 0.0))
    tool = pose_mult((BASE[0], q_unit(BASE[1])), pose_inv(cor))
    return {
        "CROSSARM.FRAME": tool,  # the last frame worked out: the tool's
        "KPF1": pose_mult(frame, (IN_WOBJ[0], q_unit(IN_WOBJ[1]))),
        "KPTURN": rel_tool(measured[1], TURN[0], rz=TURN[1]),
        "KPF2": rel_tool(measured[1], TURN[0], rz=TURN[1]),
        "KPF3": pose_mult((TARGETS[0], q_unit(DOWN)), pose_inv(tool)),
    }


def verdict(found: dict[str, str]) -> str:
    wrong = []
    loads = [f"{n}: {found.get(f'{n.lower()}_load')}" for n in LIBRARY if found.get(f"{n.lower()}_load") != "loaded"]
    wrong += loads
    if found.get("raw_load") != "loaded" or found.get("raw_run") != "done" or found.get("raw_done") != "1":
        wrong.append(f"{RAW}: {found.get('raw_load')}, {found.get('raw_run')}, done {found.get('raw_done')}")
    for register, expected in expected_raw().items():
        value = found.get(f"PR{register}", "missing")
        if value == "missing":
            wrong.append(f"PR[{register}] not read")
            continue
        mm, deg = gap(value, expected)
        if mm > 0.01 or deg > 0.01:
            wrong.append(f"PR[{register}] {value}: {mm:.3f} mm, {deg:.3f} deg from RAPID ({CALLS[register]})")
    for program, (_call, code, _flag) in ERRORS.items():
        if not found.get(f"{program}_alarm", "").startswith(code) or found.get(f"{program}_after") != "0":
            wrong.append(f"{program}: {found.get(f'{program}_run')}, {found.get(f'{program}_alarm')},"
                         f" line after {found.get(f'{program}_after')}")  # fmt: skip
    runs = [f"{n} {found.get(f'{n}_load')} {found.get(f'{n}_run')}" for n in ("KPPREP", "SETUP_FRAMES")
            if found.get(f"{n}_load") != "loaded" or found.get(f"{n}_run") != "done"]  # fmt: skip
    wrong += runs
    if found.get(f"{CONV}_load") != "loaded" or found.get("conv_run") != "done" or found.get("conv_done") != "1":
        wrong.append(f"{CONV}: {found.get(f'{CONV}_load')}, {found.get('conv_run')}, done {found.get('conv_done')}")
        return "; ".join(wrong)
    for i, target in enumerate(TARGETS, 1):  # the points read where the robot was sent
        mm, _ = gap(found[f"KPM{i}"], (target, q_unit(DOWN)))
        if mm > 0.01:
            wrong.append(f"kpM{i} {found[f'KPM{i}']}: {mm:.3f} mm from kpT{i}")
    for name, expected in expected_conv(found).items():
        mm, deg = gap(found[name], expected)
        if mm > 0.01 or deg > 0.01:
            wrong.append(f"{name} {found[name]}: {mm:.3f} mm, {deg:.3f} deg from RAPID")
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    worst = max(gap(found[f"PR{r}"], e)[0] for r, e in expected_raw().items())
    moved = max(gap(found[n], e)[0] for n, e in expected_conv(found).items())
    return (f"compiled for {found.get('version')}; PoseInv, RelTool, DefFrame in PR within {worst:.3f} mm;"
            f" {len(ERRORS)} error cases abort on the CALL; converted: DefFrame -> UFRAME, PoseMult/PoseInv ->"
            f" UTOOL, RelTool of a point read, moves within {moved:.3f} mm")  # fmt: skip


def run() -> str:
    found = measure()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text("".join(f"{k} {v}\n" for k, v in found.items()), encoding="ascii")
    print(RESULT.read_text(encoding="ascii"))
    return check()


def stored() -> dict[str, str]:
    return dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())


def check() -> str:
    found = stored()
    problem = verdict(found)
    print(f"FAIL {problem}" if problem else f"karelpose probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
