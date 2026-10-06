# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Routines with parameters: `Set_Station 3\\Wait;` -> `CALL SET_STATION(3,1)`, read as AR[n].

They are a large share of what is left after the moves in a typical backup: calls to routines
taking a number and a few switches. Only what TP can hold is converted — num, bool,
optional switches, passed by value — and every argument is passed on every call.
"""

from datetime import datetime

import pytest
from helpers import parse_module
from test_translate import run, todos, tp_lines

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.arguments import signature
from crossarm.convert.translate import Blocker
from crossarm.fanuc.tp import Instruction

SUB = """PROC Sub(num a,num b,bool on\\switch Check|switch Skip\\switch Init)
  nA:=a;
  nSum:=nSum+b;
  IF on THEN
    nOn:=nOn+1;
  ENDIF
  IF Present(Check) THEN
    nChecks:=nChecks+1;
  ENDIF
  FOR i FROM 1 TO a DO
    nLoops:=nLoops+1;
  ENDFOR
  WaitTime b;
ENDPROC"""
DATA = "VAR num nA;VAR num nSum;VAR num nOn;VAR num nChecks;VAR num nLoops;CONST num cFive:=5;VAR num nIn:=2;"


def program(body: str, data: str, procs: str, name: str) -> list[str]:
    """The lines of one program, every routine of the module converted (not only main)."""
    source = f"MODULE M\n{data}\nPROC main()\n{body}\nENDPROC\n{procs}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert not [n for n in result.notes if n.kind == "TODO"], result.notes
    found = next(p for p in result.programs if p.program.name == name).program
    return [getattr(line, "text", "") for line in found.lines[1:]]


def layout(params: str):
    return signature(parse_module(f"MODULE M\nPROC p({params})\nENDPROC\nENDMODULE").routines[0])


def test_parameters_map_to_ar_in_order_switches_last():
    sig = layout("num a,\\switch Check|switch Skip,bool on\\switch Init")
    assert [(s.name, s.kind) for s in sig.slots] == [
        ("a", "num"), ("on", "bool"), ("Check", "switch"), ("Skip", "switch"), ("Init", "switch"),
    ]  # fmt: skip
    assert (sig.register("ON"), sig.register("init"), sig.register("x")) == ("AR[2]", "AR[5]", None)


@pytest.mark.parametrize(("params", "reason"), [
    ("INOUT bool on", "bool parameter on is passed by reference (INOUT): only a num or a point is read back"),
    ("dnum d", "dnum parameter d"),
    ("INOUT tooldata t", "tooldata parameter t is passed by reference (INOUT)"),
    ("\\num speed", "optional num parameter speed"),
    ("num list{*}", "parameter list is an array"),
    (",".join(f"num a{i}" for i in range(11)), "11 parameters: a TP CALL takes at most 10 arguments"),
])  # fmt: skip
def test_what_tp_cannot_pass_is_said(params, reason):
    assert layout(params).startswith(reason)


def test_a_num_parameter_the_routine_changes_is_copied_to_a_register():
    """RAPID passes it by value: a local copy. AR[n] cannot be written, a register can."""
    procs = "PROC Turn(num angle)\n  IF angle>360 angle:=0;\n  nA:=angle;\nENDPROC"
    assert program("Turn 400;", DATA, procs, "TURN") == [
        "R[1:angle]=AR[1]",
        "IF (R[1:angle]>360) THEN", "R[1:angle]=0", "ENDIF",
        "R[2:nA]=R[1:angle]",
    ]  # fmt: skip


def test_other_parameters_the_routine_changes_are_refused():
    routine = parse_module("MODULE M\nPROC p(bool on)\n  on:=FALSE;\nENDPROC\nENDMODULE").routines[0]
    assert signature(routine) == "it changes its parameter on: only a whole num parameter can be copied to a register"


def test_the_called_routine_reads_its_arguments():
    assert program("Sub 3,-2.5,TRUE\\Check;", DATA, SUB, "SUB") == [
        "R[1:nA]=AR[1]", "R[2:nSum]=R[2:nSum]+AR[2]",
        "IF (AR[3]=1) THEN", "R[3:nOn]=R[3:nOn]+1", "ENDIF",
        "IF (AR[4]=1) THEN", "R[4:nChecks]=R[4:nChecks]+1", "ENDIF",
        "FOR R[5:i]=1 TO AR[1]", "R[6:nLoops]=R[6:nLoops]+1", "ENDFOR",
        "WAIT AR[2]",
    ]  # fmt: skip


def test_every_argument_is_passed_switches_as_1_or_0():
    body = "Sub 3,-2.5,TRUE\\Check;\nSub cFive,nIn,FALSE\\Skip\\Init;\nSub 1,0.5,TRUE;"
    lines = [line for line in tp_lines(run(body, DATA, extra_procs=SUB)) if line.startswith("CALL")]
    # nIn is only read here: like the controller, CrossArm keeps a register comment only where it is written.
    # As ROBOGUIDE stores them: a negative constant in parentheses (it refuses CALL SUB(3,-2.5,...),
    # ASBN-092), a decimal without its leading zero.
    assert lines == ["CALL SUB(3,(-2.5),1,1,0,0)", "CALL SUB(5,R[1],0,0,1,1)", "CALL SUB(1,.5,1,0,0,0)"]


def test_negative_constants_are_written_as_the_controller_accepts_them():
    """Parentheses in assignments, calculations and FOR bounds; bare in conditions (ROBOGUIDE)."""
    body = "n:=-2;\nn:=n*-3;\nFOR i FROM -2 TO 2 DO\n  n:=0;\nENDFOR\nIF n<-2.5 n:=1;"
    assert tp_lines(run(body, "VAR num n;")) == [
        "R[1:n]=(-2)", "R[1:n]=R[1:n]*(-3)",
        "FOR R[2:i]=(-2) TO 2", "R[1:n]=0", "ENDFOR",
        "IF (R[1:n]<-2.5) THEN", "R[1:n]=1", "ENDIF",
    ]  # fmt: skip


def test_a_routine_passes_its_own_arguments_on():
    outer = "PROC Outer(num x\\switch Check)\n  Sub x,1,TRUE\\Check?Check;\nENDPROC"
    assert program("Outer 4;", DATA, SUB + "\n" + outer, "OUTER") == ["CALL SUB(AR[1],1,1,AR[2],0,0)"]


def test_a_routine_of_switches_only_is_called_with_all_of_them():
    procs = "PROC Zone(\\switch Request|switch Release\\switch Wait)\n  Stop;\nENDPROC"
    assert tp_lines(run("Zone\\Release;\nZone;", extra_procs=procs)) == ["CALL ZONE(0,1,0)", "CALL ZONE(0,0,0)"]


@pytest.mark.parametrize(("call", "reason"), [
    ("Sub 3,1;", "2 arguments given, Sub takes 3"),
    ("Sub 3,1,TRUE\\Fast;", "Sub has no switch \\FAST"),
    ("Sub 3,Abs(nA),TRUE;", "argument b: 'Abs(nA)' is not a simple numeric value"),
    ("Sub 3,1,bFlag;", "argument on: 'bFlag' must be TRUE, FALSE or a bool argument"),
])  # fmt: skip
def test_calls_that_cannot_be_passed_stay_todo(call, reason):
    assert todos(run(call, DATA + "VAR bool bFlag;", extra_procs=SUB))[0].startswith(reason)


def test_a_routine_out_of_scope_says_why_at_every_call():
    procs = "PROC Grip(dnum d)\n  Stop;\nENDPROC"
    assert todos(run("Grip 3;", extra_procs=procs))[0].startswith(
        "Grip is not converted: dnum parameter d: TP arguments are numbers or text")


def test_a_string_parameter_is_passed_as_text_written_in_the_call():
    """ROBOGUIDE takes CALL X('text') up to 38 characters and refuses an apostrophe inside: a backquote."""
    procs = "PROC Fault(string sText,num nCode)\n  SetGO goCode,nCode;\n  Stop;\nENDPROC"
    body = 'Fault "Gripper not open",3;\nFault "l\'usinage",4;\nFault MSG,5;\nFault "' + "x" * 45 + '",6;'
    result = run(body, 'CONST string MSG:="From a CONST";', extra_procs=procs)
    assert [line for line in tp_lines(result) if line.startswith("CALL")] == [
        "CALL FAULT('Gripper not open',3)", "CALL FAULT('l`usinage',4)", "CALL FAULT('From a CONST',5)",
        f"CALL FAULT('{'x' * 38}',6)",
    ]  # fmt: skip
    assert any("cut to 38 characters" in n.message for n in result.notes if n.kind == "WARNING")


def test_a_string_worked_out_at_run_time_is_passed_in_a_string_register_but_not_shown():
    """A TP program keeps a string argument but cannot show it: MESSAGE takes fixed text. The text is worked
    out in a scratch string register, which the CALL copies (ROBOGUIDE)."""
    procs = "PROC Fault(string sText)\n  Set doFault;\n  TPWrite sText;\nENDPROC"
    assert tp_lines(run('Fault "Part "+NumToStr(n,0);', "VAR num n;", extra_procs=procs)) == [
        "CALL CA_TEXT(25,'Part ',0)", "SR[24]=R[200]", "SR[25]=SR[25]+SR[24]", "CALL FAULT(SR[25])"]
    source = f"MODULE M\nPROC main()\nFault \"Stop\";\nENDPROC\n{procs}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    fault = next(p for p in result.programs if p.program.name == "FAULT").program
    assert fault.lines[1].text == "DO[1]=ON"
    assert [n.category for n in result.notes if n.kind == "TODO"] == ["TPWrite showing a value"]


POINTS = """CONST robtarget pA:=[[600,0,300],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
PERS tooldata tGrip:=[TRUE,[[0,0,185.5],[1,0,0,0]],[2.4,[0,0,90],[1,0,0,0],0,0,0]];
VAR num nRow:=1;
VAR robtarget pSeen{2};
CONST robtarget pRow{2}:=[[[600,0,300],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
  [[700,0,300],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]]];"""
PICK = "PROC PickAt(robtarget p,num n)\n  MoveL Offs(p,0,0,-40),v500,fine,tGrip;\n  MoveL p,v100,fine,tGrip;\nENDPROC"


def test_a_point_parameter_is_passed_in_a_position_register():
    """The caller sets PR[k] before the CALL, the routine moves to it; Offs is a copy offset component by component."""
    source = f"MODULE M\n{POINTS}\nPROC main()\n  PickAt pA,2;\n  PickAt Offs(pA,0,50,0),3;\nENDPROC\n{PICK}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert not [n for n in result.notes if n.kind == "TODO"]
    main, pick = (next(p for p in result.programs if p.program.name == name).program for name in ("MAIN", "PICKAT"))
    assert [getattr(line, "text", "") for line in main.lines[1:]] == [
        "PR[99]=P[1]", "CALL PICKAT(2)", "PR[99]=P[2]", "CALL PICKAT(3)"]
    assert (main.positions[1].value.y, main.positions[1].uf, main.positions[1].ut) == (50, 0, 1)
    assert [line.text if isinstance(line, Instruction) else f"{line.kind} {line.target}" for line in pick.lines[1:]] == [
        "PR[98]=PR[99]", "PR[98,3]=PR[98,3]+(-40)", "UFRAME_NUM=0", "UTOOL_NUM=1", "L PR[98]", "L PR[99]"]
    assert [(a.rapid_name, a.number) for a in result.point_registers] == [("CROSSARM.POINT", 98), ("PickAt.p", 99)]


def test_a_point_only_known_at_run_time_or_turned_stays_todo():
    procs = PICK + "\nPROC Turned(robtarget p)\n  PickAt RelTool(p,0,0,10),1;\nENDPROC"
    body = "PickAt pSeen{nRow},1;\nTurned pA;"
    source = f"MODULE M\n{POINTS}\nPROC main()\n{body}\nENDPROC\n{procs}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    found = [(n.category, n.message) for n in result.notes if n.kind == "TODO"]
    assert {category for category, _ in found} == {Blocker.RUNTIME_POSITION}
    assert any("pSeen{nRow}: an array of points indexed at run time is kept in registers when no program changes"
               " it; pSeen is a VAR" in message for _, message in found)  # fmt: skip
    assert any("passed on as it is or with Offs()" in message for _, message in found)  # TP has no pose product


def test_reltool_of_a_point_parameter_is_a_tool_offset():
    """A copy of the point with the displacement and the turns in its six components, the move made to the point
    with Tool_Offset (composed in the tool frame, TP frame probe). A negated argument is multiplied by -1: `-h`."""
    procs = ("PROC Turned(robtarget p,num h)\n  MoveL RelTool(p,0,0,-h),v100,fine,tGrip;\n"
             "  MoveJ RelTool(p,10,0,0\\Rz:=90),v1000,fine,tGrip;\n  MoveL Offs(p,0,0,-h),v100,fine,tGrip;\nENDPROC")
    source = f"MODULE M\n{POINTS}\nPROC main()\n  Turned pA,40;\nENDPROC\n{procs}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert not [n for n in result.notes if n.kind == "TODO"]
    lines = next(p for p in result.programs if p.program.name == "TURNED").program.lines[1:]
    text = [line.text if isinstance(line, Instruction) else f"{line.kind} {line.target} {line.options}" for line in lines]
    assert text[:7] == ["PR[98]=PR[99]", "PR[98,1]=0", "PR[98,2]=0", "PR[98,3]=AR[1]*(-1)", "PR[98,4]=0",
                        "PR[98,5]=0", "PR[98,6]=0"]  # fmt: skip
    assert "L PR[99] Tool_Offset,PR[98]" in text and "J PR[99] Tool_Offset,PR[98]" in text
    assert "PR[98,6]=90" in text
    assert "PR[97,3]=PR[97,3]-AR[1]" in text  # Offs: one operator, `+` and `*` together are refused


def test_the_mapping_file_pins_the_register_of_a_point(tmp_path):
    source = f"MODULE M\n{POINTS}\nPROC main()\n  PickAt pA,2;\nENDPROC\n{PICK}\nENDMODULE\n"
    path = tmp_path / "map.json"
    path.write_text('{"point_registers": {"PickAt.p": 40}}', encoding="utf-8")
    config = ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))
    result = convert([parse_module(source)], config, sources={"M": source})
    main = next(p for p in result.programs if p.program.name == "MAIN").program
    assert main.lines[1].text == "PR[40]=P[1]"
    assert [(a.rapid_name, a.number, a.fixed) for a in result.point_registers] == [
        ("PickAt.p", 40, True), ("CROSSARM.POINT", 99, False)]


RECORD = ("RECORD partdata\n  string name;\n  num passes;\n  num depth;\n  bool chamfer;\nENDRECORD\n"
          'PERS partdata pdHousing:=["HOUSING-120",2,0.8,TRUE];\nVAR num nDone;VAR num nDepth;\n')  # fmt: skip
DEBURR = """PROC Deburr(partdata part)
  FOR i FROM 1 TO part.passes DO
    nDepth:=part.depth;
  ENDFOR
  IF part.chamfer THEN
    nDone:=nDone+1;
  ENDIF
ENDPROC"""


def test_a_record_is_passed_as_the_components_the_routine_reads():
    """In the record's order, each an argument of its own; a PERS no program changes gives its saved values."""
    assert program("Deburr pdHousing;", RECORD, DEBURR, "MAIN") == ["CALL DEBURR(2,.8,1)"]
    assert program("Deburr pdHousing;", RECORD, DEBURR, "DEBURR") == [
        "FOR R[1:i]=1 TO AR[1]", "R[2:nDepth]=AR[2]", "ENDFOR",
        "IF (AR[3]=1) THEN", "R[3:nDone]=R[3:nDone]+1", "ENDIF",
    ]  # fmt: skip


def test_a_record_s_text_goes_in_the_call():
    procs = "PROC Show(partdata part)\n  Say part.name;\nENDPROC\nPROC Say(string s)\nENDPROC"
    assert program("Show pdHousing;", RECORD, procs, "MAIN") == ["CALL SHOW('HOUSING-120')"]
    assert program("Show pdHousing;", RECORD, procs, "SHOW") == ["CALL SAY(AR[1])"]


def test_a_record_passed_on_whole_is_not_converted():
    procs = DEBURR + "\nPROC Twice(partdata part)\n  Deburr part;\nENDPROC"
    result = run("Twice pdHousing;", RECORD, extra_procs=procs)
    assert "partdata parameter part is used whole" in todos(result)[0]


def test_a_record_used_whole_is_not_passed():
    routine = parse_module(f"MODULE M\n{RECORD}PROC p(partdata part)\n  pdHousing:=part;\nENDPROC\nENDMODULE")
    assert signature(routine.routines[0], {"partdata": (("name", "string"), ("passes", "num"), ("depth", "num"),
                                                        ("chamfer", "bool"))}) == (
        "partdata parameter part is used whole: only its components can be passed as TP arguments")  # fmt: skip


INOUT = "PROC Count(INOUT num n,num d)\n  n:=n+d;\nENDPROC\nPROC Peek(INOUT num n)\n  nA:=n;\nENDPROC"


def test_a_num_passed_by_reference_is_read_back_after_the_call():
    """The routine works on a register of its own; the caller reads it into its data after the CALL."""
    assert program("Count nSum,2;\nPeek nSum;", DATA, INOUT, "MAIN") == [
        "CALL COUNT(R[1:nSum],2)", "R[1:nSum]=R[2:n]", "CALL PEEK(R[1:nSum])"]  # Peek does not change it
    assert program("Count nSum,2;", DATA, INOUT, "COUNT") == ["R[2:n]=AR[1]", "R[2:n]=R[2:n]+AR[2]"]


def test_incr_on_a_parameter_passed_by_reference_is_read_back_too():
    procs = "PROC Bump(INOUT num n)\n  Incr n;\nENDPROC"
    lines = program("Bump nSum;", DATA, procs, "MAIN")
    assert lines == ["CALL BUMP(R[1:nSum])", "R[1:nSum]=R[2:n]"]


def test_a_constant_passed_by_reference_and_changed_stays_todo():
    result = run("Count cFive,2;", DATA, extra_procs=INOUT)
    assert "is passed by reference and changed: it must be num data of the caller" in todos(result)[0]


def test_incr_decr_add_and_clear_are_the_assignments_they_make():
    assert tp_lines(run("Incr nSum;\nDecr nA;\nAdd nSum,-2;\nAdd nSum,nIn;\nClear nA;", DATA)) == [
        "R[1:nSum]=R[1:nSum]+1", "R[2:nA]=R[2:nA]-1", "R[1:nSum]=R[1:nSum]+(-2)", "R[1:nSum]=R[1:nSum]+R[3]",
        "R[2:nA]=0",
    ]  # fmt: skip


FRAMES = POINTS + """
CONST robtarget pFixed:=[[650,50,320],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
PERS tooldata tOther:=[TRUE,[[0,0,100],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
PERS wobjdata wFix:=[FALSE,TRUE,"",[[1000,0,0],[1,0,0,0]],[[0,0,100],[1,0,0,0]]];"""
WITH = r"""PROC PickWith(robtarget p,PERS tooldata t\PERS wobjdata WObj)
  MoveL p,v100,fine,t\WObj?WObj;
  MoveL pFixed,v200,fine,t\WObj?WObj;
  Again t;
ENDPROC
PROC Again(PERS tooldata tt)
  MoveL pFixed,v200,fine,tt;
ENDPROC"""


def test_a_tool_and_a_work_object_are_passed_as_their_frame_numbers():
    """The routine selects them from its arguments; its own points are in position registers, as the controller
    refuses a P recorded in another tool than the one selected (INTP-253). A work object not given is wobj0."""
    source = f"MODULE M\n{FRAMES}\nPROC main()\n  PickWith pA,tGrip\\WObj:=wFix;\n  PickWith pA,tOther;\nENDPROC\n{WITH}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert not [n for n in result.notes if n.kind == "TODO"]
    lines = {info.program.name: [getattr(x, "text", None) or f"{x.kind} {x.target}" for x in info.program.lines[1:]]
             for info in result.programs}  # fmt: skip
    assert [x for x in lines["MAIN"] if x.startswith("CALL")] == ["CALL PICKWITH(1,1)", "CALL PICKWITH(2,0)"]
    assert lines["PICKWITH"][:3] == ["UFRAME_NUM=AR[2]", "UTOOL_NUM=AR[1]", "L PR[99]"]
    assert lines["PICKWITH"][3].startswith("L PR[") and lines["PICKWITH"][-1] == "CALL AGAIN(AR[1])"
    assert lines["AGAIN"][:2] == ["UFRAME_NUM=0", "UTOOL_NUM=AR[1]"]
    assert [a.name for a in result.point_arrays] == ["PickWith.pFixed", "Again.pFixed"]


def test_a_frame_used_other_than_to_move_with_is_not_passed():
    routine = parse_module("MODULE M\nPROC p(PERS tooldata t)\n  TPWrite \"\"\\Num:=t.tload.mass;\nENDPROC\nENDMODULE")
    assert signature(routine.routines[0]) == "its t is used other than to move with or to pass on: a frame is passed by its number"


def test_moveabsj_with_a_tool_the_routine_is_given_stays_todo():
    joint = "CONST jointtarget jHome:=[[0,0,0,0,30,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    procs = "PROC Home(PERS tooldata t)\n  MoveAbsJ jHome,v100,fine,t;\nENDPROC"
    source = f"MODULE M\n{POINTS}\n{joint}\nPROC main()\n  Home tGrip;\nENDPROC\n{procs}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert any("INTP-253" in n.message for n in result.notes if n.kind == "TODO")


SHIFT = """PROC Shift(VAR robtarget pAt)
  pAt:=Offs(pAt,0,50,0);
  MoveL pAt,v400,fine,tGrip;
ENDPROC
PROC Lift(INOUT robtarget pAt,num nUp)
  pAt.trans.z:=pAt.trans.z-nUp;
  Shift pAt;
ENDPROC"""


def test_a_point_a_routine_changes_comes_back_to_the_caller():
    """VAR / INOUT robtarget: the routine works on the position register it is passed in, the caller reads it
    back after the CALL; the caller's point is then kept in a register too."""
    data = POINTS + "VAR robtarget pCur;\nVAR num nY;"
    body = "pCur:=pA;\nShift pCur;\nLift pCur,100;\nnY:=pCur.trans.y;"
    assert program(body, data, SHIFT, "MAIN") == [
        "PR[99]=P[1]", "PR[98]=PR[99]", "CALL SHIFT", "PR[99]=PR[98]", "PR[97]=PR[99]", "CALL LIFT(100)",
        "PR[99]=PR[97]", "R[1:nY]=PR[99,2]"]  # fmt: skip
    assert program(body, data, SHIFT, "SHIFT")[:1] == ["PR[98,2]=PR[98,2]+50"]  # in its own register: no copy
    assert program(body, data, SHIFT, "LIFT") == ["PR[97,3]=PR[97,3]-AR[1]", "PR[98]=PR[97]", "CALL SHIFT",
                                                   "PR[97]=PR[98]"]  # fmt: skip


def test_a_point_passed_back_must_be_a_point_of_the_program():
    result = run("Shift Offs(pA,0,0,10);", POINTS, extra_procs=SHIFT)
    assert "is changed by the routine: it must be a robtarget of the program" in todos(result)[0]


def test_a_routine_calling_itself_back_with_points_stays_todo():
    """Each call would write the position registers the calls under way read: Hanoi's towers in RAPID."""
    procs = "PROC Tower(num n,robtarget pFrom)\n  IF n>0 Tower n-1,pFrom;\n  MoveL pFrom,v100,fine,tGrip;\nENDPROC"
    result = run("Tower 3,pA;", POINTS, extra_procs=procs)
    assert "calls itself back and is given points" in todos(result)[0]


SPEED_POINTS = "".join(f"CONST robtarget {p}:=[[1100,{y},{z}],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
                 for p, y, z in (("pA", 50, 1000), ("pB", 250, 1000), ("pC", 250, 800)))  # fmt: skip
MOVES = """PROC Moves(speeddata v,zonedata z)
  MoveJ pA,v,z,tool0;
  MoveL pB,v,z,tool0;
  MoveL pC,v,fine,tool0;
ENDPROC"""


def test_a_routine_given_its_speed_and_zone_copies_them_to_registers():
    """A move takes no AR[n] as its speed or CNT (ROBOGUIDE, ASBN-092): R[n] it does (speed argument probe)."""
    source = f"MODULE M\n{SPEED_POINTS}\nPROC main()\nMoves v400,z50;\nMoves v200,z10;\nENDPROC\n{MOVES}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    moves = next(p for p in result.programs if p.program.name == "MOVES").program
    assert [getattr(line, "text", None) for line in moves.lines[1:5]] == [
        "R[1:v.tcp]=AR[1]", "R[2:v.joint]=AR[2]", "R[3:z.cnt]=AR[3]", "R[4:z.cnt2]=AR[4]"]  # fmt: skip
    assert [(m.speed, m.termination) for m in moves.lines if not isinstance(m, Instruction)] == [
        ("R[2]%", "CNT R[3]"), ("R[1]mm/sec", "CNT R[4]"), ("R[1]mm/sec", "FINE")]  # fmt: skip
    # the CNT of each corner as the caller would write the move with what it passes
    assert [line for line in tp_lines(result) if line.startswith("CALL")] == [
        "CALL MOVES(400,9,100,100)", "CALL MOVES(200,4,100,97)"]  # fmt: skip


def test_a_zone_written_in_the_routine_is_worked_out_at_the_call_from_the_speed():
    procs = "PROC Slow(speeddata v)\n  MoveL pA,v,z10,tool0;\n  MoveL pB,v,fine,tool0;\nENDPROC"
    sig = signature(parse_module(f"MODULE M\n{SPEED_POINTS}\n{procs}\nENDMODULE").routines[0])
    assert [s.name for s in sig.arguments] == ["v.tcp", "v.cnt"]
    assert [line for line in tp_lines(run("Slow v200;", SPEED_POINTS, extra_procs=procs)) if line.startswith("CALL")] == [
        "CALL SLOW(200,97)"]  # fmt: skip


@pytest.mark.parametrize(("procs", "reason"), [
    ("PROC P(speeddata v)\n  TPWrite \"\"\\Num:=v.v_tcp;\nENDPROC", "its speeddata v is used other than as the speed of its moves"),
    ("PROC P(zonedata z)\n  Q z;\nENDPROC\nPROC Q(zonedata z)\n  MoveL pA,v100,z,tool0;\nENDPROC",
     "its zonedata z is used other than as the zone of its moves"),
    ("PROC P(speeddata v)\n  MoveC pA,pB,v,fine,tool0;\nENDPROC", "MoveC at the speed of a parameter: not measured"),
])  # fmt: skip
def test_speeds_and_zones_used_otherwise_are_refused(procs, reason):
    assert signature(parse_module(f"MODULE M\n{SPEED_POINTS}\n{procs}\nENDMODULE").routines[0]).startswith(reason)


def test_fine_given_for_a_zone_the_routine_moves_through_stays_todo():
    assert todos(run("Moves v400,fine;", SPEED_POINTS, extra_procs=MOVES))[0].startswith(
        "argument z: fine, where Moves moves through a zone given at run time")
