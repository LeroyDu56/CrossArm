# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Functions provided as TP programs whose results start a calibration, measured on ROBOGUIDE
(tools/make_func_result_probe.py): the programs written are the fixture's, RAPID's semantics worked out by the probe
agree with CrossArm's geometry, and the stored run is as measured."""

import math
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_func_result_probe import (
    CONV,
    PROBE,
    RESULT,
    conversion,
    expected,
    kept,
    prep_program,
    provided_programs,
    verdict,
)

from crossarm.fanuc.ls_writer import write_ls
from crossarm.geometry import Pose


def test_the_programs_written_are_those_of_the_fixture():
    with tempfile.TemporaryDirectory() as temp:
        result = conversion(Path(temp))
        for name in (CONV, "SETUP_FRAMES"):
            assert (Path(temp) / f"{name}.LS").read_bytes() == (PROBE / f"{name}.LS").read_bytes(), name
    for program in [prep_program(kept(result)), *provided_programs()]:
        assert write_ls(program) == (PROBE / f"{program.name}.LS").read_bytes().decode("ascii"), program.name
    text = (PROBE / f"{CONV}.LS").read_text(encoding="ascii")
    assert "CALL XFRFIT(" in text and ",R[" in text and "CALL CA_" not in text  # all TP, no KAREL


def test_the_expected_values_are_crossarms_geometry():
    found = {"FRM1": "1000 -40 800 180 0 180", "FRM2": "1060 40 800 180 0 180"}
    values = expected(found)
    hub = Pose((1030.0, 0.0, 800.0), (0.0, 0.0, 1.0, 0.0))
    seen = hub.compose(Pose((40.0, 30.0, -60.0), (1.0, 0.0, 0.0, 0.0)))
    assert math.dist(seen.pos, values["FRF2"][0]) < 1e-9
    assert values["FRF4"][0][2] == pytest.approx(920.0)  # the tool's z: 2 * 10 + 100 under the flange


@pytest.mark.skipif(not RESULT.exists(), reason="func result probe not run yet")
def test_on_roboguide_the_results_are_where_rapid_puts_them():
    found = dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())
    assert verdict(found) == ""
