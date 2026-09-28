# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""What the desktop window says, tested without a window.

The window only lays out text built by crossarm.summary and crossarm.pipeline.inspect,
so what a user reads — what CrossArm found in their input, what needs attention
first — is checked here, where CI has no display.
"""

import pytest
from test_backup import make_backup

from crossarm import pipeline
from crossarm.convert import ConversionConfig
from crossarm.convert.translate import Blocker
from crossarm.fanuc.usage import read_controller
from crossarm.summary import GOOD, INFO, WARN, describe_controller, describe_source, summarize


@pytest.fixture
def fanuc_robot(tmp_path, fixtures_dir):
    folder = tmp_path / "fanuc_robot"
    folder.mkdir()
    for ls in (fixtures_dir / "fanuc" / "roboguide_export").glob("*.LS"):
        (folder / ls.name).write_bytes(ls.read_bytes())
    return folder


def quiet(_line: str) -> None:
    pass


# ---------------------------------------------------------------------------
# Step 1 and 2: what CrossArm found in the input
# ---------------------------------------------------------------------------


def test_a_backup_is_described_task_by_task(tmp_path):
    info = pipeline.inspect([make_backup(tmp_path / "Cell_2026")])
    assert (info.kind, info.name, info.tasks, info.eio_signals) == ("backup", "Cell_2026", [("T_ROB1", 2), ("T_ROB2", 2)], 1)
    assert describe_source(info) == (
        'ABB backup "Cell_2026": 2 robot tasks, 4 RAPID modules — T_ROB1 (2), T_ROB2 (2).'
        " I/O types read from EIO.cfg (1 signal)."
    )


def test_loose_files_say_what_is_missing(fixtures_dir):
    info = pipeline.inspect([fixtures_dir / "rapid" / "pick_and_place.mod"])
    assert describe_source(info) == (
        "1 RAPID module (pick_and_place). No EIO.cfg: I/O types are guessed from how the programs use them."
    )


def test_a_fanuc_backup_given_with_the_abb_one_is_set_aside(tmp_path, fanuc_robot):
    backup = make_backup(tmp_path / "Cell_2026")
    info = pipeline.inspect([backup, fanuc_robot])
    assert info.fanuc == [fanuc_robot]
    assert info.kind == "backup"  # still read as a backup, not as a pile of loose files


def test_inputs_that_cannot_be_converted_say_why(tmp_path, fanuc_robot):
    with pytest.raises(ValueError, match="add the ABB backup"):
        pipeline.inspect([fanuc_robot])
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no RAPID module"):
        pipeline.inspect([empty])


def test_the_target_robot_is_described(fanuc_robot):
    text = describe_controller(read_controller([fanuc_robot]))
    assert text.startswith("6 programs read. Already in use, left free: ")
    assert "UTOOL 2" in text


# ---------------------------------------------------------------------------
# The result: what to look at first
# ---------------------------------------------------------------------------


def test_a_clean_run_on_a_known_robot_is_all_good(tmp_path, fanuc_robot):
    run = pipeline.run([make_backup(tmp_path / "Cell_2026")], log=quiet, fanuc=[fanuc_robot])
    summary = summarize(run)
    assert (summary.programs, summary.ready, summary.to_review) == (2, 2, 0)
    assert summary.converted == 100.0  # both tasks counted together
    # Both tasks have a main and the robot already has MAIN: both are renamed, and it is said.
    assert [level for level, _ in summary.attention] == [INFO, INFO, GOOD, GOOD]
    # Each robot gets the program that sets its frames (here tool0, used by the programs).
    assert summary.attention[0][1].startswith("SETUP_FRAMES.LS and SETUP_FRAMES_2.LS set the 2 tool and user frames")
    assert summary.attention[1][1].startswith("2 programs renamed")
    assert summary.attention[2][1] == "Nothing to review: every routine was converted."
    assert summary.attention[3][1].startswith("Numbers already used on the FANUC robot were left free")
    assert summary.report is not None and summary.report.name == "crossarm_report.html"


def tool_rack(folder, tools: int, broken: bool = False):
    """One program that needs `tools` tool frames, optionally with a statement the parser cannot read."""
    lines = ["MODULE ToolRack", "CONST robtarget pHome:=[[600,0,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"]
    lines += [f"PERS tooldata t{i}:=[TRUE,[[0,0,{i}],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];" for i in range(tools)]
    lines += ["PROC main()", *(f"  MoveJ pHome,v100,fine,t{i};" for i in range(tools))]
    lines += ["  x := ;"] if broken else []
    lines += ["ENDPROC", "ENDMODULE", ""]
    path = folder / "tool_rack.mod"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def no_register_left() -> ConversionConfig:
    """Frames past the controller's limit are kept in position registers: none left, they are over."""
    config = ConversionConfig()
    config.limits["PR"] = 1
    return config


def test_what_blocks_loading_comes_first(tmp_path):
    run = pipeline.run([tool_rack(tmp_path, 12, broken=True)], log=quiet, config=no_register_left())
    levels = [level for level, _ in summarize(run).attention]
    texts = [text for _, text in summarize(run).attention]
    assert levels[:3] == [WARN, WARN, WARN]
    assert texts[0].startswith("Tool frames (UTOOL): 12 needed, the controller holds 10.")
    assert summarize(run).converted == 92.3  # 12 moves of 13 instructions: the unreadable one is not converted
    # Each demo tool declares 1 kg: nothing in the programs sets it on the robot.
    assert texts[1] == ("Set the payload of 12 tools on the robot (PAYLOAD) before running: "
                        "mass and centre of gravity are in the report.")  # fmt: skip
    assert texts[2] == "1 RAPID statement could not be read and was skipped: listed at the end of the report."
    # The syntax error is said once, not again as the main source of TODO.
    assert not any(Blocker.rapid("SYNTAX_ERROR") in text for text in texts)
    # No target robot: a nudge towards step 2, as information.
    assert texts[-1].startswith("No FANUC backup was given") and levels[-1] == INFO


def test_the_main_source_of_manual_work_is_named(tmp_path):
    source = tmp_path / "calls.mod"
    source.write_text("MODULE M\nPROC main()\n  Lift 1;\n  Lift 2;\n  GOTO x;\nENDPROC\nENDMODULE\n", encoding="utf-8")
    texts = [text for _, text in summarize(pipeline.run([source], log=quiet)).attention]
    assert "Most items to review come from: routine call with arguments (66 %)." in texts


def test_several_tasks_say_which_one(tmp_path):
    backup = make_backup(tmp_path / "Cell_2026")
    for task in ("TASK1", "TASK2"):
        tool_rack(backup / "RAPID" / task / "PROGMOD", 11)
    texts = [text for _, text in summarize(pipeline.run([backup], log=quiet, config=no_register_left())).attention]
    assert any(text.startswith("T_ROB1: Tool frames (UTOOL)") for text in texts)
    assert any(text.startswith("T_ROB2: Tool frames (UTOOL)") for text in texts)


def test_renamed_programs_are_mentioned(tmp_path, fanuc_robot):
    """The robot already has MAIN: the user must not look for a MAIN.LS that is MAIN_2.LS."""
    source = tmp_path / "cell.mod"
    source.write_text("MODULE Cell\n  PROC main()\n    Stop;\n  ENDPROC\nENDMODULE\n", encoding="utf-8")
    texts = [text for _, text in summarize(pipeline.run([source, fanuc_robot], log=quiet)).attention]
    assert "1 program renamed so as not to replace a program of the same name on the robot or in another task:" \
           " listed in the report." in texts  # fmt: skip


def test_frames_kept_in_registers_are_said(tmp_path):
    texts = [text for _, text in summarize(pipeline.run([tool_rack(tmp_path, 12)], log=quiet)).attention]
    assert ("3 tool or user frames past what the controller holds are kept in PR[97] to PR[99] and loaded"
            " before use: keep those registers free, or raise the controller's number of frames and set it under"
            " limits in the mapping file.") in texts  # fmt: skip


def test_corners_rounder_on_the_abb_than_cnt100_are_said(tmp_path):
    source = tmp_path / "slow.mod"
    point = "[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    source.write_text("\n".join([
        "MODULE Slow", f"CONST robtarget pA:=[[600,0,900],{point}", f"CONST robtarget pB:=[[700,0,900],{point}",
        "PROC main()", "  MoveL pA,v200,z50,tool0;", "  MoveL pB,v200,fine,tool0;", "ENDPROC", "ENDMODULE", "",
    ]), encoding="utf-8")  # fmt: skip
    texts = [text for _, text in summarize(pipeline.run([source], log=quiet)).attention]
    assert any(text.startswith("1 zone is rounder on the ABB than CNT100") for text in texts)

