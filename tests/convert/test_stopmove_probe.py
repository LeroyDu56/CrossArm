# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""StopMove / StartMove by CA_STOPMOVE run on ROBOGUIDE (tools/make_stopmove_probe.py): the robot stops on its line
while the TRAP's input is on, and in line, then goes on to the same point. tests/fixtures/probes/stopmove/results
holds what was read."""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import make_stopmove_probe

PROBE = FIXTURES / "probes" / "stopmove"


def test_the_probe_files_are_those_the_generator_writes():
    result = make_stopmove_probe.conversion()
    for info in result.programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii"), info.program.name
    setup = make_stopmove_probe.setup_program()
    assert (PROBE / f"{setup.name}.LS").read_bytes() == write_ls(setup).encode("ascii")
    assert (PROBE / "StopProbe.mod").read_bytes() == make_stopmove_probe.MODULE.encode("ascii")


def test_the_probe_calls_the_library():
    main = (PROBE / "STOPPROBE.LS").read_text(encoding="ascii")
    assert "CALL CA_STOPMOVE(1,0)" in main and "CALL CA_STOPMOVE(0,0)" in main
    trap = (PROBE / "TSTOPA.LS").read_text(encoding="ascii")
    assert "CALL CA_STOPMOVE(1,1)" in trap and "PAUSE_REQUEST\t= 2;" in trap
    assert "CALL CA_STOPMOVE(0,1)" in (PROBE / "STOPWAIT.LS").read_text(encoding="ascii")


def test_the_controller_stops_and_goes_on_as_rapid():
    if not make_stopmove_probe.RESULT.exists():
        pytest.skip("StopMove probe not run on ROBOGUIDE yet")
    assert make_stopmove_probe.verdict(make_stopmove_probe.stored()) == ""
