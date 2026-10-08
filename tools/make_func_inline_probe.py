# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the FUNC inlining probe: tools and work objects built by FUNCs of the backup from base frames
calibrated at run time, the FUNCs copied into each call (crossarm.convert.func_inline).

FICONV.LS (and the programs it calls) are converted by CrossArm from FuncInlineProbe.mod with --karel, on ROBOGUIDE:

- FiCalib: a gripper base tool whose x and z are read on the robot (its orientation as saved), a camera base tool
  whose z and orientation are, a table whose uframe is (trans and rot of a point read): frame_writes, in TP;
- FiInit: eight tools and two work objects built from them by four FUNCs: MakeTool (`r := tOfs; r.tframe :=
  PoseMult(tBase.tframe, tOfs.tframe); r.tload.mass := ...`), WithLoad (`r := tBase; r.tload.mass := m`), Shifted
  (`r := tBase; r.tframe.trans.z := tBase.tframe.trans.z + dz`), TurnTool (`r.tframe := PoseMult(tBase.tframe,
  [[0,0,0], OrientZYX(a,0,0)])`) and ShiftFixture (`r.uframe := PoseMult(wBase.uframe, peShift)`). A frame whose
  orientation is known now is moved and turned by TP (`PR[F]=UTOOL[n]`, `PR[F,i]=PR[F,i]+d`, `PR[F,4..6]=...`); one
  turned at run time by KAREL (CA_POSEMULT); a copy by TP (`PR[F]=UTOOL[n]`, `UTOOL[m]=PR[F]`); some past the UTOOL
  numbers (bank registers);
- a move with each tool, in each work object;

after each move the robot's flange is read in the world frame (CRobT(\\Tool:=tool0 \\WObj:=wobj0): PR[k]=LPOS) and
compared with where RAPID puts it, worked out here from the points read with quaternions, independently of
CrossArm. SETUP_FRAMES.LS runs first: the frames as saved are tens of millimetres and degrees from the ones the
programs make, so only the frames they load put the flange there.

  python tools/make_func_inline_probe.py write    the module and the programs, in tests/fixtures/probes/funcinline
  python tools/make_func_inline_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results stored
  python tools/make_func_inline_probe.py check    the stored results against what was measured
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

PROBE = ROOT / "tests" / "fixtures" / "probes" / "funcinline"
RESULT = PROBE / "results" / "funcinline_roboguide.txt"
STAMP = datetime(2026, 1, 1)
LIBRARY = ["CA_POSEMULT"]
CONV = "FICONV"
PROGRAMS = (CONV, "FICALIB", "FIINIT")
DOWN = (0.0, 0.0, 1.0, 0.0)  # a half turn about y: the tool's z down
UP = (1.0, 0.0, 0.0, 0.0)
IDENTITY = ((0.0, 0.0, 0.0), UP)
TURNED = q_unit(q_mul(_about(2, 20.0), DOWN))  # down, turned 20 deg about the world's z
T1 = ((950.0, -60.0, 820.0), TURNED)  # read with tool0: the camera's orientation, the table's frame
T2 = ((1050.0, 80.0, 780.0), DOWN)  # read with tool0: the gripper's x and z
GRIP_X, GRIP_Z = 1040.0, 640.0  # fiGrip.tframe.trans.x := fiM2.trans.x - 1040 (10), z := fiM2.trans.z - 640 (140)
CAM_Z = 700.0  # fiCam.tframe.trans.z := fiM1.trans.z - 700 (120)
GRIP = ((0.0, 0.0, 100.0), UP)  # as saved
CAM = ((40.0, 0.0, 90.0), UP)
TABLE = ((1000.0, 0.0, 800.0), DOWN)
GRIP_OFFSETS = {  # MakeTool(fiGrip, offset)
    "fiOfs1": ((0.0, 25.0, 40.0), UP),
    "fiOfs2": ((0.0, -25.0, 40.0), UP),
    "fiOfs3": ((30.0, 0.0, 62.0), q_unit(_about(0, 30.0))),
    "fiOfs4": ((20.0, 0.0, 30.0), q_unit(_about(1, 45.0))),
}
CAM_OFFSETS = {"fiOfs5": ((0.0, 0.0, 35.0), UP), "fiOfs6": ((15.0, 0.0, 20.0), q_unit(_about(2, -40.0)))}
SHIFT_Z = 25.0  # Shifted(fiGrip, 25)
TURN = -30.0  # TurnTool(fiCam, -30): the flange turned +30 deg, J6 clear of its limit
FIXTURES = {"fiLeft": ((0.0, -150.0, 0.0), UP), "fiRight": ((0.0, 150.0, 0.0), q_unit(_about(2, 10.0)))}
DOWN_AT = ((1000.0, 0.0, 700.0), TURNED)  # the gripper's tools: their z down (J6 clear of its +-180 deg turn limit)
UP_AT = ((1000.0, 0.0, 700.0), UP)  # the camera's tools (turned over by its orientation): the flange down
IN_FRAME = ((40.0, 30.0, -60.0), UP)  # 60 mm above the table's origin (its z down)
GRIP_TOOLS = (*(f"fiT{i}" for i in range(1, 5)), "fiHeavy", "fiShift")
CAM_TOOLS = ("fiT5", "fiT6", "fiTurn")
SEEN = ("fiG", "fiC", *(f"fiF{i}" for i in range(1, len(GRIP_TOOLS) + len(CAM_TOOLS) + len(FIXTURES) + 1)))


def _tool(name: str, frame: tuple, mass: float) -> str:
    return f"    PERS tooldata {name}:=[TRUE,{_pose(frame)},[{mass:g},[0,0,50],[1,0,0,0],0,0,0]];"


def _offset(name: str, frame: tuple) -> str:
    return f"    CONST tooldata {name}:=[TRUE,{_pose(frame)},[0.5,[0,0,20],[1,0,0,0],0,0,0]];"


def _wobj(name: str, frame: tuple) -> str:
    return f"    PERS wobjdata {name}:=[FALSE,TRUE,\"\",{_pose(frame)},[[0,0,0],[1,0,0,0]]];"


SAVED_TOOL = ((0.0, 0.0, 200.0), UP)  # the tools built, as saved: far from what the programs make
MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE FuncInlineProbe",
    "    ! CrossArm - FUNC inlining probe: see tools/make_func_inline_probe.py.",
    _tool("fiGrip", GRIP, 4),
    _tool("fiCam", CAM, 1),
    _wobj("fiTable", TABLE),
    *(_offset(name, frame) for name, frame in (GRIP_OFFSETS | CAM_OFFSETS).items()),
    *(_tool(name, SAVED_TOOL, 4.5) for name in (*GRIP_TOOLS, *CAM_TOOLS)),
    *(_wobj(name, TABLE) for name in FIXTURES),
    *(f"    CONST pose {name}Ofs:={_pose(frame)};" for name, frame in FIXTURES.items()),
    f"    CONST robtarget fiR1:={_robtarget(T1[0], T1[1])};",
    f"    CONST robtarget fiR2:={_robtarget(T2[0], T2[1])};",
    f"    CONST robtarget fiDown:={_robtarget(DOWN_AT[0], DOWN_AT[1])};",
    f"    CONST robtarget fiUp:={_robtarget(UP_AT[0], UP_AT[1])};",
    f"    CONST robtarget fiP:={_robtarget(IN_FRAME[0], IN_FRAME[1])};",
    "    VAR robtarget fiM1;",
    "    VAR robtarget fiM2;",
    *(f"    VAR robtarget {name};" for name in SEEN),
    "    VAR num fiDone:=0;",
    "",
    "    FUNC tooldata MakeTool(tooldata tBase,tooldata tOfs)",
    "        VAR tooldata tRes;",
    "        tRes:=tOfs;",
    "        tRes.tframe:=PoseMult(tBase.tframe,tOfs.tframe);",
    "        tRes.tload.mass:=tBase.tload.mass+tOfs.tload.mass;",
    "        RETURN tRes;",
    "    ENDFUNC",
    "",
    "    FUNC tooldata WithLoad(tooldata tBase,num nMass)",
    "        VAR tooldata tRes;",
    "        tRes:=tBase;",
    "        tRes.tload.mass:=nMass;",
    "        RETURN tRes;",
    "    ENDFUNC",
    "",
    "    FUNC tooldata Shifted(tooldata tBase,num nDz)",
    "        VAR tooldata tRes;",
    "        tRes:=tBase;",
    "        tRes.tframe.trans.z:=tBase.tframe.trans.z+nDz;",
    "        RETURN tRes;",
    "    ENDFUNC",
    "",
    "    FUNC tooldata TurnTool(tooldata tBase,num nAngle)",
    "        VAR pose peTurn;",
    "        VAR tooldata tRes;",
    "        peTurn:=[[0,0,0],OrientZYX(nAngle,0,0)];",
    "        tRes:=tBase;",
    "        tRes.tframe:=PoseMult(tBase.tframe,peTurn);",
    "        RETURN tRes;",
    "    ENDFUNC",
    "",
    "    FUNC wobjdata ShiftFixture(wobjdata wBase,pose peShift)",
    "        VAR wobjdata wRes;",
    "        wRes:=wBase;",
    "        wRes.uframe:=PoseMult(wBase.uframe,peShift);",
    "        RETURN wRes;",
    "    ENDFUNC",
    "",
    "    PROC FiConv()",
    "        fiDone:=0;",
    "        FiCalib;",
    "        FiInit;",
    *(line for k, name in enumerate(GRIP_TOOLS) for line in (
        f"        MoveJ fiDown,v500,fine,{name};",
        f"        fiF{k + 1}:=CRobT(\\Tool:=tool0\\WObj:=wobj0);")),
    *(line for k, name in enumerate(CAM_TOOLS) for line in (
        f"        MoveJ fiUp,v500,fine,{name};",
        f"        fiF{len(GRIP_TOOLS) + k + 1}:=CRobT(\\Tool:=tool0\\WObj:=wobj0);")),
    *(line for k, name in enumerate(FIXTURES) for line in (
        f"        MoveJ fiP,v500,fine,tool0\\WObj:={name};",
        f"        fiF{len(GRIP_TOOLS) + len(CAM_TOOLS) + k + 1}:=CRobT(\\Tool:=tool0\\WObj:=wobj0);")),
    "        fiDone:=1;",
    "    ENDPROC",
    "",
    "    PROC FiCalib()",
    "        MoveJ fiR2,v500,fine,tool0;",
    "        fiM2:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    f"        fiGrip.tframe.trans.x:=fiM2.trans.x-{GRIP_X:g};",
    f"        fiGrip.tframe.trans.z:=fiM2.trans.z-{GRIP_Z:g};",
    "        MoveJ fiR1,v500,fine,tool0;",
    "        fiM1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    f"        fiCam.tframe.trans.z:=fiM1.trans.z-{CAM_Z:g};",
    "        fiCam.tframe.rot:=fiM1.rot;",
    "        fiTable.uframe.trans:=fiM1.trans;",
    "        fiTable.uframe.rot:=fiM1.rot;",
    "        MoveJ fiDown,v500,fine,fiGrip;",
    "        fiG:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        MoveJ fiUp,v500,fine,fiCam;",
    "        fiC:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        MoveJ fiP,v500,fine,tool0\\WObj:=fiTable;",
    "    ENDPROC",
    "",
    "    PROC FiInit()",
    *(f"        fiT{i + 1}:=MakeTool(fiGrip,{name});" for i, name in enumerate(GRIP_OFFSETS)),
    "        fiHeavy:=WithLoad(fiGrip,6);",
    f"        fiShift:=Shifted(fiGrip,{SHIFT_Z:g});",
    *(f"        fiT{i + 5}:=MakeTool(fiCam,{name});" for i, name in enumerate(CAM_OFFSETS)),
    f"        fiTurn:=TurnTool(fiCam,{TURN:g});",
    *(f"        {name}:=ShiftFixture(fiTable,{name}Ofs);" for name in FIXTURES),
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip


def _program(name: str, lines: list[str], comment: str) -> Program:
    return Program(name, [Instruction(text) for text in lines], attributes=Attributes(comment=comment, created=STAMP))


def conversion(folder: Path):
    """FuncInlineProbe.mod converted with --karel as `crossarm convert` does: FICONV.LS... SETUP_FRAMES.LS."""
    from crossarm import pipeline
    from crossarm.convert import ConversionConfig

    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "FuncInlineProbe.mod").write_bytes(MODULE.encode("ascii"))
    run = pipeline.run([PROBE / "FuncInlineProbe.mod"], folder, ConversionConfig(timestamp=STAMP, karel=True),
                       log=lambda _: None)  # fmt: skip
    result = run.tasks[0].result
    assert result is not None and not [n for n in result.notes if n.kind == "TODO"], result and result.notes
    assert result.karel_programs == LIBRARY, result.karel_programs
    return result


def kept(result) -> dict[str, int]:
    """fiM1... CROSSARM.FRAME -> the PR CrossArm keeps it in; FIDONE -> its R."""
    found = {a.rapid_name.upper(): a.number for a in result.point_registers}
    found["FIDONE"] = next(a.number for a in result.registers if a.rapid_name == "fiDone")
    return found


def prep_program(numbers: dict[str, int]) -> Program:
    """FIPREP: the registers CrossArm keeps poses in made Cartesian first (another probe may leave joints there)."""
    lines = ["UFRAME_NUM=0", "UTOOL_NUM=1"] + [f"PR[{k}]=LPOS" for name, k in sorted(numbers.items()) if name != "FIDONE"]
    return _program("FIPREP", lines, "func inline probe prep")


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="crossarm_funcinline_") as temp:
        result = conversion(Path(temp))
        for name in (*PROGRAMS, "SETUP_FRAMES"):
            (PROBE / f"{name}.LS").write_bytes((Path(temp) / f"{name}.LS").read_bytes())
    program = prep_program(kept(result))
    (PROBE / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
    for name, number in kept(result).items():
        print(f"  {'R' if name == 'FIDONE' else 'PR'}[{number}] {name}")
    print(f"probe written to {PROBE}")


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------


def measure() -> dict[str, str]:
    import make_maketp_probe
    import roboguide

    write()
    with tempfile.TemporaryDirectory(prefix="crossarm_funcinline_") as temp:
        numbers = kept(conversion(Path(temp)))
    names = ["FIPREP", "SETUP_FRAMES", *PROGRAMS]
    pcs = [name.lower() for name in LIBRARY]
    found: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="crossarm_funcinline_") as temp:
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
            found["FIPREP_run"] = roboguide.run("FIPREP", 60)
            found["SETUP_FRAMES_run"] = roboguide.run("SETUP_FRAMES", 60, resumes=1)
            roboguide.zero([numbers["FIDONE"]])
            found["conv_run"] = roboguide.run(CONV, 300)
            found["conv_done"] = f"{roboguide.numreg().get(numbers['FIDONE'], float('nan')):g}"
            posreg = roboguide.page("md/POSREG.VA")
            for name in ("FIM1", "FIM2", *(s.upper() for s in SEEN)):
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


def _flange(target: tuple, tool: tuple) -> tuple:
    return pose_mult((target[0], q_unit(target[1])), pose_inv(tool))


def expected(found: dict[str, str]) -> dict[str, tuple]:
    """Where RAPID puts the flange after each move, from the points the robot read (fiM1, fiM2)."""
    m1 = pose(tuple(float(v) for v in found["FIM1"].split()))
    m2 = pose(tuple(float(v) for v in found["FIM2"].split()))
    grip = ((m2[0][0] - GRIP_X, GRIP[0][1], m2[0][2] - GRIP_Z), GRIP[1])
    cam = ((CAM[0][0], CAM[0][1], m1[0][2] - CAM_Z), m1[1])
    table = m1
    tools = [pose_mult(grip, (frame[0], q_unit(frame[1]))) for frame in GRIP_OFFSETS.values()]
    tools += [grip, ((grip[0][0], grip[0][1], grip[0][2] + SHIFT_Z), grip[1])]  # WithLoad, Shifted
    cams = [pose_mult(cam, (frame[0], q_unit(frame[1]))) for frame in CAM_OFFSETS.values()]
    cams.append(pose_mult(cam, ((0.0, 0.0, 0.0), q_unit(_about(2, TURN)))))
    out = {"FIG": _flange(DOWN_AT, grip), "FIC": _flange(UP_AT, cam)}
    for k, tool in enumerate(tools):
        out[f"FIF{k + 1}"] = _flange(DOWN_AT, tool)
    for k, tool in enumerate(cams):
        out[f"FIF{len(tools) + k + 1}"] = _flange(UP_AT, tool)
    for k, shift in enumerate(FIXTURES.values()):
        frame = pose_mult(table, (shift[0], q_unit(shift[1])))
        out[f"FIF{len(tools) + len(cams) + k + 1}"] = pose_mult(frame, (IN_FRAME[0], q_unit(IN_FRAME[1])))
    return out


def verdict(found: dict[str, str]) -> str:
    wrong = [f"{n}: {found.get(f'{n.lower()}_load')}" for n in LIBRARY if found.get(f"{n.lower()}_load") != "loaded"]
    runs = [f"{n} {found.get(f'{n}_load')} {found.get(f'{n}_run')}" for n in ("FIPREP", "SETUP_FRAMES")
            if found.get(f"{n}_load") != "loaded" or found.get(f"{n}_run") != "done"]  # fmt: skip
    wrong += runs
    loads = [n for n in PROGRAMS if found.get(f"{n}_load") != "loaded"]
    if loads or found.get("conv_run") != "done" or found.get("conv_done") != "1":
        wrong.append(f"{loads or CONV}: {found.get('conv_run')}, done {found.get('conv_done')}")
        return "; ".join(wrong)
    for name, target in (("FIM1", T1), ("FIM2", T2)):  # the points read where the robot was sent
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
    return (f"MakeTool/WithLoad/Shifted/TurnTool/ShiftFixture inlined ({len(GRIP_TOOLS) + len(CAM_TOOLS)} tools,"
            f" {len(FIXTURES)} work objects, TP and CA_POSEMULT): {len(expected(found))} flanges within"
            f" {worst[0]:.3f} mm / {worst[1]:.3f} deg")  # fmt: skip


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
    print(f"FAIL {problem}" if problem else f"funcinline probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
