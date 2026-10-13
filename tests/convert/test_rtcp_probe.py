# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A stationary tool and a robot-held work object as the FANUC Remote TCP, run on ROBOGUIDE (tools/make_rtcp_probe.py):
the flange where RAPID puts it, the stationary TCP on RAPID's line and circle in the part, J RTCP refused.
tests/fixtures/probes/rtcp/results holds what was read."""

import sys
import tempfile
from pathlib import Path

import pytest
from helpers import FIXTURES

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import make_rtcp_probe

PROBE = FIXTURES / "probes" / "rtcp"


def test_the_probe_files_are_those_the_generator_writes():
    with tempfile.TemporaryDirectory() as temp:
        result = make_rtcp_probe.conversion(Path(temp))
        for name in ("RTPREP", "RTCONV", "SETUP_FRAMES"):
            assert (PROBE / f"{name}.LS").read_bytes() == (Path(temp) / f"{name}.LS").read_bytes(), name
    assert (PROBE / "RtcpProbe.mod").read_bytes() == make_rtcp_probe.MODULE.encode("ascii")
    from crossarm.fanuc.ls_writer import write_ls

    for program in make_rtcp_probe.raw_programs(result):
        assert (PROBE / f"{program.name}.LS").read_bytes() == write_ls(program).encode("ascii"), program.name


def test_the_moves_are_remote_tcp_moves():
    text = (PROBE / "RTCONV.LS").read_text(encoding="ascii")
    assert "L P[1] 20mm/sec FINE RTCP" in text and "P[3] 20mm/sec FINE RTCP" in text
    assert "J P[1]" in (PROBE / "RTPREP.LS").read_text(encoding="ascii")


def test_the_controller_moves_as_rapid():
    if not make_rtcp_probe.RESULT.exists():
        pytest.skip("remote TCP probe not run on ROBOGUIDE yet")
    assert make_rtcp_probe.verdict(make_rtcp_probe.stored()) == ""
