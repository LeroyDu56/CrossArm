# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A jointtarget read on the robot (CJointT), kept in a joint position register: PR[k]=JPOS, its axes read
with the measured axis conventions, MoveAbsJ to it as J PR[k] (joints probe, ROBOGUIDE and RobotStudio)."""

from datetime import datetime

from test_translate import run, todos, tp_lines

from crossarm.convert import ConversionConfig
from crossarm.convert.translate import Blocker

DATA = "VAR jointtarget jNow;\nVAR num n;"


def test_cjointt_is_jpos_and_moveabsj_goes_back_to_it():
    result = run("jNow:=CJointT();\nMoveAbsJ jNow,v100,fine,tool0;", DATA)
    assert tp_lines(result) == ["PR[99]=JPOS", "UFRAME_NUM=0", "UTOOL_NUM=1", "J PR[99] 2% FINE"]
    assert todos(result) == []
    assert [(a.number, a.rapid_name) for a in result.point_registers] == [(99, "JNOW")]


def test_the_axes_are_worked_out_from_the_fanuc_joints_with_the_measured_conventions():
    reads = "\n".join(f"n:=jNow.robax.rax_{i};" for i in range(1, 7))
    result = run(f"jNow:=CJointT();\n{reads}", DATA)
    assert tp_lines(result) == [
        "PR[99]=JPOS",
        "R[1:n]=PR[99,1]",
        "R[1:n]=PR[99,2]",
        "R[2:Calc1]=PR[99,3]+PR[99,2]", "R[1:n]=R[2:Calc1]*(-1)",  # rax_3 = -(J3 + J2): J3 absolute on the FANUC
        "R[1:n]=PR[99,4]*(-1)",
        "R[1:n]=PR[99,5]*(-1)",
        "R[1:n]=180-PR[99,6]",  # the flanges differ by 180 deg about z
    ]  # fmt: skip
    assert todos(result) == []
    [warning] = [w for w in result.notes if w.category == Blocker.AXIS_CONVENTION]
    assert "rax_3 = -(J3+J2), rax_4 = -J4, rax_5 = -J5, rax_6 = 180-J6" in warning.message


def test_the_tool_pin_and_joint_mapping_change_the_readings_as_they_change_moveabsj():
    body = "jNow:=CJointT();\nn:=jNow.robax.rax_6;\nn:=jNow.robax.rax_3;"
    pin = run(body, DATA, ConversionConfig(timestamp=datetime(2026, 1, 1), tool_pin="+x"))
    assert tp_lines(pin)[1:] == ["R[1:n]=PR[99,6]*(-1)", "R[2:Calc1]=PR[99,3]+PR[99,2]", "R[1:n]=R[2:Calc1]*(-1)"]
    copied = run(body, DATA, ConversionConfig(timestamp=datetime(2026, 1, 1), joint_mapping=False))
    assert tp_lines(copied)[1:] == ["R[1:n]=PR[99,6]", "R[1:n]=PR[99,3]"]


def test_an_axis_in_a_calculation_and_in_conditions():
    body = ("jNow:=CJointT();\nn:=jNow.robax.rax_4+jNow.robax.rax_3;\n"
            "IF jNow.robax.rax_2>-30 n:=1;\nIF jNow.robax.rax_5<-40 THEN\n  n:=2;\nENDIF")  # fmt: skip
    assert tp_lines(run(body, DATA)) == [
        "PR[99]=JPOS",
        "R[2:Calc1]=PR[99,4]*(-1)", "R[3:Calc2]=PR[99,3]+PR[99,2]", "R[3:Calc2]=R[3:Calc2]*(-1)",
        "R[1:n]=R[2:Calc1]+R[3:Calc2]",
        "IF (PR[99,2]>(-30)) THEN", "R[1:n]=1", "ENDIF",
        "R[2:Calc1]=PR[99,5]*(-1)", "IF (R[2:Calc1]<(-40)) THEN", "R[1:n]=2", "ENDIF",
    ]  # fmt: skip


def test_a_wait_reads_only_the_axes_tp_reads_as_they_are():
    result = run("jNow:=CJointT();\nWaitUntil jNow.robax.rax_1>10;\nWaitUntil jNow.robax.rax_4>10;", DATA)
    assert tp_lines(result)[:2] == ["PR[99]=JPOS", "WAIT (PR[99,1]>10)"]
    assert "read again and again" in todos(result)[0]


def test_a_copy_is_another_register_and_a_constant_one_stays_todo():
    data = "VAR jointtarget jNow;\nVAR jointtarget jKeep;\nCONST jointtarget jHome:=[[0,0,0,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    result = run("jNow:=CJointT();\njKeep:=jNow;\nMoveAbsJ jKeep,v100,fine,tool0;\njNow:=jHome;", data)
    assert tp_lines(result)[:2] == ["PR[99]=JPOS", "PR[98]=PR[99]"]
    assert "J PR[98] 2% FINE" in tp_lines(result)
    assert "set to CJointT() or to another one kept in a register" in todos(result)[0]


def test_external_axes_and_writing_an_axis_stay_todo():
    body = "jNow:=CJointT();\nn:=jNow.extax.eax_a;\njNow.robax.rax_1:=5;\nMoveAbsJ jNow,v100,fine,tool0;"
    result = run(body, DATA)
    assert tp_lines(result)[0] == "PR[99]=JPOS"
    messages = todos(result)
    assert "CrossArm reads the robot's six axes (it writes no external axis)" in messages[0]
    assert "does not write them" in messages[1]
    assert "'jNow' is set at l.7 (left TODO)" in messages[2]  # its register was not set: not moved to


def test_a_jointtarget_never_read_on_the_robot_is_worked_out_as_before():
    data = "VAR jointtarget jGo:=[[0,0,0,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    result = run("MoveAbsJ jGo,v100,fine,tool0;", data)
    assert tp_lines(result)[-1] == "J P[1] 2% FINE" and not result.point_registers
