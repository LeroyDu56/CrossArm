# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the speed argument probe: a routine given its speed and zone as parameters
(`PROC SpdMoves(speeddata v,zonedata z)`), which is not a move wrapper: it makes three moves with them.

SpeedArgProbe.mod calls SpdMoves twice, with v400 and z50, then with a speeddata of its own (200 mm/s) and z10,
and makes the same three moves with those constants written in them; each run is timed. CrossArm passes the
speed as numbers (mm/s for the linear moves, % for the joint one) and the zone as the CNT of each move worked out
at the call: the converted routine must take the time the same moves take with constants.

  ABB (RobotStudio): PROC Probe runs SpdProbe and writes the times to HOME:/speedargprobe.txt.
  FANUC (ROBOGUIDE): the converted SPDPROBE runs; times and the count of calls from NUMREG.VA.

Usage:  python tools/make_speed_arg_probe.py forms    TP forms loaded only (AR[n] as speed and CNT), stored
        python tools/make_speed_arg_probe.py write    SpeedArgProbe.mod and the .LS in tests/fixtures/probes/speedargs
        python tools/make_speed_arg_probe.py run      RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_speed_arg_probe.py check    compare the stored results
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "speedargs"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "speedargprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "speedargprobe_roboguide.txt"
FORMS_RESULT = RESULTS / "speedargforms_roboguide.txt"
FORMS_DIR = PROBE / "forms"  # apart: probe_all loads every .LS of PROBE
PROGRAM = "SPDPROBE"
ROUTINES = ["SpdProbe", "SpdMoves"]
NINES = "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]"


def _timed(total: str, moves: list[str]) -> list[str]:
    return ["        MoveAbsJ jStart,v1000,fine,tool0;", "        ClkReset ckSpd;", "        ClkStart ckSpd;",
            *(f"        {m}" for m in moves), "        ClkStop ckSpd;", f"        {total}:=ClkRead(ckSpd);"]  # fmt: skip


MODULE = "\r\n".join([
    "MODULE SpeedArgProbe",
    "    ! CrossArm - speed argument probe: see tools/make_speed_arg_probe.py.",
    f"    CONST robtarget pA:=[[1100,50,1000],[0,1,0,0],[0,0,0,0],{NINES}];",
    f"    CONST robtarget pB:=[[1100,250,1000],[0,1,0,0],[0,0,0,0],{NINES}];",
    f"    CONST robtarget pC:=[[1100,250,800],[0,1,0,0],[0,0,0,0],{NINES}];",
    f"    CONST jointtarget jStart:=[[0,0,0,0,-90,0],{NINES}];",
    "    CONST speeddata vSpd:=[200,500,5000,1000];",
    "    VAR clock ckSpd;",
    "    VAR num nCalls:=0;",
    "    VAR num nT1:=0;",
    "    VAR num nT2:=0;",
    "    VAR num nT3:=0;",
    "    VAR num nT4:=0;",
    "",
    "    PROC SpdMoves(speeddata v,zonedata z)",
    "        MoveJ pA,v,z,tool0;",
    "        MoveL pB,v,z,tool0;",
    "        MoveL pC,v,fine,tool0;",
    "        Incr nCalls;",
    "    ENDPROC",
    "",
    "    PROC SpdProbe()",
    "        nCalls:=0;",
    *_timed("nT1", ["SpdMoves v400,z50;"]),
    *_timed("nT2", ["SpdMoves vSpd,z10;"]),
    *_timed("nT3", ["MoveJ pA,v400,z50,tool0;", "MoveL pB,v400,z50,tool0;", "MoveL pC,v400,fine,tool0;"]),
    *_timed("nT4", ["MoveJ pA,vSpd,z10,tool0;", "MoveL pB,vSpd,z10,tool0;", "MoveL pC,vSpd,fine,tool0;"]),
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        ConfJ\\Off;",
    "        ConfL\\Off;",
    "        SpdProbe;",
    '        Open "HOME:" \\File:="speedargprobe.txt", file \\Write;',
    '        Write file, "nCalls " \\Num:=nCalls;',
    '        Write file, "nT1 " \\Num:=nT1;',
    '        Write file, "nT2 " \\Num:=nT2;',
    '        Write file, "nT3 " \\Num:=nT3;',
    '        Write file, "nT4 " \\Num:=nT4;',
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

EXPECTED = {"nCalls": 2.0}
TIMES = ("nT1", "nT2", "nT3", "nT4")
PAIRS = (("nT1", "nT3"), ("nT2", "nT4"))  # the routine given v400,z50 / vSpd,z10 against the same moves written so
TOLERANCE = 0.01  # a routine given its speed and zone takes the time of the moves written with them, within 1 %

# Loaded only: what the controller accepts as a speed and a CNT given as arguments (measured before CrossArm
# writes it). No /POS: the moves go to position registers.
FORMS = {
    "SPDF_L": ["L PR[81] AR[1]mm/sec FINE"],
    "SPDF_J": ["J PR[81] AR[1]% FINE"],
    "SPDF_CNT": ["L PR[81] 400mm/sec CNT AR[1]"],
    "SPDF_JCNT": ["J PR[81] AR[1]% CNT AR[2]"],
    "SPDF_LCNT": ["L PR[81] AR[1]mm/sec CNT AR[2]"],
    "SPDF_JR": ["J PR[81] R[20]% FINE"],
    "SPDF_CALL": ["CALL SPDF_JCNT(25,40)"],
}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="SpeedArgProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=ROUTINES,
                     sources={"SpeedArgProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """Probe total -> the R[n] CrossArm gave it."""
    numbers = {a.rapid_name.upper(): a.number for a in result.registers}
    return {total: numbers[total.upper()] for total in (*EXPECTED, *TIMES)}


def forms() -> dict[str, str]:
    return {name: write_ls(Program(name, [Instruction(t) for t in lines], [],
                                   Attributes(comment="speed arg probe", created=datetime(2026, 1, 1))))
            for name, lines in FORMS.items()}  # fmt: skip


def programs() -> dict[str, str]:
    return {info.program.name: write_ls(info.program) for info in conversion().programs}


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    FORMS_DIR.mkdir(exist_ok=True)
    for stale in [*PROBE.glob("*.LS"), *FORMS_DIR.glob("*.LS")]:
        stale.unlink(missing_ok=True)
    for name, text in forms().items():
        FORMS_DIR.joinpath(f"{name}.LS").write_bytes(text.encode("ascii"))
    (PROBE / "SpeedArgProbe.mod").write_bytes(MODULE.encode("ascii"))
    for name, text in programs().items():
        PROBE.joinpath(f"{name}.LS").write_bytes(text.encode("ascii"))
        print(f"{name}.LS")
    for total, number in registers(conversion()).items():
        print(f"  R[{number}] {total} expected {EXPECTED.get(total, 'a time')}")


def _load(names: list[str], folder: Path) -> dict[str, str]:
    import roboguide

    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)  # a copy from an earlier run: FTP does not replace it
        except Exception:  # noqa: BLE001, S110 - not there
            pass
    refused = {}
    for name in names:
        refused[name] = roboguide.load(folder / f"{name}.LS")
        print(f"ROBOGUIDE load {name}: {refused[name] or 'loaded'}")
    return refused


def _unload(names: list[str]) -> None:
    import roboguide

    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)
        except Exception:  # noqa: BLE001, S110 - refused: never loaded
            pass


def run_forms() -> None:
    FORMS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    for name, text in forms().items():
        FORMS_DIR.joinpath(f"{name}.LS").write_bytes(text.encode("ascii"))
    refused = _load(list(FORMS), FORMS_DIR)
    FORMS_RESULT.write_text("".join(f"{name} {refused[name] or 'loaded'}\n" for name in FORMS), encoding="utf-8")
    _unload(list(FORMS))


def run() -> None:
    import roboguide
    import robotstudio

    write()
    RESULTS.mkdir(parents=True, exist_ok=True)
    home = robotstudio.home()
    print(f"RobotStudio: {robotstudio.run(PROBE / 'SpeedArgProbe.mod', 'Probe', 180, home)}")
    ABB_RESULT.write_text((home / "speedargprobe.txt").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    numbers = registers(conversion())
    names = list(programs())
    refused = _load(names, PROBE)
    lines = []
    if refused.get(PROGRAM) or any(refused.values()):
        lines.append(f"{PROGRAM}.refused {'; '.join(f'{k}: {v}' for k, v in refused.items() if v)}\n")
    else:
        print(f"ROBOGUIDE zero: {roboguide.zero(list(numbers.values()))}")
        print(f"ROBOGUIDE run {PROGRAM}: {roboguide.run(PROGRAM, 180)}")
        values = roboguide.numreg()
        lines += [f"{total} {values.get(number, float('nan')):g}\n" for total, number in numbers.items()]
    FANUC_RESULT.write_text("".join(lines), encoding="utf-8")
    _unload(names)
    check()


def read_totals(text: str) -> dict[str, str]:
    totals = {}
    for line in text.splitlines():
        if line.strip():
            name, _, value = line.partition(" ")
            totals[name] = value.strip()
    return totals


def check() -> bool:
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    ok = True
    for total, expected in EXPECTED.items():
        got = fanuc.get(total)
        same = float(abb.get(total, "nan")) == float(got or "nan") == expected
        ok &= same
        print(f"{total:8s} RobotStudio {abb.get(total)}  ROBOGUIDE {got}  expected {expected:g}  "
              f"{'ok' if same else 'DIFFERENT'}")  # fmt: skip
    for given, written in PAIRS:
        for side, values in (("RobotStudio", abb), ("ROBOGUIDE", fanuc)):
            a, b = float(values.get(given, "nan")), float(values.get(written, "nan"))
            same = abs(a - b) <= TOLERANCE * b
            ok &= same
            print(f"{side:11s} {given} {a:.3f} s (arguments)  {written} {b:.3f} s (constants)  {'ok' if same else 'DIFFERENT'}")
    for total in TIMES:
        a, b = float(abb.get(total, "nan")), float(fanuc.get(total) or "nan")
        print(f"{total:4s} RobotStudio {a:.3f} s  ROBOGUIDE {b:.3f} s  ({100 * (b - a) / a:+.0f} %)")
    if FORMS_RESULT.exists():
        for name, outcome in read_totals(FORMS_RESULT.read_text(encoding="utf-8")).items():
            print(f"{name:10s} {outcome}")
    return ok


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"forms": run_forms, "write": write, "run": run, "check": check}[command]()
