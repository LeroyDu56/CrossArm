# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""PulseDO, InvertDO, the clocks and SetAO, converted and run on ROBOGUIDE: they do what RAPID does.

tools/make_io_probe.py converts a module that inverts an output twice, pulses another and reads it
during and after the pulse, times half a second with a clock and sets an analog output with a scale.
tests/fixtures/probes/io/results/ioprobe_roboguide.txt holds the registers after running it.
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_io_probe import MODULE, conversion, matches

PROBE = FIXTURES / "probes" / "io"
RESULT = PROBE / "results" / "ioprobe_roboguide.txt"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "IoProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_instruction_of_the_probe_is_converted():
    text = (PROBE / "IOPROBE.LS").read_text(encoding="ascii")
    for form in ("DO[1]=(!DO[1])", "DO[2]=PULSE,0.5sec", "TIMER[1]=RESET", "R[3:nTime]=TIMER[1]", "AO[1]=250"):
        assert form in text
    assert conversion().coverage.percent == 100.0


@pytest.mark.skipif(not RESULT.exists(), reason="I/O probe not run on ROBOGUIDE yet")
def test_the_controller_does_what_rapid_does():
    found = {}
    for line in RESULT.read_text(encoding="utf-8").splitlines():
        name, value = line.split()
        found[name] = float(value)
    assert matches(found)
