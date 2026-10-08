# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""CrossArm's KAREL programs CA_POSEINV, CA_RELTOOL, CA_DEFFRAME measured on ROBOGUIDE (tools/make_karel_pose_probe.py):
RAPID's PoseInv, RelTool, DefFrame worked out by the probe agree with CrossArm's geometry (which RobotStudio checks:
compute and pose probes), the programs written are the fixture's, and the stored run is as measured."""

import math
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_karel_pose_probe import (
    PROBE,
    Q1,
    Q2,
    Q3,
    RESULT,
    conversion,
    def_frame,
    expected_raw,
    kept,
    pose,
    pose_inv,
    prep_program,
    raw_programs,
    rel_tool,
    verdict,
)

from crossarm.convert.compute import def_frame as crossarm_def_frame
from crossarm.fanuc.ls_writer import write_ls
from crossarm.geometry import Pose


def _same(a: tuple, pos, rot) -> bool:
    return math.dist(a[0], pos) < 1e-9 and abs(abs(sum(x * y for x, y in zip(a[1], rot, strict=True))) - 1) < 1e-12


def test_the_expected_values_are_rapids():
    a = pose((100.0, -50.0, 300.0, 30.0, -20.0, 45.0))
    mine = Pose(a[0], a[1])
    inverse = mine.inverse()
    assert _same(pose_inv(a), inverse.pos, inverse.rot)
    for d, turns in (((10.0, 20.0, 2.5), (30.0, -20.0, 45.0)), ((5.0, 0.0, 0.0), (200.0, 120.0, 0.0))):
        moved = mine.rel_tool(*d, *turns)
        assert _same(rel_tool(a, d, *turns), moved.pos, moved.rot)
    for origin in (1, 2, 3):
        frame = crossarm_def_frame(Q1, Q2, Q3, origin)
        assert _same(def_frame(Q1, Q2, Q3, origin), frame.pos, frame.rot)
    assert set(expected_raw()) == set(range(88, 96))


def test_the_programs_written_are_those_of_the_fixture():
    for program in raw_programs():
        assert write_ls(program) == (PROBE / f"{program.name}.LS").read_bytes().decode("ascii"), program.name
    with tempfile.TemporaryDirectory() as temp:
        result = conversion(Path(temp))
        for name in ("KPCONV", "SETUP_FRAMES"):
            assert (Path(temp) / f"{name}.LS").read_bytes() == (PROBE / f"{name}.LS").read_bytes(), name
    assert write_ls(prep_program(kept(result))) == (PROBE / "KPPREP.LS").read_bytes().decode("ascii")


@pytest.mark.skipif(not RESULT.exists(), reason="KAREL pose probe not run yet")
def test_on_roboguide_the_library_is_rapid_and_the_frames_are_loaded():
    found = dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())
    assert verdict(found) == ""
