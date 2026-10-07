# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""CrossArm's KAREL library (--karel): fixed programs CA_xxx doing what TP cannot compute.

The TP program stays the main program; a statement TP has no form for is written as a CALL to one of these
programs, given register NUMBERS (`CALL CA_POSEMULT(11,12,13)`): the KAREL program reads its arguments
(GET_TPE_PRM), reads and writes the registers they name, and stops the program with the controller's own
error when one is wrong (ca_lib.kl). The sources (.kl) ship inside the package; a conversion writes the ones
its programs call into the KAREL folder of the output, compiled to .pc by FANUC ktrans when it is installed
(crossarm.fanuc.ktrans). A real robot needs the KAREL option (R632) to run them.

Measured on ROBOGUIDE V10.10 (tools/make_karel_probe.py): a .LS calling a KAREL program the robot does not
have loads, and stops on the CALL when it runs (INTP-222, MEMO-073); arguments written as integer constants
reach GET_TPE_PRM as INTEGER; PR[c] = PR[a] : PR[b] is RAPID's PoseMult.

Adding a program: write ca_<name>.kl here (%INCLUDE ca_lib after its VAR section, arguments read with
ca_reg_arg), add it to PROGRAMS, measure it with a probe, then have the converter write its CALL.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources

LIBRARY = "ca_lib.kl"  # included by every program: needed to compile them, not loaded on the robot
R632 = "KAREL option (R632)"


@dataclass(frozen=True, slots=True)
class KarelProgram:
    name: str  # as TP calls it
    source: str  # its .kl file in this package
    does: str  # what it does, as the report says it
    arguments: str  # its arguments, as the report says them


PROGRAMS = {
    "CA_POSEMULT": KarelProgram("CA_POSEMULT", "ca_posemult.kl", "PR[c] = PR[a] : PR[b], RAPID PoseMult(a, b)",
                                "a, b, c: position register numbers"),
}  # fmt: skip
_CALL = re.compile(r"^CALL (CA_[A-Z0-9_]+)\(")


def source(file: str) -> str:
    """The text of a library file shipped with CrossArm."""
    return resources.files(__name__).joinpath(file).read_text(encoding="ascii")


def called(lines: Iterable[str]) -> list[str]:
    """The library programs these TP lines call, in the order of the library."""
    found = {match[1] for text in lines if (match := _CALL.match(text)) and match[1] in PROGRAMS}
    return [name for name in PROGRAMS if name in found]
