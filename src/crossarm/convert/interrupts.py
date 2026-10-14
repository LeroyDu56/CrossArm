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

A TRAP several interrupts share is called through a relay per interrupt, which notes the interrupt
in a register (what INTNO reads), calls the TRAP and arms its own condition program again. Each
interrupt has a number of its own, what an intnum reads as (`TEST INTNO CASE iStop:`).

A TRAP stopping the robot (StopMove) converts with --karel: CrossArm's KAREL program CA_STOPMOVE pauses the task
holding the robot, and lets it go on at a StartMove (convert.stop_move). No condition monitor fires while its
program is paused (ROBOGUIDE), so a TRAP that leaves the motion stopped waits itself for the interrupt that starts
it again: its own (a TRAP starting or stopping the robot as its signal changes) or the one other interrupt whose
TRAP calls StartMove, armed on a digital signal; it then runs that TRAP, and again until the motion goes on.

What does not convert: an interrupt connected to several TRAP routines, a TRAP that moves the robot or controls
its motion otherwise (StorePath, ExitCycle...: it runs without a motion group), and the interrupts FANUC
cannot watch (ITimer: a WHEN on a TIMER is refused; IError, the group and analog signals).
"""

import re
from dataclasses import dataclass, field

from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr
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
# What a TRAP may do to the motion with --karel (CA_STOPMOVE; ClearPath after a StopMove: the move goes on)
STOP_MOVES = frozenset({"STOPMOVE", "STARTMOVE", "CLEARPATH"})
KAREL_HINT = "; a TRAP pausing the motion (StopMove, StartMove) converts with --karel"


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
    number: int = 0  # what INTNO and the intnum read as: 1, 2... in the order the programs name them
    shared: bool = False  # its TRAP serves other interrupts too: called through a relay
    relay: str = ""  # the relay's TP name, when shared
    stops_motion: bool = False  # its TRAP pauses the robot or lets it go on (--karel): ignores pause requests
    arms: set[tuple[str, str]] = field(default_factory=set)  # ISignalDI / ISignalDO: (signal, value) as written
    signal: n.Expr | None = None  # the signal and the value it is armed on (the first arming)
    trigger: n.Expr | None = None
    resumer: str = ""  # its TRAP stops the motion: the interrupt whose TRAP starts it again (upper case)

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


def scan(routines: list[n.Routine], procs: dict[str, n.Routine], move_routines: set[str],
         karel: bool = False) -> dict[str, Interrupt]:  # fmt: skip
    """Every interrupt the routines connect or arm, upper-case name -> Interrupt, with its problem if any.
    `karel`: converting with --karel, where a TRAP may stop the motion and start it again (CA_STOPMOVE)."""
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
                elif len(values := [a.value for a in stmt.args if a.name is None]) == 3:
                    interrupt.arms.add((format_expr(values[0]).upper(), format_expr(values[1]).upper()))
                    if interrupt.signal is None:
                        interrupt.signal, interrupt.trigger = values[0], values[1]
    users: dict[str, int] = {}
    for interrupt in found.values():
        for trap in interrupt.traps:
            users[trap] = users.get(trap, 0) + 1
    reading = {name for name, routine in traps.items() if _reads_intno(routine.body)}
    for number, interrupt in enumerate(found.values(), start=1):
        interrupt.number = number
        # through a relay: a TRAP other interrupts share, or one that reads INTNO (the register the relay sets)
        interrupt.shared = len(interrupt.traps) == 1 and (users[interrupt.trap] > 1 or interrupt.trap in reading)
        interrupt.problem = _problem(interrupt, traps, procs, move_routines, karel)
    if karel:
        _resumers(found, traps, procs)
    return found


def _resumers(found: dict[str, Interrupt], traps: dict[str, n.Routine], procs: dict[str, n.Routine]) -> None:
    """Each interrupt whose TRAP stops the motion gets the interrupt whose TRAP starts it again (its own when it
    calls StartMove too, else the only other one that does), armed on one digital signal: the stopping TRAP waits
    for that signal, no condition monitor firing while its program is paused (ROBOGUIDE)."""
    calls = {key: [c.name.upper() for c in motion_stops(traps[i.trap], procs)]
             for key, i in found.items() if not i.problem and i.trap in traps}  # fmt: skip

    def waitable(interrupt: Interrupt) -> bool:
        return bool(interrupt.kinds) and interrupt.kinds <= {"DI", "DO"} and len(interrupt.arms) == 1 \
            and not interrupt.shared  # fmt: skip

    stopping = [key for key, names in calls.items() if "STOPMOVE" in names]
    for key in sorted(stopping, key=lambda k: "STARTMOVE" not in calls[k]):  # those resuming themselves first
        interrupt = found[key]
        routine = traps[interrupt.trap]
        if interrupt.shared:
            interrupt.problem = (f"TRAP {routine.name} stops the motion and serves several interrupts:"
                                 " CrossArm waits for the one starting it again in a TRAP serving one")  # fmt: skip
            continue
        if "STARTMOVE" in calls[key]:
            if waitable(interrupt):
                interrupt.resumer = key
            else:
                interrupt.problem = (f"TRAP {routine.name} stops the motion: CrossArm waits for the change of its"
                                     " signal to run it again, which needs it armed on one digital signal, by one"
                                     " ISignalDI or ISignalDO, for itself only")  # fmt: skip
            continue
        others = sorted(k for k, names in calls.items()
                        if k != key and _starts_first(names) and not found[k].problem and waitable(found[k]))  # fmt: skip
        if len(others) == 1:
            interrupt.resumer = others[0]
        elif not others:
            interrupt.problem = (f"TRAP {routine.name} stops the motion and no TRAP armed on a digital signal"
                                 " starts it again: the program paused cannot run its own StartMove, and no"
                                 " condition monitor fires while it is paused (ROBOGUIDE)")  # fmt: skip
        else:
            names = ", ".join(traps[found[k].trap].name for k in others)
            interrupt.problem = (f"TRAP {routine.name} stops the motion and several TRAPs start it again ({names}):"
                                 " CrossArm waits for one")  # fmt: skip
    for key, names in calls.items():
        found[key].stops_motion = not found[key].problem and bool({"STOPMOVE", "STARTMOVE"} & set(names))


def _starts_first(names: list[str]) -> bool:
    """Whether a TRAP may start a motion it did not stop: its first StopMove / StartMove is a StartMove (a TRAP
    stopping the robot then starting it again resumes itself only)."""
    return next((name for name in names if name in ("STOPMOVE", "STARTMOVE")), "") == "STARTMOVE"


def _reads_intno(node: object) -> bool:
    """Whether statements read INTNO, the interrupt that called the TRAP."""
    if isinstance(node, n.Name):
        return node.name.upper() == "INTNO"
    if isinstance(node, tuple | list):
        return any(_reads_intno(item) for item in node)
    if hasattr(node, "__dataclass_fields__") and not isinstance(node, n.Span):
        return any(_reads_intno(getattr(node, name)) for name in node.__dataclass_fields__)
    return False


def _problem(interrupt: Interrupt, traps: dict[str, n.Routine], procs: dict[str, n.Routine],
             move_routines: set[str], karel: bool = False) -> str:  # fmt: skip
    if interrupt.gap:
        return f"interrupt {interrupt.name} is armed by {interrupt.gap}"
    if not interrupt.traps:
        return f"interrupt {interrupt.name} is not connected to a TRAP routine (no CONNECT)"
    if len(interrupt.traps) > 1:
        return f"interrupt {interrupt.name} is connected to several TRAP routines ({', '.join(sorted(interrupt.traps))})"
    trap = interrupt.trap
    if trap not in traps:
        return f"TRAP {trap} of interrupt {interrupt.name} is not in the converted modules"
    if len(interrupt.kinds) > 1:
        return f"interrupt {interrupt.name} is armed on conditions of different kinds"
    routine = traps[trap]
    moving = moves(routine, procs, move_routines, STOP_MOVES if karel else frozenset())
    if moving:
        pausing = not karel and not moves(routine, procs, move_routines, STOP_MOVES) and not unpaired(routine, procs)
        return (f"TRAP {routine.name} {moving}: a FANUC condition monitor calls a program without a motion"
                f" group, which cannot move the robot or stop its motion{KAREL_HINT if pausing else ''}")  # fmt: skip
    if karel and (why := unpaired(routine, procs)):
        return f"TRAP {routine.name} {why}"
    return ""


def motion_stops(routine: n.Routine, procs: dict[str, n.Routine]) -> list[n.ProcCall]:
    """The StopMove, StartMove and ClearPath a routine runs, itself or through the routines it calls, in the order
    written."""
    found: list[n.ProcCall] = []

    def visit(current: n.Routine, seen: frozenset[str]) -> None:
        for stmt in walk_statements(current.body):
            if isinstance(stmt, n.ProcCall):
                name = stmt.name.upper()
                if name in STOP_MOVES:
                    found.append(stmt)
                elif name in procs and name not in seen:
                    visit(procs[name], seen | {name})

    visit(routine, frozenset({routine.name.upper()}))
    return found


def unpaired(routine: n.Routine, procs: dict[str, n.Routine]) -> str:
    """Why a TRAP's StopMove / StartMove / ClearPath do not convert ("" when they do, or when it has none):
    \\AllMotionTasks, and a ClearPath with no StopMove before it (the TRAP would clear a path under way)."""
    stopped = False
    for call in motion_stops(routine, procs):
        name = call.name.upper()
        if any((a.name or "").upper() == "ALLMOTIONTASKS" for a in call.args):
            return (f"calls {call.name} \\AllMotionTasks (l.{call.span.line}): CrossArm stops and starts the robot of"
                    " the program only")  # fmt: skip
        if name == "STOPMOVE":
            stopped = True
        elif name == "CLEARPATH" and not stopped:
            return (f"calls ClearPath (l.{call.span.line}) with no StopMove before it: CrossArm writes a ClearPath"
                    " after a StopMove only, the move then going on to its point")  # fmt: skip
    return ""


def moves(routine: n.Routine, procs: dict[str, n.Routine], move_routines: set[str],
          allowed: frozenset[str] = frozenset()) -> str:  # fmt: skip
    """What makes a routine, or one it calls, move the robot or control its motion ("" when nothing does);
    `allowed`: motion instructions not counted (StopMove and StartMove with --karel)."""
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
                if name in _MOTION_CONTROL and name not in allowed:
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
