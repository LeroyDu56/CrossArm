# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The fields of a tool or work object followed one by one (crossarm.convert.frame_fields): a frame depends on the
fields it reads only, a field every program sets to its declared value does not change, ufprog / ufmec write no
frame, and a field left TODO makes only what reads that field TODO."""

from datetime import datetime

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.blockers import Blocker
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import parse_text

STAMP = datetime(2026, 1, 1)
DATA = """MODULE FF
  PERS tooldata tPen:=[TRUE,[[10,0,120],[1,0,0,0]],[2,[0,0,40],[1,0,0,0],0,0,0]];
  PERS tooldata tTip:=[TRUE,[[0,0,100],[1,0,0,0]],[2,[0,0,40],[1,0,0,0],0,0,0]];
  PERS wobjdata wBase:=[FALSE,TRUE,"",[[800,0,500],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  PERS wobjdata wPlate:=[FALSE,TRUE,"",[[600,200,500],[1,0,0,0]],[[15,0,0],[1,0,0,0]]];
  PERS pose peStep:=[[0,0,25],[1,0,0,0]];
  PERS num nLen:=0;
  CONST robtarget pA:=[[900,-100,500],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  CONST robtarget pB:=[[1000,-100,500],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  CONST robtarget pC:=[[900,0,500],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  CONST robtarget pIn:=[[50,20,0],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  VAR robtarget pM1;
  VAR robtarget pM2;
  VAR robtarget pM3;
  PROC Main()
    BODY
    MoveL pIn,v200,fine,tTip\\WObj:=wBase;
    MoveL pIn,v200,fine,tPen\\WObj:=wPlate;
  ENDPROC
  OTHER
ENDMODULE
"""


def conversion(body: str, other: str = "", karel: bool = False):
    text = DATA.replace("BODY", body).replace("OTHER", other)
    parsed = parse_text(text, path="FF.mod")
    assert parsed.module is not None, parsed.diagnostics
    return convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=karel), sources={"FF": text})


def lines(result) -> list[str]:
    text = write_ls(result.programs[0].program).split("/MN")[1].split("/POS")[0]
    return [line.split(":", 1)[1].strip().rstrip(";").strip() for line in text.splitlines() if ":" in line]


def todo(result) -> list:
    return [note for note in result.notes if note.kind == "TODO"]


def warnings(result, category: str) -> list[str]:
    return [note.message for note in result.notes if note.kind == "WARNING" and note.category == category]


def test_a_tool_frame_computed_while_robhold_and_tload_change():
    result = conversion("tPen.robhold:=TRUE;\n    tPen.tload.mass:=3;\n    nLen:=tPen.tframe.trans.z+peStep.trans.z;\n"
                        "    tTip.tframe:=PoseMult(tPen.tframe,peStep);")
    assert [n.category for n in todo(result)] == [Blocker.PAYLOAD]  # the payload alone
    body = lines(result)
    assert "!l.16 tPen.robhold:=TRUE" in body  # every program sets it as declared: nothing to write
    assert any(line.endswith("=120+25") for line in body)
    assert any(line.startswith("UTOOL[") and "=PR[" in line for line in body)  # tTip computed now, loaded here


def test_an_oframe_kept_as_declared_does_not_wait_for_the_uframe():
    result = conversion("wBase.uframe:=DefFrame(pA,pB,pC);\n    wBase.oframe:=[[0,0,0],[1,0,0,0]];\n"
                        "    wBase.ufprog:=TRUE;\n    wBase.ufmec:=\"\";")
    assert not todo(result), [n.message for n in todo(result)]
    body = lines(result)
    loads = [line for line in body if line.startswith("UFRAME[")]
    assert len(loads) == 1  # the uframe; the other three fields write nothing
    assert body[body.index(loads[0]) + 1].startswith("!l.17 wBase.oframe")


def test_a_field_left_todo_makes_only_what_reads_it_todo():
    result = conversion("wPlate.uframe:=FitPlate(pA,pB,pC);\n    wPlate.ufprog:=TRUE;\n    nLen:=wPlate.oframe.trans.x+5;\n"
                        "    wPlate.oframe:=[[0,0,0],[1,0,0,0]];\n    nLen:=wPlate.oframe.trans.x+1;")
    found = todo(result)
    assert [n.rapid_line for n in found] == [16, 18, 19]  # not the ufprog
    assert "'wPlate.oframe.trans.x'" in found[1].message  # changed at l.19 (and by an earlier run): not sure
    assert "'wPlate.uframe' is set at l.16 (left TODO)" in found[2].message  # UFRAME is uframe x oframe
    assert any(line.endswith("=0+1") for line in lines(result))  # the oframe it set: known


def test_a_whole_copy_needs_the_frame_fields_only():
    result = conversion("tPen.tload.mass:=3;\n    tTip:=tPen;")
    assert [n.category for n in todo(result)] == [Blocker.PAYLOAD]
    result = conversion("tPen.tframe:=FitTool(pA);\n    tTip:=tPen;")
    assert [n.rapid_line for n in todo(result)] == [16, 17]
    assert "'tPen.tframe' is set at l.16 (left TODO)" in todo(result)[1].message


def test_ufmec_and_ufprog_write_nothing_and_say_what_they_mean():
    result = conversion("wBase.ufmec:=\"STN1\";\n    wBase.ufprog:=FALSE;\n    wPlate.ufmec:=\"ROB_1\";")
    assert not todo(result)
    said = warnings(result, Blocker.STATIONARY)
    assert len(said) == 2 and "'STN1'" in said[0] and "ufprog FALSE" in said[1]
    assert not any(line.startswith("UFRAME[") for line in lines(result))


def test_a_field_set_to_another_value_elsewhere_is_changed():
    other = "PROC Other()\n    wPlate.oframe:=[[OX,0,0],[1,0,0,0]];\n  ENDPROC"
    same = conversion("nLen:=wPlate.oframe.trans.x;", other=other.replace("OX", "15"))
    assert not todo(same) and "R[1:nLen]=15" in lines(same)  # set as declared: not changed
    changed = conversion("nLen:=wPlate.oframe.trans.x;", other=other.replace("OX", "5"))
    assert [n.category for n in todo(changed)] == [Blocker.VALUE]


def test_karel_frame_whose_other_fields_every_program_sets_as_declared():
    body = ("pM1:=CRobT(\\Tool:=tool0);\n    pM2:=CRobT(\\Tool:=tool0);\n    pM3:=CRobT(\\Tool:=tool0);\n"
            "    wBase.ufprog:=TRUE;\n    wBase.uframe:=DefFrame(pM1,pM2,pM3);\n    wBase.oframe:=[[0,0,0],[1,0,0,0]];")
    result = conversion(body, karel=True)
    assert not todo(result), [n.message for n in todo(result)]
    assert any(line.startswith("CALL CA_DEFFRAME(") for line in lines(result))
    off = conversion(body)
    assert [n.category for n in todo(off)] == [Blocker.CALIBRATION]  # the uframe alone
