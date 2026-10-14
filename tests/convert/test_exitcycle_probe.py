# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""ExitCycle by CA_EXITCYCLE run on ROBOGUIDE (tools/make_exitcycle_probe.py): the program aborted and run again from
its first line, from a TRAP and in line. tests/fixtures/probes/exitcycle/results holds what was read."""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import make_exitcycle_probe

PROBE = FIXTURES / "probes" / "exitcycle"


def test_the_probe_files_are_those_the_generator_writes():
    for info in make_exitcycle_probe.conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii"), info.program.name
    setup = make_exitcycle_probe.setup_program()
    assert (PROBE / f"{setup.name}.LS").read_bytes() == write_ls(setup).encode("ascii")
    assert (PROBE / "ExitProbe.mod").read_bytes() == make_exitcycle_probe.MODULE.encode("ascii")


def test_the_probe_calls_the_library():
    assert "CALL CA_EXITCYCLE(1)" in (PROBE / "LEAVE.LS").read_text(encoding="ascii")
    trap = (PROBE / "TABORT.LS").read_text(encoding="ascii")
    assert "CALL CA_STOPMOVE(1,1)" in trap and "CALL CA_EXITCYCLE(1)" in trap and "PAUSE_REQUEST\t= 2;" in trap


def test_the_controller_runs_the_cycle_again_as_rapid():
    if not make_exitcycle_probe.RESULT.exists():
        pytest.skip("ExitCycle probe not run on ROBOGUIDE yet")
    assert make_exitcycle_probe.verdict(make_exitcycle_probe.stored()) == ""
