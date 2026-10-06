# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The .TP FANUC MakeTP makes of CrossArm's .LS, measured on ROBOGUIDE V10.10 (tools/make_maketp_probe.py).

Every program of the probe, SETUP_FRAMES included, was made .TP, loaded and run (the registers RAPID
computes), and decoded back by FANUC PrintTP to the lines of its .LS (results/)."""

import sys
from pathlib import Path

from helpers import FIXTURES

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_maketp_probe import MODULE, body, check, programs

PROBE = FIXTURES / "probes" / "maketp"


def test_the_probe_files_are_those_the_generator_writes():
    assert (PROBE / "MakeTpProbe.mod").read_bytes() == MODULE.encode("ascii")
    texts = programs()
    assert "SETUP_FRAMES" in texts and len(texts) == 4
    for name, text in texts.items():
        assert (PROBE / f"{name}.LS").read_bytes() == text.encode("ascii")


def test_every_tp_loaded_ran_and_decodes_to_the_lines_of_its_ls():
    assert check() == ""
    decoded = (PROBE / "results" / "MTPROBE.printtp.LS").read_text(encoding="ascii")
    assert "CALL MTCOUNT" in decoded and body(decoded) == body((PROBE / "MTPROBE.LS").read_text(encoding="ascii"))
