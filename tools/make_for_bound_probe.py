# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the FOR-bound probe: FOR loops whose bounds are registers, calculations, or left to the integrator.

ForBoundProbe.mod counts the turns of FOR loops: a bound read from a register (TO, and a STEP -1 loop from one: DOWNTO), a bound
worked out before the FOR in a register of its own (`R[k]=R[n]*2`, then `R[k]=R[k]-3`), nested loops with computed
bounds, a loop whose bound data is changed by its own body (RAPID works the bounds out once, before the first
turn), a loop with no turn (start above the end), loops with a STEP (4, -3 from a computed start, 0.25: a loop of
labels, the counter tested before each turn), and a loop whose bound CrossArm cannot write (a FUNC reading the
operating mode): left to the integrator in a reserved register, the FOR skipped by a `JMP LBL[n]` until the line
setting it is written (crossarm.convert.condition_gates).

Two programs are written to this folder: FORBOUNDPROBE as CrossArm writes it, and FORBOUNDSET, the same lines with
the jump replaced by `R[k]=3`, as an integrator would. On ROBOGUIDE, load both, run FORBOUNDPROBE, read NUMREG.VA
(DEFAULT: each loop turns as in RAPID, the gated one not at all), zero the registers, run FORBOUNDSET (SET: the
gated loop three turns).

Usage:  python tools/make_for_bound_probe.py [output_dir]   (default tests/fixtures/probes/forbound)
        python tools/make_for_bound_probe.py run             (load, run both, store the dumps, check)
"""

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import parse_text

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE ForBoundProbe",
    "    ! CrossArm - FOR-bound probe: see tools/make_for_bound_probe.py.",
    "    VAR num nBefore:=0;",
    "    VAR num nCount:=0;",
    "    VAR num nTwo:=0;",
    "    VAR num nTo:=0;",
    "    VAR num nDown:=0;",
    "    VAR num nCalc:=0;",
    "    VAR num nNest:=0;",
    "    VAR num nShrink:=0;",
    "    VAR num nNone:=0;",
    "    VAR num nGated:=0;",
    "    VAR num nStepSum:=0;",
    "    VAR num nStepDown:=0;",
    "    VAR num nQuarter:=0;",
    "    VAR num nAfter:=0;",
    "",
    "    FUNC num CycleCount()",
    "        IF OpMode()=OP_AUTO RETURN 5;",
    "        RETURN 2;",
    "    ENDFUNC",
    "",
    "    PROC ForBoundProbe()",
    "        nBefore:=1;",
    "        nCount:=4;",
    "        nTwo:=2;",
    "        FOR i FROM 1 TO nCount DO",
    "            nTo:=nTo+1;",
    "        ENDFOR",
    "        FOR i FROM nCount TO 2 STEP -1 DO",
    "            nDown:=nDown+1;",
    "        ENDFOR",
    "        FOR i FROM 2 TO nCount*2-3 DO",
    "            nCalc:=nCalc+1;",
    "        ENDFOR",
    "        FOR i FROM 1 TO nTwo+1 DO",
    "            FOR j FROM nTwo-1 TO nTwo DO",
    "                nNest:=nNest+1;",
    "            ENDFOR",
    "        ENDFOR",
    "        FOR i FROM 1 TO nCount DO",
    "            nCount:=nCount-1;",
    "            nShrink:=nShrink+1;",
    "        ENDFOR",
    "        FOR i FROM nTwo TO nTwo-1 DO",
    "            nNone:=nNone+1;",
    "        ENDFOR",
    "        FOR i FROM 0 TO 20 STEP 4 DO",
    "            nStepSum:=nStepSum+i;",
    "        ENDFOR",
    "        FOR i FROM nTwo*5 TO nTwo STEP -3 DO",
    "            nStepDown:=nStepDown+1;",
    "        ENDFOR",
    "        FOR i FROM 0 TO 1 STEP 0.25 DO",
    "            nQuarter:=nQuarter+1;",
    "        ENDFOR",
    "        FOR i FROM 1 TO CycleCount() DO",
    "            nGated:=nGated+1;",
    "        ENDFOR",
    "        nAfter:=1;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

PROGRAM, SET = "FORBOUNDPROBE", "FORBOUNDSET"
NAMES = ("nBefore", "nTo", "nDown", "nCalc", "nNest", "nShrink", "nNone", "nStepSum", "nStepDown", "nQuarter",
         "nGated", "nAfter")
# As RAPID turns them (the bounds worked out once, before the first turn); the gated loop skipped.
DEFAULT = {"nBefore": 1.0, "nTo": 4.0, "nDown": 3.0, "nCalc": 4.0, "nNest": 6.0, "nShrink": 4.0, "nNone": 0.0,
           "nStepSum": 60.0, "nStepDown": 3.0, "nQuarter": 5.0, "nGated": 0.0, "nAfter": 1.0}  # fmt: skip
EXPECTED_SET = {**DEFAULT, "nGated": 3.0}  # the bound set to 3 by the line replacing the jump


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="ForBoundProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    return convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"ForBoundProbe": MODULE})


def registers(result: ConversionResult) -> dict[str, int]:
    """RAPID variable -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in NAMES}


def set_text(result: ConversionResult) -> str:
    """FORBOUNDPROBE with the jump replaced by the line an integrator writes: the bound 3."""
    text = write_ls(next(i.program for i in result.programs if i.program.name == PROGRAM))
    lines = text.split("\r\n")
    for i, line in enumerate(lines):
        found = re.match(r"(\s*\d+:\s*)!Replace JMP by (\S+?)=\(\.\.\.\) ;", line)
        if found is not None:
            number = re.match(r"(\s*\d+:\s*)", lines[i + 1])[1]  # type: ignore[index]
            assert "JMP LBL[" in lines[i + 1], lines[i + 1]
            lines[i + 1] = f"{number}{found[2]}=3 ;"
    return "\r\n".join(lines).replace(f"/PROG  {PROGRAM}", f"/PROG  {SET}", 1)


def main() -> None:
    default = Path(__file__).resolve().parents[1] / "tests/fixtures/probes/forbound"
    if sys.argv[1:] == ["run"]:
        problem = run(default)
        print(f"FAIL {problem}" if problem else "pass")
        sys.exit(1 if problem else 0)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    out.mkdir(parents=True, exist_ok=True)
    (out / "ForBoundProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    for info in result.programs:
        if info.program.name == PROGRAM:
            (out / f"{PROGRAM}.LS").write_bytes(write_ls(info.program).encode("ascii"))
    (out / f"{SET}.LS").write_bytes(set_text(result).encode("ascii"))
    for name, number in registers(result).items():
        print(f"  R[{number}] {name} default {DEFAULT[name]:g} set {EXPECTED_SET[name]:g}")
    print(f"probe written to {out}")


def run(folder: Path) -> str:
    """Load both programs, run them, store the dumps: '' when every register is as expected, else what differs."""
    import roboguide

    numbers = registers(conversion())
    (folder / "results").mkdir(exist_ok=True)
    roboguide.select()  # the program run last stays selected and cannot be replaced
    for path in sorted(folder.glob("*.LS")):
        try:
            roboguide.delete(path.stem)
        except Exception:  # noqa: BLE001, S110 - not there
            pass
        if reason := roboguide.load(path):
            return f"{path.name} not loaded: {reason}"
    problems = []
    for program, expected, dump in ((PROGRAM, DEFAULT, "numreg_default.va"), (SET, EXPECTED_SET, "numreg_set.va")):
        roboguide.zero(list(numbers.values()))
        status = roboguide.run(program, 120)
        values = roboguide.numreg()
        # the probe's registers only, without the controller's comments
        kept = "".join(f"  [{n}] = {values.get(n, 0):g}\n" for n in sorted(numbers.values()))
        (folder / "results" / dump).write_text(kept, encoding="utf-8")
        found = {name: values.get(number) for name, number in numbers.items()}
        wrong = {k: (found[k], v) for k, v in expected.items() if found[k] != v}
        if status != "done" or wrong:
            problems.append(f"{program}: {status} {wrong or ''} (found, expected)")
    roboguide.select()
    for path in sorted(folder.glob("*.LS")):
        roboguide.delete(path.stem)
    return "; ".join(problems)


if __name__ == "__main__":
    main()
