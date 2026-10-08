# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""--karel, RAPID's files (crossarm.convert.karel_files): Open, Write and Close written as CALL CA_FILE, the handle
of an iodev kept in a register, texts and numbers given in parts. Measured on ROBOGUIDE:
tools/make_karel_file_probe.py (the files read back are RAPID's, byte for byte)."""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from crossarm.convert import ConversionConfig, build_mapping, convert
from crossarm.convert.blockers import Blocker
from crossarm.convert.external import ProvidedRoutine
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Instruction
from crossarm.rapid import parse_text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import make_karel_file_probe as probe

STAMP = datetime(2026, 1, 1)
MODULE = """MODULE KF
  VAR iodev logF;
  VAR iodev many{3};
  VAR num nCount:=0;
  VAR num k:=1;
  PROC Main()
    nCount:=nCount+1;
    BODY
  ENDPROC
  PROC LogLine(string text, num n)
    Open "HOME:" \\File:="log.txt", logF \\Append;
    Write logF, "<" + text + ">" \\Num:=n;
    Close logF;
  ENDPROC
ENDMODULE
"""


def conversion(body: str, karel: bool = True, **config):
    text = MODULE.replace("BODY", body)
    parsed = parse_text(text, path="KF.mod")
    assert parsed.module is not None, parsed.diagnostics
    return convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=karel, **config), sources={"KF": text})


def lines(result, program: str = "MAIN") -> list[str]:
    info = next(i for i in result.programs if i.program.name == program)
    return [line.text for line in info.program.lines if isinstance(line, Instruction)]


def todo(result) -> list:
    return [note for note in result.notes if note.kind == "TODO"]


def register(result, name: str) -> int:
    return next(a.number for a in result.registers if a.rapid_name == name)


def test_open_write_close_are_calls_to_ca_file():
    result = conversion('Open "HOME:" \\File:="log.txt", logF \\Write;\n'
                        '    Write logF, "count " \\Num:=nCount;\n'
                        '    Write logF, "a" \\NoNewLine;\n'
                        '    Close logF;\n'
                        '    LogLine "x", 2;')  # fmt: skip
    assert todo(result) == []
    h, n = register(result, "logF"), register(result, "nCount")
    main = lines(result)
    assert f"CALL CA_FILE(1,{h},1,'UD1:log.txt')" in main
    assert f"CALL CA_FILE(2,{h},1,'count ',R[{n}])" in main
    assert f"CALL CA_FILE(2,{h},0,'a')" in main
    assert f"CALL CA_FILE(3,{h})" in main
    assert [line for line in lines(result, "LOGLINE") if not line.startswith("!")] == [
        f"CALL CA_FILE(1,{h},2,'UD1:log.txt')", f"CALL CA_FILE(2,{h},1,'<',AR[1],'>',AR[2])", f"CALL CA_FILE(3,{h})"]
    assert result.karel_programs == ["CA_FILE"]
    assert any("UD1:" in note.message for note in result.notes if note.kind == "WARNING")


def test_texts_apostrophes_long_texts_and_many_parts():
    long = "x" * 50
    result = conversion('Open diskhome \\File:="a.txt", logF;\n'
                        f'    Write logF, "it\'s {long}";\n'
                        '    Write logF, "1"+"a"+NumToStr(k,0)+"b"+NumToStr(k,0)+"c"+NumToStr(k,0)+"d"+NumToStr(k,0)+"e";')
    assert todo(result) == []
    h = register(result, "logF")
    main = lines(result)
    assert f"CALL CA_FILE(1,{h},1,'UD1:a.txt')" in main  # Open without a switch: \Write
    assert f"CALL CA_FILE(2,{h},1,'it`s {long[:33]}','{long[33:]}')" in main
    calls = [line for line in main if line.startswith(f"CALL CA_FILE(2,{h},") and "'1a'" in line or "'d'" in line]
    assert calls[0].startswith(f"CALL CA_FILE(2,{h},0,'1a',SR[")  # the scratch registers used up: a line ended later
    assert main[-1].startswith(f"CALL CA_FILE(2,{h},1,") and main[-1].endswith(",'e')")


def test_an_element_of_an_iodev_array():
    result = conversion('Open "HOME:/b.txt", many{2} \\Append;\n'
                        '    Write many{k}, "y";\n'
                        '    Close many{2};')  # fmt: skip
    assert todo(result) == []
    main = lines(result)
    fixed = next(line for line in main if line.startswith("CALL CA_FILE(1,"))
    number = int(fixed.split(",")[1])
    assert fixed == f"CALL CA_FILE(1,{number},2,'UD1:b.txt')" and f"CALL CA_FILE(3,{number})" in main
    write = next(line for line in main if line.startswith("CALL CA_FILE(2,"))
    index = write.split(",")[1]
    assert index.startswith("R[") and main[main.index(write) - 1].startswith(index[:-1])  # R[i] holding the number


@pytest.mark.parametrize(("body", "said"), [
    ('Open "HOME:" \\File:="a.txt", logF \\Read;', "\\Read"),
    ('Open "TEMP:" \\File:="a.txt", logF;', "files of HOME: only"),
    ('Open "HOME:/sub" \\File:="a.txt", logF;', "a folder of HOME:"),
    ('Open "HOME:" \\File:="sub/a.txt", logF;', "a folder of HOME:"),
    ('Write logF, "a" \\Bool:=TRUE;', "\\Bool"),
    ('Write logF, "a`b";', "a character a TP text does not pass"),
])  # fmt: skip
def test_what_ca_file_does_not_write_stays_todo(body, said):
    result = conversion(body)
    notes = todo(result)
    assert len(notes) == 1 and said in notes[0].message, [n.message for n in notes]
    assert notes[0].category == Blocker.NO_TP_EQUIVALENT


def test_without_karel_files_stay_todo_and_the_count_says_what_karel_converts():
    body = 'Open "HOME:" \\File:="log.txt", logF;\n    Write logF, "a";\n    Close logF;\n    LogLine "x", 2;'
    off = conversion(body, karel=False)
    assert len(todo(off)) == 6 and off.karel_todo == 6  # LogLine's three too
    assert all("files and serial channels" in note.message for note in todo(off))
    assert not any("CA_FILE" in line for line in lines(off))


def test_without_karel_the_output_is_the_same_as_before():
    """karel=False and the default write the very same programs and mapping."""
    body = 'Open "HOME:" \\File:="log.txt", logF;\n    Write logF, "a";\n    Close logF;'
    text = MODULE.replace("BODY", body)
    plain = convert([parse_text(text, path="KF.mod").module], ConversionConfig(timestamp=STAMP), sources={"KF": text})
    off = conversion(body, karel=False)
    assert [write_ls(i.program) for i in plain.programs] == [write_ls(i.program) for i in off.programs]
    assert build_mapping(plain, ConversionConfig(timestamp=STAMP)) == build_mapping(off, ConversionConfig(timestamp=STAMP))


def test_the_numbers_of_a_mapping_written_without_karel_are_kept_with_it(tmp_path):
    body = 'Open "HOME:" \\File:="log.txt", logF;\n    Write logF, "a" \\Num:=nCount;\n    Close logF;'
    off = conversion(body, karel=False)
    mapping = tmp_path / "crossarm_mapping.json"
    mapping.write_text(build_mapping(off, ConversionConfig(timestamp=STAMP)), encoding="utf-8")
    first = json.loads(mapping.read_text(encoding="utf-8"))
    text = MODULE.replace("BODY", body)
    config = ConversionConfig.from_mapping_file(mapping, timestamp=STAMP, karel=True)
    on = convert([parse_text(text, path="KF.mod").module], config, sources={"KF": text})
    second = json.loads(build_mapping(on, config))
    assert todo(on) == [] and first["registers"]
    for table, values in first.items():
        if isinstance(values, dict) and not table.startswith("_") and table != "external_routines":  # offers only
            for key, number in values.items():
                assert second[table].get(key) == number, (table, key)
    assert "logF" in second["registers"] and "logF" not in first["registers"]


def test_a_routine_provided_by_the_integrator_is_called_not_converted_by_karel():
    """external_routines comes first: LogLine provided as a program is called as it, CA_FILE is not written."""
    provided = {"LOGLINE": ProvidedRoutine("LogLine", "LOGLINE_TP")}
    result = conversion('LogLine "x", 2;', external_routines=provided)
    assert "CALL LOGLINE_TP('x',2)" in lines(result)
    assert "LOGLINE" not in {i.program.name for i in result.programs}
    assert result.karel_programs == []


def test_the_probe_module_converts_and_rapid_numbers_follow_the_rule():
    with tempfile.TemporaryDirectory() as temp:
        result = probe.conversion(Path(temp))
    assert [i.program.name for i in result.programs] == [probe.MAIN, probe.LINE]
    assert probe.rapid_num(1 / 3) == "0.333333" and probe.rapid_num(123456.7) == "123457"
    assert probe.rapid_num(2.0000004) == "2" and probe.rapid_num(-0.000012) == "-0.000012"
    assert probe.rapid_num(99.99999) == "100" and probe.rapid_num(0.1 + 0.2) == "0.3"


def test_the_programs_written_are_those_of_the_fixture():
    with tempfile.TemporaryDirectory() as temp:
        result = probe.conversion(Path(temp))
    for program in [i.program for i in result.programs] + probe.hand_programs():
        assert write_ls(program) == (probe.PROBE / f"{program.name}.LS").read_bytes().decode("ascii")


@pytest.mark.skipif(not probe.RESULT.exists(), reason="KAREL file probe not run yet")
def test_on_roboguide_the_files_are_rapids_byte_for_byte():
    assert probe.verdict(probe.stored()) == ""
