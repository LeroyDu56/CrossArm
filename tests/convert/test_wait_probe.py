# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Waits with a time limit, run on ROBOGUIDE: they do what the RAPID error handler does.

tools/make_wait_probe.py converts waits with a MaxTime in routines whose ERROR handler goes on (TRYNEXT)
or tries again (RETRY) before leaving the routine. WAITTIME times them.
tests/fixtures/probes/waits/results/numreg_roboguide.va is the register dump after running it.
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES
from test_arg_probe import read_numreg

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_wait_probe import EXPECTED, MODULE, WAITED_S, conversion, registers, unit_program

PROBE = FIXTURES / "probes" / "waits"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "WaitProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_the_unit_program_is_the_one_in_the_folder():
    assert (PROBE / "WAITTIME.LS").read_bytes() == write_ls(unit_program()).encode("ascii")
    assert conversion().coverage.percent == 100.0  # the handlers too


@pytest.mark.skipif(not (PROBE / "results").exists(), reason="wait probe not run on ROBOGUIDE yet")
def test_the_controller_does_what_the_handler_does():
    values = read_numreg((PROBE / "results" / "numreg_roboguide.va").read_text(encoding="utf-8"))
    found = {name: values.get(number) for name, number in registers(conversion()).items()}
    assert found == EXPECTED
    # R[41]: a 1 s WAIT, as the timer counts it; R[42]: how long the waits took, the sum of their MaxTime.
    assert values[41] == pytest.approx(1.0, abs=0.05)
    assert values[42] == pytest.approx(WAITED_S, abs=0.2)
