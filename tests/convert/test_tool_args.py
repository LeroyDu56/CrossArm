# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A routine given a tool by reference that sets its tframe (a calibration), a bool passed by reference that the
routine sets, an optional point (crossarm.convert.arguments, calls, frame_writes). Measured on ROBOGUIDE:
tools/make_tool_arg_probe.py (tests/fixtures/probes/toolarg)."""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.blockers import Blocker
from crossarm.rapid import parse_text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import make_tool_arg_probe

STAMP = datetime(2026, 1, 1)
PROBE = FIXTURES / "probes" / "toolarg"
HEAD = """MODULE TA
  PERS tooldata tA:=[TRUE,[[0,0,100],[1,0,0,0]],[2,[0,0,50],[1,0,0,0],0,0,0]];
  PERS tooldata tB:=[TRUE,[[0,30,120],[1,0,0,0]],[2,[0,0,50],[1,0,0,0],0,0,0]];
  PERS tooldata tFix:=[FALSE,[[900,0,600],[1,0,0,0]],[2,[0,0,50],[1,0,0,0],0,0,0]];
  CONST robtarget pA:=[[1000,0,800],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  CONST robtarget pB:=[[1000,50,800],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  VAR num nLen:=150;
  VAR num nMax:=0;
  VAR num nMean:=0;
  VAR bool bOk:=FALSE;
"""


def run(text: str, karel: bool = False):
    parsed = parse_text(text, path="TA.mod")
    assert parsed.module is not None, parsed.errors
    return convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=karel), sources={"TA": text})


def lines(result, name: str) -> list[str]:
    program = next(info.program for info in result.programs if info.program.name == name)
    return [getattr(line, "text", "") for line in program.lines]


def todos(result) -> list[tuple[str, str]]:
    return [(note.message, note.category) for note in result.notes if note.kind == "TODO"]


def test_a_routine_setting_the_tframe_of_a_tool_it_is_given_writes_its_utool():
    result = run(HEAD + """  PROC Main()
    SetLen tA,nLen;
    MoveL pA,v100,fine,tA;
  ENDPROC
  PROC SetLen(INOUT tooldata t,num n)
    t.tframe.trans.z:=n+2;
    t.tframe.rot:=[1,0,0,0];
  ENDPROC
ENDMODULE""")
    assert todos(result) == []
    assert "CALL SETLEN(1,R[1])" in lines(result, "MAIN")
    body = lines(result, "SETLEN")
    reads = [t for t in body if t.endswith("=UTOOL[AR[1]]")]
    assert len(reads) == 2 and sum(t.startswith("UTOOL[AR[1]]=PR[") for t in body) == 2
    assert any(t.endswith(",3]=AR[2]+2") for t in body)
    assert [t.split("=")[1] for t in body if t.startswith(reads[1].split("=")[0][:-1] + ",") and t[-1] == "0"] == ["0"] * 3


def test_the_tool_stays_known_but_for_its_tframe():
    # the call sets tA's tframe only: its robhold is known, so KAREL reads the tframe the robot holds after it
    result = run(HEAD + """  VAR pose peTip;
  PROC Main()
    SetLen tA,nLen;
    SetLen tB,nLen;
    peTip:=PoseMult([pA.trans,pA.rot],tA.tframe);
    MoveL pA,v100,fine,tA;
  ENDPROC
  PROC SetLen(INOUT tooldata t,num n)
    t.tframe.trans.z:=n;
  ENDPROC
ENDMODULE""", karel=True)
    assert todos(result) == []
    main = lines(result, "MAIN")
    assert any(t.endswith("=UTOOL[1]") for t in main) and any("CA_POSEMULT" in t for t in main)


def test_a_tool_changed_other_than_in_its_tframe_stays_todo():
    result = run(HEAD + """  PROC Main()
    SetHold tA;
  ENDPROC
  PROC SetHold(INOUT tooldata t)
    t.robhold:=FALSE;
  ENDPROC
ENDMODULE""")
    assert any("only what the routine writes in its tframe comes back" in m for m, _ in todos(result))


def test_a_stationary_tool_is_not_passed_to_be_written():
    result = run(HEAD + """  PROC Main()
    SetLen tFix,nLen;
  ENDPROC
  PROC SetLen(INOUT tooldata t,num n)
    t.tframe.trans.z:=n;
  ENDPROC
ENDMODULE""")
    assert any("robhold TRUE" in m and c == Blocker.CALL_ARGS for m, c in todos(result))


def test_a_calibration_left_todo_stops_the_tool_from_being_read_back_in_the_routine():
    result = run(HEAD + """  PROC Main()
    Calib tA,pA,pB;
  ENDPROC
  PROC Calib(INOUT tooldata t,robtarget p1,robtarget p2)
    MToolRotCalib p1,p2,t;
    t.tframe.trans.z:=nLen;
  ENDPROC
ENDMODULE""")
    found = todos(result)
    assert any("Four Point" in m and c == Blocker.NO_TP_EQUIVALENT for m, c in found)
    assert any("its UTOOL is not what the RAPID holds" in m for m, _ in found)
    assert not any("CALIB is not converted" in m for m, _ in found)


def test_a_tool_kept_in_a_bank_is_read_back_after_the_call():
    tools = "".join(f"  PERS tooldata tN{i}:=[TRUE,[[0,0,{100 + i}],[1,0,0,0]],[2,[0,0,50],[1,0,0,0],0,0,0]];\n"
                    for i in range(1, 13))  # fmt: skip
    moves = "".join(f"    MoveL pA,v100,fine,tN{i};\n" for i in range(1, 13))
    result = run(HEAD.replace("MODULE TA\n", "MODULE TA\n" + tools) + f"""  PROC Main()
{moves}    SetLen tN12,nLen;
    MoveL pB,v100,fine,tN12;
  ENDPROC
  PROC SetLen(INOUT tooldata t,num n)
    t.tframe.trans.z:=n;
  ENDPROC
ENDMODULE""")
    assert todos(result) == []
    main = lines(result, "MAIN")
    call = next(i for i, t in enumerate(main) if t.startswith("CALL SETLEN("))
    number = main[call].split("(")[1].split(",")[0]
    assert main[call - 1].startswith(f"UTOOL[{number}]=PR[")
    assert main[call + 1] == f"PR[{main[call - 1].split('PR[')[1][:-1]}]=UTOOL[{number}]"


def test_a_bool_passed_by_reference_comes_back_into_the_callers_flag():
    result = run(HEAD + """  PROC Main()
    Check nLen,bOk;
    IF bOk nMax:=1;
  ENDPROC
  PROC Check(num nLim,INOUT bool b)
    b:=nLim<500;
  ENDPROC
ENDMODULE""")
    assert todos(result) == []
    main = lines(result, "MAIN")
    call = next(i for i, t in enumerate(main) if t.startswith("CALL CHECK("))
    assert main[call - 5].startswith("IF (F[1") and main[call - 5].endswith("=ON) THEN")
    assert main[call + 1].startswith("F[1") and main[call + 1].endswith("=1)")
    assert lines(result, "CHECK")[-5:-3] == ["IF (AR[1]<500) THEN", main[call - 4]]


def test_an_optional_point_is_passed_when_given():
    result = run(HEAD + """  PROC Main()
    Visit tA\\Pt:=pB;
    Visit tA;
  ENDPROC
  PROC Visit(PERS tooldata t\\robtarget Pt)
    IF Present(Pt) MoveL Pt,v100,fine,t;
  ENDPROC
ENDMODULE""")
    assert todos(result) == []
    main = lines(result, "MAIN")
    calls = [t for t in main if t.startswith("CALL VISIT(")]
    assert calls == ["CALL VISIT(1,1)", "CALL VISIT(1,0)"]
    assert any(t.startswith("PR[") and "=P[" in t for t in main)
    assert "IF (AR[2]=1) THEN" in lines(result, "VISIT")


def test_the_probe_files_are_those_the_generator_writes():
    with tempfile.TemporaryDirectory() as temp:
        make_tool_arg_probe.conversion(Path(temp))
        for name in (*make_tool_arg_probe.PROGRAMS, "SETUP_FRAMES"):
            assert (PROBE / f"{name}.LS").read_bytes() == (Path(temp) / f"{name}.LS").read_bytes(), name
    assert (PROBE / "ToolArgProbe.mod").read_bytes() == make_tool_arg_probe.MODULE.encode("ascii")


def test_the_moves_go_where_rapid_puts_them():
    if not make_tool_arg_probe.RESULT.exists():
        pytest.skip("tool argument probe not run on ROBOGUIDE yet")
    assert make_tool_arg_probe.verdict(make_tool_arg_probe.stored()) == ""
