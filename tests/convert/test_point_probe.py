# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Points passed to routines or read from arrays, run on ROBOGUIDE: the moves go where the moves written out go.

tools/make_point_probe.py converts twelve moves twice: through routines that take a robtarget (the caller
sets a position register, the routine moves to it, Offs as component arithmetic, a point passed on as it
is and with Offs), and written out. results/ holds the poses ROBOGUIDE recorded after every move.
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_point_probe import MODULE, MOVES, RESULT, conversion, gaps, programs, read_poses

PROBE = FIXTURES / "probes" / "points"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "PointProbe.mod").read_bytes() == MODULE.encode("ascii")
    for name, text in programs().items():
        assert (PROBE / f"{name}.LS").read_bytes() == text.encode("ascii")


def test_the_points_go_in_position_registers():
    result, _ = conversion()
    assert result.coverage.percent == 100.0
    assert [a.rapid_name for a in result.point_registers] == ["CROSSARM.POINT", "CROSSARM.TOOLOFFSET", "Lift.pLift",
                                                           "Turn.pTurn", "Twice.pTwice", "PickAt.pPick"]
    text = (PROBE / "TWICE.LS").read_text(encoding="ascii")
    assert "PR[99]=PR[98]" in text and "PR[99,1]=PR[99,1]+30" in text  # passed on, and with Offs()
    ((name, dims, base),) = [(a.name, a.dims, a.base) for a in result.point_arrays]
    assert (name, dims, base) == ("pGrid", (2, 2), 90)  # {r,c} is PR[90 + 2(r-1) + (c-1)]
    assert "R[3:PointIndex]=R[3:PointIndex]+87" in (PROBE / "POINTPROBE.LS").read_text(encoding="ascii")


@pytest.mark.skipif(not RESULT.exists(), reason="point probe not run on ROBOGUIDE yet")
def test_every_move_goes_where_the_move_written_out_goes():
    rows = gaps(read_poses(RESULT.read_text(encoding="utf-8")))
    assert len(rows) == MOVES
    assert max(mm for _, mm, _ in rows) <= 0.01 and max(deg for _, _, deg in rows) <= 0.001
