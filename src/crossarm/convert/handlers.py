# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID error handlers, read for what TP can do with them.

TP has no exceptions: an error stops the program with an alarm. Most of an ERROR handler has no
equivalent, but its commonest use does: a wait with a time limit, and what to do when
it runs out.

    WaitUntil diDone=1\\MaxTime:=2;          $WAITTMOUT=200
    nNext:=1;                           ->  WAIT (DI[1]=ON) TIMEOUT,LBL[1]
  ERROR                                     LBL[1]
    TEST ERRNO                              R[1:nNext]=1
    CASE ERR_WAIT_MAXTIME:
      TRYNEXT;
    ENDTEST

What the handler does for ERR_WAIT_MAXTIME is written at the timeout label of each such wait, RETRY
jumping back to the wait and TRYNEXT past it. A handler doing nothing but that, and passing any other
error on, is then converted. So is a handler that only passes errors on (`RAISE;`): the error reaches
the caller the same way on both controllers.
"""

import re
from dataclasses import dataclass

from crossarm.rapid import nodes as n
from crossarm.rapid import parse_text

TIMEOUT = "ERR_WAIT_MAXTIME"
JUMPS = frozenset({"RETRY", "TRYNEXT", "RAISE"})  # Unsupported kinds that leave the handler


def body(handler: n.Unsupported) -> tuple[n.Stmt, ...] | None:
    """The handler's statements, read by the parser with their line numbers in the module; None if unreadable."""
    lines = handler.raw.splitlines()
    head = re.sub(r"^\s*(ERROR|UNDO|BACKWARD)\s*(\([^)]*\))?", "", lines[0], flags=re.IGNORECASE) if lines else ""
    # Blank lines first, so that each statement keeps the line it has in the module.
    text = "\n" * (handler.span.line - 1) + "MODULE H PROC h() " + head + "\n" + "\n".join(lines[1:]) + "\nENDPROC ENDMODULE\n"
    parsed = parse_text(text)
    if parsed.module is None or not parsed.ok:
        return None
    return parsed.module.routines[0].body


def _is(stmt: n.Stmt, *kinds: str) -> bool:
    return isinstance(stmt, n.Unsupported) and stmt.kind in kinds


def leaves(stmts: tuple[n.Stmt, ...]) -> bool:
    """Whether a block always ends in RETRY, TRYNEXT, RAISE or RETURN: what follows it never runs."""
    real = [s for s in stmts if not isinstance(s, n.Comment)]
    if not real:
        return False
    last = real[-1]
    if _is(last, *JUMPS) or isinstance(last, n.Return | n.Exit):
        return True
    if isinstance(last, n.If):
        return bool(last.else_body) and leaves(last.else_body) and all(leaves(b.body) for b in last.branches)
    if isinstance(last, n.Test):
        return last.default is not None and leaves(last.default) and all(leaves(c.body) for c in last.cases)
    return False


def _names_timeout(expr: n.Expr) -> bool:
    return isinstance(expr, n.Name) and expr.name.upper() == TIMEOUT


def _errno(expr: n.Expr) -> bool:
    return isinstance(expr, n.Name) and expr.name.upper() == "ERRNO"


@dataclass(frozen=True, slots=True)
class OnTimeout:
    """What a handler does when a wait runs out of time: `steps`, then the end of the routine unless they leave."""

    steps: tuple[n.Stmt, ...]
    only: bool  # the handler does nothing for other errors but pass them on


def on_timeout(stmts: tuple[n.Stmt, ...]) -> OnTimeout | None:
    """The ERR_WAIT_MAXTIME path through a handler, for its three shapes; None for any other.

    `TEST ERRNO CASE ERR_WAIT_MAXTIME: ...`, `IF ERRNO=ERR_WAIT_MAXTIME THEN ...` (each maybe followed by
    what runs for every error), and a handler with no test at all (`TRYNEXT;`), which takes every error.
    """
    real = tuple(s for s in stmts if not isinstance(s, n.Comment))
    if not real:
        return None
    first, rest = real[0], real[1:]
    passes_on = all(_is(s, "RAISE") for s in rest)  # what follows the dispatch, for other errors
    match first:
        case n.Test(subject=subject, cases=cases, default=default) if _errno(subject):
            chosen = [c for c in cases if any(_names_timeout(v) for v in c.values)]
            if chosen:
                branch = chosen[0].body
            elif default is not None:
                branch = default
            else:
                return None
            only = (all(all(_names_timeout(v) for v in c.values) for c in cases) and default is None
                    and (passes_on or not rest))  # fmt: skip
        case n.If(branches=(n.IfBranch(condition=n.BinaryOp(op="=", left=left, right=right), body=branch),),
                  else_body=()) if _errno(left) and _names_timeout(right):  # fmt: skip
            only = passes_on or not rest
        case _ if only_passes_on(real):
            return None  # the timeout goes to the caller
        case _:
            return OnTimeout(real, only=False)  # no test on the error: every error takes this path
    steps = branch if leaves(branch) else branch + rest
    return OnTimeout(tuple(steps), only)


def only_passes_on(stmts: tuple[n.Stmt, ...]) -> bool:
    """`RAISE;` or `RAISE ERR_X;` alone: the error goes to the caller, as an alarm would on FANUC."""
    real = [s for s in stmts if not isinstance(s, n.Comment)]
    return bool(real) and all(_is(s, "RAISE") for s in real)
