# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the argument probe: do converted calls with arguments compute what RAPID computes?

ArgProbe.mod calls routines taking num, bool and switch arguments: a negative and a decimal
argument, a switch given or not, a routine passing its own arguments on, a parameter the
routine changes (copied to a register), a FOR bounded by an argument, a WAIT on one. CrossArm
converts it; every program is written to this folder. On ROBOGUIDE, load them all, run
ARGPROBE, and read NUMREG.VA (the robot's web page, /md/NUMREG.VA): each RAPID num must hold
the value EXPECTED gives, which is what the same module computes on an ABB controller.

Usage:  python tools/make_arg_probe.py [output_dir]   (default tests/fixtures/probes/args)
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import parse_text

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE ArgProbe",
    "    ! CrossArm - argument probe: see tools/make_arg_probe.py.",
    "    VAR num nSum:=0;",
    "    VAR num nCount:=0;",
    "    VAR num nFlags:=0;",
    "    VAR num nOn:=0;",
    "    VAR num nLast:=0;",
    "    VAR num nAngle:=0;",
    "    VAR num nWaits:=0;",
    "",
    "    PROC ArgProbe()",
    "        nSum:=0;",
    "        nCount:=0;",
    "        nFlags:=0;",
    "        nOn:=0;",
    "        nLast:=0;",
    "        nAngle:=0;",
    "        nWaits:=0;",
    "        ArgRecord 3,-2.5,TRUE\\Check;",
    "        ArgRecord 4,0.5,FALSE;",
    "        ArgRecord 2,10,TRUE\\Check;",
    "        ArgOuter 1\\Check;",
    "        ArgTurn 400;",
    "        ArgTurn 90;",
    "        ArgWait 0.2;",
    "    ENDPROC",
    "",
    "    PROC ArgRecord(num a,num b,bool on\\switch Check)",
    "        nLast:=a;",
    "        nSum:=nSum+b;",
    "        IF on nOn:=nOn+1;",
    "        IF Present(Check) nFlags:=nFlags+1;",
    "        FOR i FROM 1 TO a DO",
    "            nCount:=nCount+1;",
    "        ENDFOR",
    "    ENDPROC",
    "",
    "    PROC ArgOuter(num x\\switch Check)",
    "        ArgRecord x,1,TRUE\\Check?Check;",
    "    ENDPROC",
    "",
    "    PROC ArgTurn(num angle)",
    "        IF angle>360 angle:=0;",
    "        nAngle:=nAngle+angle;",
    "    ENDPROC",
    "",
    "    PROC ArgWait(num t)",
    "        WaitTime t;",
    "        nWaits:=nWaits+1;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# What the module leaves in each variable, worked out by hand from RAPID's rules:
# sums of b: -2.5 + 0.5 + 10 + 1; loops: 3 + 4 + 2 + 1; switches given: 1st, 3rd, and ArgOuter's.
EXPECTED = {"nSum": 9.0, "nCount": 10.0, "nFlags": 3.0, "nOn": 3.0, "nLast": 1.0, "nAngle": 90.0, "nWaits": 1.0}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="ArgProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)),
                     sources={"ArgProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """RAPID variable -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "tests/fixtures/probes/args"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ArgProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    for info in result.programs:
        (out / f"{info.program.name}.LS").write_bytes(write_ls(info.program).encode("ascii"))
        print(f"{info.program.name}.LS")
    for name, number in registers(result).items():
        print(f"  R[{number}] {name} expected {EXPECTED[name]:g}")
    print(f"probe written to {out}")


if __name__ == "__main__":
    main()
