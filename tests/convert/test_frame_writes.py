# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A tool's tframe or a work object's uframe written part by part at run time, or copied from another frame
(crossarm.convert.frame_writes): the frame put in CROSSARM.FRAME (known now, or read back from UFRAME / UTOOL), its
parts written over it, then loaded; an oframe other than the identity by KAREL; a frame changed by a statement left
TODO is not read back."""

import re
from datetime import datetime

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.blockers import Blocker
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import parse_text

STAMP = datetime(2026, 1, 1)
DOWN = "[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]"
DATA = f"""MODULE FW
  PERS tooldata tPen:=[TRUE,[[10,0,120],[1,0,0,0]],[2,[0,0,40],[1,0,0,0],0,0,0]];
  PERS wobjdata wBase:=[FALSE,TRUE,"",[[800,0,500],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  PERS wobjdata wPlate:=[FALSE,TRUE,"",[[600,200,500],[1,0,0,0]],[[15,0,0],[1,0,0,0]]];
  CONST robtarget pA:=[[900,-100,500],{DOWN}];
  CONST robtarget pIn:=[[50,20,0],{DOWN}];
  VAR robtarget pM1;
  PROC Main()
    MoveL pA,v200,fine,tool0;
    pM1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);
    BODY
    MoveL pIn,v200,fine,tPen\\WObj:=wBase;
    MoveL pIn,v200,fine,tPen\\WObj:=wPlate;
  ENDPROC
  OTHER
ENDMODULE
"""
REG = r"PR\[\d+\]"


def conversion(body: str, other: str = "", karel: bool = False, data: str = DATA):
    text = data.replace("BODY", body).replace("OTHER", other)
    parsed = parse_text(text, path="FW.mod")
    assert parsed.module is not None, parsed.diagnostics
    return convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=karel), sources={"FW": text})


def lines(result) -> list[str]:
    text = write_ls(result.programs[0].program).split("/MN")[1].split("/POS")[0]
    return [line.split(":", 1)[1].strip().rstrip(";").strip() for line in text.splitlines() if ":" in line]


def todo(result) -> list:
    return [note for note in result.notes if note.kind == "TODO"]


def _after(found: list[str], remark: str) -> list[str]:
    start = next(i for i, line in enumerate(found) if line.startswith(f"!{remark}"))
    return found[start + 1 :]


def test_uframe_trans_and_rot_from_a_point_read_on_the_robot_by_tp_alone():
    result = conversion("wBase.uframe.trans:=pM1.trans;\n    wBase.uframe.rot:=pM1.rot;")
    assert not todo(result)
    found = lines(result)
    trans = _after(found, "l.11")[:5]
    assert re.fullmatch(rf"({REG})=UFRAME\[1\]", trans[0])
    work = trans[0].split("=")[0][:-1]
    point = next(line.split("=")[0] for line in found if line.endswith("=LPOS"))[:-1]
    assert trans[1:] == [f"{work},{i}]={point},{i}]" for i in (1, 2, 3)] + [f"UFRAME[1]={work}]"]
    rot = _after(found, "l.12")[:5]
    assert rot == [f"{work}]=UFRAME[1]"] + [f"{work},{i}]={point},{i}]" for i in (4, 5, 6)] + [f"UFRAME[1]={work}]"]
    assert result.karel_programs == []
    runtime = [n for n in result.notes if n.kind == "WARNING" and "wBase computed at run time and loaded" in n.message]
    assert len(runtime) == 1


def test_one_component_of_tframe_and_a_quaternion_known_now():
    body = "tPen.tframe.trans.z:=pM1.trans.z-380;\n    wBase.uframe.trans:=pM1.trans;\n    wBase.uframe.rot:=[0,0,0,1];"
    result = conversion(body)
    assert not todo(result)
    found = lines(result)
    tool = _after(found, "l.11")[:3]
    work = tool[0].split("=")[0]
    assert re.fullmatch(rf"{REG}=UTOOL\[2\]", tool[0])  # tool0 is UTOOL[1]
    assert re.fullmatch(rf"{re.escape(work[:-1])},3\]=PR\[\d+,3\]-380", tool[1]) and tool[2] == f"UTOOL[2]={work}"
    rot = _after(found, "l.13")[1:4]
    assert rot == [f"{work[:-1]},4]=0", f"{work[:-1]},5]=0", f"{work[:-1]},6]=180"]


def test_an_oframe_other_than_the_identity_needs_karel():
    plain = conversion("wPlate.uframe.trans:=pM1.trans;")
    (note,) = todo(plain)
    assert "oframe is not the identity" in note.message and "convert with --karel" in note.message
    assert note.category == Blocker.CALIBRATION  # read on the robot: a calibration
    assert plain.karel_todo == 1  # what --karel would convert, said in the report
    karel = conversion("wPlate.uframe.trans:=pM1.trans;", karel=True)
    assert not todo(karel)
    found = _after(lines(karel), "l.11")
    calls = [line for line in found if line.startswith("CALL CA_POSEMULT")]
    assert len(calls) == 2  # uframe x oframe read back x inverse(oframe), then the new uframe x oframe
    assert any(line.endswith(("=-15", "=(-15)")) for line in found)  # the inverse of the oframe


def test_a_frame_copied_to_work_objects_past_the_controllers_limit_goes_to_bank_registers():
    nests = "".join(f'  PERS wobjdata wN{i}:=[FALSE,TRUE,"",[[700,0,400],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];\n'
                    for i in range(1, 11))  # fmt: skip
    copies = "\n    ".join(f"wN{i}.uframe:=wBase.uframe;" for i in range(1, 11))
    moves = "\n    ".join(f"MoveL pIn,v200,fine,tPen\\WObj:=wN{i};" for i in range(1, 11))
    data = DATA.replace("  CONST robtarget pA", nests + "  CONST robtarget pA")
    result = conversion(f"wBase.uframe.trans:=pM1.trans;\n    {copies}\n    {moves}", data=data)
    assert not todo(result)
    found = lines(result)
    work = _after(found, "l.21")[0].split("=")[0]
    bank = _after(found, "l.21")[0].split("=")[1]  # wBase, used last, is past the limit: kept in a bank register
    assert re.fullmatch(REG, bank)
    copies = [_after(found, f"l.{22 + i}")[:2] for i in range(10)]
    assert all(pair[0] == f"{work}={bank}" for pair in copies)  # each copy reads wBase back
    assert [pair[1] for pair in copies[:8]] == [f"UFRAME[{i}]={work}" for i in range(1, 9)]
    assert all(re.fullmatch(rf"{REG}={re.escape(work)}", pair[1]) for pair in copies[8:])  # past the limit: banks
    assert not [line for line in found if line.startswith("CALL CA_")]


def test_a_frame_whose_change_was_left_todo_is_not_read_back():
    result = conversion("wBase.uframe:=Fit(pA);\n    wBase.uframe.rot:=pM1.rot;")
    first, second = todo(result)
    assert first.rapid_line == 11 and second.rapid_line == 12
    assert "its UFRAME is not what the RAPID holds" in second.message


def test_a_whole_uframe_from_a_trans_and_the_rot_of_another_frame():
    result = conversion("wBase.uframe.trans:=pM1.trans;\n    wPlate.uframe:=[pM1.trans,wBase.uframe.rot];", karel=True)
    assert not todo(result)
    found = _after(lines(result), "l.12")
    assert re.fullmatch(rf"{REG}=UFRAME\[1\]", found[3])  # wBase read back for its orientation
    assert any(line.startswith("CALL CA_POSEMULT") for line in found)  # wPlate's oframe multiplied in


def test_an_oframe_changed_after_the_uframe_was_set_at_run_time():
    body = ('wBase:=[FALSE,TRUE,"",[[800,0,500],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];\n'
            "    wBase.uframe.trans:=pM1.trans;\n    wBase.oframe:=[[0,0,10],[1,0,0,0]];")  # fmt: skip
    assert "convert with --karel" in todo(conversion(body))[0].message
    result = conversion(body, karel=True)
    assert not todo(result)
    found = _after(lines(result), "l.13")
    found = found[: next(i for i, line in enumerate(found) if line.startswith("UFRAME[1]=")) + 1]
    assert re.fullmatch(rf"{REG}=UFRAME\[1\]", found[0])
    assert any(line.startswith("CALL CA_POSEMULT") for line in found)
