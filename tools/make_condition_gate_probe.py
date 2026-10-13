# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the condition-gate probe: a condition CrossArm cannot convert, left to the integrator, its blocks written.

CondGateProbe.mod has an IF / ELSE, an IF / ELSEIF / ELSE whose second test cannot be converted (twice: after a
test of numbers, written IF ... THEN, and after one of texts, written with jumps), a WHILE and a TEST
whose test cannot be either (the operating mode, the length of a text). CrossArm writes each instruction whole, its
test left in a reserved flag (a register for the TEST) and a `JMP LBL[n]` skipping the instruction until the
integrator writes, in its place, the line setting it (crossarm.convert.condition_gates).

Two programs are written to this folder: CONDGATEPROBE as CrossArm writes it, and CONDGATESET, the same lines with
each jump replaced as an integrator would: the IF's flag ON, the ELSEIF's ON, the WHILE's `F[k]=(R[loops]<3)`, the
TEST's register 1. On ROBOGUIDE, load both, run CONDGATEPROBE, read NUMREG.VA (DEFAULT: nothing of the four
instructions ran, the lines before and after did), zero the registers, run CONDGATESET (SET: the blocks the set
conditions select ran, the WHILE three turns).

Usage:  python tools/make_condition_gate_probe.py [output_dir]   (default tests/fixtures/probes/condgate)
        python tools/make_condition_gate_probe.py run             (load, run both, store the dumps, check)
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
    "MODULE CondGateProbe",
    "    ! CrossArm - condition-gate probe: see tools/make_condition_gate_probe.py.",
    "    VAR num nBefore:=0;",
    "    VAR num nThen:=0;",
    "    VAR num nElse:=0;",
    "    VAR num nElseIf:=0;",
    "    VAR num nLoops:=0;",
    "    VAR num nCase:=0;",
    "    VAR num nAfter:=0;",
    '    VAR string sMode:="A";',
    "",
    "    PROC CondGateProbe()",
    "        nBefore:=1;",
    '        sMode:="A";',
    "        IF OpMode()=OP_AUTO THEN",
    "            nThen:=nThen+1;",
    "        ELSE",
    "            nElse:=nElse+1;",
    "        ENDIF",
    "        IF nBefore>5 THEN",
    "            nThen:=nThen+10;",
    "        ELSEIF OpMode()=OP_AUTO THEN",
    "            nElseIf:=nElseIf+1;",
    "        ELSE",
    "            nElse:=nElse+10;",
    "        ENDIF",
    '        IF sMode="B" THEN',
    "            nThen:=nThen+100;",
    "        ELSEIF OpMode()=OP_AUTO THEN",
    "            nElseIf:=nElseIf+10;",
    "        ELSE",
    "            nElse:=nElse+100;",
    "        ENDIF",
    "        WHILE OpMode()<>OP_AUTO DO",
    "            nLoops:=nLoops+1;",
    "        ENDWHILE",
    "        TEST StrLen(sMode)",
    "        CASE 1:",
    "            nCase:=1;",
    "        DEFAULT:",
    "            nCase:=2;",
    "        ENDTEST",
    "        nAfter:=1;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

PROGRAM, SET = "CONDGATEPROBE", "CONDGATESET"
NAMES = ("nBefore", "nThen", "nElse", "nElseIf", "nLoops", "nCase", "nAfter")
# As converted: the four instructions skipped, the lines around them run.
DEFAULT = {"nBefore": 1.0, "nThen": 0.0, "nElse": 0.0, "nElseIf": 0.0, "nLoops": 0.0, "nCase": 0.0, "nAfter": 1.0}
# Each condition set: the IF true (nThen 1), the ELSEIFs true (nElseIf 1 + 10), the WHILE true while nLoops < 3 (3 turns),
# the TEST on 1 (nCase 1); no ELSE ran.
EXPECTED_SET = {"nBefore": 1.0, "nThen": 1.0, "nElse": 0.0, "nElseIf": 11.0, "nLoops": 3.0, "nCase": 1.0, "nAfter": 1.0}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="CondGateProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    return convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"CondGateProbe": MODULE})


def registers(result: ConversionResult) -> dict[str, int]:
    """RAPID variable -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in NAMES}


def set_text(result: ConversionResult) -> str:
    """CONDGATEPROBE with each jump replaced by the line an integrator writes."""
    text = write_ls(next(i.program for i in result.programs if i.program.name == PROGRAM))
    loops = registers(result)["nLoops"]
    values = {}
    for gate in result.gated:
        if gate.slot.startswith("R["):
            values[gate.slot] = f"{gate.slot}=1"
        elif gate.rapid.startswith("OpMode() <>"):  # the WHILE: true while fewer than 3 turns
            values[gate.slot] = f"{gate.slot}=(R[{loops}]<3)"
        else:
            values[gate.slot] = f"{gate.slot}=(ON)"
    lines = text.split("\r\n")
    for i, line in enumerate(lines):
        found = re.match(r"(\s*\d+:\s*)!Replace JMP by (\S+?)=\(\.\.\.\) ;", line)
        if found is not None:
            number = re.match(r"(\s*\d+:\s*)", lines[i + 1])[1]  # type: ignore[index]
            assert "JMP LBL[" in lines[i + 1], lines[i + 1]
            lines[i + 1] = f"{number}{values[found[2]]} ;"
    return "\r\n".join(lines).replace(f"/PROG  {PROGRAM}", f"/PROG  {SET}", 1)


def main() -> None:
    default = Path(__file__).resolve().parents[1] / "tests/fixtures/probes/condgate"
    if sys.argv[1:] == ["run"]:
        problem = run(default)
        print(f"FAIL {problem}" if problem else "pass")
        sys.exit(1 if problem else 0)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    out.mkdir(parents=True, exist_ok=True)
    (out / "CondGateProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    for info in result.programs:  # CONDGATEPROBE, and CA_TEXT for the text it compares
        (out / f"{info.program.name}.LS").write_bytes(write_ls(info.program).encode("ascii"))
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
