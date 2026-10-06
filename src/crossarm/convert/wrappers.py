# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Routines that wrap a move: `MoveLSide p10,v500,z10,tGrip\\WObj:=wobj1;` -> `L P[n] ...`.

Integrators often write their own MoveL: a routine that takes the same arguments,
does something around the move (choose the point from a parameter, check a zone,
log) and then moves. A backup that makes most of its moves that way gets thousands of
TODO and not a single point left in the programs.

A routine is a *move routine* when its body holds exactly one MoveJ/MoveL/MoveC/
MoveAbsJ, at its top level, whose point, speed, zone and tool are its own parameters
(or a local copy of one). A call to it can then be written as that move, with the
call's arguments in place of the parameters.

Whether it is depends on what else the routine does:
  * nothing but comments, local declarations and the copy: the call *is* the move,
    and it is converted;
  * anything else (a condition, a modified point, I/O...): converting the call as the
    move drops that part, which is a decision for the integrator. The calls stay TODO
    unless the mapping file says otherwise: "move_routines": {"MoveLSide": true}.
"""

import re
from dataclasses import dataclass, replace

from crossarm.rapid import nodes as n
from crossarm.rapid.walk import split_params, walk_statements

_INSTRUCTION = {n.MoveKind.J: "MoveJ", n.MoveKind.L: "MoveL", n.MoveKind.C: "MoveC", n.MoveKind.ABSJ: "MoveAbsJ"}
_PARAM_NAME = re.compile(r"([A-Za-z_]\w*)\s*(?:\{[^}]*\})?\s*$")


class CallMismatch(ValueError):
    """The call's arguments do not fit the routine's parameters."""


def parameters(raw: str) -> tuple[tuple[str, ...], frozenset[str]] | None:
    """(required parameters in order, optional ones), upper-cased; None if the list cannot be read.

    'robtarget ToPoint,speeddata Speed,PERS tooldata Tool,\\PERS wobjdata WObj'
    -> (('TOPOINT', 'SPEED', 'TOOL'), {'WOBJ'}). RAPID lets an optional parameter
    follow without a comma ('num Area\\switch XP|switch XM'): '\\' starts a new one too.
    """
    required: list[str] = []
    optional: set[str] = set()
    for part in split_params(raw):
        names = []
        for alternative in part.lstrip("\\").split("|"):
            match = _PARAM_NAME.search(alternative.strip())
            if match is None:
                return None
            names.append(match.group(1).upper())
        if part.startswith("\\"):
            optional.update(names)
        elif len(names) == 1:
            required.append(names[0])
        else:
            return None
    return tuple(required), frozenset(optional)


@dataclass(frozen=True, slots=True)
class MoveRoutine:
    name: str  # as declared
    module: str
    move: n.Move  # the move in its body, written with the routine's parameters
    required: tuple[str, ...]  # upper-case parameter names, in order
    optional: frozenset[str]
    copies: tuple[tuple[str, str], ...]  # (local, parameter it copies), upper-case
    extra: tuple[n.Stmt, ...]  # what else the routine does: not part of the converted move

    @property
    def instruction(self) -> str:
        return _INSTRUCTION[self.move.kind]

    @property
    def pure(self) -> bool:
        """Nothing but the move: a call to it is exactly that move."""
        return not self.extra

    def expand(self, call: n.ProcCall) -> n.Move:
        """The move this call makes, with the call's arguments and span."""
        positional = [a for a in call.args if a.name is None]
        if len(positional) != len(self.required):
            raise CallMismatch(f"{len(positional)} arguments given, {self.name} takes {len(self.required)}")
        bound: dict[str, n.Expr] = {}
        for param, arg in zip(self.required, positional, strict=True):
            if arg.value is None:
                raise CallMismatch(f"argument for {param} is missing")
            bound[param] = arg.value
        for arg in call.args:
            if arg.name is None:
                continue
            key = arg.name.upper()
            if key not in self.optional:
                raise CallMismatch(f"{self.name} has no optional parameter \\{arg.name}")
            if arg.conditional:
                raise CallMismatch(f"conditional argument \\{arg.name}?... depends on the caller's own arguments")
            bound[key] = arg.value if arg.value is not None else n.Bool(arg.span, True)
        copies = dict(self.copies)

        def actual(expr: n.Expr | None) -> n.Expr | None:
            """The call's argument for a parameter (or a local copy of it); None if it was not given."""
            if not isinstance(expr, n.Name):
                return expr
            key = expr.name.upper()
            return bound.get(copies.get(key, key))

        m = self.move
        wobj = actual(m.wobj)
        options: list[n.Arg] = []
        for option in m.options:
            if option.name is None:
                continue
            value = actual(option.value) if option.value is not None else None
            if option.conditional:  # \WObj?WObj: passed on only when the call gave it
                if value is None:
                    continue
                if option.name.upper() == "WOBJ":
                    wobj = value
                    continue
                option = replace(option, conditional=False)
            options.append(replace(option, value=value))
        points = (actual(m.to_point), actual(m.speed), actual(m.zone), actual(m.tool))
        if any(p is None for p in points):
            raise CallMismatch("an argument the move needs was not given")
        to_point, speed, zone, tool = points
        via = actual(m.via_point) if m.via_point is not None else None
        return n.Move(call.span, m.kind, to_point, speed, zone, tool, via, wobj, tuple(options))  # type: ignore[arg-type]


def find_move_routines(modules: list[n.Module]) -> dict[str, MoveRoutine]:
    """Every PROC of these modules that wraps one move, by upper-case name."""
    found: dict[str, MoveRoutine] = {}
    for module in modules:
        for routine in module.routines:
            wrapped = _move_routine(module.name, routine)
            if wrapped is not None:
                found[routine.name.upper()] = wrapped
    return found


def _move_routine(module: str, routine: n.Routine) -> MoveRoutine | None:
    if routine.kind != "PROC" or not routine.params:
        return None
    params = parameters(routine.params)
    if params is None:
        return None
    required, optional = params
    known = set(required) | optional
    moves = [s for s in walk_statements(routine.body) if isinstance(s, n.Move)]
    if len(moves) != 1 or not any(s is moves[0] for s in routine.body):
        return None  # none, several, or one inside a condition: not a move routine
    move = moves[0]
    locals_ = {s.name.upper() for s in routine.body if isinstance(s, n.DataDecl)}
    copies: dict[str, str] = {}
    extra: list[n.Stmt] = []
    for s in routine.body:
        if s is move or isinstance(s, n.Comment):
            continue
        if isinstance(s, n.DataDecl) and not s.dims:
            if s.init is None:
                continue
            if isinstance(s.init, n.Name) and s.init.name.upper() in known:
                copies[s.name.upper()] = s.init.name.upper()
                continue
        if (
            isinstance(s, n.Assign) and isinstance(s.target, n.Name) and isinstance(s.value, n.Name)
            and s.target.name.upper() in locals_ and s.target.name.upper() not in copies
            and s.value.name.upper() in known
        ):  # fmt: skip
            copies[s.target.name.upper()] = s.value.name.upper()
            continue
        extra.append(s)
    # BACKWARD only runs when stepping backwards on the pendant; ERROR/UNDO change what a call does.
    extra += [h for h in routine.handlers if h.kind != "BACKWARD_HANDLER"]

    def from_parameter(expr: n.Expr | None) -> bool:
        if not isinstance(expr, n.Name):
            return False
        key = expr.name.upper()
        return copies.get(key, key) in known

    roles = [move.to_point, move.speed, move.zone, move.tool]
    if move.via_point is not None:
        roles.append(move.via_point)
    if move.wobj is not None:
        roles.append(move.wobj)
    if not all(from_parameter(r) for r in roles):
        return None
    return MoveRoutine(routine.name, module, move, required, optional, tuple(copies.items()), tuple(extra))
