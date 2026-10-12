# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A PERS one task declares without a value, another with one: the value it has on the controller.

A PERS is shared by the tasks of a controller. The usual way of sharing one is to give it its value in one task
(`PERS num nRings := 3;`) and to declare it without value in the others (`PERS num nRings;`): those read the value
the first one gives. Converted task by task, the second task saw a PERS "with no initial value (set at run time)".
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

from crossarm.rapid import nodes as n


def _literal(expr: n.Expr) -> bool:
    """A value written out (numbers, bools, texts, aggregates of them): it means the same in every task."""
    match expr:
        case n.Number() | n.Bool() | n.String():
            return True
        case n.UnaryOp(op="-" | "+", operand=operand):
            return _literal(operand)
        case n.Aggregate(items=items):
            return all(_literal(i) for i in items)
    return False


def _shared(decl: n.DataDecl) -> bool:
    return decl.storage == "PERS" and decl.scope not in ("LOCAL", "TASK")


def saved_values(modules: Iterable[n.Module]) -> dict[str, n.DataDecl]:
    """Upper-case name -> the declaration giving a PERS shared by the tasks its value, from every task of the
    controller; left out when two tasks give it different values or types (which one the controller keeps is not
    known)."""
    found: dict[str, n.DataDecl] = {}
    clashing: set[str] = set()
    for module in modules:
        for decl in module.declarations:
            if not _shared(decl) or decl.init is None or not _literal(decl.init):
                continue
            key = decl.name.upper()
            seen = found.setdefault(key, decl)
            if (seen.type_name.lower(), len(seen.dims), seen.init) != (decl.type_name.lower(), len(decl.dims),
                                                                       decl.init):  # fmt: skip
                clashing.add(key)
    return {key: decl for key, decl in found.items() if key not in clashing}


def given_value(decl: n.DataDecl, saved: dict[str, n.DataDecl]) -> n.DataDecl:
    """`decl` with the value another task gives it, when it is a shared PERS declared without one; else itself."""
    if decl.init is not None or not _shared(decl):
        return decl
    other = saved.get(decl.name.upper())
    if other is None or (other.type_name.lower(), len(other.dims)) != (decl.type_name.lower(), len(decl.dims)):
        return decl
    return dataclasses.replace(decl, init=other.init)
