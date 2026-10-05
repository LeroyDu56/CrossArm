# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Data of RECORD types kept field by field, run on both controllers: the same totals.

tools/make_record_probe.py converts a module whose state machine keeps its state in a record, reads a
PERS record no program changes, keeps a record of a routine of its own and copies a record whole; the
speed and zone of its moves are fields of a record. RobotStudio runs the RAPID, ROBOGUIDE the converted
programs and two variants giving the speed and zone from registers (results/).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_record_probe import (
    ABB_RESULT,
    EXPECTED,
    FANUC_RESULT,
    FORMS,
    FORMS_RESULT,
    MODULE,
    PROGRAM,
    VARIANTS,
    conversion,
    read_totals,
)

PROBE = FIXTURES / "probes" / "records"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "RecordProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_instruction_of_the_probe_is_converted():
    result = conversion()
    assert result.coverage.percent == 100.0
    text = (PROBE / "RECPROBE.LS").read_text(encoding="ascii")
    assert "SELECT R[2:recCtrl.state]=0,CALL RECSTEPA" in text  # the state machine's state, a register
    assert "F[3]=(F[2])" in text  # a record copied whole: its bool field from the other's flag
    assert "L P[3] 400mm/sec FINE" in text  # the speed RecInit sets once
    assert "R[3:RECCOUNT.tallyNo]=0" in (PROBE / "RECCOUNT.LS").read_text(encoding="ascii")  # set at each call


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="record probe not run yet")
def test_both_controllers_compute_the_same_totals():
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    for total, expected in EXPECTED.items():
        assert float(abb[total]) == expected
        for program in (PROGRAM, *VARIANTS):  # the speed and zone as constants, then from registers
            assert float(fanuc[f"{program}.{total}"]) == expected


@pytest.mark.skipif(not FANUC_RESULT.exists(), reason="record probe not run yet")
def test_the_moves_take_the_same_time_whether_the_speed_is_a_constant_or_a_register():
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    for total in ("nTime", "nTime2"):
        times = [float(fanuc[f"{program}.{total}"]) for program in (PROGRAM, *VARIANTS)]
        assert max(times) - min(times) <= 0.01


@pytest.mark.skipif(not FORMS_RESULT.exists(), reason="record probe not run yet")
def test_the_controller_refuses_a_string_literal_in_a_string_register_and_a_string_comparison():
    outcome = read_totals(FORMS_RESULT.read_text(encoding="utf-8"))
    assert set(outcome) == set(FORMS)
    refused = {name for name, verdict in outcome.items() if verdict != "loaded"}
    assert refused == {"RECF_STR_LIT", "RECF_STR_IF"}
