# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""FOR bounds that are not a constant or a register: worked out before the loop when TP can, else left to the
integrator in a reserved register, the FOR skipped until the line setting it is written (translate.for_bound)."""

import json
import re

import pytest
from test_condition_gates import reachable
from test_translate import HOME, TOOL, run, tp_lines

from crossarm.convert import ConversionConfig
from crossarm.convert.mapping import build_mapping

DATA = HOME + TOOL + "VAR num nCount:=0;\nVAR num nDone:=0;\nVAR string sName:=\"\";"
UNKNOWN = "FUNC num CellCount()\nIF OpMode()=OP_AUTO RETURN 4;\nRETURN 2;\nENDFUNC"


def test_a_register_bound_is_written_as_it_is():
    result = run("nCount:=3;\nFOR i FROM 1 TO nCount DO\nnDone:=nDone+1;\nENDFOR", DATA)
    assert any(re.fullmatch(r"FOR R\[\d+:i\]=1 TO R\[\d+(:nCount)?\]", line) for line in tp_lines(result))
    assert not result.gated and not [n for n in result.notes if n.kind == "TODO"]


def test_a_calculated_bound_is_worked_out_before_the_loop_in_a_register_of_its_own():
    result = run("nCount:=3;\nFOR i FROM 1 TO nCount*2-1 DO\nnDone:=nDone+1;\nENDFOR", DATA)
    lines = tp_lines(result)
    first = next(i for i, line in enumerate(lines) if line.startswith("FOR "))
    assert re.fullmatch(r"R\[\d+:Calc1\]=R\[\d+:nCount\]\*2", lines[first - 2])
    bound = re.fullmatch(r"(R\[\d+:FOR TO l\.\d+\])=R\[\d+:Calc1\]-1", lines[first - 1])
    assert bound is not None and lines[first].endswith(f"TO {bound[1]}")
    registers = json.loads(build_mapping(result, ConversionConfig()))["registers"]
    assert "CROSSARM.FOR.MAIN.L7.TO" in registers  # a key added
    assert not result.gated and not [n for n in result.notes if n.kind == "TODO"]


def test_an_end_the_loop_changes_is_copied_first():
    # TP reads the end register at each turn, RAPID works it out once (forbound probe).
    result = run("nCount:=4;\nFOR i FROM 1 TO nCount DO\nnCount:=nCount-1;\nENDFOR", DATA)
    lines = tp_lines(result)
    first = next(i for i, line in enumerate(lines) if line.startswith("FOR "))
    copy = re.fullmatch(r"(R\[\d+:FOR TO l\.7\])=R\[\d+:nCount\]", lines[first - 1])
    assert copy is not None and lines[first].endswith(f"TO {copy[1]}")


def test_an_end_a_called_routine_may_change_is_copied_and_a_local_one_is_not():
    body = "FOR i FROM 1 TO nCount DO\nTick;\nENDFOR"
    result = run(body, DATA + "\nPROC Tick()\nnCount:=nCount-1;\nENDPROC")
    assert any(re.fullmatch(r"R\[\d+:FOR TO l\.\d+\]=R\[\d+(:nCount)?\]", line) for line in tp_lines(result))
    local = run("VAR num nLocal:=4;\nFOR i FROM 1 TO nLocal DO\nTick;\nENDFOR", DATA + "\nPROC Tick()\nnDone:=1;\nENDPROC")
    assert not any("FOR TO" in line for line in tp_lines(local))


def test_a_bound_tp_cannot_work_out_is_left_to_the_integrator():
    result = run("FOR i FROM 1 TO CellCount() DO\nnDone:=nDone+1;\nENDFOR\nnCount:=1;", DATA + "\n" + UNKNOWN)
    lines = tp_lines(result)
    (gate,) = result.gated
    assert gate.what == "FOR" and gate.slot.startswith("R[") and gate.rapid == "CellCount()"
    assert lines[0].startswith(f"!TODO l.{gate.line} FOR i FROM 1 TO")
    assert lines[1:3] == [f"!Replace JMP by {gate.slot}=(...)", f"JMP LBL[{gate.label}]"]
    assert re.fullmatch(rf"FOR R\[\d+:i\]=1 TO {re.escape(gate.slot)}", lines[3])
    assert lines[lines.index("ENDFOR") + 1] == f"LBL[{gate.label}]"
    (note,) = [n for n in result.notes if n.kind == "TODO"]
    assert "the FOR is written with its blocks, its bound left to set in" in note.message
    registers = json.loads(build_mapping(result, ConversionConfig()))["registers"]
    key = f"CROSSARM.CONDITION.MAIN.L{gate.line}"
    assert key in registers
    again = run("FOR i FROM 1 TO CellCount() DO\nnDone:=nDone+1;\nENDFOR", DATA + "\n" + UNKNOWN,
                ConversionConfig(registers={key: 150}))  # fmt: skip
    assert [g.slot for g in again.gated] == ["R[150]"]


SHAPES = [
    "FOR i FROM 1 TO CellCount() DO\nnDone:=nDone+1;\nENDFOR",
    "FOR i FROM CellCount() TO 5 DO\nnDone:=nDone+1;\nENDFOR",
    "FOR i FROM CellCount() TO CellCount()+2 DO\nnDone:=nDone+1;\nENDFOR",
    "FOR i FROM 1 TO CellCount() DO\nFOR j FROM 1 TO nCount-1 DO\nnDone:=nDone+1;\nENDFOR\nENDFOR",
    "FOR i FROM 1 TO nCount DO\nFOR j FROM 1 TO CellCount() DO\nnDone:=nDone+1;\nENDFOR\nENDFOR",
    "FOR i FROM 0 TO CellCount() STEP 2 DO\nnDone:=nDone+1;\nENDFOR",
    "FOR i FROM CellCount() TO 0 STEP -2 DO\nnDone:=nDone+1;\nENDFOR",
]


@pytest.mark.parametrize("body", SHAPES)
def test_with_the_jump_in_place_the_loop_does_not_turn(body):
    result = run(f"{body}\nWaitTime 0.5;", DATA + "\n" + UNKNOWN)
    assert result.gated
    lines = tp_lines(result)
    inside = {i for i, line in enumerate(lines) if re.match(r"R\[\d+:nDone\]=", line)}
    assert inside
    runs = reachable(lines, set())
    assert not runs & inside, [lines[i] for i in sorted(runs & inside)]
    assert any(lines[i].startswith("WAIT") for i in runs)  # the program goes on after it
    set_lines = list(lines)
    for i, line in enumerate(lines):
        if (m := re.fullmatch(r"!Replace JMP by (\S+)=\(\.\.\.\)", line)) is not None:
            assert lines[i + 1].startswith("JMP LBL[")
            set_lines[i + 1] = f"{m[1]}=3"
    assert reachable(set_lines, set()) & inside


def test_the_reports_list_the_bound_to_set():
    from crossarm.convert.analysis import priority_actions
    from crossarm.convert.checklist import checklist_section

    result = run("FOR i FROM 1 TO CellCount() DO\nnDone:=nDone+1;\nENDFOR", DATA + "\n" + UNKNOWN)
    action = next(a for a in priority_actions(result) if a.href == "#ck-conditions")
    assert action.todo == 1 and "FOR" in action.detail
    _, _, html = checklist_section(result, ConversionConfig(), set(), identity="t")
    assert "The bound is set where the instruction starts" in html
