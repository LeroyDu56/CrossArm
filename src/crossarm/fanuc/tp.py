# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""In-memory model of a FANUC TP program, independent of the .LS text layout.

Instructions are stored as already-formatted TP text (e.g. "DO[1]=ON",
"UFRAME_NUM=1"): TP has no nested expression grammar worth modelling, and
keeping the text makes the writer trivial to check against controller exports.
Motion lines are structured because their layout differs (see ls_writer).
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Instruction:
    text: str  # "" for an empty line
    # Spaces before ';'. None: the writer's rule (generated programs). A number: exactly
    # what a controller wrote, kept by the parser — observed from 0 to 18, with no rule
    # simple enough to recompute.
    pad: int | None = None


@dataclass(frozen=True, slots=True)
class Motion:
    """J/L/C motion. For C, `via` is the circle point, `target` the end point."""

    kind: str  # "J" | "L" | "C" | "A"
    target: str  # "P[3]" or "PR[1:Home]"
    speed: str  # "50%" | "500mm/sec"
    termination: str  # "FINE" | "CNT50"
    via: str | None = None
    options: str = ""  # what follows the termination, as written: "ACC80", "Offset,PR[2]"...
    pad: int | None = None  # spaces before ';', as for Instruction


Line = Instruction | Motion


@dataclass(frozen=True, slots=True)
class CartesianPosition:
    x: float
    y: float
    z: float
    w: float
    p: float
    r: float
    config: str = "N U T, 0, 0, 0"


@dataclass(frozen=True, slots=True)
class JointPosition:
    joints: tuple[float, ...]  # degrees, J1..J6


@dataclass(frozen=True, slots=True)
class Position:
    """One entry of the /POS section: P[number] for motion group 1."""

    number: int
    uf: int
    ut: int
    value: CartesianPosition | JointPosition


@dataclass(slots=True)
class Attributes:
    """/ATTR block. Defaults are those of a program created with the editor.

    PROG_SIZE / MEMORY_SIZE are recomputed by the controller on load; 0 is what
    offline generators commonly write.
    """

    comment: str = ""
    owner: str = "MNEDITOR"
    created: datetime = field(default_factory=lambda: datetime(2000, 1, 1))
    modified: datetime | None = None  # None: same as created
    prog_size: int = 0
    memory_size: int = 0
    protect: str = "READ_WRITE"
    file_name: str = ""
    default_group: str = "1,*,*,*,*"
    local_registers: str | None = None  # "0,0,0" on recent controllers; absent on older exports
    # Raw /APPL lines, as the program's application declares them. None: no /APPL section;
    # (): an empty one, which some macros have.
    appl: tuple[str, ...] | None = None
    # Task control data and the remaining fixed-looking fields. Exports are not all alike
    # (a STACK_SIZE of 500 is possible), so a parsed program keeps its own values.
    version: int = 0
    stack_size: int = 0
    task_priority: int = 50
    time_slice: int = 0
    busy_lamp_off: int = 0
    abort_request: int = 0
    pause_request: int = 0
    control_code: str = "00000000 00000000"
    # None: the number of /MN lines. Kept from a parsed file, because it is not always that:
    # an export can have LINE_COUNT = 53 over a single line.
    line_count: int | None = None


@dataclass(slots=True)
class Program:
    name: str
    lines: list[Line] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)
    attributes: Attributes = field(default_factory=Attributes)
    macro: bool = False
    # Raw lines after the last numbered /MN line (e.g. two lines of two spaces).
    mn_extra: tuple[str, ...] = ()
