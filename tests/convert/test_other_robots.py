# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""What holds on another robot, and what CrossArm does about what does not.

CrossArm was first measured on an IRB 6700 and an M-20iD/25. The same probes, run on an R-2000iC/190S:

  * the axis conventions hold: at the same posture the FANUC flange has the ABB flange's orientation,
    and CrossArm's CONFIG is the one the controller computes (tools/check_conventions.py);
  * the J6 turn number at exactly 180, which the controller counts in turn 1, is found from the pose
    (tools/make_boundary_probe.py: every target reached);
  * speeds and zones do not carry over: the R-2000iC's axes are 2.25 times slower for the same TCP path,
    and the same CNT rounds a corner up to 2.4 times more. So CrossArm reads the robot in the FANUC backup
    and takes the profile measured on that series, or says that none was.

The same again on an R-1000iA/80F: conventions and probes hold, its own profile (J 100 % = 3,400 mm/s).
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import pytest
from helpers import FIXTURES, parse_module
from test_summary_text import fanuc_robot, quiet  # noqa: F401 - fixture
from test_translate import run

from crossarm import pipeline
from crossarm.convert import ConversionConfig
from crossarm.convert.configuration import fanuc_config, j6_on_turn_boundary
from crossarm.convert.motion import M20ID_25, R1000IA_80F, R2000IC_190S, MotionProfile, corner, profile_for
from crossarm.fanuc.usage import read_controller, robot_model
from crossarm.geometry import Pose, mat_mul, matrix_to_quat, rot_y, rot_z
from crossarm.summary import WARN, summarize

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import check_conventions
import make_boundary_probe
import make_motion_probe as probe
import probe_motion

MOTION = FIXTURES / "probes" / "motion" / "results"
DOWN = matrix_to_quat(rot_y(180))  # [0,0,1,0]: flange straight down, x backwards


# ---------------------------------------------------------------------------
# Axis conventions on both FANUC robots measured
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("folder", sorted(p.name for p in (FIXTURES / "probes" / "models").iterdir()))
def test_the_conventions_hold_on_every_robot_measured(folder):
    results = check_conventions.check(FIXTURES / "probes" / "models" / folder)
    assert all(ok for ok, _ in results), [text for ok, text in results if not ok]
    assert any("orientation at the same posture" in text for _, text in results)


# ---------------------------------------------------------------------------
# J6 exactly 180: turn 1, as the controller counts it
# ---------------------------------------------------------------------------


def test_j6_on_the_boundary_is_found_from_the_pose():
    ahead = Pose((1300.0, 0.0, 900.0), DOWN)
    assert j6_on_turn_boundary(ahead, (0, 0, 0, 0))
    assert fanuc_config((0, 0, 0, 0), j6_boundary=True) == "N U T, 0, 0, 1"
    turned = Pose((1300.0, 0.0, 900.0), matrix_to_quat(mat_mul(rot_z(0.1), rot_y(180))))
    assert not j6_on_turn_boundary(turned, (0, 0, 0, 0))  # a tenth of a degree off: turn 0 is right
    at_30 = (1300 * math.cos(math.radians(30)), 1300 * math.sin(math.radians(30)), 900.0)
    radial = Pose(at_30, matrix_to_quat(mat_mul(rot_z(30.0), rot_y(180))))
    assert j6_on_turn_boundary(radial, (0, 0, 0, 0))  # along the arm at 30 deg: J6 on 180 too
    off = Pose((1126.0, 650.0, 900.0), radial.rot)  # 29.996 deg: 0.004 deg off, beyond the controller's
    assert not j6_on_turn_boundary(off, (0, 0, 0, 0))
    assert not j6_on_turn_boundary(Pose((0.0, 0.0, 900.0), DOWN), (0, 0, 0, 0))  # above axis 1: undefined
    assert not j6_on_turn_boundary(ahead, (0, 0, 0, 4))  # behind axis 1: the arm points the other way


def test_a_target_straight_down_in_front_gets_turn_1():
    """pHome of the demo, [0,0,1,0] at y = 0: turn 0 there is refused by the controller (MOTN-018)."""
    result = run("MoveJ pHome,v1000,fine,tool0;", "CONST robtarget pHome:=[[600,0,900],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];")
    assert result.programs[0].program.positions[0].value.config == "N U T, 0, 0, 1"


def test_the_boundary_probe_is_what_the_generator_writes_and_was_reached():
    out = FIXTURES / "probes" / "boundary"
    module = make_boundary_probe.abb_module()
    assert (out / "BoundaryProbe.mod").read_bytes() == module.encode("ascii")
    text, configs = make_boundary_probe.fanuc_program(module)
    assert (out / "BOUNDARY.LS").read_bytes() == text.encode("ascii")
    for name, (_, _, _, on_boundary) in make_boundary_probe.TARGETS.items():
        if on_boundary:
            assert configs[name].endswith(", 1"), name
    runs = json.loads((out / "results" / "roboguide.json").read_text(encoding="utf-8"))
    assert runs and all(r["status"] == "done" and r["configs"] == configs for r in runs.values())


# ---------------------------------------------------------------------------
# Speeds and zones: the profile of the target's series
# ---------------------------------------------------------------------------


OTHERS = [(R2000IC_190S, 2000), (R1000IA_80F, 3400)]  # against 4500 on the M-20iD/25


def results(profile: MotionProfile) -> Path:
    return MOTION / profile.name.replace("/", "_")


@pytest.mark.parametrize(("profile", "reference"), OTHERS, ids=lambda v: getattr(v, "name", v))
def test_each_profile_is_what_its_runs_fit_to(profile, reference):
    abb = json.loads((MOTION / "motion_abb.json").read_text(encoding="utf-8"))["runs"]
    fanuc = json.loads((results(profile) / "motion_fanuc.json").read_text(encoding="utf-8"))["runs"]
    assert MotionProfile.from_dict(probe_motion.fit(abb, fanuc, profile.name)) == profile
    assert profile.joint_speed_ref_mm_s == reference


def test_the_same_cnt_rounds_differently_on_each_arm():
    # z10 at 500 mm/s: the R-2000iC's corners are about twice as round by the same CNT.
    assert corner(R2000IC_190S, "L", 10, 500, 500).cnt < corner(M20ID_25, "L", 10, 500, 500).cnt
    # z30 at 1000 mm/s: the R-1000iA's corners are rounder than the M-20iD's by the same CNT.
    assert corner(R1000IA_80F, "L", 30, 1000, 1000).cnt < corner(M20ID_25, "L", 30, 1000, 1000).cnt


@pytest.mark.parametrize(("profile", "reference"), OTHERS, ids=lambda v: getattr(v, "name", v))
def test_the_check_takes_about_as_long_and_rounds_about_as_much(profile, reference):
    abb = json.loads((MOTION / "check_abb.json").read_text(encoding="utf-8"))["runs"]
    fanuc = json.loads((results(profile) / "check_fanuc.json").read_text(encoding="utf-8"))["runs"]
    for name, _, moves in probe.CHECK_RUNS:
        assert fanuc[name]["time"] == pytest.approx(abb[name]["time"], rel=0.3), name
        if "cut" in abb[name]:
            kind, _, speed, zone = moves[0]
            speed = int(speed[1:])
            if corner(profile, kind, int(zone[1:]), speed, speed).capped:  # CNT100: as round as this arm goes
                assert abb[name]["cut"] - 3.5 < fanuc[name]["cut"] < abb[name]["cut"], name
            else:
                assert fanuc[name]["cut"] == pytest.approx(abb[name]["cut"], abs=1.5), name


@pytest.mark.parametrize(("model", "profile", "found"), [
    ("R-2000iC/165F", "R-2000iC/190S", True),  # same series
    ("R-2000iC/190S", "R-2000iC/190S", True),
    ("ARC Mate 120iD", "M-20iD/25", True),  # the same arm under another name
    ("M-20iD/35", "M-20iD/25", True),
    ("R-1000iA/80F", "R-1000iA/80F", True),
    ("LR Mate 200iD/7L", "M-20iD/25", False),  # not measured: the default, and said
])  # fmt: skip
def test_the_profile_follows_the_series_of_the_target_robot(model, profile, found):
    chosen, how = profile_for(model)
    assert (chosen.name, bool(how)) == (profile, found)


def backup_of(folder: Path, model: str) -> Path:
    (folder / "orderfil.dat").write_text(f"! robot options\r\n1A05B-9999-H999 ! {model}\r\n", encoding="ascii")
    return folder


def test_the_robot_is_read_in_the_fanuc_backup(tmp_path):
    assert robot_model([backup_of(tmp_path, "R-2000iC/165F") / "orderfil.dat"]) == "R-2000iC/165F"
    (tmp_path / "dcsvrfy.dg").write_text("DCS verify\r\nRobot: M-20iD/35                 OK \r\n", encoding="ascii")
    assert robot_model([tmp_path / "dcsvrfy.dg"]) == "M-20iD/35"
    assert read_controller([tmp_path]).robot == "R-2000iC/165F"  # the order file first


def test_the_arm_is_told_from_the_software_in_the_order_file(tmp_path):
    """ROBOGUIDE V10 lists the software first, with the same kind of order number."""
    (tmp_path / "orderfil.dat").write_text(
        "! Generated by PCMCIA 10.10270.1\r\n1A05B-2700-H552 ! HandlingTool\r\n1A05B-2700-H521 ! English UIF\r\n"
        "1A05B-2700-R796 ! Ascii Program Loader\r\n1A05B-2700-H803 ! R-2000iC/190S\r\nZ\r\n", encoding="ascii")  # fmt: skip
    assert robot_model([tmp_path / "orderfil.dat"]) == "R-2000iC/190S"
    for arm in ("LR Mate 200iD/7L", "ARC Mate 120iD", "CRX-10iA/L", "M-710iC/50"):
        (tmp_path / "orderfil.dat").write_text(f"1A05B-2700-H552 ! HandlingTool\r\n1A05B-2700-H900 ! {arm}\r\n",
                                               encoding="ascii")  # fmt: skip
        assert robot_model([tmp_path / "orderfil.dat"]) == arm


def test_speeds_and_zones_follow_the_robot_of_the_backup(tmp_path, fanuc_robot):  # noqa: F811
    source = tmp_path / "cell.mod"
    source.write_text("MODULE Cell\nCONST robtarget p:=[[900,100,700],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];\n"
                      "PROC main()\n  MoveJ p,v1000,z10,tool0;\n  MoveL p,v500,fine,tool0;\nENDPROC\nENDMODULE\n", encoding="utf-8")  # fmt: skip
    output = pipeline.run([source, backup_of(fanuc_robot, "R-2000iC/165F")], log=quiet)
    assert output.config.motion_profile is R2000IC_190S and output.config.joint_speed_ref_mm_s == 2000
    report = output.tasks[0].report_html.read_text(encoding="utf-8")
    assert "measured on the R-2000iC/190S, of the same series as the R-2000iC/165F" in report
    assert not [text for level, text in summarize(output).attention if level == WARN and "speeds and zones" in text]


def test_a_robot_nobody_measured_is_said(tmp_path, fanuc_robot):  # noqa: F811
    source = tmp_path / "cell.mod"
    source.write_text("MODULE Cell\nPROC main()\n  Stop;\nENDPROC\nENDMODULE\n", encoding="utf-8")
    output = pipeline.run([source, backup_of(fanuc_robot, "LR Mate 200iD/7L")], log=quiet)
    assert output.config.motion_profile is M20ID_25
    warnings = [text for level, text in summarize(output).attention if level == WARN]
    assert any(text.startswith("Target robot LR Mate 200iD/7L: speeds and zones were measured") for text in warnings)


def test_a_profile_in_the_mapping_file_is_kept_whatever_the_robot(tmp_path, fanuc_robot):  # noqa: F811
    mapping = tmp_path / "map.json"
    mapping.write_text(json.dumps({"motion_profile": M20ID_25.to_dict() | {"name": "measured here"}}), encoding="utf-8")
    source = tmp_path / "cell.mod"
    source.write_text("MODULE Cell\nPROC main()\n  Stop;\nENDPROC\nENDMODULE\n", encoding="utf-8")
    config = ConversionConfig.from_mapping_file(mapping, timestamp=datetime(2026, 1, 1))
    output = pipeline.run([source, backup_of(fanuc_robot, "R-2000iC/165F")], log=quiet, config=config)
    assert output.config.motion_profile.name == "measured here"


def test_parse_module_is_there():  # the helpers the other tests share still import
    assert parse_module("MODULE M\nENDMODULE\n").name == "M"
