# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Numbers the target controller already uses, and a conversion that leaves them free.

A migration lands on a cell that already has frames, registers and I/O in use.
Given that controller's programs, CrossArm reads which numbers they touch and
numbers the converted programs around them.
"""

import json
import zipfile
from datetime import datetime

import pytest
from helpers import parse_module
from test_ls_parser import JOINT, ls

from crossarm import pipeline
from crossarm.convert import ConversionConfig, convert
from crossarm.convert.translate import Blocker
from crossarm.fanuc.ls_parser import parse_ls
from crossarm.fanuc.usage import is_fanuc_input, read_controller, scan

EXISTING = ls(
    [
        "  UTOOL_NUM=1 ;",
        "  UFRAME_NUM=2 ;",
        "J P[1] 100% FINE    ;",
        "L PR[5:Approach] 500mm/sec FINE Offset,PR[6]    ;",
        "  DO[3]=ON ;",
        "  WAIT DI[7]=ON    ;",
        "  R[10:Count]=R[10:Count]+1    ;",
        "  R[R[4]]=0    ;",
        "  F[2]=(ON) ;",
        "  GO[1]=5 ;",
        "  PR[9]=UFRAME[3]    ;",
        "  !DO[99] mentioned in a remark only ;",
        "  //DO[98]=ON ;",
        "  MESSAGE[see R[97] and DO[96]] ;",
        "  SDO[40]=ON ;",
        "  $MNUFRAME[1,8]=PR[9] ;",
    ],
    JOINT,  # recorded in UF 0, UT 1
)


def used(text: str) -> dict[str, list[int]]:
    usage = scan([parse_ls(text)])
    return {res: sorted(nums) for res, nums in usage.numbers.items()}


def test_every_kind_of_use_is_found():
    found = used(EXISTING)
    assert found["UTOOL"] == [1]  # UTOOL_NUM=1, and P[1] recorded with UT 1
    assert found["UFRAME"] == [0, 2, 3]  # P[1] in UF 0, UFRAME_NUM=2, UFRAME[3] frame register
    assert found["PR"] == [5, 6, 9]  # motion target, motion option, assignment
    assert found["DO"] == [3]
    assert found["DI"] == [7]
    assert found["R"] == [4, 10]  # R[R[4]]: the index register is a use, its target is unknown
    assert found["F"] == [2]
    assert found["GO"] == [1]


def test_comments_messages_and_look_alikes_are_not_uses():
    found = used(EXISTING)
    assert 99 not in found["DO"] and 98 not in found["DO"] and 96 not in found["DO"]  # remark, //, MESSAGE
    assert 97 not in found["R"]  # MESSAGE text
    assert 40 not in found["DO"]  # SDO[40] is a safety output, not DO[40]
    assert 8 not in found["UFRAME"]  # $MNUFRAME is a system variable


def test_programs_using_each_number_are_named():
    usage = scan([parse_ls(EXISTING.replace("/PROG  SAMPLE", "/PROG  MAIN"))])
    assert usage.reserved()["DO"] == {3: ("MAIN",)}
    assert usage.summary() == "UFRAME 2, UTOOL 1, R 2, PR 3, F 1, DO 1, DI 1, GO 1"  # UFRAME 0 left out


# ---------------------------------------------------------------------------
# Reading a controller backup
# ---------------------------------------------------------------------------


@pytest.fixture
def controller(tmp_path):
    folder = tmp_path / "fanuc_backup"
    folder.mkdir()
    (folder / "MAIN.LS").write_bytes(EXISTING.encode("ascii"))
    (folder / "ERRALL.LS").write_bytes(b"alarm history, not a program\r\n")
    return folder


def test_a_backup_folder_is_read_and_non_programs_are_listed(controller):
    usage = read_controller([controller])
    assert usage.programs == ["SAMPLE"]
    assert usage.skipped == [("ERRALL.LS", "not a TP program")]


def test_a_zipped_backup_is_read(controller, tmp_path):
    archive = tmp_path / "fanuc.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.write(controller / "MAIN.LS", "MD/MAIN.LS")
    assert read_controller([archive]).numbers["DO"].keys() == {3}


def test_fanuc_input_is_told_apart_from_rapid(controller, tmp_path, fixtures_dir):
    assert is_fanuc_input(controller)
    assert is_fanuc_input(controller / "MAIN.LS")
    assert not is_fanuc_input(fixtures_dir / "rapid")
    assert not is_fanuc_input(fixtures_dir / "rapid" / "pick_and_place.mod")
    mixed = tmp_path / "mixed"
    mixed.mkdir()
    (mixed / "A.LS").write_text("x")
    (mixed / "B.mod").write_text("x")
    assert not is_fanuc_input(mixed)  # RAPID present: it is a RAPID source


# ---------------------------------------------------------------------------
# Conversion around the taken numbers
# ---------------------------------------------------------------------------

SOURCE = (
    "MODULE M\n"
    "CONST robtarget pHome:=[[600,0,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];\n"
    "PERS tooldata tGrip:=[TRUE,[[0,0,185.5],[1,0,0,0]],[2.4,[0,0,90],[1,0,0,0],0,0,0]];\n"
    "VAR num nCount:=0;\n"
    "PROC main()\nMoveJ pHome,v100,fine,tGrip;\nSet doGrip;\nSet doVac;\nnCount:=nCount+1;\nENDPROC\n"
    "ENDMODULE\n"
)


def run_with(reserved, **mapping):
    cfg = ConversionConfig(timestamp=datetime(2026, 1, 1), reserved=reserved, **mapping)
    result = convert([parse_module(SOURCE)], cfg, routines=["main"], sources={"M": SOURCE})
    text = [getattr(line, "text", "") for line in result.programs[0].program.lines]
    return result, text


def test_automatic_numbers_skip_the_taken_ones():
    result, text = run_with({"DO": {1: ("MAIN",), 2: ("MAIN",)}, "UTOOL": {1: ("MAIN",)}, "R": {1: ()}})
    assert "DO[3]=ON" in text and "DO[4]=ON" in text
    assert "UTOOL_NUM=2" in text
    assert any(t.startswith("R[2:nCount]") for t in text)
    assert not [n for n in result.notes if n.category == Blocker.TAKEN]  # nothing collided


def test_a_pinned_number_on_a_taken_one_is_kept_and_reported():
    """Often intended (the same physical signal on the new cell), so kept; but said."""
    result, text = run_with({"DO": {3: ("MAIN", "PICK")}}, digital_outputs={"DOGRIP": 3})
    assert "DO[3]=ON" in text
    [warning] = [n for n in result.notes if n.category == Blocker.TAKEN]
    assert warning.kind == "WARNING"
    assert "DO[3] is pinned for doGrip but already used on the controller by MAIN, PICK" in warning.message


def test_the_world_frame_is_never_a_collision():
    result, _ = run_with({"UFRAME": {0: ("MAIN",)}})
    assert not [n for n in result.notes if n.category == Blocker.TAKEN]


def test_taken_numbers_count_toward_the_limit():
    """Frames 1 to 9 taken: the next converted tool lands on 10, the one after is over."""
    result, _ = run_with({"UTOOL": {n: () for n in range(1, 10)}}, limits={"UTOOL": 10})
    utool = next(c for c in result.capacity if c.resource == "UTOOL")
    assert (utool.highest, utool.taken, utool.fits) == (10, 9, True)


def test_reserved_numbers_from_the_mapping_file(tmp_path):
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"reserved": {"do": [1, 2, 3]}}), encoding="utf-8")
    cfg = ConversionConfig.from_mapping_file(path, timestamp=datetime(2026, 1, 1))
    assert cfg.reserved == {"DO": {1: (), 2: (), 3: ()}}
    path.write_text(json.dumps({"reserved": {"DO": "1-3"}}), encoding="utf-8")
    with pytest.raises(TypeError, match="list of integers"):
        ConversionConfig.from_mapping_file(path)


# ---------------------------------------------------------------------------
# Pipeline: the FANUC backup dropped next to the ABB one
# ---------------------------------------------------------------------------


def test_fanuc_backup_dropped_with_the_rapid_files_is_recognised(controller, tmp_path, fixtures_dir):
    logs = []
    out = pipeline.run([fixtures_dir / "rapid" / "logic_and_io.mod", controller],
                       tmp_path / "out", log=logs.append)  # fmt: skip
    assert out.controller is not None and out.controller.programs == ["SAMPLE"]
    assert any("Existing FANUC programs: 1 read, 1 other files ignored" in line for line in logs)
    report = (tmp_path / "out" / "crossarm_report.md").read_text(encoding="utf-8")
    assert "| Taken |" in report
    assert "**Taken**" in report


def test_only_fanuc_programs_is_a_clear_error(controller):
    with pytest.raises(ValueError, match="add the ABB backup"):
        pipeline.run([controller], log=lambda _: None)
