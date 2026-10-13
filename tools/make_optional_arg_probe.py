# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the optional-argument probe: routines with optional num, bool and string parameters, read with Present().

OptArgProbe.mod calls a routine `Station(num nId\\num Speed\\bool Fast\\string Label\\INOUT num Count\\switch Slow)`
with every optional parameter given, with some, with none; a routine passing its own optional num on
(`\\Speed?Speed`); a function with an optional num written as a program (crossarm.convert.func_programs). Each optional value travels as two
arguments, 1 / 0 whether the call gives it, then the value (0, or '' for a text): Present() reads the first. A
`\\INOUT num` is read back by the caller only when it gave it.

Every program CrossArm writes is written to this folder. On ROBOGUIDE, load them, run OPTARGPROBE, read NUMREG.VA:
each counter as RAPID leaves it.

Usage:  python tools/make_optional_arg_probe.py [output_dir]   (default tests/fixtures/probes/optargs)
        python tools/make_optional_arg_probe.py run             (load, run, store the dump, check)
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import parse_text

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE OptArgProbe",
    "    ! CrossArm - optional-argument probe: see tools/make_optional_arg_probe.py.",
    "    VAR num nBefore:=0;",
    "    VAR num nSpeedSum:=0;",
    "    VAR num nAbsent:=0;",
    "    VAR num nFast:=0;",
    "    VAR num nLabel:=0;",
    "    VAR num nSlow:=0;",
    "    VAR num nCount:=0;",
    "    VAR num nKept:=0;",
    "    VAR num nBand:=0;",
    "    VAR num nAfter:=0;",
    "",
    "    PROC Station(num nId\\num Speed\\bool Fast\\string Label\\INOUT num Count\\switch Slow)",
    "        IF Present(Speed) THEN",
    "            nSpeedSum:=nSpeedSum+Speed;",
    "        ELSE",
    "            nAbsent:=nAbsent+1;",
    "        ENDIF",
    "        IF Present(Fast) AND Fast=TRUE THEN",
    "            nFast:=nFast+1;",
    "        ENDIF",
    "        IF Present(Label) nLabel:=nLabel+1;",
    "        IF Present(Slow) nSlow:=nSlow+1;",
    "        IF Present(Count) THEN",
    "            Count:=Count+nId;",
    "        ENDIF",
    "    ENDPROC",
    "",
    "    PROC Relay(\\num Speed)",
    "        Station 9\\Speed?Speed;",
    "    ENDPROC",
    "",
    "    FUNC bool InBand(num nValue,num nRef\\num Tol)",
    "        IF Present(Tol) THEN",
    "            IF nValue>=nRef-Tol AND nValue<=nRef+Tol RETURN TRUE;",
    "            RETURN FALSE;",
    "        ENDIF",
    "        RETURN nValue=nRef;",
    "    ENDFUNC",
    "",
    "    PROC OptArgProbe()",
    "        nBefore:=1;",
    "        nCount:=5;",
    "        nKept:=7;",
    "        Station 3\\Speed:=200\\Fast:=TRUE\\Count:=nCount;",
    "        Station 4\\Fast:=FALSE\\Slow;",
    "        Station 5\\Label:=\"AB\";",
    "        Station 6;",
    "        Relay\\Speed:=50;",
    "        Relay;",
    "        IF InBand(nCount,10\\Tol:=3) nBand:=nBand+1;",
    "        IF InBand(nCount,10) nBand:=nBand+10;",
    "        IF InBand(nCount,8) nBand:=nBand+100;",
    "        nAfter:=1;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

PROGRAM = "OPTARGPROBE"
NAMES = ("nBefore", "nSpeedSum", "nAbsent", "nFast", "nLabel", "nSlow", "nCount", "nKept", "nBand", "nAfter")
# As RAPID leaves them: Speed given twice (200, 50 passed on), absent four times; Count 5+3 (given once); nKept
# untouched; InBand(8,10\Tol:=3) TRUE, InBand(8,10) FALSE, InBand(8,8) TRUE.
EXPECTED = {"nBefore": 1.0, "nSpeedSum": 250.0, "nAbsent": 4.0, "nFast": 1.0, "nLabel": 1.0, "nSlow": 1.0,
            "nCount": 8.0, "nKept": 7.0, "nBand": 101.0, "nAfter": 1.0}  # fmt: skip


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="OptArgProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    return convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"OptArgProbe": MODULE})


def registers(result: ConversionResult) -> dict[str, int]:
    """RAPID variable -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in NAMES}


def main() -> None:
    default = Path(__file__).resolve().parents[1] / "tests/fixtures/probes/optargs"
    if sys.argv[1:] == ["run"]:
        problem = run(default)
        print(f"FAIL {problem}" if problem else "pass")
        sys.exit(1 if problem else 0)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    out.mkdir(parents=True, exist_ok=True)
    (out / "OptArgProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    for old in out.glob("*.LS"):
        old.unlink()
    for info in result.programs:
        (out / f"{info.program.name}.LS").write_bytes(write_ls(info.program).encode("ascii"))
    for name, number in registers(result).items():
        print(f"  R[{number}] {name} expected {EXPECTED[name]:g}")
    print(f"probe written to {out}")


def run(folder: Path) -> str:
    """Load the programs, run the probe, store the dump: '' when every register is as expected, else what differs."""
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
    roboguide.zero(list(numbers.values()))
    status = roboguide.run(PROGRAM, 120)
    values = roboguide.numreg()
    # the probe's registers only, without the controller's comments
    kept = "".join(f"  [{n}] = {values.get(n, 0):g}\n" for n in sorted(numbers.values()))
    (folder / "results" / "numreg.va").write_text(kept, encoding="utf-8")
    found = {name: values.get(number) for name, number in numbers.items()}
    wrong = {k: (found[k], v) for k, v in EXPECTED.items() if found[k] != v}
    roboguide.select()
    for path in sorted(folder.glob("*.LS")):
        roboguide.delete(path.stem)
    if status != "done" or wrong:
        return f"{PROGRAM}: {status} {wrong or ''} (found, expected)"
    return ""


if __name__ == "__main__":
    main()
