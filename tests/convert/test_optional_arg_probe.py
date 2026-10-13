# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Optional num, bool and string parameters, run on ROBOGUIDE (tools/make_optional_arg_probe.py): each counter as
RAPID leaves it. tests/fixtures/probes/optargs/results holds the register dump."""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES
from test_arg_probe import read_numreg

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_optional_arg_probe import EXPECTED, MODULE, conversion, registers

PROBE = FIXTURES / "probes" / "optargs"


def test_the_probe_files_are_those_the_generator_writes():
    result = conversion()
    assert (PROBE / "OptArgProbe.mod").read_bytes() == MODULE.encode("ascii")
    assert {path.stem for path in PROBE.glob("*.LS")} == {i.program.name for i in result.programs}
    for info in result.programs:
        assert (PROBE / f"{info.program.name}.LS").read_bytes() == write_ls(info.program).encode("ascii")


def test_everything_converts():
    assert not [n for n in conversion().notes if n.kind == "TODO"]


def test_the_controller_counts_as_rapid():
    path = PROBE / "results" / "numreg.va"
    if not path.exists():
        pytest.skip("optional-argument probe not run on ROBOGUIDE yet")
    values = read_numreg(path.read_text(encoding="utf-8"))
    numbers = registers(conversion())
    assert {name: values[numbers[name]] for name in EXPECTED} == EXPECTED
