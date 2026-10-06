# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the probe of jointtargets read on the robot (CJointT), kept in a joint position register.

JointProbe.mod moves to two joint targets, reads the robot's joints after each (CJointT) and their six axes;
compares them (block IF on a negative constant, a calculation on rax_3 first, a bool set to a comparison),
adds two up, then goes back to the first reading with another tool selected (MoveAbsJ to the jointtarget
read) and reads the joints again. CrossArm writes `PR[k]=JPOS`, the axes worked out from the FANUC joints
with the measured conventions (rax_3 = -(J3+J2), rax_4/5 = -J4/-J5, rax_6 = 180-J6) and `J PR[k]`: the
converted program must give the values RobotStudio gives, which are the ABB axes the targets are written in.

  ABB (RobotStudio): PROC Probe runs JpProbe and writes the totals to HOME:/jointprobe.txt.
  FANUC (ROBOGUIDE): the converted JPPROBE runs; totals from NUMREG.VA.

Usage:  python tools/make_joint_probe.py write    JointProbe.mod and the .LS in tests/fixtures/probes/joints
        python tools/make_joint_probe.py run      RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_joint_probe.py check    compare the stored results
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

PROBE = ROOT / "tests" / "fixtures" / "probes" / "joints"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "jointprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "jointprobe_roboguide.txt"
PROGRAM = "JPPROBE"
NINES = "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]"
A = (10, -20, 30, 40, -50, 60)
B = (-30, 15, -10, -100, 70, -150)
TOLERANCE = 0.01  # deg: what a FINE stop leaves on ROBOGUIDE (39.999996 read for 40)
ABB_TOLERANCE = 0.05  # deg: CJointT reads the measured joints, up to 0.04 from the target after a fine stop

# Worked out by hand: the axes of each target, then the first again; 1 + 10 (rax_2 > -30, rax_3 > 25); 1
# (rax_5 < -40); 40 + 60.
EXPECTED = {
    **{f"jpA{i}": v for i, v in enumerate(A, 1)},
    **{f"jpB{i}": v for i, v in enumerate(B, 1)},
    **{f"jpBack{i}": v for i, v in enumerate(A, 1)},
    "jpHigh": 11, "jpLow": 1, "jpSum": 100,
}  # fmt: skip
TOTALS = tuple(EXPECTED)


def axes(prefix: str) -> list[str]:
    return [f"        {prefix}{i}:=jpNow.robax.rax_{i};" for i in range(1, 7)]


MODULE = "\r\n".join([
    "MODULE JointProbe",
    "    ! CrossArm - probe of jointtargets read on the robot: see tools/make_joint_probe.py.",
    f"    CONST jointtarget jpTargetA:=[[{','.join(map(str, A))}],{NINES}];",
    f"    CONST jointtarget jpTargetB:=[[{','.join(map(str, B))}],{NINES}];",
    f"    CONST jointtarget jpHome:=[[0,0,0,0,-90,0],{NINES}];",
    "    PERS tooldata jpTool:=[TRUE,[[0,0,150],[1,0,0,0]],[2,[0,0,50],[1,0,0,0],0,0,0]];",
    "    VAR jointtarget jpNow;",
    "    VAR jointtarget jpKeep;",
    "    VAR bool jpBelow;",
    *[f"    VAR num {total}:=0;" for total in TOTALS],
    "",
    "    PROC JpProbe()",
    *[f"        {total}:=0;" for total in TOTALS],
    "        MoveAbsJ jpTargetA,v1000,fine,tool0;",
    "        jpNow:=CJointT();",
    *axes("jpA"),
    "        jpKeep:=jpNow;",
    "        IF jpNow.robax.rax_2>-30 THEN",
    "            jpHigh:=1;",
    "        ENDIF",
    "        IF jpNow.robax.rax_3>25 jpHigh:=jpHigh+10;",
    "        jpBelow:=jpNow.robax.rax_5<-40;",
    "        IF jpBelow jpLow:=1;",
    "        jpSum:=jpNow.robax.rax_4+jpNow.robax.rax_6;",
    "        MoveAbsJ jpTargetB,v1000,fine,tool0;",
    "        jpNow:=CJointT();",
    *axes("jpB"),
    "        MoveAbsJ jpHome,v1000,fine,jpTool;",
    "        MoveAbsJ jpKeep,v1000,fine,jpTool;",
    "        jpNow:=CJointT();",
    *axes("jpBack"),
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        VAR num v;",
    "        JpProbe;",
    '        Open "HOME:" \\File:="jointprobe.txt", file \\Write;',
    # through a copy: CrossArm takes Write for an instruction that may change what it is given
    *[line for total in TOTALS for line in (f"        v:={total};", f'        Write file, "{total} " \\Num:=v;')],
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="JointProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=["JpProbe"],
                     sources={"JointProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """Probe total -> the R[n] CrossArm gave it."""
    numbers = {a.rapid_name.upper(): a.number for a in result.registers}
    return {total: numbers[total.upper()] for total in EXPECTED}


def programs() -> dict[str, str]:
    return {info.program.name: write_ls(info.program) for info in conversion().programs}


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    for stale in PROBE.glob("*.LS"):
        stale.unlink()
    (PROBE / "JointProbe.mod").write_bytes(MODULE.encode("ascii"))
    for name, text in programs().items():
        (PROBE / f"{name}.LS").write_bytes(text.encode("ascii"))
        print(f"{name}.LS")
    for total, number in registers(conversion()).items():
        print(f"  R[{number}] {total} expected {EXPECTED[total]}")


def read_totals(text: str) -> dict[str, str]:
    totals = {}
    for line in text.splitlines():
        if line.strip():
            name, _, value = line.partition(" ")
            totals[name] = value.strip()
    return totals


def run() -> None:
    import roboguide
    import robotstudio

    write()
    RESULTS.mkdir(parents=True, exist_ok=True)
    home = robotstudio.home()
    print(f"RobotStudio: {robotstudio.run(PROBE / 'JointProbe.mod', 'Probe', 180, home)}")
    ABB_RESULT.write_text((home / "jointprobe.txt").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    names = list(programs())
    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)  # a copy from an earlier run: FTP does not replace it
        except Exception:  # noqa: BLE001, S110 - not there
            pass
    for name in names:
        print(f"ROBOGUIDE load {name}: {roboguide.load(PROBE / f'{name}.LS') or 'loaded'}")
    numbers = registers(conversion())
    print(f"ROBOGUIDE zero: {roboguide.zero(list(numbers.values()))}")
    print(f"ROBOGUIDE run {PROGRAM}: {roboguide.run(PROGRAM, 180)}")
    values = roboguide.numreg()
    FANUC_RESULT.write_text("".join(f"{total} {values.get(number, float('nan')):g}\n"
                                    for total, number in numbers.items()), encoding="utf-8")  # fmt: skip
    roboguide.select()
    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)
        except Exception:  # noqa: BLE001, S110
            pass
    check()


def same(found: str | None, expected: float, tolerance: float = TOLERANCE) -> bool:
    try:
        return abs(float(found) - expected) <= tolerance  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def check() -> bool:
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    ok = True
    for total, expected in EXPECTED.items():
        agree = same(abb.get(total), expected, ABB_TOLERANCE) and same(fanuc.get(total), expected)
        ok &= agree
        print(f"{total:10s} RobotStudio {abb.get(total)}  ROBOGUIDE {fanuc.get(total)}  expected {expected}  "
              f"{'ok' if agree else 'DIFFERENT'}")  # fmt: skip
    return ok


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
