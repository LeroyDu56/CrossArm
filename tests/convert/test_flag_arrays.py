# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Arrays of bools the programs change or index at run time: a block of consecutive flags, set by SETUP_FRAMES,
read and set as F[base+k] at a fixed index and F[R[n]] at an index known at run time (flag array probe)."""

import json
from datetime import datetime

from test_translate import run, todos, tp_lines

from crossarm.convert import ConversionConfig, build_mapping
from crossarm.convert.setup import build_setup

SLOTS = "VAR bool bSlot{4};\nVAR num nK:=2;\nVAR num nCount:=0;\nVAR string sName{3};\n"


def config(**kwargs) -> ConversionConfig:
    return ConversionConfig(timestamp=datetime(2026, 1, 1), **kwargs)


def test_an_element_set_at_a_fixed_index_is_its_own_flag_at_the_top():
    assert tp_lines(run("bSlot{2}:=TRUE;\nbSlot{4}:=bSlot{2} AND nK>1;", SLOTS)) == [
        "F[1022]=(ON)", "F[1024]=(F[1022]=ON AND R[1]>1)"]  # fmt: skip


def test_an_element_at_an_index_known_at_run_time_is_read_and_set_through_an_index_register():
    lines = tp_lines(run("bSlot{nK}:=NOT bSlot{nK+1};\nIF bSlot{nK} nCount:=nCount+1;", SLOTS))
    assert lines == [
        "R[1:Calc8]=R[2]+1", "R[3:NumberIndex]=R[1:Calc8]", "R[3:NumberIndex]=R[3:NumberIndex]+1020",
        "R[4:NumberIndex2]=R[2]", "R[4:NumberIndex2]=R[4:NumberIndex2]+1020", "F[R[4]]=(F[R[3]]=OFF)",
        "IF (F[R[4]]=ON) THEN", "R[5:nCount]=R[5:nCount]+1", "ENDIF"]  # fmt: skip


def test_setup_frames_sets_the_values_the_array_is_declared_with():
    data = "VAR bool bSlot{3}:=[TRUE,FALSE,TRUE];\nVAR num nK:=1;\n"
    result = run("bSlot{nK}:=FALSE;", data)
    [array] = result.flag_arrays
    assert (array.name, array.base, array.values) == ("bSlot", 1022, (1.0, 0.0, 1.0))
    setup = build_setup(result, config(), "SETUP_FRAMES")
    texts = [getattr(line, "text", "") for line in setup.program.lines]
    assert texts[-3:] == ["F[1022]=(ON)", "F[1023]=(OFF)", "F[1024]=(ON)"]


def test_the_mapping_file_gives_the_first_flag_of_each_array_and_takes_it_back(tmp_path):
    result = run("bSlot{nK}:=TRUE;", SLOTS)
    data = json.loads(build_mapping(result, config()))
    assert data["flag_arrays"] == {"bSlot": 1021}
    data["flag_arrays"]["bSlot"] = 500
    path = tmp_path / "map.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    again = run("bSlot{nK}:=TRUE;", SLOTS, config=ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1)))
    assert "R[2:NumberIndex]=R[2:NumberIndex]+499" in tp_lines(again)


def test_a_program_without_arrays_of_bools_keeps_its_mapping_file():
    data = json.loads(build_mapping(run("nCount:=nCount+1;", SLOTS), config()))
    assert "flag_arrays" not in data


def test_an_array_of_bools_of_a_routine_it_changes_stays_todo():
    result = run("VAR bool bOwn{2};\nbOwn{nK}:=TRUE;", SLOTS)
    assert todos(result)[0].startswith("bOwn: an array of bools of a routine, changed by it")


def test_an_array_of_strings_written_stays_todo_with_why():
    result = run('sName{nK}:="A";', SLOTS)
    assert todos(result)[0].startswith("sName{nK}: arrays of strings are not kept in string registers, of which the"
                                       " controller has 25")  # fmt: skip
