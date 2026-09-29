# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Records passed as their components and nums passed by reference, run on both controllers: the same totals.

tools/make_param_probe.py converts a module that gives a routine two records of the backup's own type,
passes a num by reference to a routine that changes it, and to one that passes it on, and changes
the totals with Incr, Decr, Add and Clear. RobotStudio runs the RAPID, ROBOGUIDE the converted
programs (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_param_probe import ABB_RESULT, EXPECTED, FANUC_RESULT, MODULE, conversion, read_totals

PROBE = FIXTURES / "probes" / "params"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "ParamProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_instruction_of_the_probe_is_converted():
    result = conversion()
    assert result.coverage.percent == 100.0
    text = (PROBE / "PARPROBE.LS").read_text(encoding="ascii")
    assert "CALL WORK(3,.5,1)" in text and "CALL WORK(2,(-1.25),0)" in text  # the components Work reads
    assert "CALL BUMP(R[3:nBack],4)" in text and "R[3:nBack]=R[4:n]" in text  # read back after the CALL


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="parameter probe not run yet")
def test_both_controllers_compute_the_same_totals():
    assert read_totals(ABB_RESULT.read_text(encoding="utf-8")) == EXPECTED
    assert read_totals(FANUC_RESULT.read_text(encoding="utf-8")) == EXPECTED
