# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID interrupts converted to condition monitors, run on ROBOGUIDE: the TRAPs are called as RAPID calls them.

tools/make_interrupt_probe.py converts a module that arms ISignalDO on a rising edge, on a falling edge
and with \\Single, and IPers on a PERS, then drives them, puts one to sleep and wakes it, pulses from a
called routine and deletes them. Each TRAP counts its calls; results/ holds the registers after the run,
to compare with what RAPID does (worked out by hand: the virtual ABB controller has no signals).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_interrupt_probe import EXPECTED, FANUC_RESULT, MODULE, conversion, read_totals

PROBE = FIXTURES / "probes" / "interrupts"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "IntProbe.mod").read_bytes() == MODULE.encode("ascii")
    programs = conversion().programs
    for info in programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")
    assert sorted(p.stem for p in PROBE.glob("*.LS")) == sorted(info.program.name for info in programs)


def test_every_interrupt_of_the_probe_is_converted():
    result = conversion()
    assert result.coverage.percent == 100.0
    conditions = sorted(info.program.name for info in result.programs if info.program.condition)
    assert conditions == ["IDOWN", "IEDGE", "IFALL", "IONCE", "IUP", "IWATCH"]
    assert "CALL TSHARED" in (PROBE / "IUP_T.LS").read_text(encoding="ascii")  # the relay of a shared TRAP
    assert "MONITOR IONCE" not in (PROBE / "TONCE.LS").read_text(encoding="ascii")  # \\Single: not armed again


@pytest.mark.skipif(not FANUC_RESULT.exists(), reason="interrupt probe not run yet")
def test_the_traps_are_called_as_rapid_calls_them():
    assert read_totals(FANUC_RESULT.read_text(encoding="utf-8")) == EXPECTED
