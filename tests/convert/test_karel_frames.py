# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""--karel, poses and frames worked out at run time (crossarm.convert.karel_poses): PoseInv, RelTool of a point whose
orientation or rotation is only known at run time, DefFrame of points read on the robot, nested PoseMult, and a work
object's uframe or a tool's tframe set to such a value, loaded into UFRAME / UTOOL. Measured on ROBOGUIDE:
tools/make_karel_pose_probe.py."""

import json
import sys
from datetime import datetime
from pathlib import Path

from crossarm.convert import ConversionConfig, build_mapping, build_report, convert
from crossarm.convert.blockers import Blocker
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import parse_text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_karel_pose_probe import MODULE as PROBE_MODULE

STAMP = datetime(2026, 1, 1)
DATA = """MODULE KF
  PERS tooldata tGun:=[TRUE,[[0,0,150],[1,0,0,0]],[5,[0,0,50],[1,0,0,0],0,0,0]];
  PERS wobjdata wFix:=[FALSE,TRUE,"",[[1000,0,800],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  PERS wobjdata wOther:=[FALSE,TRUE,"",[[500,0,800],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  CONST robtarget pT1:=[[900,-100,800],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  CONST robtarget pT2:=[[1100,50,820],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  CONST robtarget pT3:=[[950,150,780],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  CONST robtarget pIn:=[[100,50,-50],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  VAR robtarget pM1;
  VAR robtarget pM2;
  VAR robtarget pM3;
  VAR robtarget pTurn;
  VAR num nAngle:=30;
  PROC Main()
    MoveJ pT1,v500,fine,tool0;
    pM1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);
    MoveL pT2,v500,fine,tool0;
    pM2:=CRobT(\\Tool:=tool0\\WObj:=wobj0);
    MoveL pT3,v500,fine,tool0;
    pM3:=CRobT(\\Tool:=tool0\\WObj:=wobj0);
    BODY
    MoveL pIn,v500,fine,tGun\\WObj:=wFix;
    MoveL pIn,v500,fine,tGun\\WObj:=wOther;
  ENDPROC
ENDMODULE
"""


def conversion(body: str, karel: bool = True, data: str = DATA, **config):
    text = data.replace("BODY", body)
    parsed = parse_text(text, path="KF.mod")
    assert parsed.module is not None, parsed.diagnostics
    return convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=karel, **config), sources={"KF": text})


def lines(result) -> list[str]:
    text = write_ls(result.programs[0].program).split("/MN")[1].split("/POS")[0]
    return [line.split(":", 1)[1].strip().rstrip(";").strip() for line in text.splitlines() if ":" in line]


def kept(result) -> dict[str, int]:
    return {a.rapid_name.upper(): a.number for a in result.point_registers}


def todo(result) -> list:
    return [note for note in result.notes if note.kind == "TODO"]


def test_deframe_of_points_read_on_the_robot_is_loaded_into_the_user_frame():
    result = conversion("wFix.uframe:=DefFrame(pM1,pM2,pM3\\Origin:=3);")
    assert not todo(result)
    found, body = kept(result), lines(result)
    frame = found["CROSSARM.FRAME"]
    assert f"CALL CA_DEFFRAME({found['PM1']},{found['PM2']},{found['PM3']},{frame},3)" in body
    load = body.index(f"UFRAME[1]=PR[{frame}]")
    assert body[load - 2].startswith("!l.") and body[load + 1] == "UFRAME_NUM=1"  # selected again before the move
    assert result.karel_programs == ["CA_DEFFRAME"]
    warned = [n for n in result.notes if n.kind == "WARNING" and "computed at run time by KAREL" in n.message]
    assert len(warned) == 1 and warned[0].category == Blocker.RUNTIME_FRAME and "configuration" in warned[0].message


def test_without_karel_the_frame_stays_todo_and_the_count_says_karel_converts_it():
    body = "wFix.uframe:=DefFrame(pM1,pM2,pM3);"
    off = conversion(body, karel=False)
    assert [n.category for n in todo(off)] == [Blocker.CALIBRATION] and off.karel_todo == 1
    assert not any("CA_" in line for line in lines(off))
    report = build_report(off, ConversionConfig(timestamp=STAMP), ["KF.mod"])
    assert "Convert again with `--karel`" in report and "DefFrame" in report


def test_a_tool_corrected_by_posemult_and_poseinv_of_a_point_read():
    result = conversion("tGun.tframe:=PoseMult(tGun.tframe,PoseInv([[pM1.trans.x-900,0,0],[1,0,0,0]]));")
    assert not todo(result), [n.message for n in todo(result)]
    found, body = kept(result), lines(result)
    one, two, frame = found["CROSSARM.POSE1"], found["CROSSARM.POSE2"], found["CROSSARM.FRAME"]
    assert f"PR[{one}]=UTOOL[2]" in body  # tGun.tframe, which this statement changes: read where the robot keeps it
    assert f"PR[{two},1]=PR[{found['PM1']},1]-900" in body
    assert body.index(f"CALL CA_POSEINV({two},{two})") < body.index(f"CALL CA_POSEMULT({one},{two},{frame})")
    assert body[body.index(f"UTOOL[2]=PR[{frame}]") + 2] == "UTOOL_NUM=2"
    assert result.karel_programs == ["CA_POSEMULT", "CA_POSEINV"]


def test_an_oframe_other_than_the_identity_is_multiplied_in():
    data = DATA.replace('[[500,0,800],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];', '[[500,0,800],[1,0,0,0]],[[0,0,20],[1,0,0,0]]];')
    result = conversion("wOther.uframe:=DefFrame(pM1,pM2,pM3);", data=data)
    found, body = kept(result), lines(result)
    frame, one = found["CROSSARM.FRAME"], found["CROSSARM.POSE1"]
    assert f"PR[{one},3]=20" in body and f"CALL CA_POSEMULT({frame},{one},{frame})" in body
    assert f"UFRAME[2]=PR[{frame}]" in body


def test_a_frame_past_the_controller_limit_is_loaded_into_its_bank():
    result = conversion("wOther.uframe:=DefFrame(pM1,pM2,pM3);", limits={"UFRAME": 1, "UTOOL": 10, "PR": 100})
    body = lines(result)
    frame = kept(result)["CROSSARM.FRAME"]
    banked = [line for line in body if line.endswith(f"=PR[{frame}]")]
    assert len(banked) == 1 and banked[0].startswith("PR[") and not banked[0].startswith("UFRAME")
    bank = banked[0].split("]")[0] + "]"
    assert f"UFRAME[1]={bank}" in body[body.index(banked[0]):]  # loaded into the slot before the move


def test_reltool_of_a_point_read_on_the_robot():
    result = conversion("pTurn:=RelTool(pM2,0,0,-30\\Rz:=-90);\n    MoveL pTurn,v500,fine,tool0;")
    found, body = kept(result), lines(result)
    assert f"CALL CA_RELTOOL({found['PM2']},{found['PTURN']},0,0,(-30),0,0,(-90))" in body
    assert f"PR[{found['PTURN']}]" in " ".join(body)  # the move to it
    assert not todo(result) and result.karel_programs == ["CA_RELTOOL"]


def test_reltool_turned_by_an_angle_only_known_at_run_time():
    body = "nAngle:=pM1.trans.x/30;\n    pTurn:=RelTool(pT2,0,0,-nAngle\\Rx:=nAngle*2);\n    MoveL pTurn,v500,fine,tool0;"
    result = conversion(body)
    found, out = kept(result), lines(result)
    turn, scratch = found["PTURN"], found["CROSSARM.POSE1"]
    call = next(line for line in out if line.startswith("CALL CA_RELTOOL"))
    assert call.startswith(f"CALL CA_RELTOOL({scratch},{turn},0,0,R[") and call.endswith(",0,0)")
    assert out[out.index(call) - 3].startswith(f"PR[{scratch}]=P[")  # the point known now, its configuration too
    assert out[out.index(call) - 2] == "R[2:Calc3]=R[1:nAngle]*(-1)" and out[out.index(call) - 1] == "R[3:Calc4]=R[1:nAngle]*2"
    assert not todo(result)


def test_what_karel_is_not_given_stays_todo():
    cases = {
        "wFix.uframe:=DefFrame(pM1,pM2,pM3\\Origin:=nAngle);": "Origin only known at run time",
        "wFix.uframe:=DefFrame(pM1,pM2,pM3\\Origin:=4);": "RAPID takes 1, 2 or 3",
        "wFix.uframe:=PoseMult(wFix.uframe,[[0,0,0],[pM1.rot.q1,0,0,0]]);": "KAREL is given poses",
    }
    for body, why in cases.items():
        result = conversion(body)
        assert any(why in note.message for note in todo(result)), (body, [n.message for n in todo(result)])


def test_a_tool_turned_for_the_other_pin_hole_stays_todo():
    result = conversion("tGun.tframe:=PoseInv(PoseInv(tGun.tframe));\n    tGun.tframe:=DefFrame(pM1,pM2,pM3);",
                        tool_pin="+x")
    assert any("tool_pin -x" in note.message for note in todo(result))


def test_a_frame_no_move_selects_stays_todo():
    data = DATA.replace("    MoveL pIn,v500,fine,tGun\\WObj:=wOther;\n", "")
    result = conversion("wOther.uframe:=DefFrame(pM1,pM2,pM3);", data=data)
    assert [n.category for n in todo(result)] == [Blocker.CALIBRATION]


def test_the_numbers_of_a_mapping_written_without_karel_are_kept_with_it(tmp_path):
    body = "wFix.uframe:=DefFrame(pM1,pM2,pM3\\Origin:=2);\n    pTurn:=RelTool(pM2,0,0,10\\Rz:=45);"
    off = conversion(body, karel=False)
    mapping = tmp_path / "crossarm_mapping.json"
    mapping.write_text(build_mapping(off, ConversionConfig(timestamp=STAMP)), encoding="utf-8")
    first = json.loads(mapping.read_text(encoding="utf-8"))
    text = DATA.replace("BODY", body)
    config = ConversionConfig.from_mapping_file(mapping, timestamp=STAMP, karel=True)
    on = convert([parse_text(text, path="KF.mod").module], config, sources={"KF": text})
    second = json.loads(build_mapping(on, config))
    assert not todo(on)
    for table, values in first.items():
        if isinstance(values, dict) and not table.startswith("_"):
            for key, number in values.items():
                assert second[table].get(key) == number, (table, key)


def test_the_probe_module_converts_whole():
    parsed = parse_text(PROBE_MODULE, path="KarelPoseProbe.mod")
    result = convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=True), sources={"KarelPoseProbe": PROBE_MODULE})
    assert not todo(result) and result.karel_programs == ["CA_POSEMULT", "CA_POSEINV", "CA_RELTOOL", "CA_DEFFRAME"]
    off = convert([parsed.module], ConversionConfig(timestamp=STAMP), sources={"KarelPoseProbe": PROBE_MODULE})
    assert off.karel_todo == len(todo(off)) == 5
