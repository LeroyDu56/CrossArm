# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the condition probe: do conditions written from the backup's bool functions test what RAPID tests?

CondProbe.mod has the common shape of such functions (`IF x=0 OR RobOS()=FALSE THEN
RETURN TRUE; ELSE RETURN FALSE;`), called as `Ready()=TRUE`, negated, nested in another function,
in a WHILE and a WaitUntil, plus a negated group next to AND (`a AND NOT (b OR c)`), which needs its
parentheses. CrossArm converts it; every program is written to this folder. On ROBOGUIDE, load them
all, run CONDPROBE, and read NUMREG.VA (the robot's web page, /md/NUMREG.VA): each RAPID num must hold
the value EXPECTED gives, which is what the module computes on a real ABB controller (RobOS() TRUE;
in RobotStudio it is FALSE and the figures differ).

CONDIO reads a group input and a digital input in conditions (`IF (GI[1]=0 AND DI[1]=OFF)`): load it
to check the controller accepts the form. Running it needs those inputs configured.

Usage:  python tools/make_condition_probe.py [output_dir]   (default tests/fixtures/probes/conditions)
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import parse_text
from crossarm.rapid.eio import Signal

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE CondProbe",
    "    ! CrossArm - condition probe: see tools/make_condition_probe.py.",
    "    VAR num nMode:=0;",
    "    VAR bool bArmed:=FALSE;",
    "    VAR num nHits:=0;",
    "    VAR num nMiss:=0;",
    "    VAR num nGroup:=0;",
    "    VAR num nLoops:=0;",
    "    VAR num nIo:=0;",
    "",
    "    PROC CondProbe()",
    "        nHits:=0;",
    "        nMiss:=0;",
    "        nGroup:=0;",
    "        nLoops:=0;",
    "        nMode:=0;",
    "        bArmed:=TRUE;",
    "        IF Ready()=TRUE THEN",
    "            nHits:=nHits+1;",
    "        ENDIF",
    "        IF Blocked()=FALSE AND NOT Armed() THEN",
    "            nMiss:=nMiss+1;",
    "        ENDIF",
    "        nMode:=1;",
    "        IF Blocked()=FALSE AND NOT Armed() THEN",
    "            nHits:=nHits+10;",
    "        ENDIF",
    "        IF nMode>0 AND NOT (nMode>2 OR bArmed) THEN",
    "            nMiss:=nMiss+10;",
    "        ENDIF",
    "        bArmed:=FALSE;",
    "        IF nMode>0 AND NOT (nMode>2 OR bArmed) THEN",
    "            nGroup:=nGroup+1;",
    "        ENDIF",
    "        IF NOT RobOS() THEN",
    "            nMiss:=nMiss+100;",
    "        ENDIF",
    "        IF RobOS() OR bArmed THEN",
    "            nHits:=nHits+100;",
    "        ENDIF",
    "        WHILE NOT Ready() DO",
    "            nLoops:=nLoops+1;",
    "            nMode:=nMode-1;",
    "        ENDWHILE",
    "        WaitUntil Ready();",
    "    ENDPROC",
    "",
    "    PROC CondIo()",
    "        IF giCode=0 AND DInput(diReady)=0 THEN",
    "            nIo:=nIo+1;",
    "        ENDIF",
    "    ENDPROC",
    "",
    "    FUNC bool Ready()",
    "        IF nMode=0 OR RobOS()=FALSE THEN",
    "            RETURN TRUE;",
    "        ELSE",
    "            RETURN FALSE;",
    "        ENDIF",
    "    ENDFUNC",
    "",
    "    FUNC bool Blocked()",
    "        IF nMode=2 THEN",
    "            RETURN TRUE;",
    "        ENDIF",
    "        RETURN FALSE;",
    "    ENDFUNC",
    "",
    "    FUNC bool Armed()",
    "        RETURN Ready() AND bArmed;",
    "    ENDFUNC",
    "ENDMODULE",
    "",
])  # fmt: skip

SIGNALS = {"GICODE": Signal("giCode", "GI"), "DIREADY": Signal("diReady", "DI")}

# What CondProbe leaves in each variable on a real controller, worked out by hand:
# hits 1 (Ready at mode 0) + 10 (mode 1: not Blocked, not Armed) + 100 (RobOS); nothing missed;
# the group test true once bArmed is FALSE; one loop turn to bring the mode back to 0.
EXPECTED = {"nHits": 111.0, "nMiss": 0.0, "nGroup": 1.0, "nLoops": 1.0}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="CondProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)),
                     sources={"CondProbe": MODULE}, signals=SIGNALS)  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """RAPID variable -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def main() -> None:
    default = Path(__file__).resolve().parents[1] / "tests/fixtures/probes/conditions"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    out.mkdir(parents=True, exist_ok=True)
    (out / "CondProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    for info in result.programs:
        (out / f"{info.program.name}.LS").write_bytes(write_ls(info.program).encode("ascii"))
        print(f"{info.program.name}.LS")
    for name, number in registers(result).items():
        print(f"  R[{number}] {name} expected {EXPECTED[name]:g}")
    print(f"probe written to {out}")


if __name__ == "__main__":
    main()
