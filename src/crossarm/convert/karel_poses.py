# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Poses and frames worked out at run time, kept in position registers and computed by KAREL (--karel).

With --karel, a VAR pose some assignment gives a value only known at run time is kept in a position register
PR[k], as a point is (crossarm.convert.runtime_points: same mapping key `point_registers`, 'ROUTINE.NAME' for
a routine's own, 'NAME' for module data). Every assignment sets the register:

    p3 := PoseMult(p1, p2);          CALL CA_POSEMULT(a,b,c)        PR[c] = PR[a] : PR[b]      (crossarm.karel)
    p2 := PoseInv(p1);               CALL CA_POSEINV(a,b)           PR[b] = INV(PR[a])
    p2 := DefFrame(q1, q2, q3 \\Origin:=3);  CALL CA_DEFFRAME(a,b,d,c,3)
    p2 := p1;                        PR[b]=PR[a]
    p1 := [[x, y, z], q];            PR[a,1]=x ... PR[a,6]=r        q known now, x, y, z any value TP computes

The operands of these functions are poses or points kept in registers, values known now (written into
registers of CrossArm's own, CROSSARM.POSE1, 2...), or these functions again (worked out first, each into
the next of those registers). A point kept in a register set to RelTool() of one whose orientation (or the
rotation) is only known at run time is `CALL CA_RELTOOL(a,b,dx,dy,dz,rx,ry,rz)`: the displacement and the
angles are constants or registers R[i].

A work object's uframe, or a tool's tframe, set to such a value (a calibration: DefFrame of points read on
the robot, a tool corrected by PoseMult) is worked out the same way into CROSSARM.FRAME, then loaded into
the frame the moves select: `UFRAME[n]=PR[k]` (`UTOOL[n]=PR[k]`), or into its bank register for a frame past
the controller's limit; the oframe, known now, is multiplied in first when it is not the identity. The
moves after it go to their points in the new frame; their configurations are those CrossArm worked out for
the frame as saved.

`p.trans.x` reads and writes PR[k,1], as for a point. Without --karel nothing changes: such a pose stays a
value TP cannot hold (TODO, position built at run time).

Measured on ROBOGUIDE V10.10 (tools/make_karel_probe.py, tools/make_karel_pose_probe.py): the six components
written into a position register never set (or cleared) make it a Cartesian one; written into one holding
joints (`PR[k]=JPOS`), PR[k,1] is the first joint: CrossArm keeps its poses in registers of their own.
PoseMult, PoseInv, RelTool (\\Rx \\Ry \\Rz together, angles past 180) and DefFrame (each \\Origin) land in the
register as RAPID computes them, within 0.001 mm; a CALL argument R[i] holding a whole or a real number is
taken as its value. The configuration of a result is its first operand's (RelTool keeps the point's, as
RAPID keeps robconf). `UFRAME[n]=PR[k]` and `UTOOL[n]=PR[k]` load the values exactly.
"""

import re
from typing import TYPE_CHECKING

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.compute import Typed, Unknown, first_hole, path_of, to_pose
from crossarm.convert.configuration import TOOL_PIN_DEFAULT
from crossarm.convert.tp_numbers import decimal, fmt_number, operand
from crossarm.convert.values import Unresolvable
from crossarm.fanuc.tp import Instruction
from crossarm.geometry import quat_to_wpr
from crossarm.karel import PROGRAMS
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr

if TYPE_CHECKING:
    from crossarm.convert.translate import ConversionResult, Converter

POSE = "pose"
SCRATCH = "CROSSARM.POSE"  # + 1, 2...: a pose known now, or worked out first, that KAREL is given
FRAME = "CROSSARM.FRAME"  # a frame computed at run time, before it is loaded into UFRAME / UTOOL
FUNCTIONS = {"POSEMULT": "CA_POSEMULT", "POSEINV": "CA_POSEINV", "DEFFRAME": "CA_DEFFRAME", "RELTOOL": "CA_RELTOOL"}
_FIELDS = {("UF", "UFRAME"), ("UT", "TFRAME")}


def karel_call(c: "Converter", name: str, registers: list[str], numbers: tuple[str, ...] = ()) -> str:
    """`CALL CA_XXX(a,b,c)`: the library program `name` given the NUMBERS of position registers `PR[...]`, then
    `numbers` as they are (constants, R[i])."""
    if len(name) > c.config.program_name_max_length:
        raise Untranslatable(f"KAREL program {name}: longer than the {c.config.program_name_max_length} characters a"
                             " program name has on this controller", Blocker.RUNTIME_POSITION)  # fmt: skip
    assert name in PROGRAMS, name
    return f"CALL {name}({','.join([register[3:-1] for register in registers] + list(numbers))})"


def karel_candidates(modules: list[n.Module], result: "ConversionResult") -> bool:
    """Whether --karel could convert some of the TODO: a pose data the programs may change (kept in a position
    register with --karel), an iodev (a file), or a TODO on a pose function or a frame worked out at run time. The conversion is
    made again with it only then."""
    if not result.todo_count:
        return False
    declared = [d for m in modules for d in m.declarations] + [d for m in modules for r in m.routines for d in r.body
                                                       if isinstance(d, n.DataDecl)]  # fmt: skip
    if any(d.type_name.lower() == "pose" and d.storage != "CONST" and not d.dims for d in declared):
        return True
    if any(d.type_name.lower() == "iodev" for d in declared):  # files: convert.karel_files
        return True
    causes = (Blocker.RUNTIME_POSITION, Blocker.RUNTIME_FRAME, Blocker.CALIBRATION)
    return any(note.kind == "TODO" and note.category in causes and "`" in note.message
               and any(f"{name}(" in note.message.split("`")[1].upper() for name in FUNCTIONS)
               for note in result.notes)  # fmt: skip  # the RAPID statement the TODO quotes


def _identity(value) -> bool:
    pose = to_pose(value)
    return all(abs(c) < 1e-9 for c in pose.pos) and abs(abs(pose.rot[0]) - 1) < 1e-9


def place_frames(c: "Converter") -> None:
    """Load each frame KAREL works out at run time into the frame its moves select, once every move has numbered
    the frames: `UFRAME[n]=PR[k]`, or `PR[bank]=PR[k]` for a frame past the controller's limit, loaded into its
    slot before each move as any banked frame is (written `UFRAME[{UF:NAME}]=PR[...]` until then, so that
    converting with --karel numbers the frames in the order the moves use them, as without it)."""
    load = re.compile(r"^(UTOOL|UFRAME)\[\{(UT|UF):([^}]*)\}\]=(PR\[[^\]]*\])$")
    read = re.compile(r"^(PR\[[^\]]*\])=(UTOOL|UFRAME)\[\{(UT|UF):([^}]*)\}\]$")
    for info in c.result.programs:
        lines = info.program.lines
        for i, line in enumerate(lines):
            text = line.text if isinstance(line, Instruction) else ""
            if (back := read.match(text)) is not None:  # PR[k]=UTOOL[n]: the frame read
                source, resource, kind, name = back.groups()
                allocation = (c.uframes if kind == "UF" else c.utools).assigned.get(name)
                frame = c.frames.get((kind, allocation.number)) if allocation else None
                if frame is None:  # no move selects it after all
                    lines[i] = Instruction(f"!{name} not used by a move"[:33].rstrip())
                else:
                    lines[i] = Instruction(f"{source}=PR[{frame.bank}]" if frame.bank is not None
                                           else f"{source}={resource}[{frame.number}]")  # fmt: skip
                continue
            found = load.match(text)
            if found is None:
                continue
            resource, kind, name, source = found.groups()
            allocation = (c.uframes if kind == "UF" else c.utools).assigned.get(name)
            frame = c.frames.get((kind, allocation.number)) if allocation else None
            if frame is None:  # no move selects it after all: nothing to load
                lines[i] = Instruction(f"!{name} not used by a move"[:33].rstrip())
            elif frame.bank is not None:
                lines[i] = Instruction(f"PR[{frame.bank}]={source}")
            else:
                lines[i] = Instruction(f"{resource}[{frame.number}]={source}")


def karel_would(result: "ConversionResult", karel: "ConversionResult") -> int:
    """The TODO of `result` that `karel`, the same conversion with --karel, converts."""
    left = {(note.program, note.rapid_line) for note in karel.notes if note.kind == "TODO"}
    return sum(1 for note in result.notes if note.kind == "TODO" and (note.program, note.rapid_line) not in left)


class KarelPoses:
    """The routine translator's part that writes the poses kept in position registers (mixed into it)."""

    def pose_value(self, a: n.Assign, register: str) -> None:
        """The whole of a pose kept in a register (module docstring)."""
        value = a.value
        if (source := self.kept_pose(value)) is not None:
            if source != register:
                self.emit(f"{register}={source}")
            return
        if self.pose_written(value, register) or self.pose_computed(value, register, 1) \
                or self.frame_read(value, register):  # fmt: skip
            return
        raise Untranslatable(f"pose {format_expr(a.target)} set to {format_expr(value)}: a pose kept in a position"
                             " register is set to PoseMult(), PoseInv() or DefFrame() of poses, to another one, or to"
                             " a value whose orientation is known", Blocker.RUNTIME_POSITION)  # fmt: skip

    def kept_pose(self, expr: n.Expr) -> str | None:
        """PR[k] of a pose, or a point, kept in a register (read: set by then); None for anything else."""
        if not isinstance(expr, n.Name) or (key := self.runtime_key(expr.name)) is None \
                or self.c.runtime_points.get(key) not in (POSE, "robtarget"):  # fmt: skip
            return None
        self.pose_read(expr, key)
        return self.c.point_register(key)

    def pose_function(self, expr: n.Expr) -> str | None:
        """The RAPID function of KAREL's library `expr` calls (POSEMULT...), unless the backup has its own."""
        if isinstance(expr, n.FuncCall) and (name := expr.name.upper()) in FUNCTIONS \
                and name not in self.c.computer.functions:  # fmt: skip
            return name
        return None

    def pose_computed(self, expr: n.Expr, register: str, slot: int) -> bool:
        """PoseMult(), PoseInv(), DefFrame() or RelTool() worked out by KAREL into `register`, their operands first
        into the registers CROSSARM.POSE<slot>, <slot + 1>...; False for anything else."""
        name = self.pose_function(expr)
        if name is None:
            return False
        positional = [arg.value for arg in expr.args if arg.name is None]  # type: ignore[union-attr]
        options = {(arg.name or "").upper(): arg.value for arg in expr.args if arg.name is not None}  # type: ignore[union-attr]
        wanted, allowed = {"POSEMULT": (2, set()), "POSEINV": (1, set()), "DEFFRAME": (3, {"ORIGIN"}),
                           "RELTOOL": (4, {"RX", "RY", "RZ"})}[name]  # fmt: skip
        if len(positional) != wanted or None in positional or not set(options) <= allowed or None in options.values():
            raise Untranslatable(f"{format_expr(expr)}: {name.title()} with these arguments is not converted",
                                 Blocker.RUNTIME_POSITION)  # fmt: skip
        if name == "RELTOOL":
            source = self.pose_register(positional[0], slot)
            self.emit(karel_call(self.c, "CA_RELTOOL", [source, register], self.karel_numbers(positional[1:], options)))
            return True
        operands = [self.pose_register(e, slot + i, point=name == "DEFFRAME") for i, e in enumerate(positional)]
        if name == "DEFFRAME":
            try:
                origin = self.c.evaluator.constant_number(options["ORIGIN"]) if "ORIGIN" in options else 1.0
            except Unresolvable as exc:
                raise Untranslatable(f"DefFrame \\Origin only known at run time ({exc})", Blocker.RUNTIME_POSITION) from exc
            if origin not in (1.0, 2.0, 3.0):
                raise Untranslatable(f"DefFrame \\Origin:={fmt_number(origin)}: RAPID takes 1, 2 or 3", Blocker.RUNTIME_POSITION)
            self.emit(karel_call(self.c, "CA_DEFFRAME", [*operands, register], (str(int(origin)),)))
        else:
            self.emit(karel_call(self.c, FUNCTIONS[name], [*operands, register]))
        return True

    def karel_numbers(self, steps: list, options: dict) -> tuple[str, ...]:
        """RelTool's dx, dy, dz, rx, ry, rz as CALL arguments: constants, or registers TP works them out in
        (R[n:Calc<i>], one slot each, so that none overwrites another)."""
        values = [*steps, *(options.get(axis) for axis in ("RX", "RY", "RZ"))]
        out = []
        for slot, expr in enumerate(values, 1):
            if expr is None:
                out.append("0")
                continue
            try:
                out.append(decimal(self.single(expr, slot)))  # type: ignore[attr-defined]
            except Untranslatable as exc:
                raise Untranslatable(f"RelTool {format_expr(expr)}: {exc}", Blocker.RUNTIME_POSITION) from exc
        return tuple(out)

    def pose_register(self, expr: n.Expr, slot: int, point: bool = False) -> str:
        """The position register KAREL reads a pose (or a point) from: its own when kept in one, else the register
        CROSSARM.POSE<slot> a pose function or a value known now is written into first. `point`: only its x, y, z
        count (DefFrame)."""
        if (source := self.kept_pose(expr)) is not None:
            return source
        register = self.c.point_register(f"{SCRATCH}{slot}")
        if self.pose_written(expr, register) or self.pose_computed(expr, register, slot) \
                or self.frame_read(expr, register):  # fmt: skip
            return register
        try:
            target = self.c.evaluator.robtarget(expr)
        except Unresolvable:
            target = None
        if target is not None:  # a point known now: its configuration too, for RelTool
            if point:
                self.pose_components(register, [fmt_number(round(v, 3) + 0.0) for v in target.pose.pos], target.pose.rot)
            else:
                self.emit(f"{register}={self.known_point(expr, target, expr.span.line)}")  # type: ignore[attr-defined]
            return register
        try:
            self.c.computer.value(expr)
        except Unresolvable as exc:
            raise Untranslatable(f"{format_expr(expr)}: KAREL is given poses and points kept in position registers or"
                                 f" known now, not this one ({exc})", Blocker.RUNTIME_POSITION) from exc  # fmt: skip
        raise Untranslatable(f"{format_expr(expr)}: KAREL is given poses and points kept in position registers or"
                             " known now", Blocker.RUNTIME_POSITION)  # fmt: skip

    def karel_reltool(self, call: n.FuncCall, register: str) -> Unknown:
        """RelTool() of a point kept in a register whose orientation, or of a point whose rotation, is only known at
        run time: `CALL CA_RELTOOL(...)`; the orientation it leaves (only known at run time)."""
        self.pose_computed(call, register, 1)
        return Unknown("has an orientation known at run time only")

    def frame_fields(self, kind: str, name: str, span: n.Span) -> tuple:
        """(its declaration, its oframe or None) for a tool or work object whose tframe or uframe KAREL works out
        or reads: a tool the robot holds, its pin as it is (tool_pin -x); a fixed work object whose other fields
        are known now. Untranslatable otherwise."""
        decl = self.c.symbols.get(name)
        what = f"{'work object' if kind == 'UF' else 'tool'} {decl.name if decl else name}"
        root = n.Name(span, decl.name if decl else name)
        try:
            holder = self.c.computer.value(n.Component(span, root, "robhold")).value
            other = self.c.computer.value(n.Component(span, root, "oframe")).value if kind == "UF" else None
            fixed = self.c.computer.value(n.Component(span, root, "ufprog")).value if kind == "UF" else True
        except Unresolvable as exc:
            raise Untranslatable(f"{what}: computed at run time by KAREL when its other fields are known now ({exc})",
                                 Blocker.RUNTIME_FRAME) from exc  # fmt: skip
        if bool(holder) != (kind == "UT") or not fixed:
            raise Untranslatable(f"{what}: {'stationary tool' if kind == 'UT' else 'robot-held or moving work object'}:"
                                 " not supported", Blocker.STATIONARY)  # fmt: skip
        if kind == "UT" and self.c.config.tool_pin != TOOL_PIN_DEFAULT:
            raise Untranslatable(f"{what}: tframe computed at run time by KAREL with the tool's pin as it is"
                                 " (tool_pin -x), not turned for another hole", Blocker.RUNTIME_FRAME)  # fmt: skip
        return decl, other

    def frame_read(self, expr: n.Expr, register: str) -> bool:
        """A tool's tframe, or a work object's uframe (its oframe the identity), the programs change at run time,
        read where the robot keeps it: `PR[k]=UTOOL[n]` (UFRAME), what SETUP_FRAMES or the last KAREL load set;
        False for anything else. Changed by a statement left TODO before: said so."""
        path = path_of(expr) if isinstance(expr, n.Component) else None
        if not path or len(path) != 2:
            return False
        kind = {"TFRAME": "UT", "UFRAME": "UF"}.get(path[1])
        if kind is None or path[0] not in self.c.frames_in_moves[kind] or self.c.symbols.is_local(path[0]):
            return False
        decl = self.c.symbols.get(path[0])
        if decl is None or decl.type_name.lower() != ("tooldata" if kind == "UT" else "wobjdata"):
            return False
        here = self.scope(path[0])  # type: ignore[attr-defined]
        if isinstance(here, Unknown):
            raise Untranslatable(str(here.error(decl.name)), Blocker.RUNTIME_FRAME)
        if isinstance(here, Typed) and (hole := first_hole(here.value, {path[1]}, decl.type_name.lower())) is not None:
            raise Untranslatable(hole.why, Blocker.RUNTIME_FRAME)
        _decl, other = self.frame_fields(kind, path[0], expr.span)
        if other is not None and not _identity(other):
            raise Untranslatable(f"{format_expr(expr)}: read from UFRAME, which holds uframe x oframe, when the oframe"
                                 " is the identity", Blocker.RUNTIME_FRAME)  # fmt: skip
        self.emit(f"{register}={'UTOOL' if kind == 'UT' else 'UFRAME'}[{{{kind}:{path[0]}}}]")  # place_frames()
        return True

    def frame_at_run_time(self, a: n.Assign, root_type: str, remark: str) -> bool:
        """A work object's uframe, or a tool's tframe, set to a pose KAREL works out (module docstring); False when
        the statement is not one: the caller says why it stays TODO."""
        path = path_of(a.target)
        kind = "UT" if root_type == "tooldata" else "UF"
        if not path or len(path) != 2 or (kind, path[1]) not in _FIELDS:
            return False
        if self.pose_function(a.value) is None and self.kept_pose_key(a.value) is None:
            return False
        if path[0] not in self.c.frames_in_moves[kind]:
            return False
        decl, other = self.frame_fields(kind, path[0], a.span)
        what = f"{'work object' if kind == 'UF' else 'tool'} {decl.name}"
        span = a.span
        root = n.Name(span, decl.name)
        self.emit(remark)
        source = self.kept_pose(a.value)
        if source is None:
            source = self.c.point_register(FRAME)
            self.pose_computed(a.value, source, 1)
        if other is not None and not _identity(other):
            scratch = self.c.point_register(f"{SCRATCH}1")
            self.pose_written(n.Component(span, root, "oframe"), scratch)
            self.emit(karel_call(self.c, "CA_POSEMULT", [source, scratch, self.c.point_register(FRAME)]))
            source = self.c.point_register(FRAME)
        self.emit(f"{'UTOOL' if kind == 'UT' else 'UFRAME'}[{{{kind}:{path[0]}}}]={source}")  # place_frames()
        if kind == "UT":
            self.active_ut = None  # type: ignore[attr-defined]
        else:
            self.active_uf = None  # type: ignore[attr-defined]
        self.c.warn_once(f"karel-frame|{kind}|{decl.name}", self.name, span.line, f"{what} computed at run time by"
                         " KAREL and loaded where the RAPID sets it: the moves in it go to their points in the new frame,"
                         " with the configuration (and turns) CrossArm worked out for its saved value. A frame turned far"
                         " from it may need another configuration: the move then stops (MOTN-017/018) or takes"
                         " another posture: check the moves after a calibration", Blocker.RUNTIME_FRAME)  # fmt: skip
        return True

    def kept_pose_key(self, expr: n.Expr) -> str | None:
        if isinstance(expr, n.Name) and (key := self.runtime_key(expr.name)) is not None \
                and self.c.runtime_points.get(key) in (POSE, "robtarget"):  # fmt: skip
            return key
        return None

    def pose_read(self, expr: n.Name, key: str) -> None:
        """A pose kept in a register, read: set by then. Module data declared with a value starts with it in RAPID,
        its register only once a program sets it: said once."""
        self.runtime_set(expr.name)
        decl = self.c.symbols.get_global(expr.name) if "." not in key else None
        if decl is not None and decl.init is not None and self.c.runtime_points.get(key) == POSE:
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
