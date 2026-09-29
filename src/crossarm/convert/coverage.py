# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""How much of the RAPID code the conversion wrote as TP, counted per instruction and by area.

A TODO count says how many places need work, not how much of the backup is done: one TODO can
stand for a single line or for a whole IF block. Coverage counts RAPID instructions instead.
An instruction is converted when it was written as TP (or needs nothing on FANUC, like TPErase),
and not converted when it ended up in a TODO, alone or inside a block that did. Comments and
data declarations are not instructions. An error handler counts one instruction per statement
in it, as it is not read any further. Routines left out of the conversion (a TRAP that cannot be
converted, a PROC whose parameters cannot be passed) count as not converted. FUNC routines and routines wrapping a move
are not counted: they run where they are called, and it is that call that is converted or not.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from crossarm.rapid import nodes as n
from crossarm.rapid.walk import walk_statements

MOTION = "Motion"
IO = "I/O and waits"
FLOW = "Program flow"
DATA = "Data"
CALLS = "Routine calls"
MESSAGES = "Operator messages"
ERRORS = "Error handling"
OTHER = "Other instructions"
AREAS = (MOTION, IO, FLOW, DATA, CALLS, MESSAGES, ERRORS, OTHER)

_IO_CALLS = frozenset({
    "SETDO", "PULSEDO", "SETGO", "SETAO", "SETALLDATAVAL", "WAITDI", "WAITDO", "WAITGI", "WAITGO", "WAITAI",
    "WAITAO", "WAITUNTIL", "INVERTDO",
})  # fmt: skip
_MESSAGE_CALLS = frozenset({
    "TPWRITE", "TPERASE", "TPREADFK", "TPREADNUM", "TPSHOW", "UIMSGBOX", "UINUMENTRY", "UINUMTUNE",
    "UIALPHAENTRY", "UILISTVIEW", "UISHOW", "ERRWRITE", "ERRLOG",
})  # fmt: skip
_FLOW_CALLS = frozenset({"STOP", "EXIT", "EXITCYCLE", "BREAK"})
_ERROR_KINDS = frozenset({"ERROR_HANDLER", "UNDO_HANDLER", "BACKWARD_HANDLER", "RAISE", "RETRY", "TRYNEXT"})


def area(stmt: n.Stmt, routines: set[str], move_routines: set[str]) -> str | None:
    """The area an instruction belongs to; None for what is not an instruction (comment, declaration).

    `routines`: upper-case names of the backup's routines, `move_routines` those wrapping one move.
    """
    match stmt:
        case n.Comment() | n.DataDecl():
            return None
        case n.Move():
            return MOTION
        case n.SetSignal() | n.WaitTime():
            return IO
        case n.Assign():
            return DATA
        case n.If() | n.For() | n.While() | n.Test() | n.Return() | n.Exit():
            return FLOW
        case n.Unsupported(kind=kind):
            return ERRORS if kind in _ERROR_KINDS or kind.endswith("_HANDLER") else OTHER
        case n.ProcCall(name=name):
            key = name.upper()
            if key in move_routines:
                return MOTION
            if key in _IO_CALLS:
                return IO
            if key in _MESSAGE_CALLS:
                return MESSAGES
            if key in _FLOW_CALLS:
                return FLOW
            return CALLS if key in routines else OTHER
    return OTHER


def weight(stmt: n.Stmt) -> int:
    """Instructions a statement stands for: an error handler is kept as raw text, one per `;` in it."""
    if isinstance(stmt, n.Unsupported) and stmt.kind.endswith("_HANDLER"):
        return max(1, stmt.raw.count(";"))
    return 1


@dataclass(frozen=True, slots=True)
class Share:
    area: str
    total: int
    converted: int

    @property
    def percent(self) -> float:
        return percent(self.converted, self.total)


@dataclass(frozen=True, slots=True)
class Coverage:
    shares: tuple[Share, ...]  # areas with at least one instruction, in AREAS order
    skipped: int = 0  # instructions of the routines left out of the conversion (counted in shares)

    @property
    def total(self) -> int:
        return sum(s.total for s in self.shares)

    @property
    def converted(self) -> int:
        return sum(s.converted for s in self.shares)

    @property
    def percent(self) -> float:
        return percent(self.converted, self.total)

    def __add__(self, other: "Coverage") -> "Coverage":
        """Two tasks of one backup, counted together."""
        mine = {s.area: s for s in self.shares}
        theirs = {s.area: s for s in other.shares}
        shares = []
        for name in AREAS:
            a, b = mine.get(name), theirs.get(name)
            if a or b:
                shares.append(Share(name, (a.total if a else 0) + (b.total if b else 0),
                                    (a.converted if a else 0) + (b.converted if b else 0)))  # fmt: skip
        return Coverage(tuple(shares), self.skipped + other.skipped)


def percent(part: int, whole: int) -> float:
    """Rounded down to 0.1: 99.97 % is not shown as 100 % while something is left."""
    return 100.0 if whole == 0 else math.floor(part * 1000 / whole) / 10


def fmt_percent(value: float) -> str:
    """'96.4 %', '100 %'."""
    return f"{value:g} %"


def measure(
    converted: Iterable[n.Routine],
    skipped: Iterable[n.Routine],
    not_converted: set[int],
    routines: set[str],
    move_routines: set[str],
) -> Coverage:
    """`not_converted`: id() of every statement that ended up in a TODO (see _RoutineTranslator.todo)."""
    totals = dict.fromkeys(AREAS, 0)
    done = dict.fromkeys(AREAS, 0)

    def count(routine: n.Routine, written: bool) -> int:
        counted = 0
        for stmt in [*walk_statements(routine.body), *routine.handlers]:
            name = area(stmt, routines, move_routines)
            if name is None:
                continue
            size = weight(stmt)
            totals[name] += size
            counted += size
            if written and id(stmt) not in not_converted:
                done[name] += size
        return counted

    for routine in converted:
        count(routine, True)
    left_out = sum(count(routine, False) for routine in skipped if routine.kind != "FUNC")
    shares = tuple(Share(name, totals[name], done[name]) for name in AREAS if totals[name])
    return Coverage(shares, left_out)
