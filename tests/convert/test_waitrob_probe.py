# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""WaitRob \\InPos / \\ZeroSpeed after a move through a zone run on ROBOGUIDE (tools/make_waitrob_probe.py): the
robot stands on the point when the next line runs. tests/fixtures/probes/waitrob/results holds what was read."""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import make_waitrob_probe

PROBE = FIXTURES / "probes" / "waitrob"


def test_the_probe_files_are_those_the_generator_writes():
    for info in make_waitrob_probe.conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii"), info.program.name
    setup = make_waitrob_probe.setup_program()
    assert (PROBE / f"{setup.name}.LS").read_bytes() == write_ls(setup).encode("ascii")
    assert (PROBE / "WaitProbe.mod").read_bytes() == make_waitrob_probe.MODULE.encode("ascii")


def test_each_waitrob_is_a_zero_incremental_fine_move():
    main = (PROBE / "WAITPROBE.LS").read_text(encoding="ascii")
    assert main.count("100mm/sec FINE INC") == 2 and main.count("=LPOS") == 5


def test_the_robot_stands_on_the_point_as_in_rapid():
    if not make_waitrob_probe.RESULT.exists():
        pytest.skip("WaitRob probe not run on ROBOGUIDE yet")
    assert make_waitrob_probe.verdict(make_waitrob_probe.stored()) == ""
