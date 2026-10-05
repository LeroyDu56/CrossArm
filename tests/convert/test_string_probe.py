# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Strings kept in string registers, run on both controllers: the same totals.

tools/make_string_probe.py converts a module counting the letters of a text read one character at a time,
running a state machine whose state is a string, looking for texts, writing numbers as texts and passing
texts to a routine. RobotStudio runs the RAPID, ROBOGUIDE the converted programs (results/). Forms loaded
only, and a program written by hand, record what TP does otherwise than RAPID.
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_string_probe import (
    ABB_FACTS,
    ABB_RESULT,
    EXPECTED,
    FACTS_EXPECTED,
    FANUC_RESULT,
    FORMS,
    FORMS_RESULT,
    MODULE,
    STOPPING,
    conversion,
    read_totals,
)

PROBE = FIXTURES / "probes" / "strings"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "StringProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in conversion().programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_every_instruction_of_the_probe_is_converted():
    result = conversion()
    assert result.coverage.percent == 100.0
    text = (PROBE / "STRPROBE.LS").read_text(encoding="ascii")
    assert "IF SR[3]=SR[25],JMP LBL[2]" in text  # WHILE strState<>"DONE"
    assert "R[199:Calc1]=FINDSTR SR[2],SR[25]" in text  # StrMatch
    assert "CALL STRTAKE(SR[5])" in text  # a string passed in its register


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="string probe not run yet")
def test_both_controllers_compute_the_same_totals():
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    for total, expected in EXPECTED.items():
        assert float(abb[total]) == float(fanuc[total]) == expected


@pytest.mark.skipif(not ABB_RESULT.exists() or not FANUC_RESULT.exists(), reason="string probe not run yet")
def test_what_tp_does_otherwise_than_rapid_is_as_measured():
    """TP: 'A' = 'a' but 'A' <> 'A '; FINDSTR regardless of case, 0 for an empty pattern; SR=R of a whole number
    held as a real has six decimals; '12AB' reads as 12. RAPID: compared as they are, StrMatch StrLen+1,
    NumToStr rounds, StrToVal fails on '12AB'. SUBSTR past the end stops the program, as StrPart does RAPID's."""
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    for fact, expected in FACTS_EXPECTED.items():
        assert float(fanuc[f"fact.{fact}"]) == expected
    for fact, expected in ABB_FACTS.items():
        assert abb[fact] == expected
    assert all(fanuc[f"stop.{name}"] == "INTP-323" for name in STOPPING)


@pytest.mark.skipif(not FORMS_RESULT.exists(), reason="string probe not run yet")
def test_the_forms_the_controller_refuses_are_those_crossarm_never_writes():
    found = read_totals(FORMS_RESULT.read_text(encoding="utf-8"))
    assert set(found) == set(FORMS)
    refused = {name for name, outcome in found.items() if outcome.startswith("ASBN-092")}
    assert refused == {"STRF_LIT", "STRF_IFBLOCK", "STRF_IFLIT", "STRF_SELECT", "STRF_ARG39", "STRF_APOS"}
    assert found["STRF_EMPTY"] == "stored CALL CA_TEXT(20,'...',0)"  # hence an empty text from one character
    assert found["STRF_COMMENT"] == "stored SR[20]=SR[21]"  # no comment kept: CrossArm writes none
    assert found["STRF_INT_OVER"] == "stored R[60]=********"  # hence the TODO past 2147483646
