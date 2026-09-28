# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Frames past the controller's limit, kept in position registers and loaded before use, run on ROBOGUIDE.

tools/make_bank_probe.py converts the pose probe's 16 moves for a controller of 2 tool frames and
1 user frame: two tools and both work objects go through a register, in turn. The flanges ROBOGUIDE
records must be those RobotStudio computed for the pose probe (tests/fixtures/probes/pose/results).
"""

import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_writer import write_ls

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_bank_probe import DONE, MARKER, conversion, program
from make_pose_probe import FLANGE_PR, MOVES, compare, read_posreg, read_robotstudio
from test_arg_probe import read_numreg

PROBE = FIXTURES / "probes" / "banks"
RESULTS = PROBE / "results"
ROBOTSTUDIO = FIXTURES / "probes" / "pose" / "results" / "poseprobe_robotstudio.txt"


def test_the_probe_file_is_the_one_the_generator_writes():
    assert (PROBE / "BANKPROBE.LS").read_bytes() == write_ls(program()).encode("ascii")


def test_the_probe_goes_through_the_registers():
    result = conversion()
    banked = {f.rapid_name: (f.bank, f.slot) for f in [*result.utools, *result.uframes] if f.bank}
    assert set(banked) == {"tProbeB", "tProbeC", "wProbe1", "wProbe2"}
    text = write_ls(program())
    assert text.count("UTOOL[2]=PR[") >= 8 and text.count("UFRAME[1]=PR[") >= 8


@pytest.mark.skipif(not RESULTS.exists(), reason="bank probe not run on ROBOGUIDE yet")
def test_frames_loaded_from_registers_put_the_flange_where_rapid_does():
    abb = read_robotstudio(ROBOTSTUDIO.read_text(encoding="utf-8", errors="replace"))
    fanuc = read_posreg((RESULTS / "posreg_roboguide.va").read_text(encoding="utf-8", errors="replace"))
    # A real run, not the pose probe's values left in the same registers: the marker, and the banked frames.
    assert read_numreg((RESULTS / "numreg_roboguide.va").read_text(encoding="utf-8"))[MARKER] == DONE
    for frame in [*conversion().utools, *conversion().uframes]:
        if frame.bank is not None and frame.frame is not None:
            x, y, z = frame.frame.pose.pos
            assert fanuc[frame.bank][:3] == pytest.approx((x, y, z), abs=0.01), frame.rapid_name
    rows = compare(abb, fanuc)
    assert len(rows) == len(MOVES), f"moves missing on ROBOGUIDE: PR[{FLANGE_PR + 1}..] not all set"
    bad = [(i, round(gap, 3), round(turn, 3)) for i, gap, turn in rows if gap > 0.05 or turn > 0.01]
    assert not bad, f"moves where the flange differs (move, mm, deg): {bad}"
