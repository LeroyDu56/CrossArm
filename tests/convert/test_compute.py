# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Frames and positions computed at conversion time (crossarm.convert.compute): only when every input is fixed."""

import json
import math
from datetime import datetime

import pytest
from helpers import parse_module

from crossarm.convert import ConversionConfig, build_mapping, build_report, convert
from crossarm.convert.compute import Computer, Written, def_frame, to_pose
from crossarm.convert.setup import build_setup
from crossarm.convert.translate import Blocker
from crossarm.convert.values import Symbols
from crossarm.fanuc.tp import Motion
from crossarm.geometry import Pose, quat_to_matrix
from crossarm.rapid import nodes as n

BASE = "PERS tooldata tBase:=[TRUE,[[0,0,200],[1,0,0,0]],[2,[0,0,50],[1,0,0,0],0,0,0]];"
BUILT = "PERS tooldata tBuilt:=[TRUE,[[0,0,100],[1,0,0,0]],[2,[0,0,50],[1,0,0,0],0,0,0]];"
HOME = "CONST robtarget pHome:=[[600,0,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
MAKE = """FUNC tooldata Shifted(tooldata base,num dz)
    VAR tooldata t;
    t:=base;
    t.tframe.trans.z:=base.tframe.trans.z+dz;
    RETURN t;
ENDFUNC"""
MOVE = "MoveL pHome,v100,fine,tBuilt;"


def run(body: str, data: str = BASE + BUILT + HOME, extra: str = MAKE, config: ConversionConfig | None = None):
    source = f"MODULE M\n{data}\nPROC main()\n{body}\nENDPROC\n{extra}\nENDMODULE\n"
    config = config or ConversionConfig(timestamp=datetime(2026, 1, 1))
    return convert([parse_module(source)], config, routines=["main"], sources={"M": source})


def lines(result) -> list[str]:
    return [f"{x.kind} {x.target}" if isinstance(x, Motion) else x.text for x in result.programs[0].program.lines[1:]]


def todos(result) -> list[tuple[str, str]]:
    return [(n.category, n.message) for n in result.notes if n.kind == "TODO"]


# ---------------------------------------------------------------------------
# A frame computed from fixed values
# ---------------------------------------------------------------------------


def test_a_tool_built_from_fixed_values_is_loaded_where_the_rapid_builds_it():
    result = run(f"tBuilt:=Shifted(tBase,30);\n{MOVE}")
    assert todos(result) == []
    assert lines(result) == ["!l.4 tBuilt:=Shifted(tBase,30)", "UTOOL[1]=PR[99]", "UFRAME_NUM=0", "UTOOL_NUM=1",
                             "L P[1]"]  # fmt: skip
    (frame,) = result.computed_frames
    assert (frame.number, frame.key, frame.fixed) == (99, "0.000,0.000,230.000,0.000,0.000,0.000", False)
    assert frame.uses == (("UTOOL", "tBuilt", "MAIN", 4),)


def test_a_function_choosing_with_test_case_is_run():
    extra = MAKE + ("\nFUNC num Length(num size)\nTEST size\nCASE 1:\nRETURN 10;\nCASE 2, 3:\nRETURN 30;\n"
                    "DEFAULT:\nRETURN 0;\nENDTEST\nENDFUNC")  # fmt: skip
    result = run(f"tBuilt:=Shifted(tBase,Length(3));\n{MOVE}", extra=extra)
    assert todos(result) == []
    assert result.computed_frames[0].key == "0.000,0.000,230.000,0.000,0.000,0.000"


def test_identical_values_share_one_register():
    result = run(f"tBuilt:=Shifted(tBase,30);\n{MOVE}\ntBuilt:=Shifted(tBase,10);\n{MOVE}\ntBuilt:=Shifted(tBase,30);\n{MOVE}")
    assert [(f.number, len(f.uses)) for f in result.computed_frames] == [(99, 2), (98, 1)]
    assert [x for x in lines(result) if "=PR[" in x] == ["UTOOL[1]=PR[99]", "UTOOL[1]=PR[98]", "UTOOL[1]=PR[99]"]


def test_setup_frames_stores_the_computed_values_and_the_report_lists_them():
    result = run(f"tBuilt:=Shifted(tBase,30);\n{MOVE}")
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    result.setup = build_setup(result, config, "SETUP_FRAMES")
    setup = [x.text for x in result.setup.program.lines]
    assert "PR[99]=P[2]" in setup  # P[1] is the tool frame itself, as declared
    assert result.setup.program.positions[1].value.z == pytest.approx(230)
    report = build_report(result, config, ["M.mod"])
    assert "### Frames computed at conversion time" in report
    assert "| PR[99] | 0.000, 0.000, 230.000 | 0.000, 0.000, 0.000 | UTOOL tBuilt | `MAIN` l.4 | automatic |" in report
    assert next(c for c in result.capacity if c.resource == "PR").used == 2  # SETUP_FRAMES' scratch one, and PR[99]


def test_the_register_is_pinned_by_the_mapping_file_and_old_files_keep_their_numbers(tmp_path):
    first = run(f"tBuilt:=Shifted(tBase,30);\n{MOVE}")
    mapping = json.loads(build_mapping(first, ConversionConfig()))
    assert mapping["frame_registers"] == {"0.000,0.000,230.000,0.000,0.000,0.000": 99}
    mapping["frame_registers"] = {"0,0,230,0,0,0": 42}  # written by hand, another way
    path = tmp_path / "map.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    pinned = run(f"tBuilt:=Shifted(tBase,30);\n{MOVE}", config=ConversionConfig.from_mapping_file(path))
    assert "UTOOL[1]=PR[42]" in lines(pinned)
    assert pinned.computed_frames[0].fixed
    # A mapping file written before computed frames: every number it pins is still the one it gives.
    del mapping["frame_registers"], mapping["_frame_registers"]
    path.write_text(json.dumps(mapping), encoding="utf-8")
    again = run(f"tBuilt:=Shifted(tBase,30);\n{MOVE}", config=ConversionConfig.from_mapping_file(path))
    assert {k: v for k, v in json.loads(build_mapping(again, ConversionConfig())).items()
            if k not in ("frame_registers", "_frame_registers")} == mapping  # fmt: skip


def test_the_registers_come_after_the_frame_banks():
    tools = "".join(f"PERS tooldata t{i}:=[TRUE,[[0,0,{i}],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];\n" for i in range(11))
    moves = "".join(f"MoveL pHome,v100,fine,t{i};\n" for i in range(11))
    result = run(f"{moves}t10:=Shifted(tBase,5);\nMoveL pHome,v100,fine,t10;", tools + BASE + HOME)
    assert "PR[98]=PR[97]" in lines(result)  # t10 is banked in PR[98]: its new value goes there
    assert result.computed_frames[0].number == 97


def test_no_register_left_leaves_the_load_todo():
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    config.limits["PR"] = 1  # only SETUP_FRAMES' scratch register
    result = run(f"tBuilt:=Shifted(tBase,30);\n{MOVE}", config=config)
    assert [c for c, _ in todos(result)] == [Blocker.CAPACITY]
    assert result.computed_frames[0].number is None
    assert next(c for c in result.capacity if c.resource == "PR").over


def test_a_work_object_copied_from_another_is_uframe_times_its_own_oframe():
    data = (HOME + 'PERS wobjdata wA:=[FALSE,TRUE,"",[[500,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];\n'
            'PERS wobjdata wB:=[FALSE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,40],[1,0,0,0]]];')  # fmt: skip
    result = run("wB.uframe:=wA.uframe;\nMoveL pHome,v100,fine,tool0\\WObj:=wB;", data, "")
    assert result.computed_frames[0].key == "500.000,0.000,40.000,0.000,0.000,0.000"


def test_a_point_put_together_from_fixed_values_is_moved_to():
    data = HOME + "VAR robtarget pTmp;"
    result = run("pTmp:=pHome;\npTmp.trans.z:=pTmp.trans.z-100;\nMoveL pTmp,v100,fine,tool0;\n"
                 "pTmp.trans.z:=pTmp.trans.z-100;\nMoveL pTmp,v100,fine,tool0;", data, "")  # fmt: skip
    assert todos(result) == []
    assert [p.value.z for p in result.programs[0].program.positions] == [800, 700]  # not one P for both


# ---------------------------------------------------------------------------
# Not computed: an input that is not fixed
# ---------------------------------------------------------------------------


def test_an_input_the_programs_change_elsewhere_keeps_the_todo():
    extra = MAKE + "\nPROC calib()\ntBase.tframe.trans.z:=250;\nENDPROC"
    result = run(f"tBuilt:=Shifted(tBase,30);\n{MOVE}", extra=extra)
    ((category, message),) = todos(result)
    assert category == Blocker.RUNTIME_FRAME
    assert "'tBase' is changed by the programs (M.calib l." in message


def test_an_input_changed_through_a_parameter_keeps_the_todo_but_not_one_only_read():
    reads = MAKE + "\nPROC Show(PERS tooldata t)\nTPWrite \"tool\";\nENDPROC"
    result = run(f"Show tBase;\ntBuilt:=Shifted(tBase,30);\n{MOVE}", extra=reads)
    assert todos(result) == []  # Show is given the tool's number, and only reads it
    assert result.computed_frames
    writes = MAKE + "\nPROC Calib(INOUT tooldata t)\nt.tframe.trans.z:=1;\nENDPROC\nPROC other()\nCalib tBase;\nENDPROC"
    assert "is changed by the programs (M.other l." in todos(run(f"tBuilt:=Shifted(tBase,30);\n{MOVE}", extra=writes))[0][1]


def test_setdataval_with_a_computed_name_blocks_the_data_of_its_type_only():
    extra = MAKE + '\nPROC load(string name)\nVAR tooldata t;\nSetDataVal name,t;\nENDPROC'
    ((_, message),) = todos(run(f"tBuilt:=Shifted(tBase,30);\n{MOVE}", extra=extra))
    assert "SetDataVal in M.load l." in message and "can change any tooldata" in message
    data = HOME + 'PERS wobjdata wA:=[FALSE,TRUE,"",[[500,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];'
    assert todos(run("wA.oframe.trans.z:=wA.uframe.trans.z;", data, extra)) == []  # a wobjdata: not its type
    # The value given by the routine's caller: its type is the parameter's.
    by_parameter = MAKE + '\nPROC set(string name,num value)\nSetDataVal "n"+name,value;\nENDPROC'
    assert todos(run(f"tBuilt:=Shifted(tBase,30);\n{MOVE}", extra=by_parameter)) == []


def test_a_process_move_reads_its_frames_and_a_search_changes_only_its_point():
    data = (HOME + BASE + 'PERS wobjdata wA:=[FALSE,TRUE,"",[[500,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];\n'
            'PERS wobjdata wB:=[FALSE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,40],[1,0,0,0]]];\n'
            "VAR triggdata trOn;\nVAR robtarget pFound;")  # fmt: skip
    extra = ("PROC work()\nTriggIO trOn,5\\DOp:=doOn,1;\nTriggL pHome,v100,trOn,z1,tBase\\WObj:=wA;\n"
             "SearchL\\Stop,diTouch,pFound,pHome,v20,tBase\\WObj:=wA;\nENDPROC")  # fmt: skip
    result = run("wB.uframe:=wA.uframe;\nMoveL pHome,v100,fine,tool0\\WObj:=wB;", data, extra)
    assert todos(result) == []
    assert result.computed_frames


def test_a_value_set_in_one_branch_only_is_not_known_after_the_if():
    body = f"IF DInput(diA)=1 THEN\ntBuilt:=Shifted(tBase,30);\nENDIF\ntBuilt.tframe.trans.x:=5;\n{MOVE}"
    ((category, message),) = todos(run(body))
    assert category == Blocker.RUNTIME_FRAME
    assert "'tBuilt' is set differently in the branches of the IF at l.4" in message


def test_a_value_set_the_same_on_both_branches_is_known_after_the_if():
    body = (f"IF DInput(diA)=1 THEN\ntBuilt:=Shifted(tBase,30);\nELSE\ntBuilt:=Shifted(tBase,30);\nENDIF\n"
            f"tBuilt.tframe.trans.x:=5;\n{MOVE}")  # fmt: skip
    result = run(body)
    assert todos(result) == []
    assert result.computed_frames[-1].key == "5.000,0.000,230.000,0.000,0.000,0.000"


def test_a_value_changed_in_a_loop_is_not_known_in_it_nor_after_it():
    body = f"FOR i FROM 1 TO 3 DO\ntBuilt.tframe.trans.z:=tBuilt.tframe.trans.z+10;\n{MOVE}\nENDFOR"
    ((category, message),) = todos(run(body))
    assert category == Blocker.RUNTIME_FRAME
    assert "changes in the loop at l.4" in message


def test_a_frame_measured_on_the_robot_is_a_calibration_and_so_is_what_derives_from_it():
    data = BASE + BUILT + HOME + "VAR robtarget pMeas;"
    body = f"pMeas:=CRobT(\\Tool:=tBase);\ntBuilt.tframe.trans:=pMeas.trans;\n{MOVE}"
    result = run(body, data)  # the point is read (PR[k]=LPOS), the tool's x, y, z written over it, then loaded
    assert not todos(result)
    lines = [line.text for p in result.programs for line in p.program.lines if hasattr(line, "text")]
    assert sum(1 for line in lines if line.endswith("=LPOS")) == 1
    assert any("=UTOOL[" in line for line in lines) and any(line.startswith("UTOOL[") for line in lines)
    measured = [n for n in result.notes if n.kind == "WARNING" and "computed at run time and loaded" in n.message]
    assert [n.category for n in measured] == [Blocker.RUNTIME_FRAME]
    extra = MAKE + "\nFUNC pose Measure()\nVAR robtarget p;\np:=CRobT();\nRETURN [p.trans,p.rot];\nENDFUNC"
    ((category, message),) = todos(run(f"tBuilt.tframe:=Measure();\n{MOVE}", extra=extra))
    assert category == Blocker.CALIBRATION and "Measure() (CRobT()) reads the robot's position" in message


def test_a_function_that_does_more_than_compute_is_not_run():
    extra = "FUNC tooldata Noisy(tooldata base)\nTPWrite \"hello\";\nRETURN base;\nENDFUNC"
    ((_, message),) = todos(run(f"tBuilt:=Noisy(tBase);\n{MOVE}", extra=extra))
    assert "Noisy() does more than compute (TPWrite)" in message


def test_a_changed_payload_is_a_warning_on_the_computed_tool_and_a_todo_alone():
    extra = "FUNC tooldata Heavy(tooldata base)\nVAR tooldata t;\nt:=base;\nt.tload.mass:=9;\nRETURN t;\nENDFUNC"
    result = run(f"tBuilt:=Heavy(tBase);\n{MOVE}", extra=extra)
    assert [n.category for n in result.notes if n.kind == "WARNING" and "load changes" in n.message] == [Blocker.PAYLOAD]
    assert [c for c, _ in todos(run("tBuilt.tload.mass:=9;"))] == [Blocker.PAYLOAD]


# ---------------------------------------------------------------------------
# The functions, against the RAPID manual
# ---------------------------------------------------------------------------


def computer(source: str) -> Computer:
    module = parse_module(f"MODULE M\n{source}\nENDMODULE")
    return Computer([module], Symbols.from_modules([module]), Written.of([module]))


def value(c: Computer, text: str):
    module = parse_module(f"MODULE X\nPROC p()\nx:={text};\nENDPROC\nENDMODULE")
    stmt = module.routines[0].body[0]
    assert isinstance(stmt, n.Assign)
    return c.value(stmt.value).value


def test_orientzyx_and_eulerzyx_are_each_other_s_inverse():
    c = computer("")
    for axis, angle in (("Z", 25.0), ("Y", -12.0), ("X", 170.0)):
        got = value(c, f"EulerZYX(\\{axis},OrientZYX(25,-12,170))")
        assert got == pytest.approx(angle, abs=1e-9)


def test_posemult_poseinv_posevect():
    c = computer("CONST pose p:=[[100,200,300],[0.7071068,0,0,0.7071068]];")
    identity = to_pose(value(c, "PoseMult(p,PoseInv(p))"))
    assert identity.pos == pytest.approx((0, 0, 0), abs=1e-6)
    assert abs(identity.rot[0]) == pytest.approx(1, abs=1e-6)
    assert value(c, "PoseVect(p,[10,0,0])") == pytest.approx([100, 210, 300], abs=1e-5)  # 90 deg about z


def test_defframe_origins():
    p1, p2, p3 = (0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (30.0, 50.0, 0.0)
    assert def_frame(p1, p2, p3, 1).pos == (0, 0, 0)
    assert def_frame(p1, p2, p3, 2).pos == (100, 0, 0)
    assert def_frame(p1, p2, p3, 3).pos == pytest.approx((30, 0, 0))
    m = quat_to_matrix(def_frame(p1, p2, p3, 1).rot)
    assert [m[i][i] for i in range(3)] == pytest.approx([1, 1, 1])  # x to p2, p3 on +y: the base frame
    tilted = def_frame(p1, (0.0, 100.0, 0.0), (-50.0, 30.0, 0.0), 1)
    assert Pose((0.0, 0.0, 0.0), tilted.rot).compose(Pose((1.0, 0.0, 0.0), (1, 0, 0, 0))).pos == pytest.approx(
        (0, 1, 0), abs=1e-9)  # fmt: skip


def test_a_record_of_the_backup_is_read_by_its_components():
    c = computer("RECORD shift\n num rz;\n pos offset;\nENDRECORD\nPERS shift s:=[30,[1,2,3]];")
    assert value(c, "s.offset.y") == 2
    assert value(c, "s.rz*2") == 60


def test_an_orientation_that_is_not_a_unit_quaternion_is_refused():
    with pytest.raises(Exception, match="not a unit quaternion"):
        to_pose([[0, 0, 0], [0, 0, 0, 0]])
    assert math.isclose(sum(q * q for q in to_pose([[0, 0, 0], [1.000001, 0, 0, 0]]).rot), 1)
