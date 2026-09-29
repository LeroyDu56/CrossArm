# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID interrupts as FANUC condition monitors: which ones convert, and what their TRAP changes.

RAPID connects an interrupt number to a TRAP routine (CONNECT), then arms it on a condition
(ISignalDI, ISignalDO, IPers). FANUC has the Condition Monitor function: a condition program
holds `WHEN DI[1]=ON+,CALL TRAP`, and `MONITOR NAME` arms it, `MONITOR END NAME` disarms it.
Measured on ROBOGUIDE (monitor probe): the edge conditions ON+ / OFF- fire the way ISignalDI
does, once per edge and not for a signal already set when armed; the program stops while the
TRAP runs but the move under way goes on, as in RAPID; the monitor stays active in the programs
called. A condition program fires once and is then disarmed as a whole: the TRAP arms it again
as it ends, unless the RAPID asked for one interrupt only (\\Single).

What does not convert: an interrupt connected to several TRAP routines, or a TRAP connected to
several interrupts (it would not know which to arm again), a TRAP that moves the robot or stops
its motion (StopMove, ClearPath...: it runs without a motion group), and the interrupts FANUC
cannot watch (ITimer: a WHEN on a TIMER is refused; IError, the group and analog signals).
"""

import re
from dataclasses import dataclass, field

from crossarm.rapid import nodes as n
from crossarm.rapid.walk import walk_statements

_CONNECT = re.compile(r"CONNECT\s+(\w+)\s+WITH\s+(\w+)", re.IGNORECASE)
# Instructions that arm an interrupt, with the kind of condition they set
ARMING = {"ISIGNALDI": "DI", "ISIGNALDO": "DO", "IPERS": "PERS"}
SINGLE_OPTIONS = frozenset({"SINGLE", "SINGLESAFE"})
# Instructions that arm an interrupt on what a condition monitor cannot watch, and why
GAPS = {
    "ITIMER": "a condition monitor cannot watch a timer (a WHEN on TIMER[n] is refused)",
    "IERROR": "a condition monitor does not watch the controller's errors",
    "ISIGNALGI": "a condition monitor watches a group input for one value, not for any change",
    "ISIGNALGO": "a condition monitor watches a group output for one value, not for any change",
    "ISIGNALAI": "analog conditions are not converted",
    "ISIGNALAO": "analog conditions are not converted",
}
# What a TRAP cannot do without a motion group
_MOTION_CONTROL = frozenset({
    "STOPMOVE", "STARTMOVE", "STARTMOVERETRY", "STOPMOVERESET", "CLEARPATH", "STOREPATH", "RESTOPATH",
    "EXITCYCLE", "SEARCHL", "SEARCHJ", "SEARCHC",
})  # fmt: skip


@dataclass(slots=True)
class Interrupt:
    """One RAPID interrupt number (an `intnum` data) and what the programs do with it."""

    name: str  # as declared
    traps: set[str] = field(default_factory=set)  # TRAP routines CONNECTed to it, upper case
    kinds: set[str] = field(default_factory=set)  # "DI", "DO", "PERS": how it is armed
    single: bool = True  # every arming has \Single: the TRAP does not arm it again
    gap: str = ""  # an instruction arming it on what FANUC cannot watch, and why
    watched: n.Expr | None = None  # IPers: the data watched
    problem: str = ""  # why it is not converted ("" when it is)
    program: str = ""  # its TP condition program, named by the converter

    @property
    def trap(self) -> str:
        return next(iter(self.traps)) if len(self.traps) == 1 else ""


def connected(stmt: n.Stmt) -> tuple[str, str] | None:
    """(interrupt, TRAP) of a CONNECT statement, as written; None for anything else."""
    if isinstance(stmt, n.Unsupported) and stmt.kind == "CONNECT":
        found = _CONNECT.search(stmt.raw)
        if found:
            return found[1], found[2]
    return None


def arming(call: n.ProcCall) -> tuple[str, str] | None:
    """(interrupt as written, kind) of an ISignalDI / ISignalDO / IPers call; None otherwise."""
    kind = ARMING.get(call.name.upper())
    positional = [a.value for a in call.args if a.name is None]
    if kind is None or not positional or not isinstance(positional[-1], n.Name):
        return None
    return positional[-1].name, kind


def scan(routines: list[n.Routine], procs: dict[str, n.Routine], move_routines: set[str]) -> dict[str, Interrupt]:
    """Every interrupt the routines connect or arm, upper-case name -> Interrupt, with its problem if any."""
    found: dict[str, Interrupt] = {}
    traps = {r.name.upper(): r for r in routines if r.kind == "TRAP"}

    def get(name: str) -> Interrupt:
        return found.setdefault(name.upper(), Interrupt(name))

    for routine in routines:
        for stmt in walk_statements(routine.body):
            if pair := connected(stmt):
                get(pair[0]).traps.add(pair[1].upper())
            elif isinstance(stmt, n.ProcCall) and stmt.name.upper() in GAPS:
                last = [a.value for a in stmt.args if a.name is None][-1:]
                if last and isinstance(last[0], n.Name):
                    get(last[0].name).gap = f"{stmt.name}: {GAPS[stmt.name.upper()]}"
            elif isinstance(stmt, n.ProcCall) and (armed := arming(stmt)):
                interrupt = get(armed[0])
                interrupt.kinds.add(armed[1])
                interrupt.single &= any((a.name or "").upper() in SINGLE_OPTIONS for a in stmt.args)
                if armed[1] == "PERS":
                    interrupt.watched = next(a.value for a in stmt.args if a.name is None)
    users: dict[str, int] = {}
    for interrupt in found.values():
        for trap in interrupt.traps:
            users[trap] = users.get(trap, 0) + 1
    for interrupt in found.values():
        interrupt.problem = _problem(interrupt, traps, users, procs, move_routines)
    return found


def _problem(interrupt: Interrupt, traps: dict[str, n.Routine], users: dict[str, int],
             procs: dict[str, n.Routine], move_routines: set[str]) -> str:  # fmt: skip
    if interrupt.gap:
        return f"interrupt {interrupt.name} is armed by {interrupt.gap}"
    if not interrupt.traps:
        return f"interrupt {interrupt.name} is not connected to a TRAP routine (no CONNECT)"
    if len(interrupt.traps) > 1:
        return f"interrupt {interrupt.name} is connected to several TRAP routines ({', '.join(sorted(interrupt.traps))})"
    trap = interrupt.trap
    if trap not in traps:
        return f"TRAP {trap} of interrupt {interrupt.name} is not in the converted modules"
    if users[trap] > 1:
        return f"TRAP {traps[trap].name} is connected to several interrupts: it could not tell which to arm again"
    if len(interrupt.kinds) > 1:
        return f"interrupt {interrupt.name} is armed on conditions of different kinds"
    moving = moves(traps[trap], procs, move_routines)
    if moving:
        return (f"TRAP {traps[trap].name} {moving}: a FANUC condition monitor calls a program without a motion"
                " group, which cannot move the robot or stop its motion")  # fmt: skip
    return ""


def moves(routine: n.Routine, procs: dict[str, n.Routine], move_routines: set[str]) -> str:
    """What makes a routine, or one it calls, move the robot or control its motion ("" when nothing does)."""
    seen: set[str] = set()
    pending = [routine]
    while pending:
        current = pending.pop()
        if current.name.upper() in seen:
            continue
        seen.add(current.name.upper())
        for stmt in walk_statements(current.body):
            if isinstance(stmt, n.Move):
                return f"moves the robot (l.{stmt.span.line})"
            if isinstance(stmt, n.ProcCall):
                name = stmt.name.upper()
                if name in _MOTION_CONTROL:
                    return f"calls {stmt.name} (l.{stmt.span.line})"
                if name in move_routines:
                    return f"moves the robot through {stmt.name} (l.{stmt.span.line})"
                if name in procs:
                    pending.append(procs[name])
    return ""


def called_by(routine: n.Routine, procs: dict[str, n.Routine]) -> set[str]:
    """Upper-case names of the routines a routine calls, directly or not.

    A TRAP runs as a task of its own: a program it calls must not hold a motion group, which the
    program it interrupted holds (ROBOGUIDE: INTP-222 Call program failed, PROG-040 Already locked by
    other task). Written without one, it runs, and the move under way is not slowed."""
    found: set[str] = set()
    pending = [routine]
    while pending:
        for stmt in walk_statements(pending.pop().body):
            key = stmt.name.upper() if isinstance(stmt, n.ProcCall) else ""
            if key in procs and key not in found:
                found.add(key)
                pending.append(procs[key])
    return found


def changed_by(routine: n.Routine, procs: dict[str, n.Routine]) -> set[str]:
    """Upper-case names of the data a routine, or one it calls, assigns: a TRAP changes them at any time."""
    names: set[str] = set()
    seen: set[str] = set()
    pending = [routine]
    while pending:
        current = pending.pop()
        if current.name.upper() in seen:
            continue
        seen.add(current.name.upper())
        for stmt in walk_statements(current.body):
            if isinstance(stmt, n.Assign):
                target = stmt.target
                while not isinstance(target, n.Name) and hasattr(target, "base"):
                    target = target.base
                if isinstance(target, n.Name):
                    names.add(target.name.upper())
            elif isinstance(stmt, n.ProcCall):
                if stmt.name.upper() in procs:
                    pending.append(procs[stmt.name.upper()])
                for arg in stmt.args:  # Incr, Add, a routine's INOUT parameter...
                    if isinstance(arg.value, n.Name):
                        names.add(arg.value.name.upper())
    return names
