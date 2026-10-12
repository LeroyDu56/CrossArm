# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the raise probe: errors the program raises itself (RAISE of its own errnum), converted by
CrossArm into a register set by the routine raising, tested after its CALL, and the caller's ERROR handler written
there (convert.raised).

RaiseProbe.mod, PROC RpProbe:

    RpRetry     RpFlaky raises ERR_RP_A at its first two calls, passes it on (ERROR RAISE;): RETRY calls it again
    RpNext      RpOdd raises ERR_RP_B for odd numbers, in a FOR loop: TRYNEXT goes on with the next line
    RpReturn    the handler RETURNs: the routine ends, its caller goes on
    RpOuter     RpMiddle's handler counts, then RAISE: the error goes up one more level, to RpOuter's TRYNEXT
    RpBody      RAISE in the body of a routine with a handler (a CONST errnum, 7), ERRNO read there: TRYNEXT

and PROC RpLimit, run on its own: RETRY of an error raised every time stops the program after 4 retries, as
RAPID does (No Of Retry). The values are worked out here as RAPID does (EXPECTED). ROBOGUIDE runs the converted
RPPROBE, then RPLIMIT: the registers are read from NUMREG.VA.

  python tools/make_raise_probe.py write      the .mod and the .LS in tests/fixtures/probes/raise
  python tools/make_raise_probe.py run        ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); result stored
  python tools/make_raise_probe.py check      the stored result against EXPECTED
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

PROBE = ROOT / "tests" / "fixtures" / "probes" / "raise"
RESULT = PROBE / "results" / "raise_roboguide.txt"
STAMP = datetime(2026, 1, 1)
PROGRAMS = ("RPPROBE", "RPLIMIT")

MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE RaiseProbe",
    "    ! CrossArm - raise probe: see tools/make_raise_probe.py.",
    "    VAR errnum ERR_RP_A:=-1;",
    "    VAR errnum ERR_RP_B:=-1;",
    "    CONST errnum ERR_RP_C:=7;",
    *(f"    VAR num {name}:=0;" for name in ("rpTries", "rpTrace", "rpSkip", "rpRet", "rpPass", "rpCode", "rpLimit",
                                              "rpDone")),
    "",
    "    PROC RpProbe()",
    "        BookErrNo ERR_RP_A;",
    "        BookErrNo ERR_RP_B;",
    "        rpTries:=0;",
    "        rpTrace:=0;",
    "        rpSkip:=0;",
    "        rpRet:=0;",
    "        rpPass:=0;",
    "        rpCode:=0;",
    "        rpDone:=0;",
    "        RpRetry;",
    "        RpNext;",
    "        RpReturn;",
    "        rpRet:=rpRet+10;",
    "        RpOuter;",
    "        RpBody;",
    "        rpDone:=1;",
    "    ENDPROC",
    "",
    "    PROC RpFlaky()",
    "        rpTries:=rpTries+1;",
    "        IF rpTries<3 THEN",
    "            RAISE ERR_RP_A;",
    "        ENDIF",
    "    ERROR",
    "        RAISE;",
    "    ENDPROC",
    "",
    "    PROC RpRetry()",
    "        RpFlaky;",
    "        rpTrace:=rpTrace+1;",
    "    ERROR",
    "        IF ERRNO=ERR_RP_A THEN",
    "            RETRY;",
    "        ENDIF",
    "    ENDPROC",
    "",
    "    PROC RpOdd(num k)",
    "        IF k MOD 2=1 THEN",
    "            RAISE ERR_RP_B;",
    "        ENDIF",
    "    ERROR",
    "        RAISE;",
    "    ENDPROC",
    "",
    "    PROC RpNext()",
    "        FOR i FROM 1 TO 5 DO",
    "            RpOdd i;",
    "            rpSkip:=rpSkip+10;",
    "        ENDFOR",
    "    ERROR",
    "        IF ERRNO=ERR_RP_B THEN",
    "            rpSkip:=rpSkip+1;",
    "            TRYNEXT;",
    "        ENDIF",
    "    ENDPROC",
    "",
    "    PROC RpReturn()",
    "        RpOdd 1;",
    "        rpRet:=rpRet+100;",
    "    ERROR",
    "        IF ERRNO=ERR_RP_B THEN",
    "            rpRet:=rpRet+1;",
    "            RETURN;",
    "        ENDIF",
    "    ENDPROC",
    "",
    "    PROC RpMiddle()",
    "        RpOdd 3;",
    "        rpPass:=rpPass+100;",
    "    ERROR",
    "        IF ERRNO=ERR_RP_B THEN",
    "            rpPass:=rpPass+1;",
    "        ENDIF",
    "        RAISE;",
    "    ENDPROC",
    "",
    "    PROC RpOuter()",
    "        RpMiddle;",
    "        rpPass:=rpPass+1000;",
    "    ERROR",
    "        IF ERRNO=ERR_RP_B THEN",
    "            rpPass:=rpPass+10;",
    "            TRYNEXT;",
    "        ENDIF",
    "    ENDPROC",
    "",
    "    PROC RpBody()",
    "        rpCode:=1;",
    "        RAISE ERR_RP_C;",
    "        rpCode:=rpCode+20;",
    "    ERROR",
    "        TEST ERRNO",
    "        CASE ERR_RP_C:",
    "            rpCode:=rpCode+ERRNO;",
    "            TRYNEXT;",
    "        ENDTEST",
    "    ENDPROC",
    "",
    "    PROC RpAlways()",
    "        rpLimit:=rpLimit+1;",
    "        RAISE ERR_RP_A;",
    "    ERROR",
    "        RAISE;",
    "    ENDPROC",
    "",
    "    PROC RpLimit()",
    "        rpLimit:=0;",
    "        RpAlways;",
    "        rpLimit:=rpLimit+100;",
    "    ERROR",
    "        IF ERRNO=ERR_RP_A THEN",
    "            RETRY;",
    "        ENDIF",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# As RAPID runs it: RpFlaky raises twice, the third call passes -> 3 tries, rpTrace 1; RpOdd raises for 1, 3, 5,
# TRYNEXT goes on with rpSkip+10 each time -> 5 * 10 + 3; RpReturn: +1, RETURN, then +10 in RpProbe; RpMiddle +1,
# RAISE, RpOuter +10, TRYNEXT: +1000; RpBody: 1 + ERRNO (7), TRYNEXT: +20. RpLimit: RpAlways called once and
# retried 4 times, then the program stops before +100.
EXPECTED = {"rpTries": 3.0, "rpTrace": 1.0, "rpSkip": 53.0, "rpRet": 11.0, "rpPass": 1011.0, "rpCode": 28.0,
            "rpDone": 1.0, "rpLimit": 5.0}  # fmt: skip


def conversion(folder: Path):
    """RaiseProbe.mod converted (no --karel): one program per PROC, without a TODO."""
    from crossarm import pipeline
    from crossarm.convert import ConversionConfig

    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "RaiseProbe.mod").write_bytes(MODULE.encode("ascii"))
    run = pipeline.run([PROBE / "RaiseProbe.mod"], folder, ConversionConfig(timestamp=STAMP), log=lambda _: None)
    result = run.tasks[0].result
    assert result is not None and not [n for n in result.notes if n.kind == "TODO"], result and result.notes
    names = {info.program.name for info in result.programs}
    assert set(PROGRAMS) <= names, names
    return result


def registers(result) -> dict[str, int]:
    """rpTries... -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def programs(folder: Path) -> list[str]:
    return sorted(p.stem for p in folder.glob("*.LS"))


def write() -> None:
    with tempfile.TemporaryDirectory(prefix="crossarm_raise_") as temp:
        result = conversion(Path(temp))
        for old in PROBE.glob("*.LS"):
            old.unlink()
        for path in Path(temp).glob("*.LS"):
            (PROBE / path.name).write_bytes(path.read_bytes())
    for name, number in registers(result).items():
        print(f"  R[{number}] {name} expected {EXPECTED[name]:g}")
    print(f"probe written to {PROBE}")


def measure() -> dict[str, str]:
    import roboguide
    from make_karel_probe import _ftp

    write()
    with tempfile.TemporaryDirectory(prefix="crossarm_raise_") as temp:
        numbers = registers(conversion(Path(temp)))
    names = programs(PROBE)
    found: dict[str, str] = {}
    for name in names:
        roboguide.release(name)
    roboguide.select()
    for name in names:
        _ftp(f"DELE {name.lower()}.tp")
    try:
        for name in names:
            found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
        roboguide.zero(list(numbers.values()))
        found["run"] = roboguide.run("RPPROBE", 120)
        roboguide.select()
        found["limit_run"] = roboguide.run("RPLIMIT", 120)
        values = roboguide.numreg()
        for name, number in numbers.items():
            found[name] = f"{values.get(number, float('nan')):g}"
        return found
    finally:
        roboguide.select()
        for name in names:
            roboguide.release(name)
        roboguide.select()
        for name in names:
            _ftp(f"DELE {name.lower()}.tp")


def verdict(found: dict[str, str]) -> str:
    wrong = [f"{key[:-5]}: {value}" for key, value in found.items() if key.endswith("_load") and value != "loaded"]
    if found.get("run") != "done":
        wrong.append(f"RPPROBE: {found.get('run')}")
    if found.get("limit_run", "").startswith(("timeout", "refused")):  # the ABORT ends it: done or aborted
        wrong.append(f"RPLIMIT: {found.get('limit_run')}")
    for name, value in EXPECTED.items():
        got = float(found.get(name, "nan"))
        if not abs(got - value) <= 0.001:
            wrong.append(f"{name} {found.get(name)} (RAPID {value:g})")
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    return (f"errors raised by the program (RAISE, ERROR RAISE;) as a register tested after the CALL: RETRY (at most"
            f" 4, then ABORT), TRYNEXT, RETURN, RAISE up two levels, ERRNO: {len(EXPECTED)} values as RAPID")


def run() -> str:
    found = measure()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text("".join(f"{k} {v}\n" for k, v in found.items()), encoding="ascii")
    print(RESULT.read_text(encoding="ascii"))
    return check()


def stored() -> dict[str, str]:
    return dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())


def check() -> str:
    found = stored()
    problem = verdict(found)
    print(f"FAIL {problem}" if problem else f"raise probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
