# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Points the programs work out at run time, kept in position registers, run on ROBOGUIDE: the moves written out.

tools/make_pallet_probe.py converts a palletizing module: a place worked out in two FOR loops with Offs()
of the loop counters (a calculation of several operations and an array), turned on the second layer
with RelTool(), then CRobT() and one of its components changed. ROBOGUIDE runs it and the same moves
with the points written out, and records the faceplate in the world frame after each move (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_pallet_probe import MODULE, MOVES, RESULT, conversion, gaps, programs, read_poses

PROBE = FIXTURES / "probes" / "pallet"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "PalletProbe.mod").read_bytes() == MODULE.encode("ascii")
    for name, text in programs().items():
        assert (PROBE / f"{name}.LS").read_bytes() == text.encode("ascii")


def test_the_points_are_worked_out_in_position_registers():
    result, _ = conversion()
    assert result.coverage.percent == 100.0
    text = (PROBE / "PALLETPROBE.LS").read_text(encoding="ascii")
    for form in ("PR[99]=P[1]", "R[3:Calc1]=R[3:Calc1]*90", "PR[99,1]=PR[99,1]+R[3:Calc1]", "PR[99,6]=(-90)",
                 "PR[97]=LPOS", "PR[97,1]=PR[97,1]+15"):
        assert form in text, form


@pytest.mark.skipif(not RESULT.exists(), reason="pallet probe not run on ROBOGUIDE yet")
def test_every_move_goes_where_the_move_written_out_goes():
    rows = gaps(read_poses(RESULT.read_text(encoding="utf-8")))
    assert len(rows) == MOVES
    assert max(mm for _, mm, _ in rows) <= 0.01 and max(deg for _, _, deg in rows) <= 0.001
