# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the select probe: does a TEST/CASE converted to SELECT take the branch RAPID takes?

PROC SelProbe of SelectProbe.mod runs TEST in the shapes RAPID programs use: several values on one
CASE, a negative value, a CASE that only calls a routine (made on the SELECT line), an empty CASE, a
DEFAULT and none, a value no CASE has, a decimal value, a TEST nested in a CASE, a TEST on a constant
(its branch kept, no SELECT) and one on a routine's argument (selected on a copy). Every branch adds
its own weight to nSum, nCalls or nPath, so a wrong branch shows in the totals.

  ABB (RobotStudio): PROC Probe runs SelProbe and writes the three totals to HOME:/selectprobe.txt.
  FANUC (ROBOGUIDE): the converted SELPROBE runs; the totals are read from NUMREG.VA.

Usage:  python tools/make_select_probe.py write     SelectProbe.mod and the .LS in tests/fixtures/probes/select
        python tools/make_select_probe.py run       RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_select_probe.py check     compare the stored results
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

PROBE = ROOT / "tests" / "fixtures" / "probes" / "select"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "selectprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "selectprobe_roboguide.txt"
PROGRAM = "SELPROBE"

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE SelectProbe",
    "    ! CrossArm - select probe: see tools/make_select_probe.py. PROC SelProbe is what CrossArm converts;",
    "    ! PROC Probe runs it in RobotStudio and writes the totals to HOME:/selectprobe.txt.",
    "    VAR num nMode:=0;",
    "    VAR num nSum:=0;",
    "    VAR num nCalls:=0;",
    "    VAR num nPath:=0;",
    "    CONST num KIND:=2;",
    "",
    "    PROC SelProbe()",
    "        nSum:=0;",
    "        nCalls:=0;",
    "        nPath:=0;",
    "        FOR i FROM -1 TO 4 DO",
    "            nMode:=i;",
    "            TEST nMode",
    "            CASE 1, 2:",
    "                nSum:=nSum+10;",
    "                nPath:=nPath+1;",
    "                TEST nMode",
    "                CASE 2:",
    "                    nPath:=nPath+10;",
    "                ENDTEST",
    "            CASE -1:",
    "                nSum:=nSum+100;",
    "            CASE 3:",
    "                SelCount;",
    "            CASE 4:",
    "            DEFAULT:",
    "                nSum:=nSum+1000;",
    "                nPath:=nPath+1;",
    "            ENDTEST",
    "        ENDFOR",
    "        nMode:=7;",
    "        TEST nMode",
    "        CASE 1:",
    "            nSum:=nSum+5;",
    "        CASE 7:",
    "            SelCount;",
    "        ENDTEST",
    "        nMode:=8;",
    "        TEST nMode",
    "        CASE 1:",
    "            nSum:=nSum+5;",
    "            nPath:=nPath+5;",
    "        ENDTEST",
    "        nMode:=2.5;",
    "        TEST nMode",
    "        CASE 2.5:",
    "            nSum:=nSum+20000;",
    "            nPath:=nPath+1;",
    "        DEFAULT:",
    "            nSum:=nSum+50000;",
    "        ENDTEST",
    "        TEST KIND",
    "        CASE 2:",
    "            nPath:=nPath+100;",
    "        DEFAULT:",
    "            nPath:=nPath+1000;",
    "        ENDTEST",
    "        SelArg 3;",
    "        SelArg 8;",
    "    ENDPROC",
    "",
    "    PROC SelCount()",
    "        nCalls:=nCalls+1;",
    "    ENDPROC",
    "",
    "    PROC SelArg(num k)",
    "        TEST k",
    "        CASE 3:",
    "            nCalls:=nCalls+10;",
    "        DEFAULT:",
    "            nCalls:=nCalls+100;",
    "        ENDTEST",
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        SelProbe;",
    '        Open "HOME:" \\File:="selectprobe.txt", file \\Write;',
    '        Write file, "nSum " \\Num:=nSum;',
    '        Write file, "nCalls " \\Num:=nCalls;',
    '        Write file, "nPath " \\Num:=nPath;',
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# Worked out by hand, and what RobotStudio computes (results/selectprobe_robotstudio.txt):
# the loop: -1 -> 100; 0 -> DEFAULT 1000, path 1; 1 -> 10, path 1; 2 -> 10, path 1 + 10 (nested);
# 3 -> a call; 4 -> nothing. Then 7 -> a call, 8 -> nothing (no DEFAULT), 2.5 -> 20000, path 1;
# KIND is 2 -> path 100; SelArg 3 -> 10 calls, SelArg 8 -> 100.
EXPECTED = {"nSum": 21120.0, "nCalls": 112.0, "nPath": 114.0}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="SelectProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)),
                     routines=["SelProbe", "SelCount", "SelArg"], sources={"SelectProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """RAPID variable -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "SelectProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    for info in result.programs:
        (PROBE / f"{info.program.name}.LS").write_bytes(write_ls(info.program).encode("ascii"))
        print(f"{info.program.name}.LS")
    for name, number in registers(result).items():
        print(f"  R[{number}] {name} expected {EXPECTED[name]:g}")


def read_totals(text: str) -> dict[str, float]:
    totals = {}
    for line in text.splitlines():
        if line.strip():
            name, value = line.split()
            totals[name] = float(value)
    return totals


def run() -> None:
    import roboguide
    import robotstudio

    write()
    RESULTS.mkdir(parents=True, exist_ok=True)
    home = robotstudio.home()
    print(f"RobotStudio: {robotstudio.run(PROBE / 'SelectProbe.mod', 'Probe', 120, home)}")
    ABB_RESULT.write_text((home / "selectprobe.txt").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    numbers = registers(conversion())
    programs = sorted(PROBE.glob("*.LS"))
    for path in programs:
        print(f"ROBOGUIDE load {path.stem}: {roboguide.load(path) or 'loaded'}")
    print(f"ROBOGUIDE zero: {roboguide.zero(list(numbers.values()))}")
    print(f"ROBOGUIDE run: {roboguide.run(PROGRAM, 120)}")
    values = roboguide.numreg()
    FANUC_RESULT.write_text("".join(f"{name} {values.get(number, float('nan')):g}\n" for name, number in numbers.items()),
                            encoding="utf-8")  # fmt: skip
    for path in programs:
        roboguide.release(path.stem)
        roboguide.delete(path.stem)
    check()


def check() -> bool:
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    ok = True
    for name, expected in EXPECTED.items():
        same = abb.get(name) == fanuc.get(name) == expected
        ok &= same
        print(f"{name:7s} RobotStudio {abb.get(name)}  ROBOGUIDE {fanuc.get(name)}  expected {expected:g}  "
              f"{'ok' if same else 'DIFFERENT'}")  # fmt: skip
    return ok


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
