# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Error handlers: the part TP can do — a wait with a time limit, and what to do when it runs out.

The shapes are the common ones (the commonest: `TEST ERRNO CASE ERR_WAIT_MAXTIME:
TRYNEXT;`), with made-up names.
"""

from datetime import datetime

from helpers import parse_module
from test_translate import run, todos, tp_lines

from crossarm.convert import ConversionConfig
from crossarm.convert.handlers import body as handler_body
from crossarm.convert.handlers import on_timeout, only_passes_on

DATA = "VAR num nRetries:=0;\nVAR num nNext:=0;\nVAR bool bDone:=FALSE;"
TRYNEXT = """ERROR
  TEST ERRNO
  CASE ERR_WAIT_MAXTIME:
    TRYNEXT;
  ENDTEST"""


def warnings(result) -> list[str]:
    return [note.message for note in result.notes if note.kind == "WARNING"]


def test_on_timeout_go_on_with_the_next_instruction():
    result = run(f"WaitUntil bDone\\MaxTime:=2;\nWaitDI diReady,1\\MaxTime:=0.5;\nnNext:=1;\n{TRYNEXT}", DATA)
    assert todos(result) == []
    # $WAITTMOUT is write-protected for programs: each wait is a loop reading a timer.
    assert tp_lines(result) == [
        "TIMER[10]=RESET", "TIMER[10]=START",
        "LBL[1]", "R[1:WaitTimer]=TIMER[10]", "IF (F[1]=OFF AND R[1:WaitTimer]<2) THEN", "JMP LBL[1]", "ENDIF",
        "TIMER[10]=STOP",
        "TIMER[10]=RESET", "TIMER[10]=START",
        "LBL[2]", "R[1:WaitTimer]=TIMER[10]", "IF (DI[1]=OFF AND R[1:WaitTimer]<.5) THEN", "JMP LBL[2]", "ENDIF",
        "TIMER[10]=STOP",
        "R[2:nNext]=1",
    ]  # fmt: skip
    assert any("timeout of its 2 wait(s)" in w for w in warnings(result))
    assert result.coverage.percent == 100.0


def test_retry_jumps_back_to_the_wait_and_the_rest_of_the_handler_runs_at_the_timeout():
    handler = """ERROR
  IF ERRNO=ERR_WAIT_MAXTIME THEN
    IF nRetries<2 THEN
      nRetries:=nRetries+1;
      RETRY;
    ELSE
      RETURN;
    ENDIF
  ENDIF
  RAISE;"""
    result = run(f"WaitUntil bDone\\MaxTime:=0.2;\nnNext:=1;\n{handler}", DATA)
    assert todos(result) == []
    assert tp_lines(result) == [
        "LBL[1]", "TIMER[10]=RESET", "TIMER[10]=START",
        "LBL[2]", "R[1:WaitTimer]=TIMER[10]", "IF (F[1]=OFF AND R[1:WaitTimer]<.2) THEN", "JMP LBL[2]", "ENDIF",
        "TIMER[10]=STOP",
        "IF (F[1]=ON) THEN", "JMP LBL[3]", "ENDIF",  # on time
        "IF (R[2:nRetries]<2) THEN", "R[2:nRetries]=R[2:nRetries]+1", "JMP LBL[1]",
        "ELSE", "END", "ENDIF",
        "LBL[3]",
        "R[3:nNext]=1",
    ]  # fmt: skip


def test_a_timeout_path_that_falls_through_ends_the_routine():
    handler = "ERROR\n  IF ERRNO=ERR_WAIT_MAXTIME THEN\n    nNext:=9;\n  ENDIF"
    lines = tp_lines(run(f"WaitUntil bDone\\MaxTime:=1;\n{handler}", DATA))
    assert lines[lines.index("TIMER[10]=STOP") + 4 :] == ["R[2:nNext]=9", "END", "LBL[3]"]


def test_what_cannot_be_written_leaves_the_wait_and_the_handler_todo():
    # RAISE on the timeout path: the error goes to a caller TP has no handler for.
    result = run("WaitUntil bDone\\MaxTime:=1;\nERROR\n  RAISE ERR_MINE;", DATA)
    assert "ERROR handler only passes errors on" in warnings(result)[0]  # nothing for TP to do here...
    assert "does not say what to do when the time runs out" in todos(result)[0]  # ...but the wait cannot time out without it
    # Another option, or a handler that also deals with other errors: the handler stays TODO.
    result = run("WaitUntil bDone\\MaxTime:=1\\PollRate:=0.1;\nnNext:=1;\n" + TRYNEXT, DATA)
    assert "PollRate" in todos(result)[0]
    handler = "ERROR\n  TEST ERRNO\n  CASE ERR_WAIT_MAXTIME:\n    TRYNEXT;\n  DEFAULT:\n    nNext:=0;\n  ENDTEST"
    result = run(f"WaitUntil bDone\\MaxTime:=1;\n{handler}", DATA)
    assert "IF (F[1]=OFF AND R[1:WaitTimer]<1) THEN" in tp_lines(result)
    assert "its timeout part is written at the waits" in todos(result)[0]


def test_handlers_tp_has_no_use_for():
    result = run("nNext:=1;\nERROR\n  RAISE;", DATA)
    assert todos(result) == [] and "only passes errors on" in warnings(result)[0]
    result = run("nNext:=1;\nBACKWARD\n  nNext:=0;", DATA)
    assert todos(result) == [] and "stepped backwards" in warnings(result)[0]
    result = run("nNext:=1;\nUNDO\n  nNext:=0;", DATA)  # clean-up when the program is stopped: TP has none
    assert len(todos(result)) == 1


def handler_of(text: str):
    module = parse_module(f"MODULE M\nPROC p()\n  WaitTime 1;\n{text}\nENDPROC\nENDMODULE\n")
    return handler_body(module.routines[0].handlers[0])


def test_handler_bodies_are_read_with_their_module_line_numbers():
    stmts = handler_of(TRYNEXT)
    assert stmts[0].span.line == 5  # ERROR is line 4 of the module
    path = on_timeout(stmts)
    assert path is not None and path.only
    assert [s.kind for s in path.steps] == ["TRYNEXT"]
    assert on_timeout(handler_of("ERROR\n  TRYNEXT;")).only is False  # takes every error, not only timeouts
    assert on_timeout(handler_of("ERROR\n  TEST ERRNO\n  CASE ERR_OTHER:\n    RETRY;\n  ENDTEST")) is None
    assert only_passes_on(handler_of("ERROR\n  RAISE ERR_MINE;"))


def test_the_wait_timer_is_one_the_robot_does_not_use():
    config = ConversionConfig(timestamp=datetime(2026, 1, 1), reserved={"TIMER": {10: ("CYCLE",), 9: ("CYCLE",)}})
    result = run(f"WaitUntil bDone\\MaxTime:=2;\n{TRYNEXT}", DATA, config)
    assert tp_lines(result)[0] == "TIMER[8]=RESET"
    assert result.wait_clock == ("TIMER[8]", "R[1:WaitTimer]")


def test_a_wait_with_a_time_flag_sets_it_and_goes_on_without_a_handler():
    """\\TimeFlag: RAPID raises no error when the time runs out, it sets the flag and goes on."""
    result = run("WaitDI diReady,1\\MaxTime:=2.5\\TimeFlag:=bLate;\nIF bLate nNext:=1;", DATA + "\nVAR bool bLate;")
    assert todos(result) == []
    assert tp_lines(result) == [
        "TIMER[10]=RESET", "TIMER[10]=START",
        "LBL[1]", "R[1:WaitTimer]=TIMER[10]", "IF (DI[1]=OFF AND R[1:WaitTimer]<2.5) THEN", "JMP LBL[1]", "ENDIF",
        "TIMER[10]=STOP", "F[1]=(R[1:WaitTimer]>=2.5)",
        "IF (F[1]=ON) THEN", "R[2:nNext]=1", "ENDIF",
    ]  # fmt: skip


def test_a_time_flag_must_be_bool_data():
    assert "TimeFlag must be bool data" in todos(run("WaitDI diReady,1\\MaxTime:=1\\TimeFlag:=nNext;", DATA))[0]
