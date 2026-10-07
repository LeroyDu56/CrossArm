# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Positions touched up on the robot, kept through a new conversion (crossarm.convert.taught, --keep-taught).

The robot's program of the probe fixture is KEEPPROBE as ROBOGUIDE held it after two touch-ups (pKeep moved and
turned, pMove raised); v1 is the earlier conversion (its crossarm_points.json), v2 the backup changed: pNew first,
pMove moved 20 mm."""

import json
import shutil
import sys
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_taught_probe import PROBE, PROGRAM, conversion, module

from crossarm.cli import main
from crossarm.convert.taught import (
    AGAIN,
    GONE,
    KEPT,
    NEW,
    NOT_READ,
    POINTS_FILE,
    THEORETICAL,
    apply,
    build_points,
    compare,
    read_points,
    read_robot,
    records,
    report_section,
    same,
)
from crossarm.fanuc.ls_parser import read_ls
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.maketp import TpDecoded
from crossarm.fanuc.tp import CartesianPosition, JointPosition

ROBOT_LS = PROBE / "results" / f"{PROGRAM}.robot.LS"


@pytest.fixture
def robot_folder(tmp_path):
    folder = tmp_path / "robot"
    folder.mkdir()
    shutil.copy(ROBOT_LS, folder / f"{PROGRAM}.LS")
    return folder


def statuses(taught) -> dict[str, str]:
    return {p.source: p.status for p in taught.points}


def test_the_points_file_names_each_point_by_its_rapid_and_reads_back_as_written():
    result, _ = conversion(1)
    points = records(result, "files")
    text = build_points(points)
    data = json.loads(text)
    assert data["format"] == 1 and data["task"] == "files"
    assert data["frames"]["uframes"]["wKeep"] == [900.0, 0.0, 400.0, 0.0, 0.0, 0.0]
    first = data["programs"][PROGRAM]["points"][0]
    assert first["P"] == 1 and first["rapid"] == "pKeep" and first["rank"] == 1
    assert first["wobj"] == "wKeep" and first["tool"] == "tKeep" and first["config"] == "N U T, 0, 0, 0"
    stored = (PROBE / "v1" / POINTS_FILE).read_text(encoding="utf-8")
    assert text == stored
    assert build_points(read_points(PROBE / "v1" / POINTS_FILE)) == stored


def test_a_point_written_twice_by_a_routine_gets_a_rank(tmp_path):
    from crossarm.convert import ConversionConfig, convert
    from crossarm.rapid import parse_text

    text = module(1).replace("        MoveL pPlain,v200,fine,tKeep\\WObj:=wKeep;",
                             "        MoveL pPlain,v200,fine,tKeep\\WObj:=wKeep;\r\n"
                             "        MoveL pPlain,v200,fine,tool0;")  # fmt: skip
    parsed = parse_text(text, path="KeepProbe.mod")
    result = convert([parsed.module], ConversionConfig(), sources={"KeepProbe": text})
    ranks = [(r.source, r.rank) for r in records(result).points]
    assert ranks[-2:] == [("pPlain", 1), ("pPlain", 2)]


def test_a_point_touched_up_and_unchanged_keeps_its_taught_value_a_changed_one_is_theoretical(robot_folder):
    robot = read_robot([robot_folder, PROBE / "v1"])
    assert list(robot.programs) == [PROGRAM] and len(robot.earlier) == 1  # v1's .LS are CrossArm's, not the robot's
    result, _ = conversion(2)
    taught = compare(result, robot.earlier[0], robot, "files")
    assert statuses(taught) == {"pNew": NEW, "pKeep": KEPT, "pMove": AGAIN, "pPlain": THEORETICAL}
    keep = taught.of(KEPT)[0]
    assert (keep.number, keep.previous) == (2, 1)  # the P numbers moved: the RAPID names the point
    assert keep.taught == CartesianPosition(104.0, -150.0, 197.0, 180.0, -1e-9, -178.0, "N U T, 0, 0, 0")
    assert keep.deviation_mm() == pytest.approx(5.0)
    move = taught.of(AGAIN)[0]
    assert move.why == "changed in the backup: moved 20.0 mm"
    assert move.written == move.theoretical
    apply(result, taught)
    assert write_ls(result.programs[0].program) == (PROBE / "v2" / f"{PROGRAM}.LS").read_bytes().decode("ascii")
    # what the next conversion compares with stays theoretical
    assert records(result).points[1].value.x == 100.0
    text = report_section(taught, "1 read")
    assert "- 1 kept as touched up on the robot: the program holds the taught value, check only" in text
    assert "### To touch up again" in text
    assert f"| `{PROGRAM}` | P[3] (was P[2]) | `pMove` | 20.6 mm, 0.0 deg | changed in the backup: moved 20.0 mm |" in text
    assert f"| `{PROGRAM}` | P[2] (was P[1]) | `pKeep` | 5.0 mm, 2.0 deg |" in text  # kept: taught vs theoretical
    assert keep.deviation_deg() == pytest.approx(2.0)


def test_a_frame_changed_in_the_backup_makes_its_taught_points_to_touch_up_again(robot_folder):
    robot = read_robot([robot_folder, PROBE / "v1"])
    from crossarm.convert import ConversionConfig, convert
    from crossarm.rapid import parse_text

    text = module(2).replace("[[900,0,400],[1,0,0,0]]", "[[905,0,400],[1,0,0,0]]")
    parsed = parse_text(text, path="KeepProbe.mod")
    result = convert([parsed.module], ConversionConfig(), sources={"KeepProbe": text})
    taught = compare(result, robot.earlier[0], robot, "files")
    keep = next(p for p in taught.points if p.source == "pKeep")
    assert keep.status == AGAIN and keep.why == "work object wKeep changed in the backup (UFRAME)"
    assert statuses(taught)["pPlain"] == THEORETICAL  # not touched up: theoretical anyway


def test_a_point_touched_up_in_another_frame_is_to_touch_up_again(tmp_path):
    text = ROBOT_LS.read_bytes().decode("ascii").replace("UF : 1, UT : 1,\t\tCONFIG : 'N U T, 0, 0, 0',\r\n\tX =   104",
                                                         "UF : 2, UT : 1,\t\tCONFIG : 'N U T, 0, 0, 0',\r\n\tX =   104")  # fmt: skip
    assert "UF : 2" in text
    (tmp_path / f"{PROGRAM}.LS").write_bytes(text.encode("ascii"))
    robot = read_robot([tmp_path, PROBE / "v1"])
    taught = compare(conversion(2)[0], robot.earlier[0], robot)
    keep = next(p for p in taught.points if p.source == "pKeep")
    assert keep.status == AGAIN and keep.why == "touched up in UF 2, UT 1, written in UF 1, UT 1"


def test_without_the_robot_program_points_are_theoretical_gone_and_foreign_ones_listed(robot_folder):
    robot = read_robot([PROBE / "v1"])
    taught = compare(conversion(2)[0], robot.earlier[0], robot)
    assert {p.status for p in taught.points if p.source != "pNew"} == {NOT_READ}
    assert taught.unread == {PROGRAM: "not among the robot's programs given"}
    # v2 converted, v1's points: v1 had a point v2 has not; the robot holds a P CrossArm did not write
    program = read_ls(robot_folder / f"{PROGRAM}.LS")
    program.positions.append(replace(program.positions[0], number=9))
    (robot_folder / f"{PROGRAM}.LS").write_text(write_ls(program), encoding="ascii", newline="")
    robot = read_robot([robot_folder, PROBE / "v1"])
    earlier = robot.earlier[0]
    taught = compare(conversion(1)[0], earlier, robot)
    assert statuses(taught)["pKeep"] == KEPT
    assert taught.foreign == [(PROGRAM, 9)]
    taught = compare(_without("pPlain"), earlier, robot)
    assert [p.source for p in taught.of(GONE)] == ["pPlain"]


def _without(source):
    from crossarm.convert import ConversionConfig, convert
    from crossarm.rapid import parse_text

    text = module(1).replace(f"        MoveL {source},v200,fine,tKeep\\WObj:=wKeep;\r\n", "")
    parsed = parse_text(text, path="KeepProbe.mod")
    return convert([parsed.module], ConversionConfig(), sources={"KeepProbe": text})


def test_tp_programs_are_decoded_by_printtp_or_said_not_read(tmp_path):
    (tmp_path / f"{PROGRAM}.TP").write_bytes(b"binary")
    (tmp_path / "OTHER.TP").write_bytes(b"binary")

    def decode(files, request):
        return TpDecoded({PROGRAM: ROBOT_LS.read_bytes().decode("ascii")}, [("OTHER", "bad file")])

    robot = read_robot([tmp_path], decode=decode)
    assert list(robot.programs) == [PROGRAM] and robot.unread == {"OTHER": ".TP not decoded by FANUC PrintTP: bad file"}
    robot = read_robot([tmp_path], decode=lambda files, request: TpDecoded(problem="FANUC PrintTP (printtp.exe) not found"))
    assert robot.unread[PROGRAM] == ".TP not decoded by FANUC PrintTP: FANUC PrintTP (printtp.exe) not found"


def test_a_zip_of_the_robot_programs_is_read(tmp_path):
    archive = tmp_path / "robot.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.write(ROBOT_LS, f"backup/{PROGRAM}.LS")
    assert list(read_robot([archive]).programs) == [PROGRAM]


def test_the_same_point_is_told_within_the_tolerance_and_with_its_configuration():
    a = CartesianPosition(1.0, 2.0, 3.0, 180.0, 0.0, 180.0, "N U T, 0, 0, 0")
    assert same(a, replace(a, x=1.005, w=-180.0, config="N U T,0,0,0"))
    assert not same(a, replace(a, x=1.02))
    assert not same(a, replace(a, r=179.9))
    assert not same(a, replace(a, config="N U T, 0, 0, 1"))
    assert same(JointPosition((0, 0, 0, 0, -90, 0)), JointPosition((0, 0, 0, 0, -90.004, 0)))
    assert not same(a, JointPosition((0, 0, 0, 0, -90, 0)))


def test_convert_writes_the_points_file_and_keep_taught_keeps_the_touch_ups(tmp_path, robot_folder, capsys):
    v1, v2 = tmp_path / "v1.mod", tmp_path / "v2" / "KeepProbe.mod"
    v1.write_bytes(module(1).encode("ascii"))
    v2.parent.mkdir()
    v2.write_bytes(module(2).encode("ascii"))
    assert main(["convert", str(v1), "-o", str(tmp_path / "out1")]) == 0
    assert (tmp_path / "out1" / POINTS_FILE).is_file()
    assert main(["convert", str(v2), "-o", str(tmp_path / "out2"), "--keep-taught", str(robot_folder),
                 "--keep-taught", str(tmp_path / "out1")]) == 0  # fmt: skip
    out = capsys.readouterr().out
    assert "taught positions: 1 kept, 1 touch up again, 1 new, 1 theoretical" in out
    assert "touch up again: KEEPPROBE P[3] pMove: changed in the backup: moved 20.0 mm" in out
    written = read_ls(tmp_path / "out2" / f"{PROGRAM}.LS")
    assert written.positions[1].value.x == 104.0
    assert "## Taught positions (--keep-taught)" in (tmp_path / "out2" / "crossarm_report.md").read_text(encoding="utf-8")
    # the points file is found next to the mapping file given back
    assert main(["convert", str(v2), "-o", str(tmp_path / "out3"), "--keep-taught", str(robot_folder),
                 "--map", str(tmp_path / "out1" / "crossarm_mapping.json")]) == 0  # fmt: skip
    assert read_ls(tmp_path / "out3" / f"{PROGRAM}.LS").positions[1].value.x == 104.0


def test_keep_taught_without_an_earlier_conversion_says_how_to_make_one(tmp_path, robot_folder, capsys):
    v2 = tmp_path / "KeepProbe.mod"
    v2.write_bytes(module(2).encode("ascii"))
    assert main(["convert", str(v2), "-o", str(tmp_path / "out"), "--keep-taught", str(robot_folder)]) == 2
    assert f"no {POINTS_FILE} of an earlier conversion found" in capsys.readouterr().err
