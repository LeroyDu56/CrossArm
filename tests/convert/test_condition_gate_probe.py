# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Conditions left to the integrator, run on ROBOGUIDE (tools/make_condition_gate_probe.py): as CrossArm writes
them, nothing of the instructions runs; with each jump replaced by the line setting the flag, the blocks the
conditions select run. tests/fixtures/probes/condgate/results holds the register dumps of both runs."""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES
from test_arg_probe import read_numreg

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_condition_gate_probe import DEFAULT, EXPECTED_SET, MODULE, PROGRAM, SET, conversion, registers, set_text

PROBE = FIXTURES / "probes" / "condgate"


def test_the_probe_files_are_those_the_generator_writes():
    result = conversion()
    assert (PROBE / "CondGateProbe.mod").read_bytes() == MODULE.encode("ascii")
    for info in result.programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")
    assert {path.stem for path in PROBE.glob("*.LS")} == {PROGRAM, SET, "CA_TEXT"}
    assert (PROBE / f"{SET}.LS").read_bytes() == set_text(result).encode("ascii")


def test_each_instruction_is_written_with_its_condition_left_to_set():
    result = conversion()
    assert [g.slot[0] for g in result.gated] == ["F", "F", "F", "F", "R"]
    assert sum(1 for n in result.notes if n.kind == "TODO") == 5


@pytest.mark.parametrize(("dump", "expected"), [("numreg_default.va", DEFAULT), ("numreg_set.va", EXPECTED_SET)])
def test_the_controller_runs_what_the_conditions_select(dump, expected):
    path = PROBE / "results" / dump
    if not path.exists():
        pytest.skip("condition-gate probe not run on ROBOGUIDE yet")
    values = read_numreg(path.read_text(encoding="utf-8"))
    numbers = registers(conversion())
    assert {name: values[numbers[name]] for name in expected} == expected
