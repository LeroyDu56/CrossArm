# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Frames written part by part and copied at run time, measured on ROBOGUIDE (tools/make_frame_field_probe.py): the
programs written are the fixture's, RAPID's semantics worked out by the probe agree with CrossArm's geometry, and the
stored run is as measured."""

import math
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_frame_field_probe import CONV, PROBE, RESULT, conversion, expected, kept, prep_program, verdict

from crossarm.fanuc.ls_writer import write_ls
from crossarm.geometry import Pose


def test_the_programs_written_are_those_of_the_fixture():
    with tempfile.TemporaryDirectory() as temp:
        result = conversion(Path(temp))
        for name in (CONV, "SETUP_FRAMES"):
            assert (Path(temp) / f"{name}.LS").read_bytes() == (PROBE / f"{name}.LS").read_bytes(), name
    assert write_ls(prep_program(kept(result))) == (PROBE / "FFPREP.LS").read_bytes().decode("ascii")
    text = (PROBE / f"{CONV}.LS").read_text(encoding="ascii")
    assert "=UFRAME[1]" in text and "=UTOOL[2]" in text and "CALL CA_POSEMULT" in text
    assert "UFRAME[9]=PR[" in text  # work objects past the controller's limit, loaded from their bank registers


def test_the_expected_values_are_crossarms_geometry():
    found = {"FFM1": "950 -60 820 180 0 -160", "FFM2": "1050 80 780 180 0 180"}
    values = expected(found)
    pallet = Pose((950.0, -60.0, 820.0), values["FFF2"][1])  # the orientation of the point read
    seen = pallet.compose(Pose((40.0, 30.0, -60.0), (1.0, 0.0, 0.0, 0.0)))
    assert math.dist(seen.pos, values["FFF2"][0]) < 1e-9
    assert math.dist(values["FFF4"][0], values["FFF3"][0]) == pytest.approx(30.0)  # the oframe 30 mm along x


@pytest.mark.skipif(not RESULT.exists(), reason="frame field probe not run yet")
def test_on_roboguide_the_frames_are_where_rapid_puts_them():
    found = dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())
    assert verdict(found) == ""
