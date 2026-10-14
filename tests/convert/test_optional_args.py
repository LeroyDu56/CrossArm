# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Optional num, bool and string parameters (`\\num Speed`), tooldata passed by reference, as TP arguments.

An optional value is passed as two arguments: 1 / 0 whether the call gives it, then its value (0, or '' for a text,
when it does not); Present() reads the first. Measured on ROBOGUIDE: tools/make_optional_arg_probe.py.
"""

from datetime import datetime

from helpers import parse_module

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.arguments import signature

STATION = """PROC Station(num nId\\num Speed\\bool Fast\\string Label\\INOUT num Count)
  IF Present(Speed) nSpeed:=Speed;
  IF Present(Fast) AND Fast=TRUE nFast:=nFast+1;
  IF Present(Count) Count:=Count+nId;
ENDPROC"""
DATA = "VAR num nSpeed;VAR num nFast;VAR num nTotal:=4;"


def convert_all(body: str, procs: str = STATION, data: str = DATA):
    source = f"MODULE M\n{data}\nPROC main()\n{body}\nENDPROC\n{procs}\nENDMODULE\n"
    return convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})


def lines(result, name: str) -> list[str]:
    found = next(p for p in result.programs if p.program.name == name).program
    return [getattr(line, "text", "") for line in found.lines[1:]]


def todos(result) -> list[str]:
    return [n.message for n in result.notes if n.kind == "TODO"]


def test_an_optional_value_is_passed_as_given_or_not_then_its_value():
    result = convert_all('Station 3\\Speed:=200\\Fast:=TRUE;\nStation 4;\nStation 5\\Label:="AB";')
    assert not todos(result)
    calls = [t for t in lines(result, "MAIN") if t.startswith("CALL")]
    assert calls == ["CALL STATION(3,1,200,1,1,0,'',0,0)", "CALL STATION(4,0,0,0,0,0,'',0,0)",
                     "CALL STATION(5,0,0,0,0,1,'AB',0,0)"]  # fmt: skip


def test_present_reads_whether_the_value_is_given():
    station = lines(convert_all("Station 3;"), "STATION")
    assert "IF (AR[2]=1) THEN" in station
    assert "IF (AR[4]=1 AND AR[5]=1) THEN" in station


def test_an_optional_inout_num_comes_back_only_when_given():
    main = lines(convert_all("Station 3\\Count:=nTotal;\nStation 4;"), "MAIN")
    calls = [i for i, t in enumerate(main) if t.startswith("CALL")]
    assert main[calls[0]].startswith("CALL STATION(3,0,0,0,0,0,'',1,R[") and main[calls[0]].endswith(":nTotal])")
    assert main[calls[0] + 1].startswith("R[") and "nTotal" in main[calls[0] + 1].split("=")[0]
    assert main[calls[1]] == "CALL STATION(4,0,0,0,0,0,'',0,0)"
    assert len(main) == calls[1] + 1  # nothing read back after a call not giving it


def test_an_optional_value_is_passed_on():
    relay = "PROC Relay(\\num Speed)\n  Station 9\\Speed?Speed;\nENDPROC\n" + STATION
    result = convert_all("Relay\\Speed:=50;\nRelay;", relay)
    assert not todos(result)
    assert lines(result, "RELAY")[-1] == "CALL STATION(9,AR[1],AR[2],0,0,0,'',0,0)"
    assert [t for t in lines(result, "MAIN") if t.startswith("CALL")] == ["CALL RELAY(1,50)", "CALL RELAY(0,0)"]


def test_the_flags_count_in_the_ten_arguments():
    params = "num a\\num b\\num c\\num d\\num e"
    assert len(signature(parse_module(f"MODULE M\nPROC p({params})\nENDPROC\nENDMODULE").routines[0]).arguments) == 9
    reason = signature(parse_module(f"MODULE M\nPROC p({params}\\num f)\nENDPROC\nENDMODULE").routines[0])
    assert reason == "11 parameters: a TP CALL takes at most 10 arguments"


def test_a_tool_passed_by_reference_and_not_changed_is_passed_by_its_number():
    procs = "PROC Reach(INOUT tooldata tUse)\n  MoveJ pTop,v500,fine,tUse;\nENDPROC"
    data = ("PERS tooldata tHold:=[TRUE,[[0,0,100],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];"
            "CONST robtarget pTop:=[[900,0,800],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];")  # fmt: skip
    result = convert_all("Reach tHold;", procs, data)
    assert not todos(result)
    assert "UTOOL_NUM=AR[1]" in lines(result, "REACH")
    assert any(t.startswith("CALL REACH(") for t in lines(result, "MAIN"))


def test_a_tool_the_routine_changes_by_reference_says_where():
    data = "PERS tooldata tHold:=[TRUE,[[0,0,100],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];"
    procs = "PROC Tilt(INOUT tooldata tUse)\n  tUse.tframe.rot:=[1,0,0,0];\nENDPROC"
    result = convert_all("Tilt tHold;", procs, data)  # its tframe: written to UTOOL[AR[1]] (frame_writes)
    assert not todos(result) and "UTOOL[AR[1]]=PR[" in " ".join(lines(result, "TILT"))
    procs = "PROC Tilt(INOUT tooldata tUse)\n  tUse.tload.mass:=2;\nENDPROC"
    (message,) = todos(convert_all("Tilt tHold;", procs, data))
    assert "it changes its tooldata parameter tUse passed by reference (INOUT), `tUse.tload.mass := 2`" in message


def test_a_bool_passed_by_reference_is_read_when_not_changed():
    procs = "PROC Check(INOUT bool bOk)\n  IF bOk nFast:=1;\nENDPROC"
    result = convert_all("Check TRUE;", procs)
    assert not todos(result)
    assert "CALL CHECK(1)" in lines(result, "MAIN")
    procs = "PROC Check(INOUT bool bOk)\n  Other bOk;\nENDPROC\nPROC Other(INOUT bool b)\n  b:=TRUE;\nENDPROC"
    assert any("passes its bool parameter bOk, passed by reference, on to Other" in m
               for m in todos(convert_all("Check TRUE;", procs)))  # fmt: skip


def test_an_optional_pose_says_why():
    procs = "PROC Place(num n\\pose Shift)\n  nFast:=n;\nENDPROC"
    (message,) = todos(convert_all("Place 2;", procs))
    assert "optional pose parameter Shift: a pose is six numbers, a TP argument one" in message


def test_two_calculations_of_one_condition_keep_their_own_registers():
    procs = "PROC Band(num v,num r,num t)\n  IF v>=r-t AND v<=r+t nFast:=nFast+1;\nENDPROC"
    band = lines(convert_all("Band nTotal,10,3;", procs), "BAND")
    first, second, test = band[0], band[1], band[2]
    low, high = first.split("=")[0], second.split("=")[0]
    assert low != high
    assert test == f"IF (AR[1]>={low} AND AR[1]<={high}) THEN"
