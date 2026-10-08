# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A FUNC of the backup composing a tool or a work object from one calibrated at run time, copied into each call
(crossarm.convert.func_inline): its statements rewritten on the call's target, converted by TP (frame read back,
moved, loaded) or KAREL (CA_POSEMULT), the report saying at how many calls; any other body stays TODO with the
FUNC and the statement named."""

from datetime import datetime

import pytest

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.blockers import Blocker
from crossarm.convert.compute import Layouts
from crossarm.convert.func_inline import NotInlined, inline_body
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import nodes as n
from crossarm.rapid import parse_text
from crossarm.rapid.to_pseudo import format_expr

STAMP = datetime(2026, 1, 1)
DOWN = "[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]"
DATA = f"""MODULE FI
  PERS tooldata tBase:=[TRUE,[[0,0,150],[1,0,0,0]],[5,[0,0,60],[1,0,0,0],0,0,0]];
  CONST tooldata tFixed:=[TRUE,[[0,0,100],[1,0,0,0]],[2,[0,0,50],[1,0,0,0],0,0,0]];
  CONST tooldata tOfsA:=[TRUE,[[0,20,40],[1,0,0,0]],[0.5,[0,0,20],[1,0,0,0],0,0,0]];
  CONST tooldata tOfsB:=[TRUE,[[10,0,30],[0.7071068,0,0,0.7071068]],[0.5,[0,0,20],[1,0,0,0],0,0,0]];
  PERS tooldata tA:=[TRUE,[[0,20,190],[1,0,0,0]],[5.5,[0,0,60],[1,0,0,0],0,0,0]];
  PERS tooldata tB:=[TRUE,[[10,0,180],[1,0,0,0]],[5.5,[0,0,60],[1,0,0,0],0,0,0]];
  PERS wobjdata wTable:=[FALSE,TRUE,"",[[800,0,300],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  PERS wobjdata wLeft:=[FALSE,TRUE,"",[[800,-100,300],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  CONST pose peLeft:=[[0,-100,0],[1,0,0,0]];
  CONST robtarget pA:=[[900,-100,500],{DOWN}];
  CONST robtarget pIn:=[[50,20,0],{DOWN}];
  VAR robtarget pM;
  FUNC tooldata MakeTool(tooldata tB0,tooldata tOfs)
    VAR tooldata tRes;
    tRes:=tOfs;
    tRes.tframe:=PoseMult(tB0.tframe,tOfs.tframe);
    tRes.tload.mass:=tB0.tload.mass+tOfs.tload.mass;
    RETURN tRes;
  ENDFUNC
  FUNC wobjdata Shift(wobjdata wB0,pose peS)
    VAR wobjdata wRes;
    wRes:=wB0;
    wRes.uframe:=PoseMult(wB0.uframe,peS);
    RETURN wRes;
  ENDFUNC
  FUNC tooldata Checked(tooldata tB0,tooldata tOfs)
    VAR tooldata tRes;
    tRes:=MakeTool(tB0,tOfs);
    IF tB0.tframe.trans.z<100 THEN
      TPWrite "short";
    ENDIF
    RETURN tRes;
  ENDFUNC
  FUNC tooldata Twice(tooldata tB0,tooldata tOfs)
    RETURN MakeTool(tB0,tOfs);
  ENDFUNC
  PROC Calib()
    MoveL pA,v200,fine,tool0;
    pM:=CRobT(\\Tool:=tool0\\WObj:=wobj0);
    CALIB
  ENDPROC
  PROC Main()
    MoveL pIn,v200,fine,tBase\\WObj:=wTable;
    BODY
    MoveL pIn,v200,fine,tA\\WObj:=wLeft;
    MoveL pIn,v200,fine,tB;
  ENDPROC
ENDMODULE
"""
LENGTH = "tBase.tframe.trans.z:=pM.trans.z-350;\nwTable.uframe.trans.z:=pM.trans.z-200;"
TURN = "tBase.tframe.rot:=pM.rot;"


def conversion(body: str, calib: str = LENGTH, karel: bool = False):
    text = DATA.replace("BODY", body).replace("CALIB", calib)
    parsed = parse_text(text, path="FI.mod")
    assert parsed.module is not None, parsed.diagnostics
    return convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=karel), sources={"FI": text})


def lines(result) -> list[str]:
    main = next(p for p in result.programs if p.program.name == "MAIN")
    text = write_ls(main.program).split("/MN")[1].split("/POS")[0]
    return [line.split(":", 1)[1].strip().rstrip(";").strip() for line in text.splitlines() if ":" in line]


def todo(result) -> list:
    return [note for note in result.notes if note.kind == "TODO"]


def inlined(result) -> list[str]:
    return [note.message for note in result.notes if note.category == Blocker.INLINED]


CALLS = "tA:=MakeTool(tBase,tOfsA);\ntB:=MakeTool(tBase,tOfsB);"


def test_a_base_tool_whose_length_only_is_calibrated_is_composed_by_tp_alone():
    result = conversion(CALLS)
    assert todo(result) == []
    found = lines(result)
    # tBase's frame read back, moved by its rotation (known now) x the offset, turned, loaded into tA's UTOOL
    start = next(i for i, line in enumerate(found) if line.startswith("!l.46 tA.tframe:=PoseMult("))
    read, *rest = found[start + 1 : start + 7]
    assert read.endswith("=UTOOL[2]")  # tBase, as SETUP_FRAMES or its calibration left it
    register = read.split("=")[0][:-1]
    assert rest == [f"{register},2]={register},2]+20", f"{register},3]={register},3]+40", f"{register},4]=0",
                    f"{register},5]=0", f"{register},6]=0"]  # fmt: skip
    assert found[start + 7].startswith("UTOOL[") and found[start + 7].endswith(f"={register}]")
    assert inlined(result) == [("FUNC MakeTool() of the backup is inlined at 2 call sites: its body is copied into each"
                                " call, as TP (and KAREL) lines; convert again after a change of MakeTool() in the RAPID")]  # fmt: skip
    assert not any("CALL" in line for line in found)


def test_a_base_tool_turned_at_run_time_is_composed_by_karel():
    result = conversion(CALLS, LENGTH + "\n" + TURN)
    messages = [note.message for note in todo(result)]
    assert len(messages) == 2 and all("(in MakeTool(), inlined: `tA.tframe := PoseMult(" in m or "tB.tframe" in m
                                      for m in messages)  # fmt: skip
    assert all("convert with --karel" in m for m in messages)
    assert result.karel_todo == 2
    result = conversion(CALLS, LENGTH + "\n" + TURN, karel=True)
    assert todo(result) == []
    calls = [line for line in lines(result) if line.startswith("CALL CA_POSEMULT")]
    assert len(calls) == 2
    assert len(inlined(result)) == 1


def test_a_work_object_shifted_from_a_calibrated_one():
    result = conversion("wLeft:=Shift(wTable,peLeft);")
    assert todo(result) == []
    found = lines(result)
    start = next(i for i, line in enumerate(found) if line.startswith("!l.46 wLeft.uframe:=PoseMult("))
    assert found[start + 2].endswith(",2]-100")  # the table's frame read back (its bank), y moved by -100


def test_a_frame_known_now_is_computed_now_not_inlined():
    result = conversion("tA:=MakeTool(tFixed,tOfsA);")
    assert todo(result) == [] and inlined(result) == []
    assert result.computed_frames[0].key == "0.000,20.000,140.000,0.000,0.000,0.000"


def test_a_body_with_an_if_stays_todo_naming_the_func_and_the_statement():
    ((note,),) = [todo(conversion("tA:=Checked(tBase,tOfsA);"))]
    assert note.category == Blocker.RUNTIME_FRAME
    assert "Checked() is not inlined: l." in note.message
    assert "`IF tB0.tframe.trans.z < 100` (only assignments, pose functions and one RETURN" in note.message


def test_a_func_returning_another_func_is_inlined_in_turn():
    result = conversion("tA:=Twice(tBase,tOfsA);")
    assert todo(result) == []
    assert sorted(m.split(" of ")[0] for m in inlined(result)) == ["FUNC MakeTool()", "FUNC Twice()"]


def test_a_call_left_todo_is_not_counted():
    result = conversion("tA:=MakeTool(tBase,tOfsA);\ntB:=MakeTool(tBase,tOfsB);", LENGTH + "\n" + TURN)
    assert inlined(result) == []


def _body(func: str, call: str) -> list[str]:
    module = parse_text(f"MODULE X\n{func}\nPROC m()\n{call}\nENDPROC\nENDMODULE\n", path="X.mod").module
    assert module is not None
    routine = next(r for r in module.routines if r.kind == "FUNC")
    stmt = next(r for r in module.routines if r.kind == "PROC").body[0]
    assert isinstance(stmt, n.Assign) and isinstance(stmt.value, n.FuncCall)
    made = inline_body(routine, stmt.value, stmt.target, stmt.span, layouts=Layouts([module]))
    return [f"{format_expr(s.target)} := {format_expr(s.value)}" for s in made]


def test_the_body_is_rewritten_on_the_target_its_locals_substituted():
    func = ("FUNC tooldata Turn(tooldata t0,num a)\nVAR pose pe;\nVAR tooldata r;\npe:=[[0,0,0],OrientZYX(a,0,0)];\n"
            "r:=t0;\nr.tframe:=PoseMult(t0.tframe,pe);\nRETURN r;\nENDFUNC")  # fmt: skip
    assert _body(func, "tX:=Turn(tY,30);") == ["tX := tY", "tX.tframe := PoseMult(tY.tframe, [[0, 0, 0], OrientZYX(30, 0, 0)])"]
    # The target given as the argument: `r := t0` is itself; read after the result changed: refused
    assert _body(func, "tY:=Turn(tY,30);") == ["tY.tframe := PoseMult(tY.tframe, [[0, 0, 0], OrientZYX(30, 0, 0)])"]
    late = ("FUNC tooldata Late(tooldata t0)\nVAR tooldata r;\nr:=[TRUE,[[0,0,1],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];\n"
            "r.tframe:=t0.tframe;\nRETURN r;\nENDFUNC")  # fmt: skip
    with pytest.raises(NotInlined, match="reads t0 .the call's target, tY. after setting its result"):
        _body(late, "tY:=Late(tY);")
    loop = "FUNC pose Loop(pose p)\nWHILE TRUE DO\nENDWHILE\nRETURN p;\nENDFUNC"
    with pytest.raises(NotInlined, match=r"Loop\(\) is not inlined: l.3 `WHILE TRUE`"):
        _body(loop, "pX:=Loop(pY);")
