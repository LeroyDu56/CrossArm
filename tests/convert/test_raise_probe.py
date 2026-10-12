# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Errors the program raises itself, measured on ROBOGUIDE (tools/make_raise_probe.py): the programs written are the
fixture's, and the stored run gives the values RAPID works out."""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_raise_probe import PROBE, RESULT, conversion, verdict


def test_the_programs_written_are_those_of_the_fixture():
    with tempfile.TemporaryDirectory() as temp:
        conversion(Path(temp))
        written = sorted(p.name for p in Path(temp).glob("*.LS"))
        assert written == sorted(p.name for p in PROBE.glob("*.LS"))
        for name in written:
            assert (Path(temp) / name).read_bytes() == (PROBE / name).read_bytes(), name


@pytest.mark.skipif(not RESULT.exists(), reason="raise probe not run yet")
def test_on_roboguide_the_raised_errors_go_where_rapid_sends_them():
    found = dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())
    assert verdict(found) == ""
