# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Numbers as a TP line writes them: negative constants in parentheses, decimals without their leading zero,
the digits the controller runs with, and the largest whole number a line keeps (ROBOGUIDE)."""

import re
import unicodedata
from decimal import Decimal

from crossarm.convert.blockers import Blocker, Untranslatable


def operand(text: str) -> str:
    """A negative constant in parentheses, as the controller writes it in an assignment, a calculation, a
    CALL argument or a condition: `R[1]=(-2.5)`, `CALL P((-2.5))`, `IF (R[1]<(-2.5))`. ROBOGUIDE refuses
    `CALL P(-2.5)` and rewrites `R[1]=-2.5` with the parentheses; it loads `IF (R[1]<-2.5)` and `WAIT
    (R[1]<-2.5)` as written, but stops on them when they run (INTP-202 syntax error, joints probe)."""
    return f"({text})" if text.startswith("-") else text


def decimal(text: str) -> str:
    """A constant below 1 as the controller stores it in a CALL argument or a condition: `.5`, `(-.5)`,
    not `0.5` (ROBOGUIDE, argument and wait probes). Anything else is returned as it is."""
    return re.sub(r"^(\(?-?)0\.", r"\1.", text)


def fmt_number(value: float) -> str:
    """A constant with the digits the controller runs with: whole numbers as they are, 6 decimals, and as
    many as the 7 significant digits of a small one need (`.0000015`). ROBOGUIDE lists 6 significant
    digits (`300.000215` as `300`) but runs with the value written (300.000214, a 32-bit real)."""
    if float(value).is_integer():
        return str(int(value))
    if abs(value) < 0.1:
        return format(Decimal(f"{value:.7g}"), "f")
    return f"{value:.6f}".rstrip("0").rstrip(".")


# The largest whole number a TP line keeps (ROBOGUIDE): 2147483647 is stored `********`, -2147483648 as -129.
REGISTER_MAX = 2147483646


def register_value(value: float) -> str:
    """fmt_number() of a constant written in a register line; a TODO past what a register line keeps."""
    if abs(value) > REGISTER_MAX:
        raise Untranslatable(f"constant {fmt_number(value)} too large for a TP register: a TP line keeps"
                             f" {REGISTER_MAX} at most", Blocker.VALUE)  # fmt: skip
    return fmt_number(value)


# The RAPID types a numeric register holds.
NUMBER_TYPES = ("num", "byte")


def ascii_text(text: str) -> str:
    """TP files are ASCII: strip accents, replace anything else."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return folded.replace('"', "'").replace(";", ",")
