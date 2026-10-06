# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Jointtargets read on the robot (CJointT), run on both controllers: the same ABB axes.

tools/make_joint_probe.py converts a module that reads the joints after two MoveAbsJ, works with their axes
and goes back to the first reading with another tool selected. RobotStudio runs the RAPID, ROBOGUIDE the
converted program (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_joint_probe import ABB_RESULT, ABB_TOLERANCE, EXPECTED, FANUC_RESULT, MODULE, conversion, read_totals, same

PROBE = FIXTURES / "probes" / "joints"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "JointProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_instruction_of_the_probe_is_converted():
    result = conversion()
    assert result.coverage.percent == 100.0
    text = (PROBE / "JPPROBE.LS").read_text(encoding="ascii")
    for form in ("PR[99]=JPOS    ;", "=180-PR[99,6]    ;", "IF (PR[99,2]>(-30)) THEN ;", "UTOOL_NUM=2 ;\n",
                 "J PR[98] 22% FINE    ;"):  # fmt: skip
        assert form in text


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="joint probe not run yet")
def test_both_controllers_give_the_axes_of_the_targets():
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    for total, expected in EXPECTED.items():
        assert same(fanuc[total], expected), total
        assert same(abb[total], expected, ABB_TOLERANCE), total
