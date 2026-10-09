# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A routine called by its name worked out at run time (late binding), as calls to each routine it can name.

    %"Station_" + NumToStr(nStation,0)%;        SELECT R[3:nStation]=1,CALL STATION_1
    CallByVar "Station_", nStation;                    =2,CALL STATION_2 ...
    sNext := "Purge"; ... %sNext%;               IF SR[2:sNext]=SR[n],JMP ... CALL PURGE (one test per name)

TP calls a program by its name written in the line only. The names a late-bound call can take are deduced from
the backup: the texts a string variable is set to (constants, or a constant prefix and NumToStr of a num), or a
prefix and a num. A num whose values are known (set to constants only, or a FOR variable with constant bounds)
names exactly its routines, which must all be in the backup; any other names the PROCs of the backup that fit
"prefix<digits>suffix". The call is then a TEST on the num (SELECT, measured) or an IF chain comparing the text
(measured: `IF SR[a]=SR[b],JMP`), each branch the call to one routine, its arguments passed as written. A name
outside those makes RAPID raise ERR_REFUNKPRC: here the program ends (ABORT), with a warning.
"""

import dataclasses
import re
from typing import TYPE_CHECKING

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.diagnostics import Span
from crossarm.rapid import nodes as n
from crossarm.rapid import parse_text
from crossarm.rapid.to_pseudo import format_expr
from crossarm.rapid.walk import walk_statements

if TYPE_CHECKING:
    from crossarm.convert.translate import Converter

_DIGITS = re.compile(r"\d+")


def _respan(node, span: Span):
    """The node parsed from a scrap of text, every position set to the statement's own."""
    if isinstance(node, Span):
        return span
    if isinstance(node, tuple):
        return tuple(_respan(item, span) for item in node)
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        return dataclasses.replace(node, **{f.name: _respan(getattr(node, f.name), span) for f in dataclasses.fields(node)})
    return node


def parse_late_call(raw: str, span: Span) -> tuple[n.Expr, tuple[n.Arg, ...]] | None:
    """(name expression, arguments) of `%expr% args;`; None when it does not read."""
    text = raw.strip().rstrip(";").strip()
    if not text.startswith("%"):
        return None
    inside, end = False, None
    for i, char in enumerate(text[1:], start=1):  # the closing %, outside the texts
        if char == '"':
            inside = not inside
        elif char == "%" and not inside:
            end = i
            break
    if end is None:
        return None
    expr_text, args_text = text[1:end], text[end + 1:].strip()
    source = f"MODULE LateCall\nPROC p()\nx:={expr_text};\nLateCall {args_text};\nENDPROC\nENDMODULE\n"
    parsed = parse_text(source)
    if parsed.diagnostics or parsed.module is None:
        return None
    assign, call = parsed.module.routines[0].body
    if not (isinstance(assign, n.Assign) and isinstance(call, n.ProcCall)):
        return None
    return _respan(assign.value, span), _respan(call.args, span)


@dataclasses.dataclass(frozen=True, slots=True)
class _Pattern:
    """A routine name `prefix + NumToStr(number, 0) + suffix`."""

    prefix: str
    number: n.Expr
    suffix: str

    def routines(self, procs: dict[str, n.Routine]) -> dict[int, str]:
        """value -> the name RAPID builds, for the PROCs of the backup that fit."""
        found = {}
        for key, routine in procs.items():
            head, tail = self.prefix.upper(), self.suffix.upper()
            if key.startswith(head) and key.endswith(tail) and len(key) > len(head) + len(tail):
                digits = key[len(head):len(key) - len(tail)]
                if _DIGITS.fullmatch(digits) and (digits == "0" or not digits.startswith("0")):
                    found[int(digits)] = routine.name
        return dict(sorted(found.items()))

    def text(self, value: int) -> str:
        return f"{self.prefix}{value}{self.suffix}"


def _pieces(expr: n.Expr) -> list[n.Expr]:
    if isinstance(expr, n.BinaryOp) and expr.op == "+":
        return _pieces(expr.left) + _pieces(expr.right)
    return [expr]


def _pattern(expr: n.Expr, constant) -> _Pattern | str | None:
    """A constant text (str), a prefix + NumToStr(num, 0) + suffix pattern, or None. `constant(expr)`: its text if
    it is a constant one, else None."""
    pieces = _pieces(expr)
    texts = [constant(p) for p in pieces]
    if all(t is not None for t in texts):
        return "".join(texts)  # type: ignore[arg-type]
    numbers = [i for i, t in enumerate(texts) if t is None]
    if len(numbers) != 1:
        return None
    piece = pieces[numbers[0]]
    if not (isinstance(piece, n.FuncCall) and piece.name.upper() == "NUMTOSTR" and len(piece.args) == 2
            and all(a.name is None for a in piece.args) and constant_zero(piece.args[1].value)):  # fmt: skip
        return None
    i = numbers[0]
    return _Pattern("".join(texts[:i]), piece.args[0].value, "".join(texts[i + 1:]))  # type: ignore[arg-type]


def constant_zero(expr: n.Expr | None) -> bool:
    return isinstance(expr, n.Number) and expr.value == 0


class LateCalls:
    """The routine translator's part that writes late-bound calls (mixed into it)."""

    c: "Converter"
    # Comparing a routine's name: RAPID finds a routine whatever the case of its name, as TP compares texts.
    names_compared = False

    def late_call(self, stmt: n.Unsupported | n.ProcCall) -> None:
        if isinstance(stmt, n.ProcCall):  # CallByVar "prefix", number
            positional = [a.value for a in stmt.args if a.name is None]
            if len(positional) != 2 or len(stmt.args) != 2 or None in positional:
                raise Untranslatable("CallByVar: a prefix and a number are expected", Blocker.rapid("LATE_BINDING"))
            name = n.BinaryOp(stmt.span, "+", positional[0],  # type: ignore[arg-type]
                              n.FuncCall(stmt.span, "NumToStr", (n.Arg(stmt.span, positional[1]),
                                                                 n.Arg(stmt.span, n.Number(stmt.span, 0, "0")))))  # fmt: skip
            args: tuple[n.Arg, ...] = ()
            written = f"CallByVar {format_expr(positional[0])}, {format_expr(positional[1])}"  # type: ignore[arg-type]
        else:
            parsed = parse_late_call(stmt.raw, stmt.span)
            if parsed is None:
                raise Untranslatable("late-binding call %...%: its name does not read", Blocker.rapid("LATE_BINDING"))
            name, args = parsed
            written = f"%{format_expr(name)}%"
        self._late_call(stmt.span, name, args, written)

    def _late_call(self, span: Span, name: n.Expr, args: tuple[n.Arg, ...], written: str) -> None:
        blocker = Blocker.rapid("LATE_BINDING")
        procs = self.c.procs
        found = _pattern(name, self._constant_text)
        if isinstance(found, str):  # a constant name: a plain call
            self.stmt(n.ProcCall(span, found, args))  # type: ignore[attr-defined]
            return
        if isinstance(found, _Pattern):
            known = self._number_values(found.number)
            fitting = found.routines(procs)
            exact = known is not None and all(v == int(v) and v >= 0 for v in known)
            if exact and all(found.text(int(v)).upper() in procs for v in known):  # type: ignore[union-attr]
                choices, covered = {int(v): found.text(int(v)) for v in sorted(known)}, True  # type: ignore[union-attr]
            elif fitting:
                choices, covered = fitting, False
            else:
                raise Untranslatable(f"{written}: no PROC of the backup is named {found.prefix}<number>{found.suffix},"
                                     f" and the values of {format_expr(found.number)} are not known", blocker)  # fmt: skip
            cases = tuple(n.TestCase((n.Number(span, v, str(v)),), (n.ProcCall(span, procs[text.upper()].name, args),))
                          for v, text in choices.items())  # fmt: skip
            self.stmt(n.Test(span, found.number, cases, None if covered else (n.Exit(span),)))  # type: ignore[attr-defined]
            self._late_warning(span, written, [procs[t.upper()].name for t in choices.values()], covered)
            return
        if isinstance(name, n.Name) and self.c.symbols.type_of(name.name) == "string":
            texts, covered = self._text_values(name)
            if not texts:
                raise Untranslatable(f"{written}: {name.name} is set to no name CrossArm can tell before the run (a"
                                     " constant, or a constant and NumToStr of a number)", blocker)  # fmt: skip
            missing = [t for t in texts if t.upper() not in procs]
            if missing:
                raise Untranslatable(f"{written}: {name.name} names {', '.join(missing)}, not a PROC of the backup", blocker)
            branches = tuple(n.IfBranch(n.BinaryOp(span, "=", name, n.String(span, t)),
                                        (n.ProcCall(span, procs[t.upper()].name, args),)) for t in texts)  # fmt: skip
            self.names_compared = True
            try:
                self.stmt(n.If(span, branches, () if covered else (n.Exit(span),)))  # type: ignore[attr-defined]
            finally:
                self.names_compared = False
            self._late_warning(span, written, [procs[t.upper()].name for t in texts], covered)
            return
        raise Untranslatable(f"{written}: the routine's name must be a constant text, a string variable or a text and"
                             " NumToStr of a number for CrossArm to tell the routines it can call", blocker)  # fmt: skip

    def _late_warning(self, span: Span, written: str, names: list[str], covered: bool) -> None:
        shown = ", ".join(names[:6]) + (", ..." if len(names) > 6 else "")
        message = f"{written}: called as each routine it can name ({shown})"
        if not covered:
            handled = any("ERR_REFUNKPRC" in h.raw.upper() for h in self.routine.handlers)  # type: ignore[attr-defined]
            message += ("; another name makes RAPID raise ERR_REFUNKPRC" + (" (its ERROR handler's path for it is not"
                        " converted)" if handled else "") + ": the program ends there (ABORT)")  # fmt: skip
        self.c.note(self.name, span.line, "WARNING", message, Blocker.rapid("LATE_BINDING"))  # type: ignore[attr-defined]

    def _constant_text(self, expr: n.Expr) -> str | None:
        if isinstance(expr, n.String):
            return expr.value
        if isinstance(expr, n.Name):
            decl = self.c.symbols.get(expr.name)
            if decl is not None and decl.storage == "CONST" and isinstance(decl.init, n.String):
                return decl.init.value
        return None

    def _assignments(self, name: str) -> tuple[list[n.Expr], bool]:
        """What the backup's routines assign to the data `name` (by name, any routine of the task), and whether
        something else may change it (a PERS, passed by reference, changed by a routine CrossArm does not read)."""
        values, other = [], False
        decl = self.c.symbols.get(name)
        if decl is None or decl.storage not in ("VAR", "CONST") or decl.dims:
            other = True
        for module in self.c.modules:
            for routine in module.routines:
                for stmt in walk_statements(routine.body):
                    if isinstance(stmt, n.Assign) and isinstance(stmt.target, n.Name) and stmt.target.name.upper() == name.upper():
                        values.append(stmt.value)
                    elif isinstance(stmt, n.ProcCall) and any(isinstance(a.value, n.Name) and a.value.name.upper()
                                                              == name.upper() for a in stmt.args):  # fmt: skip
                        other = True  # passed to a routine, which may change it
                    elif isinstance(stmt, n.For) and stmt.var.upper() == name.upper():
                        other = True
        return values, other

    def _number_values(self, expr: n.Expr) -> set[float] | None:
        """The values a num takes when they are known before the run: a FOR variable of constant bounds being
        run, data set to constants only; None otherwise."""
        if isinstance(expr, n.Number):
            return {float(expr.value)}
        if not isinstance(expr, n.Name):
            return None
        loop = next((s for s in self._enclosing_loops() if s.var.upper() == expr.name.upper()), None)
        if loop is not None:
            try:
                start, end = (self.c.evaluator.constant_number(e) for e in (loop.start, loop.end))
            except Exception:  # noqa: BLE001 - bounds known at run time only
                return None
            low, high = sorted((start, end))
            return {float(v) for v in range(int(low), int(high) + 1)} if low == int(low) and high == int(high) else None
        values, other = self._assignments(expr.name)
        decl = self.c.symbols.get(expr.name)
        if other or decl is None or self.c.parameters and expr.name.upper() in self.c.parameters:
            return None
        found = set()
        for value in [*values, *([decl.init] if decl.init is not None else [n.Number(decl.span, 0, "0")])]:
            try:
                found.add(float(self.c.evaluator.constant_number(value)))
            except Exception:  # noqa: BLE001 - not a constant
                return None
        return found

    def _enclosing_loops(self) -> list[n.For]:
        """The FOR loops the statement being translated is in (the ones whose variable is being run)."""
        return [s for s in walk_statements(self.routine.body) if isinstance(s, n.For)  # type: ignore[attr-defined]
                and s.var.upper() in self.loop_vars]  # type: ignore[attr-defined]

    def _text_values(self, name: n.Name) -> tuple[list[str], bool]:
        """The names a string variable can hold, deduced from what the backup sets it to; and whether they are all
        (False: other texts are possible, from a pattern or from code CrossArm does not follow)."""
        values, other = self._assignments(name.name)
        decl = self.c.symbols.get(name.name)
        if decl is not None and isinstance(decl.init, n.String) and decl.init.value:
            values = [decl.init, *values]
        texts: list[str] = []
        covered = not other
        for value in values:
            found = _pattern(value, self._constant_text)
            if isinstance(found, str):
                texts.append(found)
                continue
            if found is None:
                return [], False
            known = self._number_values(found.number)
            if known is not None and all(v == int(v) and v >= 0 and found.text(int(v)).upper() in self.c.procs
                                         for v in known):  # fmt: skip
                texts += [found.text(int(v)) for v in sorted(known)]
            else:
                texts += [found.text(v) for v in found.routines(self.c.procs)]
                covered = False
        unique = list(dict.fromkeys(texts))
        return unique, covered


__all__ = ["LateCalls", "parse_late_call"]
