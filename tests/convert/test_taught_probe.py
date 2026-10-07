# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Positions touched up on ROBOGUIDE kept through a new conversion (tools/make_taught_probe.py): the point touched up
and unchanged in the backup is reached where it was taught, the point changed in the backup where the backup now
puts it; the program read back as .LS or as .TP (PrintTP) gives the same points."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_taught_probe import PROBE, RESULT, TOUCH, conversion, program, touch_helper, verdict

from crossarm.fanuc.ls_writer import write_ls


def test_the_programs_written_are_those_of_the_fixture():
    result, _ = conversion(1)
    programs = [program(result), *(touch_helper(result, source) for source in TOUCH)]
    for prog in programs:
        assert write_ls(prog) == (PROBE / "v1" / f"{prog.name}.LS").read_bytes().decode("ascii")


@pytest.mark.skipif(not RESULT.exists(), reason="taught probe not run yet")
def test_on_roboguide_the_taught_point_is_kept_and_the_changed_one_is_theoretical():
    lines = RESULT.read_text(encoding="ascii").splitlines()
    assert verdict(lines) == ""
    assert "tp_route same points" in lines
    assert "printtp_left_program no" in lines  # PrintTP deletes the program of the same name in the open cell
