# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Moves made inside the backup's own routines (MoveLSide p10,... -> L P[n]), and code switched off by hand.

A backup that makes most of its moves through such routines gets thousands of TODO and not
one point in the programs, for what is one decision per routine.
"""

import json
from datetime import datetime

import pytest
from test_translate import HOME, TOOL, WOBJ, run, todos, tp_lines

from crossarm import pipeline
from crossarm.convert import ConversionConfig, build_mapping
from crossarm.convert.report import build_report
from crossarm.convert.translate import Blocker
from crossarm.convert.wrappers import parameters
from crossarm.summary import INFO, summarize

DATA = HOME + TOOL + WOBJ + "CONST robtarget pVia:=[[650,50,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"

PURE = """PROC MyMoveL(robtarget ToPoint,speeddata Speed,zonedata Zone,PERS tooldata Tool,\\PERS wobjdata WObj)
  ! only the move
  MoveL ToPoint,Speed,Zone,Tool\\WObj?WObj;
ENDPROC"""

# A routine that decides the point from a parameter before moving.
SIDED = """PROC MoveLSide(robtarget ToPoint,speeddata Speed,zonedata Zone,PERS tooldata Tool,\\PERS wobjdata WObj)
  VAR robtarget Target;
  Target:=ToPoint;
  IF bSideB THEN
    Target:=Flip(ToPoint);
  ENDIF
  MoveL Target,Speed,Zone,Tool\\wobj?wobj;
BACKWARD
  MoveL ToPoint,Speed,Zone,Tool\\wobj?wobj;
ENDPROC
PROC MoveCSide(robtarget CirPt,robtarget EndPt,speeddata Speed,zonedata Zone,PERS tooldata Tool,\\PERS wobjdata WObj)
  Set doLog;
  MoveC CirPt,EndPt,Speed,Zone,Tool\\WObj?WObj;
ENDPROC"""


def config(**kwargs) -> ConversionConfig:
    return ConversionConfig(timestamp=datetime(2026, 1, 1), **kwargs)


# ---------------------------------------------------------------------------
# Which routines are move routines
# ---------------------------------------------------------------------------


def test_parameter_lists_are_read_like_rapid():
    assert parameters("robtarget ToPoint,speeddata Speed,PERS tooldata Tool,\\PERS wobjdata WObj") == (
        ("TOPOINT", "SPEED", "TOOL"), frozenset({"WOBJ"}))  # fmt: skip
    # An optional parameter may follow without a comma; alternatives are one optional slot.
    assert parameters("num Area\\switch XP|switch XM,\\switch YP,num list{*}") == (
        ("AREA", "LIST"), frozenset({"XP", "XM", "YP"}))  # fmt: skip
    assert parameters("num a|num b") is None  # alternatives only exist for optional parameters


def test_a_routine_that_only_moves_is_converted_as_its_move():
    result = run("MyMoveL pHome,v500,z10,tGrip\\WObj:=wFix;\nMyMoveL pHome,v100,fine,tGrip;", DATA, extra_procs=PURE)
    assert tp_lines(result) == [
        "UFRAME_NUM=1", "UTOOL_NUM=1", "L P[1] 500mm/sec CNT54",
        "UFRAME_NUM=0", "L P[2] 100mm/sec FINE",  # \WObj not given: wobj0, as in RAPID
    ]  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"]
    (use,) = result.move_routines
    assert (use.name, use.instruction, use.calls, use.converted, use.pure) == ("MyMoveL", "MoveL", 2, True, True)
    # The point is listed under the call's own argument and line.
    assert (result.programs[0].points[0].source, result.programs[0].points[0].rapid_line) == ("pHome", 4)


def test_a_routine_that_does_more_stays_todo_and_says_how_to_convert_it():
    result = run("MoveLSide pHome,v500,z10,tGrip\\WObj:=wFix;", DATA + "VAR bool bSideB;", extra_procs=SIDED)
    (todo,) = [n for n in result.notes if n.kind == "TODO"]
    assert todo.category == Blocker.MOVE_ROUTINE
    assert "MoveLSide makes a MoveL but also does more (changes the point: Target:=Flip(ToPoint); IF bSideB THEN)" in todo.message
    assert '"move_routines": {"MoveLSide": true}' in todo.message
    (use,) = result.move_routines
    assert not use.converted and not use.pure and use.also_does.startswith("changes the point: Target:=Flip(ToPoint)")


def test_the_mapping_file_converts_it_and_the_report_says_what_is_left_out():
    cfg = config(move_routines={"MOVELSIDE": True, "MOVECSIDE": True})
    body = "MoveLSide pHome,v500,z10,tGrip\\WObj:=wFix;\nMoveLSide pHome,v500,fine,tGrip\\WObj:=wFix;\nMoveCSide pVia,pHome,v100,z5,tGrip;"
    result = run(body, DATA + "VAR bool bSideB;", cfg, extra_procs=SIDED)
    assert tp_lines(result) == [
        "UFRAME_NUM=1", "UTOOL_NUM=1", "L P[1] 500mm/sec CNT54", "L P[1] 500mm/sec FINE",
        "UFRAME_NUM=0", "C P[2] P[3] 100mm/sec CNT100",  # via pVia, then pHome in wobj0
    ]  # fmt: skip
    warnings = [n for n in result.notes if n.category == Blocker.MOVE_ROUTINE_ASSUMED]
    # Once per routine and program, not once per call.
    assert [w.message.split(" (mapping")[0] for w in warnings] == ["MoveLSide converted as MoveL", "MoveCSide converted as MoveC"]
    assert "Set doLog" in warnings[1].message
    report = build_report(result, cfg, ["M.mod"])
    assert "### Moves made inside routines" in report
    assert "| MoveLSide | MoveL | 2 | converted |" in report


def test_calls_that_do_not_fit_the_routine_stay_todo():
    cfg = config(move_routines={"MOVELSIDE": True})
    result = run("MoveLSide pHome,v500,z10;\nMoveLSide pHome,v500,z10,tGrip\\Speed:=v100;", DATA + "VAR bool bSideB;", cfg,
                 extra_procs=SIDED)  # fmt: skip
    messages = [m.split(" — ")[0] for m in todos(result)]
    assert messages == [
        "call to MoveLSide not converted as MoveL: 3 arguments given, MoveLSide takes 4",
        "call to MoveLSide not converted as MoveL: MoveLSide has no optional parameter \\Speed",
    ]


def test_routines_that_are_not_one_plain_move_are_left_alone():
    procs = """PROC Twice(robtarget p,speeddata s,zonedata z,PERS tooldata t)
  MoveL p,s,z,t;
  MoveL p,s,z,t;
ENDPROC
PROC Shifted(robtarget p,speeddata s,zonedata z,PERS tooldata t)
  MoveL Offs(p,0,0,10),s,z,t;
ENDPROC
PROC Maybe(robtarget p,speeddata s,zonedata z,PERS tooldata t)
  IF TRUE THEN
    MoveL p,s,z,t;
  ENDIF
ENDPROC"""
    cfg = config(move_routines={"TWICE": True, "SHIFTED": True})
    result = run("Twice pHome,v100,fine,tGrip;\nShifted pHome,v100,fine,tGrip;\nMaybe pHome,v100,fine,tGrip;",
                 DATA, cfg, extra_procs=procs)  # fmt: skip
    assert all("is not converted: robtarget parameter p" in m for m in todos(result))
    assert not result.move_routines
    # Asked for, but not recognised: said once each, not left to be discovered.
    assert sum("is not a routine CrossArm recognises as one move" in n.message for n in result.notes) == 2


def test_the_mapping_file_lists_them_ready_to_switch_on(tmp_path):
    result = run("MoveLSide pHome,v500,z10,tGrip;\nMyMoveL pHome,v500,z10,tGrip;", DATA + "VAR bool bSideB;",
                 extra_procs=SIDED + "\n" + PURE)  # fmt: skip
    text = build_mapping(result, config())
    data = json.loads(text)
    assert data["move_routines"] == {"MoveLSide": False}  # the pure one needs no decision
    assert "_move_routines" in data
    # Accepted as it is, and switching it on is a one-word change.
    path = tmp_path / "crossarm_mapping.json"
    path.write_text(text.replace('"MoveLSide": false', '"MoveLSide": true'), encoding="utf-8")
    assert ConversionConfig.from_mapping_file(path).move_routines == {"MOVELSIDE": True}


def test_the_mapping_file_is_checked(tmp_path):
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"move_routines": {"MoveLSide": True}}), encoding="utf-8")
    assert ConversionConfig.from_mapping_file(path).move_routines == {"MOVELSIDE": True}
    path.write_text(json.dumps({"move_routines": {"MoveLSide": "MoveL"}}), encoding="utf-8")
    with pytest.raises(TypeError, match="move_routines.MoveLSide"):
        ConversionConfig.from_mapping_file(path)


def test_the_window_says_how_many_moves_wait_on_one_decision(tmp_path):
    source = tmp_path / "cell.mod"
    body = "\n".join(["  MoveLSide pHome,v500,z10,tGrip;"] * 3 + ["  Lift 1;"])
    source.write_text(f"MODULE M\n{HOME}\n{TOOL}\nVAR bool bSideB;\nPROC main()\n{body}\nENDPROC\n{SIDED}\nENDMODULE\n",
                      encoding="utf-8")  # fmt: skip
    attention = summarize(pipeline.run([source], log=lambda _line: None)).attention
    texts = [text for _, text in attention]
    assert (INFO, texts[0]) in attention
    assert texts[0].startswith("3 moves are made inside routines that also do something else (MoveLSide), so")
    # The remaining work is named without counting those moves twice.
    assert "Most items to review come from: routine call with arguments (25 %)." in texts


# ---------------------------------------------------------------------------
# Code switched off by hand
# ---------------------------------------------------------------------------


def test_if_false_is_left_out_with_a_remark():
    assert tp_lines(run("IF FALSE THEN\n  Stop;\nENDIF\nEXIT;")) == ["!l.4 IF FALSE: never runs", "ABORT"]


def test_if_false_keeps_its_else_and_elseif():
    result = run("IF FALSE THEN\n  Stop;\nELSEIF b THEN\n  EXIT;\nELSE\n  RETURN;\nENDIF", "VAR bool b;")
    assert tp_lines(result) == ["!l.4 IF FALSE: never runs", "IF (F[1]=ON) THEN", "ABORT", "ELSE", "END", "ENDIF"]
    assert tp_lines(run("IF FALSE THEN\n  Stop;\nELSE\n  EXIT;\nENDIF")) == ["!l.4 IF FALSE: never runs", "ABORT"]


def test_if_true_runs_without_a_test_and_drops_what_follows():
    assert tp_lines(run("IF TRUE THEN\n  Stop;\nELSE\n  EXIT;\nENDIF")) == ["PAUSE"]
    result = run("IF b THEN\n  Stop;\nELSEIF TRUE THEN\n  EXIT;\nELSEIF c THEN\n  RETURN;\nENDIF", "VAR bool b;VAR bool c;")
    assert tp_lines(result) == ["IF (F[1]=ON) THEN", "PAUSE", "ELSE", "ABORT", "ENDIF"]


def test_while_false_is_left_out():
    assert tp_lines(run("WHILE FALSE DO\n  Stop;\nENDWHILE")) == ["!l.4 WHILE FALSE: never runs"]
