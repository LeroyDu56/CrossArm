# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the probe of points passed by reference: a routine changing the robtarget it is given
(VAR, INOUT), which the caller reads back after the CALL.

PointRefProbe.mod moves to a point, shifts it twice by a routine taking it as VAR robtarget (which offsets
it and moves there), lowers it in a routine taking it as INOUT robtarget which passes it on to the first,
and reads its x, y and z back. The converted programs must give the values RobotStudio gives, after the
moves.

  ABB (RobotStudio): PROC Probe runs PrProbe and writes the totals to HOME:/pointrefprobe.txt.
  FANUC (ROBOGUIDE): the converted PRPROBE runs; totals from NUMREG.VA.

Usage:  python tools/make_point_ref_probe.py write    PointRefProbe.mod and the .LS in tests/fixtures/probes/pointref
        python tools/make_point_ref_probe.py run      RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_point_ref_probe.py check    compare the stored results
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "pointref"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "pointrefprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "pointrefprobe_roboguide.txt"
PROGRAM = "PRPROBE"
ROUTINES = ["PrProbe", "PrShift", "PrLift"]
TOTALS = ("prY1", "prY2", "prZ", "prX", "prSteps")
NINES = "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]"

MODULE = "\r\n".join([
    "MODULE PointRefProbe",
    "    ! CrossArm - probe of points passed by reference: see tools/make_point_ref_probe.py.",
    # flange down in front of either robot, tool0 in the world: reached by the IRB 6700 and the R-1000iA
    f"    CONST robtarget prStart:=[[1100,50,1000],[0,1,0,0],[0,0,0,0],{NINES}];",
    f"    CONST jointtarget prHome:=[[0,0,0,0,-90,0],{NINES}];",
    "    VAR robtarget prCur;",
    *[f"    VAR num {total}:=0;" for total in TOTALS],
    "",
    "    PROC PrShift(VAR robtarget pAt)",
    "        pAt:=Offs(pAt,0,50,0);",
    "        MoveL pAt,v400,fine,tool0;",
    "        Incr prSteps;",
    "    ENDPROC",
    "",
    "    PROC PrLift(INOUT robtarget pAt,num nDown)",
    "        pAt.trans.z:=pAt.trans.z-nDown;",
    "        PrShift pAt;",
    "    ENDPROC",
    "",
    "    PROC PrProbe()",
    *[f"        {total}:=0;" for total in TOTALS],
    "        MoveAbsJ prHome,v1000,fine,tool0;",
    "        prCur:=prStart;",
    "        MoveJ prCur,v1000,fine,tool0;",
    "        PrShift prCur;",
    "        PrShift prCur;",
    "        prY1:=prCur.trans.y;",
    "        PrLift prCur,100;",
    "        prY2:=prCur.trans.y;",
    "        prZ:=prCur.trans.z;",
    "        prX:=prCur.trans.x;",
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        VAR num v;",
    "        ConfJ\\Off;",
    "        ConfL\\Off;",
    "        PrProbe;",
    '        Open "HOME:" \\File:="pointrefprobe.txt", file \\Write;',
    # through a copy: CrossArm takes Write for an instruction that may change what it is given
    *[line for total in TOTALS for line in (f"        v:={total};", f'        Write file, "{total} " \\Num:=v;')],
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# Worked out by hand: y 50, then +50 twice (150); 100 lower and +50 (200, z 900); x as it was; three shifts.
EXPECTED = {"prY1": 150, "prY2": 200, "prZ": 900, "prX": 1100, "prSteps": 3}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="PointRefProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=ROUTINES,
                     sources={"PointRefProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """Probe total -> the R[n] CrossArm gave it."""
    numbers = {a.rapid_name.upper(): a.number for a in result.registers}
    return {total: numbers[total.upper()] for total in EXPECTED}


def programs() -> dict[str, str]:
    return {info.program.name: write_ls(info.program) for info in conversion().programs}


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    for stale in PROBE.glob("*.LS"):
        stale.unlink()
    (PROBE / "PointRefProbe.mod").write_bytes(MODULE.encode("ascii"))
    for name, text in programs().items():
        (PROBE / f"{name}.LS").write_bytes(text.encode("ascii"))
        print(f"{name}.LS")
    for total, number in registers(conversion()).items():
        print(f"  R[{number}] {total} expected {EXPECTED[total]}")


def read_totals(text: str) -> dict[str, str]:
    totals = {}
    for line in text.splitlines():
        if line.strip():
            name, _, value = line.partition(" ")
            totals[name] = value.strip()
    return totals


def run() -> None:
    import roboguide
    import robotstudio

    write()
    RESULTS.mkdir(parents=True, exist_ok=True)
    home = robotstudio.home()
    print(f"RobotStudio: {robotstudio.run(PROBE / 'PointRefProbe.mod', 'Probe', 180, home)}")
    ABB_RESULT.write_text((home / "pointrefprobe.txt").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    names = list(programs())
    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)  # a copy from an earlier run: FTP does not replace it
        except Exception:  # noqa: BLE001, S110 - not there
            pass
    for name in names:
        print(f"ROBOGUIDE load {name}: {roboguide.load(PROBE / f'{name}.LS') or 'loaded'}")
    numbers = registers(conversion())
    print(f"ROBOGUIDE zero: {roboguide.zero(list(numbers.values()))}")
    print(f"ROBOGUIDE run {PROGRAM}: {roboguide.run(PROGRAM, 180)}")
    values = roboguide.numreg()
    FANUC_RESULT.write_text("".join(f"{total} {values.get(number, float('nan')):g}\n"
                                    for total, number in numbers.items()), encoding="utf-8")  # fmt: skip
    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)
        except Exception:  # noqa: BLE001, S110
            pass
    check()


def check() -> bool:
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    ok = True
    for total, expected in EXPECTED.items():
        same = float(abb.get(total, "nan")) == float(fanuc.get(total, "nan")) == expected
        ok &= same
        print(f"{total:10s} RobotStudio {abb.get(total)}  ROBOGUIDE {fanuc.get(total)}  expected {expected}  "
              f"{'ok' if same else 'DIFFERENT'}")  # fmt: skip
    return ok


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
