# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Waits with \\MaxTime and \\TimeFlag, run on both controllers: the same flags, about the same time.

tools/make_time_flag_probe.py converts a module waiting on a bool no one sets (the time runs out) and on
one already TRUE, timing each wait. RobotStudio runs the RAPID, ROBOGUIDE the converted programs (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_time_flag_probe import ABB_RESULT, EXPECTED, FANUC_RESULT, MODULE, TIMES, conversion, read_totals

PROBE = FIXTURES / "probes" / "timeflag"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "TimeFlagProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_instruction_of_the_probe_is_converted():
    assert conversion().coverage.percent == 100.0
    assert "F[3]=(R[5:WaitTimer]>=1.5) ;" in (PROBE / "TFPROBE.LS").read_text(encoding="ascii")


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="time flag probe not run yet")
def test_both_controllers_set_the_same_flags_after_about_the_same_time():
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    for total, expected in EXPECTED.items():
        assert float(abb[total]) == float(fanuc[total]) == expected
    for total, seconds in TIMES.items():  # RAPID's WaitUntil checks every 0.1 s
        assert abs(float(abb[total]) - seconds) <= 0.15 and abs(float(fanuc[total]) - seconds) <= 0.15
