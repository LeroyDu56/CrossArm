# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Data of RECORD types kept field by field (crossarm.convert.records): what is a register, what is a value."""

import json
from datetime import datetime

from helpers import parse_module

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.compute import Written
from crossarm.convert.mapping import build_mapping
from crossarm.convert.report import build_report
from crossarm.convert.translate import Blocker, ControllerScope
from crossarm.fanuc.tp import Motion

TYPES = (
    "RECORD params\n  speeddata speed;\n  zonedata zone;\nENDRECORD\n"
    "RECORD ctrl\n  num state;\n  num count;\n  params p;\n  bool busy;\n  string label;\nENDRECORD\n"
    "RECORD tally\n  num n;\n  bool seen;\nENDRECORD\n"
)
HOME = "CONST robtarget pHome:=[[600,0,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];\n"
CTRL = 'VAR ctrl rc:=[0,5,[[100,500,5000,1000],[FALSE,10,15,15,1.5,15,1.5]],FALSE,"IDLE"];\n'


def run(body: str, data: str = "", procs: str = "", config: ConversionConfig | None = None, shared=None,
        routines: list[str] | None = None):  # fmt: skip
    source = f"MODULE M\n{TYPES}{HOME}{data}\nPROC main()\n{body}\nENDPROC\n{procs}\nENDMODULE\n"
    config = config or ConversionConfig(timestamp=datetime(2026, 1, 1))
    return convert([parse_module(source)], config, routines=routines or ["main"], sources={"M": source},
                   shared=shared)  # fmt: skip


def lines(result, program: str = "MAIN") -> list[str]:
    info = next(i for i in result.programs if i.program.name == program)
    out = []
    for line in info.program.lines[1:]:
        if isinstance(line, Motion):
            out.append(f"{line.kind} {line.target} {line.speed} {line.termination}")
        else:
            out.append(line.text)
    return out


def todos(result) -> list[str]:
    return [n.message for n in result.notes if n.kind == "TODO"]


def warnings(result, category: str) -> list[str]:
    return [n.message for n in result.notes if n.kind == "WARNING" and n.category == category]


# -- a field the programs change: a register, a flag ---------------------------------------------


def test_a_num_field_the_programs_change_is_a_register_named_by_its_path():
    result = run("rc.state:=1;\nrc.count:=rc.count+1;\nnOut:=rc.state;", CTRL + "VAR num nOut;\n")
    assert lines(result) == ["R[1:rc.state]=1", "R[2:rc.count]=R[2:rc.count]+1", "R[3:nOut]=R[1:rc.state]"]
    assert todos(result) == []


def test_a_field_set_in_one_routine_is_read_in_another_from_the_same_register():
    procs = "PROC DoStep()\n  rc.state:=2;\nENDPROC\nPROC Show()\n  IF rc.state=2 nOut:=1;\nENDPROC\n"
    result = run("DoStep;\nShow;", CTRL + "VAR num nOut;\n", procs, routines=["main", "DoStep", "Show"])
    assert lines(result, "DOSTEP") == ["R[1:rc.state]=2"]
    assert lines(result, "SHOW") == ["IF (R[1:rc.state]=2) THEN", "R[2:nOut]=1", "ENDIF"]


def test_a_bool_field_is_a_flag_set_tested_and_copied():
    data = CTRL + "VAR tally tA;\nVAR tally tB;\n"
    result = run("rc.busy:=TRUE;\nIF rc.busy tA.seen:=TRUE;\ntB.seen:=tA.seen;", data)
    assert lines(result) == ["F[1]=(ON)", "IF (F[1]=ON) THEN", "F[2]=(ON)", "ENDIF", "F[3]=(F[2])"]


def test_a_whole_record_is_set_field_by_field_from_another_or_from_values():
    result = run("tA:=tB;\ntB:=[4,TRUE];\nnOut:=tA.n;", "VAR tally tA;\nVAR tally tB;\nVAR num nOut;\n")
    assert lines(result) == ["R[1:tA.n]=R[2:tB.n]", "F[2]=(F[1])", "R[2:tB.n]=4", "F[1]=(ON)", "R[3:nOut]=R[1:tA.n]"]


# -- a field no program changes: its value -------------------------------------------------------


def test_a_field_no_program_changes_is_written_as_its_value():
    result = run("nOut:=rc.count+1;", CTRL + "VAR num nOut;\n")
    assert lines(result) == ["R[1:nOut]=6"]
    assert warnings(result, Blocker.SAVED_VALUE) == []  # a VAR: its declared value


def test_the_fields_of_a_pers_no_program_changes_are_its_saved_values_said_once():
    data = 'PERS ctrl rcSaved:=[0,7,[[300,500,5000,1000],[FALSE,10,15,15,1.5,15,1.5]],FALSE,"S"];\nVAR num nOut;\n'
    result = run("nOut:=rcSaved.count+rcSaved.p.speed.v_tcp;\nIF NOT rcSaved.busy nOut:=nOut+1;", data)
    found = lines(result)
    assert (found[0], found[1].endswith("IF always TRUE: no test"), found[2]) == ("R[1:nOut]=307", True,
                                                                               "R[1:nOut]=R[1:nOut]+1")  # fmt: skip
    assert len(warnings(result, Blocker.SAVED_VALUE)) == 1
    assert warnings(result, Blocker.SAVED_VALUE)[0].startswith("rcSaved, a PERS no program changes")


# -- what changes a field (crossarm.convert.compute.Written): never a value then ---------------


def _read_after(procs: str, body: str, data: str = "") -> list[str]:
    """main reads rc.count after `body`: R[...] when something may change the field, 6 when nothing does."""
    return lines(run(f"{body}\nnOut:=rc.count+1;", CTRL + "VAR num nOut;\n" + data, procs))


def test_a_field_is_changed_by_an_assignment_to_the_record_it_is_part_of():
    data = "RECORD outer\n  tally t;\nENDRECORD\nVAR outer o:=[[5,FALSE]];\n"
    result = run("o.t:=[7,TRUE];\nnOut:=o.t.n;", data + "VAR num nOut;\n")
    assert lines(result) == ["R[1:o.t.n]=7", "F[1]=(ON)", "R[2:nOut]=R[1:o.t.n]"]


def test_a_field_is_changed_by_an_assignment_to_the_whole_data():
    assert _read_after("PROC Other()\n  rc:=rc;\nENDPROC\n", "")[-1] == "R[1:nOut]=R[2:rc.count]+1"


def test_a_field_is_changed_by_a_routine_given_the_record_to_change_even_through_another():
    procs = ("PROC SetIt(INOUT ctrl c)\n  c.count:=9;\nENDPROC\n"
             "PROC Via(INOUT ctrl c)\n  SetIt c;\nENDPROC\n")  # fmt: skip
    found = _read_after(procs, "Via rc;")
    assert found[-1] == "R[1:nOut]=R[2:rc.count]+1"


def test_a_routine_given_the_record_only_to_read_changes_nothing():
    procs = "PROC Look(ctrl c)\n  TPWrite \"x\";\nENDPROC\n"
    assert _read_after(procs, "")[-1] == "R[1:nOut]=6"


def test_incr_and_clear_change_a_field_and_are_converted():
    result = run("Incr rc.count;\nClear rc.state;\nnOut:=rc.count;", CTRL + "VAR num nOut;\n")
    assert lines(result) == ["R[1:rc.count]=R[1:rc.count]+1", "R[2:rc.state]=0", "R[3:nOut]=R[1:rc.count]"]


def test_setdataval_on_the_record_changes_it():
    assert _read_after("PROC Other()\n  SetDataVal \"rc\",rc;\nENDPROC\n", "")[-1] == "R[1:nOut]=R[2:rc.count]+1"


def test_setdataval_on_a_name_computed_at_run_time_may_change_any_field():
    """SetDataVal sets data of the type of the value it is given: a ctrl, any ctrl may be the one named."""
    procs = "PROC Other()\n  VAR string s:=\"rc\";\n  SetDataVal s,rcAny;\nENDPROC\n"
    assert _read_after(procs, "", "VAR ctrl rcAny;\n")[-1] == "R[1:nOut]=R[2:rc.count]+1"
    procs = "PROC Other()\n  VAR string s:=\"rc\";\n  SetDataVal s,nAny;\nENDPROC\n"
    assert _read_after(procs, "", "VAR num nAny;\n")[-1] == "R[1:nOut]=6"  # a num: never a field of rc


def test_another_task_changing_a_pers_record_changes_it_but_not_a_var_of_its_own():
    other = parse_module(f"MODULE Other\n{TYPES}PERS ctrl rp:=[0,5,[[100,500,5000,1000],[FALSE,10,15,15,1.5,15,1.5]],"
                         'FALSE,"P"];\n' + CTRL + "PROC o()\n  rp.count:=1;\n  rc.count:=1;\nENDPROC\nENDMODULE\n")  # fmt: skip
    data = CTRL.replace("VAR ctrl rc", "PERS ctrl rp") + CTRL + "VAR num nA;\nVAR num nB;\n"
    source = f"MODULE M\n{TYPES}{HOME}{data}\nPROC main()\nnA:=rp.count;\nnB:=rc.count;\nENDPROC\nENDMODULE\n"
    module = parse_module(source)
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    shared = ControllerScope.from_config(config)
    shared.written = Written.of([module, other])
    result = convert([module], config, routines=["main"], sources={"M": source}, shared=shared)
    assert lines(result) == ["R[1:nA]=R[2:rp.count]", "R[3:nB]=5"]


# -- speeds and zones: the value every write gives --------------------------------------------


INIT = "PROC Init()\n  rc.p.speed:=v400;\n  rc.p.zone:=z50;\nENDPROC\n"


def test_a_speed_and_zone_set_once_are_the_moves_value_with_a_warning():
    result = run("Init;\nMoveL pHome,rc.p.speed,rc.p.zone,tool0;", CTRL, INIT, routines=["main", "Init"])
    assert lines(result)[-1].startswith("L P[1] 400mm/sec CNT")
    assert [line.split(" ", 1)[1] for line in lines(result, "INIT")] == ["rc.p.speed:=v400", "rc.p.zone:=z50"]
    found = warnings(result, Blocker.RECORD_VALUE)
    assert len(found) == 2 and "right once that routine has run" in found[0]
    assert todos(result) == []


def test_a_speed_read_before_the_routine_setting_it_says_so():
    body = "MoveL pHome,rc.p.speed,fine,tool0;\nInit;\nMoveL pHome,rc.p.speed,fine,tool0;"
    result = run(body, CTRL, INIT, routines=["main", "Init"])
    assert any("is read at M.main l.21 before it is set, where the ABB robot still has its declared value" in w
               for w in warnings(result, Blocker.RECORD_VALUE))  # fmt: skip


def test_a_speed_set_to_different_values_stays_todo_with_why():
    procs = INIT + "PROC Slow()\n  rc.p.speed:=v100;\nENDPROC\n"
    result = run("MoveL pHome,rc.p.speed,fine,tool0;", CTRL, procs)
    assert any("rc.p.speed: set to different values (M.Init l.24, M.Slow l.28)" in t for t in todos(result))
    assert {n.category for n in result.notes if n.kind == "TODO"} == {Blocker.VALUE}


def test_a_predefined_zone_given_as_the_value_of_a_data_is_read():
    result = run("MoveL pHome,v200,zPick,tool0;", "CONST zonedata zPick:=z50;\n")
    assert todos(result) == [] and lines(result)[-1].startswith("L P[1] 200mm/sec CNT")


# -- a record of the routine -----------------------------------------------------------------


def test_a_record_of_the_routine_is_set_to_its_initial_value_where_it_starts():
    procs = "PROC Count()\n  VAR tally t;\n  t.n:=t.n+1;\n  nOut:=t.n;\nENDPROC\n"
    result = run("Count;", "VAR num nOut;\n", procs, routines=["main", "Count"])
    assert lines(result, "COUNT") == ["R[1:COUNT.t.n]=0", "R[1:COUNT.t.n]=R[1:COUNT.t.n]+1", "R[2:nOut]=R[1:COUNT.t.n]"]
    assert any("COUNT" in w or "Count.t" in w for w in warnings(result, Blocker.LOCAL_RECORD))
    assert json.loads(build_mapping(result, ConversionConfig()))["registers"]["COUNT.t.n"] == 1


def test_a_record_of_a_routine_calling_itself_back_stays_todo():
    procs = "PROC Count()\n  VAR tally t;\n  t.n:=t.n+1;\n  IF t.n<3 Count;\nENDPROC\n"
    result = run("Count;", "", procs, routines=["main", "Count"])
    assert any("a record of a routine that calls itself back" in t for t in todos(result))


def test_a_record_of_the_routine_with_a_string_field_stays_todo():
    procs = "PROC Show()\n  VAR ctrl c;\n  c.state:=1;\nENDPROC\n"
    result = run("Show;", "", procs, routines=["main", "Show"])
    assert any("converted when all its fields are num or bool" in t for t in todos(result))


# -- what stays TODO ---------------------------------------------------------------------------


def test_string_robtarget_and_array_of_records_stay_todo_with_why():
    data = CTRL + "RECORD place\n  robtarget p;\nENDRECORD\nVAR place pl;\nVAR tally tAll{3};\n"
    result = run('rc.label:="RUN";\npl.p:=pHome;\ntAll{2}.n:=1;', data)
    found = todos(result)
    assert "string field rc.label: a string of a record is not kept in a string register" in found[0]
    assert "robtarget field pl.p: not converted" in found[1]
    assert "an array of records is not converted" in found[2]


# -- numbering, mapping file, report ----------------------------------------------------------


def test_a_field_the_mapping_file_does_not_pin_is_numbered_after_every_number_it_pins(tmp_path):
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"registers": {"rc.state": 40, "nOther": 12}}), encoding="utf-8")
    config = ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))
    result = run("rc.state:=1;\nrc.count:=2;\nnNew:=3;", CTRL + "VAR num nNew;\n", config=config)
    assert lines(result) == ["R[40:rc.state]=1", "R[41:rc.count]=2", "R[1:nNew]=3"]
    mapping = json.loads(build_mapping(result, config))["registers"]
    assert (mapping["rc.state"], mapping["rc.count"]) == (40, 41)


def test_the_report_gives_the_registers_and_flags_each_record_takes():
    result = run("rc.state:=1;\nrc.count:=2;\nrc.busy:=TRUE;", CTRL)
    assert result.records == {"rc": (2, 1)}
    report = build_report(result, ConversionConfig(), ["M.mod"])
    assert "### Records kept field by field" in report and "| rc | 2 | 1 |" in report
