# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""FUNCs of the backup giving a text, written as TP programs, measured on ROBOGUIDE (tools/make_func_text_probe.py):
the programs written are the fixture's, and the stored run gives the values RAPID works out."""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_func_text_probe import FUNCS, LIMIT, PROBE, PROGRAM, RESULT, conversion, verdict


def test_the_programs_written_are_those_of_the_fixture():
    with tempfile.TemporaryDirectory() as temp:
        conversion(Path(temp))
        written = sorted(p.name for p in Path(temp).glob("*.LS"))
        assert written == sorted(p.name for p in PROBE.glob("*.LS") if p.stem != LIMIT)
        for name in written:
            assert (Path(temp) / name).read_bytes() == (PROBE / name).read_bytes(), name
    text = (PROBE / f"{PROGRAM}.LS").read_text(encoding="ascii")
    assert all(f"CALL {name}(" in text for name in FUNCS)  # each FUNC called as a program


@pytest.mark.skipif(not RESULT.exists(), reason="text FUNC probe not run yet")
def test_on_roboguide_the_text_funcs_give_what_rapid_gives():
    found = dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())
    assert verdict(found) == ""
    assert found["R151"] == "152" and "INTP-323" in found["limit_run"]  # 304 characters: Value overflow
