# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""`crossarm diagnose`: the schema of crossarm_diag.json, the command, the internal errors reported without the
RAPID, the system description read, and no network code in what CrossArm ships."""

import ast
import json
from pathlib import Path

import pytest
from diag_backup import make_backup

from crossarm import diagnose, pipeline
from crossarm.cli import main
from crossarm.convert import translate
from crossarm.rapid import nodes as n
from crossarm.rapid.system_info import SystemInfo, read_backinfo, read_system, read_system_xml

FIXTURES = Path(__file__).parent / "fixtures"
PICK = FIXTURES / "rapid" / "pick_and_place.mod"

TOP_KEYS = {
    "schema_version", "crossarm", "environment", "input", "system", "conversion", "instructions", "functions",
    "user_calls", "data_types", "records", "aliases", "control", "signals", "internal_errors",
}  # fmt: skip
USE_KEYS = {"occurrences", "converted", "partial", "todo", "inside_todo", "not_converted", "not_converted_by"}
STATES = ("converted", "partial", "todo", "inside_todo", "not_converted")


def test_the_schema(tmp_path):
    diag = diagnose.diagnose([make_backup(tmp_path)])
    assert set(diag) == TOP_KEYS
    assert diag["schema_version"] == diagnose.SCHEMA_VERSION == 4
    assert set(diag["environment"]) == {"os", "os_release", "python", "exe", "day"}
    assert len(diag["environment"]["day"]) == 10  # the day, never the time
    assert diag["input"]["kind"] == "backup" and diag["input"]["tasks"] == 1
    assert diag["input"]["modules"] == {"program": 1, "system": 1}
    assert diag["input"]["routines"] == {"PROC": 2, "FUNC": 1, "TRAP": 0}
    conversion = diag["conversion"]
    assert conversion["completed"] and isinstance(conversion["converted_percent"], float)
    assert [t["task"] for t in conversion["tasks"]] == ["task_1"]
    for table in ("instructions", "functions", "user_calls"):
        assert diag[table] and all(set(use) == USE_KEYS for use in diag[table].values())
    assert_adds_up(diag)
    assert diag["instructions"]["MOVEL"]["occurrences"] == 1 and diag["functions"]["OFFS"]["occurrences"] == 2
    assert "user_proc(num,robtarget)" in diag["user_calls"]
    assert diag["records"] == {"record_1": ["num", "num", "string"]}
    assert diag["data_types"]["record_1"] == {"VAR": 1} and diag["data_types"]["num"]["arrays"] == 1
    assert diag["control"]["ERROR_HANDLER"] == 1 and diag["control"]["max_nesting"] == 2
    assert diag["signals"] == {"eio": True, "by_type": {"DI": 1, "DO": 1, "GO": 1, "AO": 1},
                               "eio_sections": {"DEVICENET_DEVICE": 1, "EIO_SIGNAL": 4, "INDUSTRIAL_NETWORK": 1}}  # fmt: skip
    assert diag["system"]["robotware"] == "6.14.02" and diag["system"]["robots"] == ["IRB 2400-16/1.55"]
    assert "608-1 World Zones" in diag["system"]["options"] and "709-1 DeviceNet Master/Slave" in diag["system"]["options"]
    assert diag["internal_errors"] == []
    json.dumps(diag)  # plain JSON types only


def test_the_conversion_counts_are_those_of_convert(tmp_path):
    diag = diagnose.diagnose([PICK])
    out = pipeline.run([PICK], tmp_path / "out", log=lambda _line: None)
    assert diag["conversion"]["todo"] == out.todo and diag["conversion"]["programs"] == out.programs
    assert diag["conversion"]["converted_percent"] == out.coverage.percent
    statements = [use for table in ("instructions", "user_calls") for use in diag[table].values()]
    left_out = sum(use["not_converted_by"].get(diagnose.LEFT_OUT, 0) for use in statements)
    counted = sum(use["converted"] + use["partial"] + use["todo"] + use["inside_todo"] for use in statements)
    result = out.tasks[0].result
    # an error handler is one use, weighing one per statement in coverage; a PROC left out is counted not converted
    assert counted + left_out == len(result.instructions)
    assert sum(use["todo"] + use["inside_todo"] for use in statements) + left_out == sum(
        1 for c in result.instructions.values() if not c)  # fmt: skip
    assert diag["conversion"]["todo_on_instructions"] == out.todo  # each TODO once, on its statement
    assert diag["conversion"]["todo_not_on_an_instruction"] == 0


def assert_adds_up(diag: dict) -> None:
    """Every row: its uses are converted, partial, TODO, inside a TODO, or in no program (with a reason); each TODO is
    counted once, on the statement carrying it."""
    for table in ("instructions", "functions", "user_calls"):
        for name, use in diag[table].items():
            assert set(use) == USE_KEYS, name
            assert sum(use[k] for k in STATES) == use["occurrences"], (table, name, use)
            assert sum(use["not_converted_by"].values()) == use["not_converted"], (table, name, use)
            assert set(use["not_converted_by"]) <= set(diagnose.REASONS)
            assert diagnose.NOT_COUNTED not in use["not_converted_by"], (table, name, use)  # every use explained
    assert all(use["todo"] == 0 for use in diag["functions"].values())  # the statement carries it
    conv = diag["conversion"]
    statements = [use for table in ("instructions", "user_calls") for use in diag[table].values()]
    if conv["completed"]:
        assert conv["todo_on_instructions"] == sum(use["todo"] for use in statements)
        assert conv["todo_on_instructions"] + conv["todo_not_on_an_instruction"] == conv["todo"]
        assert conv["todo_not_on_an_instruction"] >= 0
    reasons = {}
    for use in statements:
        for reason, count in use["not_converted_by"].items():
            reasons[reason] = reasons.get(reason, 0) + count
    assert conv["not_converted_by"] == {r: reasons[r] for r in diagnose.REASONS if r in reasons}


def _corpus(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith("_")
                  and any(f.suffix.lower() in (".mod", ".modx", ".sys", ".prg") for f in p.rglob("*")))  # fmt: skip


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = _corpus(ROOT / "abb")
REAL = _corpus(ROOT / "local" / "real_world")


@pytest.mark.parametrize("path", [*sorted(FIXTURES.glob("rapid/*.mod")), "diag_backup"],
                         ids=lambda p: getattr(p, "name", p))  # fmt: skip
def test_every_row_adds_up_on_the_fixtures(path, tmp_path):
    assert_adds_up(diagnose.diagnose([make_backup(tmp_path) if path == "diag_backup" else path]))


@pytest.mark.skipif(not SYNTHETIC + REAL, reason="no local test corpus")
@pytest.mark.parametrize("path", SYNTHETIC + REAL, ids=lambda p: p.name)
def test_every_row_adds_up_on_the_local_corpus(path):
    assert_adds_up(diagnose.diagnose([path]))


def test_a_todo_is_counted_on_the_statement_carrying_it(tmp_path):
    """An IF whose condition is TODO: the TODO is the IF's; its blocks are converted on their own (a Stop always,
    an Offs of a number never: a TODO of its own)."""
    source = tmp_path / "m.mod"
    source.write_text('MODULE M\n  VAR string s := "a";\n  VAR num n := 1;\n  PROC main()\n'
                      '    IF StrFind(s, 1, "b") > n Stop;\n    IF n > 2 Stop;\n'
                      '    IF StrFind(s, 1, "b") > n THEN\n      Stop;\n      n := Offs(n, 1, 1, 1);\n    ENDIF\n'
                      "  ENDPROC\nENDMODULE\n", encoding="utf-8")  # fmt: skip
    diag = diagnose.diagnose([source])
    assert_adds_up(diag)
    pick = {k: diag["instructions"][k] for k in ("IF", "STOP", "assignment")}
    assert [(u["converted"], u["todo"], u["inside_todo"]) for u in pick.values()] == [(1, 2, 0), (3, 0, 0), (0, 1, 0)]
    assert diag["functions"]["STRFIND"]["inside_todo"] == 2 and diag["functions"]["OFFS"]["inside_todo"] == 1
    assert diag["conversion"]["todo"] == diag["conversion"]["todo_on_instructions"] == 3
    md = diagnose.markdown(diag)
    assert "| Inside TODO | Not converted | Why not converted |" in md and "TODO on an instruction: 3" in md

    whole = tmp_path / "w.mod"  # a TEST whose CASE value is unknown is still a TODO whole: its blocks inside it
    whole.write_text("MODULE W\n  VAR num n := 1;\n  PROC main()\n    TEST n\n    CASE Unknown():\n      Stop;\n"
                     "    ENDTEST\n  ENDPROC\nENDMODULE\n", encoding="utf-8")  # fmt: skip
    diag = diagnose.diagnose([whole])
    assert_adds_up(diag)
    assert diag["instructions"]["STOP"]["inside_todo"] == 1


def test_the_code_in_no_program_says_why(tmp_path):
    source = tmp_path / "m.mod"
    source.write_text("MODULE M\n  VAR num n := 1;\n  PROC main()\n    n := 2;\n  ENDPROC\n"
                      "  FUNC num Twice(num x)\n    RETURN x * 2;\n  ENDFUNC\n"
                      "  TRAP lonely\n    n := 0;\n  ENDTRAP\nENDMODULE\n", encoding="utf-8")  # fmt: skip
    (tmp_path / "s.sys").write_text("MODULE S(SYSMODULE)\n  PROC helper()\n    WaitTime 1;\n  ENDPROC\nENDMODULE\n",
                                    encoding="utf-8")  # fmt: skip
    diag = diagnose.diagnose([tmp_path])
    assert_adds_up(diag)
    assert diag["instructions"]["WAITTIME"]["not_converted_by"] == {diagnose.SYSTEM_MODULE: 1}
    assert diag["instructions"]["RETURN"]["not_converted_by"] == {diagnose.FUNC_NEVER_CALLED: 1}
    assert diag["instructions"]["assignment"]["not_converted_by"] == {diagnose.LEFT_OUT: 1}


def test_a_func_with_no_program_says_why(tmp_path):
    """Schema 3: computed at conversion, inlined (here written as its test), left TODO at its calls, never called."""
    source = tmp_path / "m.mod"
    source.write_text("""MODULE M
  VAR num n := 1;
  PERS tooldata tGrip := [TRUE,[[0,0,100],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];
  PERS tooldata tLong := [TRUE,[[0,0,100],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];
  VAR string s := "a";
  CONST robtarget p10 := [[500,0,400],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  PROC main()
    tLong := Longer(tGrip);
    MoveL p10, v100, fine, tLong;
    IF Ready() Stop;
    n := Find(s);
  ENDPROC
  FUNC tooldata Longer(tooldata t)
    VAR tooldata r;
    r := t;
    r.tframe.trans.z := r.tframe.trans.z + 50;
    RETURN r;
  ENDFUNC
  FUNC bool Ready()
    RETURN DInput(di1) = 1;
  ENDFUNC
  FUNC num Find(string t)
    RETURN StrFind(t, 1, "b");
  ENDFUNC
  FUNC num Lonely()
    RETURN Find(s);
  ENDFUNC
ENDMODULE
""", encoding="utf-8")
    diag = diagnose.diagnose([source])
    assert_adds_up(diag)
    assert diag["instructions"]["RETURN"]["not_converted_by"] == {
        diagnose.FUNC_COMPUTED: 1, diagnose.FUNC_INLINED: 1, diagnose.FUNC_TODO: 1, diagnose.FUNC_NEVER_CALLED: 1}
    assert "computed or inlined" not in json.dumps(diag)  # the schema 2 reason is gone


PATH_KEYS = {"blocking_causes", "causes_to_workable", "instructions_to_workable", "verdict_with_karel"}


def test_schema_4_says_what_blocks_the_verdict(tmp_path):
    diag = diagnose.diagnose([make_backup(tmp_path)])
    conversion = diag["conversion"]
    task = conversion["tasks"][0]
    for where in (conversion, task):  # added, nothing of schema 3 removed
        assert PATH_KEYS <= set(where) and where["verdict"] in ("ready", "workable", "not ready")
        assert all(cause in diagnose._KNOWN_CAUSES for cause in where["blocking_causes"])
        assert set(where["causes_to_workable"]) <= set(where["blocking_causes"])
        assert isinstance(where["instructions_to_workable"], int)
    md = diagnose.markdown(diag)
    assert f"- Verdict: {conversion['verdict']}, blocking causes: " in md
    old = json.loads(json.dumps(diag))  # a schema 3 diagnostic: no such keys, no such lines
    for key in (*PATH_KEYS, "verdict"):
        del old["conversion"][key]
    assert "- Verdict:" not in diagnose.markdown(old)


def test_the_command_writes_both_files(tmp_path, capsys):
    assert main(["diagnose", str(PICK), "-o", str(tmp_path / "d")]) == 0
    assert "Nothing was sent" in capsys.readouterr().out
    data = json.loads((tmp_path / "d" / diagnose.DIAG_JSON).read_text(encoding="utf-8"))
    assert data["schema_version"] == 4
    md = (tmp_path / "d" / diagnose.DIAG_MD).read_text(encoding="utf-8")
    assert md == diagnose.markdown(data) and md.startswith("# CrossArm diagnostic report")
    assert not list(PICK.parent.glob("crossarm_*"))  # nothing written next to the input


def test_the_command_default_folder_is_next_to_the_input(tmp_path):
    source = tmp_path / "cell.mod"
    source.write_bytes(PICK.read_bytes())
    assert main(["diagnose", str(source)]) == 0
    assert sorted(p.name for p in (tmp_path / "crossarm_diag_cell").iterdir()) == [diagnose.DIAG_JSON, diagnose.DIAG_MD]
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith("crossarm")] == ["crossarm_diag_cell"]


def test_the_command_refuses_what_it_cannot_read(tmp_path, capsys):
    assert main(["diagnose", str(tmp_path / "missing.mod"), "-o", str(tmp_path / "d")]) == 2
    (tmp_path / "empty").mkdir()
    assert main(["diagnose", str(tmp_path / "empty"), "-o", str(tmp_path / "d")]) == 2
    assert not (tmp_path / "d").exists()


SECRET = "zwaluwCounter"


def test_an_internal_error_is_reported_without_the_rapid(tmp_path, monkeypatch):
    real = translate._RoutineTranslator.stmt

    def failing(self, stmt):
        if isinstance(stmt, n.Assign) and SECRET in str(stmt.target):
            raise KeyError(f"{SECRET} 4711 'Brandaris'")
        return real(self, stmt)

    monkeypatch.setattr(translate._RoutineTranslator, "stmt", failing)
    source = tmp_path / "m.mod"
    source.write_text(f"MODULE M\n  VAR num {SECRET} := 0;\n  PROC main()\n    {SECRET} := {SECRET} + 4711;\n"
                      "    MoveJ pHome, v1000, z50, tool0;\n  ENDPROC\nENDMODULE\n", encoding="utf-8")  # fmt: skip
    diag = diagnose.diagnose([source])
    [error] = diag["internal_errors"]
    assert error["type"] == "KeyError" and error["stage"] == "statement" and error["count"] == 1
    assert error["where"].startswith("diagnose.py:") is False and ":" in error["where"]
    assert error["tokens"] == ("VAR NUM <IDENT> := <NUM> ; PROC <IDENT> ( ) <IDENT> := <IDENT> + <NUM> ; MOVEJ <IDENT> , "
                               "<IDENT> ,")  # fmt: skip
    text = json.dumps(diag) + diagnose.markdown(diag)
    assert SECRET.lower() not in text.lower() and "4711" not in text and "Brandaris" not in text


def test_a_module_crossarm_fails_on_is_reported(tmp_path, monkeypatch):
    real = pipeline.convert

    def failing(modules, *args, **kwargs):
        if any(m.name == "Broken" for m in modules):
            raise KeyError("Broken")
        return real(modules, *args, **kwargs)

    monkeypatch.setattr(pipeline, "convert", failing)
    (tmp_path / "a.mod").write_text("MODULE A\n  PROC main()\n    WaitTime 1;\n  ENDPROC\nENDMODULE\n", encoding="utf-8")
    (tmp_path / "b.mod").write_text("MODULE Broken\n  PROC other()\n    WaitTime 1;\n  ENDPROC\nENDMODULE\n",
                                    encoding="utf-8")  # fmt: skip
    diag = diagnose.diagnose([tmp_path])
    assert [(e["type"], e["stage"], e["tokens"]) for e in diag["internal_errors"]] == [("KeyError", "module", "")]
    assert diag["internal_errors"][0]["where"].endswith(":failing") is False  # the test's own frame is not CrossArm
    assert diag["conversion"]["completed"]


def test_a_conversion_that_fails_whole_still_gives_a_diagnostic(tmp_path, monkeypatch):
    def bug(*args, **kwargs):
        raise KeyError("everywhere")

    monkeypatch.setattr(pipeline, "convert", bug)
    diag = diagnose.diagnose([PICK])
    assert not diag["conversion"]["completed"] and diag["instructions"]["MOVEL"]["occurrences"] == 3
    assert "run" in [e["stage"] for e in diag["internal_errors"]]
    assert "did not complete" in diagnose.markdown(diag)


def test_an_input_that_stopped_the_conversion_before_gives_a_diagnostic(tmp_path):
    deep = "IF n > 0 THEN\n" * 500 + "x := 1;\n" + "ENDIF\n" * 500  # RecursionError before CrossArm 1.11
    (tmp_path / "m.mod").write_text(f"MODULE M\n  VAR num n := 1;\n  VAR num x := 0;\n  PROC main()\n{deep}\n"
                                    "    x := 2;\n  ENDPROC\nENDMODULE\n", encoding="utf-8")  # fmt: skip
    assert main(["diagnose", str(tmp_path / "m.mod"), "-o", str(tmp_path / "d")]) == 0
    diag = json.loads((tmp_path / "d" / diagnose.DIAG_JSON).read_text(encoding="utf-8"))
    assert diag["input"]["syntax_errors"] >= 1 and diag["conversion"]["completed"]


def test_the_token_window_keeps_only_categories():
    text = 'MODULE M\n  PROC main()\n    TPWrite "secret 42";\n    reg_7 := Offs(p1, 10, 0, 0).trans.x;\n  ENDPROC\n'
    assert diagnose.token_window(text, 4) == ('MODULE <IDENT> PROC <IDENT> ( ) TPWRITE <STR> ; <IDENT> := OFFS ( '
                                              '<IDENT> , <NUM> , <NUM> , <NUM>')  # fmt: skip


def test_backinfo_products():
    info = SystemInfo()
    read_backinfo(">>SYSTEM_ID:\nCellName-12\n\n>>PRODUCTS_ID:\nRobotWare Version: 6.08.01\n  616-1 PC Interface\n"
                  "  My company pack 77\n  IRB 120-3/0.58\n\n>>TASK1: (T_ROB1,,)\n", info)  # fmt: skip
    assert (info.robotware, info.options, info.robots, info.other_lines) == (
        "6.08.01", ["616-1 PC Interface"], ["IRB 120-3/0.58"], 1)


def test_system_xml_read_loosely():
    info = SystemInfo()
    read_system_xml('<S><P name="RobotWare" version="7.10.1.0"/><O name="3114-1 Multitasking"/><Name>Cell 77</Name>'
                    '<Option>no code here</Option></S>', info)  # fmt: skip
    assert info.robotware == "7.10.1.0" and info.options == ["3114-1 Multitasking"] and info.other_lines == 1
    refused = SystemInfo()
    read_system_xml('<!DOCTYPE x [<!ENTITY a "616-1 PC Interface">]><x>&a;</x>', refused)
    assert refused == SystemInfo()
    assert read_system(None) == SystemInfo() and read_system(FIXTURES / "missing") == SystemInfo()


FORBIDDEN = {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "xmlrpc",
             "asyncio", "requests", "httpx", "aiohttp", "websocket", "selectors"}  # fmt: skip
ALLOWED = {"urllib.parse"}  # text only: quoting the anchors of the HTML report


@pytest.mark.parametrize("path", sorted((Path(diagnose.__file__).parent).rglob("*.py")),
                         ids=lambda p: p.relative_to(Path(diagnose.__file__).parent).as_posix())  # fmt: skip
def test_no_shipped_module_can_reach_the_network(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            assert name in ALLOWED or name.split(".")[0] not in FORBIDDEN, f"{path.name} imports {name}"


def test_the_window_loads_no_network_module():
    """The window imports webbrowser (it opens the issue form on the user's click): neither it nor anything the
    window imports loads a network module."""
    import subprocess
    import sys

    allowed = ALLOWED | {"urllib"}  # urllib: the empty package urllib.parse is in
    if sys.platform != "win32":
        allowed |= {"selectors"}  # subprocess (webbrowser) imports it on POSIX to wait on pipes: no connection
    allowed = sorted(allowed)
    probe = ("import sys; import crossarm.gui; "
             f"print(sorted(m for m in sys.modules if m.split('.')[0] in {sorted(FORBIDDEN)!r} "
             f"and m not in {allowed!r}))")  # fmt: skip
    found = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=60, check=False)
    assert found.returncode == 0, found.stderr
    assert found.stdout.strip() == "[]"
