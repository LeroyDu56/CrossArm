# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Blocker grouping and controller capacity: what the report leads with.

A large backup produces hundreds of TODO entries that come down to a handful of
causes, and allocates frame and register numbers without any upper bound. Both
are summarised so the reader sees the few jobs worth doing, and learns before
loading the programs that the controller cannot hold them.
"""

from datetime import datetime

from helpers import parse_module
from test_translate import HOME, TOOL, run

from crossarm.convert import ConversionConfig, build_report, convert
from crossarm.convert.translate import Blocker


def config(**kwargs) -> ConversionConfig:
    return ConversionConfig(timestamp=datetime(2026, 1, 1), **kwargs)


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


def test_todos_of_the_same_cause_are_grouped_under_one_blocker():
    result = run("Access_A 1;\nAccess_B 2;\nAccess_C 3;\nGOTO done;", extra_procs="PROC Access_A(robtarget x)\nENDPROC")
    assert result.todo_count == 4
    categories = {category: count for category, count, _ in result.grouped("TODO")}
    assert categories[Blocker.CALL_ARGS] == 3
    assert categories[Blocker.rapid("GOTO")] == 1


def test_blockers_are_ranked_and_carry_their_most_common_case():
    result = run("Access_A 1;\nAccess_A 2;\nGOTO done;")
    category, count, example = result.grouped("TODO")[0]
    assert (category, count) == (Blocker.CALL_ARGS, 2)
    assert example == "call to Access_A with arguments has no mapping"
    assert "`" not in example  # the quoted RAPID line is stripped: it differs on every line


def test_writing_a_frame_component_is_a_frame_blocker_not_a_record_one():
    """tool.tframe is run-time frame work, tool.tload a payload, p.trans a position: each its own job."""
    data = TOOL + "VAR robtarget pTmp:=[[0,0,0],[1,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    result = run("tGrip.tframe.trans.z:=GInput(giZ);\ntGrip.tload.mass:=5;\npTmp.trans.x:=GInput(giX);\n"
                 "struct.field:=1;", data)  # fmt: skip
    categories = {category for category, _, _ in result.grouped("TODO")}
    assert categories == {Blocker.RUNTIME_FRAME, Blocker.PAYLOAD, Blocker.RUNTIME_POSITION, Blocker.RECORD}


def test_a_whole_assignment_is_told_by_the_data_type():
    data = TOOL + "VAR speeddata vFast:=[500,500,5000,1000];\nVAR bool bOn:=TRUE;"
    result = run("tGrip:=tGrip;\nvFast:=vFast;\nbOn:=NOT bOn;", data)
    assert [n.category for n in result.notes if n.kind == "TODO"] == [
        Blocker.RUNTIME_FRAME, Blocker.VALUE, Blocker.VALUE,
    ]  # fmt: skip


def test_warnings_are_grouped_separately_from_todos():
    result = run('TPWrite "count "\\Num:=nCount;\nTPWrite "other "\\Num:=nCount;', "VAR num nCount:=0;")
    assert result.todo_count == 0
    assert result.grouped("TODO") == []
    assert [(c, n) for c, n, _ in result.grouped("WARNING")] == [(Blocker.MESSAGE_VALUE, 2)]


def test_clean_programs_are_counted():
    source = "MODULE M\nPROC good()\nStop;\nENDPROC\nPROC bad()\nGOTO x;\nENDPROC\nENDMODULE"
    result = convert([parse_module(source)], config())
    assert len(result.programs) == 2
    assert result.clean_programs() == 1


# ---------------------------------------------------------------------------
# Controller capacity
# ---------------------------------------------------------------------------


def tools_beyond(limit: int) -> str:
    """A module whose moves need `limit` + 1 different tools."""
    tools = "".join(
        f"PERS tooldata t{i}:=[TRUE,[[0,0,{i}],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];\n"
        for i in range(limit + 1)
    )  # fmt: skip
    moves = "".join(f"MoveJ pHome,v100,fine,t{i};\n" for i in range(limit + 1))
    return f"MODULE M\n{HOME}\n{tools}PROC main()\n{moves}ENDPROC\nENDMODULE\n"


def test_frames_past_the_controller_limit_are_kept_in_position_registers():
    # UTOOL_NUM=4 on a controller with 3 tool frames does not load (ASBN-092, measured on ROBOGUIDE).
    # The last free number is kept for the frames past the limit, each loaded into it from its PR.
    result = convert([parse_module(tools_beyond(3))], config(limits={"UTOOL": 3, "PR": 100}))
    lines = [line.text for line in result.programs[0].program.lines if hasattr(line, "text")]
    assert [line for line in lines if line.startswith("UTOOL")] == [
        "UTOOL_NUM=1", "UTOOL_NUM=2", "UTOOL[3]=PR[99]", "UTOOL_NUM=3", "UTOOL[3]=PR[98]", "UTOOL_NUM=3",
    ]  # fmt: skip
    assert [(f.rapid_name, f.number, f.bank, f.slot) for f in result.utools] == [
        ("t0", 1, None, None), ("t1", 2, None, None), ("t2", 4, 99, 3), ("t3", 5, 98, 3),
    ]  # fmt: skip
    positions = result.programs[0].program.positions
    assert {p.ut for p in positions} == {1, 2, 3}  # a point is taught in the frame selected: the slot
    utool = next(c for c in result.capacity if c.resource == "UTOOL")
    assert utool.fits
    (note,) = [n for n in result.notes if n.category == Blocker.CAPACITY]
    assert note.message.startswith("2 UTOOL above the 3 the controller holds (t2, t3) are kept in PR[98] to PR[99]")


def test_allocating_past_the_limit_with_no_register_left_is_reported():
    result = convert([parse_module(tools_beyond(3))], config(limits={"UTOOL": 3, "PR": 1}))  # PR[1]: scratch
    utool = next(c for c in result.capacity if c.resource == "UTOOL")
    assert not utool.fits and utool.over == ("t3",)  # no register to keep it in: as before, flagged
    (over,) = [n for n in result.notes if n.category == Blocker.CAPACITY]
    assert "above the configured limit of 3" in over.message and over.kind == "WARNING"


def test_a_conversion_that_fits_reports_no_capacity_problem():
    result = convert([parse_module(tools_beyond(3))], config(limits={"UTOOL": 10}))
    assert all(c.fits for c in result.capacity)
    assert not [n for n in result.notes if n.category == Blocker.CAPACITY]


def test_a_resource_without_a_configured_limit_is_not_checked():
    result = convert([parse_module(tools_beyond(3))], config(limits={}))
    assert result.capacity == []


def test_limits_come_from_the_mapping_file(tmp_path):
    mapping = tmp_path / "map.json"
    mapping.write_text('{"limits": {"utool": 2}}', encoding="utf-8")
    cfg = ConversionConfig.from_mapping_file(mapping, timestamp=datetime(2026, 1, 1))
    assert cfg.limits["UTOOL"] == 2
    assert cfg.limits["UFRAME"] == 9  # untouched keys keep their default
    result = convert([parse_module(tools_beyond(3))], cfg)
    assert [f.rapid_name for f in result.utools if f.bank] == ["t1", "t2", "t3"]  # past UTOOL 1, kept for them


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def test_the_report_leads_with_the_summary():
    result = convert([parse_module(tools_beyond(3))], config(limits={"UTOOL": 3, "PR": 1}))
    text = build_report(result, config(), ["m.mod"])
    assert text.index("## Summary") < text.index("## Programs") < text.index("## Items to review")
    assert "### Controller capacity" in text
    assert "**over by 1:** t3" in text


def test_the_summary_ranks_blockers_by_share():
    result = run("Access_A 1;\nAccess_A 2;\nAccess_A 3;\nGOTO done;")
    text = build_report(result, config(), ["m.mod"])
    table = text[text.index("### What is blocking") : text.index("## Programs")]
    rows = [line for line in table.splitlines() if line.startswith("| ")][1:]  # [0] is the header
    assert rows[0].startswith(f"| {Blocker.CALL_ARGS} | 3 | 75 % |")
    assert rows[1].startswith(f"| {Blocker.rapid('GOTO')} | 1 | 25 % |")


# ---------------------------------------------------------------------------
# Payload: FANUC keeps it apart from the tool frame, so it must not vanish
# ---------------------------------------------------------------------------


def test_every_tool_load_is_reported():
    """RAPID loaddata [mass, cog, aom, ix, iy, iz] used to be read, then dropped."""
    result = run("MoveJ pHome,v100,fine,tGrip;", HOME + TOOL)
    [tool] = result.payloads()
    load = tool.frame.load
    assert (tool.rapid_name, load.mass, load.cog) == ("tGrip", 2.4, (0, 0, 90))
    report = build_report(result, config(), ["m.mod"])
    assert "### Payloads to set up (PAYLOAD)" in report
    assert "| 1 | tGrip | 2.4 | 0, 0, 9 | 0, 0, 0 |  |" in report  # cm, kgf.cm.s2: the FANUC screen's units


def test_tool0_and_placeholder_loads_are_not_payloads():
    """tool0 and load0 carry RAPID's 1 g placeholder: nothing to set up."""
    light = "PERS tooldata tPen:=[TRUE,[[0,0,50],[1,0,0,0]],[0.001,[0,0,0.001],[1,0,0,0],0,0,0]];"
    result = run("MoveJ pHome,v100,fine,tool0;\nMoveJ pHome,v100,fine,tPen;", HOME + light)
    assert result.payloads() == []
    assert "### Payloads" not in build_report(result, config(), ["m.mod"])


def test_a_tool_built_at_run_time_has_an_unknown_load_and_says_so():
    result = run("MoveJ pHome,v100,fine,tRuntime;", HOME + "PERS tooldata tRuntime;")
    assert [t.rapid_name for t in result.unknown_payloads()] == ["tRuntime"]
    assert "tool built at run time: load unknown too" in build_report(result, config(), ["m.mod"])


def test_rotated_inertia_axes_are_pointed_out():
    tool = "PERS tooldata tArm:=[TRUE,[[0,0,300],[1,0,0,0]],[12,[40,0,150],[0.7071068,0,0.7071068,0],0.1,0.2,0.3]];"
    report = build_report(run("MoveJ pHome,v100,fine,tArm;", HOME + tool), config(), ["m.mod"])
    assert (
        "| 1 | tArm | 12 | 4, 0, 15 | 1.0197, 2.0394, 3.0591 |"
        " inertia given about the load's own axes (aom), not the flange's |"
    ) in report


def test_a_malformed_load_does_not_cost_the_tool_frame():
    tool = "PERS tooldata tOdd:=[TRUE,[[0,0,120],[1,0,0,0]],[1,[0,0,1]]];"
    result = run("MoveJ pHome,v100,fine,tOdd;", HOME + tool)
    [frame] = result.utools
    assert frame.frame is not None and frame.frame.load is None and not frame.problem


# ---------------------------------------------------------------------------
# Frames the programs calibrate themselves
# ---------------------------------------------------------------------------


def test_a_calibrated_tool_is_read_at_its_value_saved_in_the_backup():
    """A routine measures the tool and writes the PERS: the backup holds the last value, the one in use."""
    calibrate = "PROC Calibrate()\n  tGrip.tframe.trans.z:=190;\nENDPROC"
    result = run("MoveJ pHome,v100,fine,tGrip;", HOME + TOOL, extra_procs=calibrate)
    (tool,) = result.utools
    assert tool.frame is not None and tool.frame.pose.pos == (0, 0, 185.5) and tool.frame.saved == ("tGrip",)
    assert [t.rapid_name for t in result.payloads()] == ["tGrip"]  # its load comes back with it
    (warning,) = [n for n in result.notes if n.category == Blocker.SAVED_FRAME]
    assert warning.message.startswith("tool tGrip: value as saved in the backup")
    assert "| 1 | tGrip | 0.000, 0.000, 185.500 | 0.000, 0.000, 0.000 | value saved in the backup" in build_report(
        result, config(), ["m.mod"])  # fmt: skip


def test_a_var_frame_set_at_run_time_stays_unknown():
    """A VAR is reset at every start: its declared value is not the one the robot runs with."""
    tool = "VAR tooldata tVar:=[TRUE,[[0,0,100],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];"
    result = run("tVar.tframe.trans.z:=120;\nMoveJ pHome,v100,fine,tVar;", HOME + tool)
    (frame,) = result.utools
    assert frame.frame is None and "assigned at run time" in frame.problem
    assert not [n for n in result.notes if n.category == Blocker.SAVED_FRAME]


def test_a_controller_with_more_frames_selects_them_directly():
    # $SCR.$MAXNUMUTOOL raised at a Controlled Start, and the same number under limits: no register.
    result = convert([parse_module(tools_beyond(3))], config(limits={"UTOOL": 4, "PR": 100}))
    assert not any(f.bank for f in result.utools)
    note = convert([parse_module(tools_beyond(3))], config(limits={"UTOOL": 3, "PR": 100})).notes
    assert any("Controlled Start ($SCR.$MAXNUMUTOOL)" in n.message for n in note if n.category == Blocker.CAPACITY)
