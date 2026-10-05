# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Arrays of bools kept in blocks of flags, run on both controllers: the same totals.

tools/make_flag_array_probe.py converts a module setting a VAR and a PERS array of bools at fixed indices
and at indices known at run time, to conditions of other elements, and counting what is set. RobotStudio
runs the RAPID, ROBOGUIDE the converted programs (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_flag_array_probe import ABB_RESULT, EXPECTED, FANUC_RESULT, MODULE, conversion, read_totals

PROBE = FIXTURES / "probes" / "flagarrays"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "FlagArrayProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_instruction_of_the_probe_is_converted():
    result = conversion()
    assert result.coverage.percent == 100.0
    assert [(a.name, a.base) for a in result.flag_arrays] == [("faSlot", 1019), ("faDone", 1013)]
    text = (PROBE / "FAPROBE.LS").read_text(encoding="ascii")
    assert "F[R[12]]=(F[R[2]]) ;" in text and "F[1020]=(F[1023]=ON AND F[1021]=OFF) ;" in text


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="flag array probe not run yet")
def test_both_controllers_give_the_totals_worked_out_by_hand():
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    for total, expected in EXPECTED.items():
        assert float(abb[total]) == float(fanuc[total]) == expected
