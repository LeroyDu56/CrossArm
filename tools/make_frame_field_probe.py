# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the frame field probe: a tool's tframe and a work object's uframe written part by part at run
time, and a frame copied to a series of work objects (crossarm.convert.frame_writes).

FFCONV.LS is converted by CrossArm from FrameFieldProbe.mod with --karel, on ROBOGUIDE:

- a tool's tframe.trans set from a point kept in a position register (Offs of a point known now by a height read
  on the robot), then its x alone from a value TP computes: `PR[F]=UTOOL[n]`, `PR[F,1..3]=...`, `UTOOL[n]=PR[F]`,
  and a move with it;
- a work object's uframe.trans and uframe.rot set from a point read on the robot (CRobT: PR[k]=LPOS), its oframe
  set to the identity: `PR[F]=UFRAME[n]`, `PR[F,4..6]=PR[k,4..6]`, `UFRAME[n]=PR[F]`, and a move in it;
- that uframe copied to nine work objects (`PR[F]=UFRAME[n]`, `UFRAME[m]=PR[F]`), more than the controller's
  UFRAME numbers: the last ones kept in bank registers (`PR[bank]=PR[F]`); two of them with an oframe other than
  the identity, multiplied in by KAREL (CA_POSEMULT); one set whole from [the trans of a point, the rot of a frame];
  moves in them;

after each move the robot's flange is read in the world frame (CRobT(\\Tool:=tool0 \\WObj:=wobj0): PR[k]=LPOS) and
compared with where RAPID puts it, worked out here from the points read with quaternions, independently of
CrossArm. SETUP_FRAMES.LS runs first: the frames as saved are tens of millimetres and degrees from the ones the
program makes, so only the frames it loads put the flange there.

  python tools/make_frame_field_probe.py write    the module and the programs, in tests/fixtures/probes/framefield
  python tools/make_frame_field_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results stored
  python tools/make_frame_field_probe.py check    the stored results against what was measured
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_karel_pose_probe import _about, _pose, _robtarget, gap, pose, pose_inv, pose_mult
from make_karel_probe import _ftp, q_mul, q_unit, read_pr

from crossarm.fanuc.ktrans import KarelRequest, export
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program

PROBE = ROOT / "tests" / "fixtures" / "probes" / "framefield"
RESULT = PROBE / "results" / "framefield_roboguide.txt"
STAMP = datetime(2026, 1, 1)
LIBRARY = ["CA_POSEMULT"]
CONV = "FFCONV"
DOWN = (0.0, 0.0, 1.0, 0.0)  # a half turn about y: the tool's z down
TURNED = q_unit(q_mul(_about(2, 20.0), DOWN))  # down, turned 20 deg about the world's z
T1 = ((950.0, -60.0, 820.0), TURNED)  # the pallet's corner, touched with tool0
T2 = ((1050.0, 80.0, 780.0), DOWN)  # where the stylus' height is read
TIP = (0.0, 0.0, 150.0)  # ffTipNom: the stylus as drawn
TIP_Z = 760.0  # ffOfs:=Offs(ffTipNom, 0, 0, ffM2.trans.z - 760): + 20 mm
TIP_X = 1040.0  # ffStylus.tframe.trans.x := ffM2.trans.x - 1040: 10 mm
IN_FRAME = ((40.0, 30.0, -60.0), (1.0, 0.0, 0.0, 0.0))  # ffP: 60 mm above the frame's origin (its z down)
SAVED = ((1000.0, 0.0, 800.0), DOWN)  # the work objects as saved
NESTS = 9
OFRAMES = {8: ((30.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)), 9: ((0.0, 20.0, 0.0), q_unit(_about(2, 30.0)))}
MOVED = (1, 8, 9, 2, 3, 4, 5, 6, 7)  # the nests the moves use, in this order: 6 and 7 past the UFRAME numbers (banks)
SEEN = ("ffF1", "ffF2", *(f"ffF{3 + i}" for i in range(len(MOVED))))
IDENTITY = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))


def _nest(i: int) -> str:
    return (f"    PERS wobjdata ffNest{i}:=[FALSE,TRUE,\"\",{_pose(SAVED)},{_pose(OFRAMES.get(i, IDENTITY))}];")


MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE FrameFieldProbe",
    "    ! CrossArm - frame field probe: see tools/make_frame_field_probe.py.",
    f"    PERS tooldata ffStylus:=[TRUE,[[{','.join(f'{v:g}' for v in TIP)}],[1,0,0,0]],[3,[0,0,50],[1,0,0,0],0,0,0]];",
    f"    PERS wobjdata ffPallet:=[FALSE,TRUE,\"\",{_pose(SAVED)},[[0,0,0],[1,0,0,0]]];",
    *(_nest(i) for i in range(1, NESTS + 1)),
    f"    CONST robtarget ffT1:={_robtarget(T1[0], T1[1])};",
    f"    CONST robtarget ffT2:={_robtarget(T2[0], T2[1])};",
    f"    CONST robtarget ffTipNom:={_robtarget(TIP, (1.0, 0.0, 0.0, 0.0))};",
    f"    CONST robtarget ffP:={_robtarget(IN_FRAME[0], IN_FRAME[1])};",
    "    VAR robtarget ffM1;",
    "    VAR robtarget ffM2;",
    "    VAR robtarget ffOfs;",
    *(f"    VAR robtarget {name};" for name in SEEN),
    "    VAR num ffDone:=0;",
    "",
    "    PROC FfConv()",
    "        ffDone:=0;",
    "        MoveJ ffT2,v500,fine,tool0;",
    "        ffM2:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    f"        ffOfs:=Offs(ffTipNom,0,0,ffM2.trans.z-{TIP_Z:g});",
    "        ffStylus.tframe.trans:=ffOfs.trans;",
    f"        ffStylus.tframe.trans.x:=ffM2.trans.x-{TIP_X:g};",
    "        MoveL ffT2,v500,fine,ffStylus;",
    "        ffF1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        MoveJ ffT1,v500,fine,tool0;",
    "        ffM1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        ffPallet.uframe.trans:=ffM1.trans;",
    "        ffPallet.uframe.rot:=ffM1.rot;",
    "        ffPallet.oframe:=[[0,0,0],[1,0,0,0]];",
    "        MoveL ffP,v500,fine,tool0\\WObj:=ffPallet;",
    "        ffF2:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    *(f"        ffNest{i}.uframe:=ffPallet.uframe;" for i in range(1, NESTS + 1) if i != 2),
    "        ffNest2.uframe:=[ffM2.trans,ffPallet.uframe.rot];",
    *(line for k, i in enumerate(MOVED) for line in (
        f"        MoveL ffP,v500,fine,tool0\\WObj:=ffNest{i};",
        f"        {SEEN[2 + k]}:=CRobT(\\Tool:=tool0\\WObj:=wobj0);")),
    "        ffDone:=1;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip


def _program(name: str, lines: list[str], comment: str) -> Program:
    return Program(name, [Instruction(text) for text in lines], attributes=Attributes(comment=comment, created=STAMP))


def conversion(folder: Path):
    """FrameFieldProbe.mod converted with --karel as `crossarm convert` does: FFCONV.LS, SETUP_FRAMES.LS."""
    from crossarm import pipeline
    from crossarm.convert import ConversionConfig

    (PROBE / "FrameFieldProbe.mod").write_bytes(MODULE.encode("ascii"))
    run = pipeline.run([PROBE / "FrameFieldProbe.mod"], folder, ConversionConfig(timestamp=STAMP, karel=True),
                       log=lambda _: None)  # fmt: skip
    result = run.tasks[0].result
    assert result is not None and not [n for n in result.notes if n.kind == "TODO"], result and result.notes
    assert result.karel_programs == LIBRARY, result.karel_programs
    return result


def kept(result) -> dict[str, int]:
    """ffM1... CROSSARM.FRAME -> the PR CrossArm keeps it in; FFDONE -> its R."""
    found = {a.rapid_name.upper(): a.number for a in result.point_registers}
    found["FFDONE"] = next(a.number for a in result.registers if a.rapid_name == "ffDone")
    return found


def prep_program(numbers: dict[str, int]) -> Program:
    """FFPREP: the registers CrossArm keeps poses in made Cartesian first (another probe may leave joints there)."""
    lines = ["UFRAME_NUM=0", "UTOOL_NUM=1"] + [f"PR[{k}]=LPOS" for name, k in sorted(numbers.items()) if name != "FFDONE"]
    return _program("FFPREP", lines, "frame field probe prep")


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="crossarm_framefield_") as temp:
        result = conversion(Path(temp))
        for name in (CONV, "SETUP_FRAMES"):
            (PROBE / f"{name}.LS").write_bytes((Path(temp) / f"{name}.LS").read_bytes())
    program = prep_program(kept(result))
    (PROBE / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
    for name, number in kept(result).items():
        print(f"  {'R' if name == 'FFDONE' else 'PR'}[{number}] {name}")
    print(f"probe written to {PROBE}")


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------


def measure() -> dict[str, str]:
    import make_maketp_probe
    import roboguide

    write()
    with tempfile.TemporaryDirectory(prefix="crossarm_framefield_") as temp:
        numbers = kept(conversion(Path(temp)))
    names = ["FFPREP", "SETUP_FRAMES", CONV]
    pcs = [name.lower() for name in LIBRARY]
    found: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="crossarm_framefield_") as temp:
        work = Path(temp)
        out = export(LIBRARY, work, KarelRequest(make_maketp_probe.robot()), log=print)
        if len(out.compiled) != len(LIBRARY):
            raise RuntimeError(f"library not compiled: {out.problem or out.refused}")
        found["version"] = out.version
        for name in names:
            roboguide.release(name)
        roboguide.select()
        for name in names:
            _ftp(f"DELE {name.lower()}.tp")
        try:
            for name in pcs:
                found[f"{name}_load"] = _ftp("STOR", work / f"{name}.pc") or "loaded"
            for name in names:
                found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
            found["FFPREP_run"] = roboguide.run("FFPREP", 60)
            found["SETUP_FRAMES_run"] = roboguide.run("SETUP_FRAMES", 60, resumes=1)
            roboguide.zero([numbers["FFDONE"]])
            found["conv_run"] = roboguide.run(CONV, 240)
            found["conv_done"] = f"{roboguide.numreg().get(numbers['FFDONE'], float('nan')):g}"
            posreg = roboguide.page("md/POSREG.VA")
            for name in ("FFM1", "FFM2", "FFOFS", *(s.upper() for s in SEEN)):
                found[name] = read_pr(posreg, numbers[name])
            return found
        finally:
            roboguide.select()
            for name in names:
                roboguide.release(name)
            roboguide.select()
            for name in names:
                _ftp(f"DELE {name.lower()}.tp")
            for name in pcs:
                _ftp(f"DELE {name}.pc")
                _ftp(f"DELE {name}.vr")


def expected(found: dict[str, str]) -> dict[str, tuple]:
    """Where RAPID puts the flange after each move, from the points the robot read (ffM1, ffM2)."""
    m1 = pose(tuple(float(v) for v in found["FFM1"].split()))
    m2 = pose(tuple(float(v) for v in found["FFM2"].split()))
    tool = ((m2[0][0] - TIP_X, 0.0, TIP[2] + m2[0][2] - TIP_Z), (1.0, 0.0, 0.0, 0.0))
    pallet = m1  # uframe: the trans, then the rot of the point read; oframe the identity
    target = (IN_FRAME[0], q_unit(IN_FRAME[1]))
    out = {
        "FFOFS": ((TIP[0], TIP[1], TIP[2] + m2[0][2] - TIP_Z), (1.0, 0.0, 0.0, 0.0)),
        "FFF1": pose_mult((T2[0], q_unit(T2[1])), pose_inv(tool)),
        "FFF2": pose_mult(pallet, target),
    }
    for k, i in enumerate(MOVED):
        uframe = (m2[0], pallet[1]) if i == 2 else pallet
        other = OFRAMES.get(i, IDENTITY)
        out[SEEN[2 + k].upper()] = pose_mult(pose_mult(uframe, (other[0], q_unit(other[1]))), target)
    return out


def verdict(found: dict[str, str]) -> str:
    wrong = [f"{n}: {found.get(f'{n.lower()}_load')}" for n in LIBRARY if found.get(f"{n.lower()}_load") != "loaded"]
    runs = [f"{n} {found.get(f'{n}_load')} {found.get(f'{n}_run')}" for n in ("FFPREP", "SETUP_FRAMES")
            if found.get(f"{n}_load") != "loaded" or found.get(f"{n}_run") != "done"]  # fmt: skip
    wrong += runs
    if found.get(f"{CONV}_load") != "loaded" or found.get("conv_run") != "done" or found.get("conv_done") != "1":
        wrong.append(f"{CONV}: {found.get(f'{CONV}_load')}, {found.get('conv_run')}, done {found.get('conv_done')}")
        return "; ".join(wrong)
    for name, target in (("FFM1", T1), ("FFM2", T2)):  # the points read where the robot was sent
        mm, deg = gap(found[name], (target[0], q_unit(target[1])))
        if mm > 0.01 or deg > 0.01:
            wrong.append(f"{name} {found[name]}: {mm:.3f} mm, {deg:.3f} deg from where it was sent")
    for name, value in expected(found).items():
        mm, deg = gap(found[name], value)
        if mm > 0.01 or deg > 0.01:
            wrong.append(f"{name} {found[name]}: {mm:.3f} mm, {deg:.3f} deg from RAPID")
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    worst = max(gap(found[n], e) for n, e in expected(found).items())
    return (f"tframe.trans, uframe.trans/.rot from points read, uframe copied to {NESTS} work objects (banks,"
            f" CA_POSEMULT of the oframe): {len(expected(found))} values within {worst[0]:.3f} mm / {worst[1]:.3f} deg")


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
    print(f"FAIL {problem}" if problem else f"framefield probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
