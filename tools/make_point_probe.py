# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the point probe: points passed to routines or read from arrays go where the moves written out go.

PointProbe.mod makes the same twenty-eight moves twice. PROC PointProbe calls routines that take a robtarget:
PickAt approaches its point with Offs(), moves to it, leaves with another Offs(); Twice passes its own
point on, as it is and with Offs(). PROC PointDirect makes the same moves with the points written in
them. Then it walks a 2 x 2 array of points in two FOR loops, moving to each element and handing
Offs() of it to PickAt; PointDirect makes those moves with the elements at fixed indices. CrossArm
converts both: the first passes each point in a position register (PR[k]=P[j] before the CALL, L PR[k]
in the routine, Offs as component arithmetic on a copy) and reads the array from the registers
SETUP_FRAMES fills (PR[R[n]], the index worked out from the loop registers); the second is plain moves.

On ROBOGUIDE, PTPROBE sets the frames as SETUP_FRAMES does, runs both, and records the TCP after every
move (PR[R[90]]=LPOS, in the frames the move ran in): the first run in PR[1..], the direct one in
PR[31..]. Move by move they must be the same pose.

Usage:  python tools/make_point_probe.py write     PointProbe.mod and the .LS in tests/fixtures/probes/points
        python tools/make_point_probe.py run       ROBOGUIDE; the measured poses stored
        python tools/make_point_probe.py check     compare the stored poses
"""

import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_pose_probe import HOME_JOINTS, ZERO_TOOL, read_posreg

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.convert.setup import build_setup
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, JointPosition, Motion, Position, Program
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "points"
RESULT = PROBE / "results" / "pointprobe_roboguide.txt"
PROGRAM = "PTPROBE"
COUNTER = 90  # R[90]: the PR the next measurement goes in
PASSED_PR, DIRECT_PR = 1, 31
MOVES = 28
ZERO_PR = 49

DOWN = "[0,1,0,0]"
MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE PointProbe",
    "    ! CrossArm - point probe: see tools/make_point_probe.py.",
    "    PERS tooldata tProbe:=[TRUE,[[10,-5,120],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];",
    "    PERS wobjdata wProbe:=[FALSE,TRUE,\"\",[[1100,-150,650],[0.996195,0,0,0.087156]],[[0,0,0],[1,0,0,0]]];",
    f"    CONST robtarget pA:=[[60,20,250],{DOWN},[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    f"    CONST robtarget pB:=[[180,120,250],{DOWN},[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    "    CONST robtarget pGrid{2,2}:=[[" + ",".join(f"[[{x},{y},230],{DOWN},[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]]"
                                         for x, y in ((40, -40), (100, -40))) + "],["
    + ",".join(f"[[{x},{y},230],{DOWN},[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]]"
               for x, y in ((40, 60), (100, 60))) + "]];",
    "",
    "    PROC PointProbe()",
    "        PickAt pA;",
    "        PickAt Offs(pB,0,50,0);",
    "        Twice pB;",
    "        FOR r FROM 1 TO 2 DO",
    "            FOR c FROM 1 TO 2 DO",
    "                MoveL pGrid{r,c},v500,fine,tProbe\\WObj:=wProbe;",
    "                PickAt Offs(pGrid{r,c},0,0,20);",
    "            ENDFOR",
    "        ENDFOR",
    "    ENDPROC",
    "",
    "    PROC PickAt(robtarget pPick)",
    "        MoveJ Offs(pPick,0,0,40),v1000,fine,tProbe\\WObj:=wProbe;",
    "        MoveL pPick,v200,fine,tProbe\\WObj:=wProbe;",
    "        MoveL Offs(pPick,10,-20,40),v1000,fine,tProbe\\WObj:=wProbe;",
    "    ENDPROC",
    "",
    "    PROC Twice(robtarget pTwice)",
    "        PickAt pTwice;",
    "        PickAt Offs(pTwice,30,0,0);",
    "    ENDPROC",
    "",
    "    PROC PointDirect()",
    *[f"        {line}" for point in ("pA", "Offs(pB,0,50,0)", "pB", "Offs(pB,30,0,0)") for line in (
        f"MoveJ Offs({point},0,0,40),v1000,fine,tProbe\\WObj:=wProbe;",
        f"MoveL {point},v200,fine,tProbe\\WObj:=wProbe;",
        f"MoveL Offs({point},10,-20,40),v1000,fine,tProbe\\WObj:=wProbe;",
    )],
    *[f"        {line}" for r, c in ((1, 1), (1, 2), (2, 1), (2, 2)) for line in (
        f"MoveL pGrid{{{r},{c}}},v500,fine,tProbe\\WObj:=wProbe;",
        f"MoveJ Offs(Offs(pGrid{{{r},{c}}},0,0,20),0,0,40),v1000,fine,tProbe\\WObj:=wProbe;",
        f"MoveL Offs(pGrid{{{r},{c}}},0,0,20),v200,fine,tProbe\\WObj:=wProbe;",
        f"MoveL Offs(Offs(pGrid{{{r},{c}}},0,0,20),10,-20,40),v1000,fine,tProbe\\WObj:=wProbe;",
    )],
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip


def conversion() -> tuple[ConversionResult, ConversionConfig]:
    parsed = parse_text(MODULE, path="PointProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    result = convert([parsed.module], config, routines=["PointProbe", "PickAt", "Twice", "PointDirect"],
                     sources={"PointProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    return result, config


def measured(program: Program) -> Program:
    """The program with the TCP recorded after every move, in the frames the move ran in."""
    lines: list[Instruction | Motion] = []
    for line in program.lines:
        lines.append(line)
        if isinstance(line, Motion):
            lines += [Instruction(f"PR[R[{COUNTER}]]=LPOS"), Instruction(f"R[{COUNTER}]=R[{COUNTER}]+1")]
    return Program(program.name, lines, program.positions, program.attributes)


def programs() -> dict[str, str]:
    """PTPROBE (frames, a known start, both runs) and the converted programs, measured."""
    result, config = conversion()
    setup = build_setup(result, config, "SETUP_FRAMES")
    assert setup.program is not None
    positions = list(setup.program.positions)
    lines: list[Instruction | Motion] = [Instruction("!CrossArm point probe")]
    lines += [line for line in setup.program.lines if not line.text.startswith(("MESSAGE[", "PAUSE", "!"))]
    data = max((p.number for p in positions), default=0) + 1
    positions += [Position(data, 0, 1, CartesianPosition(0, 0, 0, 0, 0, 0)),
                  Position(data + 1, 0, ZERO_TOOL, JointPosition(HOME_JOINTS))]  # fmt: skip
    lines += [Instruction(f"PR[{ZERO_PR}]=P[{data}]"), Instruction(f"UTOOL[{ZERO_TOOL}]=PR[{ZERO_PR}]"),
              Instruction("UFRAME_NUM=0"), Instruction(f"UTOOL_NUM={ZERO_TOOL}"),
              Motion("J", f"P[{data + 1}]", "10%", "FINE"),
              Instruction(f"R[{COUNTER}]={PASSED_PR}"), Instruction("CALL POINTPROBE"),
              Instruction(f"R[{COUNTER}]={DIRECT_PR}"), Instruction("CALL POINTDIRECT")]  # fmt: skip
    out = {PROGRAM: write_ls(Program(PROGRAM, lines, positions, Attributes(comment="point probe",
                                                                           created=datetime(2026, 1, 1))))}  # fmt: skip
    for info in result.programs:
        out[info.program.name] = write_ls(measured(info.program))
    return out


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "PointProbe.mod").write_bytes(MODULE.encode("ascii"))
    for name, text in programs().items():
        (PROBE / f"{name}.LS").write_bytes(text.encode("ascii"))
        print(f"{name}.LS")


def poses(posreg: str) -> str:
    registers = read_posreg(posreg)
    rows = [f"{k} " + " ".join(f"{v:.3f}" for v in registers[k])
            for k in [*range(PASSED_PR, PASSED_PR + MOVES), *range(DIRECT_PR, DIRECT_PR + MOVES)] if k in registers]  # fmt: skip
    return "\n".join(rows) + "\n"


def read_poses(text: str) -> dict[int, tuple[float, ...]]:
    return {int(row.split()[0]): tuple(float(v) for v in row.split()[1:]) for row in text.splitlines() if row.strip()}


def gaps(found: dict[int, tuple[float, ...]]) -> list[tuple[int, float, float]]:
    """(move, mm, deg of W, P, R) between the move made by a routine given its point and the one written out."""
    rows = []
    for i in range(MOVES):
        a, b = found.get(PASSED_PR + i), found.get(DIRECT_PR + i)
        if a is None or b is None:
            continue
        turn = max(abs((x - y + 180) % 360 - 180) for x, y in zip(a[3:6], b[3:6], strict=True))
        rows.append((i + 1, math.dist(a[:3], b[:3]), turn))
    return rows


def run() -> None:
    import roboguide

    write()
    names = [PROGRAM, *(p.stem for p in sorted(PROBE.glob("*.LS")) if p.stem != PROGRAM)]
    for name in names:
        print(f"ROBOGUIDE load {name}: {roboguide.load(PROBE / f'{name}.LS') or 'loaded'}")
    print(f"ROBOGUIDE run: {roboguide.run(PROGRAM, 300)}")
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(poses(roboguide.page("md/POSREG.VA")), encoding="utf-8")
    for name in names:
        roboguide.release(name)
        roboguide.delete(name)
    check()


def check() -> list[tuple[int, float, float]]:
    rows = gaps(read_poses(RESULT.read_text(encoding="utf-8")))
    for move, mm, deg in rows:
        print(f"move {move:2d}: {mm:8.4f} mm  {deg:7.4f} deg")
    print(f"{len(rows)} of {MOVES} moves compared")
    return rows


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
