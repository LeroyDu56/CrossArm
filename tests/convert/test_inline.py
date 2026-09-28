# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Conditions calling the backup's own bool functions, written as the test those functions make.

Such conditions were a large source of lost code: a TODO on the condition took the whole IF
block with it. The functions tested here have the common shape (an input tested, RobOS() so that
it is skipped in simulation).
"""

from helpers import parse_body
from test_translate import run, todos, tp_lines

from crossarm.convert.inline import _returned
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr

HAS_VISION = """FUNC bool HasVision()
  ! the vision option is fitted
  IF diNoVision=0 OR RobOS()=FALSE THEN
    RETURN TRUE;
  ELSE
    RETURN FALSE;
  ENDIF
ENDFUNC"""
DEBUGGING = """FUNC bool Debugging()
  IF diDebug=0 THEN
    RETURN FALSE;
  ENDIF
  RETURN TRUE;
ENDFUNC"""
ARMED = """FUNC bool Armed()
  RETURN HasVision() AND bArmed;
ENDFUNC"""
FUNCS = f"{HAS_VISION}\n{DEBUGGING}\n{ARMED}"
DATA = "PERS bool bArmed:=FALSE;\nCONST bool cDemo:=FALSE;"


def test_a_bool_function_is_written_as_the_test_it_makes():
    result = run("IF HasVision()=TRUE THEN\n  Set doFlash;\nENDIF", DATA, extra_procs=FUNCS)
    assert todos(result) == []
    # RobOS() is TRUE on the robot: `x OR FALSE` is x. The remark keeps what the RAPID said.
    assert tp_lines(result) == ["!HasVision() = TRUE", "IF (DI[1]=OFF) THEN", "DO[1]=ON", "ENDIF"]
    assert result.inlined == {"HasVision": 1}
    assert [x.category for x in result.notes if x.kind == "WARNING"].count("RobOS() taken as TRUE (real controller)") == 1


def test_negations_comparisons_and_nested_functions_fold():
    result = run("IF Debugging()=FALSE AND NOT Armed() THEN\n  Set doFlash;\nENDIF", DATA, extra_procs=FUNCS)
    assert todos(result) == []
    assert tp_lines(result)[1] == "IF (DI[1]=OFF AND (DI[2]=ON OR F[1]=OFF)) THEN"


def test_a_condition_that_folds_to_a_constant_is_left_out_or_kept_without_test():
    body = "IF NOT RobOS() THEN\n  Set doSim;\nENDIF\nIF RobOS() OR bArmed THEN\n  Set doReal;\nENDIF"
    assert tp_lines(run(body, DATA)) == ["!l.5 IF never TRUE: left out", "!l.8 IF always TRUE: no test", "DO[1]=ON"]
    assert tp_lines(run("IF cDemo THEN\n  Set doDemo;\nENDIF", DATA)) == ["!l.5 IF never TRUE: left out"]


def test_while_and_waituntil_use_the_same_tests():
    result = run("WHILE Debugging() DO\n  WaitTime 1;\nENDWHILE\nWaitUntil HasVision();", DATA, extra_procs=FUNCS)
    assert todos(result) == []
    lines = tp_lines(result)
    assert "IF (DI[1]=OFF) THEN" in lines  # the loop exit: NOT Debugging()
    assert "WAIT (DI[2]=OFF)" in lines


def test_functions_doing_more_than_returning_a_value_stay_todo():
    procs = """FUNC bool Counted()
  nCalls:=nCalls+1;
  RETURN TRUE;
ENDFUNC
FUNC bool Above(num limit)
  RETURN nCalls>limit;
ENDFUNC"""
    result = run("IF Counted() THEN\n  Set doA;\nENDIF\nIF Above(3) THEN\n  Set doB;\nENDIF", "VAR num nCalls;",
                 extra_procs=procs)  # fmt: skip
    assert len(todos(result)) == 2 and not result.inlined


def test_a_local_of_the_caller_hiding_the_data_a_function_reads_stops_it():
    procs = "FUNC bool Ready()\n  RETURN bArmed;\nENDFUNC"
    result = run("VAR bool bArmed:=TRUE;\nIF Ready() THEN\n  Set doA;\nENDIF", DATA, extra_procs=procs)
    assert len(todos(result)) == 1 and not result.inlined


def returned(body: str) -> str | None:
    value = _returned(parse_body(body))
    return None if value is None else format_expr(value)


def test_the_shapes_a_function_body_can_have():
    assert returned("RETURN a AND b;") == "a AND b"
    assert returned("IF a THEN\nRETURN FALSE;\nELSE\nRETURN TRUE;\nENDIF") == "NOT a"
    assert returned("IF a THEN\nRETURN TRUE;\nENDIF\nRETURN b;") == "a OR b"
    assert returned("IF a THEN\nRETURN b;\nENDIF\nRETURN FALSE;") == "a AND b"
    assert returned("IF a THEN\nRETURN TRUE;\nELSE\nRETURN TRUE;\nENDIF") == "TRUE"
    assert returned("IF a THEN\nRETURN b;\nELSE\nRETURN c;\nENDIF") is None  # would copy a twice
    assert returned("IF a THEN\nRETURN TRUE;\nELSEIF b THEN\nRETURN TRUE;\nENDIF\nRETURN FALSE;") is None
    assert isinstance(parse_body("RETURN TRUE;")[0], n.Return)
