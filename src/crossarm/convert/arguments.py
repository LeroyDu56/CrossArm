# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID PROC parameters -> TP CALL arguments: `Set_Station 3\\Wait;` -> `CALL SET_STATION(3,1)`.

TP passes up to ten untyped values to a program called with CALL NAME(a,b,...), which reads
them as AR[1], AR[2]... and cannot change them. That holds the RAPID parameters passed by
value that TP can represent: `num`, `bool` (1 / 0), `string` (text written in the call, 38
characters at most: ROBOGUIDE refuses 39) and optional switches (1 when given, 0 otherwise).
A record the backup declares is passed as its components the routine reads, each an argument of
its own: `DeburrPart pdHousing;` -> `CALL DEBURRPART(2,.8,1)` for part.passes, part.depth,
part.chamfer. A num passed by reference (INOUT, VAR, PERS) that the routine changes is copied back:
the routine works on a register of its own, which the caller reads into its data after the CALL.
A routine with any other parameter — a tooldata, a record passed whole to another routine, an
optional num — is not converted, and its calls stay TODO with the reason.

A `robtarget` has no place in AR[n]: it goes in a position register of its own, which the caller
sets before the CALL (PR[k]=P[j]) and the routine moves to (L PR[k]). A move to a position register
takes the frames selected when it runs, and the configuration the register holds (ROBOGUIDE), as
a RAPID move takes its own tool and work object with the robtarget it is given.

A TP program can keep a string argument (SR[n]=AR[1]) and measure it (STRLEN), but not show it:
MESSAGE takes fixed text. So a TPWrite of a string parameter stays TODO in the routine, while
the routine and its calls are converted.

Every argument is passed on every call, switches included: on a FANUC controller reading an
AR[n] the caller did not pass stops the program, where RAPID's Present() just says FALSE.

A RAPID parameter passed by value is a local copy the routine may change (`Angle:=0;`). AR[n]
cannot be written, so such a num parameter is copied into a register when the program starts,
and the routine works on the register.
"""

import re
from dataclasses import dataclass

from crossarm.rapid import nodes as n
from crossarm.rapid.walk import base_name, walk_statements

MAX_ARGS = 10  # TP CALL takes at most ten arguments
_NAME = re.compile(r"([A-Za-z_]\w*)\s*(\{[^}]*\})?\s*$")


@dataclass(frozen=True, slots=True)
class Slot:
    name: str  # as declared; a record's component: "part.passes"
    # "num" | "bool" | "string" | "switch" | "robtarget" (in a position register, not in AR[n]) | "record"
    kind: str
    fields: tuple["Slot", ...] = ()  # a record: the components the routine reads, each passed as an argument
    by_reference: bool = False  # INOUT, VAR or PERS: what the routine changes goes back to the caller

    @property
    def key(self) -> str:
        return self.name.upper()


@dataclass(frozen=True, slots=True)
class Signature:
    """The AR[n] layout of a routine: required parameters in order, then each optional switch."""

    slots: tuple[Slot, ...]
    copied: frozenset[str] = frozenset()  # upper-case num parameters the routine changes: copied to R[n]
    routine: str = ""  # its name, as declared
    # robtarget parameter (upper case) -> the tool and work object of the first move the routine makes to it
    point_frames: tuple[tuple[str, n.Expr | None, n.Expr | None], ...] = ()

    @property
    def arguments(self) -> tuple[Slot, ...]:
        """The slots passed as AR[n], in order: every one but the points, a record as its components."""
        return tuple(f for s in self.slots if s.kind != "robtarget" for f in (s.fields if s.kind == "record" else (s,)))

    def frames_of(self, name: str) -> tuple[n.Expr | None, n.Expr | None]:
        """(tool, work object) the routine moves to its point `name` with; (None, None) if it only passes it on."""
        return next(((tool, wobj) for key, tool, wobj in self.point_frames if key == name.upper()), (None, None))

    def register(self, name: str) -> str | None:
        """'AR[2]' for the parameter of that name, None if it is not one."""
        for i, slot in enumerate(self.arguments, start=1):
            if slot.key == name.upper():
                return f"AR[{i}]"
        return None

    def kind(self, name: str) -> str | None:
        """The kind of a parameter, or of a record parameter's component ('PART.PASSES')."""
        return next((s.kind for s in (*self.slots, *self.arguments) if s.key == name.upper()), None)

    def returned(self) -> tuple[Slot, ...]:
        """The parameters passed by reference that the routine changes: the caller reads them back."""
        return tuple(s for s in self.slots if s.by_reference and s.key in self.copied)


def signature(routine: n.Routine, records: dict[str, tuple[tuple[str, str], ...]] | None = None) -> Signature | str:
    """The routine's AR[n] layout, or why its parameters cannot be passed as TP arguments.

    `records`: the RECORD types the backup declares, lower-case name -> (component, type) in order."""
    records = records or {}
    required: list[Slot] = []
    switches: list[Slot] = []
    for part in re.split(r",|(?=\\)", routine.params):
        part = part.strip()
        if not part:
            continue
        optional = part.startswith("\\")
        alternatives = part.lstrip("\\").split("|")
        if not optional and len(alternatives) > 1:
            return f"unreadable parameter list: {routine.params}"
        for alternative in alternatives:
            words = alternative.split()
            match = _NAME.search(alternative.strip())
            if len(words) < 2 or match is None:
                return f"unreadable parameter list: {routine.params}"
            name, dims = match.group(1), match.group(2)
            mode = words[0].upper() if words[0].upper() in ("VAR", "PERS", "INOUT") else ""
            type_name = words[-2] if not dims else words[-2].split("{")[0]
            if mode and (type_name.lower() != "num" or dims or optional):
                return f"{type_name} parameter {name} is passed by reference ({mode}): only a num is copied back"
            if dims:
                return f"parameter {name} is an array: TP arguments are single values"
            if optional:
                if type_name.lower() != "switch":
                    return f"optional {type_name} parameter {name}: only optional switches are converted"
                switches.append(Slot(name, "switch"))
            elif type_name.lower() in ("num", "bool", "string", "robtarget"):
                required.append(Slot(name, type_name.lower(), by_reference=bool(mode)))
            elif type_name.lower() in records:
                fields = _record_fields(routine, name, type_name, records[type_name.lower()])
                if isinstance(fields, str):
                    return fields
                required.append(Slot(name, "record", fields))
            else:
                return f"{type_name} parameter {name}: TP arguments are numbers or text"
    slots = tuple(required + switches)
    arguments = [s for s in slots if s.kind != "robtarget"]
    if len(arguments) > MAX_ARGS:
        return f"{len(arguments)} parameters: a TP CALL takes at most {MAX_ARGS} arguments"
    kinds = {s.key: s.kind for s in slots}
    copied: set[str] = set()
    by_reference = {s.key for s in slots if s.by_reference}
    for stmt in walk_statements(routine.body):
        changed = _changed_by_call(stmt)
        if isinstance(stmt, n.ProcCall) and stmt.name.upper() not in _CHANGING:
            # passed on to a routine that may change it (its own INOUT): the caller reads back what comes back
            for arg in stmt.args:
                if isinstance(arg.value, n.Name) and arg.value.name.upper() in by_reference:
                    copied.add(arg.value.name.upper())
        if changed and changed.upper() in kinds:
            if kinds[changed.upper()] != "num":
                return f"it changes its parameter {changed}: only a whole num parameter can be copied to a register"
            copied.add(changed.upper())
        if isinstance(stmt, n.Assign) and (target := base_name(stmt.target)) and target.upper() in kinds:
            if kinds[target.upper()] != "num" or not isinstance(stmt.target, n.Name):
                return f"it changes its parameter {target}: only a whole num parameter can be copied to a register"
            copied.add(target.upper())
        elif isinstance(stmt, n.For) and stmt.var.upper() in kinds:
            return f"it uses its parameter {stmt.var} as a FOR variable"
    points = {s.key for s in slots if s.kind == "robtarget"}
    frames: dict[str, tuple[n.Expr | None, n.Expr | None]] = {}
    for stmt in walk_statements(routine.body):
        if isinstance(stmt, n.Move):
            for target in (stmt.via_point, stmt.to_point):
                base = target.args[0].value if isinstance(target, n.FuncCall) and target.args else target
                if isinstance(base, n.Name) and base.name.upper() in points:
                    frames.setdefault(base.name.upper(), (stmt.tool, stmt.wobj))
    return Signature(slots, frozenset(copied), routine.name,
                     tuple((key, tool, wobj) for key, (tool, wobj) in frames.items()))  # fmt: skip


_CHANGING = frozenset({"INCR", "DECR", "ADD", "CLEAR"})  # instructions that change their first argument


def _changed_by_call(stmt: n.Stmt) -> str | None:
    """The data an Incr, Decr, Add or Clear changes, as written."""
    if isinstance(stmt, n.ProcCall) and stmt.name.upper() in _CHANGING and stmt.args:
        first = stmt.args[0].value
        return first.name if isinstance(first, n.Name) else None
    return None


def _record_fields(routine: n.Routine, name: str, type_name: str,
                   layout: tuple[tuple[str, str], ...]) -> tuple[Slot, ...] | str:  # fmt: skip
    """The components of a record parameter the routine reads, in the record's order, each a slot of its own;
    or why the record cannot be passed so (the routine uses it whole, or a component is not a number,
    a bool or text)."""
    read: set[str] = set()
    whole = False

    def visit(node: object) -> None:  # every statement and expression of the routine, conditions included
        nonlocal whole
        if isinstance(node, n.Component) and isinstance(node.base, n.Name) and node.base.name.upper() == name.upper():
            read.add(node.field.lower())
        elif isinstance(node, n.Name) and node.name.upper() == name.upper():
            whole = True
        elif isinstance(node, tuple | list):
            for item in node:
                visit(item)
        elif hasattr(node, "__dataclass_fields__") and not isinstance(node, n.Span):
            for field_name in node.__dataclass_fields__:
                visit(getattr(node, field_name))

    visit(routine.body)
    if whole:
        return f"{type_name} parameter {name} is used whole: only its components can be passed as TP arguments"
    fields = []
    for field_name, field_type in layout:
        if field_name not in read:
            continue
        if field_type not in ("num", "bool", "string"):
            return f"{type_name} parameter {name}: its component {field_name} is a {field_type}"
        fields.append(Slot(f"{name}.{field_name}", field_type))
    return tuple(fields)


__all__ = ["MAX_ARGS", "Signature", "Slot", "signature"]
