# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Points passed by reference (VAR, INOUT robtarget), run on both controllers: the same values.

tools/make_point_ref_probe.py converts a module whose routines change the point they are given and move
there; the caller reads the point back after each CALL. RobotStudio runs the RAPID, ROBOGUIDE the converted
programs (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_point_ref_probe import ABB_RESULT, EXPECTED, FANUC_RESULT, MODULE, conversion, read_totals

PROBE = FIXTURES / "probes" / "pointref"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "PointRefProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_instruction_of_the_probe_is_converted():
    result = conversion()
    assert result.coverage.percent == 100.0
    text = (PROBE / "PRPROBE.LS").read_text(encoding="ascii")
    assert "CALL PRSHIFT    ;\n  14:  PR[97]=PR[99]    ;" in text  # read back after the CALL


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="point reference probe not run yet")
def test_both_controllers_compute_the_same_values():
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    for total, expected in EXPECTED.items():
        assert float(abb[total]) == float(fanuc[total]) == expected
