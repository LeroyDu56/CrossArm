# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the tool argument probe: a routine given a tool by reference that sets its tframe, a bool passed
by reference that the routine sets, an optional point (crossarm.convert.arguments, crossarm.convert.frame_writes).

TACONV.LS is converted by CrossArm from ToolArgProbe.mod (without --karel), on ROBOGUIDE:

- TaLength(INOUT tooldata t, num nLen) sets t.tframe.trans.z and t.tframe.rot: given the tool's number,
  `PR[F]=UTOOL[AR[1]]`, `PR[F,3]=AR[2]`, `PR[F,4..6]=0`, `UTOOL[AR[1]]=PR[F]`; called for two tools with a length
  read on the robot (CRobT), the caller then moves with each;
- TaCheck(num nLim, INOUT bool bOk \\robtarget Pt): the caller's flag passed as 1 / 0 (`IF (F[n]=ON) THEN R[k]=1 ELSE
  R[k]=0 ENDIF`), set by the routine in its copy, read back (`F[n]=(R[k]=1)`); the optional point given once
  (`PR[k]=P[j]`, 1) and moved to (`IF (AR[3]=1)`), not given the second time (0);
- p.trans := q.trans and p.rot := q.rot of points kept in position registers;

after each move the robot's flange is read in the world frame (CRobT(\\Tool:=tool0 \\WObj:=wobj0): PR[k]=LPOS) and
compared with where RAPID puts it, worked out here independently of CrossArm; the flag read back is kept in a
register (1 / 2). SETUP_FRAMES.LS runs first: the tools as saved are tens of millimetres from the ones the program
makes, so only what the routine writes puts the flange there.

  python tools/make_tool_arg_probe.py write    the module and the programs, in tests/fixtures/probes/toolarg
  python tools/make_tool_arg_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results stored
  python tools/make_tool_arg_probe.py check    the stored results against what was measured
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_karel_pose_probe import _about, _pose, _robtarget, gap, pose_inv, pose_mult
from make_karel_probe import _ftp, q_mul, q_unit, read_pr

from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program

PROBE = ROOT / "tests" / "fixtures" / "probes" / "toolarg"
RESULT = PROBE / "results" / "toolarg_roboguide.txt"
STAMP = datetime(2026, 1, 1)
CONV = "TACONV"
DOWN = (0.0, 0.0, 1.0, 0.0)  # a half turn about y: the tool's z down
P1 = ((1000.0, 0.0, 800.0), DOWN)  # where the length is read
P2 = ((1050.0, 80.0, 760.0), q_unit(q_mul(_about(2, 25.0), DOWN)))  # moved to with each tool
P3 = ((980.0, -90.0, 840.0), DOWN)  # the optional point
BASE = 650.0  # taLen := taM.trans.z - 650: 150 mm
PEN = ((0.0, 0.0, 100.0), (1.0, 0.0, 0.0, 0.0))  # as saved
CUP = ((20.0, 0.0, 140.0), q_unit(_about(1, 30.0)))  # as saved: turned 30 deg about y
CUP_EXTRA = 30.0  # TaLength taCup, taLen + 30
SEEN = ("taF1", "taF2", "taF3", "taF4")


MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE ToolArgProbe",
    "    ! CrossArm - tool argument probe: see tools/make_tool_arg_probe.py.",
    f"    PERS tooldata taPen:=[TRUE,{_pose(PEN)},[2,[0,0,50],[1,0,0,0],0,0,0]];",
    f"    PERS tooldata taCup:=[TRUE,{_pose(CUP)},[2,[0,0,50],[1,0,0,0],0,0,0]];",
    f"    CONST robtarget taP1:={_robtarget(P1[0], P1[1])};",
    f"    CONST robtarget taP2:={_robtarget(P2[0], P2[1])};",
    f"    CONST robtarget taP3:={_robtarget(P3[0], P3[1])};",
    "    VAR robtarget taM;",
    "    VAR robtarget taCopy;",
    *(f"    VAR robtarget {name};" for name in SEEN),
    "    VAR num taLen:=0;",
    "    VAR bool taOk:=FALSE;",
    "    VAR num taOk1:=0;",
    "    VAR num taOk2:=0;",
    "    VAR num taDone:=0;",
    "",
    "    PROC TaConv()",
    "        taDone:=0;",
    "        MoveJ taP1,v500,fine,tool0;",
    "        taM:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    f"        taLen:=taM.trans.z-{BASE:g};",
    "        TaLength taPen,taLen;",
    f"        TaLength taCup,taLen+{CUP_EXTRA:g};",
    "        MoveL taP2,v500,fine,taPen;",
    "        taF1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        MoveL taP2,v500,fine,taCup;",
    "        taF2:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        taOk:=FALSE;",
    "        TaCheck taLen,taOk\\Pt:=taP3;",
    "        taF3:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        IF taOk THEN",
    "            taOk1:=1;",
    "        ELSE",
    "            taOk1:=2;",
    "        ENDIF",
    "        TaCheck taLen+1000,taOk;",
    "        IF taOk THEN",
    "            taOk2:=1;",
    "        ELSE",
    "            taOk2:=2;",
    "        ENDIF",
    "        taCopy:=taF3;",
    "        taCopy.trans:=taF1.trans;",
    "        taCopy.rot:=taF2.rot;",
    "        MoveL taCopy,v500,fine,tool0;",
    "        taF4:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        taDone:=1;",
    "    ENDPROC",
    "",
    "    PROC TaLength(INOUT tooldata t,num nLen)",
    "        t.tframe.trans.z:=nLen;",
    "        t.tframe.rot:=[1,0,0,0];",
    "    ENDPROC",
    "",
    "    PROC TaCheck(num nLim,INOUT bool bOk\\robtarget Pt)",
    "        IF Present(Pt) MoveL Pt,v500,fine,tool0;",
    "        bOk:=nLim<500;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

PROGRAMS = (CONV, "TALENGTH", "TACHECK")


def _program(name: str, lines: list[str], comment: str) -> Program:
    return Program(name, [Instruction(text) for text in lines], attributes=Attributes(comment=comment, created=STAMP))


def conversion(folder: Path):
    """ToolArgProbe.mod converted as `crossarm convert` does: TACONV.LS, TALENGTH.LS, TACHECK.LS, SETUP_FRAMES.LS."""
    from crossarm import pipeline
    from crossarm.convert import ConversionConfig

    (PROBE / "ToolArgProbe.mod").write_bytes(MODULE.encode("ascii"))
    run = pipeline.run([PROBE / "ToolArgProbe.mod"], folder, ConversionConfig(timestamp=STAMP), log=lambda _: None)
    result = run.tasks[0].result
    assert result is not None and not [n for n in result.notes if n.kind == "TODO"], result and result.notes
    return result


def kept(result) -> dict[str, int]:
    """taM... -> the PR CrossArm keeps it in; TADONE, TAOK1, TAOK2 -> their R."""
    found = {a.rapid_name.upper(): a.number for a in result.point_registers}
    for name in ("taDone", "taOk1", "taOk2"):
        found[name.upper()] = next(a.number for a in result.registers if a.rapid_name == name)
    return found


NUMBERS = ("TADONE", "TAOK1", "TAOK2")


def prep_program(numbers: dict[str, int]) -> Program:
    """TAPREP: the registers CrossArm keeps points in made Cartesian first (another probe may leave joints there)."""
    lines = ["UFRAME_NUM=0", "UTOOL_NUM=1"] + [f"PR[{k}]=LPOS" for name, k in sorted(numbers.items()) if name not in NUMBERS]
    return _program("TAPREP", lines, "tool argument probe prep")


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="crossarm_toolarg_") as temp:
        result = conversion(Path(temp))
        for name in (*PROGRAMS, "SETUP_FRAMES"):
            (PROBE / f"{name}.LS").write_bytes((Path(temp) / f"{name}.LS").read_bytes())
    program = prep_program(kept(result))
    (PROBE / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
    for name, number in kept(result).items():
        print(f"  {'R' if name in NUMBERS else 'PR'}[{number}] {name}")
    print(f"probe written to {PROBE}")


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------


def measure() -> dict[str, str]:
    import roboguide

    write()
    with tempfile.TemporaryDirectory(prefix="crossarm_toolarg_") as temp:
        numbers = kept(conversion(Path(temp)))
    names = ["TAPREP", "SETUP_FRAMES", *PROGRAMS]
    found: dict[str, str] = {}
    for name in names:
        roboguide.release(name)
    roboguide.select()
    for name in names:
        _ftp(f"DELE {name.lower()}.tp")
    try:
        for name in names:
            found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
        found["TAPREP_run"] = roboguide.run("TAPREP", 60)
        found["SETUP_FRAMES_run"] = roboguide.run("SETUP_FRAMES", 60, resumes=1)
        roboguide.zero([numbers[name] for name in NUMBERS])
        found["conv_run"] = roboguide.run(CONV, 240)
        registers = roboguide.numreg()
        for name in NUMBERS:
            found[name.lower()] = f"{registers.get(numbers[name], float('nan')):g}"
        posreg = roboguide.page("md/POSREG.VA")
        for name in ("TAM", *(s.upper() for s in SEEN)):
            found[name] = read_pr(posreg, numbers[name])
        return found
    finally:
        roboguide.select()
        for name in names:
            roboguide.release(name)
        roboguide.select()
        for name in names:
            _ftp(f"DELE {name.lower()}.tp")


def expected(found: dict[str, str]) -> dict[str, tuple]:
    """Where RAPID puts the flange after each move, from the length the robot read (taM)."""
    length = float(found["TAM"].split()[2]) - BASE
    pen = ((PEN[0][0], PEN[0][1], length), (1.0, 0.0, 0.0, 0.0))
    cup = ((CUP[0][0], CUP[0][1], length + CUP_EXTRA), (1.0, 0.0, 0.0, 0.0))
    target = (P2[0], q_unit(P2[1]))
    f1 = pose_mult(target, pose_inv(pen))
    f2 = pose_mult(target, pose_inv(cup))
    return {"TAF1": f1, "TAF2": f2, "TAF3": (P3[0], q_unit(P3[1])), "TAF4": (f1[0], f2[1])}


def verdict(found: dict[str, str]) -> str:
    wrong = [f"{n} {found.get(f'{n}_load')} {found.get(f'{n}_run')}" for n in ("TAPREP", "SETUP_FRAMES")
             if found.get(f"{n}_load") != "loaded" or found.get(f"{n}_run") != "done"]  # fmt: skip
    wrong += [f"{n}: {found.get(f'{n}_load')}" for n in PROGRAMS[1:] if found.get(f"{n}_load") != "loaded"]
    if found.get(f"{CONV}_load") != "loaded" or found.get("conv_run") != "done" or found.get("tadone") != "1":
        wrong.append(f"{CONV}: {found.get(f'{CONV}_load')}, {found.get('conv_run')}, done {found.get('tadone')}")
        return "; ".join(wrong)
    mm, deg = gap(found["TAM"], (P1[0], q_unit(P1[1])))
    if mm > 0.01 or deg > 0.01:
        wrong.append(f"TAM {found['TAM']}: {mm:.3f} mm, {deg:.3f} deg from where it was sent")
    for name, value in expected(found).items():
        mm, deg = gap(found[name], value)
        if mm > 0.01 or deg > 0.01:
            wrong.append(f"{name} {found[name]}: {mm:.3f} mm, {deg:.3f} deg from RAPID")
    if (found.get("taok1"), found.get("taok2")) != ("1", "2"):
        wrong.append(f"bool read back: {found.get('taok1')} {found.get('taok2')}, RAPID 1 2")
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    worst = max(gap(found[n], e) for n, e in expected(found).items())
    return (f"tframe written through UTOOL[AR[1]] for two tools, bool read back, optional point, trans / rot copies:"
            f" {len(expected(found))} flange positions within {worst[0]:.3f} mm / {worst[1]:.3f} deg")


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
    print(f"FAIL {problem}" if problem else f"toolarg probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
