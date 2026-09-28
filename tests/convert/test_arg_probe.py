# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Converted calls with arguments, run on ROBOGUIDE: the registers hold what RAPID computes.

tools/make_arg_probe.py converts a module of calls with num, bool and switch arguments
(negative and decimal values, a switch given or not, arguments passed on, a parameter the
routine changes, a FOR bounded by an argument, a WAIT on one). tests/fixtures/probes/args/
results/numreg_roboguide.va is the controller's register dump after running it.
"""

import re
import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_arg_probe import EXPECTED, MODULE, conversion, registers

PROBE = FIXTURES / "probes" / "args"


def read_numreg(text: str) -> dict[int, float]:
    """NUMREG.VA: '[5] = 1  'nLast'' or '[1,5] = 1.000000e+00' -> {5: 1.0}, read loosely."""
    out = {}
    for match in re.finditer(r"\[(?:1,)?(\d+)\]\s*=\s*(-?\d*\.?\d+(?:[eE][+-]?\d+)?)", text):
        out[int(match.group(1))] = float(match.group(2))
    return out


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "ArgProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_register_dumps_are_read_loosely():
    assert read_numreg("[1] = 9  'nSum'\r\n  [2] = -2.500000e+00  ''\r\n[1,3] = 0.5\r\n") == {1: 9.0, 2: -2.5, 3: 0.5}


@pytest.mark.skipif(not (PROBE / "results").exists(), reason="argument probe not run on ROBOGUIDE yet")
def test_the_controller_computes_what_rapid_computes():
    values = read_numreg((PROBE / "results" / "numreg_roboguide.va").read_text(encoding="utf-8"))
    found = {name: values.get(number) for name, number in registers(conversion()).items()}
    assert found == EXPECTED
