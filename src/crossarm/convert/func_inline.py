# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A FUNC of the backup that composes a tool, a work object or a pose, copied into each call (a mixin of the
routine translator).

An initialisation routine often builds its tools from a few base tools, through a FUNC of the backup:

    FUNC tooldata MakeTool(tooldata tBase, tooldata tOffset)
        VAR tooldata tRes;
        tRes := tOffset;
        tRes.tframe := PoseMult(tBase.tframe, tOffset.tframe);
        tRes.tload.mass := tBase.tload.mass + tOffset.tload.mass;
        RETURN tRes;
    ENDFUNC
    ...
    tFinger := MakeTool(tGripBase, tOfsFinger);

When every input is known at conversion time, the FUNC is worked out then (crossarm.convert.compute). When the
base tool is calibrated at run time, it is not: the body is then copied into the call ("inlined"), its result
replaced by the call's target and its parameters by the call's arguments:

    tFinger := tOfsFinger;                                         known now: nothing written yet
    tFinger.tframe := PoseMult(tGripBase.tframe, tOfsFinger.tframe);  PR[k]=UTOOL[base] ... CALL CA_POSEMULT
                                                                   (--karel), UTOOL[n]=PR[F]
    tFinger.tload.mass := tGripBase.tload.mass + tOfsFinger.tload.mass;   known now: the payload said

Each statement is then converted as if the routine held it (crossarm.convert.frame_writes: a frame copied or
written part by part in TP; crossarm.convert.karel_poses: pose functions by KAREL); the fields with no frame
(tload, ufprog, ufmec) follow crossarm.convert.frame_fields. A whole tool or work object copied from one the
programs change is its fields known now plus its frame read back where the robot keeps it.

Only a body made of assignments (of the result, of its fields, of other local data), values of pose functions
(PoseMult, PoseInv, RelTool, DefFrame, Offs...), constants and its parameters, and one RETURN at the end is
copied: anything else (a loop, an IF, an instruction) stays TODO, the FUNC and the statement named. The report
says at how many calls each FUNC was copied: a change of the FUNC in the RAPID means converting again.
"""

from typing import Any

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.compute import (
    FRAME_FIELDS,
    FRAME_RECORDS,
    LAYOUTS,
    Hole,
    MeasuredAtRunTime,
    Typed,
    Unknown,
    parse_params,
    path_of,
)
from crossarm.convert.values import Unresolvable
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr

FIELD = {"tooldata": "TFRAME", "wobjdata": "UFRAME"}
_POSE_FUNCTIONS = ("POSEMULT", "POSEINV", "DEFFRAME", "RELTOOL")
_DEPTH = 8


class NotInlined(Exception):
    """The body of a FUNC is not only assignments and a final RETURN: why, with the statement."""


def _describe(stmt: n.Stmt) -> str:
    """`IF tBase.tframe.trans.z < 100` / `TPWrite` / `WHILE ...`: the statement that stops the copy."""
    match stmt:
        case n.If(branches=branches):
            return f"IF {format_expr(branches[0].condition)}"
        case n.While(condition=condition):
            return f"WHILE {format_expr(condition)}"
        case n.For(var=var):
            return f"FOR {var}"
        case n.Test(subject=subject):
            return f"TEST {format_expr(subject)}"
        case n.ProcCall(name=name):
            return name
        case n.Return():
            return "RETURN"
        case n.Unsupported(raw=raw):
            return " ".join(raw.split())[:40]
    return type(stmt).__name__


def literal(value: Any, span: n.Span) -> n.Expr:
    """A value known now as a RAPID expression: [TRUE,[[0,0,145],[1,0,0,0]],...]."""
    if isinstance(value, bool):
        return n.Bool(span, value)
    if isinstance(value, int | float):
        return n.Number(span, float(value), format(float(value), ".10g"))
    if isinstance(value, str):
        return n.String(span, value)
    if isinstance(value, list):
        return n.Aggregate(span, tuple(literal(v, span) for v in value))
    raise Unresolvable(f"{value!r} is not a value")


class _Body:
    """The statements of a FUNC's body, rewritten on the call's target (module docstring)."""

    def __init__(self, routine: n.Routine, call: n.FuncCall, target: n.Expr, span: n.Span,
                 is_local: Any, layouts: Any) -> None:  # fmt: skip
        self.routine = routine
        self.name = f"{routine.name}()"
        self.target = target
        self.span = span
        self.is_local = is_local  # a name the calling routine declares itself (it would hide module data)
        self.layouts = layouts
        self.env: dict[str, n.Expr] = {}  # a parameter, a local datum: the expression it stands for
        self.params: set[str] = set()
        self.locals: set[str] = set()
        self.result: str | None = None
        self.out: list[n.Assign] = []
        self.target_root = path_of(target)[0]  # type: ignore[index]
        self.aliased: set[str] = set()  # parameters given the target itself
        self.changed = False  # the target was set to something other than itself
        self.default: n.Expr | None = None  # the result declared without a value: its default, set when needed
        self._bind(call)

    def _stop(self, why: str) -> NotInlined:
        return NotInlined(f"{self.name} is not inlined: {why}")

    def _bind(self, call: n.FuncCall) -> None:
        groups = parse_params(self.routine.params)
        if groups is None:
            raise self._stop("its parameter list is not read")
        if any(g[0].optional for g in groups) or any(a.name is not None for a in call.args):
            raise self._stop("optional parameters")
        given = [a.value for a in call.args]
        if len(given) != len(groups) or None in given:
            raise self._stop(f"it takes {len(groups)} arguments, {len(given)} given")
        for (param, *_), value in zip(groups, given, strict=True):
            self.env[param.name] = value  # type: ignore[assignment]
            self.params.add(param.name)
            if self.target_root in {p.upper() for p in self._names(value)}:  # type: ignore[arg-type]
                self.aliased.add(param.name)

    def _names(self, expr: Any) -> list[str]:
        from crossarm.convert.compute import _names

        return _names(expr)

    def statements(self) -> list[n.Assign]:
        body = [s for s in self.routine.body if not isinstance(s, n.Comment)]
        if not body or not isinstance(body[-1], n.Return) or body[-1].value is None:
            raise self._stop("it does not end with RETURN of a value")
        returned = body[-1].value
        if isinstance(returned, n.Name) and any(isinstance(s, n.DataDecl) and s.name.upper() == returned.name.upper()
                                                for s in body):  # fmt: skip
            self.result = returned.name.upper()
        for stmt in body[:-1]:
            self._statement(stmt)
        if self.result is None:
            self._emit(self.target, self._subst(returned))
        elif self.default is not None:
            self._emit(self.target, self.default)
        return self.out

    def _statement(self, stmt: n.Stmt) -> None:
        match stmt:
            case n.DataDecl(name=name, type_name=type_name, init=init, dims=dims, storage=storage):
                key = name.upper()
                if dims or storage != "VAR":
                    raise self._stop(f"l.{stmt.span.line} its local {storage} {name}{'{...}' if dims else ''}")
                self.locals.add(key)
                if init is not None:
                    value = self._subst(init)
                else:
                    try:
                        value = literal(self.layouts.default(type_name.lower()), self.span)
                    except Unresolvable as exc:
                        raise self._stop(f"l.{stmt.span.line} local {name} of type {type_name}") from exc
                if key == self.result and init is None:
                    self.default = value  # set only if a part of it is set before the whole of it
                elif key == self.result:
                    self._emit(self.target, value)
                else:
                    self.env[key] = value
            case n.Assign(target=target, value=value):
                path = path_of(target)
                if path is None:
                    raise self._stop(f"l.{stmt.span.line} `{format_expr(target)} :=`")
                root = path[0]
                if root == self.result:
                    if self.default is not None and len(path) > 1:
                        self._emit(self.target, self.default)
                    self.default = None
                    self._emit(self._subst(target), self._subst(value))
                elif root in self.locals or root in self.params:
                    if len(path) > 1:
                        raise self._stop(f"l.{stmt.span.line} sets a part of {format_expr(target)}"
                                         " (only its result is set part by part)")  # fmt: skip
                    new = self._subst(value)
                    if self.result is not None and self.result in {x.upper() for x in self._names(value)}:
                        raise self._stop(f"l.{stmt.span.line} {format_expr(target)} reads the result being built")
                    self.env[root] = new
                else:
                    raise self._stop(f"l.{stmt.span.line} changes data of the program ({format_expr(target)})")
            case _:
                raise self._stop(f"l.{stmt.span.line} `{_describe(stmt)}` (only assignments, pose functions and"
                                 " one RETURN at the end are copied into the call)")  # fmt: skip

    def _emit(self, target: n.Expr, value: n.Expr) -> None:
        identity = isinstance(value, n.Name) and value.name.upper() == self.target_root and target == self.target
        if not identity:
            self.changed = True
        if identity and path_of(target) == path_of(self.target):
            return
        if path_of(target) == path_of(self.target) and self.target_root not in {x.upper() for x in self._names(value)}:
            self.out = []  # the whole result set again: what was set before is gone
        self.out.append(n.Assign(self.span, target, value))

    def _subst(self, expr: Any) -> Any:
        """The expression with the parameters and local data replaced by what they stand for, the result by the
        call's target."""
        match expr:
            case n.Name(name=name):
                key = name.upper()
                if key == self.result:
                    return self.target
                if key in self.env:
                    if key in self.aliased and self.changed:
                        raise self._stop(f"it reads {name} (the call's target, {format_expr(self.target)}) after"
                                         " setting its result")  # fmt: skip
                    return self.env[key]
                if key in self.locals:
                    raise self._stop(f"it reads its local {name} before setting it")
                if self.is_local(name):
                    raise self._stop(f"it reads module data {name}, which the calling routine hides")
                return n.Name(self.span, name)
            case n.Component(base=base, field=field):
                return n.Component(self.span, self._subst(base), field)
            case n.Index(base=base, indices=indices):
                return n.Index(self.span, self._subst(base), tuple(self._subst(i) for i in indices))
            case n.UnaryOp(op=op, operand=operand):
                return n.UnaryOp(self.span, op, self._subst(operand))
            case n.BinaryOp(op=op, left=left, right=right):
                return n.BinaryOp(self.span, op, self._subst(left), self._subst(right))
            case n.Aggregate(items=items):
                return n.Aggregate(self.span, tuple(self._subst(i) for i in items))
            case n.FuncCall(name=name, args=args):
                return n.FuncCall(self.span, name, tuple(
                    n.Arg(self.span, self._subst(a.value) if a.value is not None else None, a.name, a.conditional)
                    for a in args))  # fmt: skip
        return expr


def inline_body(routine: n.Routine, call: n.FuncCall, target: n.Expr, span: n.Span, is_local: Any = lambda _: False,
                layouts: Any = None) -> list[n.Assign]:  # fmt: skip
    """The statements a call `target := routine(...)` stands for (module docstring); NotInlined otherwise."""
    return _Body(routine, call, target, span, is_local, layouts).statements()


def _pose_math(expr: n.Expr) -> bool:
    from crossarm.convert.runtime_points import expr_nodes

    return any(isinstance(node, n.FuncCall) and node.name.upper() in _POSE_FUNCTIONS for node in expr_nodes(expr))


class FuncInline:
    """Mixin of the routine translator: needs c, known, emit(), scope(), computed(), assign(), _payload_change(),
    rapid_text()."""

    def func_inlined(self, a: n.Assign, root_type: str, why: Unresolvable, what: str, category: str) -> bool:
        """`a` sets a tool, a work object or a pose to a FUNC of the backup not worked out now: its body copied
        into the call (module docstring). False: `a` is not such a call."""
        call = a.value
        if not isinstance(call, n.FuncCall):
            return False
        routine = self.c.computer.functions.get(call.name.upper())  # type: ignore[attr-defined]
        if routine is None or self.c.computer.robot_reads(call):  # type: ignore[attr-defined]
            return False  # a FUNC reading the robot: a calibration, said as such by the caller
        if isinstance(why, MeasuredAtRunTime):
            category = Blocker.CALIBRATION
        depth = getattr(self, "_inline_depth", 0)
        if depth >= _DEPTH:
            raise Untranslatable(f"{what}: {routine.name}() calls itself too deep to be inlined", category)
        try:
            statements = inline_body(routine, call, a.target, a.span, self.c.symbols.is_local,  # type: ignore[attr-defined]
                                     self.c.computer.layouts)  # type: ignore[attr-defined]  # fmt: skip
        except NotInlined as exc:
            raise Untranslatable(f"{what} computed from data only known at run time: {why}; {exc}", category) from exc
        path = path_of(a.target)
        assert path is not None
        self._inline_depth = depth + 1
        try:
            self.emit(("!" + _ascii(f"l.{a.span.line} {self.rapid_text(a).rstrip(';')}"))[:_REMARK].rstrip())  # type: ignore[attr-defined]
            if root_type in FRAME_RECORDS:
                self._inline_record(statements, root_type, path[0], routine.name)
            else:
                for stmt in statements:
                    self._inline_one(stmt, routine.name, lambda s: self.assign(s))  # type: ignore[attr-defined]
        finally:
            self._inline_depth = depth
        self.c.inlined.append((routine.name, self.name, a.span.line))  # type: ignore[attr-defined]
        return True

    def _inline_one(self, stmt: n.Assign, function: str, convert: Any) -> None:
        self.c.inline_texts[id(stmt)] = f"{format_expr(stmt.target)}:={format_expr(stmt.value)}"  # type: ignore[attr-defined]
        try:
            convert(stmt)
        except Untranslatable as exc:
            karel = "" if self.c.config.karel or not _pose_math(stmt.value) or "--karel" in str(exc) \
                else ": its pose functions are worked out by KAREL: convert with --karel"  # type: ignore[attr-defined]  # fmt: skip
            raise Untranslatable(f"{exc} (in {function}(), inlined: `{format_expr(stmt.target)} :="
                                 f" {format_expr(stmt.value)}`){karel}", exc.category) from exc  # fmt: skip

    def _inline_record(self, statements: list[n.Assign], root_type: str, key: str, function: str) -> None:
        """The statements setting a tool or a work object: known values followed now, frames written as they
        change at run time, the frame loaded at the end when it is known now."""
        dirty = False  # the frame changed now, not yet loaded
        frames = FRAME_FIELDS[root_type]
        copied: str | None = None  # the data whose frame was just copied: its frame read is the target's
        for i, stmt in enumerate(statements):
            if copied is not None:
                stmt = n.Assign(stmt.span, stmt.target, _frame_renamed(stmt.value, copied, root_type, self._target(stmt.target)))
            path = path_of(stmt.target)
            assert path is not None
            field = path[1] if len(path) > 1 else None
            if field is None or field in frames:  # the target's frame changes: no longer the copy
                copied = None
            try:
                root, new = self.c.computer.assigned(stmt)  # type: ignore[attr-defined]
            except Unresolvable as exc:
                if field is None and isinstance(stmt.value, n.FuncCall) \
                        and stmt.value.name.upper() in self.c.computer.functions:  # type: ignore[attr-defined]  # fmt: skip
                    pass  # another FUNC of the backup: copied in turn (computed() -> func_inlined)
                elif field is None:
                    stmt = self._whole_copy(stmt, root_type, key, exc)
                    if _frame_set_later(statements[i + 1 :], key, root_type):
                        continue  # its frame is set again further on: nothing to copy
                    copied = path_of(stmt.value)[0]  # type: ignore[index]
                elif field not in frames:
                    raise Untranslatable(f"{format_expr(stmt.target)}: {exc} (in {function}(), inlined)",
                                         Blocker.PAYLOAD if field == "TLOAD" else Blocker.RUNTIME_FRAME) from exc  # fmt: skip
                self._inline_one(stmt, function, lambda s: self.computed(s, root_type))  # type: ignore[attr-defined]
                dirty = False
                continue
            if (field is None or field in frames) and _frame_hole(new, root_type) is not None:
                self._inline_one(stmt, function, lambda s: self.computed(s, root_type))  # type: ignore[attr-defined]
                dirty = False
                continue
            self.known[root] = new  # type: ignore[attr-defined]
            if field is None or field in frames:
                dirty = True
        here = self.known.get(key)  # type: ignore[attr-defined]
        if dirty and isinstance(here, Typed):
            whole = n.Assign(statements[-1].span, self._target(statements[-1].target), literal(here.value, statements[-1].span))
            self.c.inline_texts[id(whole)] = f"{format_expr(whole.target)}:={function}()"  # type: ignore[attr-defined]
            self._inline_one(whole, function, lambda s: self.computed(s, root_type))  # type: ignore[attr-defined]
        elif root_type == "tooldata" and isinstance(here, Typed) and statements:
            self._payload_change(statements[-1], self.c.symbols.get(key).name, here)  # type: ignore[attr-defined]

    @staticmethod
    def _target(expr: n.Expr) -> n.Expr:
        while isinstance(expr, n.Component | n.Index):
            expr = expr.base
        return expr

    def _whole_copy(self, stmt: n.Assign, root_type: str, key: str, why: Unresolvable) -> n.Assign:
        """`t := tBase` with tBase's frame only known at run time: its other fields now, the frame statement
        `t.tframe := tBase.tframe` returned (frame_writes copies it at run time)."""
        source = stmt.value
        decl = self.c.symbols.get(source.name) if isinstance(source, n.Name) else None  # type: ignore[attr-defined]
        if decl is None or decl.type_name.lower() != root_type or decl.dims:
            raise Untranslatable(f"{format_expr(stmt.target)} := {format_expr(source)}: {why}", Blocker.RUNTIME_FRAME)
        here = self.scope(decl.name.upper())  # type: ignore[attr-defined]
        if isinstance(here, Unknown):
            raise Untranslatable(str(here.error(decl.name)), Blocker.CALIBRATION if here.measured else Blocker.RUNTIME_FRAME)
        try:
            value = here if isinstance(here, Typed) else self.c.computer.all_but(decl.name, (decl.name.upper(), "#"))  # type: ignore[attr-defined]
        except Unresolvable as exc:
            raise Untranslatable(f"{format_expr(stmt.target)} := {decl.name}: {exc}", Blocker.RUNTIME_FRAME) from exc
        names = [f.upper() for f, _ in LAYOUTS[root_type]]
        frame = FIELD[root_type]
        data = list(value.value)
        for name, item in zip(names, data, strict=True):
            if name != frame and isinstance(item, Hole):
                raise Untranslatable(f"{format_expr(stmt.target)} := {decl.name}: {item.why}",
                                     Blocker.CALIBRATION if item.measured else Blocker.RUNTIME_FRAME)  # fmt: skip
        data[names.index(frame)] = Hole(f"'{format_expr(stmt.target)}.{frame.lower()}' is copied from {decl.name}",
                                        here=True)  # fmt: skip
        self.known[key] = Typed(data, root_type, 0)  # type: ignore[attr-defined]
        span = stmt.span
        return n.Assign(span, n.Component(span, stmt.target, frame.lower()), n.Component(span, source, frame.lower()))


def inlined_notes(c: Any) -> None:
    """One note per FUNC copied into calls: at how many (the calls left TODO not counted)."""
    todo = {(note.program, note.rapid_line) for note in c.result.notes if note.kind == "TODO"}
    sites: dict[str, list[tuple[str, int]]] = {}
    for function, program, line in c.inlined:
        if (program, line) not in todo and (program, line) not in sites.setdefault(function, []):
            sites[function].append((program, line))
    for function, places in sites.items():
        if not places:
            continue
        count = len(places)
        c.note(places[0][0], places[0][1], "WARNING", f"FUNC {function}() of the backup is inlined at {count} call"
               f" site{'s' if count > 1 else ''}: its body is copied into each call, as TP (and KAREL) lines; convert"
               f" again after a change of {function}() in the RAPID", Blocker.INLINED)  # fmt: skip


def _frame_renamed(expr: Any, source: str, root_type: str, target: n.Expr) -> Any:
    """`expr` with what it reads of `source`'s frame read from the target's instead (just copied from it)."""
    field = FIELD[root_type]
    match expr:
        case n.Component(base=n.Name(name=name), field=f) if name.upper() == source and f.upper() == field:
            return n.Component(expr.span, target, f)
        case n.Component(base=base, field=f):
            return n.Component(expr.span, _frame_renamed(base, source, root_type, target), f)
        case n.Index(base=base, indices=indices):
            return n.Index(expr.span, _frame_renamed(base, source, root_type, target), indices)
        case n.UnaryOp(op=op, operand=operand):
            return n.UnaryOp(expr.span, op, _frame_renamed(operand, source, root_type, target))
        case n.BinaryOp(op=op, left=left, right=right):
            return n.BinaryOp(expr.span, op, _frame_renamed(left, source, root_type, target),
                              _frame_renamed(right, source, root_type, target))  # fmt: skip
        case n.Aggregate(items=items):
            return n.Aggregate(expr.span, tuple(_frame_renamed(i, source, root_type, target) for i in items))
        case n.FuncCall(name=name, args=args):
            return n.FuncCall(expr.span, name, tuple(
                n.Arg(a.span, _frame_renamed(a.value, source, root_type, target) if a.value is not None else None,
                      a.name, a.conditional) for a in args))  # fmt: skip
    return expr


def _frame_set_later(statements: list[n.Assign], key: str, root_type: str) -> bool:
    """Whether a statement further on sets the whole frame again (tframe, uframe) without reading what it was."""
    from crossarm.convert.compute import _names

    for stmt in statements:
        if key in {name.upper() for name in _names(stmt.value)}:
            return False
        if path_of(stmt.target) in ((key,), (key, FIELD[root_type])):
            return True
    return False


def _frame_hole(value: Typed, root_type: str) -> Hole | None:
    from crossarm.convert.compute import first_hole

    return first_hole(value.value, FRAME_FIELDS[root_type], root_type)


def _ascii(text: str) -> str:
    from crossarm.convert.tp_numbers import ascii_text

    return ascii_text(text)


_REMARK = 33
