# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Data of a RECORD type the backup declares, kept field by field on the FANUC.

TP has numbers, flags and strings, no records. A state machine often keeps its state in one:

    RECORD cell_ctrl               VAR cell_ctrl rCell;
      num state;                   rCell.state:=1;                 ->  R[12:rCell.state]=1
      move_param move;             MoveL p,rCell.move.speed,...    ->  L P[1] 400mm/sec ...
    ENDRECORD

Each field a program changes is a register of its own (a bool a flag), named by its path. A field no
program changes is its value, written where it is read, as a CONST is (the saved one for a PERS). A speed
or zone field is the speed or zone of the moves, which TP writes as numbers: it is the value every write
gives it, when they all give the same (the INIT routine of a state machine), else the moves stay TODO.

What changes a field is crossarm.convert.compute.Written: an assignment to it, to a record it is part of
or to the whole data, a routine changing the data it is given, Incr / Clear / SetDataVal, code CrossArm
does not read; in any task of the backup for a PERS, which the tasks share, in its own task for a VAR.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from crossarm.convert.compute import LAYOUTS, Layouts, Written, _overlap, path_of
from crossarm.convert.handlers import body as handler_body
from crossarm.convert.values import Symbols, Unresolvable
from crossarm.rapid import nodes as n
from crossarm.rapid.walk import walk_statements

SCALARS = frozenset({"num", "bool"})  # the fields TP keeps: a register, a flag
MOTION = frozenset({"speeddata", "zonedata"})  # fields the moves read, written as their value


@dataclass(frozen=True, slots=True)
class Field:
    """A part of a record data: `path` the field names from the data down (as the RECORD declares them)."""

    root: n.DataDecl
    path: tuple[str, ...]
    type: str  # lower case
    indexed: bool = False  # an array of records, or a record inside one
    within: "Field | None" = None  # the speed or zone field this one is a component of (r.p.speed.v_tcp)

    @property
    def name(self) -> str:
        """rCell.move.speed: the register's name, and its key in the mapping file."""
        return ".".join((self.root.name, *self.path))

    @property
    def key(self) -> tuple[str, ...]:
        """The path as crossarm.convert.compute.Written keeps it."""
        return (self.root.name.upper(), *(p.upper() for p in self.path))


class Records:
    def __init__(self, modules: list[n.Module], symbols: Symbols, layouts: Layouts, written: Written,
                 value: Callable[[n.Expr], Any], own: Written | None = None) -> None:  # fmt: skip
        """`written`: what the programs of every task change, `own`: of this task (the modules given) when
        other tasks are converted too. `value(expr)`: the fixed value of an expression, or Unresolvable."""
        self.modules = modules
        self.symbols = symbols
        self.layouts = layouts
        self.shared = written
        self.own = own or written
        self.value = value
        self._same: dict[tuple[str, ...], tuple[Any, list[str]] | str] = {}

    def is_record(self, type_name: str | None) -> bool:
        return type_name is not None and type_name in self.layouts.layouts and type_name not in LAYOUTS

    def field(self, expr: n.Expr | None) -> Field | None:
        """The field (or the whole data) `expr` names, when its data is of a RECORD type of the backup."""
        chain = path_of(expr)
        if chain is None:
            return None
        decl = self.symbols.get(chain[0])
        if decl is None or not self.is_record(decl.type_name.lower()):
            return None
        type_name, path, indexed = decl.type_name.lower(), [], bool(decl.dims)
        within = None
        for step in chain[1:]:
            if step == "{}":
                indexed = True
                continue
            if type_name in MOTION and within is None:
                within = Field(decl, tuple(path), type_name, indexed)
            try:
                _, field_type = self.layouts.field(type_name, step)
            except Unresolvable:
                return None
            path.append(step.lower())
            type_name = field_type
        return Field(decl, tuple(path), type_name, indexed, within)

    def leaves(self, field: Field) -> list[Field]:
        """The fields of `field` that are not records themselves, in the order the RECORD declares them."""
        if not self.is_record(field.type):
            return [field]
        out = []
        for name, type_name in self.layouts.layouts[field.type]:
            out += self.leaves(Field(field.root, (*field.path, name), type_name, field.indexed))
        return out

    def written(self, field: Field) -> Written:
        """A PERS is shared by the tasks of a controller; a VAR (and a TASK or LOCAL PERS) is its task's own."""
        return self.shared if field.root.storage == "PERS" and field.root.scope is None else self.own

    def changed(self, field: Field) -> str | None:
        """Where a program changes this field (or a record it is part of); None when none does."""
        return self.written(field).where(field.key, field.root.type_name.lower())

    def initial(self, field: Field) -> Any:
        """The value the field has before any program changes it: declared, saved (PERS), else RAPID's zeros."""
        if field.root.init is not None:
            value = self.value(field.root.init)
        else:
            value = self.layouts.default(field.root.type_name.lower())
        type_name = field.root.type_name.lower()
        for name in field.path:
            index, type_name = self.layouts.field(type_name, name)
            value = value[index]
        return value

    def same_value(self, field: Field) -> tuple[Any, list[str]] | str:
        """(value, where) when every write of the field gives it the same fixed value; else why not."""
        if field.key in self._same:
            return self._same[field.key]
        self._same[field.key] = found = self._same_value(field)
        return found

    def _same_value(self, field: Field) -> tuple[Any, list[str]] | str:
        written = self.written(field)
        if written.everything:
            return written.everything
        if field.root.type_name.lower() in written.types:
            return written.types[field.root.type_name.lower()]
        values: dict[str, Any] = {}
        for where, stmt in self._statements():
            if not isinstance(stmt, n.Assign) or not (path := path_of(stmt.target)) or not _overlap(path, field.key):
                continue
            if path != field.key:
                return f"set with the data it is part of at {where}"
            try:
                values[where] = self.value(stmt.value)
            except Unresolvable as exc:
                return f"set at {where} to a value only known at run time ({exc})"
        others = [w for path, w in written.places.get(field.key[0], ()) if _overlap(path, field.key)]
        unknown = [w for w in others if w not in values]
        if unknown:
            return f"changed at {unknown[0]}"
        if not values:
            return "never set"
        distinct = []
        for where, value in values.items():
            if all(value != v for _, v in distinct):
                distinct.append((where, value))
        if len(distinct) > 1:
            return f"set to different values ({distinct[0][0]}, {distinct[1][0]})"
        return distinct[0][1], sorted(values)

    def read_before(self, field: Field, writes: list[str]) -> str | None:
        """Where the field is read before the routine setting it does, as far as the order of the calls tells:
        earlier in that routine, or in a caller before it calls that routine (or in a routine called then)."""
        routines = {r.name.upper(): (m, r) for m in self.modules for r in m.routines}
        for where in writes:
            place, _, line = where.rpartition(" l.")
            name = place.rpartition(".")[2].upper()
            if name not in routines:
                continue
            module, routine = routines[name]
            for stmt in walk_statements(routine.body):
                if stmt.span.line >= int(line):
                    break
                if self._reads_in(stmt, field, set()):
                    return f"{module.name}.{routine.name} l.{stmt.span.line}"
            for caller_module, caller in routines.values():
                for stmt in walk_statements(caller.body):
                    if isinstance(stmt, n.ProcCall) and stmt.name.upper() == name:
                        break
                    if self._reads_in(stmt, field, set()):
                        return f"{caller_module.name}.{caller.name} l.{stmt.span.line}"
        return None

    def _reads_in(self, stmt: n.Stmt, field: Field, seen: set[str]) -> bool:
        """Whether a statement reads the field, itself or through a routine it calls."""
        skip = stmt.target if isinstance(stmt, n.Assign) else None
        found = list(nodes(stmt, skip))
        if any(isinstance(node, n.Name | n.Component) and (path := path_of(node)) and _overlap(path, field.key)
               for node in found):  # fmt: skip
            return True
        called = [stmt.name] if isinstance(stmt, n.ProcCall) else []
        called += [node.name for node in found if isinstance(node, n.FuncCall)]
        routines = {r.name.upper(): r for m in self.modules for r in m.routines}
        for name in called:
            key = name.upper()
            if key in routines and key not in seen:
                seen.add(key)
                if any(self._reads_in(s, field, seen) for s in walk_statements(routines[key].body)):
                    return True
        return False

    def _statements(self) -> Iterable[tuple[str, n.Stmt]]:
        """Every statement of the modules with where it is, as Written names places."""
        for module in self.modules:
            for routine in module.routines:
                place = f"{module.name}.{routine.name}"
                stmts = list(walk_statements(routine.body))
                for handler in routine.handlers:
                    stmts += walk_statements(handler_body(handler) or ())
                for stmt in stmts:
                    yield f"{place} l.{stmt.span.line}", stmt


def recursive(modules: list[n.Module]) -> set[str]:
    """The routines (upper case) that can call themselves back, directly or through others."""
    calls: dict[str, set[str]] = {}
    for module in modules:
        for routine in module.routines:
            found = set()
            for stmt in walk_statements(routine.body):
                if isinstance(stmt, n.ProcCall):
                    found.add(stmt.name.upper())
                found |= {node.name.upper() for node in nodes(stmt) if isinstance(node, n.FuncCall)}
            calls[routine.name.upper()] = found
    out = set()
    for start, called in calls.items():
        stack, seen = list(called), set()
        while stack:
            name = stack.pop()
            if name == start:
                out.add(start)
                break
            if name in seen or name not in calls:
                continue
            seen.add(name)
            stack += calls[name]
    return out


def nodes(node: object, skip: object = None, root: bool = True) -> Iterable[object]:
    """Every node of a statement or an expression but `skip` (an assignment's target): not the statements
    nested in it, which walk_statements gives one by one."""
    if node is skip or (not root and isinstance(node, n.Stmt)):
        return
    yield node
    if isinstance(node, tuple | list):
        for item in node:
            yield from nodes(item, skip, False)
    elif hasattr(node, "__dataclass_fields__") and not isinstance(node, n.Span):
        for name in node.__dataclass_fields__:
            yield from nodes(getattr(node, name), skip, False)
