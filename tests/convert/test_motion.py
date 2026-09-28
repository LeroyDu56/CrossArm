# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Speeds and zones: the profile CrossArm converts with is the one both simulators measured.

tools/probe_motion.py ran the same moves on an IRB 6700 (RobotStudio) and an M-20iD/25 (ROBOGUIDE),
timed on each controller's clock, the TCP read while it moved. tests/fixtures/probes/motion/results/
holds what they measured; here:

  * the profile in crossarm.convert.motion is what those runs fit to;
  * the check, RAPID moves at speeds the fit never saw, converted by CrossArm and run on both robots,
    takes about as long and rounds its corners about as much on each.
"""

import json
import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.convert.config import ConversionConfig
from crossarm.convert.motion import M20ID_25, MotionProfile, abb_cut, corner, fanuc_cut

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import make_motion_probe as probe
import probe_motion

RESULTS = FIXTURES / "probes" / "motion" / "results"


def runs(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))["runs"]


def test_the_probe_files_are_those_the_generator_writes():
    motion = FIXTURES / "probes" / "motion"
    assert (motion / "MotionPrep.mod").read_bytes() == probe.prep_module().encode("ascii")
    module = probe.abb_module()
    assert (motion / "MotionProbe.mod").read_bytes() == module.encode("ascii")
    assert (motion / "MOTIONPROBE.LS").read_bytes() == probe.fanuc_program(module).encode("ascii")
    check = probe.check_module()
    assert (motion / "MotionCheck.mod").read_bytes() == check.encode("ascii")
    assert (motion / "MOTIONCHECK.LS").read_bytes() == probe.check_program(check).encode("ascii")


def test_the_profile_is_what_the_measurements_fit_to():
    fitted = probe_motion.fit(runs("motion_abb.json"), runs("motion_fanuc.json"))
    assert MotionProfile.from_dict(fitted) == M20ID_25
    assert json.loads((RESULTS / "profile.json").read_text(encoding="utf-8")) == fitted


def test_the_joint_reference_depends_on_the_move_but_not_on_the_speed():
    refs = probe_motion.joint_reference(runs("motion_abb.json"), runs("motion_fanuc.json"))
    assert 3700 < min(refs.values()) and max(refs.values()) < 5400
    assert M20ID_25.joint_speed_ref_mm_s == 4500


def test_linear_speeds_carry_over():
    abb, fanuc = runs("motion_abb.json"), runs("motion_fanuc.json")
    for v in (100, 200, 500, 1000):
        assert fanuc[f"linear {v}mm/sec"]["time"] == pytest.approx(abb[f"linear v{v}"]["time"], rel=0.05)


def test_a_rapid_zone_rounds_the_same_at_any_speed_and_a_cnt_more_the_faster():
    abb, fanuc = runs("motion_abb.json"), runs("motion_fanuc.json")
    z10 = [abb[f"corner v{v} z10"]["cut"] for v in (200, 500, 1000)]
    assert max(z10) - min(z10) < 1
    cnt50 = [fanuc[f"corner {v}mm/sec CNT50"]["cut"] for v in (200, 500, 1000)]
    assert cnt50[1] > 2 * cnt50[0] and cnt50[2] > 2 * cnt50[1]


def test_the_check_takes_as_long_and_rounds_as_much_on_both_robots():
    """RAPID speeds the fit never saw (v300, v400, v600), converted by CrossArm, run on both robots."""
    abb, fanuc = runs("check_abb.json"), runs("check_fanuc.json")
    for name, _, moves in probe.CHECK_RUNS:
        a, f = abb[name], fanuc[name]
        assert f["time"] == pytest.approx(a["time"], rel=0.2), name
        if "cut" not in a:
            continue
        kind, _, speed, zone = moves[0]
        found = corner(M20ID_25, kind, float(zone[1:]), float(speed[1:]),
                       float(speed[1:]) if kind == "L" else round(float(speed[1:]) / 45))  # fmt: skip
        if found.capped:  # CNT100 rounds less at that speed: said in the report
            assert f["cut"] < a["cut"], name
        else:
            assert f["cut"] == pytest.approx(a["cut"], abs=1.0), name


def test_between_and_beyond_the_measured_speeds():
    # Between 500 and 1000 mm/s: between the two measured cuts.
    assert fanuc_cut(M20ID_25, "L", 50, 500) < fanuc_cut(M20ID_25, "L", 50, 750) < fanuc_cut(M20ID_25, "L", 50, 1000)
    # Beyond: in proportion to the speed; the ABB side, nearly the same at any speed, is not extrapolated.
    assert fanuc_cut(M20ID_25, "L", 50, 2000) == pytest.approx(2 * fanuc_cut(M20ID_25, "L", 50, 1000))
    assert abb_cut(M20ID_25, "L", 10, 3000) == abb_cut(M20ID_25, "L", 10, 1000)
    assert abb_cut(M20ID_25, "L", 0.3, 500) < abb_cut(M20ID_25, "L", 1, 500)  # z0: below z1


def test_the_smallest_cnt_that_rounds_as_much_is_chosen():
    found = corner(M20ID_25, "L", 10, 500, 500)
    assert not found.capped and found.fanuc_cut >= found.abb_cut > fanuc_cut(M20ID_25, "L", found.cnt - 1, 500)
    slow = corner(M20ID_25, "L", 50, 200, 200)
    assert slow.cnt == 100 and slow.capped and slow.fanuc_cut < slow.abb_cut


def test_a_profile_measured_on_another_robot_comes_in_through_the_mapping_file(tmp_path):
    other = M20ID_25.to_dict() | {"name": "R-2000iC/165F", "joint_speed_ref_mm_s": 3200}
    mapping = tmp_path / "map.json"
    mapping.write_text(json.dumps({"motion_profile": other}), encoding="utf-8")
    config = ConversionConfig.from_mapping_file(mapping)
    assert config.motion_profile.name == "R-2000iC/165F" and config.joint_speed_ref_mm_s == 3200
    mapping.write_text(json.dumps({"motion_profile": other, "joint_speed_ref_mm_s": 3000}), encoding="utf-8")
    assert ConversionConfig.from_mapping_file(mapping).joint_speed_ref_mm_s == 3000  # given: kept
    mapping.write_text('{"zone_mapping": "round"}', encoding="utf-8")
    with pytest.raises(ValueError, match="zone_mapping"):
        ConversionConfig.from_mapping_file(mapping)


def test_corner_passes_are_found_in_the_tcp_samples():
    a, b, c = (probe.POINTS[name] for name in ("pCornerA", "pCornerB", "pCornerC"))
    path = [(0.0, *a), (1.0, b[0] - 3, b[1] + 3, b[2]), (2.0, *c), (3.0, *a), (4.0, b[0] - 1, b[1] + 1, b[2]), (5.0, *c)]
    assert probe_motion.corner_cuts(path) == pytest.approx([3 * 2**0.5, 2**0.5])
