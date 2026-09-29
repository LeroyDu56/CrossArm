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
    ("INOUT num a", "parameter a is passed by reference (INOUT)"),
    ("tooldata t", "tooldata parameter t"),
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
    ("Sub 3,nA+1,TRUE;", "argument b: 'nA + 1' is not a simple numeric value"),
    ("Sub 3,1,bFlag;", "argument on: 'bFlag' must be TRUE, FALSE or a bool argument"),
])  # fmt: skip
def test_calls_that_cannot_be_passed_stay_todo(call, reason):
    assert todos(run(call, DATA + "VAR bool bFlag;", extra_procs=SUB))[0].startswith(reason)


def test_a_routine_out_of_scope_says_why_at_every_call():
    procs = "PROC Grip(tooldata t)\n  Stop;\nENDPROC"
    assert todos(run("Grip pHome;", extra_procs=procs))[0].startswith(
        "Grip is not converted: tooldata parameter t: TP arguments are numbers or text")


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


def test_a_string_known_only_at_run_time_stays_todo_and_so_does_showing_it():
    """A TP program keeps a string argument but cannot show it: MESSAGE takes fixed text."""
    procs = "PROC Fault(string sText)\n  Set doFault;\n  TPWrite sText;\nENDPROC"
    assert todos(run('Fault "Part "+NumToStr(n,0);', "VAR num n;", extra_procs=procs))[0].startswith(
        "argument sText: '\"Part \" + NumToStr(n, 0)' is only known at run time")
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
    procs = PICK + "\nPROC Turned(robtarget p)\n  MoveL RelTool(p,0,0,10),v100,fine,tGrip;\nENDPROC"
    body = "PickAt pSeen{nRow},1;\nTurned pA;"
    source = f"MODULE M\n{POINTS}\nPROC main()\n{body}\nENDPROC\n{procs}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    found = [(n.category, n.message) for n in result.notes if n.kind == "TODO"]
    assert {category for category, _ in found} == {Blocker.RUNTIME_POSITION}
    assert any("pSeen{nRow}: an array of points indexed at run time is kept in registers when no program changes"
               " it; pSeen is a VAR" in message for _, message in found)  # fmt: skip
    assert any("moved to as it is or with Offs()" in message for _, message in found)


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
