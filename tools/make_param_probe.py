# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the parameter probe: records passed by value, nums passed by reference, Incr and the like.

PROC ParProbe of ParamProbe.mod gives Work two records of the backup's own type, each passed as the
components Work reads (a loop count, a decimal, a bool): Work adds the decimal once per pass and counts
the bool's branch. Bump takes a num by reference (INOUT) and adds to it with Add; Twice takes one too
and passes it on to Bump, then Incr it; Decr and Clear change the totals as well. CrossArm passes each
record as its components (CALL WORK(3,.5,1)), and each num passed by reference in a register of the
routine's own, read back by the caller after the CALL.

  ABB (RobotStudio): PROC Probe runs ParProbe and writes the totals to HOME:/paramprobe.txt.
  FANUC (ROBOGUIDE): the converted PARPROBE runs; the totals are read from NUMREG.VA.

Usage:  python tools/make_param_probe.py write     ParamProbe.mod and the .LS in tests/fixtures/probes/params
        python tools/make_param_probe.py run       RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_param_probe.py check     compare the stored results
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

PROBE = ROOT / "tests" / "fixtures" / "probes" / "params"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "paramprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "paramprobe_roboguide.txt"
PROGRAM = "PARPROBE"
ROUTINES = ["ParProbe", "Work", "Bump", "Twice"]

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE ParamProbe",
    "    ! CrossArm - parameter probe: see tools/make_param_probe.py. PROC ParProbe is what CrossArm converts;",
    "    ! PROC Probe runs it in RobotStudio and writes the totals to HOME:/paramprobe.txt.",
    "    RECORD partspec",
    "        string name;",
    "        num passes;",
    "        num depth;",
    "        bool chamfer;",
    "    ENDRECORD",
    '    PERS partspec psA:=["PART-A",3,0.5,TRUE];',
    '    PERS partspec psB:=["PART-B",2,-1.25,FALSE];',
    "    VAR num nSum:=0;",
    "    VAR num nCount:=0;",
    "    VAR num nBack:=0;",
    "",
    "    PROC ParProbe()",
    "        nSum:=0;",
    "        nCount:=0;",
    "        nBack:=0;",
    "        Work psA;",
    "        Work psB;",
    "        Bump nBack,4;",
    "        Bump nBack,-1.5;",
    "        Twice nBack;",
    "        Decr nCount;",
    "        Add nSum,10;",
    "        Clear nCount;",
    "        Incr nCount;",
    "        Work psA;",
    "    ENDPROC",
    "",
    "    PROC Work(partspec part)",
    "        FOR i FROM 1 TO part.passes DO",
    "            nSum:=nSum+part.depth;",
    "        ENDFOR",
    "        IF part.chamfer THEN",
    "            nCount:=nCount+10;",
    "        ELSE",
    "            nCount:=nCount+1;",
    "        ENDIF",
    "    ENDPROC",
    "",
    "    PROC Bump(INOUT num n,num d)",
    "        Add n,d;",
    "    ENDPROC",
    "",
    "    PROC Twice(INOUT num n)",
    "        Bump n,1;",
    "        Incr n;",
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        ParProbe;",
    '        Open "HOME:" \\File:="paramprobe.txt", file \\Write;',
    '        Write file, "nSum " \\Num:=nSum;',
    '        Write file, "nCount " \\Num:=nCount;',
    '        Write file, "nBack " \\Num:=nBack;',
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# Worked out by hand: psA 3 passes of 0.5 and its chamfer (+10), psB 2 passes of -1.25 without (+1):
# nSum 1.5 - 2.5 = -1, nCount 11; nBack 4 - 1.5, then 1 by Bump inside Twice and 1 by Incr: 4.5.
# Decr nCount -> 10, Add nSum,10 -> 9, Clear nCount -> 0, Incr -> 1; psA again: nSum 10.5, nCount 11.
EXPECTED = {"nSum": 10.5, "nCount": 11.0, "nBack": 4.5}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="ParamProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=ROUTINES,
                     sources={"ParamProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """RAPID variable -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "ParamProbe.mod").write_bytes(MODULE.encode("ascii"))
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
    print(f"RobotStudio: {robotstudio.run(PROBE / 'ParamProbe.mod', 'Probe', 120, home)}")
    ABB_RESULT.write_text((home / "paramprobe.txt").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    numbers = registers(conversion())
    programs = sorted(PROBE.glob("*.LS"))
    for path in programs:
        roboguide.release(path.stem)
        try:
            roboguide.delete(path.stem)  # a copy from an earlier run: FTP does not replace it
        except Exception:  # noqa: BLE001, S110 - not there
            pass
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
