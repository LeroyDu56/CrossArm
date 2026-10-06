# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Depth-first traversal helpers over the RAPID AST."""

import re
from collections.abc import Iterable, Iterator

from crossarm.rapid import nodes as n


def walk_statements(stmts: Iterable[n.Stmt]) -> Iterator[n.Stmt]:
    """Every statement, depth-first, including those nested in blocks."""
    for stmt in stmts:
        yield stmt
        match stmt:
            case n.If():
                for branch in stmt.branches:
                    yield from walk_statements(branch.body)
                yield from walk_statements(stmt.else_body)
            case n.For() | n.While():
                yield from walk_statements(stmt.body)
            case n.Test():
                for case in stmt.cases:
                    yield from walk_statements(case.body)
                yield from walk_statements(stmt.default or ())


def module_statements(module: n.Module | None) -> Iterator[n.Stmt | n.ModuleItem]:
    """Module-level items and every statement of every routine (handlers included)."""
    if module is None:
        return
    for item in module.body:
        if isinstance(item, n.Routine):
            yield from walk_statements(item.body)
            yield from item.handlers
        else:
            yield item


# A comma between two parameters, not one between the dimensions of an array ({*,*}); a backslash starts an
# optional one, with or without a comma before it ('num Area\switch XP|switch XM').
_PARAM_SPLIT = re.compile(r",(?![^{}]*\})|(?=\\)")


def split_params(raw: str) -> list[str]:
    """A routine's raw parameter list, one part per parameter (alternatives `|` kept together), stripped;
    'num n, INOUT byte out{*,*}' -> ['num n', 'INOUT byte out{*,*}']."""
    return [part.strip() for part in _PARAM_SPLIT.split(raw) if part.strip()]


def base_name(expr: n.Expr) -> str | None:
    """'p10' for p10, p10.trans.x or p10{2}; None for anything else."""
    while isinstance(expr, n.Component | n.Index):
        expr = expr.base
    return expr.name if isinstance(expr, n.Name) else None
