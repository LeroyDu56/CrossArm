# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Poses worked out at run time, kept in position registers and computed by KAREL (--karel).

With --karel, a VAR pose some assignment gives a value only known at run time is kept in a position register
PR[k], as a point is (crossarm.convert.runtime_points: same mapping key `point_registers`, 'ROUTINE.NAME' for
a routine's own, 'NAME' for module data). Every assignment sets the register:

    p3 := PoseMult(p1, p2);          CALL CA_POSEMULT(a,b,c)    PR[c] = PR[a] : PR[b], by KAREL (crossarm.karel)
    p2 := p1;                        PR[b]=PR[a]
    p1 := [[x, y, z], q];            PR[a,1]=x ... PR[a,6]=r    q known now, x, y, z any value TP computes

and a pose known now passed to PoseMult is written the same way into a register of CrossArm's own
(CROSSARM.POSE1, CROSSARM.POSE2). `p.trans.x` reads and writes PR[k,1], as for a point. Without --karel
nothing changes: such a pose stays a value TP cannot hold (TODO, position built at run time).

Measured on ROBOGUIDE V10.10 (tools/make_karel_probe.py): the six components written into a position register
never set (or cleared) make it a Cartesian one; written into one holding joints (`PR[k]=JPOS`), PR[k,1] is the
first joint: CrossArm keeps its poses in registers of their own. PR[c] holds PoseMult(PR[a], PR[b]) as RAPID
computes it; its configuration is PR[a]'s, which a pose does not use.
"""

from typing import TYPE_CHECKING

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.compute import Typed, Unknown, to_pose
from crossarm.convert.tp_numbers import fmt_number, operand
from crossarm.convert.values import Unresolvable
from crossarm.geometry import quat_to_wpr
from crossarm.karel import PROGRAMS
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr

if TYPE_CHECKING:
    from crossarm.convert.translate import ConversionResult, Converter

POSE = "pose"
SCRATCH = "CROSSARM.POSE"  # + 1 or 2: a pose known now that PoseMult is given, in a register of its own


def karel_call(c: "Converter", name: str, registers: list[str]) -> str:
    """`CALL CA_XXX(a,b,c)`: the library program `name` given the NUMBERS of position registers `PR[...]`."""
    if len(name) > c.config.program_name_max_length:
        raise Untranslatable(f"KAREL program {name}: longer than the {c.config.program_name_max_length} characters a"
                             " program name has on this controller", Blocker.RUNTIME_POSITION)  # fmt: skip
    assert name in PROGRAMS, name
    return f"CALL {name}({','.join(register[3:-1] for register in registers)})"


def karel_candidates(modules: list[n.Module], result: "ConversionResult") -> bool:
    """Whether --karel could convert some of the TODO: a pose data the programs may change (kept in a position
    register with --karel, crossarm.convert.karel_poses). The conversion is made again with it only then."""
    if not result.todo_count:
        return False
    declared = [d for m in modules for d in m.declarations] + [d for m in modules for r in m.routines for d in r.body
                                                       if isinstance(d, n.DataDecl)]  # fmt: skip
    return any(d.type_name.lower() == "pose" and d.storage != "CONST" and not d.dims for d in declared)


def karel_would(result: "ConversionResult", karel: "ConversionResult") -> int:
    """The TODO of `result` that `karel`, the same conversion with --karel, converts."""
    left = {(note.program, note.rapid_line) for note in karel.notes if note.kind == "TODO"}
    return sum(1 for note in result.notes if note.kind == "TODO" and (note.program, note.rapid_line) not in left)


class KarelPoses:
    """The routine translator's part that writes the poses kept in position registers (mixed into it)."""

    def pose_value(self, a: n.Assign, register: str) -> None:
        """The whole of a pose kept in a register (module docstring)."""
        value = a.value
        if isinstance(value, n.FuncCall) and value.name.upper() == "POSEMULT" \
                and "POSEMULT" not in self.c.computer.functions:  # fmt: skip
            operands = [arg.value for arg in value.args if arg.name is None and arg.value is not None]
            if len(operands) != 2 or len(value.args) != 2:
                raise Untranslatable(f"PoseMult with {len(value.args)} arguments", Blocker.RUNTIME_POSITION)
            left, right = (self.pose_register(expr, slot) for slot, expr in enumerate(operands, 1))
            self.emit(karel_call(self.c, "CA_POSEMULT", [left, right, register]))
            return
        if isinstance(value, n.Name) and (source := self.runtime_key(value.name)) is not None \
                and self.c.runtime_points.get(source) == POSE:  # fmt: skip
            self.pose_read(value, source)
            if self.c.point_register(source) != register:
                self.emit(f"{register}={self.c.point_register(source)}")
            return
        if self.pose_written(value, register):
            return
        raise Untranslatable(f"pose {format_expr(a.target)} set to {format_expr(value)}: a pose kept in a position"
                             " register is set to PoseMult() of poses, to another one, or to a value whose orientation"
                             " is known", Blocker.RUNTIME_POSITION)  # fmt: skip

    def pose_register(self, expr: n.Expr, slot: int) -> str:
        """The position register KAREL reads a pose from: its own when kept in one, else a register of CrossArm's
        own the pose known now is written into first."""
        if isinstance(expr, n.Name) and (key := self.runtime_key(expr.name)) is not None \
                and self.c.runtime_points.get(key) == POSE:  # fmt: skip
            self.pose_read(expr, key)
            return self.c.point_register(key)
        register = self.c.point_register(f"{SCRATCH}{slot}")
        if not self.pose_written(expr, register):
            raise Untranslatable(f"PoseMult of {format_expr(expr)}: KAREL is given poses kept in position registers"
                                 " or known now", Blocker.RUNTIME_POSITION)  # fmt: skip
        return register

    def pose_read(self, expr: n.Name, key: str) -> None:
        """A pose kept in a register, read: set by then. Module data declared with a value starts with it in RAPID,
        its register only once a program sets it: said once."""
        self.runtime_set(expr.name)
        decl = self.c.symbols.get_global(expr.name) if "." not in key else None
        if decl is not None and decl.init is not None:
            self.c.warn_once(f"pose-start|{key}", self.name, expr.span.line, f"pose {decl.name} starts at the value it is"
                             " declared with in RAPID, its position register once a program sets it: set the register"
                             " on the robot before the first run", Blocker.RUNTIME_POSITION)  # fmt: skip

    def pose_written(self, expr: n.Expr, register: str) -> bool:
        """Write a pose known now, or `[[x, y, z], q]` with q known now, into PR[k] component by component; False
        when it is neither."""
        try:
            known = self.c.computer.value(expr)
        except Unresolvable:
            known = None
        if isinstance(known, Typed) and not isinstance(known, Unknown):
            try:
                pose = to_pose(known.value)
            except Unresolvable:
                return False
            self.pose_components(register, [fmt_number(round(v, 3) + 0.0) for v in pose.pos], pose.rot)
            return True
        if not (isinstance(expr, n.Aggregate) and len(expr.items) == 2 and isinstance(expr.items[0], n.Aggregate)
                and len(expr.items[0].items) == 3):  # fmt: skip
            return False
        try:
            rot = to_pose([[0, 0, 0], self.c.computer.value(expr.items[1]).value]).rot
        except Unresolvable:
            return False
        self.pose_components(register, [self.arithmetic(item) for item in expr.items[0].items], rot)
        return True

    def pose_components(self, register: str, xyz: list[str], rot: tuple[float, ...]) -> None:
        base = register[:-1]
        for axis, text in enumerate(xyz, 1):
            self.emit(f"{base},{axis}]={operand(text)}")
        for axis, angle in zip((4, 5, 6), quat_to_wpr(rot), strict=True):  # type: ignore[arg-type]
            self.emit(f"{base},{axis}]={operand(fmt_number(round(angle, 3) + 0.0))}")
