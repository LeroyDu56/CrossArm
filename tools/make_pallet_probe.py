# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the pallet probe: points the programs work out at run time go where the moves written out go.

PROC PalletProbe of PalletProbe.mod places parts the way palletizing programs do: in two FOR loops,
pPlace:=Offs(pOrigin, (c-1)*LENGTH+nShift{k}, ...) from the loop counters, a calculation of several
operations and an array; on the second layer the part is turned, pPlace:=RelTool(pPlace,0,0,0\\Rz:=90);
an approach above it with Offs(), then the place itself, then a move to Offs() of the corner by the
counters written in the move. Then it reads where the robot is, CRobT(),
moves that point's x and goes above it. CrossArm keeps pPlace and pSeen in position registers: PR[k]=P[j]
from the corner, the offsets added component by component (the calculation one operation per line in
scratch registers), the turn written as W, P, R (the orientation known at conversion time), PR[k]=LPOS
for CRobT(), PR[k,1]=PR[k,1]+15. PROC PalletDirect makes the same moves with the points written out.

On ROBOGUIDE, PALPROBE sets the frames as SETUP_FRAMES does, runs both, and records the faceplate after
every move in the world frame (make_point_probe.measured): the first run in PR[1..], the direct one in
PR[21..]. Move by move they must be the same pose.

Usage:  python tools/make_pallet_probe.py write     PalletProbe.mod and the .LS in tests/fixtures/probes/pallet
        python tools/make_pallet_probe.py run       ROBOGUIDE; the measured poses stored
        python tools/make_pallet_probe.py check     compare the stored poses
"""

import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_point_probe import COUNTER, measured
from make_pose_probe import HOME_JOINTS, ZERO_TOOL, read_posreg

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.convert.setup import build_setup
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, JointPosition, Motion, Position, Program
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "pallet"
RESULT = PROBE / "results" / "palletprobe_roboguide.txt"
PROGRAM = "PALPROBE"
PASSED_PR, DIRECT_PR = 1, 21
MOVES = 13
ZERO_PR = 49
LENGTH, WIDTH, HEIGHT, SHIFT = 90, 20, 25, (0, 30)
W = "tProbe\\WObj:=wProbe;"
NINES = "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]"


def _direct() -> list[str]:
    lines = []
    last = ""
    for k in (1, 2):
        for c in (1, 2):
            point = f"Offs(pOrigin,{(c - 1) * LENGTH + SHIFT[k - 1]},{(k - 1) * WIDTH},{(k - 1) * HEIGHT})"
            if k == 2:
                point = f"RelTool({point},0,0,0\\Rz:=90)"
            lines += [f"MoveL Offs({point},0,0,40),v500,fine,{W}", f"MoveL {point},v200,fine,{W}",
                      f"MoveL Offs(pOrigin,{c * LENGTH},{k * WIDTH},60),v500,fine,{W}"]
            last = f"Offs(pOrigin,{c * LENGTH},{k * WIDTH},60)"  # where the robot is when CRobT reads it
    lines.append(f"MoveL Offs(Offs({last},15,0,0),0,10,30),v200,fine,{W}")
    return lines


MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE PalletProbe",
    "    ! CrossArm - pallet probe: see tools/make_pallet_probe.py.",
    "    PERS tooldata tProbe:=[TRUE,[[10,-5,120],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];",
    "    PERS wobjdata wProbe:=[FALSE,TRUE,\"\",[[1100,-150,650],[0.996195,0,0,0.087156]],[[0,0,0],[1,0,0,0]]];",
    f"    CONST robtarget pOrigin:=[[40,-40,230],[0,1,0,0],[0,0,0,0],{NINES}];",
    f"    CONST num LENGTH:={LENGTH};",
    f"    CONST num WIDTH:={WIDTH};",
    f"    CONST num HEIGHT:={HEIGHT};",
    f"    CONST num nShift{{2}}:=[{SHIFT[0]},{SHIFT[1]}];",
    "    VAR robtarget pPlace;",
    "    VAR robtarget pSeen;",
    "",
    "    PROC PalletProbe()",
    "        FOR k FROM 1 TO 2 DO",
    "            FOR c FROM 1 TO 2 DO",
    "                pPlace:=Offs(pOrigin,(c-1)*LENGTH+nShift{k},(k-1)*WIDTH,(k-1)*HEIGHT);",
    "                IF k=2 pPlace:=RelTool(pPlace,0,0,0\\Rz:=90);",
    f"                MoveL Offs(pPlace,0,0,40),v500,fine,{W}",
    f"                MoveL pPlace,v200,fine,{W}",
    f"                MoveL Offs(pOrigin,c*LENGTH,k*WIDTH,60),v500,fine,{W}",
    "            ENDFOR",
    "        ENDFOR",
    "        pSeen:=CRobT(\\Tool:=tProbe\\WObj:=wProbe);",
    "        pSeen.trans.x:=pSeen.trans.x+15;",
    f"        MoveL Offs(pSeen,0,10,30),v200,fine,{W}",
    "    ENDPROC",
    "",
    "    PROC PalletDirect()",
    *[f"        {line}" for line in _direct()],
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip


def conversion() -> tuple[ConversionResult, ConversionConfig]:
    parsed = parse_text(MODULE, path="PalletProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    result = convert([parsed.module], config, routines=["PalletProbe", "PalletDirect"], sources={"PalletProbe": MODULE})
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    return result, config


def programs() -> dict[str, str]:
    """PALPROBE (frames, a known start, both runs) and the converted programs, measured."""
    result, config = conversion()
    setup = build_setup(result, config, "SETUP_FRAMES")
    assert setup.program is not None
    positions = list(setup.program.positions)
    lines: list[Instruction | Motion] = [Instruction("!CrossArm pallet probe")]
    lines += [line for line in setup.program.lines if not line.text.startswith(("MESSAGE[", "PAUSE", "!"))]
    data = max((p.number for p in positions), default=0) + 1
    positions += [Position(data, 0, 1, CartesianPosition(0, 0, 0, 0, 0, 0)),
                  Position(data + 1, 0, ZERO_TOOL, JointPosition(HOME_JOINTS))]  # fmt: skip
    lines += [Instruction(f"PR[{ZERO_PR}]=P[{data}]"), Instruction(f"UTOOL[{ZERO_TOOL}]=PR[{ZERO_PR}]"),
              Instruction("UFRAME_NUM=0"), Instruction(f"UTOOL_NUM={ZERO_TOOL}"),
              Motion("J", f"P[{data + 1}]", "10%", "FINE"),
              Instruction(f"R[{COUNTER}]={PASSED_PR}"), Instruction("CALL PALLETPROBE"),
              Instruction(f"R[{COUNTER}]={DIRECT_PR}"), Instruction("CALL PALLETDIRECT")]  # fmt: skip
    out = {PROGRAM: write_ls(Program(PROGRAM, lines, positions, Attributes(comment="pallet probe",
                                                                           created=datetime(2026, 1, 1))))}  # fmt: skip
    for info in result.programs:
        out[info.program.name] = write_ls(measured(info.program))
    return out


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "PalletProbe.mod").write_bytes(MODULE.encode("ascii"))
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
    """(move, mm, deg of W, P, R) between the move to a point worked out at run time and the one written out."""
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
        roboguide.release(name)
        try:
            roboguide.delete(name)  # a copy from an earlier run: FTP does not replace it
        except Exception:  # noqa: BLE001, S110 - not there
            pass
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
