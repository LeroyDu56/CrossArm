# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""SetSysData selects the active tool, work object or load by number; what reads them from the controller
(GetSysData, OpMode) stays TODO: a TP program reads no system variable on the measured controller (VARS-034)."""

from test_translate import HOME, TOOL, WOBJ, run, todos, tp_lines

LOAD = "PERS loaddata loBox:=[1.5,[0,0,20],[1,0,0,0],0,0,0];"


def test_the_active_frames_are_selected_by_number():
    result = run("SetSysData tGrip;\nSetSysData wFix;\nMoveL pHome,v100,fine,tGrip\\WObj:=wFix;", HOME + TOOL + WOBJ)
    assert not todos(result)
    assert tp_lines(result) == ["UTOOL_NUM=1", "UFRAME_NUM=1", "L P[1] 100mm/sec FINE"]  # the move selects nothing more


def test_a_load_is_the_payload_carried_as_gripload_says():
    load = run("SetSysData loBox;\nMoveL pHome,v100,fine,tGrip;", HOME + TOOL + LOAD)
    grip = run("GripLoad loBox;\nMoveL pHome,v100,fine,tGrip;", HOME + TOOL + LOAD)
    assert not todos(load) and tp_lines(load) == tp_lines(grip)
    assert any("as GripLoad loBox" in n.message for n in load.notes if n.kind == "WARNING")


def test_what_reads_the_controller_says_why():
    result = run("GetSysData tGrip;\nIF OpMode()=OP_AUTO Stop;\nSetSysData tGrip\\ObjectName:=\"tool0\";", TOOL)
    get, mode, named = todos(result)
    assert "GetSysData" in get and "VARS-034" in get
    assert "operating mode" in mode and "VARS-034" in mode
    assert "ObjectName" in named
