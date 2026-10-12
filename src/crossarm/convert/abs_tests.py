# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""`Abs(x) > c` in a condition, as two comparisons TP makes: `x > c OR x < -c`.

TP has no absolute value. Compared with a constant c >= 0 (a CONST or a literal), the test unfolds into tests on x
alone, which TP writes as any other comparison: `IF (PR[k,2]>(-30))` is measured (C4), as negative constants.
"""

from __future__ import annotations

from collections.abc import Callable

from crossarm.rapid import nodes as n

_MIRROR = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "=": "=", "<>": "<>"}


def _abs_of(expr: n.Expr) -> n.Expr | None:
    if isinstance(expr, n.FuncCall) and expr.name.upper() == "ABS" and len(expr.args) == 1 and expr.args[0].name is None:
        return expr.args[0].value
    return None


def unfold_abs(expr: n.Expr, constant: Callable[[n.Expr], float | None]) -> n.Expr:
    """`expr` with each comparison of Abs(x) with a constant c >= 0 written as comparisons of x; the rest as it is.
    `constant(e)`: the value of e when it is a constant, else None."""
    match expr:
        case n.UnaryOp(op="NOT", operand=operand):
            unfolded = unfold_abs(operand, constant)
            return expr if unfolded is operand else n.UnaryOp(expr.span, "NOT", unfolded)
        case n.BinaryOp(op="AND" | "OR", left=left, right=right):
            a, b = unfold_abs(left, constant), unfold_abs(right, constant)
            return expr if (a, b) == (left, right) else n.BinaryOp(expr.span, expr.op, a, b)
        case n.BinaryOp(op=op, left=left, right=right) if op in _MIRROR:
            if (x := _abs_of(left)) is not None:
                limit = right
            elif (x := _abs_of(right)) is not None:
                op, limit = _MIRROR[op], left
            else:
                return expr
            value = constant(limit)
            if value is None or value < 0 or _abs_of(limit) is not None:
                return expr
            span = expr.span
            low = n.UnaryOp(span, "-", limit)
            either = op in (">", ">=", "=")  # beyond the limit on either side; else within it
            mirrored = {">": "<", ">=": "<=", "<": ">", "<=": ">=", "=": "=", "<>": "<>"}[op]
            return n.BinaryOp(span, "OR" if either else "AND", n.BinaryOp(span, op, x, limit),
                              n.BinaryOp(span, mirrored, x, low))  # fmt: skip
    return expr
