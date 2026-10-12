# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Conditions and values left TODO before 1.10: Abs() compared with a constant, the x / y / z of a robtarget
parameter, a PERS another task gives its value."""

from datetime import datetime

from helpers import parse_module
from test_translate import run, todos, tp_lines

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.shared_pers import saved_values
from crossarm.convert.translate import ControllerScope


def test_abs_compared_with_a_constant_is_two_comparisons():
    data = "VAR num korX;\nCONST num MaxKor:=0.05;"
    body = "korX:=nIn;\nWHILE abs(korX)>MaxKor DO\n  korX:=korX/2;\nENDWHILE\nIF Abs(korX)<=1 AND diA=1 Set doA;"
    result = run(body, data + "\nVAR num nIn;")
    assert todos(result) == []
    lines = tp_lines(result)
    assert lines[2] == "IF (R[1:korX]<=.05 AND R[1:korX]>=(-.05)) THEN"  # the loop exit: NOT (abs > c)
    assert lines[8] == "IF ((R[1:korX]<=1 AND R[1:korX]>=(-1)) AND DI[1]=ON) THEN"


def test_abs_compared_with_a_value_known_at_run_time_stays_todo():
    result = run("IF Abs(nA)>nB Set doA;", "VAR num nA;\nVAR num nB;")
    assert todos(result)


def test_the_x_y_z_of_a_robtarget_parameter_are_read_in_its_position_register():
    data = ("CONST robtarget pA:=[[100,0,500],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];\n"
            "CONST robtarget pB:=[[300,0,500],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];\nVAR num nCase;")  # fmt: skip
    procs = """PROC Place(robtarget pFrom)
  IF pFrom.trans.x>pA.trans.x AND pFrom.trans.z>400 THEN
    nCase:=1;
  ENDIF
  IF pFrom.trans.y=0 nCase:=2;
  MoveL pFrom,v100,fine,tool0;
ENDPROC"""
    source = f"MODULE M\n{data}\nPROC main()\nPlace pB;\nENDPROC\n{procs}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=["main", "Place"],
                     sources={"M": source})  # fmt: skip
    # An exact comparison would not hold: the point is written to 0.001 mm, and touched up on the robot.
    (todo,) = [x.message for x in result.notes if x.kind == "TODO"]
    assert "compared exactly" in todo
    place = next(i for i in result.programs if i.program.name == "PLACE")
    texts = [getattr(x, "text", "") for x in place.program.lines]
    test = next(x for x in texts if x.startswith("IF "))
    assert test.startswith("IF (PR[") and ",1]>100 AND PR[" in test and ",3]>400) THEN" in test, test


def test_a_pers_another_task_gives_its_value_is_read_at_that_value():
    left = parse_module("MODULE A\nPERS num nRings:=3;\nPROC main()\nENDPROC\nENDMODULE\n")
    source = "MODULE B\nPERS num nRings;\nVAR num i;\nPROC main()\nFOR i FROM 1 TO Pow(2,nRings)-1 DO\n  Set doA;\nENDFOR\nENDPROC\nENDMODULE\n"
    right = parse_module(source)
    cfg = ConversionConfig(timestamp=datetime(2026, 1, 1))
    alone = convert([right], cfg, routines=["main"], sources={"B": source})
    assert any("no initial value" in x.message for x in alone.notes if x.kind == "TODO")
    shared = ControllerScope.from_config(cfg)
    shared.saved_pers = saved_values([left, right])
    result = convert([right], cfg, routines=["main"], sources={"B": source}, shared=shared)
    assert [x.message for x in result.notes if x.kind == "TODO"] == []
    lines = [getattr(x, "text", "") for x in result.programs[0].program.lines]
    assert any(x.startswith("FOR R[") and x.endswith("TO 7") for x in lines), lines
    assert any("nRings, a PERS" in x.message for x in result.notes)  # read at the value the backup saved
    from crossarm.convert.html_report import build_html_report

    page = build_html_report(result, cfg, ["b.mod"], title="t")
    assert "PERS read at their saved value: check the value on the robot" in page  # a checklist item


def test_a_pers_two_tasks_give_different_values_is_not_taken():
    a = parse_module("MODULE A\nPERS num n:=3;\nTASK PERS num t:=1;\nENDMODULE\n")
    b = parse_module("MODULE B\nPERS num n:=4;\nPERS num m:=[1,2];\nPERS num k:=nOther;\nENDMODULE\n")
    assert set(saved_values([a, b])) == {"M"}  # n differs, t is the task's own, k is not a value written out
