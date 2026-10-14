# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""World zones and the robot's safety: what the FANUC sets up in DCS, never in a TP program.

RAPID sets world zones up with instructions, often in a routine run at power on:

    WZBoxDef \\Inside, shPress, [400,-300,0], [900,300,800];   ! a box, in the world frame
    WZLimSup \\Stat, wzPress, shPress;                          ! the robot stops before entering it
    WZDOSet \\Temp, wzFeeder \\Inside, shFeeder, doInFeeder, 1;  ! an output set while the TCP is in it
    WZDisable wzFeeder;                                          ! a temporary zone switched while running

A FANUC robot has the same functions in its Dual Check Safety (DCS: Cartesian Position Check, Joint Position Check,
the zone's status on a safe output) or its interference check zones, set up on the pendant and validated on the robot.
No TP instruction sets them up: each statement stays TODO, under Blocker.SAFETY, and the commissioning checklist lists
each zone with what the RAPID gives (its shape, its values when known at conversion, what it does), to set up again on
the FANUC. CrossArm converts no safety function, and says so: a zone is redone and validated on the FANUC.

SafeMove (ABB's safety controller) has no RAPID at all: when the backup's system description lists it, or the World
Zones option, the analysis reminds that the safety is to be set up in DCS (`safety_options`).
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr
from crossarm.rapid.walk import walk_statements

SHAPES = {
    "WZBOXDEF": ("box", ("low corner", "high corner")),
    "WZCYLDEF": ("cylinder", ("centre of its base", "radius", "height")),
    "WZSPHDEF": ("sphere", ("centre", "radius")),
    "WZHOMEJOINTDEF": ("joint position", ("joint values", "tolerance per axis")),
    "WZLIMJOINTDEF": ("joint range", ("low joint values", "high joint values")),
}
SWITCHES = {"WZENABLE": "enabled", "WZDISABLE": "disabled", "WZFREE": "removed"}
INSTRUCTIONS = frozenset({*SHAPES, "WZLIMSUP", "WZDOSET", *SWITCHES})

# Options of the ABB system (crossarm.rapid.system_info) whose safety is set up in DCS on the FANUC.
_SAFETY_OPTION = re.compile(r"safemove|world zones?|electronic position switches|safezone", re.IGNORECASE)


def safety_options(options: Iterable[str]) -> list[str]:
    """The options of the ABB system that are safety or world zones ('608-1 World Zones', '1125-2 SafeMove Pro')."""
    return [option for option in options if _SAFETY_OPTION.search(option)]


@dataclass(frozen=True, slots=True)
class WorldZone:
    """One zone the RAPID sets up (or one shape it defines and never installs), for the checklist."""

    name: str  # the wztemporary / wzstationary data, else the shapedata
    shape: str  # 'box', 'cylinder'... ('' when the shape is not defined in the backup)
    inside: bool  # the zone is the inside of the shape (\Inside), else its outside
    values: str  # 'low corner [400,-300,0]; high corner [900,300,800]'
    action: str  # 'the robot stops before entering it', 'doFeeder set to 1 while the TCP is inside', ''
    temporary: bool  # \Temp: switched while running (WZEnable / WZDisable / WZFree)
    switched: tuple[str, ...]  # 'disabled in Feed l.40'
    places: tuple[tuple[str, str, int], ...]  # (module, routine, line) of each statement


def _positional(call: n.ProcCall) -> list[n.Expr]:
    return [a.value for a in call.args if a.name is None and a.value is not None]


def _switches(call: n.ProcCall) -> set[str]:
    return {a.name.upper() for a in call.args if a.name is not None and a.value is None}


def _name(expr: n.Expr | None) -> str:
    return expr.name if isinstance(expr, n.Name) else format_expr(expr) if expr is not None else "?"


def scan(modules: Iterable[n.Module], value_text: Callable[[n.Expr], str]) -> list[WorldZone]:
    """Every world zone of the backup, in the order the RAPID sets them up, from every routine (an event routine of
    a system module included: the checklist is about the cell, not about the programs converted). `value_text`: an
    argument as the checklist shows it (its value when known at conversion, else its RAPID text)."""
    shapes: dict[str, tuple[str, bool, str, tuple[str, str, int]]] = {}
    zones: dict[str, dict] = {}
    switched: dict[str, list[str]] = {}
    for module in modules:
        for routine in module.routines:
            for stmt in walk_statements(routine.body):
                if not isinstance(stmt, n.ProcCall):
                    continue
                name, place = stmt.name.upper(), (module.name, routine.name, stmt.span.line)
                args, switches = _positional(stmt), _switches(stmt)
                if name in SHAPES and args:
                    kind, words = SHAPES[name]
                    values = "; ".join(f"{word} {value_text(arg)}" for word, arg in zip(words, args[1:], strict=False))
                    shapes[_name(args[0]).upper()] = (kind, "OUTSIDE" not in switches, values, place)
                elif name == "WZLIMSUP" and len(args) >= 2:
                    zones[_name(args[0]).upper()] = {
                        "name": _name(args[0]), "shape": _name(args[1]).upper(), "temporary": "TEMP" in switches,
                        "action": "the robot stops before it enters the zone", "place": place}  # fmt: skip
                elif name == "WZDOSET" and len(args) >= 4:
                    where = "before it" if "BEFORE" in switches else "while the TCP is"
                    zones[_name(args[0]).upper()] = {
                        "name": _name(args[0]), "shape": _name(args[1]).upper(), "temporary": "TEMP" in switches,
                        "action": f"{_name(args[2])} set to {format_expr(args[3])} {where} in the zone (the robot does"
                                  " not stop)", "place": place}  # fmt: skip
                elif name in SWITCHES and args:
                    switched.setdefault(_name(args[0]).upper(), []).append(
                        f"{SWITCHES[name]} in {routine.name} l.{stmt.span.line}")
    out, used = [], set()
    for key, zone in zones.items():
        shape = shapes.get(zone["shape"])
        used.add(zone["shape"])
        places = (*((shape[3],) if shape else ()), zone["place"])
        out.append(WorldZone(zone["name"], shape[0] if shape else "", shape[1] if shape else True,
                             shape[2] if shape else f"shape {zone['shape'].lower()} not defined in the backup",
                             zone["action"], zone["temporary"], tuple(switched.get(key, ())), places))  # fmt: skip
    for key, (kind, inside, values, place) in shapes.items():
        if key not in used:  # defined, never installed here: listed all the same
            out.append(WorldZone(key.lower(), kind, inside, values, "", False, (), (place,)))
    return out


def todo_reason(call: n.ProcCall) -> str:
    """Why a world-zone statement stays TODO, naming the zone or shape it is about."""
    args = _positional(call)
    what = f" `{_name(args[0])}`" if args else ""
    return (f"{call.name}{what}: a world zone is set up on the FANUC in DCS (Cartesian or Joint Position Check, the"
            " zone's status on a safe output) or its interference check zones, not by a TP program; CrossArm converts"
            " no safety function: set the zone up again and validate it on the robot (checklist: Safety and world"
            " zones)")


__all__ = ["INSTRUCTIONS", "SHAPES", "SWITCHES", "WorldZone", "safety_options", "scan", "todo_reason"]
