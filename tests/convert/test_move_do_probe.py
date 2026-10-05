# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""MoveLDO to a fine point is the move, then the output: measured on ROBOGUIDE, the output switches with the
TCP on the point (tools/make_move_do_probe.py)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_move_do_probe import RESULT, program

from crossarm.fanuc.ls_writer import write_ls


def test_the_probe_program_is_a_fine_move_then_the_output():
    lines = write_ls(program()).splitlines()
    index = next(i for i, line in enumerate(lines) if "L P[2] 500mm/sec FINE" in line)
    assert lines[index + 1].endswith("DO[1]=ON ;")


@pytest.mark.skipif(not RESULT.exists(), reason="movedo probe not run yet")
def test_the_output_switches_with_the_tcp_on_the_point():
    found = dict(line.split() for line in RESULT.read_text(encoding="ascii").splitlines())
    assert float(found["distance_mm"]) <= 0.01
