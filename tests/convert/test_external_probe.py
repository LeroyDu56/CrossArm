# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Calls to programs the integrator provides, measured on ROBOGUIDE (tools/make_external_probe.py): the caller
loads without them and stops on the CALL when it runs (INTP-222); with them, each argument arrives as RAPID passes
it, and the num RAPID reads back comes back through the register CrossArm names."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_external_probe import EXPECTED, PROBE, RESULT, conversion, provided_programs, registers, verdict

from crossarm.fanuc.ls_writer import write_ls


def test_the_probe_calls_the_provided_programs_and_writes_none_of_the_three_routines():
    result = conversion()
    text = write_ls(result.programs[0].program)
    assert "CALL EXTADD(3,(-2.5),1) ;" in text
    assert "CALL EXTLOG('HELLO',R[5:nBack]) ;" in text
    assert "CALL EXTTWICE(R[5:nBack]) ;" in text
    numbers = registers(result)
    assert f"R[5:nBack]=R[{numbers['twice']}:value]" in text


def test_the_programs_written_are_those_of_the_fixture():
    result = conversion()
    for program in [result.programs[0].program, *provided_programs(registers(result))]:
        stored = (PROBE / f"{program.name}.LS").read_bytes().decode("ascii")
        assert write_ls(program) == stored


@pytest.mark.skipif(not RESULT.exists(), reason="external probe not run yet")
def test_on_roboguide_the_caller_loads_alone_and_the_arguments_arrive_as_rapid_passes_them():
    found = dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())
    assert verdict(found) == ""
    assert {name: float(found[name]) for name in EXPECTED} == EXPECTED
