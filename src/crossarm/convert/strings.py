# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Data of type string, kept in the string registers of the FANUC (SR[n]).

    VAR string sState;              sState:="IDLE";        ->  CALL CA_TEXT(1,'IDLE',0)
                                    IF sState="RUN" THEN   ->  CALL CA_TEXT(25,'RUN',0)
                                                               IF SR[1:sState]<>SR[25:Text],JMP LBL[2]

A string the programs change is a string register of its own, named like the data; one they never change
is its value, written where it is read, as a CONST is. Measured on ROBOGUIDE (string probe):

- 25 string registers (SR[26] does not exist), 254 characters each.
- A TP line can neither write a text in a string register (`SR[1]='IDLE'` is refused) nor compare one with
  a text (`IF SR[1]='A',JMP`): a text is loaded by a program given it as an argument, `SR[AR[1]]=AR[2]`, 38
  characters per argument; a longer one in pieces, each added at the end (`SR[AR[1]]=SR[AR[1]]+AR[2]`).
  An apostrophe ends the argument: it becomes a backquote. `"`, `,`, `(` and `;` pass. An empty argument
  works but is stored `'...'`: an empty text is one character, then `SUBSTR SR[n],2,0` (none from past it;
  `SUBSTR SR[n],1,0` stops the program, INTP-323). A text compared or passed on is loaded into a scratch
  register just before, and never kept from one instruction to the next.
- `IF SR[a]=SR[b],JMP LBL[n]` and `<>`, without parentheses: `IF (SR[a]=SR[b])` and a block IF are refused.
- TP compares texts regardless of case ('A' = 'a', FINDSTR too) but not of spaces ('A' <> 'A '); RAPID
  compares them as they are. A comparison is converted only when no text one side can hold differs from
  one of the other side by case alone: alphabet() lists the characters a string can hold.
- STRLEN is StrLen. SUBSTR is StrPart (from 1; past the end the program stops, INTP-323 Value overflow, as
  RAPID stops with an error).
  FINDSTR is StrMatch from the first character: 0 when not found, where RAPID gives StrLen+1 (also for an
  empty pattern).
- `SR[n]=R[m]` writes a whole number held as one as its digits ('13'), one held as a real with six decimals
  ('3.000000' for 2.5+.5 or 6/2): NumToStr(n,0) and ValToStr(n) are converted for a number the programs only
  ever give whole numbers (integral()).
- `CALL X(SR[n])` passes a copy of the text: a scratch register can carry a text worked out for the call.
"""

from collections.abc import Callable, Iterable
from typing import Any

from crossarm.convert.compute import Written, parse_params, path_of
from crossarm.convert.values import Symbols, Unresolvable
from crossarm.rapid import nodes as n
from crossarm.rapid.walk import walk_statements

# Functions giving a whole number: a length, a position, the value of an input or output signal.
_WHOLE_FUNCTIONS = frozenset({"STRLEN", "STRMATCH", "GINPUT", "GOUTPUT", "DINPUT", "DOUTPUT"})
TEXT_PIECE = 38  # characters of a text argument (ROBOGUIDE: 39 is refused)
TEXT_LENGTH = 254  # characters a string register holds
DIGITS = frozenset("0123456789-")  # what NumToStr(n,0) of a whole number writes
NUMBER_TEXT = frozenset("0123456789-.E+")  # what NumToStr / ValToStr of a num can write

# Instructions that change a num they are given by a whole number: still one afterwards.
_COUNTS = frozenset({"INCR", "DECR", "CLEAR"})


def cased(text: Iterable[str]) -> bool:
    """Whether a text has a letter that has another case: one TP compares regardless of case."""
    return any(c.lower() != c.upper() for c in text)


def same_regardless_of_case(left: frozenset[str] | None, right: frozenset[str] | None) -> bool:
    """Whether TP can find equal two texts RAPID finds different: one character of one side and one of the
    other differ by case alone. None: the side can hold any text."""
    if left is None or right is None:
        known = right if left is None else left
        return known is None or cased(known)
    return any(a != b and a.lower() == b.lower() for a in left for b in right)


class Strings:
    def __init__(self, modules: list[n.Module], symbols: Symbols, written: Written, value: Callable[[n.Expr], Any],
                 own: Written | None = None) -> None:  # fmt: skip
        """`written`: what the programs of every task change, `own`: of this task, when other tasks are
        converted too. `value(expr)`: the fixed value of an expression, or Unresolvable."""
        self.modules = modules
        self.symbols = symbols
        self.shared = written
        self.own = own or written
        self.value = value
        self.routines = {r.name.upper(): (m, r) for m in modules for r in m.routines}
        self._alphabets: dict[str, frozenset[str] | None] | None = None
        self._integral: dict[str, bool] | None = None
        self._for_starts: dict[tuple[str, str], list[n.Expr]] = {}  # (ROUTINE, COUNTER) -> where its FORs start

    # -- which data the programs change ----------------------------------------------------------

    def key(self, name: str, routine: str | None) -> str:
        """The data a name means: `ROUTINE.NAME` for a routine's own, `NAME` for module data."""
        if routine is not None and name.upper() in self._locals(routine):
            return f"{routine.upper()}.{name.upper()}"
        return name.upper()

    def _locals(self, routine: str) -> dict[str, n.DataDecl]:
        found = self.routines.get(routine.upper())
        return {} if found is None else {s.name.upper(): s for s in found[1].body if isinstance(s, n.DataDecl)}

    def changed(self, decl: n.DataDecl, routine: str | None = None) -> str | None:
        """Where a program changes this string; None when none does. `routine`: the one declaring it."""
        if decl.storage == "CONST":
            return None
        writes = self._writes(decl.name, routine, self.shared if decl.storage == "PERS" and decl.scope is None
                              and routine is None else self.own)  # fmt: skip
        return writes[0] if writes else None

    def _writes(self, name: str, routine: str | None, written: Written) -> list[str]:
        """The places writing this data: in its routine for a routine's own, else where no data of the routine
        has that name."""
        if written.everything:
            return [written.everything]
        if "string" in written.types:
            return [written.types["string"]]
        out = []
        for _path, where in written.places.get(name.upper(), ()):
            place = where.rpartition(" l.")[0]
            owner = place.rpartition(".")[2]
            if routine is not None:
                if owner.upper() == routine.upper():
                    out.append(where)
            elif name.upper() not in self._locals(owner):
                out.append(where)
        return out

    # -- the characters a string can hold ----------------------------------------------------------

    def alphabet(self, expr: n.Expr, routine: str | None, params: Iterable[str] = ()) -> frozenset[str] | None:
        """The characters the text of `expr` can hold, in `routine`; None: any. `params`: the routine's
        parameters (upper case), whose text comes from the caller."""
        if self._alphabets is None:
            self._alphabets = self._all_alphabets()
        return self._expr_alphabet(expr, routine, frozenset(p.upper() for p in params), self._alphabets)

    def _assignments(self) -> tuple[dict[str, list[tuple[n.Expr, str | None, frozenset[str]]]], set[str]]:
        """Each string data's assignments (value, routine, its parameters), and the data written otherwise."""
        values: dict[str, list[tuple[n.Expr, str | None, frozenset[str]]]] = {}
        other: set[str] = set()
        for module in self.modules:
            for routine in module.routines:
                params = frozenset(p.name for g in parse_params(routine.params) or [] for p in g)
                for stmt in walk_statements(routine.body):
                    if isinstance(stmt, n.Assign) and isinstance(stmt.target, n.Name):
                        key = self.key(stmt.target.name, routine.name)
                        values.setdefault(key, []).append((stmt.value, routine.name, params))
                    elif isinstance(stmt, n.Assign) and (path := path_of(stmt.target)):
                        other.add(self.key(path[0], routine.name))
        for written in (self.shared, self.own):  # passed to a routine changing it, CrossArm not reading...
            for name, places in written.places.items():
                for _path, where in places:
                    owner = where.rpartition(" l.")[0].rpartition(".")[2]
                    if not self._assigned_at(name, owner, where):
                        other.add(self.key(name, owner))
        return values, other

    def _assigned_at(self, name: str, routine: str, where: str) -> bool:
        found = self.routines.get(routine.upper())
        line = int(where.rpartition(" l.")[2]) if where.rpartition(" l.")[2].isdigit() else -1
        if found is None:
            return False
        return any(isinstance(s, n.Assign) and s.span.line == line and path_of(s.target) == (name.upper(),)
                   for s in walk_statements(found[1].body))  # fmt: skip

    def _all_alphabets(self) -> dict[str, frozenset[str] | None]:
        """Every string data's alphabet, from its initial value and the values assigned to it: worked out
        until nothing changes (a string set from another, or from itself, `s:=s+"x"`)."""
        values, other = self._assignments()
        decls: dict[str, tuple[n.DataDecl, str | None]] = {}
        for module in self.modules:
            for decl in module.declarations:
                if decl.type_name.lower() == "string" and not decl.dims:
                    decls[decl.name.upper()] = (decl, None)
            for routine in module.routines:
                for stmt in routine.body:
                    if isinstance(stmt, n.DataDecl) and stmt.type_name.lower() == "string" and not stmt.dims:
                        decls[f"{routine.name.upper()}.{stmt.name.upper()}"] = (stmt, routine.name)
        table: dict[str, frozenset[str] | None] = {}
        for key, (decl, _routine) in decls.items():
            if key in other:
                table[key] = None
            elif decl.init is None:
                table[key] = frozenset()
            elif isinstance(decl.init, n.String):
                table[key] = frozenset(decl.init.value)
            else:
                table[key] = None
        while True:
            changed = False
            for key, assigned in values.items():
                if key not in table or table[key] is None:
                    continue
                found: frozenset[str] | None = table[key]
                for value, routine, params in assigned:
                    more = self._expr_alphabet(value, routine, params, table)
                    found = None if more is None or found is None else found | more
                    if found is None:
                        break
                if found != table[key]:
                    table[key], changed = found, True
            if not changed:
                return table

    def _expr_alphabet(self, expr: n.Expr, routine: str | None, params: frozenset[str],
                       table: dict[str, frozenset[str] | None]) -> frozenset[str] | None:  # fmt: skip
        match expr:
            case n.String(value=value):
                return frozenset(value)
            case n.BinaryOp(op="+", left=left, right=right):
                a = self._expr_alphabet(left, routine, params, table)
                b = self._expr_alphabet(right, routine, params, table)
                return None if a is None or b is None else a | b
            case n.Name(name=name):
                if name.upper() in params:
                    return None
                key = self.key(name, routine)
                if key in table:
                    return table[key]
                try:
                    found = self.value(expr)
                except Unresolvable:
                    return None
                return frozenset(found) if isinstance(found, str) else None
            case n.FuncCall(name=fn, args=args) if fn.upper() == "STRPART" and args and args[0].value is not None:
                return self._expr_alphabet(args[0].value, routine, params, table)
            case n.FuncCall(name=fn) if fn.upper() in ("NUMTOSTR", "VALTOSTR"):
                return NUMBER_TEXT
            case n.Component():
                try:
                    found = self.value(expr)
                except Unresolvable:
                    return None
                return frozenset(found) if isinstance(found, str) else None
        return None

    # -- numbers only ever given whole numbers ----------------------------------------------------------

    def integral(self, expr: n.Expr, routine: str | None) -> bool:
        """Whether `expr` is always a whole number, held as one by TP: what `SR[n]=R[m]` writes as RAPID's
        NumToStr(n,0) does. A constant, a num the programs only give whole numbers (+, -, *, DIV, MOD of
        whole numbers, Incr, Decr, a FOR counter from one), StrLen, StrMatch, a group signal."""
        if self._integral is None:
            self._integral = self._all_integral()
        return self._expr_integral(expr, routine, self._integral)

    def _all_integral(self) -> dict[str, bool]:
        """Every num data: whether all its values are whole numbers. Taken as so, then let go of where a value
        is not one, until nothing changes."""
        values: dict[str, list[tuple[n.Expr | None, str | None]]] = {}
        other: set[str] = set()
        for module in self.modules:
            for routine in module.routines:
                for stmt in walk_statements(routine.body):
                    if isinstance(stmt, n.Assign) and isinstance(stmt.target, n.Name):
                        values.setdefault(self.key(stmt.target.name, routine.name), []).append((stmt.value, routine.name))
                    elif isinstance(stmt, n.ProcCall) and stmt.name.upper() in (*_COUNTS, "ADD"):
                        positional = [a.value for a in stmt.args if a.name is None]
                        if positional and isinstance(positional[0], n.Name):
                            step = positional[-1] if stmt.name.upper() == "ADD" and len(positional) > 1 else None
                            values.setdefault(self.key(positional[0].name, routine.name), []).append((step, routine.name))
                    elif isinstance(stmt, n.For):
                        self._for_starts.setdefault((routine.name.upper(), stmt.var.upper()), []).append(stmt.start)
        for written in (self.shared, self.own):
            for name, places in written.places.items():
                for _path, where in places:
                    owner = where.rpartition(" l.")[0].rpartition(".")[2]
                    if not self._assigned_at(name, owner, where) and not self._counted_at(name, owner, where):
                        other.add(self.key(name, owner))
        table: dict[str, bool] = {}
        for module in self.modules:
            for decl in module.declarations:
                if decl.type_name.lower() == "num" and not decl.dims:
                    table[decl.name.upper()] = self._initial_integral(decl)
            for routine in module.routines:
                for stmt in routine.body:
                    if isinstance(stmt, n.DataDecl) and stmt.type_name.lower() == "num" and not stmt.dims:
                        table[f"{routine.name.upper()}.{stmt.name.upper()}"] = self._initial_integral(stmt)
        for key in other:
            table[key] = False
        while True:
            changed = False
            for key, assigned in values.items():
                if not table.get(key):
                    continue
                if not all(v is None or self._expr_integral(v, r, table) for v, r in assigned):
                    table[key], changed = False, True
            if not changed:
                return table

    def _counted_at(self, name: str, routine: str, where: str) -> bool:
        """Incr / Decr / Clear / Add of the data at that place, or a FOR on it: followed by _all_integral."""
        found = self.routines.get(routine.upper())
        line = where.rpartition(" l.")[2]
        if found is None or not line.isdigit():
            return False
        for stmt in walk_statements(found[1].body):
            if stmt.span.line != int(line):
                continue
            if isinstance(stmt, n.ProcCall) and stmt.name.upper() in (*_COUNTS, "ADD"):
                first = next((a.value for a in stmt.args if a.name is None), None)
                if isinstance(first, n.Name) and first.name.upper() == name.upper():
                    return True
        return False

    def _initial_integral(self, decl: n.DataDecl) -> bool:
        if decl.init is None:
            return True  # RAPID starts a num at 0
        try:
            value = self.value(decl.init)
        except Unresolvable:
            return False
        return isinstance(value, int | float) and not isinstance(value, bool) and float(value).is_integer()

    def _expr_integral(self, expr: n.Expr, routine: str | None, table: dict[str, bool]) -> bool:
        match expr:
            case n.Number(value=value):
                return float(value).is_integer()
            case n.UnaryOp(op="-", operand=operand):
                return self._expr_integral(operand, routine, table)
            case n.BinaryOp(op="DIV" | "MOD"):
                return True
            case n.BinaryOp(op="+" | "-" | "*", left=left, right=right):
                return self._expr_integral(left, routine, table) and self._expr_integral(right, routine, table)
            case n.FuncCall(name=fn) if fn.upper() in _WHOLE_FUNCTIONS:
                return True
            case n.Name(name=name):
                key = self.key(name, routine)
                # A FOR counter counts by 1 from where it starts; the name may also be module data's, outside the
                # loop: both must be whole numbers.
                starts = self._for_starts.get(((routine or "").upper(), name.upper()), [])
                if not all(self._expr_integral(s, routine, table) for s in starts):
                    return False
                if key in table:
                    return table[key]
                if starts:
                    return True
                try:
                    value = self.value(expr)
                except Unresolvable:
                    return False
                return isinstance(value, int | float) and not isinstance(value, bool) and float(value).is_integer()
        return False


__all__ = ["DIGITS", "NUMBER_TEXT", "TEXT_LENGTH", "TEXT_PIECE", "Strings", "cased", "same_regardless_of_case"]
