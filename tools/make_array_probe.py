# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the array probe: do arrays of numbers indexed at run time give what RAPID reads?

PROC ArrProbe of ArrayProbe.mod reads a CONST table of decimals and negatives and a CONST 2 x 3 table in
FOR loops, in sums, in IF conditions, as a routine's arguments and in a WHILE whose index the loop
changes, plus a PERS table no program changes; each read adds its own weight to nSum, nCalls or nHits,
so a wrong element shows in the totals.

  ABB (RobotStudio): PROC Probe runs ArrProbe and writes the totals to HOME:/arrayprobe.txt.
  FANUC (ROBOGUIDE): ARRPROBE_RUN sets the tables in their registers as SETUP_FRAMES does, then runs the
      converted ARRPROBE; the totals are read from NUMREG.VA.

Usage:  python tools/make_array_probe.py write     ArrayProbe.mod and the .LS in tests/fixtures/probes/arrays
        python tools/make_array_probe.py run       RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_array_probe.py check     compare the stored results
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.convert.setup import build_setup
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "arrays"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "arrayprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "arrayprobe_roboguide.txt"
PROGRAM = "ARRPROBE"
RUNNER = "ARRPROBE_RUN"

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE ArrayProbe",
    "    ! CrossArm - array probe: see tools/make_array_probe.py. PROC ArrProbe is what CrossArm converts;",
    "    ! PROC Probe runs it in RobotStudio and writes the totals to HOME:/arrayprobe.txt.",
    "    CONST num FEED{4}:=[1.5,-2,0.25,10];",
    "    CONST num GRID{2,3}:=[[1,2,3],[40,50,60]];",
    "    PERS num LIMIT{3}:=[5,-5,100];",
    "    VAR num nSum:=0;",
    "    VAR num nCalls:=0;",
    "    VAR num nHits:=0;",
    "    VAR num k:=0;",
    "",
    "    PROC ArrProbe()",
    "        nSum:=0;",
    "        nCalls:=0;",
    "        nHits:=0;",
    "        FOR i FROM 1 TO 4 DO",
    "            nSum:=nSum+FEED{i};",
    "            IF FEED{i}<0 nHits:=nHits+1;",
    "        ENDFOR",
    "        FOR r FROM 1 TO 2 DO",
    "            FOR c FROM 1 TO 3 DO",
    "                nSum:=nSum+GRID{r,c};",
    "                Weigh GRID{r,c},FEED{c};",
    "            ENDFOR",
    "        ENDFOR",
    "        k:=1;",
    "        WHILE LIMIT{k}>0 DO",
    "            nHits:=nHits+10;",
    "            k:=k+1;",
    "        ENDWHILE",
    "        nSum:=nSum+LIMIT{k};",
    "    ENDPROC",
    "",
    "    PROC Weigh(num a,num b)",
    "        nCalls:=nCalls+a;",
    "        IF b>1 nHits:=nHits+100;",
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        ArrProbe;",
    '        Open "HOME:" \\File:="arrayprobe.txt", file \\Write;',
    '        Write file, "nSum " \\Num:=nSum;',
    '        Write file, "nCalls " \\Num:=nCalls;',
    '        Write file, "nHits " \\Num:=nHits;',
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# Worked out by hand, and what RobotStudio computes (results/arrayprobe_robotstudio.txt):
# FEED sums to 9.75 with one negative; GRID sums to 156; Weigh adds each GRID element (156) and 100 when
# FEED{c} > 1: FEED{1} = 1.5, twice (r = 1, 2); the WHILE stops at LIMIT{2} = -5 after one turn (10), and
# adds it: nSum = 9.75 + 156 - 5.
EXPECTED = {"nSum": 160.75, "nCalls": 156.0, "nHits": 211.0}


def conversion() -> tuple[ConversionResult, ConversionConfig]:
    parsed = parse_text(MODULE, path="ArrayProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    result = convert([parsed.module], config, routines=["ArrProbe", "Weigh"], sources={"ArrayProbe": MODULE})
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    return result, config


def registers(result: ConversionResult) -> dict[str, int]:
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def programs() -> dict[str, str]:
    """The runner (the tables as SETUP_FRAMES sets them, then the probe) and the converted programs."""
    result, config = conversion()
    setup = build_setup(result, config, "SETUP_FRAMES")
    assert setup.program is not None
    lines = [line for line in setup.program.lines if line.text.startswith(("R[", "!"))]
    lines.append(Instruction(f"CALL {PROGRAM}"))
    out = {RUNNER: write_ls(Program(RUNNER, lines, [], Attributes(comment="array probe", created=datetime(2026, 1, 1))))}
    for info in result.programs:
        out[info.program.name] = write_ls(info.program)
    return out


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "ArrayProbe.mod").write_bytes(MODULE.encode("ascii"))
    for name, text in programs().items():
        (PROBE / f"{name}.LS").write_bytes(text.encode("ascii"))
        print(f"{name}.LS")


def read_totals(text: str) -> dict[str, float]:
    return {line.split()[0]: float(line.split()[1]) for line in text.splitlines() if line.strip()}


def run() -> None:
    import roboguide
    import robotstudio

    write()
    RESULTS.mkdir(parents=True, exist_ok=True)
    home = robotstudio.home()
    print(f"RobotStudio: {robotstudio.run(PROBE / 'ArrayProbe.mod', 'Probe', 120, home)}")
    ABB_RESULT.write_text((home / "arrayprobe.txt").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    numbers = registers(conversion()[0])
    names = [p.stem for p in sorted(PROBE.glob("*.LS"))]
    for name in names:
        print(f"ROBOGUIDE load {name}: {roboguide.load(PROBE / f'{name}.LS') or 'loaded'}")
    print(f"ROBOGUIDE zero: {roboguide.zero(list(numbers.values()))}")
    print(f"ROBOGUIDE run: {roboguide.run(RUNNER, 120)}")
    values = roboguide.numreg()
    FANUC_RESULT.write_text("".join(f"{name} {values.get(number, float('nan')):g}\n" for name, number in numbers.items()),
                            encoding="utf-8")  # fmt: skip
    for name in names:
        roboguide.release(name)
        roboguide.delete(name)
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
