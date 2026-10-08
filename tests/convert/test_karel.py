# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""--karel: poses computed at run time kept in position registers, PoseMult written as a CALL to CrossArm's KAREL
program CA_POSEMULT (crossarm.convert.karel_poses, crossarm.karel). Measured on ROBOGUIDE: make_karel_probe.py."""

import json
import re
from datetime import datetime

from crossarm.convert import ConversionConfig, build_mapping, build_report, convert
from crossarm.convert.analysis import priority_actions
from crossarm.convert.blockers import Blocker
from crossarm.convert.html_report import build_html_report
from crossarm.fanuc.ktrans import KarelExport
from crossarm.fanuc.ls_writer import write_ls
from crossarm.karel import LIBRARY, PROGRAMS, called, source
from crossarm.rapid import parse_text

STAMP = datetime(2026, 1, 1)
MODULE = """MODULE KP
  VAR pose pA;
  VAR pose pB:=[[10,20,30],[1,0,0,0]];
  VAR pose pC;
  VAR num n:=5;
  VAR robtarget pHere;
  PROC Main()
    pHere:=CRobT();
    pA:=[[n,0,100],[1,0,0,0]];
    pC:=PoseMult(pA,pB);
    pC:=PoseMult(pC,[[0,0,10],[0.7071068,0,0,0.7071068]]);
    n:=pC.trans.z;
    pB:=pC;
  ENDPROC
ENDMODULE
"""


def conversion(karel: bool, text: str = MODULE, **config):
    module = parse_text(text, path="KP.mod").module
    return convert([module], ConversionConfig(timestamp=STAMP, karel=karel, **config), sources={"KP": text})


def body(result) -> list[str]:
    return [line.split(":", 1)[1].strip().rstrip(";").strip()
            for line in write_ls(result.programs[0].program).split("/MN")[1].split("/POS")[0].splitlines()
            if ":" in line]  # fmt: skip


def test_the_library_ships_with_crossarm():
    assert "ROUTINE ca_reg_arg" in source(LIBRARY)
    for name, program in PROGRAMS.items():
        text = source(program.source)
        assert re.search(rf"^PROGRAM {name}$", text, re.IGNORECASE | re.MULTILINE), name
        assert "%INCLUDE ca_lib" in text and text.index("%INCLUDE ca_lib") < text.index("BEGIN")
        assert len(name) <= 12  # a KAREL program name


def test_called_finds_the_library_calls_only():
    assert called(["CALL CA_POSEMULT(1,2,3)", "CALL CA_OTHER(1)", "CALL MAIN", "!CALL CA_POSEMULT(1,2,3)"]) == [
        "CA_POSEMULT"]


def test_without_karel_poses_stay_todo_and_the_count_says_what_karel_converts():
    off = conversion(False)
    assert [line for line in body(off) if "CA_" in line and not line.startswith("!")] == []
    assert off.karel_programs == []
    todo = [note for note in off.notes if note.kind == "TODO"]
    assert len(todo) == 5 and off.karel_todo == 5  # every line on the poses: none left with --karel
    on = conversion(True)
    assert on.todo_count == 0


def test_without_karel_the_output_is_the_same_as_before():
    """The default (no option) and karel=False write the very same programs and mapping as without the field."""
    module = parse_text(MODULE, path="KP.mod").module
    plain = convert([module], ConversionConfig(timestamp=STAMP), sources={"KP": MODULE})
    off = conversion(False)
    assert write_ls(plain.programs[0].program) == write_ls(off.programs[0].program)
    assert build_mapping(plain, ConversionConfig(timestamp=STAMP)) == build_mapping(off, ConversionConfig(timestamp=STAMP))


def test_karel_writes_the_call_with_register_numbers():
    result = conversion(True)
    lines = body(result)
    registers = {a.rapid_name.upper(): a.number for a in result.point_registers}
    a, c, scratch = registers["PA"], registers["PC"], registers["CROSSARM.POSE2"]
    b = registers["PB"]
    assert lines[lines.index(f"PR[{registers['PHERE']}]=LPOS") + 1] == f"PR[{a},1]=R[1:n]"
    assert not any(line.startswith(f"PR[{b},") for line in lines)  # module data: its register keeps what was set
    started = [note for note in result.notes if note.kind == "WARNING" and "pose pB starts at the value" in note.message]
    assert len(started) == 1
    assert f"CALL CA_POSEMULT({a},{b},{c})" in lines
    assert f"PR[{scratch},6]=90" in lines  # the quaternion about z, as W, P, R
    assert f"CALL CA_POSEMULT({c},{scratch},{c})" in lines
    assert f"R[1:n]=PR[{c},3]" in lines
    assert f"PR[{b}]=PR[{c}]" in lines
    assert result.karel_programs == ["CA_POSEMULT"] and result.karel_todo == 0


def test_a_pose_whose_orientation_is_only_known_at_run_time_stays_todo():
    text = MODULE.replace("pA:=[[n,0,100],[1,0,0,0]];", "pA:=[[0,0,100],[n,0,0,0]];")
    result = conversion(True, text)
    todo = [note for note in result.notes if note.kind == "TODO"]
    assert todo and all(note.category in (Blocker.RUNTIME_POSITION, Blocker.VALUE) for note in todo)
    assert "pA:=[[0,0,100],[n,0,0,0]]" in todo[0].message


def test_a_controller_with_short_names_leaves_the_call_todo():
    result = conversion(True, program_name_max_length=8)
    assert result.karel_programs == []
    assert any("longer than the 8 characters" in note.message for note in result.notes if note.kind == "TODO")


def test_a_routine_named_as_a_library_program_is_renamed_with_karel():
    text = MODULE.replace("ENDMODULE", "  PROC CA_POSEMULT()\n    n:=1;\n  ENDPROC\nENDMODULE")
    names = {info.program.name for info in conversion(True, text).programs}
    assert "CA_POSEMULT" not in names
    assert "CA_POSEMULT" in {info.program.name for info in conversion(False, text).programs}


def test_the_numbers_of_a_mapping_written_without_karel_are_kept_with_it(tmp_path):
    """A mapping file written without --karel, given back with it: every number it holds stays; the poses kept in
    registers with --karel take free ones (point_registers)."""
    text = MODULE.replace("    pHere:=CRobT();", "    pHere:=CRobT();\n    n:=n+1;")
    off = conversion(False, text)
    mapping = tmp_path / "crossarm_mapping.json"
    mapping.write_text(build_mapping(off, ConversionConfig(timestamp=STAMP)), encoding="utf-8")
    first = json.loads(mapping.read_text(encoding="utf-8"))
    module = parse_text(text, path="KP.mod").module
    config = ConversionConfig.from_mapping_file(mapping, timestamp=STAMP, karel=True)
    on = convert([module], config, sources={"KP": text})
    second = json.loads(build_mapping(on, config))
    assert on.karel_programs == ["CA_POSEMULT"] and first["point_registers"]
    for table, values in first.items():
        if isinstance(values, dict) and not table.startswith("_"):
            for key, number in values.items():
                assert second[table].get(key) == number, (table, key)
    assert set(second["point_registers"]) > set(first["point_registers"])


def test_report_checklist_and_analysis_with_karel(tmp_path):
    result = conversion(True)
    config = ConversionConfig(timestamp=STAMP)
    export = KarelExport(tmp_path / "KAREL", written=["CA_POSEMULT"], compiled=["CA_POSEMULT"], version="V10.10-1")
    page = build_html_report(result, config, ["KP.mod"], title="t", karel=export, karel_where="../KAREL")
    assert 'id="ck-karel"' in page and "ca_posemult.pc" in page and "KAREL option (R632)" in page
    actions = priority_actions(result)
    assert any(a.title.startswith("Load the 1 KAREL program") and a.href == "#ck-karel" for a in actions)
    missing = KarelExport(tmp_path / "KAREL", written=["CA_POSEMULT"], problem="FANUC ktrans (ktrans.exe) not found")
    page = build_html_report(result, config, ["KP.mod"], title="t", karel=missing, karel_where="KAREL")
    assert "Not compiled (FANUC ktrans (ktrans.exe) not found)" in page


def test_report_and_analysis_without_karel_say_what_it_would_convert():
    result = conversion(False)
    report = build_report(result, ConversionConfig(timestamp=STAMP), ["KP.mod"])
    assert "Convert again with `--karel` for the poses computed at run time and the text files**: 5 TODO" in report
    page = build_html_report(result, ConversionConfig(timestamp=STAMP), ["KP.mod"], title="t")
    assert 'id="ck-karel"' not in page


def test_what_karel_would_convert_is_counted_with_the_programs_named_as_this_tasks():
    """A task whose program is renamed (an earlier task has a MAIN) counts the same TODO as alone: the conversion
    made again with --karel names its programs the same way."""
    from crossarm.convert.translate import ControllerScope

    text = MODULE.replace("    pB:=pC;", "    pB:=pC;\n    pB:=[[0,0,100],[n,0,0,0]];")  # one stays TODO with --karel
    alone = conversion(False, text)
    assert 0 < alone.karel_todo < alone.todo_count
    config = ConversionConfig(timestamp=STAMP)
    shared = ControllerScope.from_config(config)
    shared.program_names.add("MAIN")
    renamed = convert([parse_text(text, path="KP.mod").module], config, sources={"KP": text}, shared=shared)
    assert renamed.programs[0].program.name != "MAIN"
    assert renamed.karel_todo == alone.karel_todo
