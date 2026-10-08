# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The fields of a tool or a work object, followed one by one as a routine changes them (a mixin of the routine
translator).

A calibration routine sets a tool's or a work object's fields one statement at a time: `tGun.robhold := TRUE`,
`tGun.tload.mass := 2.5`, `wTable.uframe := ...`, `wTable.oframe := [[0,0,0],[1,0,0,0]]`. What the TP side needs
is the frame: the tool on the faceplate (robhold, tframe) or uframe x oframe (robhold, uframe, oframe). The other
fields write no frame:

  - tload: the payload (a PAYLOAD schedule on the FANUC, crossarm.convert.translate);
  - ufprog: FALSE for a work object a mechanical unit moves (coordinated motion): said, nothing written;
  - ufmec: the name of that unit, a text: said when it names another unit than the robot, nothing written.

So each field is known or not on its own (crossarm.convert.compute.Hole): a field changed by the programs, or
set by a statement left TODO, makes only what reads that field unknown. A field every program sets, alone, to
the value it is declared with does not change at all (Computer.invariant): setting it writes nothing.
"""

from typing import Any

from crossarm.convert.blockers import Blocker
from crossarm.convert.compute import (
    FRAME_FIELDS,
    FRAME_RECORDS,
    LAYOUTS,
    Hole,
    Typed,
    Unknown,
    first_hole,
    path_of,
)
from crossarm.convert.runtime_points import expr_nodes
from crossarm.convert.values import Unresolvable
from crossarm.rapid import nodes as n


class FrameFields:
    """Mixin of the routine translator: needs c, known, emit(), warn()."""

    _field_value: tuple[n.Stmt, str, Typed] | None = None  # a frame field set to a known value, its frame not loaded

    def frame_field(self, stmt: n.Stmt) -> tuple[tuple[str, ...], Any] | None:
        """(path, declaration) when the statement sets one field (or a part of one) of a tool or work object, and
        changes nothing else of it (a routine its value calls may change its own arguments, not given that data)."""
        if not isinstance(stmt, n.Assign) or not (path := path_of(stmt.target)) or len(path) < 2 or "{}" in path[:2]:
            return None
        decl = self.c.symbols.get(path[0])  # type: ignore[attr-defined]
        if decl is None or decl.dims or decl.type_name.lower() not in FRAME_RECORDS or path[0] in self.c.volatile:  # type: ignore[attr-defined]
            return None
        if path[1] not in (name.upper() for name, _type in LAYOUTS[decl.type_name.lower()]):
            return None  # not a field of it: the statement says why it stays TODO
        names, anything = self.c.effects.of((stmt,))  # type: ignore[attr-defined]
        if anything or (names != {path[0]} and path[0] in {e.name.upper() for e in expr_nodes(stmt.value) if isinstance(e, n.Name)}):
            return None
        return path, decl

    def forget_field(self, stmt: n.Stmt, why: Unknown) -> bool:
        """A statement left TODO that sets one field of a tool or work object: that field alone is unknown after it,
        the others keep their values (False: not such a statement, or the rest of the data is not known either)."""
        if self._field_value is not None and self._field_value[0] is stmt:  # its value is known, its frame not loaded
            _stmt, root, new = self._field_value
            self._field_value = None
            self.known[root] = new  # type: ignore[attr-defined]
            return True
        found = self.frame_field(stmt)
        if found is None:
            return False
        path, decl = found
        here = self.known.get(path[0])  # type: ignore[attr-defined]
        if isinstance(here, Unknown):
            return False
        type_name = decl.type_name.lower()
        try:
            base = here if isinstance(here, Typed) else self.c.computer.all_but(decl.name, path[:2])  # type: ignore[attr-defined]
        except Unresolvable:
            return False
        self.forget((stmt,), why)  # type: ignore[attr-defined]  # what else it may change: the arguments of a call
        value = list(base.value)
        index = [name.upper() for name, _type in LAYOUTS[type_name]].index(path[1])
        value[index] = Hole(f"'{decl.name}.{path[1].lower()}' {why.reason}", why.measured, here=True)
        self.known[path[0]] = Typed(value, type_name, 0)  # type: ignore[attr-defined]
        return True

    def frame_unknown(self, a: n.Assign, root_type: str, root: str, new: Typed) -> Hole | None:
        """After `a` worked out the whole new value: the field the frame needs that is not known (a Hole), or None.
        The value is kept for what reads its other fields when `a` is then left TODO (forget_field)."""
        hole = first_hole(new.value, FRAME_FIELDS[root_type], root_type)
        self._field_value = (a, root, new) if hole is not None else None
        return hole

    def field_without_frame(self, a: n.Assign, remark: str) -> bool:
        """`a` sets a field no frame depends on (ufprog, ufmec), or one that keeps its declared value: nothing to
        write but the RAPID line as a remark, and what it means said; the field unknown alone when its new value
        is. False: the frame changes."""
        found = self.frame_field(a)
        if found is None:
            return False
        path, decl = found
        invariant = self.c.computer.invariant(path)  # type: ignore[attr-defined]
        if path[1] not in ("UFPROG", "UFMEC") and not invariant:
            return False
        try:
            root, new = self.c.computer.assigned(a)  # type: ignore[attr-defined]
        except Unresolvable:
            root, new = path[0], None
        if not invariant:
            self._field_note(a, decl.name, path, new)
        self.emit(remark)  # type: ignore[attr-defined]
        if new is not None:
            self.known[root] = new  # type: ignore[attr-defined]
        elif not invariant:
            self.forget_field(a, Unknown(f"is set at l.{a.span.line} to a value only known at run time"))
        return True

    def _field_note(self, a: n.Assign, name: str, path: tuple[str, ...], new: Typed | None) -> None:
        index = 1 if path[1] == "UFPROG" else 2
        value = new.value[index] if new is not None and isinstance(new.value, list) else None
        if isinstance(value, Hole):
            value = None
        if path[1] == "UFPROG" and value is not True:
            self.warn(a, f"work object {name}: ufprog {'FALSE' if value is False else 'only known at run time'} here:"  # type: ignore[attr-defined]
                      " a work object moved by a mechanical unit (coordinated motion) is not converted, its UFRAME"
                      " does not follow the unit", Blocker.STATIONARY)  # fmt: skip
        elif path[1] == "UFMEC" and (value is None or (value and not str(value).upper().startswith("ROB_"))):
            unit = f"'{value}'" if value is not None else "a mechanical unit only known at run time"
            self.warn(a, f"work object {name}: ufmec names {unit}: nothing written on the FANUC, a work object moved"  # type: ignore[attr-defined]
                      " by another unit than the robot is not converted (coordinated motion)", Blocker.STATIONARY)  # fmt: skip
