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
reach GET_TPE_PRM as INTEGER; PR[c] = PR[a] : PR[b] is RAPID's PoseMult. tools/make_karel_pose_probe.py: CA_POSEINV,
CA_RELTOOL (arguments R[i] holding a whole or a real number, angles past 180) and CA_DEFFRAME (each origin) give
RAPID's values within 0.001 mm; points closer than 10 mm, an origin other than 1 to 3 (ROUT-035) and a string
argument (ROUT-043) abort on the CALL.

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
    "CA_POSEINV": KarelProgram("CA_POSEINV", "ca_poseinv.kl", "PR[c] = INV(PR[a]), RAPID PoseInv(a)",
                               "a, c: position register numbers"),
    "CA_RELTOOL": KarelProgram("CA_RELTOOL", "ca_reltool.kl", "PR[c] = RAPID RelTool(PR[a], dx, dy, dz \\Rx \\Ry \\Rz):"
                               " moved along PR[a]'s axes, then turned about its x, y, z in that order",
                               "a, c: position register numbers; dx, dy, dz (mm), rx, ry, rz (degrees): constants"
                               " or R[i]"),
    "CA_DEFFRAME": KarelProgram("CA_DEFFRAME", "ca_defframe.kl", "PR[c] = RAPID DefFrame(PR[a], PR[b], PR[d]"
                                " \\Origin:=o)", "a, b, d, c: position register numbers; o: 1, 2 or 3"),
    "CA_FILE": KarelProgram("CA_FILE", "ca_file.kl", "RAPID's Open (1), Write (2) and Close (3) of a text file of"
                            " HOME:, written on UD1: (lines ended by CR LF, numbers as Write \\Num writes them)",
                            "op; h: number of the register keeping the handle; Open: mode 1 \\Write, 2 \\Append,"
                            " then the name's parts; Write: 1 new line or 0 \\NoNewLine, then texts (constants,"
                            " SR[n], AR[n]) and numbers (constants, R[n])"),
}  # fmt: skip
_CALL = re.compile(r"^CALL (CA_[A-Z0-9_]+)\(")


def source(file: str) -> str:
    """The text of a library file shipped with CrossArm."""
    return resources.files(__name__).joinpath(file).read_text(encoding="ascii")


def called(lines: Iterable[str]) -> list[str]:
    """The library programs these TP lines call, in the order of the library."""
    found = {match[1] for text in lines if (match := _CALL.match(text)) and match[1] in PROGRAMS}
    return [name for name in PROGRAMS if name in found]
