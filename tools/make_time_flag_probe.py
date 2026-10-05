# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the time flag probe: waits with \\MaxTime and \\TimeFlag, which set a bool when the time
runs out instead of raising an error.

TimeFlagProbe.mod waits on a bool no one sets (the time runs out: the flag TRUE), then on one already TRUE
(the flag FALSE), and times each wait with a clock. The converted programs must give the flags RobotStudio
gives, and wait about as long (the FANUC polls a TIMER).

  ABB (RobotStudio): PROC Probe runs TfProbe and writes the results to HOME:/timeflagprobe.txt.
  FANUC (ROBOGUIDE): the converted TFPROBE runs; results from NUMREG.VA.

Usage:  python tools/make_time_flag_probe.py write    TimeFlagProbe.mod and the .LS in tests/fixtures/probes/timeflag
        python tools/make_time_flag_probe.py run      RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_time_flag_probe.py check    compare the stored results
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

PROBE = ROOT / "tests" / "fixtures" / "probes" / "timeflag"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "timeflagprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "timeflagprobe_roboguide.txt"
PROGRAM = "TFPROBE"
ROUTINES = ["TfProbe"]
TOTALS = ("tfLate1", "tfLate2", "tfTime1", "tfTime2")

MODULE = "\r\n".join([
    "MODULE TimeFlagProbe",
    "    ! CrossArm - time flag probe: see tools/make_time_flag_probe.py.",
    "    VAR bool tfNever;",
    "    VAR bool tfReady;",
    "    VAR bool tfLate;",
    "    VAR clock tfClock;",
    *[f"    VAR num {total}:=0;" for total in TOTALS],
    "",
    "    PROC TfProbe()",
    *[f"        {total}:=0;" for total in TOTALS],
    "        tfNever:=FALSE;",
    "        tfReady:=TRUE;",
    "        ClkReset tfClock;",
    "        ClkStart tfClock;",
    "        WaitUntil tfNever\\MaxTime:=1.5\\TimeFlag:=tfLate;",
    "        ClkStop tfClock;",
    "        tfTime1:=ClkRead(tfClock);",
    "        IF tfLate tfLate1:=1;",
    "        ClkReset tfClock;",
    "        ClkStart tfClock;",
    "        WaitUntil tfReady\\MaxTime:=1.5\\TimeFlag:=tfLate;",
    "        ClkStop tfClock;",
    "        tfTime2:=ClkRead(tfClock);",
    "        IF tfLate tfLate2:=1;",
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        VAR num v;",
    "        TfProbe;",
    '        Open "HOME:" \\File:="timeflagprobe.txt", file \\Write;',
    # through a copy: CrossArm takes Write for an instruction that may change what it is given
    *[line for total in TOTALS for line in (f"        v:={total};", f'        Write file, "{total} " \\Num:=v;')],
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# The first wait runs out (the flag TRUE), the second does not (FALSE).
EXPECTED = {"tfLate1": 1, "tfLate2": 0}
TIMES = {"tfTime1": 1.5, "tfTime2": 0.0}  # seconds, within 0.15 s: WaitUntil checks every 0.1 s (\PollRate)


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="TimeFlagProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=ROUTINES,
                     sources={"TimeFlagProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """Probe total -> the R[n] CrossArm gave it."""
    numbers = {a.rapid_name.upper(): a.number for a in result.registers}
    return {total: numbers[total.upper()] for total in TOTALS}


def programs() -> dict[str, str]:
    return {info.program.name: write_ls(info.program) for info in conversion().programs}


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    for stale in PROBE.glob("*.LS"):
        stale.unlink()
    (PROBE / "TimeFlagProbe.mod").write_bytes(MODULE.encode("ascii"))
    for name, text in programs().items():
        (PROBE / f"{name}.LS").write_bytes(text.encode("ascii"))
        print(f"{name}.LS")
    for total, number in registers(conversion()).items():
        print(f"  R[{number}] {total}")


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
    print(f"RobotStudio: {robotstudio.run(PROBE / 'TimeFlagProbe.mod', 'Probe', 180, home)}")
    ABB_RESULT.write_text((home / "timeflagprobe.txt").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
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
    for total, expected in TIMES.items():
        a, b = float(abb.get(total, "nan")), float(fanuc.get(total, "nan"))
        near = abs(a - expected) <= 0.15 and abs(b - expected) <= 0.15
        ok &= near
        print(f"{total:10s} RobotStudio {a:.3f} s  ROBOGUIDE {b:.3f} s  expected {expected} s  {'ok' if near else 'DIFFERENT'}")
    return ok


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
