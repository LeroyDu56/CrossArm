# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID PROC parameters -> TP CALL arguments: `Set_Station 3\\Wait;` -> `CALL SET_STATION(3,1)`.

TP passes up to ten untyped values to a program called with CALL NAME(a,b,...), which reads
them as AR[1], AR[2]... and cannot change them. That holds the RAPID parameters passed by
value that TP can represent: `num`, `bool` (1 / 0), `string` (text written in the call, 38
characters at most: ROBOGUIDE refuses 39) and optional switches (1 when given, 0 otherwise).
A routine with any other parameter — a robtarget, a tooldata, one passed by reference (INOUT,
VAR, PERS), an optional num — is not converted, and its calls stay TODO with the reason.

A TP program can keep a string argument (SR[n]=AR[1]) and measure it (STRLEN), but not show it:
MESSAGE takes fixed text. So a TPWrite of a string parameter stays TODO in the routine, while
the routine and its calls are converted.

Every argument is passed on every call, switches included: on a FANUC controller reading an
AR[n] the caller did not pass stops the program, where RAPID's Present() just says FALSE.

A RAPID parameter passed by value is a local copy the routine may change (`Angle:=0;`). AR[n]
cannot be written, so such a num parameter is copied into a register when the program starts,
and the routine works on the register.
"""

import re
from dataclasses import dataclass

from crossarm.rapid import nodes as n
from crossarm.rapid.walk import base_name, walk_statements

MAX_ARGS = 10  # TP CALL takes at most ten arguments
_NAME = re.compile(r"([A-Za-z_]\w*)\s*(\{[^}]*\})?\s*$")


@dataclass(frozen=True, slots=True)
class Slot:
    name: str  # as declared
    kind: str  # "num" | "bool" | "string" | "switch"

    @property
    def key(self) -> str:
        return self.name.upper()


@dataclass(frozen=True, slots=True)
class Signature:
    """The AR[n] layout of a routine: required parameters in order, then each optional switch."""

    slots: tuple[Slot, ...]
    copied: frozenset[str] = frozenset()  # upper-case num parameters the routine changes: copied to R[n]

    def register(self, name: str) -> str | None:
        """'AR[2]' for the parameter of that name, None if it is not one."""
        for i, slot in enumerate(self.slots, start=1):
            if slot.key == name.upper():
                return f"AR[{i}]"
        return None

    def kind(self, name: str) -> str | None:
        return next((s.kind for s in self.slots if s.key == name.upper()), None)


def signature(routine: n.Routine) -> Signature | str:
    """The routine's AR[n] layout, or why its parameters cannot be passed as TP arguments."""
    required: list[Slot] = []
    switches: list[Slot] = []
    for part in re.split(r",|(?=\\)", routine.params):
        part = part.strip()
        if not part:
            continue
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
            if mode:
                return f"parameter {name} is passed by reference ({mode}): TP arguments are values"
            if dims:
                return f"parameter {name} is an array: TP arguments are single values"
            if optional:
                if type_name.lower() != "switch":
                    return f"optional {type_name} parameter {name}: only optional switches are converted"
                switches.append(Slot(name, "switch"))
            elif type_name.lower() in ("num", "bool", "string"):
                required.append(Slot(name, type_name.lower()))
            else:
                return f"{type_name} parameter {name}: TP arguments are numbers or text"
    slots = tuple(required + switches)
    if len(slots) > MAX_ARGS:
        return f"{len(slots)} parameters: a TP CALL takes at most {MAX_ARGS} arguments"
    kinds = {s.key: s.kind for s in slots}
    copied: set[str] = set()
    for stmt in walk_statements(routine.body):
        if isinstance(stmt, n.Assign) and (target := base_name(stmt.target)) and target.upper() in kinds:
            if kinds[target.upper()] != "num" or not isinstance(stmt.target, n.Name):
                return f"it changes its parameter {target}: only a whole num parameter can be copied to a register"
            copied.add(target.upper())
        elif isinstance(stmt, n.For) and stmt.var.upper() in kinds:
            return f"it uses its parameter {stmt.var} as a FOR variable"
    return Signature(slots, frozenset(copied))


__all__ = ["MAX_ARGS", "Signature", "Slot", "signature"]
