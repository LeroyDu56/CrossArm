# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Frames and positions the programs compute, worked out at conversion time when nothing they read can change.

RAPID programs often build a frame instead of declaring it: a tool made from a base tool and an
offset (`tGrip := MakeTool(tBase, nAngle)`), a work object copied from another one, a point put
together from a pose. TP cannot do that arithmetic: `PR[1]=PR[2]+PR[3]` adds component by
component, a pose product, an inverse or an angle function does not exist (measured on ROBOGUIDE).
But when every value such a computation reads is fixed, its result is fixed too, and CrossArm can
work it out once. The program then only loads it, where the RAPID computed it:
`UTOOL[3]=PR[95]`, the register set by SETUP_FRAMES.

A value is computed only when each input is certain:

  - a CONST; a PERS or VAR that no program changes (`Written`: assignments, arguments passed to a
    routine that can change them, error handlers, SetDataVal), in any task of the backup;
  - a routine's own data, set earlier on every path to this point (the converter follows the
    routine: a value set in one branch of an IF only, in a loop, or before a call that may change
    it is unknown after it);
  - built by the functions below, or by a FUNC of the backup that only computes.

Anything else leaves the TODO, with the reason: a frame frozen at a wrong value, without a word,
would be worse than a TODO. A value read from the robot (CRobT, CJointT...) is a calibration
measured when the program runs: `MeasuredAtRunTime`, which the report explains apart.
"""

import copy
import math
import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from crossarm.convert.handlers import body as handler_body
from crossarm.convert.values import (
    PREDEFINED_SPEEDS,
    PREDEFINED_ZONES,
    NotInBackup,
    Symbols,
    Unresolvable,
    predefined_value,
    unit_quaternion,
)
from crossarm.geometry import Pose, mat_mul, matrix_to_quat, matrix_to_wpr, quat_to_matrix, rot_x, rot_y, rot_z
from crossarm.rapid import nodes as n
from crossarm.rapid.walk import split_params, walk_statements


class MeasuredAtRunTime(Unresolvable):
    """The value reads the robot (its position, its joints): a calibration, only known when the program runs."""


def measured_reason(what: str, type_name: str, is_frame: bool, exc: MeasuredAtRunTime, read_here: bool) -> str:
    """Why a frame or a position read on the robot stays TODO: TP reads the robot's position (LPOS, JPOS), but no
    frame is computed from it, and only a robtarget set to CRobT() itself is kept in a position register.
    `read_here`: the assignment itself reads the robot; else it derives from a reading left TODO, which says why."""
    if is_frame:
        return (f"{what} measured on the robot when the program runs (a calibration): {exc}. TP reads the position"
                " (PR[n]=LPOS) but cannot compute a frame from it (no pose product, inverse or angle function):"
                " set this frame with the FANUC frame setup, or in KAREL")  # fmt: skip
    if not read_here:
        return f"{what} measured on the robot when the program runs: {exc}"
    if type_name == "robtarget":  # a FUNC of the backup reads it, or a component of the point is set
        kept = "a point is kept in a position register when it is set to CRobT() itself, as a whole"
    else:
        kept = f"CrossArm keeps robtargets in position registers, not a {type_name}"
    reading = "the joints (PR[n]=JPOS)" if type_name in ("jointtarget", "robjoint") else "the TCP (PR[n]=LPOS)"
    return f"{what} measured on the robot when the program runs: {exc}. TP reads {reading}, but {kept}"


# -- data layouts ----------------------------------------------------------------------------------

LAYOUTS: dict[str, tuple[tuple[str, str], ...]] = {
    "pos": (("x", "num"), ("y", "num"), ("z", "num")),
    "orient": (("q1", "num"), ("q2", "num"), ("q3", "num"), ("q4", "num")),
    "pose": (("trans", "pos"), ("rot", "orient")),
    "confdata": (("cf1", "num"), ("cf4", "num"), ("cf6", "num"), ("cfx", "num")),
    "speeddata": (("v_tcp", "num"), ("v_ori", "num"), ("v_leax", "num"), ("v_reax", "num")),
    "zonedata": (("finep", "bool"), ("pzone_tcp", "num"), ("pzone_ori", "num"), ("pzone_eax", "num"),
                 ("zone_ori", "num"), ("zone_leax", "num"), ("zone_reax", "num")),
    "robjoint": tuple((f"rax_{i}", "num") for i in range(1, 7)),
    "extjoint": tuple((f"eax_{c}", "num") for c in "abcdef"),
    "robtarget": (("trans", "pos"), ("rot", "orient"), ("robconf", "confdata"), ("extax", "extjoint")),
    "jointtarget": (("robax", "robjoint"), ("extax", "extjoint")),
    "loaddata": (("mass", "num"), ("cog", "pos"), ("aom", "orient"), ("ix", "num"), ("iy", "num"), ("iz", "num")),
    "tooldata": (("robhold", "bool"), ("tframe", "pose"), ("tload", "loaddata")),
    "wobjdata": (("robhold", "bool"), ("ufprog", "bool"), ("ufmec", "string"), ("uframe", "pose"), ("oframe", "pose")),
}
_SCALARS = {"num": 0.0, "dnum": 0.0, "bool": False, "string": ""}
_RECORD = re.compile(r"RECORD\s+([A-Za-z_]\w*)(.*?)ENDRECORD", re.IGNORECASE | re.DOTALL)
_FIELD = re.compile(r"([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*;")


class Layouts:
    """The components of every data type: RAPID's own, and the RECORDs the backup declares."""

    def __init__(self, modules: Iterable[n.Module]) -> None:
        self.layouts = dict(LAYOUTS)
        for module in modules:
            for item in module.body:
                if isinstance(item, n.Unsupported) and item.kind == "RECORD":
                    found = _RECORD.search(item.raw)
                    if found:
                        fields = tuple((f.lower(), t.lower()) for t, f in _FIELD.findall(found.group(2)))
                        self.layouts.setdefault(found.group(1).lower(), fields)

    def field(self, type_name: str | None, name: str) -> tuple[int, str]:
        """(index, type) of a component."""
        for i, (field_name, field_type) in enumerate(self.layouts.get(type_name or "", ())):
            if field_name == name.lower():
                return i, field_type
        raise Unresolvable(f"no component '{name}' in {type_name or 'this data'}")

    def default(self, type_name: str) -> Any:
        """The value RAPID gives a VAR declared without one: zeros, FALSE, empty strings."""
        if type_name in _SCALARS:
            return _SCALARS[type_name]
        if type_name not in self.layouts:
            raise Unresolvable(f"no default value known for {type_name}")
        return [self.default(t) for _, t in self.layouts[type_name]]


# -- what the programs can change ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Param:
    name: str  # upper case
    type: str  # lower case
    mode: str  # "" (a copy), "VAR", "PERS" or "INOUT" (the caller's data itself)
    optional: bool


_PARAM = re.compile(r"^(?:(VAR|PERS|INOUT)\s+)?([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*(\{[^}]*\})?$", re.IGNORECASE)


def parse_params(raw: str) -> list[list[Param]] | None:
    """A routine's parameters, each a list of alternatives (`\\switch On | switch Off`); None if unreadable."""
    out: list[list[Param]] = []
    for part in split_params(raw):
        optional = part.startswith("\\")
        group = []
        for alternative in part.lstrip("\\").split("|"):
            match = _PARAM.match(alternative.strip())
            if match is None:
                return None
            mode, type_name, name, _dims = match.groups()
            group.append(Param(name.upper(), type_name.lower(), (mode or "").upper(), optional))
        out.append(group)
    return out


# Instructions and functions that only read their arguments. Any other one may change what it is
# given (SearchL writes its point, MToolTCPCalib its tool, StrToVal its value...), so what it is
# given counts as changed.
READ_ONLY_PROCS = frozenset({
    "TPWRITE", "TPERASE", "ERRWRITE", "SETDO", "SETGO", "SETAO", "PULSEDO", "SET", "RESET", "INVERTDO",
    "WAITDI", "WAITDO", "WAITGI", "WAITGO", "WAITAI", "WAITAO", "WAITUNTIL", "WAITTIME", "STOP", "EXIT",
    "EXITCYCLE", "BREAK", "CONFL", "CONFJ", "SINGAREA", "ACCSET", "VELSET", "PATHACCLIM", "STOPMOVE",
    "STARTMOVE", "CLEARPATH", "TPSHOW", "UISHOW", "RETURN", "GRIPLOAD", "CIRPATHMODE", "CLKRESET", "CLKSTART",
    "CLKSTOP",
    # moves with a process: they read their point, tool and work object like MoveL
    "TRIGGL", "TRIGGJ", "TRIGGC", "MOVELDO", "MOVEJDO", "MOVECDO", "MOVELAO", "MOVEJAO", "MOVECAO", "MOVELGO",
    "MOVEJGO", "MOVECGO", "MOVELSYNC", "MOVEJSYNC", "MOVECSYNC", "MOVEEXTJ",
})  # fmt: skip
# Instructions that change one of their arguments only, by position among the positional ones: a search
# its search point, a trigger set-up its triggdata.
WRITES_ONLY = {
    "SEARCHL": 1, "SEARCHJ": 1, "SEARCHC": 1,
    "TRIGGIO": 0, "TRIGGEQUIP": 0, "TRIGGINT": 0, "TRIGGSPEED": 0, "TRIGGCHECKIO": 0, "TRIGGRAMPAO": 0,
}  # fmt: skip
PURE_FUNCTIONS = frozenset({
    "OFFS", "RELTOOL", "POSEMULT", "POSEINV", "POSEVECT", "ORIENTZYX", "EULERZYX", "NORIENT", "DEFFRAME",
    "DEFDFRAME", "CROBT", "CJOINTT", "CPOS", "CTOOL", "CWOBJ", "CALCROBT", "CALCJOINTT", "ABS", "SQRT", "SIN",
    "COS", "TAN", "ASIN", "ACOS", "ATAN", "ATAN2", "ROUND", "TRUNC", "EXP", "POW", "VALTOSTR", "NUMTOSTR",
    "STRLEN", "STRPART", "STRFIND", "STRMATCH", "STRMEMB", "STRORDER", "STRMAP", "DOUTPUT", "DINPUT",
    "GINPUT", "GOUTPUT", "AINPUT", "AOUTPUT", "TESTDI", "PRESENT", "DIM", "OPMODE", "RUNMODE", "ROBOS",
    "CLKREAD", "GETTIME", "CDATE", "CTIME", "VECTMAGN", "DOTPROD", "CROSSPROD", "MIRPOS", "DISTANCE",
    "UIMESSAGEBOX", "UINUMENTRY", "UINUMTUNE", "UIALPHAENTRY", "UILISTVIEW", "ISFILE", "ISPERS", "ISVAR",
})  # fmt: skip
_READS_ROBOT = frozenset({"CROBT", "CJOINTT", "CPOS", "CTOOL", "CWOBJ", "CALCROBT", "CALCJOINTT"})
_NOT_DATA = frozenset({"LABEL", "GOTO", "RAISE", "RETRY", "TRYNEXT", "SYNTAX_ERROR"})
_IDENT = re.compile(r"[A-Za-z_]\w*")


def path_of(expr: n.Expr | None) -> tuple[str, ...] | None:
    """('TGRIP', 'TFRAME', 'TRANS') for tGrip.tframe.trans; an array element is '{}'. None: not data."""
    parts: list[str] = []
    while isinstance(expr, n.Component | n.Index):
        parts.append(expr.field.upper() if isinstance(expr, n.Component) else "{}")
        expr = expr.base
    if not isinstance(expr, n.Name):
        return None
    return (expr.name.upper(), *reversed(parts))


def _overlap(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    """Whether writing one of the two changes the other: one is a part of the other."""
    return all(x == y or "{}" in (x, y) for x, y in zip(a, b, strict=False))


@dataclass
class Written:
    """Every piece of data the programs can change, with where: one place each is enough to say why."""

    places: dict[str, list[tuple[tuple[str, ...], str]]] = field(default_factory=lambda: defaultdict(list))
    # SetDataVal with a name computed at run time: any data of that type may change (lower-case type -> where);
    # `everything` when not even the type is known.
    types: dict[str, str] = field(default_factory=dict)
    everything: str = ""

    def add(self, path: tuple[str, ...] | None, where: str) -> None:
        if path is not None:
            self.places[path[0]].append((path, where))

    def where(self, path: tuple[str, ...], type_name: str | None = None) -> str | None:
        """Where the programs change this data (or a part of it, or the data it is part of); None: nowhere.
        `type_name`: the data's type, for the instructions that change data by its type and a computed name."""
        if self.everything:
            return self.everything
        if type_name in self.types:
            return self.types[type_name]
        for written, where in self.places.get(path[0], ()):
            if _overlap(written, path):
                return where
        return None

    @classmethod
    def of(cls, modules: Iterable[n.Module]) -> "Written":
        """What the programs of these modules can change: give every task of a backup, a PERS is shared."""
        modules = list(modules)
        written = cls()
        calls = Calls(modules)
        declared = {d.name.upper() for m in modules for d in m.declarations}

        def changed_args(name: str, args: tuple[n.Arg, ...], where: str, builtin_safe: frozenset[str]) -> None:
            for value in calls.changed(name, args, builtin_safe):
                written.add(path_of(value), where)

        def expressions(stmt: n.Stmt, where: str) -> None:
            for call in _function_calls(stmt):
                changed_args(call.name, call.args, where, PURE_FUNCTIONS)

        def by_name(stmt: n.ProcCall, where: str, local_types: dict[str, str]) -> None:
            """SetDataVal / SetAllDataVal: data named by a string, of the type of the value given."""
            positional = [a.value for a in stmt.args if a.name is None]
            first, value = (positional[0], positional[-1]) if len(positional) >= 2 else (None, None)
            if stmt.name.upper() == "SETDATAVAL" and isinstance(first, n.String):
                written.add((first.value.upper(),), where)
                return
            type_name = first.value.lower() if stmt.name.upper() == "SETALLDATAVAL" and isinstance(first, n.String) else None
            if type_name is None and isinstance(value, n.Name):
                type_name = local_types.get(value.name.upper()) or types.get(value.name.upper())
            if type_name is None:
                written.everything = f"{stmt.name} in {where} can change any data"
            else:
                written.types.setdefault(type_name, f"{stmt.name} in {where} can change any {type_name}")

        def statements(stmts: Iterable[n.Stmt], place: str, local_types: dict[str, str]) -> None:
            for stmt in walk_statements(stmts):
                where = f"{place} l.{stmt.span.line}"
                if isinstance(stmt, n.Assign):
                    written.add(path_of(stmt.target), where)
                elif isinstance(stmt, n.ProcCall):
                    if stmt.name.upper() in ("SETDATAVAL", "SETALLDATAVAL"):
                        by_name(stmt, where, local_types)
                    changed_args(stmt.name, stmt.args, where, READ_ONLY_PROCS)
                elif isinstance(stmt, n.Unsupported) and stmt.kind not in _NOT_DATA:
                    raw(stmt.raw, where)
                expressions(stmt, where)

        def raw(text: str, where: str) -> None:
            """RAPID CrossArm does not read (late binding, CONNECT...): every data it names may change."""
            for name in set(_IDENT.findall(text)):
                if name.upper() in declared:
                    written.add((name.upper(),), where)

        types = {d.name.upper(): d.type_name.lower() for m in modules for d in m.declarations}
        for module in modules:
            for routine in module.routines:
                place = f"{module.name}.{routine.name}"
                local_types = {p.name: p.type for g in parse_params(routine.params) or [] for p in g}
                local_types |= {s.name.upper(): s.type_name.lower() for s in routine.body if isinstance(s, n.DataDecl)}
                statements(routine.body, place, local_types)
                for handler in routine.handlers:
                    stmts = handler_body(handler)
                    if stmts is None:
                        raw(handler.raw, f"{place} l.{handler.span.line}")
                    else:
                        statements(stmts, place, local_types)
        return written


class Effects:
    """What running some statements can change in the routine being converted: its data, and whether
    they may also change the module's (a call to a routine, code CrossArm does not read)."""

    def __init__(self, modules: Iterable[n.Module]) -> None:
        self.calls = Calls(modules)

    def of(self, stmts: Iterable[n.Stmt]) -> tuple[set[str], bool]:
        """(upper-case names of the data they may change, whether they may change any module data)."""
        names: set[str] = set()
        anything = False
        for stmt in walk_statements(stmts):
            if isinstance(stmt, n.Assign) and (path := path_of(stmt.target)):
                names.add(path[0])
            elif isinstance(stmt, n.For):
                names.add(stmt.var.upper())
            elif isinstance(stmt, n.ProcCall):
                if stmt.name.upper() not in READ_ONLY_PROCS:
                    anything = anything or stmt.name.upper() not in WRITES_ONLY
                    names |= self._roots(self.calls.changed(stmt.name, stmt.args, READ_ONLY_PROCS))
            elif isinstance(stmt, n.Unsupported) and stmt.kind not in ("RAISE", "RETRY", "TRYNEXT"):
                anything = True  # a label (jumped to), CONNECT, late binding...: not followed
            for call in _function_calls(stmt):
                if call.name.upper() in self.calls.routines:
                    anything = True  # a FUNC can change module data
                names |= self._roots(self.calls.changed(call.name, call.args, PURE_FUNCTIONS))
        return names, anything

    @staticmethod
    def _roots(values: Iterable[n.Expr]) -> set[str]:
        return {path[0] for value in values if (path := path_of(value))}


class Calls:
    """Which of its arguments a call may change.

    A routine of the backup changes an argument only through a VAR, PERS or INOUT parameter, and only
    if it does change that parameter: assigns it, or passes it on to a call that may change it. A
    routine that only reads a PERS tooldata parameter leaves the tool alone. Any other instruction or
    function may change what it is given, but those known to only read it."""

    def __init__(self, modules: Iterable[n.Module]) -> None:
        self.routines = {r.name.upper(): r for m in modules for r in m.routines}
        self.groups = {name: parse_params(r.params) for name, r in self.routines.items()}
        self._changes: dict[str, frozenset[str] | None] = {}

    def changed(self, name: str, args: tuple[n.Arg, ...], read_only: frozenset[str]) -> list[n.Expr]:
        """The arguments this call may change."""
        key = name.upper()
        values = [a.value for a in args if a.value is not None]
        if key not in self.routines:
            if key in WRITES_ONLY:
                positional = [a.value for a in args if a.name is None and a.value is not None]
                index = WRITES_ONLY[key]
                return positional[index : index + 1]
            return [] if key in read_only else values
        groups = self.groups[key]
        if groups is None:  # its parameter list is not read: anything given may be changed
            return values
        changes = self.changes(key)

        def may(param: Param) -> bool:
            return bool(param.mode) and (changes is None or param.name in changes)

        required = [g[0] for g in groups if not g[0].optional]
        optional = {p.name: p for g in groups if g[0].optional for p in g}
        out = []
        for i, arg in enumerate(a for a in args if a.name is None):
            if arg.value is not None and (i >= len(required) or may(required[i])):
                out.append(arg.value)
        for arg in (a for a in args if a.name is not None):
            param = optional.get(arg.name.upper())
            if arg.value is not None and (param is None or may(param)):
                out.append(arg.value)
        return out

    def changes(self, key: str) -> frozenset[str] | None:
        """The VAR / PERS / INOUT parameters a routine of the backup changes; None when that is not told."""
        if key in self._changes:
            return self._changes[key]
        self._changes[key] = None  # a routine calling itself back while this is worked out: it may change any
        groups = self.groups[key]
        if groups is None:
            return None
        routine = self.routines[key]
        params = {p.name for g in groups for p in g if p.mode}
        found: set[str] = set()
        stmts = list(walk_statements(routine.body))
        for handler in routine.handlers:
            body = handler_body(handler)
            if body is None:
                found |= {w.upper() for w in _IDENT.findall(handler.raw)} & params
            else:
                stmts += walk_statements(body)
        for stmt in stmts:
            changed: list[n.Expr] = []
            if isinstance(stmt, n.Assign):
                changed.append(stmt.target)
            elif isinstance(stmt, n.ProcCall):
                changed += self.changed(stmt.name, stmt.args, READ_ONLY_PROCS)
            elif isinstance(stmt, n.Unsupported) and stmt.kind not in _NOT_DATA:
                found |= {w.upper() for w in _IDENT.findall(stmt.raw)} & params
            for call in _function_calls(stmt):
                changed += self.changed(call.name, call.args, PURE_FUNCTIONS)
            found |= {path[0] for value in changed if (path := path_of(value))} & params
        self._changes[key] = frozenset(found)
        return self._changes[key]


def _function_calls(obj: Any) -> Iterable[n.FuncCall]:
    """Every function call inside a statement or an expression (not inside nested statements)."""
    stack = [obj]
    while stack:
        item = stack.pop()
        if isinstance(item, n.FuncCall):
            yield item
        if isinstance(item, tuple):
            stack.extend(item)
        elif hasattr(item, "__slots__") and not isinstance(item, n.Span):
            for name in item.__slots__:
                value = getattr(item, name, None)
                if isinstance(value, n.IfBranch):
                    stack.append(value.condition)
                elif isinstance(value, tuple) and value and isinstance(value[0], n.IfBranch):
                    stack.extend(b.condition for b in value)
                elif name not in ("body", "else_body", "cases", "default") and not isinstance(
                    value, str | int | float | bool | n.Span | type(None)
                ):
                    stack.append(value)


# -- values ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Typed:
    """A value (float, bool, str, or nested lists in the data's component order) and its RAPID type."""

    value: Any
    type: str | None  # lower case; None for an aggregate whose type the context gives
    dims: int = 0  # array dimensions left


@dataclass(frozen=True)
class Unknown:
    """A routine's data whose value depends on the run: why, completing "'pTmp' ...", and whether it was
    measured on the robot (a value derived from a calibration is one too)."""

    reason: str
    measured: bool = False

    def error(self, name: str) -> Unresolvable:
        return (MeasuredAtRunTime if self.measured else Unresolvable)(f"'{name}' {self.reason}")


UNKNOWN = Unknown("is set at run time before this point")

Scope = Callable[[str], "Typed | Unknown | None"]  # upper-case name -> value, Unknown, or None: not the routine's

PREDEFINED = {
    "TOOL0": Typed([True, [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]], [0.001, [0.0, 0.0, 0.001], [1.0, 0.0, 0.0, 0.0],
                                                                        0.0, 0.0, 0.0]], "tooldata"),
    "WOBJ0": Typed([False, True, "", [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]]],
                   "wobjdata"),
    "LOAD0": Typed([0.001, [0.0, 0.0, 0.001], [1.0, 0.0, 0.0, 0.0], 0.0, 0.0, 0.0], "loaddata"),
    **{name: Typed(predefined_value(name), "speeddata") for name in PREDEFINED_SPEEDS},
    **{name: Typed(predefined_value(name), "zonedata") for name in (*PREDEFINED_ZONES, "FINE")},
}  # fmt: skip


def to_pose(value: Any) -> Pose:
    """A RAPID pose ([[x, y, z], [q1, q2, q3, q4]]) as a Pose; an orientation that is not a unit quaternion is refused."""
    try:
        (x, y, z), q = value
        q = unit_quaternion(q, "a pose")
    except (TypeError, ValueError) as exc:
        raise Unresolvable("not a pose") from exc
    norm = math.sqrt(sum(c * c for c in q))
    return Pose((float(x), float(y), float(z)), tuple(c / norm for c in q))  # type: ignore[arg-type]


def from_pose(pose: Pose) -> list:
    return [list(pose.pos), list(pose.rot)]


def _vector(value: Any) -> tuple[float, float, float]:
    x, y, z = value
    return float(x), float(y), float(z)


def _unit(v: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(c * c for c in v))
    if length < 1e-9:
        raise Unresolvable("the points do not define a frame (two of them coincide or all are on a line)")
    return (v[0] / length, v[1] / length, v[2] / length)


def _cross(a, b) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def def_frame(p1, p2, p3, origin: int) -> Pose:
    """RAPID DefFrame: x from p1 towards p2, p3 on the positive-y side of the xy plane; the origin at
    p1 (1), at p2 (2), or on the line p1-p2 where y passes through p3 (3)."""
    x = _unit(tuple(b - a for a, b in zip(p1, p2, strict=True)))  # type: ignore[arg-type]
    to3 = tuple(b - a for a, b in zip(p1, p3, strict=True))
    z = _unit(_cross(x, to3))
    y = _cross(z, x)
    if origin == 1:
        o = p1
    elif origin == 2:
        o = p2
    elif origin == 3:
        along = _dot(to3, x)
        o = tuple(a + along * c for a, c in zip(p1, x, strict=True))
    else:
        raise Unresolvable(f"DefFrame \\Origin:={origin}")
    matrix = tuple(tuple((x, y, z)[col][row] for col in range(3)) for row in range(3))
    return Pose(tuple(float(c) for c in o), matrix_to_quat(matrix))  # type: ignore[arg-type]


def _orient_zyx(z: float, y: float, x: float) -> list[float]:
    return list(matrix_to_quat(mat_mul(rot_z(z), mat_mul(rot_y(y), rot_x(x)))))


def _euler_zyx(axis: str, q) -> float:
    w, p, r = matrix_to_wpr(quat_to_matrix(to_pose([[0, 0, 0], q]).rot))
    return {"X": w, "Y": p, "Z": r}[axis]


def _round(value: float, decimals: float, trunc: bool) -> float:
    scale = 10 ** int(decimals)
    return (math.trunc(value * scale) if trunc else math.floor(value * scale + 0.5)) / scale


class Computer:
    """Evaluates RAPID expressions whose every input is fixed (see the module docstring)."""

    def __init__(self, modules: list[n.Module], symbols: Symbols, written: Written) -> None:
        self.symbols = symbols
        self.layouts = Layouts(modules)
        self.written = written
        self.functions = {r.name.upper(): r for m in modules for r in m.routines if r.kind == "FUNC"}
        self.scope: Scope = lambda name: None  # the routine being converted: its data, set by the converter
        self._frames: list[tuple[dict[str, Typed], set[str], str]] = []  # FUNC calls: data, switches given, name
        self._resolving: set[str] = set()

    # -- reading data ----------------------------------------------------------------------------

    def value(self, expr: n.Expr) -> Typed:
        match expr:
            case n.Number(value=value):
                return Typed(float(value), "num")
            case n.Bool(value=value):
                return Typed(value, "bool")
            case n.String(value=value):
                return Typed(value, "string")
            case n.Aggregate(items=items):
                return Typed([self.value(i).value for i in items], None)
            case n.UnaryOp(op="NOT", operand=operand):
                return Typed(not self._bool(operand), "bool")
            case n.UnaryOp(op=op, operand=operand):
                inner = self.value(operand)
                sign = -1.0 if op == "-" else 1.0
                if inner.type == "num":
                    return Typed(sign * inner.value, "num")
                if inner.type == "pos":
                    return Typed([sign * c for c in inner.value], "pos")
            case n.BinaryOp():
                return self._binary(expr)
            case n.Name() | n.Component() | n.Index():
                return self.read(expr)
            case n.FuncCall():
                return self.call(expr)
        raise Unresolvable(f"{_text(expr)} is not computed at conversion time")

    def number(self, expr: n.Expr) -> float:
        typed = self.value(expr)
        if typed.type not in ("num", "dnum", None) or isinstance(typed.value, bool | list | str):
            raise Unresolvable(f"{_text(expr)} is not a number")
        return float(typed.value)

    def _bool(self, expr: n.Expr) -> bool:
        typed = self.value(expr)
        if not isinstance(typed.value, bool):
            raise Unresolvable(f"{_text(expr)} is not a bool")
        return typed.value

    def read(self, expr: n.Expr) -> Typed:
        chain = path_of(expr)
        if chain is None:
            raise Unresolvable(f"{_text(expr)} is not computed at conversion time")
        root_expr = expr
        while isinstance(root_expr, n.Component | n.Index):
            root_expr = root_expr.base
        assert isinstance(root_expr, n.Name)
        root = self._root(root_expr.name, chain, _text(expr))
        return self._walk(root, expr)

    def _root(self, name: str, chain: tuple[str, ...], label: str) -> Typed:
        """The data a read starts from; `chain` is the part read (for what changes it), `label` its RAPID text."""
        key = name.upper()
        if self._frames:
            data = self._frames[-1][0]
            if key in data:
                return data[key]
        else:
            known = self.scope(key)
            if isinstance(known, Unknown):
                raise known.error(name)
            if isinstance(known, Typed):
                return known
        decl = self.symbols.get(name) if not self._frames else self.symbols.get_global(name)
        if decl is None:
            if key in PREDEFINED:
                return PREDEFINED[key]
            raise NotInBackup(name)
        if decl.storage != "CONST":
            where = self.written.where(chain, decl.type_name.lower())
            if where is not None:
                raise Unresolvable(f"'{label}' is changed by the programs ({where})")
        if decl.init is None:
            raise Unresolvable(f"'{name}' has no initial value (set at run time)")
        if key in self._resolving:
            raise Unresolvable(f"circular definition of '{name}'")
        self._resolving.add(key)
        frames, self._frames = self._frames, []  # a declaration sees module data only
        try:
            value = self.value(decl.init).value
        finally:
            self._frames = frames
            self._resolving.discard(key)
        return Typed(value, decl.type_name.lower(), len(decl.dims))

    def _walk(self, root: Typed, expr: n.Expr) -> Typed:
        steps: list[n.Component | n.Index] = []
        while isinstance(expr, n.Component | n.Index):
            steps.append(expr)
            expr = expr.base
        current = root
        for step in reversed(steps):
            current = self._step(current, step)
        return current

    def _step(self, current: Typed, step: n.Component | n.Index) -> Typed:
        if isinstance(step, n.Index):
            if current.dims < len(step.indices):
                raise Unresolvable("index on data that is not an array")
            value = current.value
            for index in step.indices:
                i = self.number(index)
                if not float(i).is_integer() or not 1 <= i <= len(value):
                    raise Unresolvable(f"index {i:g} out of range")
                value = value[int(i) - 1]
            return Typed(value, current.type, current.dims - len(step.indices))
        if current.dims:
            raise Unresolvable("component of a whole array")
        index, field_type = self.layouts.field(current.type, step.field)
        try:
            return Typed(current.value[index], field_type)
        except (TypeError, IndexError) as exc:
            raise Unresolvable(f"malformed {current.type}") from exc

    # -- operators -----------------------------------------------------------------------------------

    def _binary(self, expr: n.BinaryOp) -> Typed:
        op = expr.op
        if op in ("AND", "OR", "XOR"):
            a, b = self._bool(expr.left), self._bool(expr.right)
            return Typed({"AND": a and b, "OR": a or b, "XOR": a != b}[op], "bool")
        left, right = self.value(expr.left), self.value(expr.right)
        lt, rt = left.type or "num", right.type or "num"
        if op in ("=", "<>"):
            same = _equal(left.value, right.value)
            return Typed(same if op == "=" else not same, "bool")
        if lt == rt == "num":
            a, b = float(left.value), float(right.value)
            if op in ("<", ">", "<=", ">="):
                return Typed({"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op], "bool")
            if op in ("/", "DIV", "MOD") and b == 0:
                raise Unresolvable("division by zero")
            results = {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else 0.0,
                       "DIV": float(math.trunc(a / b)) if b else 0.0, "MOD": math.fmod(a, b) if b else 0.0}  # fmt: skip
            if op in results:
                return Typed(results[op], "num")
        if lt == rt == "pos" and op in ("+", "-"):
            sign = 1.0 if op == "+" else -1.0
            return Typed([a + sign * b for a, b in zip(left.value, right.value, strict=True)], "pos")
        if {lt, rt} == {"pos", "num"} and op == "*":
            vector, scale = (left.value, right.value) if lt == "pos" else (right.value, left.value)
            return Typed([c * float(scale) for c in vector], "pos")
        if lt == "pos" and rt == "num" and op == "/" and right.value:
            return Typed([c / float(right.value) for c in left.value], "pos")
        raise Unresolvable(f"{lt} {op} {rt} is not computed at conversion time")

    # -- functions -------------------------------------------------------------------------------------

    def call(self, call: n.FuncCall) -> Typed:
        key = call.name.upper()
        if key in self.functions:
            return self._user_function(self.functions[key], call)
        if key in _READS_ROBOT:
            raise MeasuredAtRunTime(f"{call.name}() reads the robot's position when the program runs")
        positional = [a.value for a in call.args if a.name is None and a.value is not None]
        options = {a.name.upper(): a.value for a in call.args if a.name is not None}
        if key == "PRESENT":
            return Typed(self._present(positional), "bool")
        builtin = _BUILTINS.get(key)
        if builtin is None:
            raise Unresolvable(f"{call.name}() is not computed at conversion time")
        try:
            return builtin(self, positional, options)
        except (TypeError, ValueError, IndexError, ZeroDivisionError) as exc:
            raise Unresolvable(f"{call.name}(): {exc}") from exc

    def _present(self, positional: list[n.Expr]) -> bool:
        if not self._frames or len(positional) != 1 or not isinstance(positional[0], n.Name):
            raise Unresolvable("Present() outside a function of the backup")
        data, switches, _ = self._frames[-1]
        key = positional[0].name.upper()
        return key in switches or key in data

    def _user_function(self, routine: n.Routine, call: n.FuncCall) -> Typed:
        """A FUNC of the backup, run on fixed values: it may only compute (no instruction, no change to other data)."""
        if len(self._frames) > 20:
            raise Unresolvable(f"{routine.name}() calls itself too deep")
        groups = parse_params(routine.params)
        if groups is None:
            raise Unresolvable(f"{routine.name}(): parameter list not read")
        data: dict[str, Typed] = {}
        switches: set[str] = set()
        modes: dict[str, str] = {}
        required = [g[0] for g in groups if not g[0].optional]
        optional = {p.name: p for g in groups if g[0].optional for p in g}
        given = [a for a in call.args if a.name is None]
        if len(given) != len(required):
            raise Unresolvable(f"{routine.name}() takes {len(required)} arguments, {len(given)} given")
        for param, arg in zip(required, given, strict=True):
            data[param.name] = self._argument(arg, param)
            modes[param.name] = param.mode
        for arg in (a for a in call.args if a.name is not None):
            param = optional.get(arg.name.upper())
            if param is None or arg.conditional:
                raise Unresolvable(f"{routine.name}(): argument \\{arg.name} not computed")
            if arg.value is None:
                switches.add(param.name)
            else:
                data[param.name] = self._argument(arg, param)
            modes[param.name] = param.mode
        self._frames.append((data, switches, routine.name))
        try:
            result = self._run(routine.body, data, modes, routine.name)
        finally:
            self._frames.pop()
        if result is None:
            raise Unresolvable(f"{routine.name}() ends without RETURN")
        return Typed(result.value, (routine.return_type or "").lower() or result.type, result.dims)

    def _argument(self, arg: n.Arg, param: Param) -> Typed:
        assert arg.value is not None
        typed = self.value(arg.value)
        return Typed(typed.value, param.type, typed.dims)

    def _run(self, stmts: tuple[n.Stmt, ...], data: dict[str, Typed], modes: dict[str, str], function: str) -> Typed | None:
        for stmt in stmts:
            match stmt:
                case n.Comment():
                    continue
                case n.DataDecl(name=name, type_name=type_name, init=init, dims=dims):
                    if init is not None:
                        data[name.upper()] = Typed(self.value(init).value, type_name.lower(), len(dims))
                    elif dims:
                        raise Unresolvable(f"{function}(): local array {name}")
                    else:
                        data[name.upper()] = Typed(self.layouts.default(type_name.lower()), type_name.lower())
                case n.Assign(target=target, value=value):
                    chain = path_of(target)
                    if chain is None or chain[0] not in data:
                        raise Unresolvable(f"{function}() changes data of the program ({_text(target)})")
                    if modes.get(chain[0]):
                        raise Unresolvable(f"{function}() changes its caller's data ({_text(target)})")
                    data[chain[0]] = self.assign_into(data[chain[0]], target, self.value(value))
                case n.If(branches=branches, else_body=else_body):
                    body = else_body
                    for branch in branches:
                        if self._bool(branch.condition):
                            body = branch.body
                            break
                    result = self._run(body, data, modes, function)
                    if result is not None:
                        return result
                case n.Test(subject=subject, cases=cases, default=default):
                    chosen = self.value(subject).value
                    body = next((c.body for c in cases if any(self.value(v).value == chosen for v in c.values)),
                                default or ())  # fmt: skip
                    result = self._run(body, data, modes, function)
                    if result is not None:
                        return result
                case n.Return(value=value) if value is not None:
                    return self.value(value)
                case _:
                    raise Unresolvable(f"{function}() does more than compute ({_statement(stmt)})")
        return None

    # -- writing data --------------------------------------------------------------------------------

    def assign_into(self, root: Typed, target: n.Expr, value: Typed) -> Typed:
        """The root data after `target := value`, target being the root or one of its components."""
        steps: list[n.Component | n.Index] = []
        expr = target
        while isinstance(expr, n.Component | n.Index):
            steps.append(expr)
            expr = expr.base
        if not steps:
            return Typed(value.value, root.type, root.dims)
        new = copy.deepcopy(root.value)
        holder, current = None, Typed(new, root.type, root.dims)
        slot: int | None = None
        for step in reversed(steps):
            if isinstance(step, n.Index):
                if len(step.indices) != 1:
                    raise Unresolvable("element of a multi-dimensional array")
                i = self.number(step.indices[0])
                if not float(i).is_integer() or not 1 <= i <= len(current.value):
                    raise Unresolvable(f"index {i:g} out of range")
                holder, slot = current.value, int(i) - 1
                current = Typed(current.value[slot], current.type, current.dims - 1)
            else:
                index, field_type = self.layouts.field(current.type, step.field)
                holder, slot = current.value, index
                current = Typed(current.value[index], field_type)
        assert holder is not None and slot is not None
        holder[slot] = copy.deepcopy(value.value)
        return Typed(new, root.type, root.dims)

    def robot_reads(self, expr: n.Expr) -> str:
        """'CRobT() reads' / 'CalibFrame() reads (CRobT)': whether the value reads the robot, directly or in a
        FUNC of the backup it calls. A calibration: said as such, whatever else is not known about it."""
        seen: set[str] = set()

        def search(obj: Any) -> str:
            for call in _function_calls(obj):
                key = call.name.upper()
                if key in _READS_ROBOT:
                    return f"{call.name}()"
                if key in self.functions and key not in seen:
                    seen.add(key)
                    for stmt in walk_statements(self.functions[key].body):
                        inner = search(stmt)
                        if inner:
                            return f"{self.functions[key].name}() ({inner})"
            return ""

        found = search(expr)
        return f"{found} reads" if found else ""

    def assigned(self, assign: n.Assign) -> tuple[str, Typed]:
        """(upper-case root name, its whole value after the assignment); Unresolvable if an input is not fixed."""
        chain = path_of(assign.target)
        if chain is None:
            raise Unresolvable(f"{_text(assign.target)} is not data")
        root_expr = assign.target
        while isinstance(root_expr, n.Component | n.Index):
            root_expr = root_expr.base
        assert isinstance(root_expr, n.Name)
        reads = self.robot_reads(assign.value)
        if reads:
            raise MeasuredAtRunTime(f"{reads} the robot's position when the program runs")
        for name in _names(assign.value):  # a value measured before: that is the reason, whatever else is not fixed
            known = self.scope(name)
            if isinstance(known, Unknown) and known.measured:
                raise known.error(name)
        decl = self.symbols.get(root_expr.name)
        known = self.scope(chain[0])
        if isinstance(known, Unknown) and len(chain) > 1:  # the rest of it is not known either
            raise known.error(root_expr.name)
        if decl is None and not isinstance(known, Typed):
            raise NotInBackup(root_expr.name)
        new = self.value(assign.value)
        if len(chain) == 1:
            type_name = decl.type_name.lower() if decl else known.type  # type: ignore[union-attr]
            return chain[0], Typed(new.value, type_name, len(decl.dims) if decl else known.dims)  # type: ignore[union-attr]
        root = known if isinstance(known, Typed) else self._all_but(root_expr.name, chain)
        return chain[0], self.assign_into(root, assign.target, new)

    def _all_but(self, name: str, chain: tuple[str, ...]) -> Typed:
        """A data's value, read component by component, but for the part being assigned: what the programs do to
        that part does not matter, the rest must be fixed."""
        decl = self.symbols.get(name)
        assert decl is not None
        if "{}" in chain:
            raise Unresolvable(f"'{name}': element of an array assigned")
        type_name = decl.type_name.lower()
        target = Typed(self.layouts.default(type_name), type_name)

        def fill(value: list, type_name: str, prefix: tuple[str, ...]) -> None:
            for i, (field_name, field_type) in enumerate(self.layouts.layouts.get(type_name, ())):
                path = (*prefix, field_name.upper())
                if path == chain:
                    continue
                if chain[: len(path)] == path:
                    fill(value[i], field_type, path)
                else:
                    value[i] = self._read_path(name, path, field_type)

        fill(target.value, type_name, (chain[0],))
        return target

    def _read_path(self, name: str, path: tuple[str, ...], type_name: str) -> Any:
        expr: n.Expr = n.Name(n.Span(0, 0), name)
        for part in path[1:]:
            expr = n.Component(n.Span(0, 0), expr, part.lower())
        return self.read(expr).value


# RAPID's math functions: TP has none of them (no power, no root, no angle function).
_MATH = frozenset({"ABS", "SQRT", "SIN", "COS", "TAN", "ASIN", "ACOS", "ATAN", "ATAN2", "EXP", "POW", "ROUND",
                   "TRUNC"})  # fmt: skip


def fixed_math(computer: "Computer", expr: n.Expr) -> tuple[float, list[str]] | None:
    """A number calculated with RAPID's math functions (Pow, Sqrt, Sin...) from data no program changes: its value,
    worked out once as TP cannot, and the PERS it read at their saved value (to say so). None when the expression
    calls another function, or none; Unresolvable, with why, when it reads something that can change."""
    calls = _calls(expr)
    if not calls or any(c.name.upper() not in _MATH or c.name.upper() in computer.functions for c in calls):
        return None
    value = computer.number(expr)
    pers = [name for name in dict.fromkeys(_names(expr))  # not the routine's own value at this point: the saved one
            if not isinstance(computer.scope(name.upper()), Typed)
            and (decl := computer.symbols.get(name)) is not None and decl.storage == "PERS"]  # fmt: skip
    return value, pers


def _calls(expr: Any) -> list[n.FuncCall]:
    """The function calls in an expression, outer ones first."""
    found = [expr] if isinstance(expr, n.FuncCall) else []
    if isinstance(expr, tuple):
        return [call for item in expr for call in _calls(item)]
    if hasattr(expr, "__slots__") and not isinstance(expr, n.Span | str):
        found += [call for slot in expr.__slots__ for call in _calls(getattr(expr, slot, None))]
    return found


def _names(expr: Any) -> list[str]:
    """The data an expression reads, as written, in order."""
    if isinstance(expr, n.Name):
        return [expr.name]
    if isinstance(expr, tuple):
        return [name for item in expr for name in _names(item)]
    if hasattr(expr, "__slots__") and not isinstance(expr, n.Span | str):
        return [name for slot in expr.__slots__ for name in _names(getattr(expr, slot, None))]
    return []


def _equal(a: Any, b: Any) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float | int) and isinstance(b, float | int) and not isinstance(a, bool):
        return abs(float(a) - float(b)) < 1e-9
    return a == b


def _text(expr: n.Expr) -> str:
    from crossarm.rapid.to_pseudo import format_expr

    text = format_expr(expr)
    return text if len(text) <= 60 else text[:57] + "..."


def _statement(stmt: n.Stmt) -> str:
    if isinstance(stmt, n.ProcCall):
        return stmt.name
    return getattr(stmt, "kind", None) and str(stmt.kind) or type(stmt).__name__  # type: ignore[attr-defined]


# -- RAPID functions -------------------------------------------------------------------------------


def _pose_arg(c: Computer, expr: n.Expr) -> Pose:
    return to_pose(c.value(expr).value)


def _robtarget_arg(c: Computer, expr: n.Expr) -> list:
    value = c.value(expr).value
    if not (isinstance(value, list) and len(value) == 4):
        raise Unresolvable(f"{_text(expr)} is not a robtarget")
    to_pose(value[:2])
    return value


def _offs(c: Computer, args: list, options: dict) -> Typed:
    point = copy.deepcopy(_robtarget_arg(c, args[0]))
    dx, dy, dz = (c.number(e) for e in args[1:4])
    point[0] = [float(point[0][0]) + dx, float(point[0][1]) + dy, float(point[0][2]) + dz]
    return Typed(point, "robtarget")


def _reltool(c: Computer, args: list, options: dict) -> Typed:
    point = copy.deepcopy(_robtarget_arg(c, args[0]))
    dx, dy, dz = (c.number(e) for e in args[1:4])
    rx, ry, rz = (c.number(options[k]) if options.get(k) is not None else 0.0 for k in ("RX", "RY", "RZ"))
    moved = to_pose(point[:2]).rel_tool(dx, dy, dz, rx, ry, rz)
    point[0], point[1] = list(moved.pos), list(moved.rot)
    return Typed(point, "robtarget")


def _def_frame(c: Computer, args: list, options: dict) -> Typed:
    p1, p2, p3 = (_vector(_robtarget_arg(c, e)[0]) for e in args[:3])
    origin = c.number(options["ORIGIN"]) if options.get("ORIGIN") is not None else 1.0
    return Typed(from_pose(def_frame(p1, p2, p3, int(origin))), "pose")


def _euler(c: Computer, args: list, options: dict) -> Typed:
    axes = [k for k in ("X", "Y", "Z") if k in options]
    if len(axes) != 1:
        raise Unresolvable("EulerZYX needs one of \\X, \\Y, \\Z")
    return Typed(_euler_zyx(axes[0], c.value(args[0]).value), "num")


def _math(fn: Callable[..., float]) -> Callable[[Computer, list, dict], Typed]:
    return lambda c, args, options: Typed(float(fn(*(c.number(e) for e in args))), "num")


def _rounding(trunc: bool) -> Callable[[Computer, list, dict], Typed]:
    def run(c: Computer, args: list, options: dict) -> Typed:
        decimals = c.number(options["DEC"]) if options.get("DEC") is not None else 0.0
        return Typed(_round(c.number(args[0]), decimals, trunc), "num")

    return run


_DEG = math.radians
_BUILTINS: dict[str, Callable[[Computer, list, dict], Typed]] = {
    "OFFS": _offs,
    "RELTOOL": _reltool,
    "POSEMULT": lambda c, a, o: Typed(from_pose(_pose_arg(c, a[0]).compose(_pose_arg(c, a[1]))), "pose"),
    "POSEINV": lambda c, a, o: Typed(from_pose(_pose_arg(c, a[0]).inverse()), "pose"),
    "POSEVECT": lambda c, a, o: Typed(list(_pose_arg(c, a[0]).compose(Pose(_vector(c.value(a[1]).value),
                                                                           (1.0, 0.0, 0.0, 0.0))).pos), "pos"),
    "ORIENTZYX": lambda c, a, o: Typed(_orient_zyx(*(c.number(e) for e in a[:3])), "orient"),
    "NORIENT": lambda c, a, o: Typed(list(to_pose([[0, 0, 0], c.value(a[0]).value]).rot), "orient"),
    "EULERZYX": _euler,
    "DEFFRAME": _def_frame,
    "ABS": _math(abs),
    "SQRT": _math(math.sqrt),
    "SIN": _math(lambda x: math.sin(_DEG(x))),
    "COS": _math(lambda x: math.cos(_DEG(x))),
    "TAN": _math(lambda x: math.tan(_DEG(x))),
    "ASIN": _math(lambda x: math.degrees(math.asin(x))),
    "ACOS": _math(lambda x: math.degrees(math.acos(x))),
    "ATAN": _math(lambda x: math.degrees(math.atan(x))),
    "ATAN2": _math(lambda y, x: math.degrees(math.atan2(y, x))),
    "EXP": _math(math.exp),
    "POW": _math(math.pow),
    "ROUND": _rounding(False),
    "TRUNC": _rounding(True),
}  # fmt: skip


__all__ = [
    "UNKNOWN",
    "Computer",
    "Effects",
    "Layouts",
    "MeasuredAtRunTime",
    "Typed",
    "Unknown",
    "Written",
    "def_frame",
    "fixed_math",
    "from_pose",
    "measured_reason",
    "parse_params",
    "path_of",
    "to_pose",
]  # fmt: skip
