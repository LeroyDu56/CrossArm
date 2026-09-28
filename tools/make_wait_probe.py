# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the wait probe: do waits with a time limit do on FANUC what the RAPID error handler does?

WaitProbe.mod waits on things that never happen, with \\MaxTime, in routines whose ERROR handler
goes on with the next instruction (TRYNEXT) or tries again a few times (RETRY) before leaving the
routine. CrossArm writes each as a loop reading a TIMER, with the handler's path after it: the time
limit of WAIT ... TIMEOUT, $WAITTMOUT, is write-protected for programs (a first version of this probe
stopped on VARS-010). On ROBOGUIDE, load every program, run WAITTIME, and read NUMREG.VA
(/md/NUMREG.VA): each RAPID num must hold the value EXPECTED gives.

WAITTIME runs WAITPROBE between timer readings: R[41] holds a 1 s WAIT as the controller times it
(1.0: TIMER counts seconds), R[42] how long the waits took, which must be the sum of their MaxTime.

Usage:  python tools/make_wait_probe.py [output_dir]   (default tests/fixtures/probes/waits)
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program
from crossarm.rapid import parse_text
from crossarm.rapid.eio import Signal

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE WaitProbe",
    "    ! CrossArm - wait probe: see tools/make_wait_probe.py.",
    "    VAR num nTimeouts:=0;",
    "    VAR num nAfter:=0;",
    "    VAR num nRetries:=0;",
    "    VAR bool bNever:=FALSE;",
    "",
    "    PROC WaitProbe()",
    "        nTimeouts:=0;",
    "        nAfter:=0;",
    "        nRetries:=0;",
    "        bNever:=FALSE;",
    "        WaitNext;",
    "        WaitRetry;",
    "        nAfter:=nAfter+100;",
    "    ENDPROC",
    "",
    "    PROC WaitNext()",
    "        WaitUntil bNever=TRUE\\MaxTime:=0.5;",
    "        nAfter:=nAfter+1;",
    "        WaitDI diNever,1\\MaxTime:=0.3;",
    "        nAfter:=nAfter+1;",
    "    ERROR",
    "        TEST ERRNO",
    "        CASE ERR_WAIT_MAXTIME:",
    "            TRYNEXT;",
    "        ENDTEST",
    "    ENDPROC",
    "",
    "    PROC WaitRetry()",
    "        WaitUntil bNever\\MaxTime:=0.2;",
    "        nAfter:=nAfter+10;",
    "    ERROR",
    "        IF ERRNO=ERR_WAIT_MAXTIME THEN",
    "            IF nRetries<2 THEN",
    "                nRetries:=nRetries+1;",
    "                RETRY;",
    "            ELSE",
    "                nTimeouts:=nTimeouts+1;",
    "                RETURN;",
    "            ENDIF",
    "        ENDIF",
    "        RAISE;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

SIGNALS = {"DINEVER": Signal("diNever", "DI")}

# What WaitProbe leaves in each variable, worked out by hand from RAPID's rules: both waits of WaitNext
# time out and go on (+1 +1); WaitRetry times out three times, retries twice, then leaves before its +10;
# the main routine goes on (+100).
EXPECTED = {"nAfter": 102.0, "nRetries": 2.0, "nTimeouts": 1.0}

# How long the waits take, timed with the controller's own timer, next to a 1 s WAIT.
TIME_LINES = [
    "!wait probe: timing",
    "TIMER[1]=RESET",
    "TIMER[1]=START",
    "WAIT   1.00(sec)",
    "TIMER[1]=STOP",
    "R[41]=TIMER[1]",
    "TIMER[1]=RESET",
    "TIMER[1]=START",
    "CALL WAITPROBE",
    "TIMER[1]=STOP",
    "R[42]=TIMER[1]",
]
WAITED_S = 0.5 + 0.3 + 3 * 0.2  # WaitNext's two waits, WaitRetry's three


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="WaitProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)),
                     sources={"WaitProbe": MODULE}, signals=SIGNALS)  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    return result


def unit_program() -> Program:
    return Program("WAITTIME", [Instruction(line) for line in TIME_LINES], [],
                   Attributes(comment="wait probe", created=datetime(2026, 1, 1)))  # fmt: skip


def registers(result: ConversionResult) -> dict[str, int]:
    """RAPID variable -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "tests/fixtures/probes/waits"
    out.mkdir(parents=True, exist_ok=True)
    (out / "WaitProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    for program in [*(info.program for info in result.programs), unit_program()]:
        (out / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
        print(f"{program.name}.LS")
    for name, number in registers(result).items():
        print(f"  R[{number}] {name} expected {EXPECTED[name]:g}")
    print(f"  R[41]: 1 s WAIT as timed (1.0); R[42]: the waits, about {WAITED_S:g} s")
    print(f"probe written to {out}")


if __name__ == "__main__":
    main()
