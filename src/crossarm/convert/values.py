# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Static evaluation of RAPID data: turn AST expressions into numbers and poses.

The converter only needs values known at conversion time: literals, CONST/PERS
declarations with an initial value, predefined data (v100, z10, fine, tool0...)
and Offs()/RelTool() applied to those. Anything that depends on the program
state at run time raises Unresolvable with a human-readable reason.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from crossarm.geometry import Pose
from crossarm.rapid import nodes as n
from crossarm.rapid.walk import base_name, module_statements


class Unresolvable(Exception):
    """The value is not known at conversion time."""


class NotInBackup(Unresolvable):
    """No module of the backup declares this data: a system module, an option or another task does, or it is
    not data at all (a signal, a name of RAPID). The translator tells which (Converter: not_declared)."""

    def __init__(self, name: str) -> None:
        super().__init__(f"'{name}' is not declared in the converted modules")
        self.name = name


def unit_quaternion(q: Any, what: str) -> tuple[float, float, float, float]:
    """An orientation a move or a frame can use: a unit quaternion (Pose normalises the rounding of a backup).

    [0,0,0,0] is the value of a robtarget or tool nobody has set yet: a PERS the program fills in
    before using it. There is no rotation to convert, and a value worked out from it would be wrong.
    """
    q = tuple(float(c) for c in q)
    if len(q) != 4:
        raise ValueError(f"{len(q)} components in an orientation")
    norm = math.sqrt(sum(c * c for c in q))
    if abs(norm - 1) > 0.01:
        unset = ": a value only set at run time" if norm < 1e-9 else ""
        shown = ", ".join(f"{c:g}" for c in q)
        raise Unresolvable(f"the orientation of {what}, [{shown}], is not a unit quaternion{unset}")
    return q  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class RobTarget:
    pose: Pose
    conf: tuple[int, int, int, int]  # cf1, cf4, cf6, cfx


@dataclass(frozen=True, slots=True)
class JointTarget:
    joints: tuple[float, ...]  # robax, degrees


@dataclass(frozen=True, slots=True)
class Speed:
    v_tcp: float  # mm/s
    name: str


@dataclass(frozen=True, slots=True)
class Zone:
    fine: bool
    radius_mm: float
    name: str


@dataclass(frozen=True, slots=True)
class Load:
    """RAPID loaddata: what the robot carries, as RAPID gives it (kg, mm, kg.m2).

    FANUC keeps this in PAYLOAD schedules, apart from the tool frame. A robot running
    with the wrong payload has its collision detection and its dynamics wrong, so the
    report lists it for every tool rather than let it disappear.
    """

    mass: float  # kg
    cog: tuple[float, float, float]  # centre of gravity, mm, in the flange (tool0) frame
    aom: tuple[float, float, float, float]  # axes of moment: orientation of the inertia axes
    inertia: tuple[float, float, float]  # ix, iy, iz, kg.m2 about the aom axes


@dataclass(frozen=True, slots=True)
class Frame:
    """Tool (tframe) or work object (uframe * oframe)."""

    pose: Pose
    robhold: bool
    name: str
    load: Load | None = None  # tools only: their loaddata
    # PERS the programs change at run time (calibration...), read at the value saved in the backup.
    saved: tuple[str, ...] = ()


# RAPID predefined speeddata (v_tcp in mm/s) and zonedata (pzone_tcp in mm).
PREDEFINED_SPEEDS = {
    f"V{v}": float(v)
    for v in (5, 10, 20, 30, 40, 50, 60, 80, 100, 150, 200, 300, 400, 500, 600, 800,
              1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000, 7000)
}  # fmt: skip
PREDEFINED_ZONES = {
    "Z0": 0.3, "Z1": 1, "Z5": 5, "Z10": 10, "Z15": 15, "Z20": 20, "Z30": 30, "Z40": 40,
    "Z50": 50, "Z60": 60, "Z80": 80, "Z100": 100, "Z150": 150, "Z200": 200,
}  # fmt: skip


def predefined_value(name: str) -> list | None:
    """A predefined speeddata or zonedata as data, for data declared with it (`CONST zonedata zPick:=z50`).
    CrossArm reads a speed's v_tcp and a zone's finep and pzone_tcp; the other components are RAPID's
    usual ones (v_ori 500, v_leax 5000, v_reax 1000; 1.5 and 0.15 times the TCP zone)."""
    key = name.upper()
    if key in PREDEFINED_SPEEDS:
        return [PREDEFINED_SPEEDS[key], 500.0, 5000.0, 1000.0]
    if key == "FINE":
        return [True, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    if key in PREDEFINED_ZONES:
        r = float(PREDEFINED_ZONES[key])
        return [False, r, 1.5 * r, 1.5 * r, 0.15 * r, 1.5 * r, 0.15 * r]
    return None
_IDENTITY = Pose((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))


class Symbols:
    """Data declarations visible from a routine: routine locals shadow module data."""

    def __init__(self, declarations: dict[str, n.DataDecl], assigned: frozenset[str] = frozenset()) -> None:
        self._globals = declarations
        self._locals: dict[str, n.DataDecl] = {}
        # Names that appear on the left of ':=' anywhere: a VAR among them is not a constant.
        self._assigned = assigned

    @classmethod
    def from_modules(cls, modules: list[n.Module]) -> "Symbols":
        table: dict[str, n.DataDecl] = {}
        assigned: set[str] = set()
        for module in modules:
            for decl in module.declarations:
                table.setdefault(decl.name.upper(), decl)
            for stmt in module_statements(module):
                if isinstance(stmt, n.Assign) and (name := base_name(stmt.target)):
                    assigned.add(name.upper())
        return cls(table, frozenset(assigned))

    def is_assigned(self, name: str) -> bool:
        return name.upper() in self._assigned

    def enter_routine(self, routine: n.Routine) -> None:
        self._locals = {s.name.upper(): s for s in routine.body if isinstance(s, n.DataDecl)}

    def is_local(self, name: str) -> bool:
        return name.upper() in self._locals

    def get(self, name: str) -> n.DataDecl | None:
        key = name.upper()
        return self._locals.get(key) or self._globals.get(key)

    def get_global(self, name: str) -> n.DataDecl | None:
        """Module data only: what a FUNC sees, whatever routine calls it."""
        return self._globals.get(name.upper())

    def type_of(self, name: str) -> str | None:
        decl = self.get(name)
        return decl.type_name.lower() if decl else None


class Evaluator:
    def __init__(self, symbols: Symbols) -> None:
        self.symbols = symbols
        self._resolving: set[str] = set()
        self._constants_only = False
        self._saved: list[str] | None = None  # frames: PERS changed at run time read at their saved value
        # The routine being converted: the value its data has at this point, when the converter knows it
        # (crossarm.convert.compute), else None; raises Unresolvable when it depends on the path taken.
        self.known: Callable[[str], Any] | None = None
        # A field of a record data (crossarm.convert.records): its value where it is one, None for any other
        # expression; raises Unresolvable when the programs change it.
        self.fields: Callable[[n.Expr], Any] | None = None

    # -- generic -----------------------------------------------------------

    def value(self, expr: n.Expr):
        """Number, bool, string or (nested) list of those."""
        match expr:
            case n.Number(value=value):
                return float(value)
            case n.Bool(value=value) | n.String(value=value):
                return value
            case n.Aggregate(items=items):
                return [self.value(i) for i in items]
            case n.UnaryOp(op="-", operand=operand):
                return -self.number(operand)
            case n.UnaryOp(op="+", operand=operand):
                return self.number(operand)
            case n.BinaryOp(op=op, left=left, right=right) if op in ("+", "-", "*", "/"):
                a, b = self.number(left), self.number(right)
                if op == "/" and b == 0:
                    raise Unresolvable("division by zero")
                return {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else 0.0}[op]
            case n.Name(name=name) if self.symbols.get(name) is None and predefined_value(name) is not None:
                return predefined_value(name)
            case n.Component() if self.fields is not None and (found := self.fields(expr)) is not None:
                return found
            case n.Name(name=name):
                # Constants only: a register stays a register, even when its value here is known.
                if self.known is not None and not self._constants_only:
                    found = self.known(name)
                    if found is not None:
                        return found
                init = self._initial_value(name)
                key = name.upper()
                self._resolving.add(key)
                try:
                    return self.value(init)
                finally:
                    self._resolving.discard(key)
            case n.FuncCall(name=fn, args=(n.Arg(name=None, value=n.Name(name=array)), n.Arg(name=None, value=k))) if (
                fn.upper() == "DIM" and (decl := self.symbols.get(array)) is not None and decl.dims
            ):  # the size of an array as declared: Dim(pSlot,1)
                axis = self.constant_number(k)
                if not (float(axis).is_integer() and 1 <= axis <= len(decl.dims)):
                    raise Unresolvable(f"{_short(expr)}: {array} has {len(decl.dims)} dimension(s)")
                return self.constant_number(decl.dims[int(axis) - 1])
            case n.Index(base=n.Name() as base, indices=indices):
                # An element at a fixed index (pSlot{2}): the index a CONST, the array as its name reads it.
                data = self.value(base)
                for index in indices:
                    i = self.constant_number(index)
                    if not (isinstance(data, list) and float(i).is_integer() and 1 <= i <= len(data)):
                        raise Unresolvable(f"index out of the array: {_short(expr)}")
                    data = data[int(i) - 1]
                return data
        raise Unresolvable(f"expression is not a constant: {_short(expr)}")

    def number(self, expr: n.Expr) -> float:
        value = self.value(expr)
        if isinstance(value, bool) or not isinstance(value, float):
            raise Unresolvable(f"not a number: {_short(expr)}")
        return value

    def constant_number(self, expr: n.Expr) -> float:
        """Like number(), but only CONST data count as known: VAR/PERS stay variables."""
        previous, self._constants_only = self._constants_only, True
        try:
            return self.number(expr)
        finally:
            self._constants_only = previous

    def _initial_value(self, name: str) -> n.Expr:
        decl = self.symbols.get(name)
        if decl is None:
            raise NotInBackup(name)
        if self._constants_only and decl.storage != "CONST":
            raise Unresolvable(f"'{name}' is a {decl.storage}, not a constant")
        if decl.init is None:
            raise Unresolvable(f"'{name}' has no initial value (set at run time)")
        if decl.storage != "CONST" and self.symbols.is_assigned(name):
            if self._saved is None or decl.storage != "PERS":
                raise Unresolvable(f"'{name}' is a {decl.storage} assigned at run time")
            if decl.name not in self._saved:
                self._saved.append(decl.name)
        key = name.upper()
        if key in self._resolving:
            raise Unresolvable(f"circular definition of '{name}'")
        return decl.init

    # -- typed data --------------------------------------------------------

    def robtarget(self, expr: n.Expr) -> RobTarget:
        if isinstance(expr, n.FuncCall):
            return self._pose_function(expr)
        if isinstance(expr, n.Name) and (t := self.symbols.type_of(expr.name)) not in (None, "robtarget"):
            raise Unresolvable(f"'{expr.name}' is a {t}, not a robtarget")
        data = self.value(expr)
        try:
            (x, y, z), q, conf, _extax = data
            q = unit_quaternion(q, _short(expr))
            return RobTarget(Pose((x, y, z), q), tuple(int(c) for c in conf))  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise Unresolvable(f"malformed robtarget: {_short(expr)}") from exc

    def jointtarget(self, expr: n.Expr) -> JointTarget:
        if isinstance(expr, n.Name) and (t := self.symbols.type_of(expr.name)) not in (None, "jointtarget"):
            raise Unresolvable(f"'{expr.name}' is a {t}, not a jointtarget")
        data = self.value(expr)
        try:
            robax, _extax = data
            return JointTarget(tuple(float(j) for j in robax))
        except (TypeError, ValueError) as exc:
            raise Unresolvable(f"malformed jointtarget: {_short(expr)}") from exc

    def speed(self, expr: n.Expr) -> Speed:
        if isinstance(expr, n.Name):
            if expr.name.upper() in PREDEFINED_SPEEDS and self.symbols.get(expr.name) is None:
                return Speed(PREDEFINED_SPEEDS[expr.name.upper()], expr.name)
            if expr.name.upper() == "VMAX":
                raise Unresolvable("vmax depends on the robot model")
        data = self.value(expr)
        try:
            return Speed(float(data[0]), _short(expr))
        except (TypeError, IndexError) as exc:
            raise Unresolvable(f"malformed speeddata: {_short(expr)}") from exc

    def zone(self, expr: n.Expr) -> Zone:
        if isinstance(expr, n.Name) and self.symbols.get(expr.name) is None:
            key = expr.name.upper()
            if key == "FINE":
                return Zone(True, 0.0, expr.name)
            if key in PREDEFINED_ZONES:
                return Zone(False, PREDEFINED_ZONES[key], expr.name)
        data = self.value(expr)
        try:  # [finep, pzone_tcp, pzone_ori, ...]
            return Zone(bool(data[0]), float(data[1]), _short(expr))
        except (TypeError, IndexError) as exc:
            raise Unresolvable(f"malformed zonedata: {_short(expr)}") from exc

    def _frame_value(self, expr: n.Expr) -> tuple[Any, tuple[str, ...]]:
        """A frame's value, and the PERS read at their saved value to get it.

        Tools and work objects are often calibrated by the programs themselves: a routine
        measures the tool and writes the PERS. The backup holds the last value written,
        which is the one the robot runs with and the one an integrator would copy, so it is
        used, and named, rather than leaving the frame blank. A VAR is reset at every start:
        its declared value means nothing then, so it stays unknown.
        """
        previous, self._saved = self._saved, []
        try:
            return self.value(expr), tuple(self._saved)
        finally:
            self._saved = previous

    def tool(self, expr: n.Expr) -> Frame:
        if isinstance(expr, n.Name) and expr.name.upper() == "TOOL0" and self.symbols.get("tool0") is None:
            return Frame(_IDENTITY, True, "tool0")
        data, saved = self._frame_value(expr)
        try:  # [robhold, [trans, rot], loaddata]
            robhold, ((x, y, z), q), load = data
            q = unit_quaternion(q, _short(expr))
            frame = Frame(Pose((x, y, z), q), bool(robhold), _short(expr), saved=saved)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise Unresolvable(f"malformed tooldata: {_short(expr)}") from exc
        try:  # loaddata: [mass, [cog], [aom], ix, iy, iz]
            mass, (cx, cy, cz), aom, ix, iy, iz = load
            try:
                aom = unit_quaternion(aom, "its load's axes of moment")
            except Unresolvable:
                if any((ix, iy, iz)):
                    raise ValueError("inertia about axes that are no rotation") from None
                aom = (1.0, 0.0, 0.0, 0.0)  # no inertia: its axes do not matter
            loaded = Load(float(mass), (cx, cy, cz), aom, (ix, iy, iz))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return frame  # a malformed load must not cost the tool frame
        return Frame(frame.pose, frame.robhold, frame.name, loaded, saved)

    def wobj(self, expr: n.Expr) -> Frame:
        if isinstance(expr, n.Name) and expr.name.upper() == "WOBJ0" and self.symbols.get("wobj0") is None:
            return Frame(_IDENTITY, False, "wobj0")
        data, saved = self._frame_value(expr)
        try:  # [robhold, ufprog, ufmec, uframe, oframe]
            robhold, _ufprog, _ufmec, ((ux, uy, uz), uq), ((ox, oy, oz), oq) = data
            uq, oq = unit_quaternion(uq, f"{_short(expr)}.uframe"), unit_quaternion(oq, f"{_short(expr)}.oframe")
            pose = Pose((ux, uy, uz), uq).compose(Pose((ox, oy, oz), oq))  # type: ignore[arg-type]
            return Frame(pose, bool(robhold), _short(expr), saved=saved)
        except (TypeError, ValueError) as exc:
            raise Unresolvable(f"malformed wobjdata: {_short(expr)}") from exc

    def _pose_function(self, call: n.FuncCall) -> RobTarget:
        name = call.name.upper()
        positional = [a.value for a in call.args if a.name is None and a.value is not None]
        options = {a.name.upper(): a.value for a in call.args if a.name is not None}
        if name == "OFFS" and len(positional) == 4 and not options:
            base = self.robtarget(positional[0])
            dx, dy, dz = (self.number(e) for e in positional[1:])
            return RobTarget(base.pose.offs(dx, dy, dz), base.conf)
        if name == "RELTOOL" and len(positional) == 4 and set(options) <= {"RX", "RY", "RZ"}:
            base = self.robtarget(positional[0])
            dx, dy, dz = (self.number(e) for e in positional[1:])
            rot = {k: self.number(v) for k, v in options.items() if v is not None}
            pose = base.pose.rel_tool(dx, dy, dz, rot.get("RX", 0.0), rot.get("RY", 0.0), rot.get("RZ", 0.0))
            return RobTarget(pose, base.conf)
        raise Unresolvable(f"function {call.name}() is evaluated at run time")


def _short(expr: n.Expr) -> str:
    from crossarm.rapid.to_pseudo import format_expr

    text = format_expr(expr)
    return text if len(text) <= 60 else text[:57] + "..."
