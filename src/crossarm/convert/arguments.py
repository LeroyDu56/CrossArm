# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID PROC parameters -> TP CALL arguments: `Set_Station 3\\Wait;` -> `CALL SET_STATION(3,1)`.

TP passes up to ten untyped values to a program called with CALL NAME(a,b,...), which reads
them as AR[1], AR[2]... and cannot change them. That holds the RAPID parameters passed by
value that TP can represent: `num`, `bool` (1 / 0), `string` (text written in the call, 38
characters at most: ROBOGUIDE refuses 39) and optional switches (1 when given, 0 otherwise).
A record the backup declares is passed as its components the routine reads, each an argument of
its own: `DeburrPart pdHousing;` -> `CALL DEBURRPART(2,.8,1)` for part.passes, part.depth,
part.chamfer. A num passed by reference (INOUT, VAR, PERS) that the routine changes is copied back:
the routine works on a register of its own, which the caller reads into its data after the CALL.
A tooldata or wobjdata the routine moves with is passed as its frame number (`CALL PICK(3)`), which the
routine selects (`UTOOL_NUM=AR[1]`); an optional work object not given is 0, wobj0. A point moved to
in such a routine is in a position register: the controller refuses a P recorded in another tool
than the one selected (INTP-253), a move to a register takes the frames selected when it runs.
A speeddata or zonedata parameter the routine makes its MoveJ, MoveL and MoveAbsJ with is passed as numbers:
the speed in mm/s for its linear moves and in % for its joint ones, and the CNT of each corner the call decides,
worked out by the caller as it would write the move with what it passes (motion.corner: the CNT depends on the
zone, the speed and the speed of the move after). A move takes no AR[n] as its speed or CNT (measured: ASBN-092),
so the routine copies them to registers when it starts: `L P[1] R[k]mm/sec CNT R[m]`. A TP move is FINE or CNT as
written: when every call passes `fine` for a zone, the routine's moves through it are FINE and nothing is passed
for them; when only some do, each such move is written twice, CNT and FINE, and the call passes 101 for fine
(`IF R[m]>100,JMP LBL[a]`): a CALL takes no negative number (ASBN-092), a CNT is at most 100.
A routine with any other parameter — a record passed whole to another routine, a frame used other
than to move with, an optional pose, a work object the routine changes when it is passed by reference — is
not converted, and its calls stay TODO with the reason.

A `robtarget` has no place in AR[n]: it goes in a position register of its own, which the caller
sets before the CALL (PR[k]=P[j]) and the routine moves to (L PR[k]). A move to a position register
takes the frames selected when it runs, and the configuration the register holds (ROBOGUIDE), as
a RAPID move takes its own tool and work object with the robtarget it is given.

A TP program can keep a string argument (SR[n]=AR[1]) and measure it (STRLEN), but not show it:
MESSAGE takes fixed text. So a TPWrite of a string parameter stays TODO in the routine, while
the routine and its calls are converted.

Every argument is passed on every call, switches included: on a FANUC controller reading an
AR[n] the caller did not pass stops the program, where RAPID's Present() just says FALSE. An optional
num, bool or string is passed as two arguments: 1 / 0 whether the call gives it, then its value (0, or ''
when not given): `Station 3\\Speed:=200;` -> `CALL STATION(3,1,200)`, `Station 4;` -> `CALL STATION(4,0,0)`,
and Present(Speed) in the routine reads the first (`IF AR[2]=1`). Passed by reference (`\\INOUT num`), the
caller reads it back only when it gave it. A tooldata or wobjdata passed by reference (INOUT, VAR) is passed
by its number when the routine does not change it: the frame is the caller's own. A tooldata of which the routine
sets the tframe (a calibration: `tCal.tframe.trans.z := nLen`) is passed by its number too: the routine writes
UTOOL[AR[n]] (crossarm.convert.frame_writes), which is where the caller's moves take the tool from. An optional
point is passed as whether the call gives it (Present() reads it), the point in its position register when given.
A bool passed by reference that the routine sets is copied to a register as a num is (1 / 0), and read back into
the caller's flag.

A RAPID parameter passed by value is a local copy the routine may change (`Angle:=0;`). AR[n]
cannot be written, so such a num parameter is copied into a register when the program starts,
and the routine works on the register.
"""

import re
from dataclasses import dataclass, replace

from crossarm.convert.motion import next_move
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr
from crossarm.rapid.walk import base_name, split_params, walk_statements

MAX_ARGS = 10  # TP CALL takes at most ten arguments
_NAME = re.compile(r"([A-Za-z_]\w*)\s*(\{[^}]*\})?\s*$")


@dataclass(frozen=True, slots=True)
class CallCorner:
    """A move of the routine through a zone whose CNT the call decides: its zone is a zonedata parameter, or its
    speed a speeddata one. The caller works the CNT out from what it passes and gives it as a number."""

    motion: str  # "J" | "L"
    zone: n.Expr
    speed: n.Expr
    following: n.Expr | None  # the speed of the move the corner leads into (motion.next_move)

    @property
    def key(self) -> tuple[str, ...]:
        return (self.motion, *(format_expr(e).upper() if e is not None else "" for e in (self.zone, self.speed, self.following)))


# What a speeddata or zonedata parameter is passed as: the TCP speed in mm/s, the % of a joint move, a CNT.
MOTION_ARGUMENTS = frozenset({"speed_tcp", "speed_joint", "cnt"})


@dataclass(frozen=True, slots=True)
class Slot:
    name: str  # as declared; a record's component: "part.passes"; a speed's: "v.tcp", "v.joint", "z.cnt"
    # "num" | "bool" | "string" | "switch" | "robtarget" (in a position register, not in AR[n]) | "record"
    # | "tooldata" | "wobjdata" (its frame number) | "speeddata" | "zonedata" (as their MOTION_ARGUMENTS)
    kind: str
    # a record: the components the routine reads, each passed as an argument; a speed or zone: its numbers
    fields: tuple["Slot", ...] = ()
    by_reference: bool = False  # INOUT, VAR or PERS: what the routine changes goes back to the caller
    optional: bool = False  # a switch, or an optional work object (0 when not given: wobj0)
    corner: CallCorner | None = None  # a "cnt": the move it is the CNT of
    fine: bool = False  # a "cnt" some calls pass fine for (101): the routine writes the move both ways

    @property
    def key(self) -> str:
        return self.name.upper()

    @property
    def given_flag(self) -> bool:
        """An optional num, bool or string: passed as two arguments, 1 / 0 whether the call gives it, then its
        value (0, or '' for a text, when it does not). Present() reads the first."""
        return self.optional and self.kind in ("num", "bool", "string")


def presence(name: str) -> str:
    """The key of the argument saying whether an optional value is given: 'PRESENT(SPEED)'."""
    return f"PRESENT({name})".upper()


# Why an optional parameter of another type is not passed: a TP argument is a number or a text.
_OPTIONAL_REFUSED = {
    "pose": "a pose is six numbers, a TP argument one",
    "pos": "a position is three numbers, a TP argument one",
    "orient": "an orientation is four numbers, a TP argument one",
    "tooldata": "a tool is passed by its number, and a call not giving it would leave the routine none to select",
    "speeddata": "a speed is passed as the numbers the routine's moves take, and a call not giving it has none",
    "zonedata": "a zone is passed as the CNT of the routine's corners, and a call not giving it has none",
}
_OPTIONAL_OTHER = "only optional num, bool, string, switch and work object parameters are passed as TP arguments"


@dataclass(frozen=True, slots=True)
class Signature:
    """The AR[n] layout of a routine: required parameters in order, then each optional switch."""

    slots: tuple[Slot, ...]
    copied: frozenset[str] = frozenset()  # upper-case num parameters the routine changes: copied to R[n]
    routine: str = ""  # its name, as declared
    # robtarget parameter (upper case) -> the tool and work object of the first move the routine makes to it
    point_frames: tuple[tuple[str, n.Expr | None, n.Expr | None], ...] = ()
    # upper-case robtarget parameters the routine changes, in their position register: passed by reference
    # (VAR, INOUT), the caller reads the point back after the CALL
    points_changed: frozenset[str] = frozenset()
    fine_zones: frozenset[str] = frozenset()  # upper-case zonedata parameters every call passes fine for: FINE
    # upper-case tooldata parameters passed by reference of which the routine sets the tframe: UTOOL[AR[n]]
    frames_written: frozenset[str] = frozenset()

    @property
    def arguments(self) -> tuple[Slot, ...]:
        """The slots passed as AR[n], in order: every one but the points, a record as its components, an optional
        value after the argument saying whether the call gives it."""
        return tuple(f for s in self.slots if s.kind != "robtarget" or s.optional
                     for f in (s.fields if s.kind in ("record", "speeddata", "zonedata") else
                               (Slot(f"Present({s.name})", "present", optional=True),) if s.kind == "robtarget" else
                               (Slot(f"Present({s.name})", "present", optional=True), s) if s.given_flag else
                               (s,)))  # fmt: skip

    def present(self, name: str) -> str | None:
        """'AR[3]' that Present(name) reads: an optional switch itself, or the argument saying whether an optional
        value is given; None when `name` is neither."""
        kind = self.kind(name)
        if kind == "switch":
            return self.register(name)
        return self.register(presence(name)) if kind in ("num", "bool", "string", "robtarget") else None

    def frames_of(self, name: str) -> tuple[n.Expr | None, n.Expr | None]:
        """(tool, work object) the routine moves to its point `name` with; (None, None) if it only passes it on."""
        return next(((tool, wobj) for key, tool, wobj in self.point_frames if key == name.upper()), (None, None))

    def register(self, name: str) -> str | None:
        """'AR[2]' for the parameter of that name, None if it is not one."""
        for i, slot in enumerate(self.arguments, start=1):
            if slot.key == name.upper():
                return f"AR[{i}]"
        return None

    def kind(self, name: str) -> str | None:
        """The kind of a parameter, or of a record parameter's component ('PART.PASSES')."""
        return next((s.kind for s in (*self.slots, *self.arguments) if s.key == name.upper()), None)

    @property
    def required(self) -> tuple[Slot, ...]:
        """The slots a call gives in order, without a name: every one but the optional ones."""
        return tuple(s for s in self.slots if not s.optional)

    def frame(self, name: str) -> str | None:
        """'AR[1]' when `name` is a tooldata or wobjdata parameter: the frame number the caller passed."""
        return self.register(name) if self.kind(name) in ("tooldata", "wobjdata") else None

    def given_speed(self, expr: n.Expr, motion: str) -> Slot | None:
        """The argument a move at one of the routine's speeddata parameters takes its speed from."""
        if isinstance(expr, n.Name) and self.kind(expr.name) == "speeddata":
            name = f"{expr.name}.{'joint' if motion == 'J' else 'tcp'}".upper()
            return next((s for s in self.arguments if s.key == name), None)
        return None

    def given_corner(self, motion: str, zone: n.Expr, speed: n.Expr, following: n.Expr | None) -> Slot | None:
        """The argument a move through a zone the call decides takes its CNT from."""
        key = CallCorner(motion, zone, speed, following).key
        return next((s for s in self.arguments if s.corner is not None and s.corner.key == key), None)

    def returned(self) -> tuple[Slot, ...]:
        """The parameters passed by reference that the routine changes: the caller reads them back."""
        return tuple(s for s in self.slots if s.by_reference and s.key in self.copied)


def signature(routine: n.Routine, records: dict[str, tuple[tuple[str, str], ...]] | None = None,
              fine: dict[str, bool] | None = None) -> Signature | str:  # fmt: skip
    """The routine's AR[n] layout, or why its parameters cannot be passed as TP arguments.

    `records`: the RECORD types the backup declares, lower-case name -> (component, type) in order.
    `fine`: the zonedata parameters (upper case) calls pass fine for -> whether every call does (fine_given)."""
    records = records or {}
    fine = fine or {}
    required: list[Slot] = []
    switches: list[Slot] = []
    frames_written: set[str] = set()
    for part in split_params(routine.params):
        optional = part.startswith("\\")
        alternatives = part.lstrip("\\").split("|")
        if not optional and len(alternatives) > 1:
            return f"unreadable parameter list: {routine.params}"
        for alternative in alternatives:
            words = alternative.split()
            match = _NAME.search(alternative.strip())
            if len(words) < 2 or match is None:
                return f"unreadable parameter list: {routine.params}"
            name, dims = match.group(1), match.group(2)
            mode = words[0].upper() if words[0].upper() in ("VAR", "PERS", "INOUT") else ""
            type_name = words[-2] if not dims else words[-2].split("{")[0]
            frame = type_name.lower() in ("tooldata", "wobjdata")
            written = False
            if mode in ("VAR", "INOUT") and frame and (changed := _frame_changed(routine, name)):
                if type_name.lower() != "tooldata":
                    return (f"it changes its {type_name} parameter {name} passed by reference ({mode}), `{changed}`: a"
                            " frame is passed by its number, and only what a routine writes in a tool's tframe comes"
                            " back (UTOOL)")  # fmt: skip
                if other := _tframe_only(routine, name):
                    return (f"it changes its tooldata parameter {name} passed by reference ({mode}), `{other}`: a tool"
                            " is passed by its number, and only what the routine writes in its tframe comes back"
                            " (UTOOL)")  # fmt: skip
                written = True
            if dims:
                return f"parameter {name} is an array: TP arguments are single values"
            record = type_name.lower() in records
            if mode and not frame and not record and type_name.lower() not in ("num", "bool", "string", "robtarget"):
                return f"{type_name} parameter {name} is passed by reference ({mode}): only a num or a point is read back"
            if frame and (reason := _frame_uses(routine, name, written)):
                return reason
            if optional:
                kind = type_name.lower()
                if kind in ("wobjdata", "switch", "num", "bool", "string") or (kind == "robtarget" and not mode):
                    # an optional value: an argument saying whether the call gives it, then the value (Present());
                    # a point: in its position register, set by the calls giving it
                    switches.append(Slot(name, kind, optional=True,
                                         by_reference=bool(mode) and kind not in ("wobjdata", "robtarget")))  # fmt: skip
                    continue
                if kind == "robtarget":
                    return f"optional robtarget parameter {name} passed by reference ({mode}): a point does not come back"
                return f"optional {type_name} parameter {name}: {_OPTIONAL_REFUSED.get(kind, _OPTIONAL_OTHER)}"
            elif frame:
                required.append(Slot(name, type_name.lower()))
                if written:
                    frames_written.add(name.upper())
            elif type_name.lower() in ("num", "bool", "string", "robtarget", "speeddata", "zonedata"):
                required.append(Slot(name, type_name.lower(), by_reference=bool(mode)))
            elif type_name.lower() in records:
                fields = _record_fields(routine, name, type_name, records[type_name.lower()])
                if isinstance(fields, str):
                    return fields
                required.append(Slot(name, "record", fields, by_reference=bool(mode)))
            else:
                return f"{type_name} parameter {name}: TP arguments are numbers or text"
    motion = {s.key: s for s in required if s.kind in ("speeddata", "zonedata")}
    if motion:
        found = _motion_fields(routine, motion, fine)
        if isinstance(found, str):
            return found
        required = [replace(s, fields=found[s.key]) if s.key in motion else s for s in required]
    slots = tuple(required + switches)
    arguments = [f for s in slots if s.kind != "robtarget" for f in (s.fields if s.kind in ("speeddata", "zonedata") else (s,))]
    arguments += [s for s in slots if s.given_flag or (s.optional and s.kind == "robtarget")]  # whether given
    if len(arguments) > MAX_ARGS:
        return f"{len(arguments)} parameters: a TP CALL takes at most {MAX_ARGS} arguments"
    kinds = {s.key: s.kind for s in slots}
    copied: set[str] = set()
    points_changed: set[str] = set()  # robtarget parameters it changes: in their position register
    by_reference = {s.key for s in slots if s.by_reference}
    components = {f.key: f.kind for s in slots if s.kind == "record" for f in s.fields}
    for stmt in walk_statements(routine.body):
        if (part := _changed_component(stmt, components)) is not None:  # g.count := ..., Incr g.count
            if components[part] != "num":
                return (f"it changes the {components[part]} component {part.lower()} of its record parameter: only num"
                        " components are copied to registers")  # fmt: skip
            copied.add(part)
            continue
        changed = _changed_by_call(stmt)
        if isinstance(stmt, n.ProcCall) and stmt.name.upper() not in _CHANGING:
            # passed on to a routine that may change it (its own INOUT): the caller reads back what comes back
            for arg in stmt.args:
                if isinstance(arg.value, n.Name) and arg.value.name.upper() in by_reference:
                    key = arg.value.name.upper()
                    if kinds[key] in ("bool", "string"):
                        return (f"it passes its {kinds[key]} parameter {arg.value.name}, passed by reference, on to"
                                f" {stmt.name}, which may change it: only a num is read back from a call")  # fmt: skip
                    (points_changed if kinds[key] == "robtarget" else copied).add(key)
        if changed and changed.upper() in kinds:
            if kinds[changed.upper()] != "num":
                return f"it changes its parameter {changed}: only a whole num parameter can be copied to a register"
            copied.add(changed.upper())
        if isinstance(stmt, n.Assign) and (target := base_name(stmt.target)) and kinds.get(target.upper()) == "robtarget":
            if target.upper() not in {s.key for s in required}:
                return f"it changes its optional robtarget parameter {target}: a point given or not does not come back"
            points_changed.add(target.upper())  # worked out in its position register, as a point of the program
        elif isinstance(stmt, n.Assign) and (target := base_name(stmt.target)) and target.upper() in frames_written:
            continue  # a part of the tframe of a tool passed by its number: written to UTOOL[AR[n]] (frame_writes)
        elif isinstance(stmt, n.Assign) and (target := base_name(stmt.target)) and target.upper() in kinds:
            if kinds[target.upper()] not in ("num", "bool") or not isinstance(stmt.target, n.Name):
                return (f"it changes its parameter {target}: only a whole num or bool parameter can be copied to a"
                        " register")  # fmt: skip
            if kinds[target.upper()] == "bool" and target.upper() not in by_reference:
                return f"it changes its bool parameter {target} passed by value: a bool is copied to a register only to come back"
            copied.add(target.upper())
        elif isinstance(stmt, n.For) and stmt.var.upper() in kinds:
            return f"it uses its parameter {stmt.var} as a FOR variable"
    points = {s.key for s in slots if s.kind == "robtarget"}
    given = {s.key for s in slots if s.kind in ("tooldata", "wobjdata")}

    def fixed(expr: n.Expr | None) -> n.Expr | None:  # a frame the routine is given is not the point's own
        return None if isinstance(expr, n.Name) and expr.name.upper() in given else expr

    frames: dict[str, tuple[n.Expr | None, n.Expr | None]] = {}
    for stmt in walk_statements(routine.body):
        if isinstance(stmt, n.Move):
            for target in (stmt.via_point, stmt.to_point):
                base = target.args[0].value if isinstance(target, n.FuncCall) and target.args else target
                if isinstance(base, n.Name) and base.name.upper() in points:
                    frames.setdefault(base.name.upper(), (fixed(stmt.tool), fixed(stmt.wobj)))
    return Signature(slots, frozenset(copied), routine.name,
                     tuple((key, tool, wobj) for key, (tool, wobj) in frames.items()), frozenset(points_changed),
                     frozenset(key for key, every in fine.items() if every and key in motion),
                     frozenset(frames_written))  # fmt: skip


def fine_given(calls: list[tuple[Signature, n.ProcCall]], is_fine) -> dict[str, dict[str, bool]]:
    """The zonedata parameters calls pass fine for: routine (upper case) -> parameter (upper case) -> whether every
    call that passes a zone known now passes fine. `is_fine(expr)`: True or False, None when not known now (the call
    stays TODO, or is checked when it is written)."""
    seen: dict[str, dict[str, set[bool]]] = {}
    for layout, call in calls:
        positional = [a.value for a in call.args if a.name is None]
        if len(positional) != len(layout.required):
            continue  # stays TODO
        for value, slot in zip(positional, layout.required, strict=True):
            if slot.kind == "zonedata" and value is not None and (found := is_fine(value)) is not None:
                seen.setdefault(layout.routine.upper(), {}).setdefault(slot.key, set()).add(found)
    return {routine: {key: values == {True} for key, values in params.items() if True in values}
            for routine, params in seen.items() if any(True in values for values in params.values())}  # fmt: skip


_CHANGING = frozenset({"INCR", "DECR", "ADD", "CLEAR"})  # instructions that change their first argument


def _frame_changed(routine: n.Routine, name: str) -> str:
    """The first statement assigning a tooldata or wobjdata parameter, or one of its components, as written ("" when
    none does)."""
    for stmt in walk_statements(routine.body):
        if isinstance(stmt, n.Assign) and (base_name(stmt.target) or "").upper() == name.upper():
            return f"{format_expr(stmt.target)} := {format_expr(stmt.value)}"
    return ""


def _tframe_only(routine: n.Routine, name: str) -> str:
    """The first statement setting a tooldata parameter other than in a part of its tframe, as written ("" when
    none does): `t.tframe.trans.z := 120`, `t.tframe := [[0, 0, 120], [1, 0, 0, 0]]` are parts of its tframe."""
    for stmt in walk_statements(routine.body):
        if isinstance(stmt, n.Assign) and (base_name(stmt.target) or "").upper() == name.upper() \
                and not _in_tframe(stmt.target):  # fmt: skip
            return f"{format_expr(stmt.target)} := {format_expr(stmt.value)}"
    return ""


def _in_tframe(expr: n.Expr) -> bool:
    """`t.tframe`, `t.tframe.trans`, `t.tframe.rot`, `t.tframe.trans.z`: a part of a tool's tframe."""
    chain: list[str] = []
    while isinstance(expr, n.Component):
        chain.insert(0, expr.field.upper())
        expr = expr.base
    return isinstance(expr, n.Name) and tuple(chain) in (("TFRAME",), ("TFRAME", "TRANS"), ("TFRAME", "ROT"),
                                                         *(("TFRAME", "TRANS", a) for a in "XYZ"))  # fmt: skip


def _frame_uses(routine: n.Routine, name: str, written: bool = False) -> str:
    """Why a tooldata or wobjdata parameter cannot be passed as its frame number: the routine uses it other
    than as the tool or work object of its moves, or passed on to a routine ("" when it does not). ArgName() of it
    is its name; `written`: a tool whose tframe the routine sets, which it may read too (UTOOL[AR[n]])."""
    other: list[str] = []

    def mine(expr: object) -> bool:
        return isinstance(expr, n.Name) and expr.name.upper() == name.upper()

    def named(node: object) -> bool:  # ArgName(t)
        return isinstance(node, n.FuncCall) and node.name.upper() == "ARGNAME" and len(node.args) == 1 \
            and mine(node.args[0].value)  # fmt: skip

    def visit(node: object) -> None:
        if mine(node):
            other.append(name)
        elif named(node) or (written and isinstance(node, n.Component) and _in_tframe(node) and mine(_root(node))):
            return  # its name, or its tframe the routine sets or reads (UTOOL[AR[n]])
        elif isinstance(node, n.Move):
            for field_name in node.__dataclass_fields__:
                value = getattr(node, field_name)
                if field_name in ("tool", "wobj") and mine(value):
                    continue
                if field_name == "options":  # \WObj?wObj: the work object when the routine was given one
                    value = [a for a in value if not ((a.name or "").upper() == "WOBJ" and mine(a.value))]
                visit(value)
        elif isinstance(node, n.ProcCall):
            visit([a.value for a in node.args if not mine(a.value)])
        elif isinstance(node, tuple | list):
            for item in node:
                visit(item)
        elif hasattr(node, "__dataclass_fields__") and not isinstance(node, n.Span):
            for field_name in node.__dataclass_fields__:
                visit(getattr(node, field_name))

    visit(routine.body)
    return f"its {name} is used other than to move with or to pass on: a frame is passed by its number" if other else ""


def _root(expr: n.Expr) -> n.Expr:
    while isinstance(expr, n.Component | n.Index):
        expr = expr.base
    return expr


def _motion_fields(routine: n.Routine, params: dict[str, Slot], given_fine: dict[str, bool]) -> dict[str, tuple[Slot, ...]] | str:
    """The numbers each speeddata and zonedata parameter is passed as: a speed its TCP speed when linear moves
    take it and its % when joint moves do; then the CNT of each corner it decides (a zone parameter, or the
    speed of a move through a zone written in the routine), but for a zone every call passes fine for (FINE).
    Or why they cannot be passed so: the routine uses them other than as the speed and zone of its MoveJ, MoveL
    and MoveAbsJ."""
    other: list[str] = []

    def mine(expr: object, kind: str | None = None) -> str | None:
        key = expr.name.upper() if isinstance(expr, n.Name) else None
        return key if key in params and (kind is None or params[key].kind == kind) else None

    def visit(node: object) -> None:
        if (key := mine(node)) is not None:
            other.append(params[key].name)
        elif isinstance(node, n.Move):
            for field_name in node.__dataclass_fields__:
                value = getattr(node, field_name)
                if (field_name == "speed" and mine(value, "speeddata")) or (field_name == "zone" and mine(value, "zonedata")):
                    continue
                visit(value)
        elif isinstance(node, tuple | list):
            for item in node:
                visit(item)
        elif hasattr(node, "__dataclass_fields__") and not isinstance(node, n.Span):
            for field_name in node.__dataclass_fields__:
                visit(getattr(node, field_name))

    visit(routine.body)
    if other:
        slot = params[other[0].upper()]
        return f"its {slot.kind} {slot.name} is used other than as the {'speed' if slot.kind == 'speeddata' else 'zone'} of its moves"
    speeds: dict[str, set[str]] = {key: set() for key in params}
    corners: dict[str, list[CallCorner]] = {key: [] for key in params}
    for block in _blocks(routine.body):
        for i, stmt in enumerate(block):
            if not isinstance(stmt, n.Move):
                continue
            speed, zone = mine(stmt.speed, "speeddata"), mine(stmt.zone, "zonedata")
            motion = "J" if stmt.kind in (n.MoveKind.J, n.MoveKind.ABSJ) else stmt.kind.value
            if (speed or zone) and motion not in ("J", "L"):
                return f"Move{motion} at the {'speed' if speed else 'zone'} of a parameter: not measured on the controller"
            if speed:
                speeds[speed].add("joint" if motion == "J" else "tcp")
            fine = isinstance(stmt.zone, n.Name) and stmt.zone.name.upper() == "FINE" or given_fine.get(zone) is True
            if owner := (zone if given_fine.get(zone) is not True else None) or (speed if not fine else None):
                following = next_move(block, i)
                corner = CallCorner(motion, stmt.zone, stmt.speed, following.speed if following else None)
                if corner.key not in {c.key for c in corners[owner]}:
                    corners[owner].append(corner)
    fields = {}
    for key, slot in params.items():
        found = [Slot(f"{slot.name}.{use}", f"speed_{use}") for use in ("tcp", "joint") if use in speeds[key]]
        found += [Slot(f"{slot.name}.cnt{i if i > 1 else ''}", "cnt", corner=c, fine=given_fine.get(key) is False)
                  for i, c in enumerate(corners[key], 1)]  # fmt: skip
        fields[key] = tuple(found)
    return fields


def _blocks(stmts: tuple[n.Stmt, ...]) -> list[tuple[n.Stmt, ...]]:
    """Each block of statements, nested ones included: a corner leads into the next move of its own block."""
    found = [stmts]
    for stmt in stmts:
        match stmt:
            case n.If():
                for branch in stmt.branches:
                    found += _blocks(branch.body)
                found += _blocks(stmt.else_body)
            case n.For() | n.While():
                found += _blocks(stmt.body)
            case n.Test():
                for case in stmt.cases:
                    found += _blocks(case.body)
                found += _blocks(stmt.default or ())
    return found


def _changed_component(stmt: n.Stmt, components: dict[str, str]) -> str | None:
    """'G.COUNT' when the statement changes a component of a record parameter: assigned, changed by Incr,
    Decr, Add or Clear; None otherwise (passed on to a routine's INOUT: TODO where it is passed)."""
    targets: list[n.Expr | None] = []
    if isinstance(stmt, n.Assign):
        targets = [stmt.target]
    elif isinstance(stmt, n.ProcCall):
        targets = [stmt.args[0].value] if stmt.name.upper() in _CHANGING and stmt.args else []
    for target in targets:
        if isinstance(target, n.Component) and isinstance(target.base, n.Name):
            key = f"{target.base.name}.{target.field}".upper()
            if key in components:
                return key
    return None


def _changed_by_call(stmt: n.Stmt) -> str | None:
    """The data an Incr, Decr, Add or Clear changes, as written."""
    if isinstance(stmt, n.ProcCall) and stmt.name.upper() in _CHANGING and stmt.args:
        first = stmt.args[0].value
        return first.name if isinstance(first, n.Name) else None
    return None


def _record_fields(routine: n.Routine, name: str, type_name: str,
                   layout: tuple[tuple[str, str], ...]) -> tuple[Slot, ...] | str:  # fmt: skip
    """The components of a record parameter the routine reads, in the record's order, each a slot of its own;
    or why the record cannot be passed so (the routine uses it whole, or a component is not a number,
    a bool or text)."""
    read: set[str] = set()
    whole = False

    def visit(node: object) -> None:  # every statement and expression of the routine, conditions included
        nonlocal whole
        if isinstance(node, n.Component) and isinstance(node.base, n.Name) and node.base.name.upper() == name.upper():
            read.add(node.field.lower())
        elif isinstance(node, n.Name) and node.name.upper() == name.upper():
            whole = True
        elif isinstance(node, tuple | list):
            for item in node:
                visit(item)
        elif hasattr(node, "__dataclass_fields__") and not isinstance(node, n.Span):
            for field_name in node.__dataclass_fields__:
                visit(getattr(node, field_name))

    visit(routine.body)
    if whole:
        return f"{type_name} parameter {name} is used whole: only its components can be passed as TP arguments"
    fields = []
    for field_name, field_type in layout:
        if field_name not in read:
            continue
        if field_type not in ("num", "bool", "string"):
            return f"{type_name} parameter {name}: its component {field_name} is a {field_type}"
        fields.append(Slot(f"{name}.{field_name}", field_type))
    return tuple(fields)


__all__ = ["MAX_ARGS", "MOTION_ARGUMENTS", "CallCorner", "Signature", "Slot", "fine_given", "presence", "signature"]
