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
USE_KEYS = {"occurrences", "converted", "partial", "todo"}


def test_the_schema(tmp_path):
    diag = diagnose.diagnose([make_backup(tmp_path)])
    assert set(diag) == TOP_KEYS
    assert diag["schema_version"] == diagnose.SCHEMA_VERSION == 1
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
        for use in diag[table].values():
            assert use["converted"] + use["partial"] + use["todo"] <= use["occurrences"]
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
    counted = sum(use["converted"] + use["partial"] + use["todo"]
                  for table in ("instructions", "user_calls") for use in diag[table].values())  # fmt: skip
    result = out.tasks[0].result
    assert counted == len(result.instructions)  # an error handler is one use, weighing one per statement in coverage
    assert sum(use["todo"] for use in diag["instructions"].values()) == sum(1 for c in result.instructions.values()
                                                                            if not c)  # fmt: skip


def test_the_command_writes_both_files(tmp_path, capsys):
    assert main(["diagnose", str(PICK), "-o", str(tmp_path / "d")]) == 0
    assert "Nothing was sent" in capsys.readouterr().out
    data = json.loads((tmp_path / "d" / diagnose.DIAG_JSON).read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
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

    allowed = sorted(ALLOWED | {"urllib"})  # urllib: the empty package urllib.parse is in
    probe = ("import sys; import crossarm.gui; "
             f"print(sorted(m for m in sys.modules if m.split('.')[0] in {sorted(FORBIDDEN)!r} "
             f"and m not in {allowed!r}))")  # fmt: skip
    found = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=60, check=False)
    assert found.returncode == 0, found.stderr
    assert found.stdout.strip() == "[]"
