# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Points worked out at run time, kept in position registers.

A VAR robtarget some assignment gives a value only known when the program runs (the robot's position, an
input, data the programs change, a routine's own data or parameter) is kept in a position register PR[k]:
every assignment sets it, every read reads it, in whatever routine (find_runtime_points). The register is
numbered by the mapping key `point_registers` ('ROUTINE.NAME' for a routine's own, 'NAME' for module data).

Measured on ROBOGUIDE (point and pose probes): `PR[k]=P[j]` keeps the values and configuration whatever
frames are selected; a move to a register is made in the frames selected when it runs; `PR[k,3]=PR[k,3]+40`
is Offs in z; `PR[k]=LPOS` reads the TCP in the frames selected.

A VAR jointtarget set to CJointT() is kept the same way, in a joint position register (`PR[k]=JPOS`); a
MoveAbsJ to it is `J PR[k]`, and its axes are worked out from the FANUC joints with the conventions
MoveAbsJ is written with, inverted (configuration.fanuc_joints): rax_1 = J1, rax_2 = J2, rax_3 = -(J3+J2)
(FANUC's J3 is the forearm's angle to the horizontal), rax_4 = -J4, rax_5 = -J5, rax_6 = 180-J6 (-J6 with
the tool's pin on +x). Measured on ROBOGUIDE (joints probe, RobotStudio the same): `PR[k]=JPOS` holds the
joints of the robot, `PR[k,i]` reads one in degrees, `IF (PR[k,2]>30)` compares one, and `J PR[k]` goes
back to them whatever tool is selected (a joint P of another tool is refused, INTP-253). External axes
stay TODO: CrossArm writes none.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING

from crossarm.convert.arguments import Signature
from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.compute import MeasuredAtRunTime, Typed, Unknown, path_of
from crossarm.convert.configuration import TOOL_PIN_DEFAULT
from crossarm.convert.tp_numbers import fmt_number, operand
from crossarm.convert.values import RobTarget, Unresolvable
from crossarm.convert.wrappers import parameters
from crossarm.geometry import mat_mul, matrix_to_quat, matrix_to_wpr, quat_to_matrix, rot_x, rot_y, rot_z
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr
from crossarm.rapid.walk import walk_statements

if TYPE_CHECKING:
    from crossarm.convert.translate import Converter

KEPT = ("robtarget", "jointtarget")  # the data a position register can keep
# ABB axis of a jointtarget -> its FANUC joint (jointtarget.robax.rax_i)
AXES = {("ROBAX", f"RAX_{i}"): i for i in range(1, 7)}

# Functions whose value is only known at run time: the robot's position, inputs
RUNTIME_FUNCTIONS = frozenset({"CROBT", "CJOINTT", "CPOS", "CTOOL", "CWOBJ", "DINPUT", "DOUTPUT", "GINPUT", "GOUTPUT",
                                "AINPUT", "AOUTPUT", "TESTDI", "READNUM", "CLKREAD"})  # fmt: skip


def expr_nodes(node: object) -> Iterable[object]:
    """Every node of an expression, itself first."""
    yield node
    if isinstance(node, tuple | list):
        for item in node:
            yield from expr_nodes(item)
    elif hasattr(node, "__dataclass_fields__") and not isinstance(node, n.Span):
        for name in node.__dataclass_fields__:
            yield from expr_nodes(getattr(node, name))


def find_runtime_points(c: "Converter", routines: list[n.Routine]) -> dict[str, str]:
    """The robtargets and jointtargets (not arrays, not CONST) some assignment gives a value only known at run
    time, and their type: kept in a position register, which every assignment sets and every read reads, in
    whatever routine.

    An assignment is known at run time only when it reads what changes then: data the programs change, a
    routine's own data or parameter, an input or the robot's position (CRobT...), or such a point. One
    reading the point itself and fixed data (`pTmp.trans.z:=pTmp.trans.z-100`) is worked out where it is,
    as before: the point stays a P of each move."""
    assignments: list[tuple[str, n.Assign, set[str], set[str]]] = []  # key, statement, own names, params
    kinds: dict[str, str] = {}
    for routine in routines:
        own = {d.name.upper(): d for d in routine.body if isinstance(d, n.DataDecl)}
        read = parameters(routine.params)
        params = set(read[0]) | set(read[1]) if read else set()
        params |= {s.var.upper() for s in walk_statements(routine.body) if isinstance(s, n.For)}  # its counters
        for stmt in walk_statements(routine.body):
            if not isinstance(stmt, n.Assign) or not (path := path_of(stmt.target)):
                continue
            decl = own.get(path[0]) or c.symbols.get_global(path[0])
            if decl is None or decl.type_name.lower() not in KEPT or decl.dims or decl.storage == "CONST":
                continue
            key = f"{routine.name}.{decl.name}".upper() if path[0] in own else path[0]
            assignments.append((key, stmt, set(own), params))
            kinds[key] = decl.type_name.lower()
    found: set[str] = set()
    for routine in routines:  # passed to a routine changing it (VAR robtarget): read back into its register
        own = {d.name.upper(): d for d in routine.body if isinstance(d, n.DataDecl)}
        for stmt in walk_statements(routine.body):
            searched = [a.value for a in stmt.args if a.name is None][1:2] \
                if isinstance(stmt, n.ProcCall) and stmt.name.upper() == "SEARCHL" else []  # fmt: skip
            if searched and isinstance(searched[0], n.Name):  # the point SearchL finds
                decl = own.get(searched[0].name.upper()) or c.symbols.get_global(searched[0].name)
                if decl is not None and decl.type_name.lower() == "robtarget" and not decl.dims and decl.storage != "CONST":
                    found.add(f"{routine.name}.{decl.name}".upper() if decl.name.upper() in own else decl.name.upper())
            layout = c.signatures.get(stmt.name.upper()) if isinstance(stmt, n.ProcCall) else None
            if not isinstance(layout, Signature) or not layout.points_changed:
                continue
            for slot, value in zip(layout.required, [a.value for a in stmt.args if a.name is None], strict=False):
                if not (slot.kind == "robtarget" and slot.by_reference and slot.key in layout.points_changed
                        and isinstance(value, n.Name)):  # fmt: skip
                    continue
                decl = own.get(value.name.upper()) or c.symbols.get_global(value.name)
                if decl is not None and decl.type_name.lower() == "robtarget" and not decl.dims and decl.storage != "CONST":
                    found.add(f"{routine.name}.{decl.name}".upper() if value.name.upper() in own else decl.name.upper())
    while True:  # a point reading a point known at run time is one too
        more = {key for key, stmt, own, params in assignments
                if key not in found and at_run_time(c, stmt, own, params, found)}  # fmt: skip
        if not more:
            return {key: kinds.get(key, "robtarget") for key in found}
        found |= more


def at_run_time(c: "Converter", stmt: n.Assign, own: set[str], params: set[str], found: set[str]) -> bool:
    """Whether an assignment to a point reads what is only known at run time (_runtime_points)."""
    target = path_of(stmt.target)[0]  # type: ignore[index]
    try:
        c.computer.value(stmt.value)
        return False
    except Unresolvable:
        pass
    for node in expr_nodes(stmt.value):
        if isinstance(node, n.FuncCall) and node.name.upper() in RUNTIME_FUNCTIONS:
            return True
        if not isinstance(node, n.Name) or node.name.upper() == target:
            continue
        key = node.name.upper()
        decl = c.symbols.get_global(node.name)
        if key in own or key in params or key in found:
            return True
        if decl is not None and decl.storage != "CONST" and c.computer.written.where((key,)) is not None:
            return True
    return False


class RuntimePoints:
    """The routine translator's part that writes the points kept in position registers (mixed into it)."""

    def runtime_key(self, name: str) -> str | None:
        """The key of the position register a point worked out at run time is kept in; None for another data. A
        robtarget parameter the routine changes is one, in the register the caller passes it in."""
        if self.args and self.args.kind(name) == "robtarget" and name.upper() in self.args.points_changed:
            slot = next(s for s in self.args.slots if s.key == name.upper())
            return f"{self.routine.name}.{slot.name}"  # as the caller names it (point_argument)
        if name.upper() in self.local_names or self.c.symbols.is_local(name):
            key = f"{self.routine.name}.{name}".upper()
        else:
            key = name.upper()
        return key if key in self.c.runtime_points else None

    def runtime_set(self, name: str) -> None:
        """A point kept in a register must have been set: not when its last assignment was left TODO."""
        unset = self.known.get(f"{name.upper()}#UNSET")
        if isinstance(unset, Unknown):
            raise Untranslatable(str(unset.error(name)), Blocker.CALIBRATION if unset.measured else Blocker.RUNTIME_POSITION)

    def runtime_axis(self, expr: n.Expr) -> str | None:
        """`PR[k,3]` for `pDepose.trans.z`, pDepose kept in PR[k]; None for anything else."""
        path = path_of(expr) if isinstance(expr, n.Component) else None
        if not path or not (key := self.runtime_key(path[0])):
            return None
        root = expr
        while isinstance(root, n.Component | n.Index):
            root = root.base
        self.runtime_set(root.name if isinstance(root, n.Name) else path[0])
        if self.c.runtime_points.get(key) == "jointtarget":  # rax_1 and rax_2 read as they are, the others worked out
            reading = self.joint_axis(expr)
            if reading is None or not reading.startswith("PR["):
                raise Untranslatable(f"{format_expr(expr)}: TP works this axis out of the FANUC joints on a line of"
                                     " its own, not here", Blocker.RUNTIME_POSITION)  # fmt: skip
            return reading
        axis = {("TRANS", "X"): 1, ("TRANS", "Y"): 2, ("TRANS", "Z"): 3}.get(path[1:])
        if axis is None:
            raise Untranslatable(f"{format_expr(expr)}: of a point kept in a position register, TP reads x, y and z",
                                 Blocker.RUNTIME_POSITION)  # fmt: skip
        return f"{self.c.point_register(key)[:-1]},{axis}]"

    def runtime_assign(self, a: n.Assign, key: str, path: tuple[str, ...]) -> None:
        """A point worked out at run time, in its position register PR[k]: a value known now (PR[k]=P[j]); a copy of
        another one, Offs() of it (component by component); RelTool() of one whose orientation is known now
        (the displacement turned by it, the new W, P, R written); CRobT() (PR[k]=LPOS, in the frames
        selected); one of its x, y, z (PR[k,3]=...)."""
        register = self.c.point_register(key)
        name = path_of(a.target)[0] if path_of(a.target) else key  # type: ignore[index]
        turn = f"{name}#ROT"
        if len(path) > 1 and self.c.runtime_points.get(key) == "jointtarget":
            raise Untranslatable(f"{format_expr(a.target)} set: CrossArm reads the axes of a jointtarget kept in a position"
                                 " register (CJointT), but does not write them", Blocker.RUNTIME_POSITION)  # fmt: skip
        if len(path) > 1:
            axis = self.runtime_axis(a.target)
            self.emit(f"{axis}={self.arithmetic(a.value)}")
            return
        if self.c.runtime_points.get(key) == "jointtarget":
            self.robot_joints(a, register)
        else:
            self._runtime_value(a, register, name, turn)
        self.known.pop(f"{name}#UNSET", None)  # set whole: readable again

    def _runtime_value(self, a: n.Assign, register: str, name: str, turn: str) -> None:
        """The whole of a point kept in a register (runtime_assign)."""
        value = a.value
        if isinstance(value, n.FuncCall) and value.name.upper() == "CROBT":
            self.robot_position(value)
            self.emit(f"{register}=LPOS")
            self.known[turn] = Unknown(f"is measured on the robot at l.{a.span.line}", measured=True)
            return
        if isinstance(value, n.FuncCall) and value.name.upper() == "RELTOOL":
            orientation = self.turned(value, register)
            if orientation is not None:
                self.known[turn] = orientation
                return
        try:
            target = self.c.evaluator.robtarget(value)
        except Unresolvable:
            target = None
        if target is not None:
            self.emit(f"{register}={self.known_point(value, target, a.span.line)}")
            self.known[turn] = Typed(tuple(target.pose.rot), "orient")
            return
        offs = isinstance(value, n.FuncCall) and value.name.upper() == "OFFS" and len(value.args) == 4 \
            and all(arg.name is None and arg.value is not None for arg in value.args)  # fmt: skip
        base = value.args[0].value if offs else value  # type: ignore[union-attr]
        try:  # Offs() of a point known now, by what is only known at run time: the pallet's corner and the cell
            fixed = self.c.evaluator.robtarget(base) if offs else None  # type: ignore[arg-type]
        except Unresolvable:
            fixed = None
        if fixed is not None:
            self.emit(f"{register}={self.known_point(base, fixed, a.span.line)}")  # type: ignore[arg-type]
            self.add_offsets(register, [arg.value for arg in value.args[1:]])  # type: ignore[union-attr, misc]
            self.known[turn] = Typed(tuple(fixed.pose.rot), "orient")
            return
        if self.passed_point(value, "CROSSARM.POINT", into=register) is None:
            raise Untranslatable(f"point {format_expr(a.target)} set to {format_expr(value)}: a point kept in a position"
                                 " register is set to a point, Offs() or RelTool() of one, or CRobT()",
                                 Blocker.RUNTIME_POSITION)  # fmt: skip
        source = path_of(base) if isinstance(base, n.Name) else None  # Offs keeps the orientation
        self.known[turn] = self.known.get(f"{source[0]}#ROT", Unknown("has an orientation known at run time only")) \
            if source else Unknown("has an orientation known at run time only")  # fmt: skip

    def robot_joints(self, a: n.Assign, register: str) -> None:
        """The whole of a jointtarget kept in a register: CJointT() (PR[k]=JPOS, the robot's joints, whatever
        frames are selected), or a copy of another one kept in a register."""
        value = a.value
        if isinstance(value, n.FuncCall) and value.name.upper() == "CJOINTT" and not value.args:
            self.emit(f"{register}=JPOS")
            return
        if isinstance(value, n.Name) and (source := self.runtime_key(value.name)) is not None \
                and self.c.runtime_points.get(source) == "jointtarget":  # fmt: skip
            self.runtime_set(value.name)
            if self.c.point_register(source) != register:
                self.emit(f"{register}={self.c.point_register(source)}")
            return
        what = f"position {format_expr(a.target)}"
        try:
            self.c.computer.value(value)
        except MeasuredAtRunTime as exc:
            raise Untranslatable(self.measured_why(a, "jointtarget", what, exc), Blocker.CALIBRATION) from exc
        except Unresolvable:
            pass
        raise Untranslatable(f"{what} set to {format_expr(value)}: a jointtarget kept in a position register is set to"
                             " CJointT() or to another one kept in a register", Blocker.RUNTIME_POSITION)  # fmt: skip

    def joint_axis(self, expr: n.Expr, slot: int = 1, operation: bool = False) -> str | None:
        """The ABB axis `j.robax.rax_i` of a jointtarget kept in PR[k], worked out from the FANUC joints JPOS read
        (module docstring): `PR[k,1]`, `PR[k,2]` as they are; the others in R[Calc<slot>], rax_3 added up there
        first. `operation`: the right side of an assignment, which can be one operation (`PR[k,4]*(-1)`,
        `180-PR[k,6]`). None for anything but an axis of such a jointtarget."""
        path = path_of(expr) if isinstance(expr, n.Component) else None
        if not path or not (key := self.runtime_key(path[0])) or self.c.runtime_points.get(key) != "jointtarget":
            return None
        self.runtime_set(path[0])
        axis = AXES.get(path[1:])
        if axis is None:
            raise Untranslatable(f"{format_expr(expr)}: of a jointtarget kept in a position register, CrossArm reads the"
                                 " robot's six axes (it writes no external axis)", Blocker.RUNTIME_POSITION)  # fmt: skip
        joints = self.c.point_register(key)[:-1]
        if not self.c.config.joint_mapping:  # MoveAbsJ copies the ABB axes as they are: so is a reading
            self.c.warn_once("joint-reads", self.name, expr.span.line, "joint_mapping is off: the axes of a jointtarget"
                             " read on the robot (CJointT) are the FANUC joints as they are", Blocker.AXIS_CONVENTION)  # fmt: skip
            return f"{joints},{axis}]"
        six = "180-J6" if self.c.config.tool_pin == TOOL_PIN_DEFAULT else "-J6"
        self.c.warn_once("joint-reads", self.name, expr.span.line, "the axes of a jointtarget read on the robot"
                         " (CJointT) are worked out from the FANUC joints with the measured axis conventions (rax_3 ="
                         f" -(J3+J2), rax_4 = -J4, rax_5 = -J5, rax_6 = {six}): the values the ABB gives in the same"
                         " posture", Blocker.AXIS_CONVENTION)  # fmt: skip
        if axis in (1, 2):
            return f"{joints},{axis}]"
        if self.stepless:
            raise Untranslatable(f"{format_expr(expr)} in a condition read again and again: TP works the ABB axis out"
                                 " of the FANUC joints on a line of its own", Blocker.CONDITION)  # fmt: skip
        register = self.c.written_register(f"Calc{slot}", key=f"CROSSARM.CALC{slot}")
        if axis == 3:
            self.emit(f"{register}={joints},3]+{joints},2]")
            right = f"{register}*(-1)"
        elif axis == 6 and self.c.config.tool_pin == TOOL_PIN_DEFAULT:
            right = f"180-{joints},6]"
        else:
            right = f"{joints},{axis}]*(-1)"
        if operation:
            return right
        self.emit(f"{register}={right}")
        return register

    def joints_kept(self, expr: n.Expr) -> str | None:
        """PR[k] for MoveAbsJ to a jointtarget kept in a position register (`J PR[k]`: the joints JPOS read,
        whatever tool is selected); None for another one."""
        key = self.runtime_key(expr.name) if isinstance(expr, n.Name) else None
        if key is None or self.c.runtime_points.get(key) != "jointtarget":
            return None
        self.runtime_set(expr.name)  # type: ignore[union-attr]
        return self.c.point_register(key)

    def known_point(self, expr: n.Expr, value: RobTarget, line: int) -> str:
        """P[j] for a point known now that a position register is set from (`PR[k]=P[j]` keeps its values and
        configuration, whatever frames are selected and the P is recorded in: ROBOGUIDE). Recorded in the frames
        selected, else those of the routine's first move (its configuration worked out for them), else UF 0, UT 1."""
        uf, ut = self.active_uf, self.active_ut
        if uf is None or ut is None:
            first = next((s for s in walk_statements(self.routine.body) if isinstance(s, n.Move)), None)
            try:
                if first is not None and self.given_frames(first) == (None, None):
                    uf = uf or self.c.selection("UF", self.c.frame_number("UF", first.wobj, self.name, line))
                    ut = ut or self.c.selection("UT", self.c.frame_number("UT", first.tool, self.name, line))
            except Untranslatable:
                pass
        return self.point(expr, value, uf or (0, None), ut or (1, None), line)

    def turned(self, call: n.FuncCall, register: str) -> Typed | None:
        """RelTool() of a point kept in a register whose orientation is known now: the displacement turned into the
        work object's axes and added component by component, the new orientation written as W, P, R; the
        orientation it leaves. None when RelTool() is of a point known now (worked out whole)."""
        positional = [a.value for a in call.args if a.name is None]
        options = {(a.name or "").upper(): a.value for a in call.args if a.name is not None}
        if len(positional) != 4 or not isinstance(positional[0], n.Name) or not set(options) <= {"RX", "RY", "RZ"}:
            return None
        source = self.runtime_key(positional[0].name)
        if source is None:
            return None
        orientation = self.known.get(f"{positional[0].name.upper()}#ROT")
        if not isinstance(orientation, Typed):
            raise Untranslatable(f"RelTool of {positional[0].name}, whose orientation is only known at run time: TP"
                                 " cannot turn a position register", Blocker.RUNTIME_POSITION)  # fmt: skip
        try:
            turns = {axis: self.c.evaluator.constant_number(v) for axis, v in options.items() if v is not None}
        except Unresolvable as exc:
            raise Untranslatable(f"RelTool rotation only known at run time ({exc})", Blocker.RUNTIME_POSITION) from exc
        m = quat_to_matrix(orientation.value)
        from_register = self.c.point_register(source)
        if from_register != register:
            self.emit(f"{register}={from_register}")
        span = call.span
        for i in range(3):  # the displacement along the tool's axes, in the work object's
            terms = [(m[i][j], positional[j + 1]) for j in range(3) if abs(m[i][j]) > 1e-9]
            try:
                step = sum(c * self.c.evaluator.constant_number(d) for c, d in terms)  # type: ignore[arg-type]
                if abs(step) > 1e-9:
                    sign, size = ("-", -step) if step < 0 else ("+", step)
                    self.emit(f"{register[:-1]},{i + 1}]={register[:-1]},{i + 1}]{sign}{fmt_number(round(size, 3))}")
                continue
            except Unresolvable:
                pass
            expr: n.Expr | None = None
            for c, d in terms:
                term = n.BinaryOp(span, "*", n.Number(span, round(c, 6), str(round(c, 6))), d)  # type: ignore[arg-type]
                expr = term if expr is None else n.BinaryOp(span, "+", expr, term)
            if expr is not None:
                self.emit(f"{register[:-1]},{i + 1}]={register[:-1]},{i + 1}]+{self.single(expr)}")
        if turns:
            rotation = mat_mul(m, mat_mul(rot_x(turns.get("RX", 0.0)), mat_mul(rot_y(turns.get("RY", 0.0)),
                                                                           rot_z(turns.get("RZ", 0.0)))))  # fmt: skip
            for axis, angle in zip((4, 5, 6), matrix_to_wpr(rotation), strict=True):
                self.emit(f"{register[:-1]},{axis}]={operand(fmt_number(round(angle, 3) + 0.0))}")
            orientation = Typed(tuple(matrix_to_quat(rotation)), "orient")
        return orientation

    def robot_position(self, call: n.FuncCall) -> None:
        """CRobT() as LPOS: the TCP in the frames selected, the ones \\Tool and \\WObj name selected first (a
        selection does not move the robot). Without them RAPID reads in the active tool and work object, those
        of the last move made, whatever the program: the frames that move selected on the FANUC, and still
        selected when LPOS reads (a selection lasts until another one)."""
        wanted = {"UF": self.active_uf, "UT": self.active_ut}
        for arg in call.args:
            kind = {"TOOL": "UT", "WOBJ": "UF"}.get((arg.name or "").upper())
            if kind is None:
                raise Untranslatable(f"CRobT option \\{arg.name}: LPOS reads the TCP in the frames selected",
                                     Blocker.CALIBRATION)  # fmt: skip
            wanted[kind] = self.c.selection(kind, self.c.frame_number(kind, arg.value, self.name, call.span.line))
        for kind, name, active in (("UF", "UFRAME", self.active_uf), ("UT", "UTOOL", self.active_ut)):
            if wanted[kind] is not None and wanted[kind] != active:
                number, bank = wanted[kind]  # type: ignore[misc]
                if bank is not None:
                    self.emit(f"{name}[{number}]=PR[{bank}]")
                self.emit(f"{name}_NUM={number}")
        self.active_uf, self.active_ut = wanted["UF"], wanted["UT"]
