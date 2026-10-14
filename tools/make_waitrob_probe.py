# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the WaitRob probe: WaitRob \\InPos / \\ZeroSpeed after a move through a zone.

WaitProbe.mod, converted by CrossArm, moves the robot through a zone (z100) to a corner three times and reads its
position (CRobT, PR[k]=LPOS) on the next line: once without a wait, once after WaitRob \\InPos, once after a routine
whose last move goes through a zone and WaitRob \\ZeroSpeed. RAPID reads the corner after a WaitRob: the zone point
becomes a stop point, the robot stands on it. CrossArm writes each WaitRob as a zero incremental FINE move
(`PR[k]=LPOS`, `PR[k]=PR[k]-PR[k]`, `L PR[k] 100mm/sec FINE INC`).

Measured before (raw programs, 2026-10-14): the line after an L CNT100 at 100 mm/s runs 9.3 mm before the point,
also when the move is the last of a called program; `R[n]=$MOR_GRP[1].$ROB_MOVE` and
`WAIT ($MOR_GRP[1].$ROB_MOVE=0)` load but stop on VARS-034 on this cell; the zero incremental FINE move: on the point
(0.000 mm), in the program and after a CALL, and nothing when the robot already stands (L and J alike).

  python tools/make_waitrob_probe.py write    the module and the programs, in tests/fixtures/probes/waitrob
  python tools/make_waitrob_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results stored
  python tools/make_waitrob_probe.py check    the stored results against what was measured
"""

import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, Position, Program
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "waitrob"
RESULT = PROBE / "results" / "waitrob_roboguide.txt"
PROGRAM = "WAITPROBE"
SETUP = "WPSETUP"
STAMP = datetime(2026, 1, 1)
CORNER = (1400.0, -200.0, 800.0)
SEEN = ("wpNoWait", "wpInPos", "wpZeroSpeed")  # read on the next line: without a wait, after each WaitRob
_Q = "[0,0.3826834,0.9238795,0]"
MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE WaitProbe",
    "    ! CrossArm - WaitRob probe: see tools/make_waitrob_probe.py.",
    f"    CONST robtarget wpStart:=[[1100,-200,800],{_Q},[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    f"    CONST robtarget wpCorner:=[[1400,-200,800],{_Q},[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    f"    CONST robtarget wpEnd:=[[1400,200,800],{_Q},[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    "    VAR robtarget wpNoWait;",
    "    VAR robtarget wpInPos;",
    "    VAR robtarget wpZeroSpeed;",
    "    VAR num nDone:=0;",
    "",
    "    PROC WaitProbe()",
    "        nDone:=0;",
    "        MoveJ wpStart,v1000,fine,tool0;",
    "        MoveL wpCorner,v100,z100,tool0;",
    "        wpNoWait:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        MoveL wpStart,v1000,fine,tool0;",
    "        MoveL wpCorner,v100,z100,tool0;",
    "        WaitRob\\InPos;",
    "        wpInPos:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        MoveL wpStart,v1000,fine,tool0;",
    "        ToCorner;",
    "        WaitRob\\ZeroSpeed;",
    "        wpZeroSpeed:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        MoveL wpEnd,v100,fine,tool0;",
    "        nDone:=1;",
    "    ENDPROC",
    "",
    "    PROC ToCorner()",
    "        MoveL wpCorner,v100,z100,tool0;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip
ROUTINES = ["WaitProbe", "ToCorner"]


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="WaitProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=STAMP), routines=ROUTINES,
                     sources={"WaitProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    return result


def numbers(result: ConversionResult) -> dict[str, int]:
    """The position register of each point read, and the register of nDone."""
    found = {name: a.number for a in result.point_registers for name in SEEN if a.rapid_name == name.upper()}
    found.update({a.rapid_name: a.number for a in result.registers if a.rapid_name == "nDone"})
    if set(found) != {*SEEN, "nDone"}:
        raise RuntimeError(f"registers found for {sorted(found)} only")
    return found


def setup_program() -> Program:
    """UTOOL[1] = tool0 (zero), as the moves of the probe use it."""
    lines = [Instruction("PR[20]=P[1]"), Instruction("UTOOL[1]=PR[20]")]
    positions = [Position(1, 0, 1, CartesianPosition(0.0, 0.0, 0.0, 0.0, 0.0, 0.0))]
    return Program(SETUP, list(lines), positions, Attributes(comment="WaitRob setup", created=STAMP))


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "WaitProbe.mod").write_bytes(MODULE.encode("ascii"))
    for info in conversion().programs:
        (PROBE / f"{info.program.name}.LS").write_bytes(write_ls(info.program).encode("ascii"))
    (PROBE / f"{SETUP}.LS").write_bytes(write_ls(setup_program()).encode("ascii"))


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------


def measure() -> dict[str, str]:
    import roboguide
    from make_karel_probe import read_pr

    write()
    found_numbers = numbers(conversion())
    programs = [SETUP, "TOCORNER", PROGRAM]
    found: dict[str, str] = {}
    for name in programs:
        roboguide.release(name)
    roboguide.select()
    try:
        for name in programs:
            found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
        if any(value != "loaded" for value in found.values()):
            return found
        found["setup_run"] = roboguide.run(SETUP, 60)
        roboguide.zero([found_numbers["nDone"]])
        found["run"] = roboguide.run(PROGRAM, 120)
        found["nDone"] = f"{roboguide.numreg().get(found_numbers['nDone'], float('nan')):g}"
        posreg = roboguide.page("md/POSREG.VA")
        for name in SEEN:
            found[name] = read_pr(posreg, found_numbers[name])
    finally:
        roboguide.select()
        for name in programs:
            roboguide.release(name)
        roboguide.select()
        for name in programs:
            try:
                roboguide.delete(name)
            except Exception as exc:  # noqa: BLE001  # not loaded
                print(f"{name} not deleted: {exc}")
    return found


def distances(found: dict[str, str]) -> dict[str, float]:
    """mm from the corner of each position read."""
    out = {}
    for name in SEEN:
        try:
            out[name] = math.dist([float(v) for v in found[name].split()[:3]], CORNER)
        except (KeyError, ValueError):
            out[name] = math.nan
    return out


def verdict(found: dict[str, str]) -> str:
    wrong = [f"{k}: {v}" for k, v in found.items() if k.endswith(("_load", "_run")) and v not in ("loaded", "done")]
    if found.get("run") != "done" or found.get("nDone") != "1":
        wrong.append(f"run {found.get('run')}, nDone {found.get('nDone')}")
        return "; ".join(wrong)
    d = distances(found)
    if not d["wpNoWait"] > 1.0:  # the line after a CNT move runs before the point: the probe tells the waits apart
        wrong.append(f"read {d['wpNoWait']:.3f} mm from the corner without a wait, more than 1 mm before")
    for name in SEEN[1:]:
        if not d[name] <= 0.01:
            wrong.append(f"{name} read {d[name]:.3f} mm from the corner, RAPID on it")
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    d = distances(found)
    return (f"read {d['wpNoWait']:.1f} mm before the corner without a wait, on it after WaitRob \\InPos"
            f" ({d['wpInPos']:.3f} mm) and after a call + \\ZeroSpeed ({d['wpZeroSpeed']:.3f} mm)")


def run() -> str:
    found = measure()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text("".join(f"{k} {v}\n" for k, v in found.items()), encoding="ascii")
    return check()


def stored() -> dict[str, str]:
    return dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())


def check() -> str:
    found = stored()
    problem = verdict(found)
    print(f"FAIL {problem}" if problem else f"waitrob probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
