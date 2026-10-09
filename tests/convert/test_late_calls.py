# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A routine called by a name worked out at run time (%name%, CallByVar): a call to each routine it can name."""

from test_translate import run, todos, tp_lines

from crossarm.convert.late_calls import parse_late_call
from crossarm.diagnostics import Span

BAYS = "\n".join(f'PROC Bay_{i}()\n  TPWrite "bay {i}";\nENDPROC' for i in (1, 2, 3))
OTHERS = 'PROC Rinse()\n  TPWrite "r";\nENDPROC\nPROC Purge()\n  TPWrite "p";\nENDPROC'
DATA = "VAR num nBay;\nPERS num nCell:=0;"


def warnings(result) -> list[str]:
    return [n.message for n in result.notes if n.kind == "WARNING" and n.category == "RAPID late binding"]


def test_the_name_and_arguments_read():
    name, args = parse_late_call('%"Bay_" + NumToStr(nBay,0)% 3, "100%";', Span(4, 0))
    assert name.span.line == 4 and len(args) == 2 and args[1].value.value == "100%"
    assert parse_late_call("%sName", Span(1, 0)) is None


def test_a_prefix_and_a_number_set_at_run_time_call_each_routine_that_fits():
    for body in ('nBay:=nCell DIV 10;\n%"Bay_"+NumToStr(nBay,0)%;', 'nBay:=nCell DIV 10;\nCallByVar "Bay_",nBay;'):
        result = run(body, DATA, extra_procs=BAYS)
        assert not todos(result)
        assert tp_lines(result)[1:] == ["SELECT R[1:nBay]=1,CALL BAY_1", "       =2,CALL BAY_2", "       =3,CALL BAY_3",
                                        "       ELSE,JMP LBL[2]", "JMP LBL[1]", "LBL[2]", "ABORT", "LBL[1]"]  # fmt: skip
        (warning,) = warnings(result)
        assert "Bay_1, Bay_2, Bay_3" in warning and "ERR_REFUNKPRC" in warning and "ABORT" in warning


def test_a_number_of_known_values_needs_no_other_branch():
    result = run('FOR i FROM 1 TO 2 DO\n  %"Bay_"+NumToStr(i,0)%;\nENDFOR', DATA, extra_procs=BAYS)
    assert tp_lines(result) == ["FOR R[1:i]=1 TO 2", "SELECT R[1:i]=1,CALL BAY_1", "       =2,CALL BAY_2", "ENDFOR"]
    assert "ERR_REFUNKPRC" not in warnings(result)[0]


def test_a_text_set_to_names_compares_the_text():
    data = 'VAR string sStep:="Rinse";'
    result = run('%sStep%;\nsStep:="Purge";', data, extra_procs=OTHERS)
    assert not todos(result)
    lines = tp_lines(result)
    assert "CALL RINSE" in lines and "CALL PURGE" in lines and "ABORT" not in lines
    assert any(line.startswith("IF SR[") and ",JMP LBL[" in line for line in lines)
    assert "%'Purge'%" not in lines and tp_lines(run('%"Purge"%;', extra_procs=OTHERS)) == ["CALL PURGE"]


def test_what_cannot_be_told_says_why():
    assert "no PROC of the backup is named Cell_<number>" in todos(run('%"Cell_"+NumToStr(nCell,0)%;', DATA, extra_procs=BAYS))[0]
    assert "not a PROC of the backup" in todos(run('VAR string s:="Drain";\n%s%;', extra_procs=OTHERS))[0]
    assert "must be a constant text" in todos(run('%StrPart("Rinse",1,3)%;', extra_procs=OTHERS))[0]
