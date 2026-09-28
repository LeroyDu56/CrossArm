# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Conditions made of the backup's own bool functions, written as the test those functions make.

TP has no function a condition could call. Yet RAPID programs often wrap their tests in small
FUNCs — `HasVision()`, `InTestMode()` — and a condition calling one used to be a TODO that
took the whole IF block with it.

A bool FUNC without parameters whose body only returns a value is replaced by that value:

    FUNC bool HasVision()                     IF HasVision()=TRUE THEN
      IF diNoVision=0 OR RobOS()=FALSE THEN     ->  IF (DI[5]=OFF) THEN
        RETURN TRUE;
      ELSE
        RETURN FALSE;
      ENDIF
    ENDFUNC

`RobOS()` (FALSE on a virtual controller only) is TRUE, since the programs are made to run on a
real robot; what that leaves constant folds away. A function that does anything else — reads a
local, loops, writes data, takes a parameter — is left alone, and the condition stays a TODO.
"""

from collections.abc import Callable

from crossarm.rapid import nodes as n

MAX_DEPTH = 8  # a function calling a function...: past that, give up rather than loop
REAL_CONTROLLER = "ROBOS"  # system function: TRUE on a real controller, FALSE in RobotStudio


class Inliner:
    def __init__(self, modules: list[n.Module], is_const_bool: Callable[[str], bool | None],
                 on_assumption: Callable[[str], None], is_local: Callable[[str], bool] = lambda _: False) -> None:  # fmt: skip
        """`is_const_bool(name)`: the value of a CONST bool, None for anything else.
        `on_assumption(key)` is called when RobOS() is taken as TRUE, and when a function is inlined.
        `is_local(name)`: a data of the calling routine, which would hide the one the function reads."""
        self.functions = {
            r.name.upper(): r for m in modules for r in m.routines
            if r.kind == "FUNC" and (r.return_type or "").lower() == "bool" and not r.params.strip()
        }  # fmt: skip
        self.is_const_bool = is_const_bool
        self.on_assumption = on_assumption
        self.is_local = is_local
        self._bodies: dict[str, n.Expr | None] = {}

    def simplify(self, expr: n.Expr, depth: int = 0) -> n.Expr:
        """expr with the backup's bool functions inlined and constant parts folded (maybe to an n.Bool)."""
        match expr:
            case n.FuncCall(name=name, args=()) if name.upper() == REAL_CONTROLLER:
                self.on_assumption(REAL_CONTROLLER)
                return n.Bool(expr.span, True)
            case n.FuncCall(name=name, args=()) if name.upper() in self.functions and depth < MAX_DEPTH:
                body = self.body(name.upper())
                if body is None or any(self.is_local(used) for used in _names(body)):
                    return expr
                self.on_assumption(name.upper())
                return self.simplify(body, depth + 1)
            case n.Name(name=name) if self.is_const_bool(name) is not None:
                return n.Bool(expr.span, bool(self.is_const_bool(name)))
            case n.UnaryOp(op="NOT", operand=operand):
                inner = self.simplify(operand, depth)
                return n.Bool(expr.span, not inner.value) if isinstance(inner, n.Bool) else n.UnaryOp(expr.span, "NOT", inner)
            case n.BinaryOp(op="AND" | "OR", left=left, right=right):
                return self._logic(expr, self.simplify(left, depth), self.simplify(right, depth))
            case n.BinaryOp(op="=" | "<>", left=left, right=right) if isinstance(left, n.Bool) or isinstance(right, n.Bool):
                # A bool compared with TRUE / FALSE: `f()=TRUE` is f(), `f()=FALSE` is NOT f().
                constant, other = (left, right) if isinstance(left, n.Bool) else (right, left)
                keep = constant.value == (expr.op == "=")
                inner = self.simplify(other, depth)
                if isinstance(inner, n.Bool):
                    return n.Bool(expr.span, inner.value == keep)
                return inner if keep else self.simplify(n.UnaryOp(expr.span, "NOT", inner), depth)
            case n.BinaryOp(op=op, left=left, right=right):
                simpler = n.BinaryOp(expr.span, op, self.simplify(left, depth), self.simplify(right, depth))
                return expr if simpler == expr else simpler
        return expr

    @staticmethod
    def _logic(expr: n.BinaryOp, left: n.Expr, right: n.Expr) -> n.Expr:
        """AND / OR with what folded to a constant taken out: `x OR FALSE` is x, `x AND FALSE` is FALSE."""
        absorbing = expr.op == "OR"  # TRUE absorbs an OR, FALSE an AND
        for side, other in ((left, right), (right, left)):
            if isinstance(side, n.Bool):
                return n.Bool(expr.span, absorbing) if side.value == absorbing else other
        return n.BinaryOp(expr.span, expr.op, left, right)

    def body(self, name: str) -> n.Expr | None:
        """What the function returns, as one expression; None when it does more than return a value."""
        if name not in self._bodies:
            self._bodies[name] = _returned(self.functions[name].body)
        return self._bodies[name]


def _names(expr: n.Expr) -> set[str]:
    """Every data name an expression reads (function names excluded)."""
    match expr:
        case n.Name(name=name):
            return {name}
        case n.UnaryOp(operand=operand):
            return _names(operand)
        case n.BinaryOp(left=left, right=right):
            return _names(left) | _names(right)
        case n.Component(base=base):
            return _names(base)
        case n.Index(base=base, indices=indices):
            return _names(base).union(*(_names(i) for i in indices))
        case n.FuncCall(args=args) | n.Aggregate(items=args):
            values = [a.value if isinstance(a, n.Arg) else a for a in args]
            return set().union(*(_names(v) for v in values if v is not None))
    return set()


def _returned(body: tuple[n.Stmt, ...]) -> n.Expr | None:
    """The one value a body returns, as an expression; None when it does anything else.

    `RETURN e;` -> e.  `IF c THEN RETURN a; ELSE RETURN b; ENDIF` (or that IF without its ELSE, followed
    by `RETURN b;`) -> c, NOT c, c AND a, c OR b...: as long as a or b is TRUE or FALSE, so that the
    test c is not copied twice into the condition.
    """
    stmts = [s for s in body if not isinstance(s, n.Comment)]
    match stmts:
        case [n.Return(value=value)] if value is not None:
            return value
        case [n.If(branches=(branch,), else_body=else_body)] if else_body:
            otherwise = _returned(else_body)
        case [n.If(branches=(branch,), else_body=()), n.Return(value=value)] if value is not None:
            otherwise = value
        case _:
            return None
    then = _returned(branch.body)
    if then is None or otherwise is None:
        return None
    test, span = branch.condition, branch.condition.span
    untested = n.UnaryOp(span, "NOT", test)
    match then, otherwise:
        case n.Bool(value=a), n.Bool(value=b):
            return then if a == b else (test if a else untested)
        case n.Bool(value=True), _:
            return n.BinaryOp(span, "OR", test, otherwise)
        case n.Bool(value=False), _:
            return n.BinaryOp(span, "AND", untested, otherwise)
        case _, n.Bool(value=False):
            return n.BinaryOp(span, "AND", test, then)
        case _, n.Bool(value=True):
            return n.BinaryOp(span, "OR", untested, then)
    return None
