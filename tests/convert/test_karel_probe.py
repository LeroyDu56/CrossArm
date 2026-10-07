# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""CrossArm's KAREL library called from TP, measured on ROBOGUIDE (tools/make_karel_probe.py): PoseMult of poses
kept in position registers as RAPID computes it, a CALL before the .pc stopping on it, the error cases aborting."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_karel_probe import (
    POSE_A,
    POSE_B,
    POSE_C,
    PROBE,
    RESULT,
    conversion,
    error_programs,
    gap,
    q_from_wpr,
    registers,
    verdict,
)

from crossarm.fanuc.ls_writer import write_ls
from crossarm.geometry import Pose


def test_the_expected_values_are_rapids_posemult():
    """The probe's own quaternion arithmetic agrees with CrossArm's Pose.compose (both RAPID PoseMult)."""
    composed = Pose(POSE_A[0], POSE_A[1]).compose(Pose(POSE_B[0], POSE_B[1]))
    assert math.dist(composed.pos, POSE_C[0]) < 1e-9
    assert abs(abs(sum(a * b for a, b in zip(composed.rot, POSE_C[1], strict=True))) - 1) < 1e-12
    assert gap("100 -50 300 30 -20 45", POSE_A) == pytest.approx((0, 0), abs=1e-5)
    assert q_from_wpr(0, 0, 90) == pytest.approx((math.sqrt(0.5), 0, 0, math.sqrt(0.5)))


def test_the_programs_written_are_those_of_the_fixture():
    result = conversion()
    text = write_ls(result.programs[0].program)
    numbers = registers(result)
    assert f"CALL CA_POSEMULT({numbers['krA']},{numbers['krB']},{numbers['krC']}) ;" in text
    for program in [result.programs[0].program, *error_programs(numbers)]:
        assert write_ls(program) == (PROBE / f"{program.name}.LS").read_bytes().decode("ascii")


@pytest.mark.skipif(not RESULT.exists(), reason="KAREL probe not run yet")
def test_on_roboguide_posemult_is_rapids_and_the_errors_stop_on_the_call():
    found = dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())
    assert verdict(found) == ""
