# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Bools set to a condition, kept in flags, run on both controllers: the same totals.

tools/make_flag_probe.py converts a module setting bools to comparisons, AND, NOT, another bool and a
comparison of texts, and looping on a bool set at each turn. RobotStudio runs the RAPID, ROBOGUIDE the
converted programs (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_flag_probe import ABB_RESULT, EXPECTED, FANUC_RESULT, MODULE, conversion, read_totals

PROBE = FIXTURES / "probes" / "flags"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "FlagProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_instruction_of_the_probe_is_converted():
    result = conversion()
    assert result.coverage.percent == 100.0
    text = (PROBE / "FPPROBE.LS").read_text(encoding="ascii")
    assert "F[2]=(R[7:fpA]<5 AND R[8:fpB]>8) ;" in text
    assert "F[3]=(F[1]=OFF) ;" in text  # NOT fpBig


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="flag probe not run yet")
def test_both_controllers_compute_the_same_totals():
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    for total, expected in EXPECTED.items():
        assert float(abb[total]) == float(fanuc[total]) == expected
