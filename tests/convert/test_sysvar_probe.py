# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The system-variable probe (tools/make_sysvar_probe.py): its programs are the fixture's, and what CrossArm says of
GetSysData and OpMode() is what it measured."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_sysvar_probe import PROBE, READS, REFUSAL, programs

from crossarm.convert.unsupported import why_none
from crossarm.fanuc.ls_writer import write_ls


def test_the_programs_written_are_those_of_the_fixture():
    for program in programs():
        assert write_ls(program) == (PROBE / f"{program.name}.LS").read_bytes().decode("ascii"), program.name
    assert {"$MNUTOOLNUM[1]", "$MSKKEY"} <= set(READS.values())


def test_the_reasons_given_name_the_measured_refusal():
    for name in ("GETSYSDATA", "OPMODE"):
        assert REFUSAL in why_none(name)
