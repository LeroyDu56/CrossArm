# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A FUNC of the backup whose value is only known at run time, written as a TP program that writes its result in a
register the caller names (a mixin of the routine translator, and the converter's part).

A FUNC is worked out at conversion time when its inputs are known (crossarm.convert.compute), copied into its calls
when its body is one expression (crossarm.convert.inline) or composes a frame (crossarm.convert.func_inline). The
others gave a TODO at each call. A FUNC returning a num, a bool or a robtarget is now a program of its own:

    FUNC robtarget GetCell(num row, num col)       CALL GETCELL(R[3:row],R[4:col],{PA:GETCELL.result})
        VAR robtarget p;                           PR[{PA:pCell}]=PR[{PA:GETCELL.result}]
        p := pStart;
        p.trans.x := pStart.trans.x + col * 50;    GETCELL.LS: ... PR[AR[3]]=PR[k]
        RETURN p;
    ENDFUNC
    ...
    pCell := GetCell(row, col);

Its parameters are passed as any routine's (crossarm.convert.arguments), and one argument more, last: the number of
the register its result goes in, R[AR[n]] for a num or a bool (1 TRUE, 0 FALSE), PR[AR[n]] for a robtarget, as
measured for the programs an integrator provides (tools/make_func_result_probe.py) and for the converted FUNCs
themselves (tools/make_func_body_probe.py). Each RETURN writes it, then ENDs the program (back to the caller). The
caller makes the CALL just before the line that reads the value: an assignment, a condition (IF, ELSEIF, a WHILE
turn: before each test), a move to its point, an argument; with a register of its own per call of one line.

Written only for the FUNCs some converted line does call this way, after the programs, with their own body
converted like any routine's (its TODO are its own). Not for a FUNC using files or sockets (the call says why),
nor one whose parameters TP cannot pass. A FUNC read in a wait (WaitUntil), whose condition the controller reads
again and again, stays TODO: the CALL cannot be made before each reading.
"""

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from crossarm.convert.arguments import MAX_ARGS, Signature, signature
from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.compute import Unknown
from crossarm.convert.external import RESULT
from crossarm.convert.runtime_points import expr_nodes
from crossarm.convert.values import Unresolvable
from crossarm.rapid import nodes as n

if TYPE_CHECKING:
    from crossarm.convert.translate import Converter

# What a FUNC returns -> where its result is kept: a number register (num, bool as 1/0) or a position register.
RETURNS = {"num": "num", "dnum": "num", "bool": "bool", "robtarget": "robtarget"}


def func_layouts(modules: Iterable[n.Module], records: Mapping[str, tuple[tuple[str, str], ...]],
                 externals: Mapping[str, object], inside, recursive: set[str]) -> tuple[dict[str, tuple[Signature, str]], dict[str, str]]:  # fmt: skip
    """(upper-case name -> (AR[n] layout, what it returns) of each FUNC that can be written as a program: returning a
    num, a bool or a robtarget, its parameters passed as TP arguments with one left for the result register, not
    provided by the integrator, using no file or socket (`inside`: RoutineUse.inside); upper-case name -> why not,
    for the other FUNCs whose return type or parameters stop it)."""
    found: dict[str, tuple[Signature, str]] = {}
    why: dict[str, str] = {}
    for module in modules:
        for routine in module.routines:
            key = routine.name.upper()
            if routine.kind != "FUNC" or key in externals or inside(key) is not None:
                continue
            kind = RETURNS.get((routine.return_type or "").lower())
            if kind is None:
                why[key] = (f"it returns a {routine.return_type}: a FUNC is written as a program when it returns a num,"
                            " a bool or a robtarget")  # fmt: skip
                continue
            if key in recursive:
                why[key] = ("it calls itself back: its result register and its data would be shared by every call under"
                            " way")  # fmt: skip
                continue
            layout = signature(routine, dict(records)) if routine.params.strip() else Signature((), routine=routine.name)
            if isinstance(layout, str):
                why[key] = layout
            elif len(layout.arguments) >= MAX_ARGS:
                why[key] = f"{len(layout.arguments)} arguments and its result register: a TP CALL takes {MAX_ARGS}"
            else:
                found[key] = (layout, kind)
    return found, why


def func_call_sites(conv: "Converter") -> None:
    """ConversionResult.func_calls: the lines calling each FUNC written as a program, those left TODO not
    counted."""
    todo = {(note.program, note.rapid_line) for note in conv.result.notes if note.kind == "TODO"}
    names = {r.name.upper(): r.name for m in conv.modules for r in m.routines}
    for key, program, line in conv.func_called:
        if (program, line) in todo:
            continue
        sites = conv.result.func_calls.setdefault(names.get(key, key), [])
        if (program, line) not in sites:
            sites.append((program, line))


def called_programs(conv: "Converter", programs) -> set[str]:
    """The FUNCs (upper case) some of these programs CALL as programs of their own."""
    names = {conv.program_names[key]: key for key in conv.func_named}
    called: set[str] = set()
    for info in programs:
        for line in info.program.lines:
            text = getattr(line, "text", "")
            if text.startswith("CALL "):
                name = text[5:].split("(", 1)[0].strip()
                if name in names:
                    called.add(names[name])
    return called


class FuncPrograms:
    """The routine translator's part that calls a FUNC written as a program, and writes its RETURN (mixed into it)."""

    c: "Converter"

    def func_reset(self) -> None:
        """A new statement: the results of the FUNCs the one before called are not read again."""
        for node in self.func_nodes:
            self.provided_results.pop(id(node), None)  # type: ignore[attr-defined]
        self.func_nodes: list[n.FuncCall] = []

    def func_first(self, expr: n.Expr) -> None:
        """Call first the FUNCs an expression reads as programs (in the order RAPID reads them), so that no scratch
        register worked out for it is overwritten by a FUNC's own calculation."""
        if not self.c.func_layouts or self.stepless:  # type: ignore[attr-defined]
            return
        for node in expr_nodes(expr):
            if not (isinstance(node, n.FuncCall) and node.name.upper() in self.c.func_layouts):
                continue
            if id(node) in self.provided_results:  # type: ignore[attr-defined]
                continue
            try:
                self.c.computer.value(node)
                continue  # worked out at conversion time
            except Unresolvable:
                pass
            if self.c.func_trouble(node.name.upper()) is None:  # else left to the line, which says why
                self.func_result(node)

    def func_result(self, expr: n.Expr) -> tuple[str, str] | None:
        """(register, kind) of a FUNC of the backup called as a program: `CALL F(args,k)` written just before the
        line, k its result register, R[k] or PR[k]; None when the expression is no such call."""
        if not isinstance(expr, n.FuncCall) or (entry := self.c.func_layouts.get(expr.name.upper())) is None:
            return None
        if id(expr) in self.provided_results:  # type: ignore[attr-defined]
            return self.provided_results[id(expr)]  # type: ignore[attr-defined]
        if self.stepless:  # type: ignore[attr-defined]
            raise Untranslatable(f"{expr.name}() is a FUNC written as a program: it is called before the line reading"
                                 " its value, not in a wait the controller reads again and again", Blocker.CONDITION)  # fmt: skip
        if (trouble := self.c.func_trouble(expr.name.upper())) is not None:
            raise Untranslatable(f"{expr.name}() is written as a program only when its whole body converts, and"
                                 f" {trouble[0]}", trouble[1])  # fmt: skip
        layout, kind = entry
        name = self.c.func_program(expr.name.upper())
        self.c.func_called.append((expr.name.upper(), self.name, expr.span.line))  # type: ignore[attr-defined]
        same = sum(1 for node in self.func_nodes if node.name.upper() == expr.name.upper())
        # a register per caller: a FUNC another FUNC calls never writes over the result its own caller reads next
        key = f"{self.name}.{name}.{RESULT}{same + 1 if same else ''}"  # type: ignore[attr-defined]
        if kind == "robtarget":
            register = self.c.point_register(key)
            number = register[3:-1]  # {PA:KEY}, numbered with the other position registers
        else:
            register = self.c.written_register(RESULT, key=key)
            number = register[2 : register.index(":")]
        call = n.ProcCall(expr.span, expr.name, expr.args)
        self.call_with_args(call, layout, result=number)  # type: ignore[attr-defined]
        self.provided_results[id(expr)] = (register, kind)  # type: ignore[attr-defined]
        self.func_nodes.append(expr)  # kept alive: its id stays its own while the statement is written
        self.forget((call,), Unknown(f"may be changed by {expr.name}() at l.{expr.span.line}"))  # type: ignore[attr-defined]
        return register, kind

    def func_excluded(self, expr: n.Expr) -> None:
        """Untranslatable, saying why, for a FUNC of the backup not written as a program (func_layouts)."""
        if isinstance(expr, n.FuncCall) and (why := self.c.func_why.get(expr.name.upper())) is not None:
            raise Untranslatable(f"{expr.name}() is not written as a program: {why}", Blocker.CALL_ARGS)

    def func_number(self, expr: n.Expr) -> str | None:
        """R[k] of a FUNC returning a number called as a program; None when the expression is no such call."""
        found = self.func_result(expr)
        if found is None:
            self.func_excluded(expr)
            return None
        if found[1] != "num":
            raise Untranslatable(f"{expr.name}() gives back a {found[1]}, not a number", Blocker.VALUE)  # type: ignore[attr-defined]
        return found[0]

    def func_point(self, expr: n.Expr) -> str | None:
        """PR[k] of a FUNC returning a robtarget called as a program, when its value is not known now."""
        if not (isinstance(expr, n.FuncCall) and self.c.func_layouts.get(expr.name.upper(), (None, ""))[1] == "robtarget"):
            return None
        try:
            self.c.evaluator.robtarget(expr)
            return None  # worked out at conversion time: a P[n] of the program
        except Unresolvable:
            pass
        found = self.func_result(expr)
        return found[0] if found is not None else None

    def func_return(self, stmt: n.Return) -> None:
        """RETURN of a FUNC written as a program: its value in the register the caller passed the number of, last
        argument, then END (back to the caller) unless it is the last statement."""
        layout, kind = self.c.func_layouts[self.routine.name.upper()]  # type: ignore[attr-defined]
        ar = f"AR[{len(layout.arguments) + 1}]"
        value = stmt.value
        assert value is not None
        if kind == "num":
            self.emit(f"R[{ar}]={self.arithmetic(value)}")  # type: ignore[attr-defined]
        elif kind == "bool":
            source = self.fold_texts(self.simplify(value))  # type: ignore[attr-defined]
            if isinstance(source, n.Bool):
                self.emit(f"R[{ar}]={1 if source.value else 0}")  # type: ignore[attr-defined]
            elif self.has_text(source):  # type: ignore[attr-defined]
                raise Untranslatable("RETURN of a comparison of texts: TP compares texts in a jump only", Blocker.CONDITION)
            else:
                test = self.condition(source)  # type: ignore[attr-defined]
                for text in (f"IF ({test}) THEN", f"R[{ar}]=1", "ELSE", f"R[{ar}]=0", "ENDIF"):
                    self.emit(text)  # type: ignore[attr-defined]
        else:
            self._runtime_value(n.Assign(stmt.span, n.Name(stmt.span, RESULT), value), f"PR[{ar}]", RESULT,  # type: ignore[attr-defined]
                                f"{RESULT}#ROT")  # fmt: skip
        last = next((s for s in reversed(self.routine.body) if not isinstance(s, n.Comment)), None)  # type: ignore[attr-defined]
        if stmt is not last:
            for text in self.epilogue:  # type: ignore[attr-defined]
                self.emit(text)  # type: ignore[attr-defined]
            self.emit("END")  # type: ignore[attr-defined]
