# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The committed configuration probes must match tools/make_config_probes.py."""

import sys
from pathlib import Path

from helpers import FIXTURES, parse_module

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import make_config_probes

PROBES = FIXTURES / "probes"


def test_fanuc_probe_is_up_to_date():
    assert (PROBES / "CFGPROBE.LS").read_bytes().decode("ascii") == make_config_probes.fanuc_probe()


def test_abb_probe_is_up_to_date_and_parses():
    text = (PROBES / "CfgProbe.mod").read_bytes().decode("ascii")
    assert text == make_config_probes.abb_probe()
    module = parse_module(text)
    (table,) = module.declarations
    assert len(table.init.items) == len(make_config_probes.JOINT_SETS)


def test_abb_elbow_probe_is_up_to_date_and_parses():
    text = (PROBES / "ElbowProbe.mod").read_bytes().decode("ascii")
    assert text == make_config_probes.abb_elbow_probe()
    (table,) = parse_module(text).declarations
    assert len(table.init.items) == len(make_config_probes.ELBOW_SWEEP)


def test_the_robotstudio_server_parses():
    """tools/CrossArmServer.mod is loaded by hand in RobotStudio: it must at least be valid RAPID."""
    module = parse_module((Path(__file__).resolve().parents[1] / "tools" / "CrossArmServer.mod").read_text())
    assert {r.name for r in module.routines} == {"main", "Serve", "Drop"}


def test_probes_sent_to_the_server_do_not_stop_it():
    import robotstudio

    for name in ("CfgProbe.mod", "ElbowProbe.mod", "pose/PoseProbe.mod", "pin/PinProbe.mod"):
        served = robotstudio.served_copy((PROBES / name).read_text())
        module = parse_module(served)
        assert module.routines, name
        assert "Stop;" not in [line.strip() for line in served.splitlines()], name
