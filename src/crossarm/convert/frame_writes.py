# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A tool's tframe or a work object's uframe changed at run time part by part, or copied from another frame (a
mixin of the routine translator).

A calibration routine often writes a frame one part at a time, from a point read on the robot, or copies a
frame it has just measured to a series of work objects:

    w.uframe.trans := pMeas.trans;   PR[F]=UFRAME[n]   PR[F,1]=PR[k,1]  PR[F,2]=PR[k,2]  PR[F,3]=PR[k,3]   UFRAME[n]=PR[F]
    w.uframe.rot := pMeas.rot;       PR[F]=UFRAME[n]   PR[F,4]=PR[k,4]  PR[F,5]=PR[k,5]  PR[F,6]=PR[k,6]   UFRAME[n]=PR[F]
    t.tframe.trans.z := nLen;        PR[F]=UTOOL[m]    PR[F,3]=R[i]                                         UTOOL[m]=PR[F]
    wB.uframe := wA.uframe;          PR[F]=UFRAME[a]                                                        UFRAME[b]=PR[F]
    w.oframe := [[0,0,0],[1,0,0,0]]; PR[F]=UFRAME[n] (the uframe at run time), then uframe x oframe loaded

PR[F] is CrossArm's register CROSSARM.FRAME (mapping key `point_registers`). The frame is first put in it: its
value when known now, else read back where the robot keeps it (`PR[F]=UFRAME[n]`, what SETUP_FRAMES or the
last load set); then the parts the RAPID sets are written over it: x, y, z by TP from any value TP computes;
the orientation copied as the W, P, R of a point or a pose kept in a position register (the same rotation as
RAPID's quaternion), or written from a quaternion known now; then the frame is loaded into the frame the
moves select (`UFRAME[n]=PR[F]`, or its bank register past the controller's limit: crossarm.convert.
karel_poses.place_frames). UFRAME holds uframe x oframe: an oframe other than the identity is multiplied in
by KAREL (CA_POSEMULT, --karel), and taken out again when the uframe is read back (its inverse, known now).

What the robot keeps in UFRAME / UTOOL is what the RAPID data holds as long as each statement changing the
frame was converted: one left TODO marks the frame (`NAME#FRAME`), and it is not read back after that.

Measured on ROBOGUIDE V10.10 (tools/make_frame_field_probe.py): `PR[F]=UFRAME[n]` / `UTOOL[n]`, `PR[F,i]=PR[k,i]`
for the six components, and `UFRAME[n]=PR[F]` / `UTOOL[n]=PR[F]` put the frame where RAPID's data does.
"""

from typing import Any

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.compute import FRAME_RECORDS, LAYOUTS, Hole, Typed, Unknown, path_of, to_pose
from crossarm.convert.tp_numbers import fmt_number, operand
from crossarm.convert.values import Unresolvable
from crossarm.geometry import Pose, quat_to_wpr
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr

FRAME = "CROSSARM.FRAME"
SCRATCH = "CROSSARM.POSE"
STALE = "#FRAME"  # NAME#FRAME in the routine's known values: a statement changing the frame was left TODO
FIELD = {"UT": "TFRAME", "UF": "UFRAME"}
RESOURCE = {"UT": "UTOOL", "UF": "UFRAME"}
_AXES = ("X", "Y", "Z")


def identity(pose: Pose | None) -> bool:
    return pose is None or (all(abs(c) < 1e-9 for c in pose.pos) and abs(abs(pose.rot[0]) - 1) < 1e-9)


class FrameWrites:
    """Mixin of the routine translator: needs c, known, emit(), scope(), arithmetic(), kept_pose(), frame_fields(),
    pose_components()."""

    # -- what the robot holds -------------------------------------------------------------------------------------

    def frame_kind(self, expr: n.Expr) -> tuple[str, str] | None:
        """("UF", "WTABLE") for `wTable.uframe`, ("UT", "TGUN") for `tGun.tframe` (module data); None otherwise."""
        path = path_of(expr) if isinstance(expr, n.Component) else None
        if not path or len(path) != 2:
            return None
        decl = self.c.symbols.get(path[0])  # type: ignore[attr-defined]
        if decl is None or decl.dims or self.c.symbols.is_local(path[0]):  # type: ignore[attr-defined]
            return None
        kind = {"tooldata": "UT", "wobjdata": "UF"}.get(decl.type_name.lower())
        return (kind, path[0]) if kind is not None and FIELD[kind] == path[1] else None

    def frame_kept(self, kind: str, key: str) -> None:
        """Untranslatable unless what the robot holds in UFRAME / UTOOL for this data is its frame now: no move
        selects it (no number), a statement changing it was left TODO, or a call may have changed it."""
        decl = self.c.symbols.get(key)  # type: ignore[attr-defined]
        name = decl.name if decl is not None else key
        if key not in self.c.frames_in_moves[kind]:  # type: ignore[attr-defined]
            raise Untranslatable(
                f"{name}: no move selects it, the robot does not keep its frame", Blocker.RUNTIME_FRAME
            )
        stale = self.known.get(f"{key}{STALE}")  # type: ignore[attr-defined]
        if isinstance(stale, Unknown):
            raise Untranslatable(f"'{name}' {stale.reason}: its {RESOURCE[kind]} is not what the RAPID holds",
                                 Blocker.CALIBRATION if stale.measured else Blocker.RUNTIME_FRAME)  # fmt: skip
        here = self.scope(key)  # type: ignore[attr-defined]
        if isinstance(here, Unknown):
            raise Untranslatable(str(here.error(name)), Blocker.CALIBRATION if here.measured else Blocker.RUNTIME_FRAME)
        if isinstance(here, Typed) and isinstance(here.value, list):
            index = [f.upper() for f, _ in LAYOUTS[decl.type_name.lower()]].index(FIELD[kind])  # type: ignore[union-attr]
            hole = here.value[index]
            if isinstance(hole, Hole) and hole.here and not hole.loaded:
                raise Untranslatable(hole.why, Blocker.CALIBRATION if hole.measured else Blocker.RUNTIME_FRAME)

    def frame_now(self, kind: str, key: str, span: n.Span) -> tuple[Pose | None, Pose | None]:
        """(its frame known now or None: read back, its oframe or None) for a tool or work object, Untranslatable
        when it is neither known nor kept by the robot."""
        decl = self.c.symbols.get(key)  # type: ignore[attr-defined]
        _decl, other = self.frame_fields(kind, key, span)  # type: ignore[attr-defined]
        try:
            return to_pose(self.c.computer.value(n.Component(span, n.Name(span, decl.name), FIELD[kind].lower())).value), \
                to_pose(other) if other is not None else None  # type: ignore[attr-defined]  # fmt: skip
        except Unresolvable:
            pass
        self.frame_kept(kind, key)
        return None, to_pose(other) if other is not None else None

    def frame_into(
        self, register: str, kind: str, key: str, span: n.Span, known: Pose | None, other: Pose | None
    ) -> None:
        """Write the frame (tframe, uframe) into `register`: its value known now, or read back (frame_now)."""
        if known is not None:
            self.pose_components(register, [fmt_number(round(v, 3) + 0.0) for v in known.pos], known.rot)  # type: ignore[attr-defined]
            return
        self.emit(f"{register}={RESOURCE[kind]}[{{{kind}:{key}}}]")  # type: ignore[attr-defined]  # place_frames()
        if not identity(other):  # UFRAME holds uframe x oframe
            scratch = self.c.point_register(f"{SCRATCH}2")  # type: ignore[attr-defined]
            inverse = other.inverse()  # type: ignore[union-attr]
            self.pose_components(scratch, [fmt_number(round(v, 3) + 0.0) for v in inverse.pos], inverse.rot)  # type: ignore[attr-defined]
            self.emit(self.karel_line("CA_POSEMULT", [register, scratch, register]))

    def karel_line(self, name: str, registers: list[str]) -> str:
        from crossarm.convert.karel_poses import karel_call

        return karel_call(self.c, name, registers)  # type: ignore[attr-defined]

    def frame_load(self, kind: str, key: str, register: str, other: Pose | None) -> None:
        """Load the frame in `register` into the frame the moves select, its oframe multiplied in first."""
        if not identity(other):
            scratch = self.c.point_register(f"{SCRATCH}2")  # type: ignore[attr-defined]
            self.pose_components(scratch, [fmt_number(round(v, 3) + 0.0) for v in other.pos], other.rot)  # type: ignore[attr-defined, union-attr]
            self.emit(self.karel_line("CA_POSEMULT", [register, scratch, register]))
        self.emit(f"{RESOURCE[kind]}[{{{kind}:{key}}}]={register}")  # type: ignore[attr-defined]  # place_frames()
        if kind == "UT":
            self.active_ut = None
        else:
            self.active_uf = None

    def frame_loaded(self, kind: str, key: str, line: int, measured: bool, warn: bool = True) -> None:
        """After a frame was loaded at run time: the routine's value of that field is the one the robot holds."""
        decl = self.c.symbols.get(key)  # type: ignore[attr-defined]
        self.known.pop(f"{key}{STALE}", None)  # type: ignore[attr-defined]
        here = self.known.get(key)  # type: ignore[attr-defined]
        type_name = decl.type_name.lower()
        if isinstance(here, Unknown):
            return
        try:
            base = here if isinstance(here, Typed) else self.c.computer.all_but(decl.name, (key, FIELD[kind]))  # type: ignore[attr-defined]
        except Unresolvable:
            return
        value = list(base.value)
        index = [f.upper() for f, _ in LAYOUTS[type_name]].index(FIELD[kind])
        value[index] = Hole(f"'{decl.name}.{FIELD[kind].lower()}' is set at l.{line} at run time", measured, here=True,
                            loaded=True)  # fmt: skip
        self.known[key] = Typed(value, type_name, 0)  # type: ignore[attr-defined]
        if warn:
            self.c.warn_once(f"runtime-frame|{kind}|{decl.name}", self.name, line, f"{'tool' if kind == 'UT' else 'work object'}"  # type: ignore[attr-defined]
                         f" {decl.name} computed at run time and loaded where the RAPID sets it: the moves in it go"
                             " to their points in the new frame, with the configuration (and turns) CrossArm worked out"
                             " for its saved value. A frame turned far from it may need another configuration: the move"
                             " then stops (MOTN-017/018) or takes another posture: check the moves after a calibration",
                             Blocker.RUNTIME_FRAME)  # fmt: skip

    # -- the statements -----------------------------------------------------------------------------------------

    def frame_written(self, a: n.Assign, root_type: str, remark: str, measured: bool, why: str = "") -> bool:
        """`a` sets a part of a tool's tframe or a work object's uframe, or the whole of it from another frame or
        from [trans, rot], at run time (module docstring); False when it is not such a statement, or when its value
        reads what a statement left TODO sets (`why`, the reason it is not known now, then says best why)."""
        if "(left TODO)" in why:
            return False
        try:
            return self._frame_written(a, root_type, remark, measured)
        except Untranslatable as exc:  # a frame measured on the robot: a calibration, whatever else stops it
            if measured and exc.category == Blocker.RUNTIME_FRAME:
                raise Untranslatable(str(exc), Blocker.CALIBRATION) from exc
            raise

    def _frame_written(self, a: n.Assign, root_type: str, remark: str, measured: bool) -> bool:
        path = path_of(a.target)
        if root_type not in FRAME_RECORDS or not path or len(path) < 2 or "{}" in path:
            return False
        kind = "UT" if root_type == "tooldata" else "UF"
        rest = path[2:]
        if path[1] != FIELD[kind] or rest not in ((), ("TRANS",), ("ROT",), *(("TRANS", axis) for axis in _AXES)):
            return False
        whole = not rest
        value = a.value
        pair = isinstance(value, n.Aggregate) and len(value.items) == 2
        source = self.frame_kind(value) if whole else None
        key = path[0]
        if key not in self.c.frames_in_moves[kind] or self.c.symbols.is_local(key):  # type: ignore[attr-defined]
            return False
        if whole and source is None and not pair:
            # PoseMult(frame read back, pose known now), the frame's orientation known now: TP; any other pose
            # function, or a pose kept in a register: crossarm.convert.karel_poses
            return self._frame_moved(a, kind, key, remark, measured)
        decl = self.c.symbols.get(key)  # type: ignore[attr-defined]
        what = f"{'tool' if kind == 'UT' else 'work object'} {decl.name}"
        # What it needs, before anything is written: the frame now (unless every part is written), its oframe.
        if whole and source is not None:
            base, base_other = self.frame_now(source[0], source[1], a.span)
            _decl, other = self.frame_fields(kind, key, a.span)  # type: ignore[attr-defined]
            other_pose = to_pose(other) if other is not None else None
        elif whole:
            base, base_other = None, None
            _decl, other = self.frame_fields(kind, key, a.span)  # type: ignore[attr-defined]
            other_pose = to_pose(other) if other is not None else None
        else:
            base, other_pose = self.frame_now(kind, key, a.span)
            base_other = other_pose
        if (not identity(other_pose) or (base is None and (not whole or source is not None) and not identity(base_other))) \
                and not self.c.config.karel:  # type: ignore[attr-defined]  # fmt: skip
            raise Untranslatable(f"{what}: its oframe is not the identity: the uframe x oframe UFRAME holds is worked"
                                 " out by KAREL: convert with --karel", Blocker.RUNTIME_FRAME)  # fmt: skip
        self.emit(remark)  # type: ignore[attr-defined]
        register = self.c.point_register(FRAME)  # type: ignore[attr-defined]
        if whole and source is not None:
            self.frame_into(register, source[0], source[1], a.span, base, base_other)
        elif whole:
            self._trans_into(register, value.items[0], _AXES)  # type: ignore[union-attr]
            self._rot_into(register, value.items[1])  # type: ignore[union-attr]
        else:
            self.frame_into(register, kind, key, a.span, base, base_other)
            if rest[0] == "ROT":
                self._rot_into(register, value)
            else:
                self._trans_into(register, value, rest[1:] or _AXES, (key, FIELD[kind], "TRANS"))
        self.frame_load(kind, key, register, other_pose)
        self.frame_loaded(kind, key, a.span.line, measured)
        return True

    def _frame_moved(self, a: n.Assign, kind: str, key: str, remark: str, measured: bool) -> bool:
        """`t.tframe := PoseMult(tBase.tframe, peOfs)`, tBase's tframe changed at run time but for its orientation,
        known now as peOfs is: the frame read back, moved by R x peOfs.trans and turned to R x peOfs.rot, in TP
        (`PR[F,1]=PR[F,1]+dx`...). False when the statement is not one (KAREL or TODO then)."""
        call = a.value
        if not isinstance(call, n.FuncCall) or call.name.upper() != "POSEMULT" \
                or call.name.upper() in self.c.computer.functions:  # type: ignore[attr-defined]  # fmt: skip
            return False
        given = [arg.value for arg in call.args if arg.name is None]
        if len(given) != 2 or len(call.args) != 2 or None in given:
            return False
        left, right = given
        source = self.frame_kind(left)  # type: ignore[arg-type]
        if source is None:
            return False
        try:
            offset = to_pose(self.c.computer.value(right).value)  # type: ignore[attr-defined, arg-type]
            turn = to_pose([[0, 0, 0], self.c.computer.value(n.Component(left.span, left, "rot")).value])  # type: ignore[attr-defined, union-attr]
        except Unresolvable:
            return False
        base, base_other = self.frame_now(source[0], source[1], a.span)
        _decl, other = self.frame_fields(kind, key, a.span)  # type: ignore[attr-defined]
        other_pose = to_pose(other) if other is not None else None
        if base is not None or not identity(base_other) or (not identity(other_pose) and not self.c.config.karel):  # type: ignore[attr-defined]
            return False
        moved = turn.compose(offset)  # R x peOfs: its position is what the base frame's origin moves by
        self.emit(remark)  # type: ignore[attr-defined]
        register = self.c.point_register(FRAME)  # type: ignore[attr-defined]
        self.frame_into(register, source[0], source[1], a.span, None, base_other)
        element = register[:-1]
        for axis, shift in enumerate(moved.pos, 1):
            shift = round(shift, 3) + 0.0
            if shift:
                self.emit(f"{element},{axis}]={element},{axis}]{'-' if shift < 0 else '+'}{fmt_number(abs(shift))}")  # type: ignore[attr-defined]
        for axis, angle in zip((4, 5, 6), quat_to_wpr(moved.rot), strict=True):  # type: ignore[arg-type]
            self.emit(f"{element},{axis}]={operand(fmt_number(round(angle, 3) + 0.0))}")  # type: ignore[attr-defined]
        self.frame_load(kind, key, register, other_pose)
        self.frame_loaded(kind, key, a.span.line, measured)
        return True

    def oframe_written(self, a: n.Assign, root_type: str, remark: str, new: Typed) -> bool:
        """`a` sets a work object's oframe to a value known now while its uframe is only known at run time: the
        uframe read back (with the oframe it had), the new uframe x oframe loaded; False otherwise."""
        path = path_of(a.target)
        if root_type != "wobjdata" or not path or len(path) < 2 or path[1] != "OFRAME" or "{}" in path:
            return False
        key = path[0]
        if key not in self.c.frames_in_moves["UF"] or self.c.symbols.is_local(key):  # type: ignore[attr-defined]
            return False
        try:
            robhold, ufprog, _ufmec, _uframe, oframe = new.value
            after = to_pose(oframe)
        except (TypeError, ValueError, Unresolvable):
            return False
        if robhold is not False or ufprog is not True:
            return False
        try:
            base, before = self.frame_now("UF", key, a.span)
        except Untranslatable:
            return False  # the reason the statement gave stands
        if base is not None:
            return False
        decl = self.c.symbols.get(key)  # type: ignore[attr-defined]
        if not (identity(before) and identity(after)) and not self.c.config.karel:  # type: ignore[attr-defined]
            raise Untranslatable(f"work object {decl.name}: oframe changed while its uframe is only known at run time:"
                                 " the uframe x oframe UFRAME holds is worked out by KAREL: convert with --karel",
                                 Blocker.RUNTIME_FRAME)  # fmt: skip
        self._field_value = None
        self.emit(remark)  # type: ignore[attr-defined]
        if not (identity(before) and identity(after)):
            register = self.c.point_register(FRAME)  # type: ignore[attr-defined]
            self.frame_into(register, "UF", key, a.span, None, before)
            self.frame_load("UF", key, register, after)
        self.known[key] = new  # type: ignore[attr-defined]
        self.known.pop(f"{key}{STALE}", None)  # type: ignore[attr-defined]
        return True

    def _trans_into(self, register: str, value: n.Expr, axes: tuple[str, ...], own: tuple[str, ...] = ()) -> None:
        """x, y, z (those of `axes`) of `value` into PR[register, 1..3]: the items of [x, y, z], or its components.
        `own`: the frame's own translation, read back into the register: `t.tframe.trans.z := t.tframe.trans.z + 10`
        is `PR[F,3]=PR[F,3]+10`."""
        base = register[:-1]
        for axis in axes:
            if len(axes) == 1:
                part = value
            elif isinstance(value, n.Aggregate) and len(value.items) == 3:
                part = value.items[_AXES.index(axis)]
            else:
                part = n.Component(value.span, value, axis.lower())
            element = f"{base},{_AXES.index(axis) + 1}]"
            if own and isinstance(part, n.BinaryOp) and part.op in ("+", "-") \
                    and path_of(part.left) == (*own, axis):  # fmt: skip
                self.emit(f"{element}={element}{part.op}{self.single(part.right, 1)}")  # type: ignore[attr-defined]
                continue
            self.emit(f"{element}={self.arithmetic(part)}")  # type: ignore[attr-defined]

    def _rot_into(self, register: str, value: n.Expr) -> None:
        """The orientation `value` into PR[register, 4..6]: from a quaternion known now, or the W, P, R of a point
        or pose kept in a position register, or of a frame."""
        base = register[:-1]
        try:
            known: Any = self.c.computer.value(value)  # type: ignore[attr-defined]
            rot = to_pose([[0, 0, 0], known.value]).rot
        except Unresolvable:
            rot = None
        if rot is not None:
            for axis, angle in zip((4, 5, 6), quat_to_wpr(rot), strict=True):  # type: ignore[arg-type]
                self.emit(f"{base},{axis}]={operand(fmt_number(round(angle, 3) + 0.0))}")  # type: ignore[attr-defined]
            return
        source = None
        if isinstance(value, n.Component) and value.field.upper() == "ROT":
            source = self.kept_pose(value.base)  # type: ignore[attr-defined]
            if source is None and (frame := self.frame_kind(value.base)) is not None:
                known_frame, other = self.frame_now(frame[0], frame[1], value.span)
                if known_frame is None and not identity(other) and not self.c.config.karel:  # type: ignore[attr-defined]
                    raise Untranslatable(f"{format_expr(value)}: read from {RESOURCE[frame[0]]}, which holds uframe x"
                                         " oframe: worked out by KAREL: convert with --karel", Blocker.RUNTIME_FRAME)  # fmt: skip
                source = self.c.point_register(f"{SCRATCH}1")  # type: ignore[attr-defined]
                self.frame_into(source, frame[0], frame[1], value.span, known_frame, other)
        if source is None:
            raise Untranslatable(f"orientation {format_expr(value)}: only known at run time: TP copies the W, P, R of a"
                                 " point or a pose kept in a position register, or of a frame", Blocker.RUNTIME_FRAME)  # fmt: skip
        for axis in (4, 5, 6):
            self.emit(f"{base},{axis}]={source[:-1]},{axis}]")  # type: ignore[attr-defined]
