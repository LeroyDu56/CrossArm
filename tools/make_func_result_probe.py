# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the provided-functions probe: functions the backup does not declare, provided as TP programs
(external_routines with "returns"), whose results start a calibration.

FuncResultProbe.mod reads two points on the robot (CRobT), then calls four functions it does not declare:

    frGap := FrGap(frM1, frM2)                    num: CALL XFRGAP(a,b,k), the program writes R[AR[3]]
    frMid := FrMid(frM1, frM2)                    robtarget: PR[AR[3]] written whole, then x and y
    frRing.uframe := FrFit(frA, frB, frGap)       pose: points known now copied into registers, a num passed
    frProbe.tframe.trans := FrOffset(2)           pos: x, y, z written in PR[AR[2],1..3] only

and uses them: a move to frMid, frHub.uframe.trans := frMid.trans, a move in frHub, one in frRing, one with
frProbe. Converted WITHOUT --karel (all TP). The provided programs are written here by hand, as an integrator
would, reading their points as PR[AR[n]] and writing their result where AR[last] says. The register the pos
result is given in is made a joint one first (PR[k]=JPOS): a pos is written and read back component by component.

After each move the flange is read in the world (CRobT(\\Tool:=tool0 \\WObj:=wobj0): PR[k]=LPOS), and compared
with where RAPID puts it, worked out here (Python, from the points read and what the programs compute).

  python tools/make_func_result_probe.py write    the programs, in tests/fixtures/probes/funcresult
  python tools/make_func_result_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results stored
  python tools/make_func_result_probe.py check    the stored result against RAPID
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_karel_pose_probe import _pose, _robtarget, gap, pose, pose_inv, pose_mult
from make_karel_probe import _ftp, q_unit, read_pr

from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program

PROBE = ROOT / "tests" / "fixtures" / "probes" / "funcresult"
RESULT = PROBE / "results" / "funcresult_roboguide.txt"
STAMP = datetime(2026, 1, 1)
CONV = "FRCONV"
DOWN = (0.0, 0.0, 1.0, 0.0)  # a half turn about y: the tool's z down
A = ((1000.0, -40.0, 800.0), DOWN)  # frA, frB: where the two points are read (tool0)
B = ((1060.0, 40.0, 800.0), DOWN)
SAVED = ((1000.0, 0.0, 800.0), DOWN)  # the work objects as saved
IN_FRAME = ((40.0, 30.0, -60.0), (1.0, 0.0, 0.0, 0.0))  # frP: 60 mm above the frame's origin (its z down)
RING_WPR = (180.0, 0.0, -160.0)  # what XFRFIT writes as the ring's orientation
TIP = (0.0, 0.0, 150.0)  # frProbe as saved
FUNCTIONS = {"FrGap": ("XFRGAP", "num"), "FrMid": ("XFRMID", "robtarget"), "FrFit": ("XFRFIT", "pose"),
             "FrOffset": ("XFROFS", "pos")}  # fmt: skip
SEEN = ("frF1", "frF2", "frF3", "frF4")

MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE FuncResultProbe",
    "    ! CrossArm - provided functions probe: see tools/make_func_result_probe.py.",
    f"    PERS tooldata frProbe:=[TRUE,[[{','.join(f'{v:g}' for v in TIP)}],[1,0,0,0]],[3,[0,0,50],[1,0,0,0],0,0,0]];",
    f"    PERS wobjdata frHub:=[FALSE,TRUE,\"\",{_pose(SAVED)},[[0,0,0],[1,0,0,0]]];",
    f"    PERS wobjdata frRing:=[FALSE,TRUE,\"\",{_pose(SAVED)},[[0,0,0],[1,0,0,0]]];",
    f"    CONST robtarget frA:={_robtarget(A[0], A[1])};",
    f"    CONST robtarget frB:={_robtarget(B[0], B[1])};",
    f"    CONST robtarget frP:={_robtarget(IN_FRAME[0], IN_FRAME[1])};",
    "    VAR robtarget frM1;",
    "    VAR robtarget frM2;",
    "    VAR robtarget frMid;",
    *(f"    VAR robtarget {name};" for name in SEEN),
    "    VAR num frGap:=0;",
    "    VAR num frDone:=0;",
    "",
    "    PROC FrConv()",
    "        frDone:=0;",
    "        MoveJ frA,v500,fine,tool0;",
    "        frM1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        MoveL frB,v500,fine,tool0;",
    "        frM2:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        frGap:=FrGap(frM1,frM2);",
    "        frMid:=FrMid(frM1,frM2);",
    "        MoveL frMid,v500,fine,tool0;",
    "        frF1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        frHub.uframe.trans:=frMid.trans;",
    "        MoveL frP,v500,fine,tool0\\WObj:=frHub;",
    "        frF2:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        frRing.uframe:=FrFit(frA,frB,frGap);",
    "        MoveL frP,v500,fine,tool0\\WObj:=frRing;",
    "        frF3:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        frProbe.tframe.trans:=FrOffset(2);",
    "        MoveL frB,v500,fine,frProbe;",
    "        frF4:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        frDone:=1;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip


def _program(name: str, lines: list[str], comment: str) -> Program:
    return Program(name, [Instruction(text) for text in lines], attributes=Attributes(comment=comment, created=STAMP))


def provided_programs() -> list[Program]:
    """The integrator's programs: their points read as PR[AR[n]], their result written where AR[last] says."""
    return [
        _program("XFRGAP", ["R[AR[3]]=PR[AR[2],1]-PR[AR[1],1]"], "provided FrGap"),
        _program("XFRMID", ["PR[AR[3]]=PR[AR[1]]", "PR[AR[3],1]=PR[AR[1],1]+PR[AR[2],1]", "PR[AR[3],1]=PR[AR[3],1]/2",
                            "PR[AR[3],2]=PR[AR[1],2]+PR[AR[2],2]", "PR[AR[3],2]=PR[AR[3],2]/2"], "provided FrMid"),
        _program("XFRFIT", ["PR[AR[4]]=PR[AR[1]]", "PR[AR[4],3]=PR[AR[4],3]+AR[3]", f"PR[AR[4],4]={RING_WPR[0]:g}",
                            f"PR[AR[4],5]={RING_WPR[1]:g}", f"PR[AR[4],6]=({RING_WPR[2]:g})"], "provided FrFit"),
        _program("XFROFS", ["PR[AR[2],1]=0", "PR[AR[2],2]=0", "PR[AR[2],3]=AR[1]*10", "PR[AR[2],3]=PR[AR[2],3]+100"],
                 "provided FrOffset"),
    ]  # fmt: skip


def conversion(folder: Path):
    """FuncResultProbe.mod converted (no --karel) with the four functions provided: FRCONV.LS, SETUP_FRAMES.LS."""
    from crossarm import pipeline
    from crossarm.convert import ConversionConfig
    from crossarm.convert.external import ProvidedRoutine

    (PROBE / "FuncResultProbe.mod").write_bytes(MODULE.encode("ascii"))
    provided = {name.upper(): ProvidedRoutine(name, program, None, kind) for name, (program, kind) in FUNCTIONS.items()}
    run = pipeline.run([PROBE / "FuncResultProbe.mod"], folder,
                       ConversionConfig(timestamp=STAMP, external_routines=provided), log=lambda _: None)  # fmt: skip
    result = run.tasks[0].result
    assert result is not None and not [n for n in result.notes if n.kind == "TODO"], result and result.notes
    assert not result.karel_programs
    return result


def kept(result) -> dict[str, int]:
    """frM1... XFROFS.RESULT -> the PR CrossArm keeps it in; FRDONE, FRGAP -> their R."""
    found = {a.rapid_name.upper(): a.number for a in result.point_registers}
    for name in ("frDone", "frGap"):
        found[name.upper()] = next(a.number for a in result.registers if a.rapid_name == name)
    return found


def prep_program(numbers: dict[str, int]) -> Program:
    """FRPREP: CrossArm's position registers made Cartesian (another probe may leave joints there), but the one the
    pos result is given in made a joint one: a pos is written and read component by component."""
    pos = numbers["XFROFS.RESULT"]
    lines = ["UFRAME_NUM=0", "UTOOL_NUM=1"] + [f"PR[{k}]=LPOS" for name, k in sorted(numbers.items())
                                              if name not in ("FRDONE", "FRGAP") and k != pos] + [f"PR[{pos}]=JPOS"]  # fmt: skip
    return _program("FRPREP", lines, "func result probe prep")


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="crossarm_funcresult_") as temp:
        result = conversion(Path(temp))
        for name in (CONV, "SETUP_FRAMES"):
            (PROBE / f"{name}.LS").write_bytes((Path(temp) / f"{name}.LS").read_bytes())
    for program in [prep_program(kept(result)), *provided_programs()]:
        (PROBE / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
    for name, number in kept(result).items():
        print(f"  {'R' if name in ('FRDONE', 'FRGAP') else 'PR'}[{number}] {name}")
    print(f"probe written to {PROBE}")


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------


def measure() -> dict[str, str]:
    import roboguide

    write()
    with tempfile.TemporaryDirectory(prefix="crossarm_funcresult_") as temp:
        numbers = kept(conversion(Path(temp)))
    names = ["FRPREP", "SETUP_FRAMES", CONV, *(p.name for p in provided_programs())]
    found: dict[str, str] = {}
    for name in names:
        roboguide.release(name)
    roboguide.select()
    for name in names:
        _ftp(f"DELE {name.lower()}.tp")
    try:
        for name in names:
            found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
        found["FRPREP_run"] = roboguide.run("FRPREP", 60)
        found["SETUP_FRAMES_run"] = roboguide.run("SETUP_FRAMES", 60, resumes=1)
        roboguide.zero([numbers["FRDONE"], numbers["FRGAP"]])
        found["conv_run"] = roboguide.run(CONV, 240)
        registers = roboguide.numreg()
        found["conv_done"] = f"{registers.get(numbers['FRDONE'], float('nan')):g}"
        found["FRGAP"] = f"{registers.get(numbers['FRGAP'], float('nan')):g}"
        posreg = roboguide.page("md/POSREG.VA")
        for name in ("FRM1", "FRM2", "FRMID", *(s.upper() for s in SEEN)):
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
    """Where RAPID puts the flange after each move, from the points the robot read (frM1, frM2) and what the
    provided programs compute."""
    m1 = pose(tuple(float(v) for v in found["FRM1"].split()))
    m2 = pose(tuple(float(v) for v in found["FRM2"].split()))
    gap_x = m2[0][0] - m1[0][0]
    mid = (((m1[0][0] + m2[0][0]) / 2, (m1[0][1] + m2[0][1]) / 2, m1[0][2]), m1[1])
    hub = (mid[0], q_unit(SAVED[1]))
    ring = pose((A[0][0], A[0][1], A[0][2] + gap_x, *RING_WPR))
    tool = ((0.0, 0.0, 2 * 10 + 100.0), (1.0, 0.0, 0.0, 0.0))
    target = (IN_FRAME[0], q_unit(IN_FRAME[1]))
    return {
        "FRMID": mid,
        "FRF1": mid,
        "FRF2": pose_mult(hub, target),
        "FRF3": pose_mult(ring, target),
        "FRF4": pose_mult((B[0], q_unit(B[1])), pose_inv(tool)),
    }


def verdict(found: dict[str, str]) -> str:
    wrong = [f"{name}: {found.get(f'{name}_load')}" for name in ["FRPREP", "SETUP_FRAMES", CONV, *(p.name for p in provided_programs())]
             if found.get(f"{name}_load") != "loaded"]  # fmt: skip
    wrong += [f"{n} {found.get(f'{n}_run')}" for n in ("FRPREP", "SETUP_FRAMES") if found.get(f"{n}_run") != "done"]
    if found.get("conv_run") != "done" or found.get("conv_done") != "1":
        wrong.append(f"{CONV}: {found.get('conv_run')}, done {found.get('conv_done')}")
        return "; ".join(wrong)
    for name, target in (("FRM1", A), ("FRM2", B)):  # the points read where the robot was sent
        mm, deg = gap(found[name], (target[0], q_unit(target[1])))
        if mm > 0.01 or deg > 0.01:
            wrong.append(f"{name} {found[name]}: {mm:.3f} mm, {deg:.3f} deg from where it was sent")
    m1, m2 = (float(found[n].split()[0]) for n in ("FRM1", "FRM2"))
    if abs(float(found["FRGAP"]) - (m2 - m1)) > 0.01:
        wrong.append(f"FRGAP {found['FRGAP']} (RAPID {m2 - m1:.3f})")
    for name, value in expected(found).items():
        mm, deg = gap(found[name], value)
        if mm > 0.01 or deg > 0.01:
            wrong.append(f"{name} {found[name]}: {mm:.3f} mm, {deg:.3f} deg from RAPID")
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    worst = max(gap(found[n], e) for n, e in expected(found).items())
    return (f"num, robtarget, pose, pos results of provided TP programs (R[AR[n]], PR[AR[n]], PR[AR[n],i]): the gap"
            f" and {len(expected(found))} poses within {worst[0]:.3f} mm / {worst[1]:.3f} deg")


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
    print(f"FAIL {problem}" if problem else f"funcresult probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
