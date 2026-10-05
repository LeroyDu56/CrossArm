# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""SearchL converted to a skip, run on ROBOGUIDE with the input switched through COM as the TCP passes y=150
(tools/make_search_probe.py): the point found where the input switched, a move above it, the search going on
to its point with \\Sup, a pause where RAPID stops with an error. The RobotStudio virtual controller has no
signals: what RAPID does is worked out by hand (EXPECTED).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_search_probe import EXPECTED, MODULE, RESULT, SPEEDS, TOLERANCE, conversion, read_results, verdict

from crossarm.convert.translate import SKIP_SPEED_MAX

PROBE = FIXTURES / "probes" / "search"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "SearchProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_instruction_of_the_probe_is_converted():
    assert conversion().coverage.percent == 100.0
    assert "L P[2] 50mm/sec FINE Skip,LBL[2],PR[99]=LPOS    ;" in (PROBE / "SPSTOP.LS").read_text(encoding="ascii")


@pytest.mark.skipif(not RESULT.exists(), reason="search probe not run yet")
def test_the_point_found_is_where_the_input_switched():
    found = read_results(RESULT.read_text(encoding="utf-8"))
    for total, expected in EXPECTED.items():
        assert abs(float(found[total]) - expected) <= TOLERANCE[total], total
    assert found["SPEARLY_status"].startswith("paused")


@pytest.mark.skipif(not RESULT.exists(), reason="search probe not run yet")
def test_a_skip_latching_the_position_slows_no_search_converted_down():
    """The controller slows a move with `PR[k]=LPOS` down past a speed: a search faster stays TODO."""
    found = read_results(RESULT.read_text(encoding="utf-8"))
    for speed in SPEEDS:
        plain, latched = float(found[f"speed{speed}_plain"]), float(found[f"speed{speed}_latched"])
        assert (latched >= 0.95 * plain) == (speed <= SKIP_SPEED_MAX), speed
    assert verdict(found)[0]
