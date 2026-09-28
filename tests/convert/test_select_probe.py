# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""TEST/CASE converted to SELECT, run on both controllers: the converted program takes the branches RAPID takes.

tools/make_select_probe.py converts a module that runs TEST in the shapes RAPID programs use (several
values on a CASE, negative and decimal values, CASEs that only call a routine or do nothing, with and
without DEFAULT, nested, on a constant, on an argument). Each branch adds its own weight to three
totals: RobotStudio computes them with the RAPID, ROBOGUIDE with the converted programs (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_select_probe import ABB_RESULT, EXPECTED, FANUC_RESULT, MODULE, conversion, read_totals

PROBE = FIXTURES / "probes" / "select"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "SelectProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_test_of_the_probe_is_converted():
    result = conversion()
    assert result.coverage.percent == 100.0
    text = (PROBE / "SELPROBE.LS").read_text(encoding="ascii")
    assert text.count("SELECT ") == 5  # the TEST on a constant keeps its branch only
    assert "=3,CALL SELCOUNT" in text and "=(-1),JMP" in text and "=2.5,JMP" in text


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="select probe not run yet")
def test_both_controllers_take_the_branches_rapid_takes():
    assert read_totals(ABB_RESULT.read_text(encoding="utf-8")) == EXPECTED
    assert read_totals(FANUC_RESULT.read_text(encoding="utf-8")) == EXPECTED
