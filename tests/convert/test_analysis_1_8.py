# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The analysis says what --karel did on the run (which KAREL programs, called from where, how often), and points
at the FUNCs copied into their calls and the frames kept in position registers past the controller's limit."""

from datetime import datetime
from pathlib import Path

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.analysis import analysis_markdown, karel_use, priority_actions
from crossarm.convert.blockers import Blocker
from crossarm.convert.translate import ConversionResult, Note
from crossarm.fanuc import ktrans
from crossarm.karel import calls
from crossarm.rapid import parse_text

STAMP = datetime(2026, 1, 1)
DOWN = "[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]"
POSES = f"""MODULE KP
  PERS tooldata tPen:=[TRUE,[[10,0,120],[1,0,0,0]],[2,[0,0,40],[1,0,0,0],0,0,0]];
  PERS wobjdata wPlate:=[FALSE,TRUE,"",[[600,200,500],[1,0,0,0]],[[15,0,0],[1,0,0,0]]];
  CONST robtarget pA:=[[900,-100,500],{DOWN}];
  CONST robtarget pIn:=[[50,20,0],{DOWN}];
  VAR robtarget pM1;
  PROC Main()
    MoveL pA,v200,fine,tool0;
    pM1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);
    wPlate.uframe.trans:=pM1.trans;
    MoveL pIn,v200,fine,tPen\\WObj:=wPlate;
  ENDPROC
ENDMODULE
"""


def _convert(text: str, **config) -> ConversionResult:
    parsed = parse_text(text, path="x.mod")
    assert parsed.module is not None, parsed.diagnostics
    return convert([parsed.module], ConversionConfig(timestamp=STAMP, **config), sources={"X": text})


def test_calls_are_counted_per_library_program_and_caller():
    found = calls([("MAIN", ["CALL CA_POSEINV(1,2)", "CALL CA_POSEMULT(1,2,3)", "CALL CA_POSEMULT(3,2,3)",
                             "CALL OTHER"]), ("OTHER", ["CALL CA_POSEMULT(1,1,1)", "CALL CA_NOTOURS(1)"])])
    assert found == {"CA_POSEMULT": {"MAIN": 2, "OTHER": 1}, "CA_POSEINV": {"MAIN": 1}}


def test_without_karel_nothing_is_said():
    result = _convert(POSES)
    assert result.karel_calls is None and karel_use(result) == ""


def test_with_karel_the_analysis_names_each_program_its_callers_and_calls():
    result = _convert(POSES, karel=True)
    assert result.karel_calls and set(result.karel_programs) == set(result.karel_calls)
    said = karel_use(result)
    for name, callers in result.karel_calls.items():
        assert f"`{name}` {sum(callers.values())} call" in said
        assert all(f"`{caller}` ({count})" in said for caller, count in callers.items())
    assert "everything else is TP" in said and any(said in line for line in analysis_markdown(result))


def test_karel_used_for_nothing_says_so():
    result = _convert("MODULE KN\n  PROC Main()\n    TPWrite \"x\";\n  ENDPROC\nENDMODULE\n", karel=True)
    assert result.karel_calls == {}
    assert "no KAREL program used" in karel_use(result)


def test_the_karel_section_lists_the_callers():
    export = ktrans.KarelExport(Path("KAREL"), written=["CA_POSEMULT"], compiled=[], version="V10.10", problem="no ktrans")
    text = ktrans.report_section(export, "KAREL", {"CA_POSEMULT": {"MAIN": 2, "CALIB": 1}})
    assert "Called on this run from 2 programs (3 calls)" in text and "`MAIN` (2), `CALIB` (1)" in text


def test_inlined_funcs_ask_to_convert_again_after_a_change():
    result = ConversionResult()
    result.notes.append(Note("MAIN", 3, "WARNING", "FUNC MakeTool() of the backup is inlined at 4 call sites: its"
                             " body is copied", Blocker.INLINED))  # fmt: skip
    action = next(a for a in priority_actions(result) if "copied into their calls" in a.title)
    assert "`MakeTool()` (4)" in action.detail and "converted again" in action.detail


def test_frames_past_the_limit_name_their_registers():
    lines = ["MODULE KB"]
    lines += [f"PERS tooldata tB{i}:=[TRUE,[[0,0,{100 + i}],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];"
              for i in range(1, 13)]  # fmt: skip
    lines += ["CONST robtarget p:=[[500,0,500],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];", "PROC main()"]
    lines += [f"  MoveL p,v100,fine,tB{i};" for i in range(1, 13)]
    result = _convert("\n".join([*lines, "ENDPROC", "ENDMODULE", ""]))
    action = next(a for a in priority_actions(result) if "past the controller's limit" in a.title)
    assert "3 frames" in action.title and "UTOOL[10]" in action.detail and "PR[" in action.detail
