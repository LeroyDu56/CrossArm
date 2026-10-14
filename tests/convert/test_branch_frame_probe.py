# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A work object's uframe from a pose chosen in the branches of an IF, run on ROBOGUIDE
(tools/make_branch_frame_probe.py): the moves in its copies where RAPID puts the flange.
tests/fixtures/probes/branchframe/results holds what was read."""

import sys
import tempfile
from pathlib import Path

import pytest
from helpers import FIXTURES

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import make_branch_frame_probe

PROBE = FIXTURES / "probes" / "branchframe"


def test_the_probe_files_are_those_the_generator_writes():
    with tempfile.TemporaryDirectory() as temp:
        make_branch_frame_probe.conversion(Path(temp))
        for name in make_branch_frame_probe.PROGRAMS[1:]:
            assert (PROBE / f"{name}.LS").read_bytes() == (Path(temp) / f"{name}.LS").read_bytes(), name
    assert (PROBE / "BranchFrameProbe.mod").read_bytes() == make_branch_frame_probe.MODULE.encode("ascii")


def test_both_branches_write_the_pose_and_karel_turns_it():
    turn = (PROBE / "BFTURN.LS").read_text(encoding="ascii")
    assert turn.count("PR[95,1]=") == 2 and "PR[94,6]=AR[2]" in turn and "CALL CA_POSEMULT(95,94,93)" in turn


def test_the_moves_go_where_rapid_puts_them():
    if not make_branch_frame_probe.RESULT.exists():
        pytest.skip("branch frame probe not run on ROBOGUIDE yet")
    assert make_branch_frame_probe.verdict(make_branch_frame_probe.stored()) == ""
