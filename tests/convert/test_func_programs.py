# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""FUNCs of the backup whose value is only known at run time, written as TP programs (crossarm.convert.func_programs):
`CALL F(args,k)` just before the line reading the value, the FUNC's program writing it in R[AR[last]] / PR[AR[last]]."""

import json
from datetime import datetime

from helpers import parse_module

from crossarm.convert import ConversionConfig, build_mapping, convert
from crossarm.convert.blockers import Blocker

EXTAX = "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]"
DATA = f"""    CONST robtarget pOrigin:=[[600,-100,400],[0,0,1,0],[0,0,0,0],{EXTAX}];
    PERS tooldata tGrip:=[TRUE,[[0,0,100],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    VAR num nCount:=0;
    VAR num nGap:=0;
    VAR bool bFree:=FALSE;
    VAR robtarget pCell;
"""
FUNCS = """    FUNC robtarget Cell(num row,num col)
        VAR robtarget p;
        p:=pOrigin;
        p.trans.x:=pOrigin.trans.x+col*50;
        p.trans.y:=pOrigin.trans.y+row*40;
        RETURN p;
    ENDFUNC
    FUNC bool Free(num row)
        IF row>nCount THEN
            RETURN TRUE;
        ENDIF
        RETURN FALSE;
    ENDFUNC
    FUNC num Gap(num n)
        nCount:=nCount+1;
        RETURN n*2+nCount;
    ENDFUNC
"""


def run(body: str, funcs: str = FUNCS, data: str = DATA, karel: bool = False):
    source = f"MODULE M\n{data}    PROC main()\n{body}\n    ENDPROC\n{funcs}ENDMODULE\n"
    return convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1), karel=karel),
                   sources={"M": source})  # fmt: skip


def lines(result, program: str = "MAIN") -> list[str]:
    info = next(i for i in result.programs if i.program.name == program)
    return [getattr(line, "text", None) or f"{line.kind} {line.target}" for line in info.program.lines[1:]]


def todos(result) -> list:
    return [n for n in result.notes if n.kind == "TODO"]


LOOP = "        FOR r FROM 1 TO 3 DO\n{}\n        ENDFOR"


def test_a_robtarget_func_is_called_and_its_register_read_back():
    result = run(LOOP.format("            pCell:=Cell(r,2);\n            MoveL pCell,v100,fine,tGrip;"))
    assert not todos(result)
    main = lines(result)
    call = next(text for text in main if text.startswith("CALL CELL("))
    k = call.split(",")[-1].rstrip(")")
    assert call.startswith("CALL CELL(R[1:r],2,") and f"PR[{k}]" in " ".join(main)
    cell = lines(result, "CELL")
    assert cell[-1].startswith("PR[AR[3]]=PR[") and cell[0].endswith("=P[1]")  # a copy of pOrigin, then x, y
    assert {i.program.name for i in result.programs} == {"MAIN", "CELL"}  # only what is called


def test_a_bool_func_in_conditions_and_a_num_func_in_a_calculation():
    body = LOOP.format("            IF Free(r) THEN\n                nGap:=nGap+Gap(r)*3;\n"
                       "            ELSEIF Gap(r)>4 THEN\n                bFree:=Free(r+1);\n            ENDIF")
    result = run(body)
    assert not todos(result)
    main = lines(result)
    assert main[1:3] == ["CALL FREE(R[1:r],2)", "IF (R[2:result]=1) THEN"]
    assert main[3].startswith("CALL GAP(R[1:r],")  # before the scratch register is worked out
    assert main.index("ELSE") < next(i for i, t in enumerate(main) if i > 3 and t.startswith("CALL GAP("))  # ELSEIF: inside ELSE
    assert lines(result, "FREE") == ["IF (AR[1]>R[7:nCount]) THEN", "R[AR[2]]=1", "END", "ENDIF", "R[AR[2]]=0"]
    assert lines(result, "GAP")[-1].startswith("R[AR[2]]=")


def test_a_func_in_a_while_test_is_called_before_each_test():
    result = run("        WHILE NOT Free(nCount) DO\n            nCount:=nCount+1;\n        ENDWHILE")
    main = lines(result)
    assert main[:3] == ["LBL[1]", "CALL FREE(R[2:nCount],1)", "IF (R[1:result]=1) THEN"]


def test_a_func_whose_body_does_not_convert_leaves_its_calls_todo_and_says_why():
    funcs = FUNCS + """    FUNC num Ask()
        VAR num n;
        n:=UINumEntry(\\Header:="Rows"\\Message:="How many?");
        RETURN n;
    ENDFUNC
"""
    result = run("        nGap:=Ask();", funcs)
    (todo,) = todos(result)
    assert todo.program == "MAIN" and "Ask() is written as a program only when its whole body converts" in todo.message
    assert "UINumEntry" in todo.message and {i.program.name for i in result.programs} == {"MAIN"}


def test_a_func_a_wait_reads_or_calling_itself_stays_todo():
    funcs = FUNCS + "    FUNC num Fact(num n)\n        IF n<=1 RETURN 1;\n        RETURN n*Fact(n-1);\n    ENDFUNC\n"
    result = run("        WaitUntil Free(nCount);\n        nGap:=Fact(nCount);", funcs)
    first, second = todos(result)
    assert "not in a wait the controller reads again and again" in first.message
    assert "Fact() is not written as a program: it calls itself back" in second.message
    assert second.category == Blocker.CALL_ARGS


def test_a_func_known_at_conversion_time_is_still_worked_out():
    result = run("        pCell:=Cell(1,2);\n        MoveL pCell,v100,fine,tGrip;\n        nGap:=Gap(2);")
    assert all(not text.startswith("CALL CELL") for text in lines(result))
    assert "CALL GAP(2,2)" in lines(result)


def test_the_mapping_names_the_func_programs():
    result = run(LOOP.format("            nGap:=Gap(r);"))
    mapping = json.loads(build_mapping(result, ConversionConfig()))
    assert mapping["programs"]["Gap"] == "GAP"
    assert not any(s[1] == "Gap" for s in result.skipped_routines)


def test_the_reports_name_the_func_programs_and_those_left_todo():
    from crossarm.convert import analysis
    from crossarm.convert.html_report import build_html_report

    funcs = FUNCS + """    FUNC num Ask()
        VAR num n;
        n:=UINumEntry(\\Header:="Rows"\\Message:="How many?");
        RETURN n;
    ENDFUNC
"""
    result = run("        nGap:=Gap(2);\n        nGap:=Ask();", funcs)
    assert result.func_calls == {"Gap": [("MAIN", 9)]}
    assert "`Gap()` as `GAP` (1 call)" in analysis.func_programs_use(result)
    action = next(a for a in analysis.priority_actions(result) if "not written as TP programs" in a.title)
    assert action.todo == 1 and "`Ask()` (1 TODO)" in action.detail
    page = build_html_report(result, ConversionConfig(), ["m.mod"], title="t")
    assert "1 FUNC program call" in page and "CALL GAP</code>" in page and "1 FUNC of the backup written" in page


TEXT_FUNCS = FUNCS + """    FUNC string Padded(string text,num width,\\string Fill)
        VAR string out;
        VAR string pad:=" ";
        IF Present(Fill) pad:=Fill;
        out:=text;
        FOR i FROM StrLen(text) TO width-1 DO
            out:=pad+out;
        ENDFOR
        RETURN out;
    ENDFUNC
    FUNC string Joined(string a,string b)
        RETURN a+"-"+b;
    ENDFUNC
"""
TEXT_DATA = DATA + "    VAR string sCode;\n    VAR string sTag;\n"


def test_a_text_func_writes_its_result_in_the_string_register_the_caller_names():
    body = LOOP.format('            sCode:=Padded(NumToStr(r,0),4\\Fill:="0");\n'
                       '            IF sCode="0002" nCount:=nCount+1;')
    result = run(body, TEXT_FUNCS, TEXT_DATA)
    assert not todos(result)
    main = lines(result)
    call = next(text for text in main if text.startswith("CALL PADDED("))
    k = call.rstrip(")").split(",")[-1]
    assert call.startswith("CALL PADDED(SR[") and ",4,1,'0'," in call
    assert main[main.index(call) + 1].endswith(f"=SR[{k}]")  # read back by the caller
    assert lines(result, "PADDED")[-1].startswith("SR[AR[5]]=SR[")  # the result, last argument


def test_text_funcs_put_together_and_given_to_a_text_func():
    result = run('        sTag:="#"+Padded(sCode,3)+Joined(sCode,"9");\n        sTag:=Joined(Joined(sTag,sCode),sCode);',
                 TEXT_FUNCS, TEXT_DATA)  # fmt: skip
    assert not todos(result)
    main = lines(result)
    assert [t.split("(")[0] for t in main if t.startswith("CALL ") and "CA_TEXT" not in t] == [
        "CALL PADDED", "CALL JOINED", "CALL JOINED", "CALL JOINED"]  # fmt: skip
    first_join = next(i for i, t in enumerate(main) if t.startswith("CALL JOINED"))
    assert first_join < main.index("CALL CA_TEXT(1,'#',0)")  # both FUNCs called before the text is put together
    assert main[-2:] == ["CALL JOINED(SR[3],SR[25],3)", "SR[1]=SR[3]"]  # inner result given to the outer call
    assert lines(result, "JOINED")[-1] == "SR[AR[3]]=SR[25]"


def test_a_text_func_compared_is_called_before_the_other_side_is_worked_out():
    result = run('        IF sCode+"1"=Joined(sCode,"2") nCount:=1;', TEXT_FUNCS, TEXT_DATA)
    assert not todos(result)
    main = lines(result)
    call = next(i for i, t in enumerate(main) if t.startswith("CALL JOINED("))
    other = next(i for i, t in enumerate(main) if t.startswith("CALL CA_TEXT(") and ",'1'," in t)
    assert call < other < next(i for i, t in enumerate(main) if t.startswith("IF SR["))


def test_a_text_func_after_a_text_worked_out_in_a_scratch_register_stays_todo():
    procs = "    PROC Show(string a,string b)\n        nCount:=StrLen(a)+StrLen(b);\n    ENDPROC\n"
    result = run('        Show sCode+"1",Joined(sCode,"2");', TEXT_FUNCS + procs, TEXT_DATA)
    (todo,) = todos(result)
    assert todo.category == Blocker.TEXT and "scratch string register its program may use too" in todo.message


def test_a_text_func_result_holds_the_characters_its_returns_and_arguments_can():
    """TP compares texts regardless of case: a FUNC's text compared is converted when what it can give back (its
    RETURNs, its parameters as the call gives them) cannot differ by case alone from the other side."""
    padded = run('        IF Padded(NumToStr(nCount,0),4\\Fill:="0")="AB12" nGap:=1;', TEXT_FUNCS, TEXT_DATA)
    assert not todos(padded)
    joined = run('        IF Joined(sCode,"x")="X-1" nGap:=1;', TEXT_FUNCS, TEXT_DATA)
    assert [n.category for n in todos(joined)] == [Blocker.CONDITION]  # 'x' and 'X'
