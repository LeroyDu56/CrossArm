# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Frames and points the programs compute: does the converted program put the flange where RAPID does?

tools/make_compute_probe.py converts PROC Path of a module that builds its tool with a FUNC, copies a
uframe, computes a frame with DefFrame three ways, and puts a point together from pose functions.
CrossArm works every value out at conversion time; RobotStudio computes the flanges with the RAPID
itself, ROBOGUIDE measures them after running the converted program (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_compute_probe import (
    ABB_RESULT,
    FANUC_RESULT,
    FLANGE_PR,
    MOVES,
    PROGRAM,
    abb_module,
    compare,
    conversion,
    fanuc_program,
    read_fanuc,
    read_robotstudio,
)

PROBE = FIXTURES / "probes" / "compute"


def test_the_probe_files_are_those_the_generator_writes():
    """Regenerated from the current CrossArm: a change in the conversion shows up here first."""
    module = abb_module()
    assert (PROBE / "ComputeProbe.mod").read_bytes() == module.encode("ascii")
    assert (PROBE / f"{PROGRAM}.LS").read_bytes() == fanuc_program(module).encode("ascii")


def test_every_computed_value_is_kept_once_and_loaded_where_the_rapid_computes_it():
    result, _ = conversion(abb_module())
    assert result.todo_count == 0
    # tBuilt twice, wCopy, wDef three ways; the fourth wDef is the first one again.
    assert [f.number for f in result.computed_frames] == [99, 98, 97, 96, 95, 94]
    assert [len(f.uses) for f in result.computed_frames] == [1, 1, 2, 1, 1, 1]
    text = (PROBE / f"{PROGRAM}.LS").read_text(encoding="ascii")
    assert text.count("UFRAME[2]=PR[97]") == 2


@pytest.mark.skipif(not FANUC_RESULT.exists(), reason="compute probe not run on the controllers yet")
def test_roboguide_puts_the_flange_where_robotstudio_computes_it():
    abb = read_robotstudio(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_fanuc(FANUC_RESULT.read_text(encoding="utf-8"))
    rows = compare(abb, fanuc)
    assert len(rows) == MOVES - 1  # all but the MoveAbsJ, whose flange depends on the robot model
    assert FLANGE_PR + MOVES in fanuc  # the moves after the MoveAbsJ ran: it did too
    assert max(gap for _, gap, _ in rows) < 0.01  # mm: W,P,R written with 3 decimals
    assert max(turn for _, _, turn in rows) < 0.002  # deg
    # DefFrame's three origins: three different frames, the same RobotStudio computes.
    assert len({tuple(round(c) for c in abb[i].pos) for i in (3, 4, 5)}) == 3
