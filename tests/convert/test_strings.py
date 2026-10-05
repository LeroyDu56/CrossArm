# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Strings kept in string registers (crossarm.convert.strings): what ROBOGUIDE takes, as measured."""

import json
from datetime import datetime

import pytest
from helpers import parse_module
from test_translate import run, todos, tp_lines

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.mapping import build_mapping
from crossarm.convert.report import build_report
from crossarm.convert.translate import Blocker

STATE = "VAR string sState;\nVAR num nRun;\n"
SET = 'PROC Set()\n  sState:="RUN";\nENDPROC'  # sState changed, upper case only


def program(result, name: str) -> list[str]:
    found = next(info.program for info in result.programs if info.program.name == name)
    return [getattr(line, "text", None) or f"{line.kind} {line.target}" for line in found.lines][1:]


def notes(result, kind: str) -> list[tuple[str, str]]:
    return [(n.category, n.message) for n in result.notes if n.kind == kind]


# -- a string the programs change is a string register -------------------------------------------


def test_a_text_is_loaded_into_the_string_register_by_the_program_loading_texts():
    result = run('sState:="IDLE";', STATE)
    assert tp_lines(result) == ["CALL CA_TEXT(1,'IDLE',0)"]
    assert program(result, "CA_TEXT") == [
        "!AR[3]=1: added at its end", "IF AR[3]=1,JMP LBL[1]", "SR[AR[1]]=AR[2]", "END", "LBL[1]",
        "SR[AR[1]]=SR[AR[1]]+AR[2]"]  # fmt: skip
    helper = next(p.program for p in result.programs if p.program.name == "CA_TEXT")
    assert helper.attributes.default_group == "*,*,*,*,*"  # a TRAP can call it
    assert [(a.number, a.rapid_name) for a in result.string_registers] == [(1, "sState")]


def test_no_program_loading_texts_without_a_text_to_load():
    result = run("sCopy:=sState;", "VAR string sState;\nVAR string sCopy;\nPROC other()\nsState:=sCopy;\nENDPROC")
    assert tp_lines(result) == ["SR[1]=SR[2]"]
    assert [p.program.name for p in result.programs] == ["MAIN"]


def test_a_text_longer_than_a_tp_argument_is_loaded_in_pieces_added_at_the_end():
    text = "A" * 38 + "B" * 38 + "C"  # 77 characters: RAPID strings hold 80
    assert tp_lines(run(f'sState:="{text}";', STATE)) == [
        f"CALL CA_TEXT(1,'{'A' * 38}',0)", f"CALL CA_TEXT(1,'{'B' * 38}',1)", "CALL CA_TEXT(1,'C',1)"]


def test_an_empty_text_is_one_character_then_none_from_past_it():
    """ROBOGUIDE stores CALL X(n,'',0) as '...', and stops on SUBSTR SR[n],1,0 (INTP-323)."""
    assert tp_lines(run('sState:="";', STATE)) == ["CALL CA_TEXT(1,'x',0)", "SR[1]=SUBSTR SR[1],2,0"]


def test_an_apostrophe_is_written_as_a_backquote_and_said_so():
    result = run('sState:="it\'s";', STATE)
    assert tp_lines(result) == ["CALL CA_TEXT(1,'it`s',0)"]
    why = "'it's' written with a backquote for each apostrophe: an apostrophe ends a TP text"
    assert notes(result, "WARNING") == [(Blocker.TEXT, why)]


@pytest.mark.parametrize("text", ['say "hi"', "a,b", "f(x)", "a;b"])
def test_quotes_commas_brackets_and_semicolons_pass_as_they_are(text):
    escaped = text.replace('"', '""')
    assert tp_lines(run(f'sState:="{escaped}";', STATE)) == [f"CALL CA_TEXT(1,'{text}',0)"]


def test_a_text_with_a_character_tp_has_not_stays_todo():
    result = run('sState:="señal";', STATE)
    assert [c for c, _ in notes(result, "TODO")] == [Blocker.TEXT]


def test_texts_are_put_together_in_the_register():
    data = STATE + "VAR string sPart;\nPROC other()\nsPart:=sState;\nENDPROC"
    assert tp_lines(run('sState:="P"+sPart+"-"+"OK";', data)) == [
        "CALL CA_TEXT(1,'P',0)", "SR[1]=SR[1]+SR[2]", "CALL CA_TEXT(1,'-OK',1)"]


def test_a_text_reading_itself_further_on_is_worked_out_apart_first():
    assert tp_lines(run('sState:="<"+sState;', STATE)) == [
        "CALL CA_TEXT(25,'<',0)", "SR[25]=SR[25]+SR[1]", "SR[1]=SR[25]"]


def test_a_string_no_program_changes_is_its_value():
    result = run('IF sMode="AUTO" nRun:=1;', 'VAR string sMode:="AUTO";\nVAR num nRun;')
    assert tp_lines(result) == ["!l.5 IF always TRUE: no test", "R[1:nRun]=1"]
    assert result.string_registers == []


# -- comparing texts ----------------------------------------------------------------------------------


def test_a_comparison_is_a_jump_on_two_string_registers():
    """ROBOGUIDE refuses IF (SR[a]=SR[b]) THEN and IF SR[a]='A',JMP: the text goes to a scratch register."""
    result = run('IF sState="RUN" THEN\n  nRun:=1;\nENDIF', STATE, extra_procs=SET)
    assert tp_lines(result) == [
        "CALL CA_TEXT(25,'RUN',0)", "IF SR[1]<>SR[25],JMP LBL[1]", "R[200:nRun]=1", "LBL[1]"]


def test_elseif_and_else_are_jumps_past_the_other_branches():
    body = 'IF sState="A" THEN\n  nRun:=1;\nELSEIF sState<>"B" THEN\n  nRun:=2;\nELSE\n  nRun:=3;\nENDIF'
    assert tp_lines(run(body, STATE, extra_procs=SET)) == [
        "CALL CA_TEXT(25,'A',0)", "IF SR[1]<>SR[25],JMP LBL[2]", "R[200:nRun]=1", "JMP LBL[1]", "LBL[2]",
        "CALL CA_TEXT(25,'B',0)", "IF SR[1]=SR[25],JMP LBL[3]", "R[200:nRun]=2", "JMP LBL[1]", "LBL[3]",
        "R[200:nRun]=3", "LBL[1]"]  # fmt: skip


def test_and_or_not_are_jumps_too():
    body = 'IF sState="A" AND NOT (nRun>2 OR sState="B") nRun:=1;'
    assert tp_lines(run(body, STATE, extra_procs=SET)) == [
        "CALL CA_TEXT(25,'A',0)", "IF SR[1]<>SR[25],JMP LBL[1]",
        "IF (R[200:nRun]>2),JMP LBL[1]", "CALL CA_TEXT(25,'B',0)", "IF SR[1]=SR[25],JMP LBL[1]",
        "R[200:nRun]=1", "LBL[1]"]  # fmt: skip


def test_a_while_on_a_text_tests_it_at_each_turn():
    assert tp_lines(run('WHILE sState<>"STOP" DO\n  nRun:=nRun+1;\nENDWHILE', STATE, extra_procs=SET)) == [
        "LBL[1]", "CALL CA_TEXT(25,'STOP',0)", "IF SR[1]=SR[25],JMP LBL[2]", "R[200:nRun]=R[200:nRun]+1",
        "JMP LBL[1]", "LBL[2]"]  # fmt: skip


def test_a_comparison_two_texts_could_pass_by_case_alone_stays_todo():
    """TP finds 'A' and 'a' equal (ROBOGUIDE), RAPID does not."""
    data = STATE + 'PROC other()\nsState:="run";\nENDPROC'
    found = notes(run('IF sState="RUN" nRun:=1;', data), "TODO")  # sState may be "run"
    assert found and found[0][0] == Blocker.CONDITION
    assert "regardless of case" in found[0][1]


def test_a_text_of_a_caller_compared_with_a_text_without_letters_is_converted():
    procs = 'PROC Check(string sCode)\n  IF sCode="42" nRun:=1;\n  IF sCode="OK" nRun:=2;\nENDPROC'
    source = f"MODULE M\nVAR num nRun;\nPROC main()\nCheck \"42\";\nENDPROC\n{procs}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert program(result, "CHECK")[:3] == ["CALL CA_TEXT(25,'42',0)", "IF SR[25]<>AR[1],JMP LBL[1]", "R[200:nRun]=1"]
    assert "regardless of case" in todos(result)[0]  # "OK": the caller's text may be "ok"


def test_texts_are_compared_with_equal_and_not_equal_only():
    assert todos(run('IF sState>"A" nRun:=1;', STATE, extra_procs=SET))[0].startswith("texts compared with '>'")


# -- working texts out ----------------------------------------------------------------------------------


def test_strlen_strpart_and_numtostr_of_a_whole_number():
    data = STATE + "VAR string sPart;\nVAR num nLen;\nVAR num nCount;\nPROC other()\nsState:=sPart;\nENDPROC"
    body = 'nCount:=nCount+1;\nnLen:=StrLen(sState);\nsPart:=StrPart(sState,2,nLen);\nsPart:=NumToStr(nCount,0);'
    assert tp_lines(run(body, data)) == [
        "R[1:nCount]=R[1:nCount]+1", "R[200:nLen]=STRLEN SR[1]", "SR[2]=SUBSTR SR[1],2,R[200:nLen]",
        "SR[2]=R[1:nCount]"]  # fmt: skip


def test_numtostr_of_a_number_ever_given_a_fraction_stays_todo():
    """ROBOGUIDE writes SR=R of 2.5+.5 as '3.000000', RAPID NumToStr(3,0) as '3'."""
    data = STATE + "VAR num nHalf;\nPROC other()\nnHalf:=nHalf/2;\nENDPROC"
    found = todos(run("sState:=NumToStr(nHalf,0);", data))  # nHalf may hold 2.5
    assert "six decimals" in found[0]
    assert "with decimals" in todos(run("sState:=NumToStr(nRun,2);", STATE))[0]


def test_strmatch_from_the_first_character_is_findstr_with_rapid_s_not_found():
    data = STATE + "VAR num nAt;\nPROC other()\nsState:=\"RUN\";\nENDPROC"
    assert tp_lines(run('nAt:=StrMatch(sState,1,"UN");', data)) == [
        "CALL CA_TEXT(25,'UN',0)", "R[199:Calc1]=FINDSTR SR[1],SR[25]", "IF R[199:Calc1]<>0,JMP LBL[1]",
        "R[199:Calc1]=STRLEN SR[1]", "R[199:Calc1]=R[199:Calc1]+1", "LBL[1]", "R[200:nAt]=R[199:Calc1]"]  # fmt: skip
    assert "from the first only" in todos(run('nAt:=StrMatch(sState,2,"UN");', data))[0]


def test_strlen_in_a_condition_is_worked_out_on_a_line_of_its_own():
    assert tp_lines(run('IF StrLen(sState)>80 nRun:=1;', STATE, extra_procs=SET))[:2] == [
        "R[200:Calc1]=STRLEN SR[1]", "IF (R[200:Calc1]>80) THEN"]


@pytest.mark.parametrize(("call", "why"), [
    ("bOk:=StrToVal(sState,nRun);", "StrToVal: TP reads a text as a number"),
    ('nRun:=StrFind(sState,1,"AB");', "StrFind: it looks for a character of a set"),
    ('bOk:=StrMemb(sState,1,"AB");', "StrMemb: TP has no test"),
])  # fmt: skip
def test_text_functions_tp_does_otherwise_stay_todo_with_why(call, why):
    assert todos(run(call, STATE + "VAR bool bOk;"))[0].startswith(why)


# -- texts in calls, local strings, TRAPs ---------------------------------------------------------------


def test_a_string_the_programs_change_is_passed_in_its_register():
    procs = "PROC Show(string sText)\n  nRun:=StrLen(sText);\nENDPROC"
    source = f'MODULE M\n{STATE}PROC main()\nsState:="A";\nShow sState;\nShow "B";\nENDPROC\n{procs}\nENDMODULE\n'
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert program(result, "MAIN") == ["CALL CA_TEXT(1,'A',0)", "CALL SHOW(SR[1])", "CALL SHOW('B')"]
    assert program(result, "SHOW") == ["R[200:nRun]=STRLEN AR[1]"]


def test_a_string_of_the_routine_is_set_where_it_starts():
    result = run('VAR string sLocal:="X";\nsLocal:=sLocal+"Y";\nIF sLocal="XY" nRun:=1;', "VAR num nRun;")
    assert tp_lines(result)[:3] == ["CALL CA_TEXT(1,'X',0)", "CALL CA_TEXT(1,'Y',1)", "CALL CA_TEXT(25,'XY',0)"]
    assert [a.key for a in result.string_registers] == ["MAIN.sLocal", "CROSSARM.TEXT"]
    assert any("every call of the routine shares it" in m for _, m in notes(result, "WARNING"))


def test_a_string_of_a_routine_calling_itself_back_stays_todo():
    procs = 'PROC Again()\n  VAR string sLocal;\n  sLocal:="X";\n  Again;\nENDPROC'
    source = f"MODULE M\nPROC main()\nAgain;\nENDPROC\n{procs}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert any("calling itself back" in t for t in todos(result))


TRAP = """VAR intnum iStop;
VAR string sLast;
VAR num nRun;
PROC main()
  CONNECT iStop WITH tStop;
  ISignalDI diStop,1,iStop;
  IF sLast="STOP" nRun:=1;
ENDPROC
TRAP tStop
  sLast:="STOP";
  IF sLast="STOP" nRun:=2;
ENDTRAP
"""


def test_a_trap_loads_its_texts_into_scratch_registers_of_its_own():
    source = f"MODULE M\n{TRAP}ENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert "CALL CA_TEXT(25,'STOP',0)" in program(result, "MAIN")
    assert program(result, "TSTOP")[:3] == ["CALL CA_TEXT(1,'STOP',0)", "CALL CA_TEXT(24,'STOP',0)",
                                            "IF SR[1]<>SR[24],JMP LBL[1]"]  # fmt: skip
    assert any("what the TRAPs run loads its texts into SR[24]" in m for _, m in notes(result, "WARNING"))


def test_a_routine_run_by_a_trap_and_by_the_programs_loads_no_text():
    source = TRAP.replace('  sLast:="STOP";\n', "  Note;\n").replace("  IF sLast=\"STOP\" nRun:=1;\n", "  Note;\n")
    source = f'MODULE M\n{source}PROC Note()\n  sLast:="SEEN";\nENDPROC\nENDMODULE\n'
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert any("run by a TRAP and by the programs" in t for t in todos(result))


# -- numbering ------------------------------------------------------------------------------------------


def test_string_registers_are_in_the_mapping_file_and_given_back_give_the_same_numbers(tmp_path):
    result = run('sState:="A";\nIF sState="B" nRun:=1;', STATE)  # sState: "A" or "B", no case to tell
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    mapping = json.loads(build_mapping(result, config))
    assert mapping["string_registers"] == {"sState": 1, "CROSSARM.TEXT": 25}
    assert "_string_registers" in mapping and mapping["limits"]["SR"] == 25
    mapping["string_registers"] = {"sState": 7, "CROSSARM.TEXT": 20}
    path = tmp_path / "map.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    again = run('sState:="A";\nIF sState="B" nRun:=1;', STATE, ConversionConfig.from_mapping_file(path))
    assert tp_lines(again)[:2] == ["CALL CA_TEXT(7,'A',0)", "CALL CA_TEXT(20,'B',0)"]


def test_a_mapping_without_strings_has_no_string_register_limit():
    mapping = json.loads(build_mapping(run("nRun:=1;", STATE), ConversionConfig()))
    assert "SR" not in mapping["limits"] and "string_registers" not in mapping


def test_string_registers_the_robot_uses_are_left_free():
    config = ConversionConfig(timestamp=datetime(2026, 1, 1), reserved={"SR": {1: ("PNS0001",), 25: ("PNS0001",)}})
    assert tp_lines(run('IF sState="B" nRun:=1;\nsState:="A";', STATE, config))[:2] == [
        "CALL CA_TEXT(24,'B',0)", "IF SR[2]<>SR[24],JMP LBL[1]"]


def test_past_the_string_registers_of_the_controller_the_strings_are_todo_and_listed():
    data = "".join(f"VAR string s{k};\n" for k in range(26))
    result = run("".join(f's{k}:="A";\n' for k in range(26)), data)
    found = notes(result, "TODO")
    assert [c for c, _ in found] == [Blocker.CAPACITY] * 2
    assert found[1][1].startswith("1 string(s) without a string register, the controller has 25 (SR[1] to SR[25])"
                                  ": s25.")  # fmt: skip


def test_a_program_without_texts_keeps_its_numbers_when_another_one_works_texts_out():
    """What only a statement converted with texts numbers first is numbered from the top, after the others."""
    procs = "PROC Later()\n  nB:=nB+1;\nENDPROC"
    data = STATE + "VAR num nA;\nVAR num nB;\n"
    source = f"MODULE M\n{data}PROC main()\nnA:=StrLen(sState);\nnB:=1;\nENDPROC\n{procs}\n{SET}\nENDMODULE\n"
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert program(result, "MAIN") == ["R[200:nA]=STRLEN SR[1]", "R[1:nB]=1"]
    assert program(result, "LATER") == ["R[1:nB]=R[1:nB]+1"]


def test_the_report_tells_how_texts_are_kept():
    result = run('sState:="A";', STATE)
    report = build_report(result, ConversionConfig(), ["M.mod"])
    assert "### Texts in string registers" in report and "| SR[1] | sState |" in report


def test_a_text_field_of_a_record_parameter_is_its_argument():
    procs = 'RECORD part\n  string name;\n  num n;\nENDRECORD\nPROC Load(part p)\n  IF p.name="42" nRun:=1;\nENDPROC'
    source = f'MODULE M\nVAR num nRun;\n{procs}\nPROC main()\nLoad ["42",1];\nENDPROC\nENDMODULE\n'
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    assert program(result, "LOAD")[:2] == ["CALL CA_TEXT(25,'42',0)", "IF SR[25]<>AR[1],JMP LBL[1]"]


def test_numtostr_of_a_group_input_read_is_its_digits():
    data = STATE + "VAR num nCode;\nVAR signalgi giCode;\n"
    assert tp_lines(run("nCode:=GInput(giCode);\nsState:=NumToStr(nCode,0);", data))[-1] == "SR[1]=R[1:nCode]"
