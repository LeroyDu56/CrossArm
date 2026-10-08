# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""FUNCs of the backup copied into each call, measured on ROBOGUIDE (tools/make_func_inline_probe.py): the programs
written are the fixture's, RAPID's semantics worked out by the probe agree with CrossArm's geometry, and the stored
run is as measured."""

import math
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_func_inline_probe import PROBE, PROGRAMS, RESULT, conversion, expected, kept, prep_program, verdict

from crossarm.fanuc.ls_writer import write_ls
from crossarm.geometry import Pose


def test_the_programs_written_are_those_of_the_fixture():
    with tempfile.TemporaryDirectory() as temp:
        result = conversion(Path(temp))
        for name in (*PROGRAMS, "SETUP_FRAMES"):
            assert (Path(temp) / f"{name}.LS").read_bytes() == (PROBE / f"{name}.LS").read_bytes(), name
    assert write_ls(prep_program(kept(result))) == (PROBE / "FIPREP.LS").read_bytes().decode("ascii")
    text = (PROBE / "FIINIT.LS").read_text(encoding="ascii")
    assert "CALL CA_POSEMULT" in text  # the camera's tools: its orientation is only known at run time
    assert ",2]+25" in text and ",3]+40" in text  # the gripper's: its orientation known, moved by TP


def test_the_expected_values_are_crossarms_geometry():
    found = {"FIM1": "950 -60 820 180 0 -160", "FIM2": "1050 80 780 180 0 180"}
    values = expected(found)
    grip = Pose((10.0, 0.0, 140.0), (1.0, 0.0, 0.0, 0.0))
    finger = grip.compose(Pose((0.0, 25.0, 40.0), (1.0, 0.0, 0.0, 0.0)))
    target = Pose((1000.0, 0.0, 700.0), values["FIG"][1])  # the flange's orientation is the target's here
    flange = Pose(target.pos, values["FIF1"][1]).compose(finger.inverse())
    assert math.dist(flange.pos, values["FIF1"][0]) < 1e-6
    assert values["FIF6"][0][2] == pytest.approx(values["FIG"][0][2] + 25.0)  # Shifted: 25 mm along the tool's z


@pytest.mark.skipif(not RESULT.exists(), reason="func inline probe not run yet")
def test_on_roboguide_the_tools_are_where_rapid_puts_them():
    found = dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())
    assert verdict(found) == ""
