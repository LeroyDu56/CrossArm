# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID -> TP translation rules, one behaviour per test."""

from datetime import datetime

import pytest
from helpers import parse_module

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.translate import Blocker
from crossarm.fanuc.tp import CartesianPosition, Instruction, JointPosition, Motion
from crossarm.rapid.eio import Signal

HOME = "CONST robtarget pHome:=[[600,0,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
TOOL = "PERS tooldata tGrip:=[TRUE,[[0,0,185.5],[1,0,0,0]],[2.4,[0,0,90],[1,0,0,0],0,0,0]];"
WOBJ = 'PERS wobjdata wFix:=[FALSE,TRUE,"",[[1000,0,0],[1,0,0,0]],[[0,0,100],[1,0,0,0]]];'


def run(body: str, data: str = "", config: ConversionConfig | None = None, extra_procs: str = ""):
    source = f"MODULE M\n{data}\nPROC main()\n{body}\nENDPROC\n{extra_procs}\nENDMODULE\n"
    config = config or ConversionConfig(timestamp=datetime(2026, 1, 1))
    return convert([parse_module(source)], config, routines=["main"], sources={"M": source})


def tp_lines(result) -> list[str]:
    """Program lines as text, without the leading '!RAPID M.main' remark."""
    out = []
    for line in result.programs[0].program.lines[1:]:
        if isinstance(line, Motion):
            via = f" {line.via}" if line.via else ""
            out.append(f"{line.kind}{via} {line.target} {line.speed} {line.termination}")
        else:
            out.append(line.text)
    return out


def todos(result) -> list[str]:
    return [note.message for note in result.notes if note.kind == "TODO"]


# ---------------------------------------------------------------------------
# Motion
# ---------------------------------------------------------------------------


def test_movel_emits_frames_then_motion_and_cartesian_point():
    result = run("MoveL pHome,v500,z10,tGrip\\WObj:=wFix;", HOME + TOOL + WOBJ)
    assert tp_lines(result) == ["UFRAME_NUM=1", "UTOOL_NUM=1", "L P[1] 500mm/sec CNT54"]
    (pos,) = result.programs[0].program.positions
    assert (pos.uf, pos.ut) == (1, 1)
    assert pos.value == CartesianPosition(600, 0, 900, 180, 0, 0)


def test_frames_are_only_emitted_when_they_change():
    result = run("MoveJ pHome,v1000,z50,tGrip;\nMoveL pHome,v100,fine,tGrip;", HOME + TOOL)
    assert tp_lines(result) == ["UFRAME_NUM=0", "UTOOL_NUM=1", "J P[1] 22% CNT92", "L P[1] 100mm/sec FINE"]


def test_same_target_reuses_the_same_point():
    result = run("MoveJ pHome,v1000,fine,tool0;\nMoveJ pHome,v1000,fine,tool0;", HOME)
    assert len(result.programs[0].program.positions) == 1


def test_offs_is_computed_at_conversion_time():
    result = run("MoveL Offs(pHome,10,-20,30),v100,fine,tool0;", HOME)
    value = result.programs[0].program.positions[0].value
    assert (value.x, value.y, value.z) == (610, -20, 930)


def test_reltool_moves_along_the_tool_axis():
    # Tool pointing down: +100 along tool Z is -100 in Z of the work object.
    result = run("MoveL RelTool(pHome,0,0,100),v100,fine,tool0;", HOME)
    assert result.programs[0].program.positions[0].value.z == pytest.approx(800)


def test_movec_has_via_and_target_points():
    data = HOME + "CONST robtarget pEnd:=[[700,100,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    result = run("MoveC pHome,pEnd,v200,z5,tool0;", data)
    assert tp_lines(result)[-1] == "C P[1] P[2] 200mm/sec CNT72"


def test_moveabsj_becomes_joint_point_with_warning():
    data = "CONST jointtarget jPark:=[[0,-30,30,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    result = run("MoveAbsJ jPark\\NoEOffs,v500,fine,tool0;", data)
    # Measured conventions: J3 absolute = -(J2 + J3), J4/J5 reversed, J6 = 180 - J6.
    assert result.programs[0].program.positions[0].value == JointPosition((0, -30, 0, 0, -90, 180))
    assert any("joint targets" in n.message for n in result.notes if n.kind == "WARNING")


STATIONARY = "PERS tooldata tFixed:=[FALSE,[[900,0,500],[1,0,0,0]],[1,[0,0,0],[1,0,0,0],0,0,0]];"
HELD = 'PERS wobjdata wHeld:=[TRUE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];'
PARK = "CONST jointtarget jPark:=[[0,-30,30,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"


def test_moveabsj_with_a_stationary_tool_is_made_with_the_tool_already_selected():
    """A joint target does not depend on the tool: only a Cartesian move needs the stationary tool."""
    result = run("MoveL pHome,v100,fine,tGrip;\nMoveAbsJ jPark,v500,fine,tFixed\\WObj:=wHeld;",
                 HOME + TOOL + STATIONARY + HELD + PARK)  # fmt: skip
    assert tp_lines(result) == ["UFRAME_NUM=0", "UTOOL_NUM=1", "L P[1] 100mm/sec FINE", "J P[2] 11% FINE"]
    point = result.programs[0].program.positions[1]
    assert (point.uf, point.ut) == (0, 1)  # the selected numbers: the controller checks them (INTP-253)
    assert todos(result) == []
    warnings = [n for n in result.notes if n.category == Blocker.STATIONARY]
    assert len(warnings) == 2 and all(n.kind == "WARNING" for n in warnings)
    # Numbered as when the move stayed TODO: the work object was, the tool it stopped was not.
    assert [a.rapid_name for a in result.uframes] == ["wobj0", "wHeld"]
    assert [a.rapid_name for a in result.utools] == ["tGrip"]


def test_moveabsj_with_a_stationary_tool_first_selects_tool0():
    result = run("MoveAbsJ jPark,v500,fine,tFixed;", STATIONARY + PARK)
    assert tp_lines(result) == ["UFRAME_NUM=0", "UTOOL_NUM=2", "J P[1] 11% FINE"]
    assert [a.rapid_name for a in result.utools] == ["tFixed", "tool0"]


def test_a_cartesian_move_with_a_stationary_tool_stays_todo():
    result = run("MoveL pHome,v100,fine,tFixed;", HOME + STATIONARY)
    assert [n.category for n in result.notes if n.kind == "TODO"] == [Blocker.STATIONARY]


def test_joint_mapping_can_be_disabled():
    data = "CONST jointtarget jPark:=[[0,-30,30,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    config = ConversionConfig(joint_mapping=False, timestamp=datetime(2026, 1, 1))
    result = run("MoveAbsJ jPark,v500,fine,tool0;", data, config)
    assert result.programs[0].program.positions[0].value == JointPosition((0, -30, 30, 0, 90, 0))


def test_tool_pin_on_plus_x_turns_the_tools_and_j6(tmp_path):
    """The tool's pin in the +x hole of the faceplate (ISO 9409-1): half a turn about z from the ABB flange."""
    mapping = tmp_path / "map.json"
    mapping.write_text('{"tool_pin": "+x"}', encoding="utf-8")
    config = ConversionConfig.from_mapping_file(mapping, timestamp=datetime(2026, 1, 1))
    tool = "PERS tooldata tSide:=[TRUE,[[30,-50,185.5],[0.9659258,0,0,0.2588190]],[2.4,[12,-8,90],[1,0,0,0],0,0,0]];"
    park = "CONST jointtarget jPark:=[[0,-30,30,0,90,40],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    result = run("MoveJ pHome,v1000,fine,tSide;\nMoveAbsJ jPark,v500,fine,tool0;", HOME + tool + park, config)
    (frame,) = [f.frame for f in result.utools if f.rapid_name == "tSide"]
    assert frame.pose.pos == (-30.0, 50.0, 185.5)
    assert frame.pose.wpr()[2] == pytest.approx(30 - 180)  # Rz(30) turned half a turn
    assert frame.load.cog == (-12, 8, 90) and tuple(frame.load.aom) == (1, 0, 0, 0)
    assert result.programs[0].program.positions[1].value == JointPosition((0, -30, 0, 0, -90, -40))
    with pytest.raises(ValueError, match="tool_pin"):
        mapping.write_text('{"tool_pin": "x"}', encoding="utf-8")
        ConversionConfig.from_mapping_file(mapping)


def test_custom_speeddata_and_zonedata_are_resolved():
    data = HOME + "PERS speeddata vSlow:=[250,30,500,50];\nCONST zonedata zBig:=[FALSE,120,150,150,15,150,15];"
    result = run("MoveJ pHome,vSlow,zBig,tool0;\nMoveL pHome,vSlow,zBig,tool0;", data)
    assert tp_lines(result)[-2:] == ["J P[1] 6% CNT100", "L P[1] 250mm/sec CNT100"]


def test_zones_are_matched_on_the_corner_cut_measured_at_each_speed():
    """The same z10 rounds a corner by about 5 mm on the ABB at any speed; a CNT, by more the faster the move."""
    data = HOME + "CONST robtarget pNext:=[[700,0,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    moves = "\n".join(f"MoveL pHome,v{v},z10,tool0;\nMoveL pNext,v{v},fine,tool0;" for v in (200, 500, 1000))
    result = run(moves, data)
    cnts = [line.split()[-1] for line in tp_lines(result) if line.startswith("L P[1]")]
    assert cnts == ["CNT97", "CNT54", "CNT31"]
    uses = {speed: use for (zone, speed, _, _), use in result.zones.items() if zone == "z10"}
    assert all(4.5 < use.abb_cut < 5.5 and abs(use.fanuc_cut - use.abb_cut) < 0.3 for use in uses.values())
    big = run("MoveL pHome,v500,z50,tool0;\nMoveL pNext,v500,fine,tool0;", data)
    (use,) = [u for (z, _, _, _), u in big.zones.items() if z == "z50"]
    assert use.tp == "CNT100" and use.capped  # 17 mm on the ABB: CNT100 rounds 12 at 500 mm/s


def test_a_corner_into_a_faster_move_is_matched_at_the_faster_speed():
    """Into a faster move the FANUC rounds more than at the zoned move's own speed (tools/make_path_probe.py:
    6.8 mm for the ABB's 4.9 off the top of a retract): the CNT is the one of the next move's speed."""
    data = HOME + "CONST robtarget pNext:=[[700,0,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    result = run("MoveL pHome,v300,z10,tool0;\nSetDO do1,1;\n! away\nMoveL pNext,v1000,fine,tool0;\n"
                 "MoveL pHome,v1000,z10,tool0;\nMoveL pNext,v300,fine,tool0;\n"
                 "MoveL pHome,v300,z10,tool0;\nWaitTime 1;\nMoveL pNext,v1000,fine,tool0;",
                 data + "\nVAR signaldo do1;")  # fmt: skip
    cnts = [line.split()[-1] for line in tp_lines(result) if line.startswith("L P[1]")]
    alone = run("MoveL pHome,v300,z10,tool0;\nMoveL pNext,v300,fine,tool0;", data)
    at_300 = next(line.split()[-1] for line in tp_lines(alone) if line.startswith("L P[1]"))
    # Into v1000, past an output and a remark: matched at 1000 mm/s, on the ABB's cut at 300 (4.9 mm, where
    # v1000 z10 cuts 5.4: CNT31). Into a slower move, or where the robot stops (WaitTime): at its own speed.
    assert cnts == ["CNT29", "CNT31", at_300] and at_300 == "CNT71"
    assert result.zones[("z10", "v300", "L", "v1000")].tp == "CNT29"


def test_the_old_zone_rule_is_still_there():
    config = ConversionConfig(zone_mapping="linear", cnt_per_mm=2, timestamp=datetime(2026, 1, 1))
    result = run("MoveL pHome,v500,z10,tool0;", HOME, config)
    assert tp_lines(result)[-1] == "L P[1] 500mm/sec CNT20"


def test_speed_heuristic_is_configurable():
    config = ConversionConfig(joint_speed_ref_mm_s=1000, timestamp=datetime(2026, 1, 1))
    result = run("MoveJ pHome,v500,fine,tool0;", HOME, config)
    assert tp_lines(result)[-1] == "J P[1] 50% FINE"


def test_target_set_at_run_time_becomes_todo_without_orphan_point():
    result = run("pTmp:=CRobT();\nMoveL pTmp,v100,fine,tool0;", HOME + "VAR robtarget pTmp;")
    assert result.programs[0].program.positions == []
    assert [line.startswith("!TODO l.") for line in tp_lines(result)] == [True, True]
    assert "measured on the robot at l.4" in todos(result)[1]
    assert {n.category for n in result.notes if n.kind == "TODO"} == {Blocker.CALIBRATION}


def test_untranslatable_move_keeps_the_rapid_source_in_the_remark():
    result = run("MoveL pUnknown,v100,fine,tool0;")
    assert tp_lines(result) == ["!TODO l.4 MoveL pUnknown,v100,fin"]  # 32 characters


# ---------------------------------------------------------------------------
# I/O, waits, calls
# ---------------------------------------------------------------------------


def test_set_reset_setdo_share_one_output_number():
    result = run("Set doGrip;\nReset doGrip;\nSetDO doGrip,1;")
    assert tp_lines(result) == ["DO[1]=ON", "DO[1]=OFF", "DO[1]=ON"]


def test_mapping_file_pins_numbers(tmp_path):
    mapping = tmp_path / "map.json"
    mapping.write_text('{"digital_outputs": {"DOGRIP": 12}, "utools": {"tGrip": 5}}', encoding="utf-8")
    config = ConversionConfig.from_mapping_file(mapping, timestamp=datetime(2026, 1, 1))
    result = run("Set doGrip;\nMoveJ pHome,v1000,fine,tGrip;", HOME + TOOL, config)
    assert tp_lines(result)[:3] == ["DO[12]=ON", "UFRAME_NUM=0", "UTOOL_NUM=5"]
    assert result.digital_outputs[0].fixed


def test_unknown_mapping_key_is_rejected(tmp_path):
    mapping = tmp_path / "map.json"
    mapping.write_text('{"registres": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="registres"):
        ConversionConfig.from_mapping_file(mapping)


def test_comments_follow_controller_rules():
    # Register comments survive only on registers the programs write; flag comments never.
    result = run("n:=1;\nIF m=2 AND bOk Stop;", "VAR num n;\nVAR num m;\nVAR bool bOk;")
    assert tp_lines(result) == ["R[1:n]=1", "IF (R[2]=2 AND F[1]=ON) THEN", "PAUSE", "ENDIF"]


def test_waits():
    result = run("WaitTime 0.5;\nWaitDI diReady,1;\nWaitUntil diReady=0 AND nCount>2;", "VAR num nCount;")
    assert tp_lines(result) == ["WAIT    .50(sec)", "WAIT DI[1]=ON", "WAIT (DI[1]=OFF AND R[1]>2)"]


def test_waittime_on_a_variable_uses_the_register():
    assert tp_lines(run("WaitTime tDelay;", "PERS num tDelay:=2;")) == ["WAIT R[1]"]


def test_calls_stop_return_exit():
    result = run("Sub;\nStop;\nRETURN;\nEXIT;", extra_procs="PROC Sub()\nENDPROC")
    assert tp_lines(result) == ["CALL SUB", "PAUSE", "END", "ABORT"]


def test_call_with_arguments_is_a_todo():
    result = run("Grip 3;")
    assert tp_lines(result) == ["!TODO l.4 Grip 3"]
    assert "with arguments" in todos(result)[0]


def test_tpwrite_fixed_text_becomes_message():
    result = run('TPErase;\nTPWrite "Cycle [A] start";\nTPWrite "Part "+"done";\nTPWrite "";')
    assert tp_lines(result) == ["MESSAGE[Cycle (A) start]", "MESSAGE[Part done]"]


def test_tpwrite_constant_and_long_text():
    result = run('TPWrite MSG;\nTPWrite "A message that is far too long for the pendant";', 'CONST string MSG:="Ready";')
    assert tp_lines(result) == ["MESSAGE[Ready]", "MESSAGE[A message that is far to]"]  # 24 characters
    assert any("cut to 24" in n.message for n in result.notes)


def test_tpwrite_with_a_value_shows_the_text_and_reports_the_value():
    result = run('TPWrite "Count: "\\Num:=n;\nTPWrite "Code "+ValToStr(n)+" ok";', "VAR num n;")
    assert tp_lines(result) == ["MESSAGE[Count:]", "MESSAGE[Code  ok]"]
    warnings = [x.message for x in result.notes if x.kind == "WARNING"]
    assert any("\\Num:=n" in w for w in warnings)
    assert any("ValToStr(n)" in w for w in warnings)
    assert not todos(result)


def test_tpwrite_values_setting_can_keep_the_todo():
    config = ConversionConfig(tpwrite_values="todo", timestamp=datetime(2026, 1, 1))
    result = run('TPWrite "Count: "\\Num:=n;', "VAR num n;", config)
    assert tp_lines(result)[0].startswith("!TODO")


def test_tpwrite_with_only_a_value_stays_a_todo():
    result = run("TPWrite ValToStr(n);", "VAR num n;")
    assert tp_lines(result)[0].startswith("!TODO")
    assert "only a value" in todos(result)[0]


def test_group_outputs_and_inputs():
    result = run("n:=GInput(giCode);\nSetGO goEcho,n;\nSetGO goStatus,3;", "VAR num n;")
    assert tp_lines(result) == ["R[1:n]=GI[1]", "GO[1]=R[1:n]", "GO[2]=3"]
    assert [a.rapid_name for a in result.group_outputs] == ["goEcho", "goStatus"]
    # A group output set from a group input: the controller refuses GO[1]=GI[1] (ASBN-092, ROBOGUIDE).
    result = run("SetGO goEcho,GInput(giCode);")
    assert tp_lines(result) == ["R[1:GroupCopy]=GI[1]", "GO[1]=R[1:GroupCopy]"]


def test_a_group_input_read_by_its_name():
    source = "MODULE M\nPROC main()\nIF giCode>0 AND diReady=1 THEN\nWaitTime 1;\nENDIF\nENDPROC\nENDMODULE\n"
    signals = {"GICODE": Signal("giCode", "GI"), "DIREADY": Signal("diReady", "DI")}
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), signals=signals)
    assert tp_lines(result)[0] == "IF (GI[1]>0 AND DI[1]=ON) THEN"


# ---------------------------------------------------------------------------
# Data and control flow
# ---------------------------------------------------------------------------


def test_num_and_bool_data_become_registers_and_flags():
    data = "PERS num nCycles:=0;\nVAR bool bDone:=FALSE;\nCONST num MAX:=3;"
    result = run("nCycles:=nCycles+1;\nnCycles:=MAX*2;\nbDone:=TRUE;", data)
    assert tp_lines(result) == ["R[1:nCycles]=R[1:nCycles]+1", "R[1:nCycles]=6", "F[1]=(ON)"]
    assert "initial value 0" in result.registers[0].detail


def test_if_elseif_else_is_unrolled_into_nested_ifs():
    result = run("IF n=1 THEN\n  Set doA;\nELSEIF n=2 THEN\n  Set doB;\nELSE\n  Reset doA;\nENDIF", "VAR num n;")
    assert tp_lines(result) == [
        "IF (R[1]=1) THEN", "DO[1]=ON",
        "ELSE",
        "IF (R[1]=2) THEN", "DO[2]=ON",
        "ELSE", "DO[1]=OFF",
        "ENDIF",
        "ENDIF",
    ]  # fmt: skip


def test_conditions_negation_is_pushed_down():
    result = run("IF NOT (n>2 AND diOk=1) Set doA;", "VAR num n;")
    assert tp_lines(result)[0] == "IF (R[1]<=2 OR DI[1]=OFF) THEN"
    # A negated group is still a group: it keeps its parentheses next to another operator.
    result = run("IF n>0 AND NOT (n>2 OR diOk=1) Set doA;", "VAR num n;")
    assert tp_lines(result)[0] == "IF (R[1]>0 AND (R[1]<=2 AND DI[1]=OFF)) THEN"


def test_signal_functions_in_conditions():
    result = run("IF DOutput(doA)=1 AND DInput(diB)=0 THEN\nENDIF")
    assert tp_lines(result)[0] == "IF (DO[1]=ON AND DI[1]=OFF) THEN"


def test_for_loops():
    result = run("FOR i FROM 1 TO 3 DO\n  n:=i;\nENDFOR\nFOR k FROM 5 TO 1 STEP -1 DO\nENDFOR", "VAR num n;")
    assert tp_lines(result) == [
        "FOR R[1:i]=1 TO 3", "R[2:n]=R[1:i]", "ENDFOR",
        "FOR R[3:k]=5 DOWNTO 1", "ENDFOR",
    ]  # fmt: skip


def test_for_with_other_step_is_a_todo():
    assert "STEP" in todos(run("FOR i FROM 0 TO 10 STEP 2 DO\nENDFOR"))[0]


def test_while_loops_use_labels():
    assert tp_lines(run("WHILE TRUE DO\n  Stop;\nENDWHILE")) == ["LBL[1]", "PAUSE", "JMP LBL[1]"]
    result = run("WHILE n<3 DO\n  n:=n+1;\nENDWHILE", "VAR num n;")
    assert tp_lines(result) == [
        "LBL[1]", "IF (R[1:n]>=3) THEN", "JMP LBL[2]", "ENDIF",
        "R[1:n]=R[1:n]+1", "JMP LBL[1]", "LBL[2]",
    ]  # fmt: skip


def test_test_case_becomes_select():
    """One SELECT line per CASE value; the branches behind labels, each ending on the common exit."""
    body = "TEST n\nCASE 1, 2:\n  Set doA;\n  Set doB;\nCASE -1:\n  Reset doA;\n  Reset doB;\nDEFAULT:\n  Stop;\nENDTEST"
    result = run(body, "VAR num n;")
    assert tp_lines(result) == [
        "SELECT R[1]=1,JMP LBL[2]",
        "       =2,JMP LBL[2]",
        "       =(-1),JMP LBL[3]",
        "       ELSE,JMP LBL[4]",
        "LBL[2]", "DO[1]=ON", "DO[2]=ON", "JMP LBL[1]",
        "LBL[3]", "DO[1]=OFF", "DO[2]=OFF", "JMP LBL[1]",
        "LBL[4]", "PAUSE",
        "LBL[1]",
    ]  # fmt: skip
    assert not todos(result)


def test_test_case_calls_are_made_on_the_select_lines():
    """A CALL on a SELECT line comes back after the SELECT (ROBOGUIDE): no label needed."""
    procs = "PROC palA()\nENDPROC\nPROC palB()\nENDPROC\n"
    result = run("TEST n\nCASE 1:\n  palA;\nCASE 2:\n  palB;\nCASE 3:\nENDTEST", "VAR num n;", extra_procs=procs)
    assert tp_lines(result) == [
        "SELECT R[1]=1,CALL PALA",
        "       =2,CALL PALB",
        "       =3,JMP LBL[1]",
        "LBL[1]",
    ]  # fmt: skip


def test_test_case_without_default_goes_on_after_the_select():
    result = run("TEST n\nCASE 1:\n  Set doA;\n  Set doB;\nCASE 2:\n  palA;\nENDTEST", "VAR num n;",
                 extra_procs="PROC palA()\nENDPROC\n")  # fmt: skip
    assert tp_lines(result) == [
        "SELECT R[1]=1,JMP LBL[2]",
        "       =2,CALL PALA",
        "JMP LBL[1]",
        "LBL[2]", "DO[1]=ON", "DO[2]=ON",
        "LBL[1]",
    ]  # fmt: skip


def test_test_case_on_an_argument_or_a_group_input_selects_a_copy():
    source = ("MODULE M\nPROC main()\nTEST giCode\nCASE 1:\n  Set doA;\nENDTEST\nENDPROC\n"
              "PROC sub(num k)\nTEST k\nCASE 1:\n  Set doA;\nENDTEST\nENDPROC\nENDMODULE\n")  # fmt: skip
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)),
                     signals={"GICODE": Signal("giCode", "GI")}, sources={"M": source})  # fmt: skip
    main, sub = (info.program.lines[1:4] for info in result.programs)
    assert [line.text for line in main] == ["R[1:TestValue]=GI[1]", "SELECT R[1:TestValue]=1,JMP LBL[2]", "JMP LBL[1]"]
    assert [line.text for line in sub] == ["R[1:TestValue]=AR[1]", "SELECT R[1:TestValue]=1,JMP LBL[2]", "JMP LBL[1]"]


def test_test_case_on_a_constant_keeps_its_branch_only():
    result = run("TEST MODE\nCASE 1:\n  Set doA;\nCASE 2:\n  Set doB;\nENDTEST", "CONST num MODE:=2;")
    assert tp_lines(result) == ["!l.4 TEST 2: one CASE", "DO[1]=ON"]


def test_test_case_on_a_string_or_a_variable_value_is_a_todo():
    result = run('TEST s\nCASE "A":\n  Set doA;\nENDTEST', "VAR string s;")
    assert [n.category for n in result.notes if n.kind == "TODO"] == [Blocker.CONDITION]
    result = run("TEST n\nCASE m:\n  Set doA;\nENDTEST", "VAR num n;\nVAR num m;")
    assert "CASE value 'm'" in todos(result)[0]


def test_test_case_branches_merge_what_they_know():
    """A value set in one CASE only is not known after the TEST: the move on it stays a TODO."""
    data = HOME + "VAR num n;\nVAR robtarget p;"
    result = run("p:=pHome;\nTEST n\nCASE 1:\n  p:=Offs(pHome,0,0,50);\nENDTEST\nMoveL p,v100,fine,tool0;", data)
    assert "branches of the TEST" in todos(result)[0]


def test_comments_are_split_to_32_characters():
    result = run("! " + "word " * 12)
    lines = tp_lines(result)
    assert len(lines) == 2 and all(len(line) <= 33 for line in lines)


def test_accents_are_folded_to_ascii():
    assert tp_lines(run("! réglage opérateur")) == ["! reglage operateur"]


# ---------------------------------------------------------------------------
# Program level
# ---------------------------------------------------------------------------


def test_routine_selection_and_skipped_routines():
    source = "MODULE M\nPROC a()\nENDPROC\nPROC b(robtarget x)\nENDPROC\nFUNC num f()\nRETURN 1;\nENDFUNC\nENDMODULE"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)))
    assert [p.program.name for p in result.programs] == ["A"]
    assert [(r, why.split(" ")[0]) for _, r, why in result.skipped_routines] == [("b", "parameters"), ("f", "FUNC")]


def test_system_modules_are_data_only_unless_requested():
    sys_module = parse_module(f"MODULE D(SYSMODULE)\n{HOME}\nPROC util()\nENDPROC\nENDMODULE")
    prog = parse_module("MODULE P\nPROC main()\nMoveJ pHome,v100,fine,tool0;\nENDPROC\nENDMODULE")
    result = convert([sys_module, prog], ConversionConfig(timestamp=datetime(2026, 1, 1)))
    assert [p.program.name for p in result.programs] == ["MAIN"]
    assert result.todo_count == 0  # pHome resolved from the system module


def test_program_names_are_sanitised_and_unique():
    source = "MODULE M\nPROC go_to_home()\nENDPROC\nLOCAL PROC Go_To_Home2()\nENDPROC\nENDMODULE"
    result = convert([parse_module(source)], ConversionConfig(program_name_max_length=8, timestamp=datetime(2026, 1, 1)))
    assert [p.program.name for p in result.programs] == ["GO_TO_HO", "GO_TO__2"]


def test_first_line_names_the_rapid_origin():
    result = run("Stop;")
    assert result.programs[0].program.lines[0] == Instruction("!RAPID M.main")


# ---------------------------------------------------------------------------
# A bug on one statement must not cost the whole conversion
# ---------------------------------------------------------------------------


def test_an_internal_error_becomes_a_todo_and_the_conversion_goes_on(monkeypatch):
    """Simulated bug in the WaitTime path: that line is marked, the rest is converted."""
    from crossarm.convert import translate

    def broken(self, expr):
        raise ZeroDivisionError("simulated")

    monkeypatch.setattr(translate._RoutineTranslator, "numeric", broken)
    result = run("MoveL pHome,v500,fine,tGrip;\nWaitTime 0.5;\nStop;", HOME + TOOL)
    lines = tp_lines(result)
    assert lines[-1] == "PAUSE"  # the statement after the bug is still converted
    [note] = [n for n in result.notes if n.category == translate.Blocker.INTERNAL]
    assert note.kind == "TODO"
    assert note.message.startswith("CrossArm internal error, please report it: ZeroDivisionError: simulated (at ")


def test_a_failed_statement_leaves_no_orphan_point(monkeypatch):
    """A P[n] created before the failure is dropped with the statement's lines."""
    from crossarm.convert import translate

    original = translate._RoutineTranslator.point

    def point_then_fail(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise RuntimeError("after the point")

    monkeypatch.setattr(translate._RoutineTranslator, "point", point_then_fail)
    result = run("MoveL pHome,v500,fine,tGrip;", HOME + TOOL)
    program = result.programs[0].program
    assert program.positions == [] and result.programs[0].points == ()


def test_routines_of_system_modules_the_programs_call_are_written_too():
    program = "MODULE Cell\nPROC main()\n  Helper;\nENDPROC\nENDMODULE\n"
    library = ("MODULE Lib(SYSMODULE)\nPROC Helper()\n  Deep;\nENDPROC\nPROC Deep()\n  Set doA;\nENDPROC\n"
               "PROC Unused()\n  Set doB;\nENDPROC\nENDMODULE\n")  # fmt: skip
    result = convert([parse_module(program), parse_module(library)], ConversionConfig(timestamp=datetime(2026, 1, 1)))
    assert [info.program.name for info in result.programs] == ["MAIN", "HELPER", "DEEP"]
    assert result.from_system == ["Lib.Helper", "Lib.Deep"]


TOOL_B = "PERS tooldata tB:=[TRUE,[[0,0,50],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];"


def test_frames_are_selected_again_where_they_may_have_changed():
    # After a CALL: the called program selects its own tool, and UTOOL_NUM is the controller's.
    other = "PROC Other()\n  MoveJ pHome,v100,fine,tB;\nENDPROC"
    result = run("MoveJ pHome,v100,fine,tGrip;\nOther;\nMoveJ pHome,v100,fine,tGrip;", HOME + TOOL + TOOL_B,
                 extra_procs=other)  # fmt: skip
    assert tp_lines(result) == ["UFRAME_NUM=0", "UTOOL_NUM=1", "J P[1] 2% FINE", "CALL OTHER",
                                "UFRAME_NUM=0", "UTOOL_NUM=1", "J P[1] 2% FINE"]  # fmt: skip
    # After an IF that may not run: the frames it selected are not known to be active.
    result = run("IF nX>0 THEN\n  MoveJ pHome,v100,fine,tGrip;\nENDIF\nMoveL pHome,v100,fine,tGrip;",
                 HOME + TOOL + "VAR num nX;")  # fmt: skip
    assert tp_lines(result)[-3:] == ["UFRAME_NUM=0", "UTOOL_NUM=1", "L P[1] 100mm/sec FINE"]
    # Both branches select the same: known after the IF.
    result = run("IF nX>0 THEN\n  MoveJ pHome,v100,fine,tGrip;\nELSE\n  MoveL pHome,v100,fine,tGrip;\nENDIF\n"
                 "MoveL pHome,v100,fine,tGrip;", HOME + TOOL + "VAR num nX;")  # fmt: skip
    assert tp_lines(result)[-2:] == ["ENDIF", "L P[1] 100mm/sec FINE"]
    # A loop: its second turn starts where the first ended.
    result = run("MoveJ pHome,v100,fine,tGrip;\nFOR i FROM 1 TO 2 DO\n  MoveJ pHome,v100,fine,tGrip;\n"
                 "  MoveJ pHome,v100,fine,tB;\nENDFOR", HOME + TOOL + TOOL_B)  # fmt: skip
    lines = tp_lines(result)
    start = lines.index("FOR R[1:i]=1 TO 2")
    assert lines[start + 1 : start + 3] == ["UFRAME_NUM=0", "UTOOL_NUM=1"]


def test_a_remark_cut_to_32_characters_ends_without_a_space():
    # The controller drops it when it stores the program (measured on ROBOGUIDE).
    result = run("Abcdefghijklmnopqrstuv 1;")  # 'TODO l.4 ' + 22 characters: the 32nd is the space
    assert tp_lines(result) == ["!TODO l.4 Abcdefghijklmnopqrstuv"]
