# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Coverage: the share of the RAPID instructions written as TP, by area.

It is the figure a customer asks for first ("how much of my backup does it do?"), so it must
not flatter: a block that became one TODO counts every instruction in it, routines left out
count as not converted, and 99.97 % is never shown as 100 %.
"""

from datetime import datetime

from helpers import parse_module

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.coverage import CALLS, DATA, ERRORS, FLOW, IO, MOTION, OTHER, Coverage, Share, percent

DATA_DECLS = """CONST robtarget p1:=[[500,0,500],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
VAR num nCount:=0;"""


def coverage(body: str, procs: str = "") -> Coverage:
    source = f"MODULE M\n{DATA_DECLS}\nPROC main()\n{body}\nENDPROC\n{procs}\nENDMODULE\n"
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    return convert([parse_module(source)], config, sources={"M": source}).coverage


def shares(result: Coverage) -> dict[str, tuple[int, int]]:
    return {s.area: (s.converted, s.total) for s in result.shares}


def test_every_instruction_counts_once_by_area():
    result = coverage("""  ! a comment is not an instruction
  VAR num nLocal:=1;
  MoveJ p1,v1000,z50,tool0;
  Set do1;
  WaitTime 0.5;
  nCount:=nCount+1;
  IF nCount>2 THEN
    Reset do1;
  ENDIF
  Sub;""", "PROC Sub()\n  Stop;\nENDPROC")
    assert shares(result) == {MOTION: (1, 1), IO: (3, 3), DATA: (1, 1), FLOW: (2, 2), CALLS: (1, 1)}
    assert (result.converted, result.total, result.percent) == (8, 8, 100.0)


def test_a_block_that_became_a_todo_counts_all_its_instructions():
    # The condition cannot be converted: the IF is one TODO, and the three instructions in it are lost with it.
    result = coverage("""  IF Unknown() THEN
    MoveJ p1,v1000,z50,tool0;
    Set do1;
  ENDIF
  Set do2;""")
    assert shares(result) == {MOTION: (0, 1), IO: (1, 2), FLOW: (0, 1)}
    assert (result.converted, result.total, result.percent) == (1, 4, 25.0)


def test_error_handlers_count_their_statements_and_left_out_routines_count_as_not_converted():
    result = coverage("  Set do1;\nERROR\n  nCount:=0;\n  RETRY;", """TRAP tReset
  Reset do1;
  nCount:=0;
ENDTRAP
FUNC num Twice(num x)
  RETURN 2*x;
ENDFUNC""")
    assert shares(result) == {IO: (1, 2), DATA: (0, 1), ERRORS: (0, 2)}
    assert result.skipped == 2  # the TRAP; the FUNC is counted where it is called


def test_calls_that_convert_nothing_are_counted_as_other_instructions():
    result = coverage("  SomeSystemInstruction;\n  Set do1;")
    assert shares(result) == {IO: (1, 1), OTHER: (0, 1)}


def test_calls_to_a_move_routine_are_motion_and_the_routine_is_not_counted_again():
    result = coverage("  Go p1,v500,fine,tool0;",
                      "PROC Go(robtarget pt,speeddata s,zonedata z,PERS tooldata t)\n  MoveL pt,s,z,t;\nENDPROC")
    assert shares(result) == {MOTION: (1, 1)}
    assert result.skipped == 0


def test_percent_is_rounded_down_and_tasks_add_up():
    assert percent(999, 1000) == 99.9
    assert percent(9999, 10000) == 99.9  # not 100
    assert percent(0, 0) == 100.0
    a = Coverage((Share(MOTION, 10, 9),), skipped=1)
    b = Coverage((Share(MOTION, 5, 5), Share(IO, 4, 2)))
    total = a + b
    assert shares(total) == {MOTION: (14, 15), IO: (2, 4)}
    assert (total.skipped, total.total, total.converted) == (1, 19, 16)
