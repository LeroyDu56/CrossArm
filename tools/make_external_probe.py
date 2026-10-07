# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the provided-programs probe: calls to routines the integrator provides (external_routines).

ExtProbe.mod calls three routines CrossArm does not write: ProbeAdd, which the backup does not declare (typed
from the call: a num, a negative num, a bool), ProbeLog, which writes a file (a string, a num), and ProbeTwice,
which writes a file and doubles its INOUT num. With external_routines naming EXTADD, EXTLOG and EXTTWICE,
CrossArm writes EXTPROBE.LS calling them, and no program for the three routines. The provided programs are
written here by hand, as an integrator would: each copies what it is given (AR[n]) into registers, EXTTWICE
writes twice its argument in the register CrossArm names for the num RAPID reads back.

On ROBOGUIDE: EXTPROBE.LS is loaded first, alone (a .LS calling a program the robot does not have still loads),
run without them (it stops on the first CALL: INTP-222), then the provided programs are loaded and it runs to
the end: each register must hold EXPECTED.

  python tools/make_external_probe.py write    the programs, in tests/fixtures/probes/external
  python tools/make_external_probe.py run      ROBOGUIDE; result in tests/fixtures/probes/external/results
  python tools/make_external_probe.py check    the result against EXPECTED
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.convert.external import ProvidedRoutine
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "external"
RESULT = PROBE / "results" / "external_roboguide.txt"
PROGRAM = "EXTPROBE"
PROVIDED = {"ProbeAdd": "EXTADD", "ProbeLog": "EXTLOG", "ProbeTwice": "EXTTWICE"}

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE ExtProbe",
    "    ! CrossArm - provided programs probe: see tools/make_external_probe.py.",
    "    VAR num nSum:=0;",
    "    VAR num nFlag:=0;",
    "    VAR num nLen:=0;",
    "    VAR num nLogged:=0;",
    "    VAR num nBack:=0;",
    "    VAR num nAfter:=0;",
    "    VAR iodev log;",
    "",
    "    PROC ExtProbe()",
    "        nSum:=0;",
    "        nFlag:=0;",
    "        nLen:=0;",
    "        nLogged:=0;",
    "        nBack:=7;",
    "        nAfter:=0;",
    "        ProbeAdd 3,-2.5,TRUE;",
    '        ProbeLog "HELLO",nBack;',
    "        ProbeTwice nBack;",
    "        nAfter:=nAfter+1;",
    "    ENDPROC",
    "",
    "    PROC ProbeLog(string text,num n)",
    '        Open "HOME:/crossarm_probe.txt",log\\Append;',
    "        Write log,text\\Num:=n;",
    "        Close log;",
    "    ENDPROC",
    "",
    "    PROC ProbeTwice(INOUT num value)",
    '        Open "HOME:/crossarm_probe.txt",log\\Append;',
    "        Write log,\"twice\"\\Num:=value;",
    "        Close log;",
    "        value:=value*2;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# What the provided programs leave, from what RAPID passes: 3 + -2.5, TRUE, StrLen("HELLO"), nBack (7) when
# ProbeLog runs, 7 * 2 read back into nBack, and the line after the last CALL reached.
EXPECTED = {"nSum": 0.5, "nFlag": 1.0, "nLen": 5.0, "nLogged": 7.0, "nBack": 14.0, "nAfter": 1.0}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="ExtProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    provided = {name.upper(): ProvidedRoutine(name, program) for name, program in PROVIDED.items()}
    config = ConversionConfig(timestamp=datetime(2026, 1, 1), external_routines=provided)
    result = convert([parsed.module], config, sources={"ExtProbe": MODULE})
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    assert [info.program.name for info in result.programs] == [PROGRAM]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """RAPID variable -> the R[n] CrossArm gave it; and 'twice' -> the register EXTTWICE gives its value back in."""
    found = {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}
    twice = next(use for use in result.provided if use.program == "EXTTWICE")
    found["twice"] = twice.returned["value"]
    return found


def provided_programs(numbers: dict[str, int]) -> list[Program]:
    """The integrator's programs: what each is given, copied into the registers the probe reads."""

    def program(name: str, lines: list[str]) -> Program:
        return Program(name, [Instruction(text) for text in lines],
                       attributes=Attributes(comment="provided", created=datetime(2026, 1, 1), default_group="*,*,*,*,*"))  # fmt: skip

    r = {name: f"R[{number}]" for name, number in numbers.items()}
    return [
        program("EXTADD", [f"{r['nSum']}=AR[1]+AR[2]", f"{r['nFlag']}=AR[3]"]),
        program("EXTLOG", [f"{r['nLen']}=STRLEN AR[1]", f"{r['nLogged']}=AR[2]"]),
        program("EXTTWICE", [f"{r['twice']}=AR[1]*2"]),
    ]


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "ExtProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    numbers = registers(result)
    for program in [info.program for info in result.programs] + provided_programs(numbers):
        (PROBE / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
        print(f"{program.name}.LS")
    for name, number in numbers.items():
        print(f"  R[{number}] {name}" + (f" expected {EXPECTED[name]:g}" if name in EXPECTED else ""))
    print(f"probe written to {PROBE}")


def measure() -> dict[str, str]:
    """Load the caller alone, run it (it stops on the first CALL), load the provided programs, run it again:
    what each step gave, and the registers."""
    import roboguide

    write()
    numbers = registers(conversion())
    names = [PROGRAM, *PROVIDED.values()]
    for name in names:
        roboguide.release(name)
    roboguide.select()
    for name in names:
        try:
            roboguide.delete(name)
        except Exception:  # noqa: BLE001, S110 - not there
            pass
    found: dict[str, str] = {}
    try:
        found["alone_load"] = roboguide.load(PROBE / f"{PROGRAM}.LS") or "loaded"
        if found["alone_load"] != "loaded":
            return found
        roboguide.zero(list(numbers.values()))
        found["alone_run"] = roboguide.run(PROGRAM, 60)
        log = roboguide.page("md/ERRALL.LS")
        found["alone_alarm"] = "INTP-222" if f"INTP-222 ({PROGRAM}," in log else "none"
        roboguide.release(PROGRAM)
        roboguide.select()
        for name in PROVIDED.values():
            reason = roboguide.load(PROBE / f"{name}.LS")
            if reason:
                found["provided_load"] = f"{name}: {reason}"
                return found
        found["provided_load"] = "loaded"
        roboguide.zero(list(numbers.values()))
        found["run"] = roboguide.run(PROGRAM, 60)
        values = roboguide.numreg()
        for name in EXPECTED:
            found[name] = f"{values.get(numbers[name], float('nan')):g}"
        return found
    finally:
        roboguide.select()
        for name in names:
            try:
                roboguide.delete(name)
            except Exception:  # noqa: BLE001, S110 - already gone
                pass


def verdict(found: dict[str, str]) -> str:
    """'' when the probe went as measured; else what differs."""
    wrong = []
    if found.get("alone_load") != "loaded":
        wrong.append(f"caller alone not loaded: {found.get('alone_load')}")
    if not found.get("alone_run", "").startswith("paused at line") or found.get("alone_alarm") != "INTP-222":
        wrong.append(f"caller alone ran: {found.get('alone_run')}, {found.get('alone_alarm')}")
    if found.get("provided_load") != "loaded" or found.get("run") != "done":
        wrong.append(f"with the provided programs: {found.get('provided_load')}, {found.get('run')}")
    wrong += [f"{name} {found.get(name)} (expected {value:g})" for name, value in EXPECTED.items()
              if found.get(name) is None or float(found[name]) != value]  # fmt: skip
    return "; ".join(wrong)


def run() -> None:
    found = measure()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text("".join(f"{k} {v}\n" for k, v in found.items()), encoding="ascii")
    print(RESULT.read_text(encoding="ascii"))
    check()


def check() -> None:
    found = dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())
    problem = verdict(found)
    print(f"FAIL {problem}" if problem else "external probe: as measured")


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
