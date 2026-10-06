# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID -> TP translation rules, one behaviour per test."""

from datetime import datetime

import pytest
from helpers import parse_module

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.setup import build_setup
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


def test_waittime_on_a_calculation_works_it_out_first():
    lines = tp_lines(run("WaitTime PERIOD-tSpent;", "CONST num PERIOD:=0.5;\nVAR num tSpent;"))
    assert lines == ["R[1:Calc1]=.5-R[2]", "WAIT R[1:Calc1]"]


def test_a_byte_is_kept_in_a_register_as_a_num():
    result = run("nType:=nType+1;\nIF nType=3 Stop;", "VAR byte nType:=2;")
    assert tp_lines(result) == ["R[1:nType]=R[1:nType]+1", "IF (R[1:nType]=3) THEN", "PAUSE", "ENDIF"]
    assert todos(result) == []


def test_a_position_compared_as_a_whole_is_a_condition_todo():
    empty = "[[0,0,0],[1,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]]"
    result = run("IF pPick=pEmpty Stop;", f"VAR robtarget pPick;\nCONST robtarget pEmpty:={empty};")
    found = [n for n in result.notes if n.kind == "TODO"]
    assert [n.category for n in found] == [Blocker.CONDITION]
    assert found[0].message.startswith("'pPick' is a robtarget: TP compares and calculates numbers")


def test_calls_stop_return_exit():
    result = run("Sub;\nStop;\nRETURN;\nEXIT;", extra_procs="PROC Sub()\nENDPROC")
    assert tp_lines(result) == ["CALL SUB", "PAUSE", "END", "ABORT"]


def test_call_with_arguments_is_a_todo():
    result = run("SpeedRefresh 50;")  # RAPID's own, not converted
    assert tp_lines(result) == ["!TODO l.4 SpeedRefresh 50"]
    assert "with arguments" in todos(result)[0]
    assert [note.category for note in result.notes if note.kind == "TODO"] == [Blocker.CALL_ARGS]


def test_a_routine_or_data_the_backup_does_not_declare_says_what_to_add():
    result = run("Grip 3;\nOpenGripper;\nnCount:=nMissing+1;\nbDone:=TRUE;", data="VAR num nCount;")
    assert tp_lines(result) == ["!TODO l.4 Grip 3", "!TODO l.5 OpenGripper", "!TODO l.6 nCount:=nMissing+1",
                                "!TODO l.7 bDone:=TRUE"]  # fmt: skip
    assert [note.category for note in result.notes if note.kind == "TODO"] == [Blocker.MISSING] * 4
    add = "is not in the backup: add the module that declares it (system module, option, other task)"
    assert [message.split(" — ")[0] for message in todos(result)] == [
        f"routine 'Grip' {add}",
        f"routine 'OpenGripper' {add}",
        f"data 'nMissing' {add}, or EIO.cfg if it is a signal",  # no EIO.cfg in the backup: it may be one
        f"data 'bDone' {add}, or EIO.cfg if it is a signal",
    ]


def test_a_parameter_or_rapid_data_is_not_missing_from_the_backup():
    source = ("MODULE M\nVAR num nCount;\nPROC main()\n  Sub 2;\nENDPROC\nPROC Sub(num pTime)\n"
              "  IF ERRNO=ERR_WAIT_MAXTIME nCount:=0;\n  PulseDO \\PLength:=pTime, do1;\n  nCount:=nGone;\n"
              "ENDPROC\nENDMODULE\n")  # fmt: skip
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    categories = [note.category for note in result.notes if note.kind == "TODO"]
    # ERRNO is RAPID's, pTime the routine's own: what CrossArm cannot do yet; nGone is nobody's.
    assert categories == [Blocker.VALUE, Blocker.VALUE, Blocker.MISSING]


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


def warnings(result) -> list[tuple[str, str]]:
    return [(note.category, note.message) for note in result.notes if note.kind == "WARNING"]


def test_pulsedo_becomes_a_pulse_in_tenths_of_a_second():
    """ROBOGUIDE: 0.1 s steps, 0.25 stored 0.3, below 0.05 the length is dropped, 25.6 refused."""
    result = run("PulseDO doBlow;\nPulseDO\\High\\PLength:=1,doBlow;\nPulseDO\\PLength:=0.25,doBlow;\n"
                 "PulseDO\\PLength:=0.01,doBlow;")  # fmt: skip
    assert tp_lines(result) == ["DO[1]=PULSE,0.2sec", "DO[1]=PULSE,1.0sec", "DO[1]=PULSE,0.3sec", "DO[1]=PULSE,0.1sec"]
    assert [c for c, _ in warnings(result)] == [Blocker.IO_ROUNDED, Blocker.IO_ROUNDED]
    assert "25.5 s at most" in todos(run("PulseDO\\PLength:=30,doBlow;"))[0]


def test_invertdo_inverts_the_output():
    assert tp_lines(run("InvertDO doLamp;")) == ["DO[1]=(!DO[1])"]


def test_setao_needs_the_scale_of_the_fanuc_module():
    data = "VAR num nRpm;"
    body = "SetAO aoFlow,4.5;\nSetAO aoFlow,nRpm/1000;"
    result = run(body, data)
    assert all("analog_scales.aoFlow" in t for t in todos(result))
    assert [a.rapid_name for a in result.analog_outputs] == ["aoFlow"]  # numbered, for the mapping file
    result = run(body, data, config=ConversionConfig(analog_scales={"AOFLOW": 409.5},
                                                     timestamp=datetime(2026, 1, 1)))  # fmt: skip
    assert tp_lines(result) == ["AO[1]=1843", "R[1:AnalogCopy]=R[2]/1000", "R[1:AnalogCopy]=R[1:AnalogCopy]*409.5",
                                "AO[1]=R[1:AnalogCopy]"]  # fmt: skip


def test_rapid_clocks_become_timers_apart_from_the_wait_timer():
    body = ("ClkReset ckCycle;\nClkStart ckCycle;\nWaitDI diGo,1\\MaxTime:=2;\nClkStop ckCycle;\n"
            "nTime:=ClkRead(ckCycle);\nERROR\nTRYNEXT;")  # fmt: skip
    result = run(body, "VAR clock ckCycle;\nVAR num nTime;")
    lines = tp_lines(result)
    assert lines[:2] == ["TIMER[1]=RESET", "TIMER[1]=START"]
    assert "TIMER[1]=STOP" in lines and "R[2:nTime]=TIMER[1]" in lines
    assert result.wait_clock[0] == "TIMER[10]" and [a.number for a in result.timers] == [1]


def test_motion_settings_fanuc_does_its_own_way_are_warnings():
    result = run("ConfL\\Off;\nConfJ\\On;\nSingArea\\Wrist;\nSingArea\\Off;\nCirPathMode\\PathFrame;\n"
                 "AccSet 100,100;\nVelSet 100,2000;")  # fmt: skip
    assert tp_lines(result) == []
    assert [c for c, _ in warnings(result)] == [Blocker.MOTION_SETTING] * 3


def test_motion_settings_that_slow_the_robot_stay_todo():
    """Dropping them would run the FANUC faster than the ABB."""
    result = run("AccSet 50,50;\nVelSet 50,250;")
    assert [n.category for n in result.notes if n.kind == "TODO"] == [Blocker.MOTION_SETTING] * 2


def test_interrupts_are_their_own_blocker():
    source = ("MODULE M\nVAR intnum iStop;\nPROC main()\nCONNECT iStop WITH tStop;\nISignalDI diStop,1,iStop;\n"
              "IDelete iStop;\nENDPROC\nTRAP tStop\nStop;\nENDTRAP\nENDMODULE\n")  # fmt: skip
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)),
                     routines=["main"], sources={"M": source})  # fmt: skip
    assert [n.category for n in result.notes if n.kind == "TODO"] == [Blocker.INTERRUPT] * 3


LOAD = "PERS loaddata lBox:=[5,[0,0,100],[1,0,0,0],0.1,0.1,0.1];"


def test_gripload_selects_the_payload_of_the_tool_with_the_part():
    """A FANUC schedule is all the flange carries: the tool and the part together, numbered from the top down;
    load0 goes back to the tool's own schedule, its UTOOL number."""
    body = "GripLoad lBox;\nMoveL pHome,v100,fine,tGrip;\nGripLoad load0;\nMoveL pHome,v100,fine,tGrip;"
    result = run(body, HOME + TOOL + LOAD)
    assert tp_lines(result) == ["PAYLOAD[10]", "UFRAME_NUM=0", "UTOOL_NUM=1", "L P[1] 100mm/sec FINE", "PAYLOAD[1]",
                                "L P[1] 100mm/sec FINE"]  # fmt: skip
    gripped, alone = sorted(result.grip_payloads, key=lambda s: s.load is None)
    assert (gripped.key, gripped.number, alone.key, alone.number) == ("tGrip+lBox", 10, "tGrip", 1)
    # tGrip: 2.4 kg at z 90; lBox: 5 kg 100 mm past the TCP (z 185.5): together 7.4 kg at z 222.09
    assert gripped.payload.mass == pytest.approx(7.4)
    assert gripped.payload.cog == pytest.approx((0, 0, (2.4 * 90 + 5 * 285.5) / 7.4))
    assert gripped.payload.inertia[0] == pytest.approx(0.1 + 2.4 * 0.13209459**2 + 5 * 0.06340541**2, rel=1e-4)


def test_gripload_takes_the_tool_selected_or_the_task_s_only_one():
    result = run("MoveL pHome,v100,fine,tGrip;\nGripLoad lBox;", HOME + TOOL + LOAD)
    assert tp_lines(result)[-1] == "PAYLOAD[10]"
    source = (f"MODULE M\n{HOME}{TOOL}{LOAD}\nPROC main()\nMoveL pHome,v100,fine,tGrip;\nENDPROC\n"
              "PROC grip()\nGripLoad lBox;\nENDPROC\nENDMODULE\n")  # fmt: skip
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert "PAYLOAD[10]" in [getattr(line, "text", "") for info in result.programs for line in info.program.lines]


def test_gripload_with_several_tools_or_a_load_changed_at_run_time_is_a_todo():
    tools = TOOL + "PERS tooldata tOther:=[TRUE,[[0,0,100],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];"
    result = run("GripLoad lBox;\nMoveL pHome,v100,fine,tGrip;\nMoveL pHome,v100,fine,tOther;", HOME + tools + LOAD)
    assert "2 tools" in todos(result)[0]
    result = run("lBox.mass:=7;\nGripLoad lBox;\nMoveL pHome,v100,fine,tGrip;", HOME + TOOL + LOAD)
    assert any("GripLoad lBox: load only known at run time" in t for t in todos(result))


SLOTS = ("CONST robtarget pSlot{3}:=[[[100,0,300],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],"
         "[[200,0,300],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],"
         "[[300,0,300],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]]];VAR num n:=1;")


def test_an_array_of_points_indexed_at_run_time_is_read_from_position_registers():
    """SETUP_FRAMES keeps the array in consecutive registers; the program works the index out once and reads PR[R[n]]."""
    result = run("MoveL pSlot{n},v100,fine,tGrip;\nMoveL Offs(pSlot{n},0,0,50),v100,fine,tGrip;\nMoveL pSlot{2},v100,fine,tGrip;",
                 SLOTS + TOOL)  # fmt: skip
    assert tp_lines(result) == [
        "R[2:PointIndex]=R[1]", "R[2:PointIndex]=R[2:PointIndex]+95",  # {n} of 3 from PR[96]: n + 95
        "UFRAME_NUM=0", "UTOOL_NUM=1", "L PR[R[2]] 100mm/sec FINE",
        "PR[99]=PR[R[2]]", "PR[99,3]=PR[99,3]+50", "L PR[99] 100mm/sec FINE",  # Offs() in CROSSARM.POINT
        "L P[1] 100mm/sec FINE",  # a fixed element: a point like any other
    ]  # fmt: skip
    ((array),) = result.point_arrays
    assert (array.name, array.dims, array.base, [v.x for v in array.values]) == ("pSlot", (3,), 96, [100, 200, 300])
    setup = build_setup(result, ConversionConfig(), "SETUP_FRAMES")
    assert [line.text for line in setup.program.lines if line.text.startswith("PR[9")] == [
        "PR[96]=P[2]", "PR[97]=P[3]", "PR[98]=P[4]"]


def test_the_index_is_worked_out_again_after_what_may_change_it():
    result = run("MoveL pSlot{n},v100,fine,tGrip;\nn:=n+1;\nMoveL pSlot{n},v100,fine,tGrip;", SLOTS + TOOL)
    assert sum(line.endswith("+96") for line in tp_lines(result)) == 2


def test_the_mapping_file_pins_the_first_register_of_an_array(tmp_path):
    path = tmp_path / "map.json"
    path.write_text('{"point_arrays": {"pSlot": 40}}', encoding="utf-8")
    config = ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))
    result = run("MoveL pSlot{n},v100,fine,tGrip;", SLOTS + TOOL, config=config)
    assert "R[2:PointIndex]=R[2:PointIndex]+39" in tp_lines(result)
    assert [(a.base, a.fixed) for a in result.point_arrays] == [(40, True)]


TABLE = "CONST num TORQUE{3}:=[1.5,2,-0.5];PERS num LIMIT{2}:=[5,6];VAR num nSum;VAR num k:=1;VAR num nCount{2};"


def test_an_array_of_numbers_indexed_at_run_time_is_read_from_registers():
    result = run("nSum:=nSum+TORQUE{k};\nnSum:=TORQUE{2}*2;", TABLE)
    assert tp_lines(result) == ["R[3:NumberIndex]=R[2]", "R[3:NumberIndex]=R[3:NumberIndex]+197",
                                "R[1:nSum]=R[1:nSum]+R[R[3]]", "R[1:nSum]=4"]  # fmt: skip
    assert [(a.name, a.base, a.values) for a in result.number_arrays] == [("TORQUE", 198, (1.5, 2.0, -0.5))]
    setup = build_setup(result, ConversionConfig(), "SETUP_FRAMES")
    assert [line.text for line in setup.program.lines if line.text.startswith("R[")] == [
        "R[198]=1.5", "R[199]=2", "R[200]=(-.5)"]


def test_two_elements_in_one_statement_take_two_index_registers():
    lines = tp_lines(run("nSum:=TORQUE{k};\nnSum:=TORQUE{k}+LIMIT{k};", TABLE))
    assert lines[-1] == "R[1:nSum]=R[R[3]]+R[R[4]]"


def test_a_pers_table_no_program_changes_is_kept_and_a_var_no_program_sets_is_not():
    result = run("nSum:=LIMIT{k};", TABLE)
    assert any("PERS array kept in registers" in n.message for n in result.notes if n.kind == "WARNING")
    assert "nCount is a VAR" in todos(run("nSum:=nCount{k};", TABLE))[0]


def test_an_array_the_programs_change_is_written_in_its_registers():
    """ROBOGUIDE: R[R[50]]=R[R[50]]+1, R[R[50]]=(-2.5), R[R[50]]=R[R[52]] load and run as RAPID does."""
    result = run("LIMIT{1}:=3;\nLIMIT{k}:=LIMIT{k}+1;\nnSum:=LIMIT{k};\nnCount{k+1}:=nSum*2;", TABLE)
    assert todos(result) == []
    assert tp_lines(result) == [
        "R[199]=3",  # LIMIT{1}: its own register
        "R[2:NumberIndex]=R[1]", "R[2:NumberIndex]=R[2:NumberIndex]+198", "R[R[2]]=R[R[2]]+1",
        "R[3:nSum]=R[R[2]]",
        "R[4:Calc8]=R[1]+1", "R[2:NumberIndex]=R[4:Calc8]", "R[2:NumberIndex]=R[2:NumberIndex]+196",
        "R[R[2]]=R[3:nSum]*2"]  # fmt: skip
    assert [(a.name, a.base, a.values) for a in result.number_arrays] == [("LIMIT", 199, (5.0, 6.0)),
                                                                         ("nCount", 197, (0.0, 0.0))]  # fmt: skip
    warnings = [n.message for n in result.notes if n.kind == "WARNING"]
    assert any(m.startswith("LIMIT, an array the programs change") and "values saved in the backup" in m
               for m in warnings)  # fmt: skip
    assert any(m.startswith("nCount, an array the programs change") and "RAPID sets a VAR again" in m for m in warnings)


def test_an_index_out_of_the_array_or_an_array_of_a_routine_stays_todo():
    assert "index out of the array" in todos(run("LIMIT{3}:=1;", TABLE))[0]
    assert "an array of numbers of a routine" in todos(run("VAR num nOwn{2};\nnOwn{k}:=1;", TABLE))[0]


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
    source = "MODULE M\nPROC a()\nENDPROC\nPROC b(dnum x)\nENDPROC\nFUNC num f()\nRETURN 1;\nENDFUNC\nENDMODULE"
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


# ---------------------------------------------------------------------------
# Calculations of several operations, points worked out at run time
# ---------------------------------------------------------------------------


def test_a_calculation_of_several_operations_is_made_one_per_line():
    """TP refuses `+` and `*` in one calculation (ASBN-040): scratch registers, the left side in the first."""
    data = "VAR num nA:=0;\nVAR num nB:=1;\nVAR num nC:=2;"
    assert tp_lines(run("nA:=(nB-1)*600+nC*3;", data)) == [
        "R[2:Calc1]=R[3]-1", "R[2:Calc1]=R[2:Calc1]*600", "R[4:Calc2]=R[5]*3", "R[1:nA]=R[2:Calc1]+R[4:Calc2]"]


def test_a_wait_on_a_calculation_stays_todo():
    """Worked out once before the WAIT, it would not follow the data the WAIT waits on."""
    result = run("WaitUntil nA+nB>3;", "VAR num nA:=0;\nVAR num nB:=1;")
    assert len(todos(result)) == 1


PALLET = HOME + TOOL + WOBJ + "VAR robtarget pPlace;\nVAR num nCol:=1;\n"


def test_a_point_worked_out_from_run_time_data_is_kept_in_a_position_register():
    body = ("nCol:=nCol+1;\npPlace:=Offs(pHome,(nCol-1)*100,0,0);\nIF nCol=2 pPlace:=RelTool(pPlace,0,0,0\\Rz:=90);\n"
            "MoveL pPlace,v100,fine,tGrip\\WObj:=wFix;")
    lines = tp_lines(run(body, PALLET))
    assert lines[1:5] == ["PR[99]=P[1]", "R[2:Calc1]=R[1:nCol]-1", "R[2:Calc1]=R[2:Calc1]*100",
                          "PR[99,1]=PR[99,1]+R[2:Calc1]"]  # fmt: skip
    assert "PR[99,6]=(-90)" in lines and lines[-1] == "L PR[99] 100mm/sec FINE"


def test_crobt_is_lpos_in_the_frames_it_names():
    body = "pPlace:=CRobT(\\Tool:=tGrip\\WObj:=wFix);\npPlace.trans.z:=pPlace.trans.z+50;\nMoveL pPlace,v100,fine,tGrip\\WObj:=wFix;"
    lines = tp_lines(run(body, PALLET))
    assert lines[:4] == ["UFRAME_NUM=1", "UTOOL_NUM=1", "PR[99]=LPOS", "PR[99,3]=PR[99,3]+50"]


def test_a_point_whose_assignment_is_left_todo_is_never_moved_to():
    """Its register was not set: the moves to it stay TODO, with why, not moves to whatever it holds."""
    body = "pPlace:=Offs(pHome,GInput(giX)*Abs(nCol),0,0);\nMoveL pPlace,v100,fine,tGrip;"
    result = run(body, PALLET)
    assert [line.startswith("!TODO") for line in tp_lines(result)] == [True, True]
    assert "'pPlace' is set at l." in todos(result)[1]


def test_a_var_array_no_program_changes_holds_its_declared_values():
    data = HOME + TOOL + "VAR num nOffsets{3}:=[0,120,240];\nVAR num nSlot:=1;\n"
    result = run("nSlot:=nSlot+1;\nMoveL Offs(pHome,nOffsets{nSlot},0,0),v100,fine,tGrip;", data)
    assert todos(result) == []


def test_a_hexadecimal_literal_is_written_in_decimal():
    assert tp_lines(run("nMask:=0xFF00;", "VAR num nMask;")) == ["R[1:nMask]=65280"]


def test_a_point_nobody_set_is_a_todo_not_an_internal_error():
    """[0,0,0,0] is the orientation of a PERS the program fills in before moving there."""
    data = "PERS robtarget pDummy:=[[0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0,0,0]];"
    result = run("MoveL pDummy,v200,fine,tool0;", data)
    assert [line.startswith("!TODO") for line in tp_lines(result)] == [True]
    assert "the orientation of pDummy, [0, 0, 0, 0], is not a unit quaternion: a value only set at run time" in todos(result)[0]
    assert {n.category for n in result.notes if n.kind == "TODO"} == {Blocker.VALUE}


def test_tools_work_objects_and_point_arrays_with_no_rotation_are_todo():
    data = (HOME + "PERS tooldata tNone:=[TRUE,[[0,0,100],[0,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];\n"
            'PERS wobjdata wNone:=[FALSE,TRUE,"",[[0,0,0],[0,0,0,0]],[[0,0,0],[1,0,0,0]]];\n'
            "CONST robtarget pRow{2}:=[[[1000,0,500],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],"
            "[[1000,0,500],[0,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]]];\nVAR num i:=1;\n")
    body = "MoveL pHome,v100,fine,tNone;\nMoveL pHome,v100,fine,tool0\\WObj:=wNone;\nFOR i FROM 1 TO 2 DO\nMoveL pRow{i},v100,fine,tool0;\nENDFOR"
    result = run(body, data)
    # A frame is numbered all the same: SETUP_FRAMES leaves it unset, with why, as a frame set at run time.
    problems = {frame.rapid_name: frame.problem for frame in [*result.utools, *result.uframes]}
    assert "tNone, [0, 0, 0, 0], is not a unit quaternion" in problems["tNone"]
    assert "wNone.uframe, [0, 0, 0, 0], is not a unit quaternion" in problems["wNone"]
    assert ["pRow{2}, [0, 0, 0, 0], is not a unit quaternion" in m for m in todos(result)] == [True]


def test_a_load_with_no_inertia_keeps_its_mass_whatever_its_axes():
    data = HOME + "PERS tooldata tLoad:=[TRUE,[[0,0,100],[1,0,0,0]],[3,[0,0,50],[0,0,0,0],0,0,0]];"
    result = run("MoveL pHome,v100,fine,tLoad;", data)
    assert todos(result) == []
    assert [(f.frame.load.mass, f.frame.load.aom) for f in result.utools] == [(3, (1.0, 0.0, 0.0, 0.0))]


def test_gripload_on_a_tool_whose_load_has_no_axes_of_moment():
    """1.2.0 stopped the whole conversion here (zero-length quaternion): the load has no inertia to turn."""
    data = HOME + ("PERS tooldata tLoad:=[TRUE,[[0,0,100],[1,0,0,0]],[3,[0,0,50],[0,0,0,0],0,0,0]];\n"
                   "PERS loaddata lPart:=[2,[0,0,10],[1,0,0,0],0,0,0];")
    result = run("MoveL pHome,v100,fine,tLoad;\nGripLoad lPart;", data)
    assert todos(result) == []
    assert tp_lines(result)[-1] == "PAYLOAD[10]"


@pytest.mark.parametrize(("value", "text"), [
    (300.000215, "300.000215"), (12.345678, "12.345678"), (99999.99, "99999.99"), (0.25, "0.25"),
    (0.0000015, "0.0000015"), (-2.5, "-2.5"), (1234567.5, "1234567.5"), (123456.7, "123456.7"),
])  # fmt: skip
def test_constants_are_written_with_the_digits_the_controller_runs_with(value, text):
    """ROBOGUIDE lists R[79]=300.000215 as 300 but runs with 300.000214, and 1234567.5 with 1234567.5."""
    from crossarm.convert.translate import fmt_number

    assert fmt_number(value) == text


@pytest.mark.parametrize("text", ["1234567", "99999999", "16777215", "0xFFFFFF", "123456789", "2147483646",
                                  "-2147483646", "1999999999"])  # fmt: skip
def test_whole_numbers_a_register_keeps_are_written_digit_for_digit(text):
    """Measured on ROBOGUIDE: each read back from NUMREG.VA as written."""
    value = int(text, 0)
    assert tp_lines(run(f"nId:={text};", "VAR num nId;")) == [f"R[1:nId]={value if value >= 0 else f'({value})'}"]


@pytest.mark.parametrize("text", ["2147483647", "0xFFFFFFFF", "-2147483648", "4294967295", "1E10"])
def test_a_constant_past_what_a_register_line_keeps_is_a_todo(text):
    """ROBOGUIDE stores R[60]=2147483647 as `********`, -2147483648 as -129, 4294967295 as 4.29497e+09."""
    result = run(f"nId:={text};\nIF nId={text} nId:=0;", "VAR num nId;")
    found = [n for n in result.notes if n.kind == "TODO"]
    assert [n.category for n in found] == [Blocker.VALUE, Blocker.VALUE]
    assert "too large for a TP register" in found[0].message


def test_a_constant_below_one_is_assigned_without_its_zero():
    assert tp_lines(run("nGap:=0.25;\nnGap:=-0.5;\nnGap:=nGap*0.5;", "VAR num nGap;")) == [
        "R[1:nGap]=.25", "R[1:nGap]=(-.5)", "R[1:nGap]=R[1:nGap]*.5"]


@pytest.mark.parametrize(("body", "data", "start"), [
    ('Open "HOME:"\\File:="log.txt",fLog\\Append;', "VAR iodev fLog;", "Open: files and serial channels"),
    ('Write fLog,"cycle";', "VAR iodev fLog;", "Write: files and serial channels"),
    ("SocketCreate sServer;", "VAR socketdev sServer;", "SocketCreate: sockets: TP has no network messaging"),
    ("IF SocketGetStatus(sServer)=SOCKET_CONNECTED nOk:=1;", "VAR socketdev sServer;\nVAR num nOk;",
     "SocketGetStatus: sockets"),
    ("sState:=SocketGetStatus(sServer);", "VAR socketdev sServer;\nVAR socketstatus sState;", "SocketGetStatus: sockets"),
    ('TPReadFK nAnswer,"Go on?","Yes","No",stEmpty,stEmpty,stEmpty;', "VAR num nAnswer;", "TPReadFK: operator dialog"),
    ("TPShow TP_LATEST;", "", "TPShow: a screen or an application of the ABB pendant"),
    ("BookErrNo ERR_GRIP;", "VAR errnum ERR_GRIP:=-1;", "BookErrNo: the ABB event log"),
    ('ErrWrite\\W,"Gripper","Part lost";', "", "ErrWrite: the ABB event log"),
    ("WZLimSup\\Temp,wzZone,shVolume;", "VAR wztemporary wzZone;\nVAR shapedata shVolume;", "WZLimSup: world zone"),
    ("IF sState=SOCKET_CONNECTED nOk:=1;", "VAR socketstatus sState;\nVAR num nOk;", "sState (socketstatus data): sockets"),
    ("WHILE answer<>4 DO\nStop;\nENDWHILE", "VAR btnres answer:=-1;", "answer (btnres data): operator dialog"),
])  # fmt: skip
def test_rapid_instructions_without_a_tp_equivalent_are_said_so(body, data, start):
    result = run(body, data)
    found = [n for n in result.notes if n.kind == "TODO"]
    assert [n.category for n in found] == [Blocker.NO_TP_EQUIVALENT]
    assert found[0].message.startswith(start)


SOCKETS = """PROC SendLine(string sLine)
  SocketSend sCam\\Str:=sLine;
ENDPROC
FUNC string Ask(string sQuestion)
  VAR string sReply;
  SendLine sQuestion;
  SocketReceive sCam\\Str:=sReply;
  RETURN sReply;
ENDFUNC
PROC LogLine(string sLine)
  VAR iodev fLog;
  Open "HOME:"\\File:="log.txt",fLog\\Append;
  Write fLog,sLine;
  Close fLog;
ENDPROC
FUNC string Label(num nKind)
  TEST nKind
  CASE 1:
    RETURN "BOX";
  ENDTEST
  RETURN "NONE";
ENDFUNC"""


@pytest.mark.parametrize(("body", "message"), [
    ('sAnswer:=Ask("state");', "Ask, through SendLine, calls SocketSend: sockets: TP has no network messaging"),
    ('LogLine "part "+Ask("id");', "LogLine calls Open: files and serial channels: TP reads and writes no file"),
])  # fmt: skip
def test_a_call_to_a_routine_of_the_backup_using_files_or_sockets_is_said_so(body, message):
    result = run(body, "VAR socketdev sCam;\nVAR string sAnswer;", extra_procs=SOCKETS)
    found = [n for n in result.notes if n.kind == "TODO" and n.program == result.programs[0].program.name]
    assert [(n.category, n.message.split(" — ")[0]) for n in found] == [(Blocker.NO_TP_EQUIVALENT, message)]


def test_a_text_a_function_of_the_backup_gives_is_said_so():
    result = run("sName:=Label(nKind);", "VAR string sName;\nVAR num nKind;", extra_procs=SOCKETS)
    found = [n for n in result.notes if n.kind == "TODO"]
    assert [n.category for n in found] == [Blocker.VALUE]
    assert "is given by Label, a function of the backup: a TP program returns no value" in found[0].message


def test_an_element_of_an_array_of_texts_is_said_so():
    result = run('sPath:=sPath+sParts{k}+"/";', 'VAR string sPath;\nVAR string sParts{3};\nVAR num k:=1;')
    found = [n for n in result.notes if n.kind == "TODO"]
    assert [n.category for n in found] == [Blocker.TEXT]
    assert "an element of an array of texts" in found[0].message


def test_a_call_to_a_routine_of_the_backup_writing_a_file_that_converts_stays_a_call():
    result = run('LogLine "cycle";', extra_procs=SOCKETS)
    assert tp_lines(result) == ["CALL LOGLINE('cycle')"]


def test_a_routine_of_the_backup_named_like_a_rapid_instruction_is_not_one():
    result = run("Write 3;", "", extra_procs="PROC Write(num n)\n  nLast:=n;\nENDPROC\nVAR num nLast;")
    assert {n.category for n in result.notes if n.kind == "TODO"} <= {Blocker.CALL_ARGS}


def test_the_size_of_an_array_is_a_constant():
    assert tp_lines(run("FOR i FROM 1 TO Dim(nCount,1) DO\n  nSum:=nSum+i;\nENDFOR", TABLE))[0] == "FOR R[1:i]=1 TO 2"


def test_the_tasks_sharing_a_pers_array_share_its_registers():
    """A PERS is the tasks' own data: an array of them changed by one is read changed by the other."""
    from crossarm.convert.compute import Written
    from crossarm.convert.translate import ControllerScope

    def task(name: str, body: str):
        return parse_module(f"MODULE {name}\nPERS num nPlan{{2,3}};\nVAR num k:=1;\nVAR num n{name};\n"
                            f"PROC main()\n{body}\nENDPROC\nENDMODULE\n")  # fmt: skip

    left, right = task("L", "nPlan{k,2}:=4;"), task("R", "nR:=nPlan{k,2};")
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    shared = ControllerScope.from_config(config)
    shared.written = Written.of([left, right])
    first = convert([left], config, routines=["main"], shared=shared)
    second = convert([right], config, routines=["main"], shared=shared)
    assert [(a.name, a.base) for a in first.number_arrays] == [(a.name, a.base) for a in second.number_arrays]
    assert first.number_arrays[0].base == 195


def test_an_array_no_run_of_registers_holds_is_not_counted_as_converted():
    result = run("nBig{k}:=1;\nnSum:=1;", TABLE + "VAR num nBig{300};")
    assert any("no run of free registers left for the array nBig" in m for m in todos(result))
    assert result.coverage.converted == 1  # nSum:=1 only


@pytest.mark.parametrize(("body", "line"), [
    ("bOk:=nCount>2;", "F[1]=(R[1]>2)"),
    ("bOk:=nCount>2 AND NOT bBusy;", "F[2]=(R[1]>2 AND F[1]=OFF)"),
    ("bOk:=bBusy;", "F[2]=(F[1])"),
    ("bOk:=NOT bOk;", "F[1]=(F[1]=OFF)"),
    ("bOk:=nCount<-1 OR nCount=3;", "F[1]=(R[1]<-1 OR R[1]=3)"),
])  # fmt: skip
def test_a_bool_set_to_a_condition_is_a_flag_set_to_it(body, line):
    """ROBOGUIDE: F[n]=(R[1]<5 AND R[2]>8), F[n]=(F[m]=OFF), F[n]=(F[m]) load and give the condition's value."""
    result = run(body, "VAR num nCount;\nVAR bool bOk;\nVAR bool bBusy;")
    assert todos(result) == []
    assert tp_lines(result) == [line]


def test_moveldo_to_a_fine_point_is_the_move_then_the_output():
    """ROBOGUIDE: the line after a FINE move sets the output with the TCP on the point, as MoveLDO does."""
    result = run("MoveLDO pHome,v500,fine,tGrip,doGrip,1;\nMoveJDO pHome,v500,fine,tGrip,doGrip,0;", HOME + TOOL)
    assert tp_lines(result)[-4:] == ["L P[1] 500mm/sec FINE", "DO[1]=ON", "J P[1] 11% FINE", "DO[1]=OFF"]
    assert todos(result) == []


def test_moveldo_through_a_zone_stays_todo():
    result = run("MoveLDO pHome,v500,z10,tGrip,doGrip,1;", HOME + TOOL)
    assert "in the middle of the corner path" in todos(result)[0]


def test_testdi_is_the_input_at_one():
    assert tp_lines(run("IF TestDI(diReady) nCount:=1;\nWHILE NOT TestDI(diReady) DO\n  nCount:=2;\nENDWHILE",
                        "VAR num nCount;"))[:2] == ["IF (DI[1]=ON) THEN", "R[1:nCount]=1"]  # fmt: skip


def test_waitrob_after_a_fine_move_has_nothing_to_wait_for():
    result = run("MoveL pHome,v500,fine,tGrip;\nWaitRob\\InPos;\nMoveL pHome,v500,z10,tGrip;\nWaitRob\\InPos;", HOME + TOOL)
    assert tp_lines(result)[3] == "!WaitRob InPos: FINE before"
    assert [n.message.split(":")[0] for n in result.notes if n.kind == "TODO"] == ["WaitRob \\InPos"]
