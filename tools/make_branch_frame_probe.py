# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the branch frame probe (--karel): a work object's uframe computed from a pose chosen in the
branches of an IF, turned by OrientZYX of a routine's parameter, then copied to other work objects.

BFCONV.LS is converted by CrossArm from BranchFrameProbe.mod with --karel, on ROBOGUIDE. BfTurn(nSide, nAngle):

- IF nSide=1: pBase := bfSideA.uframe; ELSEIF nSide=2: pBase := bfSideB.uframe; ELSE Stop; EXIT (bfTurn.ufmec set
  in each branch): pBase is kept in a position register both branches write;
- pTurn.rot := OrientZYX(nAngle, 10, 5): the routine's own pose, its trans as declared (zero), W, P, R = 5, 10,
  nAngle (`PR[k,4..6]`);
- bfTurn.uframe := PoseMult(pBase, pTurn) by CA_POSEMULT, loaded into its UFRAME; bfCopy1.uframe and bfCopy2.uframe
  := bfTurn.uframe (`PR[F]=UFRAME[n]`, `UFRAME[m]=PR[F]`).

BfConv calls it for side 1 and 30 degrees, then side 2 and 135 degrees, a move in each copy after each call; after
each move the flange is read in the world frame (CRobT(\\Tool:=tool0 \\WObj:=wobj0): PR[k]=LPOS) and compared with
where RAPID puts it, worked out here with quaternions, independently of CrossArm. SETUP_FRAMES.LS runs first: the
copies as saved are far from the frames the program makes.

  python tools/make_branch_frame_probe.py write    the module and the programs, in tests/fixtures/probes/branchframe
  python tools/make_branch_frame_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results stored
  python tools/make_branch_frame_probe.py check    the stored results against what was measured
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_karel_pose_probe import _about, _pose, _robtarget, gap, pose_mult
from make_karel_probe import _ftp, q_mul, q_unit, read_pr

from crossarm.fanuc.ktrans import KarelRequest, export
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program

PROBE = ROOT / "tests" / "fixtures" / "probes" / "branchframe"
RESULT = PROBE / "results" / "branchframe_roboguide.txt"
STAMP = datetime(2026, 1, 1)
LIBRARY = ["CA_POSEMULT"]
CONV = "BFCONV"
DOWN = (0.0, 0.0, 1.0, 0.0)  # a half turn about y: the tool's z down
SIDE_A = ((1000.0, -100.0, 700.0), (1.0, 0.0, 0.0, 0.0))
SIDE_B = ((1100.0, 100.0, 700.0), q_unit(_about(2, 90.0)))  # turned about z
SAVED = ((900.0, 0.0, 650.0), (1.0, 0.0, 0.0, 0.0))  # the turned frame and its copies as saved
IN_FRAME = ((40.0, 30.0, 80.0), DOWN)  # bfP: 80 mm above the frame's origin, the tool's z down
CALLS = ((1, 30.0), (2, 135.0))  # BfTurn(nSide, nAngle)
SEEN = ("bfS1", "bfS2", "bfS3", "bfS4")  # the flange after each move: copy 1, copy 2, for each call

MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE BranchFrameProbe",
    "    ! CrossArm - branch frame probe: see tools/make_branch_frame_probe.py.",
    f"    PERS wobjdata bfSideA:=[FALSE,TRUE,\"\",{_pose(SIDE_A)},[[0,0,0],[1,0,0,0]]];",
    f"    PERS wobjdata bfSideB:=[FALSE,TRUE,\"\",{_pose(SIDE_B)},[[0,0,0],[1,0,0,0]]];",
    f"    PERS wobjdata bfTurn:=[FALSE,TRUE,\"\",{_pose(SAVED)},[[0,0,0],[1,0,0,0]]];",
    f"    PERS wobjdata bfCopy1:=[FALSE,TRUE,\"\",{_pose(SAVED)},[[0,0,0],[1,0,0,0]]];",
    f"    PERS wobjdata bfCopy2:=[FALSE,TRUE,\"\",{_pose(SAVED)},[[0,0,0],[1,0,0,0]]];",
    f"    CONST robtarget bfP:={_robtarget(IN_FRAME[0], IN_FRAME[1])};",
    *(f"    VAR robtarget {name};" for name in SEEN),
    "    VAR num bfDone:=0;",
    "",
    "    PROC BfConv()",
    "        bfDone:=0;",
    *(line for k, (side, angle) in enumerate(CALLS) for line in (
        f"        BfTurn {side},{angle:g};",
        "        MoveL bfP,v500,fine,tool0\\WObj:=bfCopy1;",
        f"        {SEEN[2 * k]}:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
        "        MoveL bfP,v500,fine,tool0\\WObj:=bfCopy2;",
        f"        {SEEN[2 * k + 1]}:=CRobT(\\Tool:=tool0\\WObj:=wobj0);")),
    "        bfDone:=1;",
    "    ENDPROC",
    "",
    "    PROC BfTurn(num nSide,num nAngle)",
    "        VAR pose pBase;",
    "        VAR pose pTurn;",
    "        IF nSide=1 THEN",
    "            pBase:=bfSideA.uframe;",
    "            bfTurn.ufmec:=\"ROB_1\";",
    "        ELSEIF nSide=2 THEN",
    "            pBase:=bfSideB.uframe;",
    "            bfTurn.ufmec:=\"ROB_1\";",
    "        ELSE",
    "            Stop;",
    "            EXIT;",
    "        ENDIF",
    "        pTurn.rot:=OrientZYX(nAngle,10,5);",
    "        bfTurn.uframe:=PoseMult(pBase,pTurn);",
    "        bfCopy1.uframe:=bfTurn.uframe;",
    "        bfCopy2.uframe:=bfTurn.uframe;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip
PROGRAMS = ["BFPREP", "SETUP_FRAMES", "BFTURN", CONV]


def _program(name: str, lines: list[str], comment: str) -> Program:
    return Program(name, [Instruction(text) for text in lines], attributes=Attributes(comment=comment, created=STAMP))


def conversion(folder: Path):
    """BranchFrameProbe.mod converted with --karel as `crossarm convert` does."""
    from crossarm import pipeline
    from crossarm.convert import ConversionConfig

    (PROBE / "BranchFrameProbe.mod").write_bytes(MODULE.encode("ascii"))
    run = pipeline.run([PROBE / "BranchFrameProbe.mod"], folder, ConversionConfig(timestamp=STAMP, karel=True),
                       log=lambda _: None)  # fmt: skip
    result = run.tasks[0].result
    assert result is not None and not [n for n in result.notes if n.kind == "TODO"], result and result.notes
    assert result.karel_programs == LIBRARY, result.karel_programs
    return result


def kept(result) -> dict[str, int]:
    """bfS1... and the poses kept -> their PR; BFDONE -> its R."""
    found = {a.rapid_name.upper(): a.number for a in result.point_registers}
    found["BFDONE"] = next(a.number for a in result.registers if a.rapid_name == "bfDone")
    return found


def prep_program(numbers: dict[str, int]) -> Program:
    """BFPREP: the registers CrossArm keeps poses in made Cartesian first (another probe may leave joints there)."""
    lines = ["UFRAME_NUM=0", "UTOOL_NUM=1"] + [f"PR[{k}]=LPOS" for name, k in sorted(numbers.items()) if name != "BFDONE"]
    return _program("BFPREP", lines, "branch frame probe prep")


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="crossarm_branchframe_") as temp:
        result = conversion(Path(temp))
        for name in PROGRAMS[1:]:
            (PROBE / f"{name}.LS").write_bytes((Path(temp) / f"{name}.LS").read_bytes())
    program = prep_program(kept(result))
    (PROBE / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------


def measure() -> dict[str, str]:
    import make_maketp_probe
    import roboguide

    write()
    with tempfile.TemporaryDirectory(prefix="crossarm_branchframe_") as temp:
        numbers = kept(conversion(Path(temp)))
    pcs = [name.lower() for name in LIBRARY]
    found: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="crossarm_branchframe_") as temp:
        work = Path(temp)
        out = export(LIBRARY, work, KarelRequest(make_maketp_probe.robot()), log=print)
        if len(out.compiled) != len(LIBRARY):
            raise RuntimeError(f"library not compiled: {out.problem or out.refused}")
        for name in PROGRAMS:
            roboguide.release(name)
        roboguide.select()
        for name in PROGRAMS:
            _ftp(f"DELE {name.lower()}.tp")
        try:
            for name in pcs:
                found[f"{name}_load"] = _ftp("STOR", work / f"{name}.pc") or "loaded"
            for name in PROGRAMS:
                found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
            found["BFPREP_run"] = roboguide.run("BFPREP", 60)
            found["SETUP_FRAMES_run"] = roboguide.run("SETUP_FRAMES", 60, resumes=1)
            roboguide.zero([numbers["BFDONE"]])
            found["conv_run"] = roboguide.run(CONV, 240)
            found["conv_done"] = f"{roboguide.numreg().get(numbers['BFDONE'], float('nan')):g}"
            posreg = roboguide.page("md/POSREG.VA")
            for name in SEEN:
                found[name.upper()] = read_pr(posreg, numbers[name.upper()])
            return found
        finally:
            roboguide.select()
            for name in PROGRAMS:
                roboguide.release(name)
            roboguide.select()
            for name in PROGRAMS:
                _ftp(f"DELE {name.lower()}.tp")
            for name in pcs:
                _ftp(f"DELE {name}.pc")
                _ftp(f"DELE {name}.vr")


def zyx(z: float, y: float, x: float) -> tuple[float, ...]:
    """RAPID OrientZYX: turned about z, then the new y, then the new x."""
    return q_unit(q_mul(q_mul(_about(2, z), _about(1, y)), _about(0, x)))  # _about: 0 x, 1 y, 2 z


def expected() -> dict[str, tuple]:
    """Where RAPID puts the flange after each move."""
    out = {}
    for k, (side, angle) in enumerate(CALLS):
        base = SIDE_A if side == 1 else SIDE_B
        frame = pose_mult(base, ((0.0, 0.0, 0.0), zyx(angle, 10.0, 5.0)))
        flange = pose_mult(frame, (IN_FRAME[0], q_unit(IN_FRAME[1])))
        out[SEEN[2 * k].upper()] = out[SEEN[2 * k + 1].upper()] = flange
    return out


def verdict(found: dict[str, str]) -> str:
    wrong = [f"{k}: {v}" for k, v in found.items() if k.endswith(("_load", "_run")) and v not in ("loaded", "done")]
    if found.get("conv_run") != "done" or found.get("conv_done") != "1":
        wrong.append(f"{CONV}: {found.get('conv_run')}, done {found.get('conv_done')}")
        return "; ".join(wrong)
    for name, value in expected().items():
        mm, deg = gap(found[name], value)
        if mm > 0.01 or deg > 0.01:
            wrong.append(f"{name} {found[name]}: {mm:.3f} mm, {deg:.3f} deg from RAPID")
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    worst = max(gap(found[n], e) for n, e in expected().items())
    return (f"uframe from a pose chosen per IF branch turned by OrientZYX of a parameter (CA_POSEMULT), copied to two"
            f" work objects, two calls: {len(SEEN)} moves within {worst[0]:.3f} mm / {worst[1]:.3f} deg")


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
    print(f"FAIL {problem}" if problem else f"branchframe probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
