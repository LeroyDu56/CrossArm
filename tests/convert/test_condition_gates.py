# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A condition CrossArm cannot convert no longer takes its blocks with it (crossarm.convert.condition_gates): the
blocks are converted, the condition is left to the integrator in a reserved flag, and until the integrator writes it
nothing of the instruction runs."""

import json
import re

import pytest
from test_translate import HOME, TOOL, run, todos, tp_lines

from crossarm.convert import ConversionConfig
from crossarm.convert.blockers import Blocker
from crossarm.convert.mapping import build_mapping

DATA = HOME + TOOL + "VAR num nCount:=0;\nVAR num nMode:=0;\nVAR string sName:=\"\";"


def test_an_if_keeps_its_blocks_and_leaves_its_condition_in_a_flag():
    result = run("IF OpMode()=OP_AUTO THEN\nMoveL pHome,v100,fine,tGrip;\nELSE\nStop;\nENDIF", DATA)
    assert tp_lines(result) == [
        "!TODO l.6 IF OpMode()=OP_AUTO THE", "!Replace JMP by F[1]=(...)", "JMP LBL[1]",
        "IF (F[1]=ON) THEN", "UFRAME_NUM=0", "UTOOL_NUM=1", "L P[1] 100mm/sec FINE", "ELSE", "PAUSE", "ENDIF",
        "LBL[1]"]  # fmt: skip
    (note,) = [n for n in result.notes if n.kind == "TODO"]
    assert note.category == Blocker.NO_TP_EQUIVALENT and note.message.startswith("OpMode: the operating mode")
    assert "the IF is written with its blocks, its condition left to set in F[1]" in note.message
    (gate,) = result.gated
    assert (gate.slot, gate.rapid, gate.label, gate.line) == ("F[1]", "OpMode() = OP_AUTO", 1, 6)
    assert result.coverage.converted == 2 and result.coverage.total == 3  # the IF alone is not converted


def test_an_elseif_condition_is_set_before_the_if_and_skips_every_branch():
    result = run("IF nMode>1 THEN\nnCount:=1;\nELSEIF OpMode()=OP_AUTO THEN\nnCount:=2;\nELSE\nnCount:=3;\nENDIF", DATA)
    lines = tp_lines(result)
    assert lines[:3] == ["!TODO l.8 ELSEIF OpMode()=OP_AUTO", "!Replace JMP by F[1]=(...)", "JMP LBL[1]"]
    assert "IF (F[1]=ON) THEN" in lines and lines[-1] == "LBL[1]"


def test_a_while_does_not_turn_until_its_condition_is_set():
    result = run("WHILE OpMode()<>OP_AUTO DO\nWaitTime 1;\nENDWHILE\nnCount:=1;", DATA)
    assert tp_lines(result)[:9] == [
        "LBL[1]", "!TODO l.6 WHILE OpMode()<>OP_AUTO", "!Replace JMP by F[1]=(...)", "JMP LBL[2]",
        "IF (F[1]=OFF) THEN", "JMP LBL[2]", "ENDIF", "WAIT   1.00(sec)", "JMP LBL[1]"]  # fmt: skip


def test_a_test_on_a_value_not_convertible_selects_on_a_reserved_register():
    result = run("TEST StrLen(sName)\nCASE 1:\nnCount:=1;\nCASE 2:\nnCount:=2;\nENDTEST", DATA)
    lines = tp_lines(result)
    (gate,) = result.gated
    assert lines[1] == f"!Replace JMP by {gate.slot}=(...)" and lines[2] == f"JMP LBL[{gate.label}]"
    assert gate.slot.startswith("R[") and any(line.startswith(f"SELECT {gate.slot}=1,") for line in lines)
    assert lines[-1] == f"LBL[{gate.label}]"


def test_the_flag_has_an_added_mapping_key_and_comes_back_the_same():
    body = "IF OpMode()=OP_AUTO THEN\nnCount:=1;\nENDIF\nIF nMode=0 AND OpMode()=OP_AUTO nCount:=2;"
    result = run(body, DATA)
    flags = json.loads(build_mapping(result, ConversionConfig()))["flags"]
    assert flags == {"CROSSARM.CONDITION.MAIN.L6": 1, "CROSSARM.CONDITION.MAIN.L9": 2}
    again = run(body, DATA, ConversionConfig(flags={"CROSSARM.CONDITION.MAIN.L6": 30, "CROSSARM.CONDITION.MAIN.L9": 31}))
    assert [g.slot for g in again.gated] == ["F[30]", "F[31]"]


def test_an_if_in_a_gated_block_converts_on_its_own():
    result = run("IF OpMode()=OP_AUTO THEN\nIF nMode>0 nCount:=1;\nENDIF", DATA)
    assert len(result.gated) == 1  # the outer one; the inner IF converts


def test_a_body_statement_that_cannot_convert_is_its_own_todo():
    result = run("IF OpMode()=OP_AUTO THEN\nnCount:=StrLen(sName)*Unknown();\nnCount:=2;\nENDIF", DATA)
    assert len(todos(result)) == 2 and "R[1:nCount]=2" in tp_lines(result)


# ---------------------------------------------------------------------------
# Safety: with the flags as they are (OFF) and the jumps in place, nothing of the instruction runs
# ---------------------------------------------------------------------------

_IF = re.compile(r"IF \((.*)\) THEN$")
_JMP_IF = re.compile(r"IF .*,JMP LBL\[(\d+)\]$")
_LABEL = re.compile(r"(?:JMP )?LBL\[(\d+)\]")


def reachable(lines: list[str], off: set[str]) -> set[int]:
    """Indices of the lines a run can reach, every condition taken both ways except a flag of `off` alone in its
    IF (taken as OFF)."""
    labels = {int(m[1]): i for i, line in enumerate(lines) if (m := re.fullmatch(r"LBL\[(\d+)\]", line))}

    def block_end(i: int) -> tuple[int | None, int]:  # (ELSE, ENDIF) of the IF ... THEN at i
        depth, other = 0, None
        for j in range(i + 1, len(lines)):
            if _IF.match(lines[j]):
                depth += 1
            elif lines[j] == "ENDIF":
                if depth == 0:
                    return other, j
                depth -= 1
            elif lines[j] == "ELSE" and depth == 0:
                other = j
        raise AssertionError("no ENDIF")

    def after_else(i: int) -> int:  # the ENDIF closing the ELSE at i
        depth = 0
        for j in range(i + 1, len(lines)):
            if _IF.match(lines[j]):
                depth += 1
            elif lines[j] == "ENDIF":
                if depth == 0:
                    return j
                depth -= 1
        raise AssertionError("no ENDIF")

    seen: set[int] = set()
    todo = [0]
    while todo:
        i = todo.pop()
        if i >= len(lines) or i in seen:
            continue
        seen.add(i)
        line = lines[i]
        if (m := _IF.match(line)) is not None:
            other, end = block_end(i)
            flag = re.fullmatch(r"(F\[\d+\])=(ON|OFF)", m[1])
            truth = None if flag is None or flag[1] not in off else flag[2] == "OFF"
            if truth in (None, True):
                todo.append(i + 1)
            if truth in (None, False):
                todo.append(other + 1 if other is not None else end + 1)
        elif line == "ELSE":
            todo.append(after_else(i) + 1)
        elif line.startswith("JMP LBL["):
            todo.append(labels[int(_LABEL.match(line)[1])])  # type: ignore[index]
        elif (m := _JMP_IF.match(line)) is not None or line.lstrip().startswith(("SELECT ", "=", "ELSE,")):
            if (m := re.search(r"JMP LBL\[(\d+)\]", line)) is not None:
                todo.append(labels[int(m[1])])
            todo.append(i + 1)
        elif line in ("END", "ABORT"):
            continue
        else:
            todo.append(i + 1)
    return seen


SHAPES = [
    "IF OpMode()=OP_AUTO THEN\nMoveL pHome,v100,fine,tGrip;\nELSE\nStop;\nENDIF",
    "IF nMode>1 THEN\nnCount:=1;\nELSEIF OpMode()=OP_AUTO THEN\nnCount:=2;\nELSE\nnCount:=3;\nENDIF",
    ("IF OpMode()=OP_AUTO THEN\nnCount:=1;\nELSEIF nMode>1 THEN\nnCount:=2;\nELSEIF OpMode()=OP_T1 THEN\n"
     "nCount:=3;\nELSE\nnCount:=4;\nENDIF"),
    "WHILE OpMode()<>OP_AUTO DO\nnCount:=nCount+1;\nENDWHILE",
    "IF sName=\"A\" THEN\nnCount:=1;\nELSEIF OpMode()=OP_AUTO THEN\nnCount:=2;\nELSE\nnCount:=3;\nENDIF",
    "WHILE sName<>\"A\" AND OpMode()<>OP_AUTO DO\nnCount:=nCount+1;\nENDWHILE",
    "TEST StrLen(sName)\nCASE 1:\nnCount:=1;\nCASE 2:\nnCount:=2;\nDEFAULT:\nnCount:=3;\nENDTEST",
    "IF nMode>0 THEN\nIF OpMode()=OP_AUTO THEN\nnCount:=1;\nELSE\nnCount:=2;\nENDIF\nENDIF",
    "IF OpMode()=OP_AUTO Stop;",
]


@pytest.mark.parametrize("body", SHAPES)
def test_with_the_jumps_in_place_no_block_of_the_instruction_runs(body):
    result = run(f"{body}\nWaitTime 0.5;", DATA)
    assert result.gated
    lines = tp_lines(result)
    inside = {i for i, line in enumerate(lines) if line in ("PAUSE", "L P[1] 100mm/sec FINE")
              or re.match(r"R\[\d+(:[^\]]*)?\]=", line)}  # what the blocks do  # fmt: skip
    assert inside
    flags = {g.slot for g in result.gated}
    runs = reachable(lines, flags)
    assert not runs & inside, [lines[i] for i in sorted(runs & inside)]
    assert any(lines[i].startswith("WAIT") for i in runs)  # and the program goes on after it
    # Each jump replaced by the line setting its flag, as the remark before it says: the blocks run.
    set_lines = list(lines)
    for i, line in enumerate(lines):
        if (m := re.fullmatch(r"!Replace JMP by (\S+)=\(\.\.\.\)", line)) is not None:
            assert lines[i + 1].startswith("JMP LBL[")
            set_lines[i + 1] = f"{m[1]}=(ON)" if m[1].startswith("F") else f"{m[1]}=1"
    assert reachable(set_lines, set()) & inside


def test_the_reports_list_each_condition_to_set():
    from crossarm.convert.analysis import priority_actions
    from crossarm.convert.checklist import checklist_section

    result = run("IF OpMode()=OP_AUTO THEN\nnCount:=1;\nENDIF\nWHILE OpMode()<>OP_T1 DO\nnCount:=2;\nENDWHILE", DATA)
    action = next(a for a in priority_actions(result) if a.href == "#ck-conditions")
    assert action.title == "Set the 2 conditions CrossArm could not convert" and action.todo == 2
    assert action.who == ("FANUC integrator",)
    _, _, html = checklist_section(result, ConversionConfig(), set(), identity="t")
    assert 'id="ck-conditions"' in html and "MAIN.LS: set <code>F[1]</code> to <code>OpMode() = OP_AUTO</code>" in html
    assert "Replace <code>JMP LBL[1]</code> by <code>F[1]=(...)</code>" in html
    assert "Reserved by CrossArm: a condition" in html  # in the flags of the registers group
