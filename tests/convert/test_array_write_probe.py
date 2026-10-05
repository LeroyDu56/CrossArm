# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Arrays of numbers the programs write, run on both controllers: the same totals.

tools/make_array_write_probe.py converts a module filling an array of 3 x 4 in two FOR loops, summing it in
another routine, changing a PERS array at fixed indices, with Incr and at an index worked out, and reading
elements back. RobotStudio runs the RAPID, ROBOGUIDE the converted programs (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_array_write_probe import ABB_RESULT, EXPECTED, FANUC_RESULT, MODULE, conversion, read_totals

PROBE = FIXTURES / "probes" / "arraywrite"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "ArrayWriteProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_instruction_of_the_probe_is_converted():
    result = conversion()
    assert result.coverage.percent == 100.0
    assert "R[R[3]]=R[4:Calc1]+R[2:j]    ;" in (PROBE / "AWFILL.LS").read_text(encoding="ascii")
    text = (PROBE / "AWPROBE.LS").read_text(encoding="ascii")
    assert "R[186]=R[186]+1    ;" in text  # Incr awTable{3}: its own register
    assert "R[R[3]]=R[R[14]]*2    ;" in text  # awTable{awK+1}:=awTable{awK}*2


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="array write probe not run yet")
def test_both_controllers_compute_the_same_totals():
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    for total, expected in EXPECTED.items():
        assert float(abb[total]) == float(fanuc[total]) == expected
