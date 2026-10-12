# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Errors the program raises itself (`RAISE ERR_X;` of its own errnum, `RAISE 12;`), and the ERROR handlers that
take them (a mixin of the routine translator, and the converter's part).

TP has no exceptions, but an error the program raises itself is only a jump: CrossArm writes it with a register.
How RAPID runs it (RobotStudio, RobotWare 8.1, 2026-10-12): an error raised in a routine without an ERROR handler
stops the program ("unhandled error", event 40229) even when its caller has one; a routine's handler takes the
errors raised in it, and its `RAISE` passes the error on to its caller, at the line that called the routine.

    PROC CloseGrip()                                    CLOSEGRIP:  R[e]=0
        IF diGripClosed=0 THEN                                      IF (DI[2]=OFF) THEN
            RAISE ERR_GRIP_LOST;                                    R[e]=10000          (the error's code)
        ENDIF                                                       END                 (RAISE in the handler)
    ERROR  RAISE;                                       PICKCYCLE:  R[r]=0
                                                                    LBL[1]
    PROC PickCycle()                                                CALL CLOSEGRIP
        CloseGrip;                                                  IF R[e]=0,JMP LBL[2]
    ERROR                                                           R[en]=R[e]          (ERRNO)
        IF ERRNO=ERR_GRIP_LOST THEN                                 R[e]=0
            RETRY;                                                  IF (R[en]=10000) THEN
        ENDIF                                                       R[r]=R[r]+1
                                                                    IF R[r]<=4,JMP LBL[1]  (RAPID retries 4 times)
                                                                    ABORT
                                                                    ENDIF
                                                                    ABORT               (end of the handler)
                                                                    LBL[2]

R[e] (CROSSARM.RAISED) holds the error a routine ends with, 0 for none: each routine that can end with one sets it
to 0 first. After the CALL of such a routine, and at a RAISE in the body, the caller's handler is written where the
error happens, as the timeout path of a wait is: RETRY jumps back (at most 4 times, RAPID's No Of Retry, then the
program stops), TRYNEXT goes on with the next line, RETURN ends the routine, `RAISE` sets R[e] and ends it (the
caller tests it), RAISE in a routine without a handler and the end of a handler stop the program (ABORT), as RAPID
does. ERRNO is the register R[en] (CROSSARM.ERRNO), the program's own errors are numbers: a CONST errnum its value,
the others 10000, 10001... (BookErrNo, a remark here); an error of the system (ERR_DIVZERO...) never comes this way:
on FANUC it stops the program with its alarm, and a handler taking such errors stays TODO.
"""

import re
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.compute import Unknown
from crossarm.convert.handlers import body as handler_body
from crossarm.convert.handlers import leaves, only_passes_on
from crossarm.rapid import nodes as n
from crossarm.rapid.walk import walk_statements

if TYPE_CHECKING:
    from crossarm.convert.translate import Converter

RETRIES = 4  # RAPID's default No Of Retry (system parameters, controller): one more RETRY stops the program
BOOKED = 10000  # the first number BookErrNo gives (RobotStudio: 10000, 10001...)
_RAISE = re.compile(r"\s*RAISE\s*(\w*)\s*;?\s*$", re.IGNORECASE)

NONE, PASSES, HANDLER, UNREADABLE = "none", "passes", "handler", "unreadable"


def raised_name(stmt: n.Stmt) -> str | None:
    """'ERR_X' / '12' of `RAISE ERR_X;`, '' of `RAISE;`, None for any other statement."""
    if not (isinstance(stmt, n.Unsupported) and stmt.kind == "RAISE"):
        return None
    found = _RAISE.match(stmt.raw)
    return found[1].upper() if found else None


class RaisedErrors:
    """The converter's part: the program's own error numbers, and how each PROC's handler takes them."""

    def __init__(self, procs: Mapping[str, n.Routine], type_of: Callable[[str], str | None],
                 constant: Callable[[str], float | None]) -> None:  # fmt: skip
        self.handlers: dict[str, tuple[n.Stmt, ...] | None] = {}
        self.kinds: dict[str, str] = {}
        self.codes: dict[str, int] = {}  # upper-case error name or number -> its number
        booked = BOOKED
        for key, routine in procs.items():
            handlers = [h for h in routine.handlers if h.kind == "ERROR_HANDLER"]
            stmts = handler_body(handlers[0]) if handlers else None
            self.handlers[key] = stmts
            if not handlers:
                self.kinds[key] = NONE
            elif stmts is None:
                self.kinds[key] = UNREADABLE
            else:
                self.kinds[key] = PASSES if only_passes_on(stmts) else HANDLER
            for stmt in [*walk_statements(routine.body), *walk_statements(stmts or ())]:
                name = raised_name(stmt)
                if not name or name in self.codes:
                    continue
                if name.isdigit() and 1 <= int(name) <= 90:
                    self.codes[name] = int(name)
                elif type_of(name) == "errnum":
                    value = constant(name)
                    if value is not None and value > 0 and value == int(value):
                        self.codes[name] = int(value)
                    else:
                        self.codes[name], booked = booked, booked + 1
        # The PROCs that can end with an error for their caller: a RAISE in their handler, of their own errors.
        self.passes: set[str] = set()
        changed = True
        while changed:
            changed = False
            for key, routine in procs.items():
                if key in self.passes or self.kinds[key] == NONE:
                    continue
                stmts = self.handlers[key] or ()
                raised = [raised_name(s) for s in walk_statements(stmts)]
                reached = any(self.own(s) or self.raising_call(s) for s in walk_statements(routine.body))
                if any(r and r in self.codes for r in raised) or (reached and "" in raised):
                    self.passes.add(key)
                    changed = True

    def own(self, stmt: n.Stmt) -> bool:
        """`RAISE ERR_X;` of an error of the program's own."""
        name = raised_name(stmt)
        return bool(name) and name in self.codes

    def raising_call(self, stmt: n.Stmt) -> bool:
        return isinstance(stmt, n.ProcCall) and stmt.name.upper() in self.passes

    def code(self, expr: n.Expr) -> int | None:
        """The number of an error of the program's own, named in an expression."""
        if isinstance(expr, n.Name):
            return self.codes.get(expr.name.upper())
        return None


class RaisedPaths:
    """The routine translator's part that writes a RAISE and the handler path after a call (mixed into it)."""

    c: "Converter"
    routine: n.Routine
    error_jumps: tuple[int, int] | None
    strict: int
    raised_sites: int
    epilogue: list[str]

    def raised_reset(self) -> None:
        """First line of a routine that can end with an error: none yet."""
        if self.routine.kind == "PROC" and self.routine.name.upper() in self.c.raised.passes:
            self.emit(f"{self.raised_register()}=0")  # type: ignore[attr-defined]

    def raised_register(self) -> str:
        return self.c.written_register("Raised", key="CROSSARM.RAISED")

    def errno_register(self) -> str:
        return self.c.written_register("ErrNo", key="CROSSARM.ERRNO")

    def _kind(self) -> str:
        return self.c.raised.kinds.get(self.routine.name.upper(), NONE) if self.routine.kind == "PROC" else UNREADABLE

    def raising_call(self, stmt: n.Stmt) -> bool:
        """A call of a routine that can end with an error, written as a CALL here."""
        if not self.c.raised.raising_call(stmt):
            return False
        name = stmt.name.upper()  # type: ignore[attr-defined]
        return name in self.c.program_names and name not in self.c.externals and name not in self.c.move_routines

    def error_value(self, expr: n.Expr) -> str | None:
        """ERRNO in a handler written after a raised error: its register; an error of the program's own: its number;
        an error of the system there: -1, never the number of a raised error."""
        if not isinstance(expr, n.Name):
            return None
        if (code := self.c.raised.code(expr)) is not None:
            return str(code)
        if getattr(self, "errno_live", False):
            if expr.name.upper() == "ERRNO":
                return self.errno_register()
            if expr.name.upper().startswith("ERR_") and self.c.symbols.type_of(expr.name) in (None, "errnum"):
                return "(-1)"
        return None

    def leave_with_error(self) -> None:
        for text in self.epilogue:
            self.emit(text)  # type: ignore[attr-defined]
        self.emit("END")  # type: ignore[attr-defined]

    def raise_stmt(self, s: n.Unsupported) -> None:
        """A RAISE: in a handler path, the error for the caller; in the body, the error where it happens."""
        name = raised_name(s)
        if self.error_jumps is not None:  # in a handler's path: the routine ends, the caller tests R[e]
            if name and name in self.c.raised.codes:
                self.emit(f"{self.raised_register()}={self.c.raised.codes[name]}")  # type: ignore[attr-defined]
            elif name == "" and getattr(self, "errno_live", False):
                self.emit(f"{self.raised_register()}={self.errno_register()}")  # type: ignore[attr-defined]
            else:
                raise Untranslatable(f"{' '.join(s.raw.split())}: only an error of the program's own is passed on"
                                     " to the caller", Blocker.rapid("RAISE"))  # fmt: skip
            self.leave_with_error()
            return
        if not name or name not in self.c.raised.codes:
            raise Untranslatable(f"{' '.join(s.raw.split())}: only the program's own errors (errnum data of the"
                                 " backup, numbers 1 to 90) are converted", Blocker.rapid("RAISE"))  # fmt: skip
        code = self.c.raised.codes[name]
        self.raised_site(s, lambda: self.emit(f"{self.raised_register()}={code}"), always=True)  # type: ignore[attr-defined]

    def raised_site(self, stmt: n.Stmt, write: Callable[[], None], always: bool = False) -> None:
        """`write` (a CALL of a routine that can end with an error, or the error set by a RAISE), then what
        this routine does with that error."""
        kind = self._kind()
        if kind == HANDLER and self.error_jumps is not None:
            # An error raised in the ERROR handler itself goes to the caller (RAPID): the handler is not written
            # again for it, which a call in it of a routine ending with that error repeated without end.
            kind = PASSES if self.routine.name.upper() in self.c.raised.passes else NONE
        if kind == UNREADABLE:
            raise Untranslatable("this routine's ERROR handler could not be read: what it does with the error is"
                                 " not known", Blocker.rapid("ERROR_HANDLER"))  # fmt: skip
        if kind == NONE and always:
            self.emit("ABORT")  # type: ignore[attr-defined]  # RAISE without a handler: RAPID stops the program
            return
        raised = self.raised_register()
        if kind in (NONE, PASSES):
            write()
            after = None if always else self.label()  # type: ignore[attr-defined]
            if after is not None:
                self.emit(f"IF {raised}=0,JMP LBL[{after}]")  # type: ignore[attr-defined]
            if kind == NONE:
                self.emit("ABORT")  # type: ignore[attr-defined]  # no handler: RAPID stops the program
            else:
                self.leave_with_error()  # ERROR RAISE;: the caller takes it
            if after is not None:
                self.emit(f"LBL[{after}]")  # type: ignore[attr-defined]
            return
        steps = self.c.raised.handlers[self.routine.name.upper()] or ()
        self.raised_sites += 1
        counter = None
        if any(isinstance(s, n.Unsupported) and s.kind == "RETRY" for s in walk_statements(steps)):
            counter = self.c.written_register(f"{self.routine.name}Retries", key=f"CROSSARM.RETRY.{self.routine.name.upper()}")
            self.emit(f"{counter}=0")  # type: ignore[attr-defined]
        retry = self.label()  # type: ignore[attr-defined]
        if counter is not None:
            self.emit(f"LBL[{retry}]")  # type: ignore[attr-defined]
        write()
        after = self.label()  # type: ignore[attr-defined]
        if not always:
            self.emit(f"IF {raised}=0,JMP LBL[{after}]")  # type: ignore[attr-defined]
        errno = self.errno_register()
        self.emit(f"{errno}={raised}")  # type: ignore[attr-defined]
        self.emit(f"{raised}=0")  # type: ignore[attr-defined]
        saved = (self.error_jumps, getattr(self, "retry_counter", None), getattr(self, "errno_live", False))
        self.error_jumps, self.retry_counter, self.errno_live = (retry, after), counter, True
        self.strict += 1
        try:
            self.block(steps)  # type: ignore[attr-defined]
        finally:
            self.error_jumps, self.retry_counter, self.errno_live = saved
            self.strict -= 1
        self.forget(steps, Unknown(f"may be changed by the ERROR handler, after l.{stmt.span.line}"))  # type: ignore[attr-defined]
        if not leaves(steps):
            self.emit("ABORT")  # type: ignore[attr-defined]  # the end of a handler: RAPID stops the program
        self.emit(f"LBL[{after}]")  # type: ignore[attr-defined]

    def retry_jump(self) -> None:
        """RETRY in a handler path: back to the line that raised; RAPID gives up after 4."""
        retry, _ = self.error_jumps  # type: ignore[misc]
        counter = getattr(self, "retry_counter", None)
        if counter is None:
            self.emit(f"JMP LBL[{retry}]")  # type: ignore[attr-defined]
            return
        self.emit(f"{counter}={counter}+1")  # type: ignore[attr-defined]
        self.emit(f"IF {counter}<={RETRIES},JMP LBL[{retry}]")  # type: ignore[attr-defined]
        self.emit("ABORT")  # type: ignore[attr-defined]

    def book_error(self, call: n.ProcCall) -> bool:
        """BookErrNo of an error the program raises: its number is fixed here, a remark says which."""
        args = [a.value for a in call.args]
        if len(args) != 1 or (code := self.c.raised.code(args[0])) is None:
            return False
        self.emit(f"!{args[0].name} is error {code}"[:33].rstrip())  # type: ignore[attr-defined, union-attr]
        return True

    def handler_written(self) -> bool:
        """Whether the routine's ERROR handler was written in full at the lines raising the program's own errors:
        it tests ERRNO against those errors only, and does nothing for the others but pass them on or end."""
        if self._kind() != HANDLER:
            return False
        steps = self.c.raised.handlers[self.routine.name.upper()] or ()
        tested = _tested(steps)
        return bool(tested) and tested <= set(self.c.raised.codes) and _only_dispatch(steps)


def _tested(stmts) -> set[str]:
    from crossarm.convert.unsupported import tested_errors

    return tested_errors(stmts)


def _only_dispatch(stmts: tuple[n.Stmt, ...]) -> bool:
    """`TEST ERRNO` without DEFAULT / `IF ERRNO=...` without ELSE, then nothing or RAISE: other errors go on."""
    real = [s for s in stmts if not isinstance(s, n.Comment)]
    if not real:
        return False
    first, rest = real[0], real[1:]
    if not all(raised_name(s) == "" for s in rest):
        return False
    if isinstance(first, n.Test):
        return first.default is None
    if isinstance(first, n.If):
        return not first.else_body
    return False
