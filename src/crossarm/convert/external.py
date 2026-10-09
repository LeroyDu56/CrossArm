# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Routines the integrator provides as TP (or KAREL) programs: the mapping key `external_routines`.

Some RAPID routines CrossArm cannot write: one the backup does not declare (a system module, an option, another
task holds it), or one that reads or writes files, talks over sockets or packs byte buffers, itself or through what
it calls (convert.unsupported.RoutineUse). The integrator can write that program on the FANUC side, by hand or in
KAREL, and say so in the mapping file:

    "external_routines": {"WriteLog": {"program": "WRITE_LOG"}}

Then each call is `CALL WRITE_LOG(args)`, its arguments passed as CrossArm passes them to the routines it converts
(convert.arguments, measured: numbers, registers, text up to 38 characters, 1 / 0 for a switch, a frame by its
number), the routine of the backup is not written, and the report lists what the program has to do: its
arguments in order (AR[1], AR[2]...) with their RAPID types, and the num RAPID reads back, which the program
writes in the register named before it ends (the caller reads it back after the CALL, as it does from the
routines CrossArm converts). A call to a program the robot does not have stops the caller there (ROBOGUIDE:
INTP-222 Call program failed, MEMO-073 Program does not exist); a .LS calling it loads all the same.

A routine the backup does not declare has no parameter list: its arguments are typed from what the calls pass
(a number, a text, TRUE / FALSE, data of the backup), or from "arguments" in the mapping file
(["num", "string", "INOUT num"]): "INOUT num" is a num RAPID reads back.

A point (robtarget, pos, pose) is passed by the number of the position register that holds it: the program reads
PR[AR[n]] (a point the caller keeps in a register: that one; else a copy in a register of CrossArm's own).

A function returning a num, a pos, a pose or a robtarget is provided when its call is the whole right-hand side of
an assignment (`x := F(args)`): `CALL PROG(args,k)`, k the number of a result register of its own (R[k] for a num,
PR[k] for the others: key "PROG.result" of `registers` / `point_registers`); the program writes its result in
R[AR[last]] or PR[AR[last]] (x, y, z only for a pos), and the caller reads it there after the CALL. A function
the backup does not declare says what it returns in the mapping file ("returns": "pose"). Used elsewhere in an
expression it stays TODO: TP gives no value back to an expression.

What TP cannot pass stays TODO with why: a speed or a zone, a record, an array, data passed by reference
other than a num.

Measured on ROBOGUIDE V10.10 (tools/make_external_probe.py, tools/make_func_result_probe.py): a provided program
writes `R[AR[n]]=...`, `PR[AR[n]]=...`, `PR[AR[n],i]=...` and reads `PR[AR[n],i]`; the caller reads the result
after the CALL.

CrossArm writes, in the mapping file of every conversion, the routines it could not write for those reasons,
each with `"program": null`: nothing changes until a name is filled in.
"""

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from crossarm.convert.arguments import MAX_ARGS, Signature, Slot
from crossarm.convert.compute import PURE_FUNCTIONS, path_of
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr
from crossarm.rapid.walk import base_name, split_params, walk_statements

# The types "arguments" may give an argument of a routine the backup does not declare.
ARGUMENT_TYPES = ("num", "bool", "string", "INOUT num", "robtarget", "pos", "pose")
POINT_TYPES = ("robtarget", "pos", "pose")  # passed by the number of the position register holding it
RETURN_TYPES = ("num", "pos", "pose", "robtarget")  # what a provided function may give back ("returns")
RESULT = "result"  # the key of its result register: "PROG.result"
# RAPID's own functions: a call to one is not a routine missing from the backup
RAPID_FUNCTIONS = PURE_FUNCTIONS | frozenset({
    "CALCROTAXISFRAME", "CALCROTAXFFRAMEZ", "DEFACCFRAME", "ORROBT", "OROBT", "READMOTOR", "CORRREAD", "READNUM",
    "READBIN", "READSTR", "READSTRBIN", "READVAR", "READANYBIN", "DNUMTONUM", "NUMTODNUM", "STRTOVAL", "STRTOBYTE",
    "BYTETOSTR", "BITAND", "BITOR", "BITXOR", "BITNEG", "BITLSH", "BITRSH", "BITCHECK", "GINPUTDNUM",
    "GOUTPUTDNUM", "CSPEEDOVERRIDE", "MAXROBSPEED", "TESTANDSET", "SOCKETPEEK", "SOCKETGETSTATUS", "ISSYNCMOVEON",
    "TASKRUNMOT", "TASKRUNROB", "PARIDPOSVALID", "PARIDROBVALID", "PFRESTART", "ARGNAME", "VALIDIO", "IOUNITSTATE",
    "TYPE", "UICLIENTEXIST", "EVENTTYPE", "EXECHANDLER", "EXECLEVEL", "NUMTOSTR", "DNUMTOSTR", "STRFORMAT", "ERRSTR",
    "GETTASKNAME", "GETMECUNITNAME", "GETNEXTMECHUNIT", "GETSYSINFO", "GETSIGNALORIGIN", "GETSERVICEINFO",
    "ROBNAME", "NONMOTIONMODE", "CDATE", "CTIME", "GETTIME", "DECTOHEX", "HEXTODEC", "STRDIGCMP", "STRDIGCALC",
    "MODEXIST", "MODTIME", "FILESIZE", "FSSIZE", "ISDIR", "READDIR", "CANONCHAR", "SIMULATEMODE", "ISSTOPMOVEACT",
    "ISSTOPSTATEEVENT", "ISMECHUNITACTIVE", "ISREADONLY", "ISLOGGEDIN", "USERNAME", "PATHLEVEL", "PATHRECVALIDBWD",
    "PATHRECVALIDFWD", "RMQGETSLOTNAME", "RMQFINDSLOT", "TESTSIGNREAD", "TASKSINSYNC", "ABS", "SQRT",
})  # fmt: skip
_NAME = re.compile(r"([A-Za-z_]\w*)\s*(\{[^}]*\})?\s*$")
_CHANGING = frozenset({"INCR", "DECR", "ADD", "CLEAR"})  # instructions that change their first argument
MISSING_WHY = "not in the backup (a system module, an option, another task)"


@dataclass(frozen=True, slots=True)
class ProvidedRoutine:
    """An entry of external_routines the integrator filled in."""

    name: str  # the RAPID routine, as the mapping file writes it
    program: str  # the TP program that does its job, upper case
    arguments: tuple[str | None, ...] | None = None  # types of a routine the backup does not declare
    returns: str | None = None  # what a function the backup does not declare gives back (RETURN_TYPES)


@dataclass(frozen=True, slots=True)
class ProvidedArgument:
    """One argument of a provided program, as the CALL passes it."""

    register: str  # "AR[1]"
    name: str  # the RAPID parameter ("argument 2" for a routine the backup does not declare)
    rapid_type: str  # "num", "INOUT num", "switch", "tooldata"...
    passed: str  # what the program reads in it
    returned: bool = False  # RAPID reads it back after the call: the program writes it in a register


@dataclass
class ProvidedProgram:
    """A routine of the backup (or one it calls) the integrator provides as a TP or KAREL program."""

    routine: str  # as declared, else as called
    program: str
    module: str | None  # the module declaring it; None: the backup does not
    declaration: str  # "PROC WriteLog(string text)", "" when the backup does not declare it
    why: str  # why CrossArm does not write it itself; "" when it could have
    function: bool = False  # a FUNC: its value comes back only to `x := F(args)`, when it returns one of RETURN_TYPES
    returns: str | None = None  # a function: what it gives back, in R[AR[last]] (num) or PR[AR[last]]
    arguments: tuple[ProvidedArgument, ...] | None = None  # None: not known (its calls stay TODO, see problem)
    problem: str = ""  # why its calls cannot be written, when its parameters say so
    calls: list[tuple[str, int]] = field(default_factory=list)  # (TP program, RAPID line) of each CALL written
    todo: dict[tuple[str, int], str] = field(default_factory=dict)  # calls left TODO -> why
    returned: dict[str, int] = field(default_factory=dict)  # argument read back -> the R[n] the program writes
    on_robot: bool | None = None  # whether the FANUC robot has it already; None: its programs were not read
    layout: Signature | None = None  # its AR[n] layout, from its parameters (a routine the backup declares)


@dataclass(frozen=True, slots=True)
class Candidate:
    """A routine CrossArm could not write, which the integrator may provide (written with "program": null)."""

    name: str
    why: str
    arguments: tuple[str | None, ...] | None = None  # for one the backup does not declare: types from its calls
    returns: str | None = None  # a function: what its calls assign it to (RETURN_TYPES)


def declared_layout(routine: n.Routine, extra: int = 0) -> Signature | str:
    """The AR[n] layout of a provided program from the routine's parameters, or why they cannot be passed.

    Required parameters in order, then the optional switches and work objects (1 / 0, a frame number); a num
    passed by reference that the routine changes is read back after the CALL (Signature.copied). `extra`: the
    arguments the CALL adds (1 for a function: its result register)."""
    required: list[Slot] = []
    optional: list[Slot] = []
    modes: dict[str, str] = {}
    for part in split_params(routine.params):
        is_optional = part.startswith("\\")
        alternatives = part.lstrip("\\").split("|")
        if not is_optional and len(alternatives) > 1:
            return f"unreadable parameter list: {routine.params}"
        for alternative in alternatives:
            words = alternative.split()
            match = _NAME.search(alternative.strip())
            if len(words) < 2 or match is None:
                return f"unreadable parameter list: {routine.params}"
            name, dims = match.group(1), match.group(2)
            mode = words[0].upper() if words[0].upper() in ("VAR", "PERS", "INOUT") else ""
            type_name = (words[-2] if not dims else words[-2].split("{")[0]).lower()
            if dims:
                return f"parameter {name} is an array: TP arguments are single values"
            if is_optional:
                if type_name in ("switch", "wobjdata") and mode not in ("VAR", "INOUT"):
                    optional.append(Slot(name, type_name, optional=True))
                    continue
                return f"optional {type_name} parameter {name}: only optional switches and work objects are passed"
            if type_name in ("tooldata", "wobjdata"):
                if mode in ("VAR", "INOUT"):
                    return f"{type_name} parameter {name} is passed by reference ({mode}): a frame is passed by its number"
                required.append(Slot(name, type_name))
            elif type_name in ("num", "bool", "string", *POINT_TYPES):  # a point: its position register's number
                required.append(Slot(name, type_name, by_reference=bool(mode)))
                modes[name.upper()] = mode
            elif type_name in ("speeddata", "zonedata"):
                return (f"{type_name} parameter {name}: CrossArm passes a speed or a zone as the numbers the routine's"
                        " own moves take, and a provided program's moves are not known")  # fmt: skip
            else:
                return f"{type_name} parameter {name}: TP arguments are numbers, text or frame numbers"
    slots = tuple(required + optional)
    if len(slots) + extra > MAX_ARGS:
        return f"{len(slots) + extra} arguments: a TP CALL takes at most {MAX_ARGS} arguments"
    changed = changed_parameters(routine.body, {s.key for s in slots if s.by_reference})
    for slot in slots:
        if slot.key in changed and slot.kind != "num":
            return (f"RAPID reads its {slot.kind} {slot.name} ({modes[slot.key]}) back after the call: a provided"
                    " program gives back only a num, in a register")  # fmt: skip
    return Signature(slots, frozenset(changed), routine.name)


def provided_returns(routine: n.Routine | None, entry: ProvidedRoutine) -> str | None:
    """What a provided function gives back to `x := F(args)`: its declared type when the backup declares it (None
    for a type a register does not hold), else "returns" of the mapping file."""
    if routine is None:
        return entry.returns
    if routine.kind != "FUNC":
        return None
    kind = (routine.return_type or "").lower()
    return "num" if kind == "dnum" else kind if kind in RETURN_TYPES else None


def changed_parameters(body: Iterable[n.Stmt], keys: set[str]) -> set[str]:
    """The parameters (upper case, among `keys`) the routine may change: assigned, changed by Incr / Add...,
    or passed on to a call (which may change it, as RAPID's SocketReceive \\Str:=... does)."""
    found: set[str] = set()
    for stmt in walk_statements(body):
        if isinstance(stmt, n.Assign) and (target := base_name(stmt.target)) and target.upper() in keys:
            found.add(target.upper())
        elif isinstance(stmt, n.ProcCall):
            args = stmt.args[:1] if stmt.name.upper() in _CHANGING else stmt.args
            found |= {a.value.name.upper() for a in args if isinstance(a.value, n.Name) and a.value.name.upper() in keys}
        elif isinstance(stmt, n.For) and stmt.var.upper() in keys:
            found.add(stmt.var.upper())
    for stmt in walk_statements(body):  # StrToVal(text, value) sets its second argument
        for node in _expressions(stmt):
            if isinstance(node, n.FuncCall) and node.name.upper() == "STRTOVAL" and len(node.args) > 1:
                value = node.args[1].value
                if isinstance(value, n.Name) and value.name.upper() in keys:
                    found.add(value.name.upper())
    return found


def _expressions(node: object, root: bool = True) -> Iterable[object]:
    if not root and isinstance(node, n.Stmt):
        return
    yield node
    if isinstance(node, tuple | list):
        for item in node:
            yield from _expressions(item, False)
    elif hasattr(node, "__dataclass_fields__") and not isinstance(node, n.Span):
        for name in node.__dataclass_fields__:
            yield from _expressions(getattr(node, name), False)


def undeclared_layout(call: n.ProcCall | n.FuncCall, provided: ProvidedRoutine,
                      kind_of: Callable[[n.Expr], str | None], extra: int = 0) -> Signature | str:  # fmt: skip
    """The AR[n] layout of a call to a provided routine the backup does not declare: each argument typed by the
    mapping file ("arguments"), else by what the call passes; or why it cannot be passed."""
    named = [a for a in call.args if a.name is not None]
    if named:
        return (f"its optional argument \\{named[0].name}: the backup does not declare {call.name}, so where it goes"
                " among the arguments is not known")  # fmt: skip
    values = [a.value for a in call.args]
    hints = provided.arguments
    if hints is not None and len(hints) != len(values):
        return (f"{len(values)} arguments given, external_routines.{provided.name}.arguments gives"
                f" {len(hints)}")  # fmt: skip
    if len(values) + extra > MAX_ARGS:
        return f"{len(values) + extra} arguments: a TP CALL takes at most {MAX_ARGS}"
    slots = []
    for i, value in enumerate(values, 1):
        kind = (hints[i - 1] if hints is not None else None) or (kind_of(value) if value is not None else None)
        if kind is None:
            shown = f" ('{format_expr(value)}')" if value is not None else ""
            return (f"argument {i}{shown}: its type is not known, the backup does not declare {call.name}: give it"
                    f" in external_routines.{provided.name}.arguments")  # fmt: skip
        returned = kind == "INOUT num"
        slots.append(Slot(f"arg{i}", "num" if returned else kind, by_reference=returned))
    return Signature(tuple(slots), frozenset(s.key for s in slots if s.by_reference), call.name)


def arguments_of(layout: Signature, declared: bool, returns: str | None = None) -> tuple[ProvidedArgument, ...]:
    """What the report says of each argument of a provided program, in AR[n] order; a function's result
    register last."""
    out = []
    for i, slot in enumerate(layout.slots, 1):
        name = slot.name if declared else f"argument {i}"
        returned = slot.key in layout.copied
        rapid_type = ("INOUT " if slot.by_reference and not declared else "") + slot.kind
        passed = {
            "num": "the number",
            "bool": "1 for TRUE, 0 for FALSE",
            "string": "the text (38 characters at most)",
            "switch": "1 when the call gives it, 0 otherwise",
            "tooldata": "the UTOOL number of the tool",
            "wobjdata": "the UFRAME number of the work object (0 when not given)" if slot.optional else
                        "the UFRAME number of the work object",
            "robtarget": f"the number of the position register holding the point: read PR[AR[{i}]]",
            "pos": f"the number of the position register holding it: read x, y, z in PR[AR[{i}],1..3]",
            "pose": f"the number of the position register holding it: read PR[AR[{i}]] (x, y, z, w, p, r)",
        }[slot.kind]  # fmt: skip
        out.append(ProvidedArgument(f"AR[{i}]", name, rapid_type, passed, returned))
    if returns is not None:
        k = len(layout.slots) + 1
        out.append(ProvidedArgument(f"AR[{k}]", RESULT, returns, result_text(returns, k)))
    return tuple(out)


def result_text(returns: str, k: int) -> str:
    """What a provided function does with its result register AR[k]."""
    return {
        "num": f"the number of the register to write the result in: R[AR[{k}]]=...",
        "pos": f"the number of the position register to write the result in: x, y, z in PR[AR[{k}],1..3]",
        "pose": f"the number of the position register to write the result in: PR[AR[{k}]] (x, y, z, w, p, r)",
        "robtarget": f"the number of the position register to write the point in: PR[AR[{k}]] (x, y, z, w, p, r"
                     " and its configuration)",
    }[returns]  # fmt: skip


def literal_kind(expr: n.Expr, type_of: Callable[[str], str | None]) -> str | None:
    """num, bool or string for what a call passes, when that can be told without the routine's declaration."""
    if isinstance(expr, n.Number):
        return "num"
    if isinstance(expr, n.String):
        return "string"
    if isinstance(expr, n.Bool):
        return "bool"
    if isinstance(expr, n.Name):
        kind = type_of(expr.name)
        return {"num": "num", "dnum": "num", "bool": "bool", "string": "string", "robtarget": "robtarget",
                "pos": "pos", "pose": "pose"}.get(kind or "")  # fmt: skip
    if isinstance(expr, n.UnaryOp):
        return "bool" if expr.op.upper() == "NOT" else literal_kind(expr.operand, type_of)
    if isinstance(expr, n.BinaryOp):
        if expr.op.upper() in ("AND", "OR", "XOR", "=", "<>", "<", ">", "<=", ">="):
            return "bool"
        if expr.op in ("-", "*", "/") or expr.op.upper() in ("DIV", "MOD"):
            return "num"
        return literal_kind(expr.left, type_of) or literal_kind(expr.right, type_of)
    return None


def candidates(selected: Iterable[n.Routine], procs: Mapping[str, n.Routine], declared: set[str],
               instructions: set[str] | frozenset[str], move_routines: set[str], uses,
               type_of: Callable[[str], str | None]) -> list[Candidate]:  # fmt: skip
    """The routines CrossArm could not write that the integrator may provide, in the order the programs reach
    them: those the written programs call that the backup does not declare, and those using files, sockets or
    byte buffers themselves (not through another routine: providing that one is enough) that they reach.

    `uses(name)`: (the routines in between, 'Open: why') when a routine uses those, else None
    (RoutineUse._uses, upper-case name)."""
    found: dict[str, Candidate] = {}
    missing: dict[str, list[tuple[str | None, ...] | None]] = {}
    returned: dict[str, set[str | None]] = {}  # a function missing from the backup -> what its calls assign it to
    shown: dict[str, str] = {}
    reached: dict[str, n.Routine] = {}
    todo = list(selected)
    first = True
    while todo:
        batch, todo = todo, []
        for routine in batch:
            for stmt in walk_statements(routine.body):
                if first and isinstance(stmt, n.Assign) and isinstance(stmt.value, n.FuncCall):
                    call = stmt.value
                    key = call.name.upper()
                    if key not in declared and key not in RAPID_FUNCTIONS \
                            and (kind := assigned_kind(stmt.target, type_of)) is not None:  # fmt: skip
                        kinds = None if any(a.name is not None for a in call.args) else tuple(
                            literal_kind(a.value, type_of) if a.value is not None else None for a in call.args)  # fmt: skip
                        missing.setdefault(key, []).append(kinds)
                        returned.setdefault(key, set()).add(kind)
                        found.setdefault(key, Candidate(call.name, MISSING_WHY))
                    continue
                if not isinstance(stmt, n.ProcCall):
                    continue
                key = stmt.name.upper()
                if first and key not in declared and key not in instructions and key not in move_routines:
                    shown.setdefault(key, stmt.name)
                    kinds = None if any(a.name is not None for a in stmt.args) else tuple(
                        literal_kind(a.value, type_of) if a.value is not None else None for a in stmt.args)  # fmt: skip
                    missing.setdefault(key, []).append(kinds)
                    found.setdefault(key, Candidate(stmt.name, MISSING_WHY))
                elif key in procs and key not in reached:
                    reached[key] = procs[key]
                    todo.append(procs[key])
        first = False  # a call the written programs make: the TODO is theirs; deeper ones are not written
    for key in [r.name.upper() for r in selected] + list(reached):
        found_use = uses(key)
        if found_use is not None and not found_use[0] and key in procs and key not in found:
            found[key] = Candidate(procs[key].name, f"it calls {found_use[1]}")
    out = []
    for key, candidate in found.items():
        returns = returned.get(key, set())
        returns_one = next(iter(returns)) if len(returns) == 1 else None
        if key in missing:
            out.append(Candidate(candidate.name, candidate.why, _agreed(missing[key]), returns_one))
        else:
            out.append(candidate)
    return out


def assigned_kind(target: n.Expr, type_of: Callable[[str], str | None]) -> str | None:
    """What a provided function assigned to `target` gives back (RETURN_TYPES): num data, a robtarget or a pose,
    a frame's uframe or tframe (a pose), the trans of one (a pos); None for anything else."""
    path = path_of(target)
    if not path:
        return None
    root = type_of(path[0])
    rest = tuple(p for p in path[1:] if p != "{}")
    if root in ("num", "dnum") and not rest:
        return "num"
    if root in ("robtarget", "pose") and not rest:
        return root
    if root in ("tooldata", "wobjdata") and rest in (("TFRAME",), ("UFRAME",)):
        return "pose" if rest[0] == ("TFRAME" if root == "tooldata" else "UFRAME") else None
    if root in ("tooldata", "wobjdata") and rest in (("TFRAME", "TRANS"), ("UFRAME", "TRANS")):
        return "pos" if rest[0] == ("TFRAME" if root == "tooldata" else "UFRAME") else None
    return None


def _agreed(calls: list[tuple[str | None, ...] | None]) -> tuple[str | None, ...] | None:
    """The argument types every call agrees on (None where they do not); None when the calls differ in number of
    arguments or pass options."""
    if any(c is None for c in calls) or len({len(c) for c in calls if c is not None}) != 1:
        return None
    first = calls[0]
    assert first is not None
    if not first:
        return None  # no argument: nothing to say
    return tuple(kinds[0] if len(set(kinds)) == 1 else None for kinds in zip(*calls, strict=True))  # type: ignore[arg-type]


PROVIDED_INTRO = (
    "These routines are not written: the mapping file (external_routines) says a TP or KAREL program of the name"
    " given does their job. Each call is CALL NAME(arguments): the program reads them as AR[1], AR[2]... and cannot"
    " change them; a num RAPID reads back after the call is given back in the register named, which the program"
    " sets before it ends; a point is passed by the number of the position register holding it (PR[AR[n]]); a"
    " function writes its result in the register its last argument names (R[AR[n]] or PR[AR[n]]). Load them with the other programs: a CALL to a program the robot does not have stops the"
    " caller there (INTP-222)."
)


def argument_texts(use: ProvidedProgram) -> list[str]:
    """'AR[1] text (string): the text (38 characters at most)' for each argument, in order; with the register a
    num read back is given back in."""
    out = []
    for argument in use.arguments or ():
        text = f"{argument.register} {argument.name} ({argument.rapid_type}): {argument.passed}"
        if argument.returned:
            register = use.returned.get(argument.name)
            where = f"R[{register}]" if register is not None else "the register the report names once a call is written"
            text += f"; RAPID reads it back: write its new value in {where}"
        out.append(text)
    return out


def note_texts(use: ProvidedProgram) -> list[str]:
    """What else the integrator needs to know of a provided program: why CrossArm does not write it, the RAPID
    declaration, the calls left TODO, whether the robot has it."""
    out = []
    if use.why:
        out.append(f"CrossArm cannot write it: {use.why}")
    if use.declaration:
        out.append(f"RAPID: {use.declaration}")
    else:
        out.append("the backup does not declare it: arguments as the calls pass them")
    if use.arguments is not None and not use.arguments:
        out.append("no argument")
    if use.function and use.returns is not None:
        out.append(f"a function returning a {use.returns}: called where it is the whole right-hand side of an"
                   " assignment, its result read back from the register its last argument names; used elsewhere in"
                   " an expression, the statement stays TODO")  # fmt: skip
    elif use.function:
        out.append("a function: TP gives no value back to an expression, the statements using it stay TODO (only a"
                   " num, pos, pose or robtarget comes back, to `x := F(...)`)")  # fmt: skip
    if use.problem:
        out.append(f"its calls stay TODO: {use.problem}")
    elif use.todo and not (use.function and use.returns is None):
        first = next(iter(use.todo.values()))
        out.append(f"{len(use.todo)} call{'s' if len(use.todo) > 1 else ''} left TODO: {first}")
    if use.on_robot is not None:
        out.append("the FANUC robot has it" if use.on_robot else "the FANUC robot does not have it yet")
    return out


__all__ = [
    "ARGUMENT_TYPES",
    "MISSING_WHY",
    "POINT_TYPES",
    "PROVIDED_INTRO",
    "RAPID_FUNCTIONS",
    "RESULT",
    "RETURN_TYPES",
    "Candidate",
    "ProvidedArgument",
    "ProvidedProgram",
    "ProvidedRoutine",
    "argument_texts",
    "arguments_of",
    "assigned_kind",
    "candidates",
    "changed_parameters",
    "declared_layout",
    "literal_kind",
    "note_texts",
    "provided_returns",
    "result_text",
    "undeclared_layout",
]  # fmt: skip
