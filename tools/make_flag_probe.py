# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the flag probe: bools set to a condition, kept in flags (F[n]=(R[1]<5 AND F[2]=OFF)).

FlagProbe.mod sets bools to a comparison, to comparisons joined by AND, to NOT another bool, to another
bool, to a comparison of texts joined with one of numbers, and loops on a bool it sets to a comparison at
each turn; each is tested in an IF that counts. The converted programs must give the totals RobotStudio
gives.

  ABB (RobotStudio): PROC Probe runs FpProbe and writes the totals to HOME:/flagprobe.txt.
  FANUC (ROBOGUIDE): the converted FPPROBE runs; totals from NUMREG.VA.

Usage:  python tools/make_flag_probe.py write    FlagProbe.mod and the .LS in tests/fixtures/probes/flags
        python tools/make_flag_probe.py run      RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_flag_probe.py check    compare the stored results
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

PROBE = ROOT / "tests" / "fixtures" / "probes" / "flags"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "flagprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "flagprobe_roboguide.txt"
PROGRAM = "FPPROBE"
ROUTINES = ["FpProbe"]
TOTALS = ("fpN1", "fpN2", "fpN3", "fpN4", "fpN5", "fpTurns")

MODULE = "\r\n".join([
    "MODULE FlagProbe",
    "    ! CrossArm - flag probe: see tools/make_flag_probe.py.",
    "    VAR bool fpBig;",
    "    VAR bool fpBoth;",
    "    VAR bool fpNot;",
    "    VAR bool fpCopy;",
    "    VAR bool fpText;",
    "    VAR bool fpGo;",
    "    VAR string fpState;",
    "    VAR num fpA:=0;",
    "    VAR num fpB:=0;",
    *[f"    VAR num {total}:=0;" for total in TOTALS],
    "",
    "    PROC FpProbe()",
    *[f"        {total}:=0;" for total in TOTALS],
    "        fpA:=3;",
    "        fpB:=7;",
    '        fpState:="RUN";',
    "        fpBig:=fpA<5;",
    "        fpBoth:=fpA<5 AND fpB>8;",
    "        fpNot:=NOT fpBig;",
    "        fpCopy:=fpBig;",
    '        fpText:=fpState="RUN" AND fpA=3;',
    "        IF fpBig fpN1:=1;",
    "        IF fpBoth fpN2:=1;",
    "        IF fpNot fpN3:=1;",
    "        IF fpCopy fpN4:=1;",
    "        IF fpText fpN5:=1;",
    "        fpGo:=TRUE;",
    "        WHILE fpGo DO",
    "            Incr fpTurns;",
    "            fpGo:=fpTurns<4;",
    "        ENDWHILE",
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        VAR num v;",
    "        FpProbe;",
    '        Open "HOME:" \\File:="flagprobe.txt", file \\Write;',
    # through a copy: CrossArm takes Write for an instruction that may change what it is given
    *[line for total in TOTALS for line in (f"        v:={total};", f'        Write file, "{total} " \\Num:=v;')],
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# Worked out by hand: 3<5 TRUE; 3<5 AND 7>8 FALSE; NOT TRUE; a copy of TRUE; "RUN" and 3=3 TRUE; 4 turns.
EXPECTED = {"fpN1": 1, "fpN2": 0, "fpN3": 0, "fpN4": 1, "fpN5": 1, "fpTurns": 4}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="FlagProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=ROUTINES,
                     sources={"FlagProbe": MODULE})  # fmt: skip
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
    (PROBE / "FlagProbe.mod").write_bytes(MODULE.encode("ascii"))
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
    print(f"RobotStudio: {robotstudio.run(PROBE / 'FlagProbe.mod', 'Probe', 180, home)}")
    ABB_RESULT.write_text((home / "flagprobe.txt").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
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
