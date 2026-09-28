# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the compute probe: frames and points the programs compute, end to end.

PROC Path of ComputeProbe.mod builds frames and points the way RAPID programs do: a tool made by a
FUNC from a base tool and a RECORD, a work object's uframe copied from another's, DefFrame with each
\\Origin, one frame computed three times over, a point put together from PoseVect, PoseInv, EulerZYX
and OrientZYX, RelTool on it, and a MoveAbsJ with a stationary tool. CrossArm converts PROC Path,
working every value out at conversion time (crossarm.convert.compute), and each controller then says
where the flange ends up at every move:

  ABB (RobotStudio, no motion): PROC Probe runs the same statements, each move replaced by the flange
      pose it would reach, uframe * oframe * target * inverse(tframe), written to HOME:/computeprobe.txt.
  FANUC (ROBOGUIDE, simulated motion): COMPPROBE.LS sets the frames and the computed registers as
      SETUP_FRAMES does, runs the converted program and records the faceplate after each move (LPOS,
      a zero tool, UFRAME 0) in PR[51..].

The same flange on both sides, move by move, means the computation, the registers it lands in and the
loads the programs make are right. The MoveAbsJ is not compared (a joint target puts the flange elsewhere
on another robot model): the moves after it must still be measured, which says it ran.

Usage:  python tools/make_compute_probe.py write     ComputeProbe.mod and COMPPROBE.LS in tests/fixtures/probes/compute
        python tools/make_compute_probe.py run       RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_compute_probe.py check     compare the stored results
"""

import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_pose_probe import FLANGE_PR, HOME_JOINTS, JOINTS_PR, ZERO_TOOL, compare, read_posreg, read_robotstudio

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.setup import build_setup
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, JointPosition, Motion, Position, Program
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "compute"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "computeprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "computeprobe_roboguide.txt"
PROGRAM = "COMPPROBE"
ZERO_PR = 29  # the zero tool on its way to UTOOL[ZERO_TOOL]

DATA = """\
    RECORD shiftdata
        num rz;
        pos offset;
    ENDRECORD

    PERS tooldata tBase:=[TRUE,[[20,-30,200],[1,0,0,0]],[5,[0,0,80],[1,0,0,0],0,0,0]];
    PERS tooldata tBuilt:=[TRUE,[[0,0,100],[1,0,0,0]],[5,[0,0,80],[1,0,0,0],0,0,0]];
    PERS tooldata tFixed:=[FALSE,[[1500,0,400],[1,0,0,0]],[1,[0,0,0],[1,0,0,0],0,0,0]];
    PERS shiftdata sShift:=[25,[15,-10,40]];
    PERS wobjdata wBase:=[FALSE,TRUE,"",[[900,-200,100],[0.9723323,-0.0774561,0.0273980,0.2186775]],[[30,20,0],[1,0,0,0]]];
    PERS wobjdata wCopy:=[FALSE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,50],[0.9961947,0,0,-0.0871557]]];
    PERS wobjdata wDef:=[FALSE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    CONST robtarget pD1:=[[950,-150,120],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pD2:=[[1150,-50,110],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pD3:=[[1000,100,140],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pT1:=[[1100,50,500],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pT2:=[[200,100,300],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pT3:=[[100,50,350],[0,1,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST robtarget pT4:=[[0,0,0],[1,0,0,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
    CONST jointtarget jPark:=[[10,-10,10,0,60,30],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
"""

FUNC = """\
    FUNC tooldata MakeTool(tooldata base,shiftdata shift)
        VAR tooldata t;
        VAR pose p;
        t:=base;
        p.trans:=shift.offset;
        p.rot:=OrientZYX(shift.rz,0,0);
        t.tframe:=PoseMult(base.tframe,p);
        RETURN t;
    ENDFUNC
"""

LOCALS = ["VAR robtarget pC;"]

# What PROC Path does, in order: a RAPID statement, or a move ("MoveJ" / "MoveAbsJ", target, tool, wobj).
STEPS: list[str | tuple[str, str, str, str]] = [
    "tBuilt:=MakeTool(tBase,sShift);",
    ("MoveJ", "pT1", "tBuilt", "wobj0"),
    "wCopy.uframe:=wBase.uframe;",
    ("MoveJ", "pT2", "tBuilt", "wCopy"),
    "wDef.uframe:=DefFrame(pD1,pD2,pD3);",
    ("MoveJ", "pT3", "tBase", "wDef"),
    "wDef.uframe:=DefFrame(pD1,pD2,pD3\\Origin:=2);",
    ("MoveJ", "pT3", "tBase", "wDef"),
    "wDef.uframe:=DefFrame(pD1,pD2,pD3\\Origin:=3);",
    ("MoveJ", "pT3", "tBase", "wDef"),
    "pC:=pT4;",
    "pC.trans:=PoseVect(PoseInv([[-1000,200,-600],[1,0,0,0]]),[70,-20,0]);",
    "pC.rot:=OrientZYX(EulerZYX(\\Z,wBase.uframe.rot),EulerZYX(\\Y,wBase.uframe.rot),180+EulerZYX(\\X,wBase.uframe.rot));",
    ("MoveJ", "pC", "tBase", "wobj0"),
    ("MoveJ", "RelTool(pC,0,0,-50\\Rz:=20)", "tBase", "wobj0"),
    "tBuilt:=MakeTool(tBase,[-40,[0,25,-30]]);",
    ("MoveJ", "pT1", "tBuilt", "wobj0"),
    ("MoveAbsJ", "jPark", "tFixed", ""),
    "wDef.uframe:=DefFrame(pD1,pD2,pD3);",
    ("MoveJ", "pT3", "tBase", "wDef"),
]
MOVES = sum(1 for s in STEPS if isinstance(s, tuple))


def abb_module() -> str:
    lines = [
        "MODULE ComputeProbe",
        "    ! CrossArm - compute probe. In RobotStudio, run PROC Probe (no motion): it does what PROC Path does and",
        "    ! writes, for each move, the flange pose in the world frame to HOME:/computeprobe.txt as",
        "    ! i x y z q1 q2 q3 q4. PROC Path is what CrossArm converts: never run it on a robot.",
        DATA.rstrip(),
        "",
        FUNC.rstrip(),
        "",
        "    PROC Path()",
        *(f"        {local}" for local in LOCALS),
    ]
    for step in STEPS:
        if isinstance(step, str):
            lines.append(f"        {step}")
        elif step[0] == "MoveAbsJ":
            lines.append(f"        MoveAbsJ {step[1]},v200,fine,{step[2]};")
        else:
            lines.append(f"        MoveJ {step[1]},v200,fine,{step[2]}\\WObj:={step[3]};")
    lines += [
        "    ENDPROC",
        "",
        "    PROC Probe()",
        *(f"        {local}" for local in LOCALS),
        "        VAR iodev f;",
        '        Open "HOME:" \\File:="computeprobe.txt", f \\Write;',
        "        Close f;",
    ]
    move = 0
    for step in STEPS:
        if isinstance(step, str):
            lines.append(f"        {step}")
            continue
        move += 1
        if step[0] == "MoveJ":
            lines.append(f"        WriteFlange {move},{step[1]},{step[2]},{step[3]};")
        else:
            lines.append(f"        ! move {move}: a joint target, not compared")
    lines += [
        '        TPWrite "computeprobe.txt written in HOME:";',
        "        Stop;",
        "    ENDPROC",
        "",
        "    PROC WriteFlange(num i,robtarget target,PERS tooldata tool,PERS wobjdata wobj)",
        "        VAR iodev f;",
        "        VAR pose tcp;",
        "        VAR pose flange;",
        "        tcp.trans:=target.trans;",
        "        tcp.rot:=target.rot;",
        "        flange:=PoseMult(PoseMult(PoseMult(wobj.uframe,wobj.oframe),tcp),PoseInv(tool.tframe));",
        '        Open "HOME:" \\File:="computeprobe.txt", f \\Append;',
        (
            '        Write f, NumToStr(i,0)+" "+NumToStr(flange.trans.x,3)+" "+NumToStr(flange.trans.y,3)+" "'
            '+NumToStr(flange.trans.z,3)\\NoNewLine;'
        ),
        (
            '        Write f, " "+NumToStr(flange.rot.q1,6)+" "+NumToStr(flange.rot.q2,6)+" "+NumToStr(flange.rot.q3,6)'
            '+" "+NumToStr(flange.rot.q4,6);'
        ),
        "        Close f;",
        "    ENDPROC",
        "ENDMODULE",
        "",
    ]
    return "\r\n".join(lines)


def conversion(module_text: str):
    parsed = parse_text(module_text, path="ComputeProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    result = convert([parsed.module], config, routines=["Path"])
    return result, config


def fanuc_program(module_text: str) -> str:
    """SETUP_FRAMES' lines, then CrossArm's own conversion of PROC Path, each move followed by a measurement."""
    result, config = conversion(module_text)
    todo = [n.message for n in result.notes if n.kind == "TODO"]
    assert not todo, todo
    (info,) = result.programs
    setup = build_setup(result, config, "SETUP_FRAMES")
    assert setup.program is not None
    positions = list(info.program.positions)
    by_number = {p.number: p for p in positions}
    offset = max(by_number)
    lines: list[Instruction | Motion] = [Instruction("!CrossArm compute probe"), Instruction("!SETUP_FRAMES")]
    for line in setup.program.lines:  # its frames and registers, without its opening message and pause
        text = line.text
        if text.startswith(("MESSAGE[", "PAUSE", "!")):
            continue
        lines.append(Instruction(re.sub(r"=P\[(\d+)\]", lambda m: f"=P[{int(m[1]) + offset}]", text)))
    for position in setup.program.positions:
        positions.append(Position(position.number + offset, position.uf, position.ut, position.value))
    data = max(p.number for p in positions) + 1
    positions.append(Position(data, 0, 1, CartesianPosition(0, 0, 0, 0, 0, 0)))
    positions.append(Position(data + 1, 0, ZERO_TOOL, JointPosition(HOME_JOINTS)))
    lines += [Instruction(f"PR[{ZERO_PR}]=P[{data}]"), Instruction(f"UTOOL[{ZERO_TOOL}]=PR[{ZERO_PR}]"),
              Instruction("!known start"), Instruction("UFRAME_NUM=0"), Instruction(f"UTOOL_NUM={ZERO_TOOL}"),
              Motion("J", f"P[{data + 1}]", "10%", "FINE"),
              Instruction(f"PR[{FLANGE_PR}]=LPOS"), Instruction(f"PR[{JOINTS_PR}]=JPOS")]  # fmt: skip
    move = 0
    for line in info.program.lines[1:]:  # after its '!RAPID ...' remark
        if not isinstance(line, Motion):
            lines.append(line)
            continue
        move += 1
        target = by_number[int(line.target[2:-1])]
        lines += [Instruction(f"!move {move}"), Instruction(f"UFRAME_NUM={target.uf}"),
                  Instruction(f"UTOOL_NUM={target.ut}"), line,
                  Instruction("UFRAME_NUM=0"), Instruction(f"UTOOL_NUM={ZERO_TOOL}"),
                  Instruction(f"PR[{FLANGE_PR + move}]=LPOS"), Instruction(f"PR[{JOINTS_PR + move}]=JPOS")]  # fmt: skip
    assert move == MOVES
    return write_ls(Program(PROGRAM, lines, positions, Attributes(comment="compute probe", created=datetime(2026, 1, 1))))


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    module = abb_module()
    (PROBE / "ComputeProbe.mod").write_bytes(module.encode("ascii"))
    (PROBE / f"{PROGRAM}.LS").write_bytes(fanuc_program(module).encode("ascii"))
    print(f"probe written to {PROBE}")


def fanuc_flanges(posreg: str) -> str:
    """The measured faceplates, 'i x y z w p r' per move: only these values are kept, not the register dump."""
    registers = read_posreg(posreg)
    rows = []
    for i in range(1, MOVES + 1):
        if FLANGE_PR + i in registers:
            rows.append(f"{i} " + " ".join(f"{v:.3f}" for v in registers[FLANGE_PR + i]))
    return "\n".join(rows) + "\n"


def read_fanuc(text: str) -> dict[int, tuple[float, ...]]:
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 7:
            out[FLANGE_PR + int(parts[0])] = tuple(float(v) for v in parts[1:])
    return out


def run() -> None:
    import roboguide
    import robotstudio

    RESULTS.mkdir(parents=True, exist_ok=True)
    home = robotstudio.home()
    status = robotstudio.run(PROBE / "ComputeProbe.mod", "Probe", 120, home)
    print(f"RobotStudio: {status}")
    ABB_RESULT.write_text((home / "computeprobe.txt").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    print(f"ROBOGUIDE load: {roboguide.load(PROBE / f'{PROGRAM}.LS') or 'loaded'}")
    print(f"ROBOGUIDE run: {roboguide.run(PROGRAM, 300)}")
    FANUC_RESULT.write_text(fanuc_flanges(roboguide.page("md/POSREG.VA")), encoding="utf-8")
    roboguide.release(PROGRAM)
    roboguide.delete(PROGRAM)
    check()


def check() -> list[tuple[int, float, float]]:
    abb = read_robotstudio(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_fanuc(FANUC_RESULT.read_text(encoding="utf-8"))
    rows = compare(abb, fanuc)
    for i, gap, turn in rows:
        print(f"move {i:2d}: {gap:8.4f} mm  {turn:7.4f} deg")
    measured = sorted(k - FLANGE_PR for k in fanuc)
    print(f"{len(rows)} moves compared, {len(measured)} of {MOVES} measured on ROBOGUIDE")
    return rows


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
