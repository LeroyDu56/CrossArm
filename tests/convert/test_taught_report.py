# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""How the reports show the taught positions kept or not (--keep-taught): the page's section, the .md tables, the
checklist's points group, the analysis action, what the window says.

The case has every status: KEEPPROBE as the taught probe left it on the robot (pKeep kept, pMove to touch up again,
pNew new, pPlain theoretical) plus a position added by hand (P[9]); STATION touched up on pA (kept) and pB (moved in
the backup: again), pC gone from the backup, pD new; DEPOSIT not given (not read)."""

import re
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_taught_probe import PROBE, PROGRAM, TARGET, module

from crossarm import pipeline
from crossarm.cli import main
from crossarm.convert.analysis import priority_actions
from crossarm.convert.taught import AGAIN, GONE, KEPT, NEW, NOT_READ, THEORETICAL, Taught, TaughtPoint
from crossarm.fanuc.ls_parser import read_ls
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import CartesianPosition, JointPosition
from crossarm.summary import describe_keep, describe_taught


def station(version: int) -> str:
    b = "[420,60,180]" if version == 2 else "[400,60,180]"
    return "\r\n".join([
        "MODULE Station",
        "    PERS tooldata tGrip:=[TRUE,[[0,0,200],[1,0,0,0]],[3,[0,0,80],[1,0,0,0],0,0,0]];",
        '    PERS wobjdata wTable:=[FALSE,TRUE,"",[[1200,-300,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];',
        f"    CONST robtarget pA:=[[300,0,200],{TARGET}];",
        f"    CONST robtarget pB:=[{b},{TARGET}];",
        *([f"    CONST robtarget pC:=[[500,-40,220],{TARGET}];"] if version == 1 else []),
        *([f"    CONST robtarget pD:=[[520,-80,240],{TARGET}];"] if version == 2 else []),
        f"    CONST robtarget pU1:=[[100,100,300],{TARGET}];",
        "    PROC Station()",
        "        MoveJ pA,v1000,z50,tGrip\\WObj:=wTable;",
        "        MoveL pB,v500,z10,tGrip\\WObj:=wTable;",
        *(["        MoveL pC,v200,fine,tGrip\\WObj:=wTable;"] if version == 1 else []),
        *(["        MoveL pD,v200,fine,tGrip\\WObj:=wTable;"] if version == 2 else []),
        "    ENDPROC",
        "    PROC Deposit()",
        "        MoveL pU1,v500,z10,tGrip\\WObj:=wTable;",
        "    ENDPROC",
        "ENDMODULE",
        "",
    ])  # fmt: skip


@pytest.fixture(scope="module")
def case(tmp_path_factory) -> Path:
    """The earlier conversion (out1), the robot's programs touched up, the backup changed converted again (out2)."""
    base = tmp_path_factory.mktemp("taught_report")
    for version in (1, 2):
        folder = base / f"abb_v{version}"
        folder.mkdir()
        (folder / "KeepProbe.mod").write_bytes(module(version).encode("ascii"))
        (folder / "Station.mod").write_bytes(station(version).encode("ascii"))
    assert main(["convert", str(base / "abb_v1"), "-o", str(base / "out1")]) == 0
    robot = base / "robot"
    robot.mkdir()
    program = read_ls(PROBE / "results" / f"{PROGRAM}.robot.LS")
    program.positions.append(replace(program.positions[0], number=9))  # added by hand on the robot
    (robot / f"{PROGRAM}.LS").write_text(write_ls(program), encoding="ascii", newline="")
    touched = read_ls(base / "out1" / "STATION.LS")
    a, b = touched.positions[0], touched.positions[1]
    touched.positions[0] = replace(a, value=replace(a.value, x=a.value.x + 3.0, z=a.value.z - 4.0))
    touched.positions[1] = replace(b, value=replace(b.value, y=b.value.y + 2.0, r=b.value.r + 1.5))
    (robot / "STATION.LS").write_text(write_ls(touched), encoding="ascii", newline="")
    for out in ("out2", "out3"):  # converted twice: the checklist's ids do not change
        assert main(["convert", str(base / "abb_v2"), "-o", str(base / out), "--keep-taught", str(robot),
                     "--keep-taught", str(base / "out1")]) == 0  # fmt: skip
    return base


def _page(case: Path, out: str = "out2") -> str:
    return (case / out / "crossarm_report.html").read_text(encoding="utf-8")


def _section(page: str, sid: str) -> str:
    return page.split(f'<section id="{sid}">', 1)[1].split("</section>", 1)[0]


def test_the_page_has_a_taught_section_with_a_row_per_point_and_counts_that_filter(case):
    page = _page(case)
    assert page.count('id="taught"') == 1  # the section, not also a heading of the details
    assert '<a href="#taught">Taught positions (2 again)</a>' in page  # the menu
    section = _section(page, "taught")
    for status, n in ((AGAIN, 2), (KEPT, 2), (NEW, 2), (THEORETICAL, 1), (GONE, 1), (NOT_READ, 1)):
        assert f'data-status="{status}"' in section and len(re.findall(f'data-s="{status}"', section)) == n, status
    # by default, all but the points theoretical as before: the first option of the filter
    assert '<select id="t-status" aria-label="Status"><option value="look">All but theoretical as before' in section
    keep = re.search(r'<tr class="st-kept" data-s="kept"><td class="pt">P\[2\] \(was P\[1\]\)</td>.*?</tr>', section)
    assert keep and "<code>pKeep</code>" in keep[0] and "5.0 mm, 2.0 deg" in keep[0]
    assert 'href="#L-KEEPPROBE-' in keep[0]  # its RAPID line in the side-by-side view
    move = re.search(r'<tr class="st-again".*?pMove.*?</tr>', section)
    assert move and "changed in the backup: moved 20.0 mm" in move[0]
    gone = re.search(r'<tr class="st-gone".*?</tr>', section)
    assert gone and "was P[3]" in gone[0] and "<code>pC</code>" in gone[0] and "<td>—</td></tr>" in gone[0]
    # programs folded, those with points to touch up again open
    assert '<details class="tprog" data-p="KEEPPROBE" open>' in section
    assert '<details class="tprog" data-p="DEPOSIT">' in section
    assert "Programs not read on the robot (1)" in section and "<code>DEPOSIT</code>: not among the robot" in section
    assert "Positions on the robot CrossArm did not write (1)" in section and "<code>KEEPPROBE</code>: P[9]" in section
    # the analysis leads there: count, programs, how far the earlier touch-ups are
    analysis = _section(page, "analysis")
    assert "Touch up again the 2 points that changed" in analysis and "<code>KEEPPROBE</code> (1)" in analysis
    assert "the earlier touch-ups are up to" in analysis and 'href="#taught"' in analysis
    assert "Touch up the 4 theoretical points on the robot" in analysis  # 2 new, 1 theoretical, 1 not read


def test_the_md_report_tables_the_points_to_look_at(case):
    text = (case / "out2" / "crossarm_report.md").read_text(encoding="utf-8")
    assert "| `STATION` | P[2] | `pB` | " in text and "| changed in the backup: moved 20.0 mm |" in text
    assert "### Kept as touched up on the robot (check only)" in text and "| `STATION` | P[1] | `pA` | 5.0 mm, 0.0 deg |" in text
    assert "### Gone from the backup" in text and "| `STATION` | was P[3] | `pC` |" in text
    assert "- `KEEPPROBE`: P[9]" in text and "- `DEPOSIT`: not among the robot's programs given" in text
    assert "pPlain" not in text.split("## Taught positions")[1].split("###")[0]  # theoretical: counted only


def _items(page: str) -> dict[str, str]:
    group = page.split('<div class="ckg" id="ck-points">', 1)[1].split('<div class="ckg"', 1)[0]
    return {m[1]: m[2] for m in re.finditer(r'<li data-id="(\w+)">(.*?)</li>', group)}


def test_the_checklist_tells_points_kept_from_points_to_touch_up_again_with_stable_ids(case):
    items = _items(_page(case))
    titles = [re.search(r'class="ckt">(.*?)</label>', body)[1] for body in items.values()]
    assert titles == [
        "KEEPPROBE.LS: 1 point to touch up again", "KEEPPROBE.LS: 2 points to touch up",
        "KEEPPROBE.LS: 1 point kept as touched up: check only",
        "STATION.LS: 1 point to touch up again", "STATION.LS: 1 point to touch up",
        "STATION.LS: 1 point kept as touched up: check only",
        "DEPOSIT.LS: 1 point to touch up", "KEEPPROBE: 1 position on the robot CrossArm did not write",
    ]  # fmt: skip
    again = next(body for body in items.values() if "STATION.LS: 1 point to touch up again" in body)
    assert "P[2] pB: changed in the backup: moved 20.0 mm; the earlier touch-up is" in again
    assert "Theoretical: 1 new, 1 not touched up on the robot yet." in next(
        body for body in items.values() if "KEEPPROBE.LS: 2 points to touch up" in body)
    assert "Theoretical: 1 not compared: program not read on the robot." in next(
        body for body in items.values() if "DEPOSIT.LS" in body)
    assert list(_items(_page(case, "out3"))) == list(items)  # converted again: the same ids, ticks kept


def test_a_program_never_touched_up_keeps_the_ids_it_had_without_keep_taught(case, tmp_path):
    plain = tmp_path / "plain"
    assert main(["convert", str(case / "abb_v2"), "-o", str(plain)]) == 0
    before = _items((plain / "crossarm_report.html").read_text(encoding="utf-8"))
    after = _items(_page(case))
    deposit = [i for i, body in before.items() if "DEPOSIT.LS" in body]
    assert deposit and deposit[0] in after  # all its points theoretical: the same item, its tick kept


def test_the_window_says_what_step_5_found_and_how_many_points_were_kept(case):
    check = pipeline.check_keep([case / "robot", case / "out1"])
    assert (check.programs, check.tp_files, len(check.earlier), check.beside_mapping) == (2, 0, 1, False)
    text, usable = describe_keep(check)
    assert usable and text == "2 robot programs read. Earlier conversion: crossarm_points.json found (7 points)."
    # without the earlier output, found next to the mapping file given back
    check = pipeline.check_keep([case / "robot"], case / "out1" / "crossarm_mapping.json")
    assert check.beside_mapping and "found next to the mapping file of step 3" in describe_keep(check)[0]
    text, usable = describe_keep(pipeline.check_keep([case / "robot"]))
    assert not usable and "No crossarm_points.json of an earlier conversion: add the CrossArm output folder" in text
    # .TP are only counted: PrintTP runs when converting, with the robot of step 4
    tp = case / "robot_tp"
    tp.mkdir(exist_ok=True)
    (tp / "STATION.TP").write_bytes(b"binary")
    check = pipeline.check_keep([tp, case / "out1"])
    assert (check.programs, check.tp_files, check.unread) == (0, 1, {})
    text, usable = describe_keep(check)
    assert not usable and "1 .TP to decode by FANUC PrintTP when converting: choose a ROBOGUIDE robot" in text
    assert describe_keep(check, tp_robot=True)[1]
    # the result panel's line
    run = pipeline.run([case / "abb_v2"], output=case / "out_window", log=lambda line: None,
                       keep=pipeline.KeepTaught([case / "robot", case / "out1"]))  # fmt: skip
    line = describe_taught(run)
    assert line is not None and line.headline == "2 points kept, 2 to touch up again" and line.level == "warn"
    assert line.detail == ("1 program not read on the robot; 1 position on the robot not in the new programs: see"
                           " the report.")  # fmt: skip


def test_deviation_in_degrees_and_for_joint_points():
    cart = CartesianPosition(0.0, 0.0, 0.0, 180.0, 0.0, 0.0, "N U T, 0, 0, 0")
    point = TaughtPoint(KEPT, "M.R", "p", 1, "R", 1, 1, "", cart, cart, replace(cart, x=3.0, y=4.0, r=10.0))
    assert point.deviation() == "5.0 mm, 10.0 deg" and (point.where, point.rapid) == ("P[1]", "p")
    joints = JointPosition((0.0, 10.0, 0.0, 0.0, -90.0, 0.0))
    point = TaughtPoint(KEPT, "M.R", "j", 2, "R", 4, 3, "", joints, joints, JointPosition((0.5, 10, 0, 0, -92.5, 0)))
    assert point.deviation_mm() is None and point.deviation() == "joints up to 2.5 deg"
    assert (point.where, point.rapid) == ("P[4] (was P[3])", "j #2")
    assert TaughtPoint(NEW, "M.R", "n", 1, "R", 2, None, "").deviation() == ""


def test_with_every_point_kept_the_last_action_is_to_check_them():
    from crossarm.convert.translate import ConversionResult, PointInfo, ProgramInfo
    from crossarm.fanuc.tp import Program

    cart = CartesianPosition(0.0, 0.0, 0.0, 180.0, 0.0, 0.0, "N U T, 0, 0, 0")
    result = ConversionResult()
    result.programs = [ProgramInfo(Program("MAIN"), "M", "main", (PointInfo(1, "p", 3, 1, 1, cart),))]
    result.taught = Taught("x", [TaughtPoint(KEPT, "M.main", "p", 1, "MAIN", 1, 1, "", cart, cart, cart)])
    assert "Check the 1 point kept as touched up on the robot" in [a.title for a in priority_actions(result)]
    result.taught = None
    assert any(a.title == "Touch up the 1 point on the robot" for a in priority_actions(result))


def test_without_keep_taught_nothing_of_it_shows(case):
    plain = (case / "out1" / "crossarm_report.html").read_text(encoding="utf-8")
    assert 'id="taught"' not in plain and "Taught positions" not in plain
    shutil.rmtree(case / "out_window", ignore_errors=True)
