# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""FOR bounds, run on ROBOGUIDE (tools/make_for_bound_probe.py): each loop turns as in RAPID, the one whose bound
is left to the integrator not at all until the line setting it replaces the jump, then three times.
tests/fixtures/probes/forbound/results holds the register dumps of both runs."""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES
from test_arg_probe import read_numreg

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_for_bound_probe import DEFAULT, EXPECTED_SET, MODULE, PROGRAM, SET, conversion, registers, set_text

PROBE = FIXTURES / "probes" / "forbound"


def test_the_probe_files_are_those_the_generator_writes():
    result = conversion()
    assert (PROBE / "ForBoundProbe.mod").read_bytes() == MODULE.encode("ascii")
    program = next(i.program for i in result.programs if i.program.name == PROGRAM)
    assert (PROBE / f"{PROGRAM}.LS").read_bytes() == write_ls(program).encode("ascii")
    assert {path.stem for path in PROBE.glob("*.LS")} == {PROGRAM, SET}
    assert (PROBE / f"{SET}.LS").read_bytes() == set_text(result).encode("ascii")


def test_one_bound_is_left_to_the_integrator_and_the_others_are_written():
    result = conversion()
    assert [(g.what, g.slot[0]) for g in result.gated] == [("FOR", "R")]
    assert sum(1 for n in result.notes if n.kind == "TODO") == 1


@pytest.mark.parametrize(("dump", "expected"), [("numreg_default.va", DEFAULT), ("numreg_set.va", EXPECTED_SET)])
def test_the_controller_turns_each_loop_as_rapid(dump, expected):
    path = PROBE / "results" / dump
    if not path.exists():
        pytest.skip("FOR-bound probe not run on ROBOGUIDE yet")
    values = read_numreg(path.read_text(encoding="utf-8"))
    numbers = registers(conversion())
    assert {name: values[numbers[name]] for name in expected} == expected
