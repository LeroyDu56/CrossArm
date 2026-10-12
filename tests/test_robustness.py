# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""An unknown backup never stops the conversion: what CrossArm cannot read or fails on is left out, said, and
the rest converted. Each test here is an input that crashed the conversion before (CrossArm 1.10.1)."""

import struct
import time
import zipfile

import pytest

from crossarm import pipeline
from crossarm.backup import open_source
from crossarm.cli import main
from crossarm.convert.blockers import Blocker
from crossarm.fanuc.usage import is_fanuc_input
from crossarm.rapid import nodes as n
from crossarm.rapid import parse_text
from crossarm.rapid.parser import MAX_EXPRESSION_DEPTH, MAX_NESTING
from crossarm.rapid.source import decode

QUIET = {"log": lambda _line: None}


def module(body: str, declarations: str = "") -> str:
    return (f"MODULE M\n  VAR num n := 1;\n  VAR num x := 0;\n{declarations}\n  PROC main()\n{body}\n"
            "    x := 2;\n  ENDPROC\nENDMODULE\n")  # fmt: skip


@pytest.mark.parametrize("deep", [
    "x := " + "(" * 1000 + "1" + ")" * 1000 + ";",  # parser recursion
    "x := " + "Abs(" * 300 + "1" + ")" * 300 + ";",
    "x := " + "-" * 2000 + "1;",
    "IF " + "NOT " * 2000 + "TRUE THEN\n x := 1;\nENDIF",
    "IF n > 0 THEN\n" * 500 + "x := 1;\n" + "ENDIF\n" * 500,
    "x := " + "+".join(["1"] * 5000) + ";",  # parsed without recursion: the converter's tree walks recursed
])  # fmt: skip
def test_a_statement_nested_without_end_is_a_syntax_error_of_its_own(deep, tmp_path):
    parsed = parse_text(module(deep))
    assert parsed.module is not None
    errors = [d.message for d in parsed.diagnostics if d.severity.value == "error"]
    assert errors and "levels deep: not read" in errors[0]
    body = parsed.module.routines[0].body
    assert isinstance(body[-1], n.Assign)  # the statement after it is read
    (tmp_path / "m.mod").write_text(module(deep), encoding="utf-8")
    out = pipeline.run([tmp_path / "m.mod"], tmp_path / "out", **QUIET)
    assert out.tasks[0].syntax_errors and out.programs == 1


def test_a_declaration_nested_without_end_is_left_out_alone():
    deep = "  VAR num y := " + "+".join(["1"] * 5000) + ";\n  VAR num z := 3;"
    parsed = parse_text(module("    x := z;", deep))
    assert [d.name for d in parsed.module.declarations] == ["n", "x", "z"]


def test_nesting_up_to_the_bounds_is_read():
    within = "(" * (MAX_NESTING - 5) + "n" + ")" * (MAX_NESTING - 5)
    chain = "+".join(["n"] * (MAX_EXPRESSION_DEPTH - 2))
    parsed = parse_text(module(f"    x := {within};\n    x := {chain};"))
    assert parsed.ok


def test_abs_of_abs_in_a_condition_is_unfolded_once(tmp_path):
    """Each Abs unfolded both sides of the test again: 2^n conditions (20 levels: minutes)."""
    deep = "Abs(" * 20 + "n" + ")" * 20
    (tmp_path / "m.mod").write_text(module(f"    IF {deep} > 2 THEN\n      x := 1;\n    ENDIF"), encoding="utf-8")
    started = time.perf_counter()
    out = pipeline.run([tmp_path / "m.mod"], tmp_path / "out", **QUIET)
    assert time.perf_counter() - started < 20
    assert "IF (R[1]>2 OR R[1]<(-2)) THEN" in (tmp_path / "out" / "MAIN.LS").read_text()
    assert out.todo == 0


def test_a_handler_calling_a_routine_that_raises_its_error(tmp_path):
    """The ERROR handler was written again at each call in it of a routine raising that error: without end."""
    source = """MODULE Grip
  VAR errnum ERR_LOST:=-1;
  PROC Init()
    BookErrNo ERR_LOST;
  ENDPROC
  PROC Close()
    IF diClosed=0 THEN
      RAISE ERR_LOST;
    ENDIF
  ERROR
    RAISE;
  ENDPROC
  PROC Cycle()
    Close;
    TPWrite "gripped";
  ERROR
    WaitTime 0.5;
    Close;
    RETRY;
  ENDPROC
ENDMODULE
"""
    (tmp_path / "grip.mod").write_text(source, encoding="utf-8")
    out = pipeline.run([tmp_path / "grip.mod"], tmp_path / "out", **QUIET)
    notes = out.tasks[0].result.notes
    assert not [note for note in notes if note.category == Blocker.INTERNAL]
    cycle = (tmp_path / "out" / "CYCLE.LS").read_text()
    assert cycle.count("CALL CLOSE") == 2


def test_utf16_module_is_read():
    text, encoding = decode("MODULE Été\nENDMODULE\n".encode("utf-16"))
    assert (text, encoding) == ("MODULE Été\nENDMODULE\n", "utf-16")


def _two_modules(tmp_path):
    (tmp_path / "Good.mod").write_text(module("    x := 1;").replace("MODULE M", "MODULE Good"), encoding="utf-8")
    (tmp_path / "Broken.mod").write_text("MODULE Broken\n  VAR num y := 0;\n  PROC other()\n    y := 3;\n  ENDPROC\nENDMODULE\n",
                                         encoding="utf-8")  # fmt: skip
    return [tmp_path / "Good.mod", tmp_path / "Broken.mod"]


def test_a_module_crossarm_fails_on_is_left_out_and_said(tmp_path, monkeypatch):
    real = pipeline.convert

    def failing(modules, *args, **kwargs):
        if any(m.name == "Broken" for m in modules):
            raise KeyError("a CrossArm bug")
        return real(modules, *args, **kwargs)

    monkeypatch.setattr(pipeline, "convert", failing)
    lines = []
    out = pipeline.run(_two_modules(tmp_path), tmp_path / "out", log=lines.append)
    result = out.tasks[0].result
    assert [p.program.name for p in result.programs] == ["MAIN"]
    [note] = [note for note in result.notes if note.category == Blocker.INTERNAL]
    assert note.kind == "TODO" and note.message.startswith("module Broken not converted: CrossArm internal error")
    assert "KeyError" in note.message and "please report it" in note.message
    assert any("module Broken not converted" in line for line in lines)
    assert "module Broken not converted" in (tmp_path / "out" / "crossarm_report.md").read_text(encoding="utf-8")


def test_the_numbers_a_failed_conversion_took_are_given_back(tmp_path, monkeypatch):
    real, calls = pipeline.convert, []

    def failing(modules, *args, **kwargs):
        calls.append([m.name for m in modules])
        result = real(modules, *args, **kwargs)  # numbers taken, then the failure
        if any(m.name == "Broken" for m in modules):
            raise KeyError("late")
        return result

    monkeypatch.setattr(pipeline, "convert", failing)
    pipeline.run(_two_modules(tmp_path), tmp_path / "out", **QUIET)
    assert calls[-1] == ["Good"]
    assert "R[1:x]=1" in (tmp_path / "out" / "MAIN.LS").read_text()  # not R[2]: the first attempt's R[1] given back


def test_a_failure_no_module_explains_still_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "convert", lambda *a, **k: (_ for _ in ()).throw(KeyError("everywhere")))
    with pytest.raises(KeyError):
        pipeline.run(_two_modules(tmp_path), tmp_path / "out", **QUIET)


def test_a_file_the_parser_fails_on_is_a_syntax_error_of_its_own(tmp_path, monkeypatch):
    real = pipeline.parse_file

    def failing(path):
        if path.name == "Broken.mod":
            raise IndexError("a parser bug")
        return real(path)

    monkeypatch.setattr(pipeline, "parse_file", failing)
    out = pipeline.run(_two_modules(tmp_path), tmp_path / "out", **QUIET)
    assert out.programs == 1
    [error] = out.tasks[0].syntax_errors
    assert error.startswith("Broken.mod: not read: CrossArm internal error, please report it: IndexError")


def _zip(tmp_path, damage):
    archive = tmp_path / "backup.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("backup/m.mod", module("    x := 1;") * 20)
    data = bytearray(archive.read_bytes())
    damage(data)
    archive.write_bytes(bytes(data))
    return archive


def _version(data):  # "version needed to extract" of the central directory entry: 10.0
    at = data.index(b"PK\x01\x02") + 6
    data[at : at + 2] = struct.pack("<H", 100)


def _deflated(data):  # bytes of the compressed module changed
    for at in range(40, 60):
        data[at] ^= 0x55


@pytest.mark.parametrize("damage", [_version, _deflated, lambda d: d.__delitem__(slice(len(d) // 2, None))])
def test_a_damaged_zip_says_so(tmp_path, damage):
    archive = _zip(tmp_path, damage)
    assert not is_fanuc_input(archive)
    with pytest.raises(ValueError, match="cannot read the zip file backup.zip"), open_source([archive]):
        pass


def test_cli_internal_error_is_a_message_and_a_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    def bug(*args, **kwargs):
        raise KeyError("a CrossArm bug")

    monkeypatch.setattr(pipeline, "run", bug)
    (tmp_path / "m.mod").write_text(module("    x := 1;"), encoding="utf-8")
    assert main(["convert", str(tmp_path / "m.mod")]) == 3
    err = capsys.readouterr().err
    assert "CrossArm internal error, please report it: KeyError" in err and "Traceback" not in err
    report = tmp_path / "CrossArm" / "crossarm_error.txt"
    assert report.is_file() and "KeyError" in report.read_text(encoding="utf-8")


def test_a_confdata_of_three_values_is_a_warning_not_an_internal_error(tmp_path):
    point = "  CONST robtarget pA:=[[500,-300,400],[0,0.707107,0.707107,0],[0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    (tmp_path / "m.mod").write_text(module("    MoveJ pA,v800,z50,tool0;", point), encoding="utf-8")
    out = pipeline.run([tmp_path / "m.mod"], tmp_path / "out", **QUIET)
    notes = out.tasks[0].result.notes
    assert not [note for note in notes if note.category == Blocker.INTERNAL]
    assert any("confdata of 3 values" in note.message for note in notes if note.kind == "WARNING")
    assert out.todo == 0
