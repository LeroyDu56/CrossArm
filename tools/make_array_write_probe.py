# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the probe of arrays the programs write: arrays of numbers kept in blocks of registers,
written at a fixed index (R[base+k]) and at an index only known at run time (R[R[n]]).

ArrayWriteProbe.mod fills a VAR array of 3 x 4 in two FOR loops (awGrid{i,j}:=i*10+j) in a routine of its
own, sums it in another, changes a PERS array at a fixed index, from another element, with Incr, and at an
index worked out (awTable{k+1}:=awTable{k}*2), then reads elements back at fixed indices. Each result is a
number: the converted programs must give the totals RobotStudio gives.

  ABB (RobotStudio): PROC Probe runs AwProbe and writes the totals to HOME:/arraywriteprobe.txt.
  FANUC (ROBOGUIDE): the converted AWPROBE runs; totals from NUMREG.VA.

Usage:  python tools/make_array_write_probe.py write    ArrayWriteProbe.mod and the .LS in tests/fixtures/probes/arraywrite
        python tools/make_array_write_probe.py run      RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_array_write_probe.py check    compare the stored results
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

PROBE = ROOT / "tests" / "fixtures" / "probes" / "arraywrite"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "arraywriteprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "arraywriteprobe_roboguide.txt"
PROGRAM = "AWPROBE"
ROUTINES = ["AwProbe", "AwFill", "AwAdd"]
TOTALS = ("awSum", "awCheck", "awFixed", "awCorners", "awSecond")

MODULE = "\r\n".join([
    "MODULE ArrayWriteProbe",
    "    ! CrossArm - probe of arrays the programs write: see tools/make_array_write_probe.py.",
    "    VAR num awGrid{3,4};",
    "    PERS num awTable{5}:=[10,20,30,40,50];",
    "    VAR num awK:=0;",
    *[f"    VAR num {total}:=0;" for total in TOTALS],
    "",
    "    PROC AwFill()",
    "        FOR i FROM 1 TO 3 DO",
    "            FOR j FROM 1 TO 4 DO",
    "                awGrid{i,j}:=i*10+j;",
    "            ENDFOR",
    "        ENDFOR",
    "    ENDPROC",
    "",
    "    PROC AwAdd()",
    "        FOR i FROM 1 TO 3 DO",
    "            FOR j FROM 1 TO 4 DO",
    "                awSum:=awSum+awGrid{i,j};",
    "            ENDFOR",
    "        ENDFOR",
    "    ENDPROC",
    "",
    "    PROC AwProbe()",
    *[f"        {total}:=0;" for total in TOTALS],
    *[f"        awTable{{{k}}}:={10 * k};" for k in range(1, 6)],
    "        AwFill;",
    "        AwAdd;",
    "        awTable{2}:=awTable{2}+awTable{5};",
    "        Incr awTable{3};",
    "        awK:=4;",
    "        awTable{awK+1}:=awTable{awK}*2;",
    "        awCheck:=awTable{1}+awTable{2}+awTable{3}+awTable{4}+awTable{5};",
    "        awFixed:=awGrid{2,3};",
    "        awCorners:=awGrid{3,4}+awGrid{1,1};",
    "        awK:=2;",
    "        awSecond:=awGrid{awK,awK+2}+awTable{awK};",
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        VAR num v;",
    "        AwProbe;",
    '        Open "HOME:" \\File:="arraywriteprobe.txt", file \\Write;',
    # through a copy: CrossArm takes Write for an instruction that may change what it is given
    *[line for total in TOTALS for line in (f"        v:={total};", f'        Write file, "{total} " \\Num:=v;')],
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# Worked out by hand: the grid holds i*10+j, 270 in all; the table 10, 20+50, 30+1, 40, 40*2: 231; awGrid{2,3}
# 23; 34+11; awGrid{2,4}+awTable{2}: 24+70.
EXPECTED = {"awSum": 270, "awCheck": 231, "awFixed": 23, "awCorners": 45, "awSecond": 94}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="ArrayWriteProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=ROUTINES,
                     sources={"ArrayWriteProbe": MODULE})  # fmt: skip
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
    (PROBE / "ArrayWriteProbe.mod").write_bytes(MODULE.encode("ascii"))
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
    print(f"RobotStudio: {robotstudio.run(PROBE / 'ArrayWriteProbe.mod', 'Probe', 180, home)}")
    ABB_RESULT.write_text((home / "arraywriteprobe.txt").read_text(encoding="utf-8", errors="replace"),
                          encoding="utf-8")  # fmt: skip
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
