# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Conditions written from the backup's bool functions, run on ROBOGUIDE: they test what RAPID tests.

tools/make_condition_probe.py converts a module whose conditions call bool functions of the shape
RAPID programs commonly use (RobOS() included), negated and nested, plus a negated group next to AND.
tests/fixtures/probes/conditions/results/numreg_roboguide.va is the register dump after running it.
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES
from test_arg_probe import read_numreg

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_condition_probe import EXPECTED, MODULE, conversion, registers

PROBE = FIXTURES / "probes" / "conditions"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "CondProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_condition_of_the_probe_is_converted():
    result = conversion()
    assert result.inlined == {"Ready": 5, "Blocked": 2, "Armed": 2}  # Ready also inside Armed
    assert result.coverage.percent == 100.0


@pytest.mark.skipif(not (PROBE / "results").exists(), reason="condition probe not run on ROBOGUIDE yet")
def test_the_controller_tests_what_rapid_tests():
    values = read_numreg((PROBE / "results" / "numreg_roboguide.va").read_text(encoding="utf-8"))
    found = {name: values.get(number) for name, number in registers(conversion()).items()}
    assert found == EXPECTED
