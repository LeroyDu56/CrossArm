# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Routines the integrator provides as TP or KAREL programs (external_routines, crossarm.convert.external): their
calls are CALL PROGRAM(args), they are not written, the report and the checklist say what each program has to do,
and the mapping file CrossArm writes offers the routines it could not write, activating none."""

import json
from datetime import datetime

import pytest
from helpers import parse_module

from crossarm.convert import ConversionConfig, build_mapping, build_report, convert
from crossarm.convert.blockers import Blocker
from crossarm.convert.checklist import checklist_section
from crossarm.convert.external import ProvidedRoutine
from crossarm.fanuc.tp import Instruction

SOURCE = """MODULE M
    VAR num nState:=0;
    VAR num nCount:=3;
    VAR iodev log;
    PROC main()
        WriteLog "start",nCount;
        ReadState nState;
        GripOpen 2.5,TRUE;
        Helper;
    ENDPROC
    PROC WriteLog(string text,num n)
        Open "HOME:/log.txt",log;
        Write log,text;
        Close log;
    ENDPROC
    PROC ReadState(INOUT num s)
        s:=5;
        WriteLog "x",1;
    ENDPROC
    PROC Helper()
        WriteLog "h",2;
    ENDPROC
ENDMODULE
"""
STAMP = datetime(2026, 1, 1)


def config(**kwargs) -> ConversionConfig:
    return ConversionConfig(timestamp=STAMP, **kwargs)


def provided(**entries: str) -> dict[str, ProvidedRoutine]:
    return {name.upper(): ProvidedRoutine(name, program) for name, program in entries.items()}


def run(source: str = SOURCE, cfg: ConversionConfig | None = None, **entries: str):
    cfg = cfg or config(external_routines=provided(**entries))
    return convert([parse_module(source)], cfg, sources={"M": source})


def lines(result, program: str = "MAIN") -> list[str]:
    info = next(i for i in result.programs if i.program.name == program)
    return [line.text for line in info.program.lines if isinstance(line, Instruction)]


def todos(result) -> list[str]:
    return [n.message for n in result.notes if n.kind == "TODO"]


def mapping_file(tmp_path, data: dict):
    path = tmp_path / "map.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return ConversionConfig.from_mapping_file(path, timestamp=STAMP)


# ---------------------------------------------------------------------------
# The key in the mapping file
# ---------------------------------------------------------------------------


def test_the_key_names_a_program_and_types_the_arguments_of_an_undeclared_routine(tmp_path):
    cfg = mapping_file(tmp_path, {"external_routines": {
        "WriteLog": {"program": "write_log"},
        "GripOpen": {"program": "GRIP_OPEN", "arguments": ["num", None, "INOUT num"], "_why": "a note"},
        "ReadState": {"program": None},  # a candidate CrossArm wrote: nothing provided
        "Other": None,
        "_README": "ignored",
    }})  # fmt: skip
    assert cfg.external_routines == {
        "WRITELOG": ProvidedRoutine("WriteLog", "WRITE_LOG"),
        "GRIPOPEN": ProvidedRoutine("GripOpen", "GRIP_OPEN", ("num", None, "INOUT num")),
    }


@pytest.mark.parametrize(("entry", "message"), [
    ("WRITE_LOG", "expected {\"program\": \"NAME\"}"),
    ({"program": "1LOG"}, "external_routines.WriteLog.program: expected a TP program name"),
    ({"program": "LOG-1"}, "expected a TP program name"),
    ({"program": 3}, "expected a TP program name"),
    ({"program": "L" * 37}, "longer than program_name_max_length"),
    ({"program": "LOG", "args": ["num"]}, "unknown keys args"),
    ({"program": "LOG", "arguments": ["float"]}, "external_routines.WriteLog.arguments: expected a list of"),
    ({"program": "LOG", "arguments": "num"}, "expected a list of"),
    ({"program": "LOG", "arguments": ["num"] * 11}, "at most 10"),
])  # fmt: skip
def test_a_wrong_entry_is_refused_saying_which_and_why(tmp_path, entry, message):
    with pytest.raises((ValueError, TypeError), match=message.replace("(", r"\(").replace("{", r"\{")):
        mapping_file(tmp_path, {"external_routines": {"WriteLog": entry}})


def test_a_provided_program_may_not_take_the_name_of_another_program_crossarm_writes(tmp_path):
    with pytest.raises(ValueError, match="MAIN is the name programs gives MAIN"):
        mapping_file(tmp_path, {"programs": {"main": "MAIN"}, "external_routines": {"WriteLog": {"program": "MAIN"}}})
    # the routine's own name in programs (it was written before it was provided) is no clash
    cfg = mapping_file(tmp_path, {"programs": {"WriteLog": "WRITELOG"},
                                  "external_routines": {"WriteLog": {"program": "WRITELOG"}}})  # fmt: skip
    assert cfg.external_routines["WRITELOG"].program == "WRITELOG"


def test_the_name_length_follows_program_name_max_length(tmp_path):
    with pytest.raises(ValueError, match="longer than program_name_max_length"):
        mapping_file(tmp_path, {"program_name_max_length": 8, "external_routines": {"W": {"program": "WRITE_LOG"}}})


# ---------------------------------------------------------------------------
# The conversion
# ---------------------------------------------------------------------------


def test_without_the_key_nothing_changes_and_the_routines_stay_todo():
    result = run()
    assert [i.program.name for i in result.programs] == ["MAIN", "WRITELOG", "READSTATE", "HELPER"]
    assert any("GripOpen' is not in the backup" in t for t in todos(result))
    assert result.provided == []


def test_each_call_is_a_call_to_the_program_and_the_routine_is_not_written():
    result = run(WriteLog="WRITE_LOG", ReadState="READ_STATE", GripOpen="GRIP_OPEN")
    assert [i.program.name for i in result.programs] == ["MAIN", "HELPER"]  # neither WRITELOG nor READSTATE
    assert lines(result)[1:] == [
        "CALL WRITE_LOG('start',R[1])",
        "CALL READ_STATE(R[2:nState])",
        "R[2:nState]=R[3:s]",  # INOUT num the routine changes: read back from the register the program writes
        "CALL GRIP_OPEN(2.5,1)",  # not in the backup: typed from what the call passes
        "CALL HELPER",
    ]
    assert lines(result, "HELPER")[1:] == ["CALL WRITE_LOG('h',2)"]  # no longer files through WriteLog
    assert todos(result) == []


def test_the_report_record_says_what_each_program_has_to_do():
    result = run(WriteLog="WRITE_LOG", ReadState="READ_STATE", GripOpen="GRIP_OPEN")
    uses = {u.program: u for u in result.provided}
    log, state, grip = uses["WRITE_LOG"], uses["READ_STATE"], uses["GRIP_OPEN"]
    assert log.declaration == "PROC WriteLog(string text,num n)"
    assert log.why.startswith("it calls Open: files")
    assert [(a.register, a.name, a.rapid_type) for a in log.arguments] == [("AR[1]", "text", "string"),
                                                                           ("AR[2]", "n", "num")]  # fmt: skip
    assert log.calls == [("MAIN", 6), ("HELPER", 21)]
    assert state.returned == {"s": 3} and state.arguments[0].returned
    assert grip.module is None and "not in the backup" in grip.why
    assert [(a.name, a.rapid_type) for a in grip.arguments] == [("argument 1", "num"), ("argument 2", "bool")]


def test_an_undeclared_routine_can_be_typed_by_the_mapping_file_with_a_num_given_back():
    source = SOURCE.replace("GripOpen 2.5,TRUE;", "GripOpen 2.5,nCount;")
    cfg = config(external_routines={"GRIPOPEN": ProvidedRoutine("GripOpen", "GRIP_OPEN", ("num", "INOUT num"))})
    result = run(source, cfg)
    text = lines(result)
    index = text.index("CALL GRIP_OPEN(2.5,R[1:nCount])")
    assert text[index + 1].startswith("R[1:nCount]=R[")
    assert result.provided[-1].returned == {"argument 2": int(text[index + 1].split("R[")[2].split(":")[0])}


@pytest.mark.parametrize(("call", "why"), [
    ("GripOpen pHome;", "its type is not known"),
    ("GripOpen 2\\Wait;", "where it goes among the arguments is not known"),
])  # fmt: skip
def test_what_cannot_be_passed_to_an_undeclared_routine_stays_todo(call, why):
    source = SOURCE.replace("GripOpen 2.5,TRUE;", call)
    result = run(source, None, GripOpen="GRIP_OPEN")
    found = [n for n in result.notes if n.kind == "TODO" and n.program == "MAIN"]
    assert len(found) == 1 and why in found[0].message and "provided as GRIP_OPEN" in found[0].message
    assert found[0].category == Blocker.CALL_ARGS
    assert result.provided[0].todo == {("MAIN", 8): found[0].message.split("(external_routines): ")[1].split(" — `")[0]}


def test_a_parameter_tp_cannot_pass_leaves_the_calls_todo_with_why():
    source = SOURCE.replace("PROC WriteLog(string text,num n)", "PROC WriteLog(string text,robtarget n)")
    source = source.replace('WriteLog "start",nCount;', 'WriteLog "start",pHome;')
    result = run(source, None, WriteLog="WRITE_LOG")
    assert any("robtarget parameter n: a provided program is not given points" in t for t in todos(result))
    assert "WRITELOG" not in [i.program.name for i in result.programs]
    assert "is not given points" in result.provided[0].problem


def test_a_string_read_back_cannot_be_given_back():
    source = SOURCE.replace("PROC ReadState(INOUT num s)\n        s:=5;", 'PROC ReadState(INOUT string s)\n        s:="a";')
    source = source.replace("VAR num nState:=0;", 'VAR string nState:="";')
    result = run(source, None, ReadState="READ_STATE")
    assert any("RAPID reads its string s (INOUT) back after the call" in t for t in todos(result))


def test_a_provided_function_in_an_expression_stays_todo():
    source = SOURCE.replace("Helper;\n", "Helper;\n        nCount:=Sensor(2)+1;\n")
    result = run(source, None, Sensor="SENSOR")
    found = [n for n in result.notes if n.category == Blocker.PROVIDED_FUNCTION]
    assert len(found) == 1 and "TP CALL gives no value back" in found[0].message
    assert result.provided[0].function and result.provided[0].todo


def test_a_rapid_instruction_is_not_a_routine_to_provide():
    result = run(WaitTime="MY_WAIT")
    assert any("an instruction of RAPID" in n.message for n in result.notes if n.kind == "WARNING")
    assert result.provided == []


def test_a_written_routine_does_not_take_the_name_of_a_provided_program():
    result = run(WriteLog="HELPER")
    names = [i.program.name for i in result.programs]
    assert "HELPER" not in names and "HELPER_2" in names
    assert any("to a program the integrator provides" in n.message for n in result.notes)
    assert "CALL HELPER('start',R[1])" in lines(result)


# ---------------------------------------------------------------------------
# Report, checklist, mapping file
# ---------------------------------------------------------------------------


def test_the_report_lists_the_programs_to_provide():
    result = run(WriteLog="WRITE_LOG", ReadState="READ_STATE", GripOpen="GRIP_OPEN")
    report = build_report(result, config(), ["M.mod"])
    assert "### Programs to provide" in report
    row = next(line for line in report.splitlines() if line.startswith("| `READ_STATE`"))
    assert "AR[1] s (num)" in row and "write its new value in R[3]" in row and "MAIN l.7" in row
    assert "RAPID: PROC ReadState(INOUT num s)" in row
    grip = next(line for line in report.splitlines() if line.startswith("| `GRIP_OPEN`"))
    assert "the backup does not declare it" in grip and "AR[2] argument 2 (bool)" in grip


def test_the_report_offers_the_routines_crossarm_could_not_write():
    report = build_report(run(), config(), ["M.mod"])
    assert "### Programs to provide" not in report
    assert "2 routines CrossArm cannot write could be a TP or KAREL program you provide" in report
    assert "GripOpen (not in the backup" in report and "WriteLog (it calls Open" in report


def test_the_checklist_has_a_group_for_the_programs_to_provide():
    result = run(WriteLog="WRITE_LOG", GripOpen="GRIP_OPEN")
    _, _, page = checklist_section(result, config(), {("MAIN", 6), ("MAIN", 8)}, identity="t")
    assert "Programs to provide" in page
    assert "Provide <code>WRITE_LOG</code>" in page and "AR[1] text (string)" in page
    assert 'called in <a href="#' in page
    _, _, plain = checklist_section(run(), config(), set(), identity="t")
    assert "Programs to provide" not in plain


def test_the_mapping_file_offers_the_candidates_without_activating_any(tmp_path):
    first = run()
    data = json.loads(build_mapping(first, config()))
    assert data["external_routines"] == {
        "GripOpen": {"program": None, "arguments": ["num", "bool"],
                     "_why": "not in the backup (a system module, an option, another task)"},
        "WriteLog": {"program": None, "_why": "it calls Open: files and serial channels: TP reads and writes no file"},
    }  # fmt: skip
    assert "program" in data["_external_routines"]
    path = tmp_path / "map.json"
    path.write_text(build_mapping(first, config()), encoding="utf-8")
    again = convert([parse_module(SOURCE)], ConversionConfig.from_mapping_file(path, timestamp=STAMP),
                    sources={"M": SOURCE})  # fmt: skip
    assert [i.program.lines for i in again.programs] == [i.program.lines for i in first.programs]
    assert build_mapping(again, config()) == build_mapping(first, config())


def test_filled_in_the_mapping_file_provides_the_routine_and_keeps_the_entry(tmp_path):
    data = json.loads(build_mapping(run(), config()))
    data["external_routines"]["WriteLog"]["program"] = "WRITE_LOG"
    cfg = mapping_file(tmp_path, data)
    result = run(SOURCE, cfg)
    assert "CALL WRITE_LOG('start',R[1])" in lines(result)
    written = json.loads(build_mapping(result, cfg))["external_routines"]
    assert written["WriteLog"] == {"program": "WRITE_LOG"}
    assert written["GripOpen"]["program"] is None


def test_a_backup_without_candidates_writes_no_such_key():
    source = "MODULE M\n    PROC main()\n        WaitTime 1;\n    ENDPROC\nENDMODULE\n"
    result = convert([parse_module(source)], config(), sources={"M": source})
    assert "external_routines" not in json.loads(build_mapping(result, config()))
