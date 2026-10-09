# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Calls to routines with arguments: `CALL NAME(a,b,...)`, how each argument is passed (convert/arguments.py has
the AR[n] layout of a routine), what comes back after the CALL. The routine translator's part (mixed into it)."""

from typing import TYPE_CHECKING

from crossarm.convert.arguments import Signature
from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.external import (
    POINT_TYPES,
    RESULT,
    ProvidedRoutine,
    arguments_of,
    literal_kind,
    undeclared_layout,
)
from crossarm.convert.records import nodes
from crossarm.convert.tp_numbers import NUMBER_TYPES as _NUMBERS
from crossarm.convert.tp_numbers import ascii_text, decimal
from crossarm.convert.values import Unresolvable
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr

if TYPE_CHECKING:
    from crossarm.convert.translate import Converter

STRING_ARGUMENT_MAX = 38  # characters of a string CALL argument (ROBOGUIDE: 38 loads, 39 is refused)


class RoutineCalls:
    """The routine translator's part that writes calls with arguments (mixed into it)."""

    c: "Converter"

    def provided_call(self, call: n.ProcCall, provided: ProvidedRoutine) -> None:
        """A call to a routine the integrator provides (external_routines): `CALL PROGRAM(args)`, its arguments as
        a routine CrossArm converts is given them; what TP cannot pass leaves the call TODO, with why."""
        use = self.c.provided[call.name.upper()]
        try:
            self.call_with_args(call, self.provided_layout(call, provided), numbered=True)
        except Untranslatable as exc:
            use.todo[(self.name, call.span.line)] = str(exc)
            raise Untranslatable(f"{call.name}, provided as {provided.program} (external_routines): {exc}",
                                 exc.category) from exc  # fmt: skip

    def provided_layout(self, call: n.ProcCall | n.FuncCall, provided: ProvidedRoutine) -> Signature:
        """The AR[n] layout of a call to a provided program: from its declaration, else from the mapping file or
        this call (external.undeclared_layout); Untranslatable when its arguments cannot be passed."""
        use = self.c.provided[call.name.upper()]
        if use.problem:
            raise Untranslatable(use.problem, Blocker.CALL_ARGS)
        if use.layout is not None:
            return use.layout
        extra = 1 if use.returns is not None and isinstance(call, n.FuncCall) else 0
        found = undeclared_layout(call, provided, self.argument_kind, extra)
        if isinstance(found, str):
            raise Untranslatable(found, Blocker.CALL_ARGS)
        if use.arguments is None:
            use.arguments = arguments_of(found, False, use.returns if extra else None)
        return found

    def provided_result_call(self, a: n.Assign) -> n.FuncCall | None:
        """The call of `x := F(args)`, F a function the integrator provides that gives back a value a register
        holds, not written yet; None otherwise."""
        call = a.value
        if not (isinstance(call, n.FuncCall) and (key := call.name.upper()) in self.c.externals):
            return None
        if id(call) in self.provided_results or self.c.provided[key].returns is None:
            return None
        return call

    def provided_assign(self, a: n.Assign, call: n.FuncCall) -> None:
        """`x := F(args)`, F provided (external_routines) and returning a num, pos, pose or robtarget: `CALL PROG(args,k)`
        with k its result register of its own, R[k] (num) or PR[k], then the assignment written from that register
        (provided_operand, provided_point)."""
        use = self.c.provided[call.name.upper()]
        provided = self.c.externals[call.name.upper()]
        kind = use.returns
        key = f"{provided.program}.{RESULT}"
        try:
            layout = self.provided_layout(call, provided)
            if kind == "num":
                register = self.c.written_register(RESULT, key=key)
                number = register[2 : register.index(":")]
            else:
                register = self.c.point_register(key)
                number = register[3:-1]  # {PA:KEY}, numbered with the other position registers
            self.call_with_args(n.ProcCall(call.span, call.name, call.args), layout, numbered=True, result=number)
            self.provided_results[id(call)] = (register, kind)  # type: ignore[assignment]
            try:
                self.assign(a)  # type: ignore[attr-defined]
            finally:
                del self.provided_results[id(call)]
        except Untranslatable as exc:
            use.todo[(self.name, call.span.line)] = str(exc)  # type: ignore[attr-defined]
            raise Untranslatable(f"{call.name}, provided as {provided.program} (external_routines): {exc}",
                                 exc.category) from exc  # fmt: skip

    def provided_operand(self, expr: n.Expr) -> str | None:
        """R[k] for the value of a provided function just called (provided_assign), PR[k,i] for x, y, z of its
        point, pos or pose; None for anything else."""
        if not self.provided_results:
            return None
        if isinstance(expr, n.FuncCall) and id(expr) in self.provided_results:
            register, kind = self.provided_results[id(expr)]
            if kind != "num":
                raise Untranslatable(f"{format_expr(expr)} gives back a {kind}, not a number", Blocker.VALUE)
            return register
        if not isinstance(expr, n.Component) or (axis := {"X": 1, "Y": 2, "Z": 3}.get(expr.field.upper())) is None:
            return None
        base = expr.base  # F().x of a pos, F().trans.x of a point or pose
        if isinstance(base, n.Component) and base.field.upper() == "TRANS":
            base = base.base
        if isinstance(base, n.FuncCall) and id(base) in self.provided_results:
            register, kind = self.provided_results[id(base)]
            if kind != "num" and (kind == "pos") == (base is expr.base):
                return f"{register[:-1]},{axis}]"
        return None

    def provided_point(self, expr: n.Expr) -> str | None:
        """PR[k] of a provided function's point, pos or pose just called (provided_assign); None otherwise."""
        if self.provided_results and isinstance(expr, n.FuncCall) and id(expr) in self.provided_results:
            register, kind = self.provided_results[id(expr)]
            return register if kind != "num" else None
        return None

    def point_number(self, expr: n.Expr | None, slot, layout: Signature) -> str:
        """The number of the position register a point (robtarget, pos, pose) passed to a provided program is in:
        its own, kept in one, else copied into a register of CrossArm's own ('PROG.parameter')."""
        if expr is None:
            raise Untranslatable(f"argument {slot.name} is missing", Blocker.CALL_ARGS)
        source = self.kept_pose(expr) or self.point_source(expr)  # type: ignore[attr-defined]
        if source is None and isinstance(expr, n.Component) and expr.field.upper() in ("TFRAME", "UFRAME"):
            source = self.c.point_register(f"{self.c.program_names[layout.routine.upper()]}.{slot.name}")
            if not self.frame_read(expr, source):  # type: ignore[attr-defined]
                source = None
        if source is None:
            register = self.c.point_register(f"{self.c.program_names[layout.routine.upper()]}.{slot.name}")
            if not self.c.config.karel and self.pose_function(expr) is not None:  # type: ignore[attr-defined]
                raise Untranslatable(f"argument {slot.name}: {format_expr(expr)} is worked out by KAREL: convert with"
                                     " --karel", Blocker.RUNTIME_POSITION)  # fmt: skip
            if slot.kind == "robtarget":
                try:
                    target = self.c.evaluator.robtarget(expr)
                except Unresolvable:
                    target = None
                if target is not None:
                    self.emit(f"{register}={self.known_point(expr, target, expr.span.line)}")  # type: ignore[attr-defined]
                    return register[3:-1]
            if not (self.pose_written(expr, register) or self.pose_computed(expr, register, 1)):  # type: ignore[attr-defined]
                raise Untranslatable(f"argument {slot.name}: '{format_expr(expr)}' is neither known now nor kept in a"
                                     " position register", Blocker.RUNTIME_POSITION)  # fmt: skip
            source = register
        return source[3:-1]

    def argument_kind(self, expr: n.Expr) -> str | None:
        """num, bool or string for what a call passes, as far as it can be told: this routine's own parameter, data of
        the backup, a constant."""
        if isinstance(expr, n.Name) and self.args and (kind := self.args.kind(expr.name)) in ("num", "bool", "string"):
            return kind
        return literal_kind(expr, self.c.symbols.type_of)

    def provided_function(self, stmt: n.Stmt) -> str | None:
        """Why a statement using a function the integrator provides stays TODO; None when it uses none, or uses one
        as the whole right-hand side of an assignment, giving back a value a register holds (provided_assign)."""
        whole = stmt.value if isinstance(stmt, n.Assign) and isinstance(stmt.value, n.FuncCall) else None
        for node in nodes(stmt):
            if isinstance(node, n.FuncCall) and (provided := self.c.externals.get(node.name.upper())) is not None:
                use = self.c.provided[node.name.upper()]
                if node is whole and use.returns is not None:
                    use.function = True
                    continue
                if use.returns is not None:
                    why = (f"{node.name} is a function, provided as {provided.program} (external_routines): its value"
                           f" comes back to `x := {node.name}(...)` only, not inside an expression")  # fmt: skip
                elif use.module is None:
                    why = (f"{node.name} is a function, provided as {provided.program} (external_routines): a TP CALL"
                           " gives no value back to an expression; say what it returns in external_routines."
                           f"{provided.name}.returns (num, pos, pose, robtarget) to call it as `x := {node.name}(...)`")  # fmt: skip
                else:
                    why = (f"{node.name} is a function, provided as {provided.program} (external_routines): a TP CALL"
                           " gives no value back to an expression")  # fmt: skip
                use.function = True
                use.todo[(self.name, stmt.span.line)] = why
                return why
        return None

    def call_with_args(self, call: n.ProcCall, layout: Signature, numbered: bool = False, result: str = "") -> None:
        """CALL NAME(a,b,...): required arguments in order, then 1 / 0 for every optional switch. `numbered`: a
        provided program, given its points by the number of their position register; `result`: the number of the
        register a provided function writes its result in, its last argument."""
        positional = [a for a in call.args if a.name is None]
        required = list(layout.required)
        if len(positional) != len(required):
            raise Untranslatable(f"{len(positional)} arguments given, {call.name} takes {len(required)}", Blocker.CALL_ARGS)
        given = {a.name.upper(): a for a in call.args if a.name is not None}
        unknown = set(given) - {s.key for s in layout.slots if s.optional}
        if unknown:
            raise Untranslatable(f"{call.name} has no switch \\{min(unknown)}", Blocker.CALL_ARGS)
        if call.name.upper() in self.c.recursive and any(s.kind == "robtarget" for s in required):
            raise Untranslatable(f"{call.name} calls itself back and is given points: they travel in position"
                                 " registers every call under way shares", Blocker.CALL_ARGS)  # fmt: skip
        if call.name.upper() in self.c.recursive and any(s.fields for s in required if s.kind in ("speeddata", "zonedata")):
            raise Untranslatable(f"{call.name} calls itself back and is given speeds or zones: they are copied to"
                                 " registers every call under way shares", Blocker.CALL_ARGS)  # fmt: skip
        values, points, back = [], [], []
        name = self.c.program_names[call.name.upper()]
        returned = {s.key for s in layout.returned()}
        bound = {s.key: a.value for a, s in zip(positional, required, strict=True)}  # parameter -> what this call passes
        # The tool and work object this call gives the routine: a point passed with them is recorded in them.
        framed = [(s, a.value) for a, s in zip(positional, required, strict=True)]
        framed += [(s, given[s.key].value) for s in layout.slots if s.kind == "wobjdata" and s.key in given]
        frames = {("UT" if s.kind == "tooldata" else "UF"): value for s, value in framed
                  if s.kind in ("tooldata", "wobjdata") and isinstance(value, n.Name)
                  and not (self.args and self.args.frame(value.name))}  # fmt: skip
        for a, slot in zip(positional, required, strict=True):
            if numbered and slot.kind in POINT_TYPES:
                if slot.key in returned:
                    raise Untranslatable(f"argument {slot.name}: a {slot.kind} the program changes does not come back",
                                         Blocker.CALL_ARGS)  # fmt: skip
                values.append(self.point_number(a.value, slot, layout))
            elif slot.kind == "robtarget":
                points.append(self.point_argument(a.value, slot, layout, call.span.line, frames))
                if slot.by_reference and slot.key in layout.points_changed:  # VAR, INOUT: the point comes back
                    back.append(f"{self.point_back(a.value, slot)}={self.c.point_register(f'{layout.routine}.{slot.name}')}")
            elif slot.kind in ("tooldata", "wobjdata"):
                values.append(self.frame_argument(a.value, slot, points))
            elif slot.kind in ("speeddata", "zonedata"):
                if a.value is None:
                    raise Untranslatable(f"argument {slot.name} is missing", Blocker.CALL_ARGS)
                if slot.key in layout.fine_zones and not self.fine_zone(a.value):
                    raise Untranslatable(f"argument {slot.name}: {format_expr(a.value)}, where every other call passes"
                                         f" fine: {layout.routine} writes its moves through it FINE", Blocker.CALL_ARGS)  # fmt: skip
                values += [self.motion_argument(field, bound, layout.routine) for field in slot.fields]
            elif slot.kind == "record":
                if a.value is None:
                    raise Untranslatable(f"argument {slot.name} is missing", Blocker.CALL_ARGS)
                for field in slot.fields:
                    component = n.Component(a.value.span, a.value, field.name.split(".", 1)[1])
                    values.append(self.argument(component, field))
            else:
                values.append(self.argument(a.value, slot))
                if slot.key in returned:  # INOUT, VAR, PERS the routine changes: read back after the CALL
                    copy = self.c.written_register(slot.name, key=f"{name}.{slot.name}")
                    back.append(f"{self.returned_to(a.value, slot)}={copy}")
        for slot in layout.slots[len(required):]:
            arg = given.get(slot.key)
            if arg is None:
                values.append("0")  # a switch not given; a work object not given: wobj0, UFRAME 0
            elif slot.kind == "wobjdata":
                values.append(self.frame_argument(arg.value, slot, points))
            elif arg.conditional:  # \Check?Check: passed on only when this routine was given it
                forwarded = self.args.register(arg.value.name) if self.args and isinstance(arg.value, n.Name) else None
                if forwarded is None:
                    raise Untranslatable(f"\\{arg.name}?... does not name a switch of this routine", Blocker.CALL_ARGS)
                values.append(forwarded)
            else:
                values.append("1")
        if result:
            values.append(result)
        for text in filter(None, points):
            self.emit(text)
        self.emit(f"CALL {name}({','.join(values)})" if values else f"CALL {name}")
        for text in back:
            self.emit(text)

    def fine_zone(self, expr: n.Expr) -> bool:
        try:
            return self.c.evaluator.zone(expr).fine
        except Unresolvable as exc:
            raise Untranslatable(f"zone {format_expr(expr)}: {exc}", Blocker.CALL_ARGS) from exc

    def motion_argument(self, field, bound: dict[str, n.Expr | None], routine: str) -> str:
        """The number a speed or a corner of the called routine is passed as: the TCP speed in mm/s, the % of a
        joint move, or the CNT of the corner, worked out as the move would be written with what this call gives."""

        def passed(expr: n.Expr | None) -> n.Expr | None:  # the routine's own parameter: what this call passes
            return bound.get(expr.name.upper(), expr) if isinstance(expr, n.Name) else expr

        try:
            if field.kind != "cnt":
                return str(self.speed(bound[field.key.split(".")[0]], "J" if field.kind == "speed_joint" else "L")[2])
            corner = field.corner
            zone, speed = passed(corner.zone), passed(corner.speed)
            if self.c.evaluator.zone(zone).fine:
                if field.fine:
                    return "101"  # above any CNT: the routine writes this move FINE as well (IF R[m]>100,JMP)
                if zone is not corner.zone:
                    raise Untranslatable(f"argument {field.name.split('.')[0]}: fine, where {routine} moves through a "
                                         "zone given at run time: a TP move is FINE or CNT as written", Blocker.CALL_ARGS)  # fmt: skip
                return "0"  # a zone written in the routine, fine: the routine writes FINE
            _, rapid_speed, fanuc_speed = self.speed(speed, corner.motion)
            return self.termination(zone, speed, corner.motion, rapid_speed, fanuc_speed,
                                    passed(corner.following)).removeprefix("CNT")  # fmt: skip
        except Unresolvable as exc:
            raise Untranslatable(f"argument {field.name}: {exc}", Blocker.CALL_ARGS) from exc

    def frame_argument(self, expr: n.Expr | None, slot, before: list[str]) -> str:
        """The frame number a tooldata or wobjdata argument is passed as; this routine's own frame parameter as
        its AR[n]. A frame above what the controller holds is loaded into its slot first (`before`)."""
        kind = "UT" if slot.kind == "tooldata" else "UF"
        if isinstance(expr, n.Name) and self.args and (own := self.args.frame(expr.name)):
            return own
        number, bank = self.c.selection(kind, self.c.frame_number(kind, expr, self.name, expr.span.line if expr else 0))
        if bank is not None:
            before.append(f"{'UTOOL' if kind == 'UT' else 'UFRAME'}[{number}]=PR[{bank}]")
        return str(number)

    def returned_to(self, expr: n.Expr | None, slot) -> str:
        """The register a num passed by reference is read back into: the caller's data, or its own copy."""
        if isinstance(expr, n.Name):
            key = expr.name.upper()
            if key in self.copies:
                return self.copies[key]
            decl = self.c.symbols.get(expr.name)
            if key not in self.c.parameters and decl is not None and decl.type_name.lower() in _NUMBERS \
                    and decl.storage != "CONST" and not decl.dims:
                return self.c.written_register(expr.name)
        raise Untranslatable(f"argument {slot.name}: '{format_expr(expr) if expr else ''}' is passed by reference"
                             " and changed: it must be num data of the caller", Blocker.CALL_ARGS)  # fmt: skip

    def argument(self, expr: n.Expr | None, slot) -> str:
        """One TP CALL argument: a constant, a register, or this routine's own AR[n]."""
        if expr is None:
            raise Untranslatable(f"argument {slot.name} is missing", Blocker.CALL_ARGS)
        if isinstance(expr, n.Name) and expr.name.upper() in self.copies:  # a parameter it changes: its copy
            return self.copies[expr.name.upper()]
        if isinstance(expr, n.Name) and self.args and self.args.register(expr.name):
            return self.args.register(expr.name)  # type: ignore[return-value]
        if (field := self.component(expr)) is not None:  # a component of this routine's own record parameter
            return self.args.register(field)  # type: ignore[union-attr, return-value]
        if slot.kind == "string":
            return self.text_argument(expr, slot)
        if slot.kind == "bool":
            if isinstance(expr, n.Bool):
                return "1" if expr.value else "0"
            decl = self.c.symbols.get(expr.name) if isinstance(expr, n.Name) else None
            if decl is not None and decl.storage == "CONST" and isinstance(decl.init, n.Bool):
                return "1" if decl.init.value else "0"
            if isinstance(expr, n.Component):  # a record's bool no program changes: pdHousing.chamfer
                try:
                    found = self.c.computer.value(expr).value
                except Unresolvable:
                    found = None
                if isinstance(found, bool):
                    return "1" if found else "0"
            raise Untranslatable(f"argument {slot.name}: '{format_expr(expr)}' must be TRUE, FALSE or a bool "
                                 "argument (a flag cannot be passed)", Blocker.CALL_ARGS)  # fmt: skip
        try:
            text = self.single(expr)
        except Untranslatable as exc:
            raise Untranslatable(f"argument {slot.name}: {exc}", Blocker.CALL_ARGS) from exc
        return decimal(text)  # CALL P(.5), not CALL P(0.5)

    def point_argument(self, expr: n.Expr | None, slot, layout: Signature, line: int,
                       frames: dict[str, n.Expr] | None = None) -> str:  # fmt: skip
        """`PR[k]=P[j]` for a robtarget argument: the point worked out here, recorded with the frames the routine
        moves to it with; `PR[k]=PR[m]` for a point this routine was given itself."""
        if expr is None:
            raise Untranslatable(f"argument {slot.name} is missing", Blocker.CALL_ARGS)
        register = self.c.point_register(f"{layout.routine}.{slot.name}")
        if self.passed_point(expr, "CROSSARM.POINT", into=register):  # a parameter, an array element, Offs() of one
            return ""
        try:
            value = self.c.evaluator.robtarget(expr)
        except Unresolvable as exc:
            raise Untranslatable(f"argument {slot.name}: '{format_expr(expr)}' is only known at run time ({exc})",
                                 Blocker.RUNTIME_POSITION) from exc  # fmt: skip
        tool, wobj = self.c.point_frames(layout.routine, slot.name)
        if tool is None and frames:  # moved to with the frames the routine is given: those of this call
            tool, wobj = frames.get("UT"), wobj or frames.get("UF")
        if tool is None and self.active_uf is not None and self.active_ut is not None:
            uf, ut = self.active_uf, self.active_ut  # no routine moves to it: recorded in the frames selected here
        else:
            uf = self.c.selection("UF", self.c.frame_number("UF", wobj, self.name, line))
            ut = self.c.selection("UT", self.c.frame_number("UT", tool or n.Name(expr.span, "tool0"), self.name, line))
        return f"{register}={self.point(expr, value, uf, ut, line)}"

    def point_back(self, expr: n.Expr | None, slot) -> str:
        """The position register a point passed by reference is read back into, after the CALL: the caller's own,
        a point it keeps in a register (a VAR robtarget, or a point parameter of its own it changes)."""
        if isinstance(expr, n.Name) and (key := self.runtime_key(expr.name)) is not None:
            return self.c.point_register(key)
        raise Untranslatable(f"argument {slot.name}: '{format_expr(expr) if expr else ''}' is changed by the routine:"
                             " it must be a robtarget of the program (VAR)", Blocker.RUNTIME_POSITION)  # fmt: skip

    def text_argument(self, expr: n.Expr, slot) -> str:
        """A string argument: text written in the call ('...'), as TP takes it. An apostrophe ends the text
        on FANUC (ROBOGUIDE refuses l''a): it becomes a backquote. Past 38 characters it is cut, with a warning."""
        text, dropped = self.split_text(expr)
        if dropped:  # a text worked out at run time: passed in a string register, which the CALL copies
            return self.text_source(expr, tuple(k for k in (1, 2) if k not in self.text_slots))
        text = ascii_text(text).replace("'", "`")
        if len(text) > STRING_ARGUMENT_MAX:
            self.c.note(self.name, expr.span.line, "WARNING", f"argument {slot.name} cut to {STRING_ARGUMENT_MAX}"
                        f" characters (the most a TP string argument takes): '{text}'", Blocker.MESSAGE_CUT)  # fmt: skip
            text = text[:STRING_ARGUMENT_MAX].rstrip()
        return f"'{text}'"
