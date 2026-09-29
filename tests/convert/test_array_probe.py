# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Arrays of numbers indexed at run time, run on both controllers: the converted programs read what RAPID reads.

tools/make_array_probe.py converts a module that reads a CONST table of decimals and negatives, a CONST 2 x 3
table and a PERS table no program changes, in FOR loops, sums, IF conditions, a WHILE and a call given two
elements at once. RobotStudio computes the totals with the RAPID, ROBOGUIDE with the converted programs
after setting the tables in their registers as SETUP_FRAMES does (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_array_probe import ABB_RESULT, EXPECTED, FANUC_RESULT, MODULE, conversion, programs, read_totals

PROBE = FIXTURES / "probes" / "arrays"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "ArrayProbe.mod").read_bytes() == MODULE.encode("ascii")
    for name, text in programs().items():
        assert (PROBE / f"{name}.LS").read_bytes() == text.encode("ascii")


def test_the_tables_are_kept_in_registers_and_two_elements_take_two_index_registers():
    result, _ = conversion()
    assert result.coverage.percent == 100.0
    assert [(a.name, a.base, len(a.values)) for a in result.number_arrays] == [
        ("FEED", 197, 4), ("GRID", 191, 6), ("LIMIT", 188, 3)]
    assert "CALL WEIGH(R[R[5]],R[R[8]])" in (PROBE / "ARRPROBE.LS").read_text(encoding="ascii")


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="array probe not run yet")
def test_both_controllers_read_what_rapid_reads():
    assert read_totals(ABB_RESULT.read_text(encoding="utf-8")) == EXPECTED
    assert read_totals(FANUC_RESULT.read_text(encoding="utf-8")) == EXPECTED
