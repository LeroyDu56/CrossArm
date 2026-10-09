# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID AST -> FANUC TP programs.

One TP program is produced per RAPID PROC (with parameters: num, bool and switches only). Each RAPID
statement becomes zero or more TP lines. A statement that cannot be converted
faithfully is never guessed: it becomes a '!TODO' remark in the program and an
entry in the conversion report, with its RAPID line number.

Mapping rules (see the report for the values actually used):
  MoveJ/MoveAbsJ -> J, MoveL -> L, MoveC -> C, target -> local P[n] with /POS data
  robtarget quaternion -> W,P,R        (crossarm.geometry, fixed XYZ angles)
  confdata           -> CONFIG 'F/N U/D T/B, t1, t4, t6' (crossarm.convert.configuration)
  speeddata          -> J: % of joint_speed_ref_mm_s ; L/C: mm/sec
  zonedata           -> FINE / the CNT that rounds the corner as much at that speed (convert.motion)
  wobjdata / tooldata-> UFRAME_NUM / UTOOL_NUM, emitted when they change
  num / bool data    -> R[n] / F[n]      Set/Reset, SetDO -> DO[n]=ON/OFF
  IF/ELSEIF/ELSE     -> IF (...) THEN / ELSE / ENDIF (ELSEIF unrolled into nested IFs)
  FOR                -> FOR R[n]=a TO|DOWNTO b      WHILE -> LBL/JMP loop
  WaitTime           -> WAIT x(sec)      WaitDI/WaitDO/WaitUntil -> WAIT (cond)
  TPWrite "text"     -> MESSAGE[text]    TPErase -> (nothing)   SetGO / GInput -> GO[n]= / GI[n]
  PROC call          -> CALL NAME        Stop -> PAUSE   RETURN -> END   EXIT -> ABORT
  call with num / bool / switch arguments -> CALL NAME(3,1,0), read as AR[n] (crossarm.convert.arguments)
  call to a routine wrapping one move -> that move (crossarm.convert.wrappers)
  IF FALSE / WHILE FALSE (code switched off by hand) -> left out, with a remark
"""

import copy
import dataclasses
import itertools
import math
import re
import traceback
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from crossarm.convert.arguments import MOTION_ARGUMENTS, Signature, fine_given, signature
from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.calls import RoutineCalls
from crossarm.convert.compute import (
    LAYOUTS,
    PREDEFINED,
    Computer,
    Effects,
    MeasuredAtRunTime,
    Typed,
    Unknown,
    Written,
    first_hole,
    fixed_math,
    measured_reason,
    parse_params,
    path_of,
    to_pose,
)
from crossarm.convert.config import ConversionConfig, frame_key
from crossarm.convert.configuration import (
    TOOL_PIN_DEFAULT,
    UnsupportedConfdata,
    fanuc_config,
    fanuc_joints,
    j6_on_turn_boundary,
    tool_on_flange,
)
from crossarm.convert.coverage import Coverage, measure
from crossarm.convert.external import (
    MISSING_WHY,
    Candidate,
    ProvidedProgram,
    ProvidedRoutine,
    arguments_of,
    candidates,
    declared_layout,
    provided_returns,
)
from crossarm.convert.frame_fields import FrameFields
from crossarm.convert.frame_writes import FrameWrites
from crossarm.convert.func_inline import FuncInline, inlined_notes
from crossarm.convert.handlers import OnTimeout, leaves, on_timeout, only_passes_on
from crossarm.convert.handlers import body as handler_body
from crossarm.convert.inline import REAL_CONTROLLER, Inliner
from crossarm.convert.interrupts import GAPS, SINGLE_OPTIONS, Interrupt, arming, called_by, changed_by, connected
from crossarm.convert.interrupts import scan as scan_interrupts
from crossarm.convert.karel_files import CONVERTED as KAREL_FILES
from crossarm.convert.karel_files import INSTRUCTIONS as FILE_INSTRUCTIONS
from crossarm.convert.karel_files import KarelFiles
from crossarm.convert.karel_poses import KarelPoses, karel_candidates, karel_would
from crossarm.convert.karel_poses import place_frames as place_karel_frames
from crossarm.convert.late_calls import LateCalls
from crossarm.convert.motion import corner, next_move
from crossarm.convert.payload import Payload, combined
from crossarm.convert.records import MOTION, SCALARS, Field, Records, nodes, recursive
from crossarm.convert.runtime_points import RuntimePoints, expr_nodes, find_runtime_points
from crossarm.convert.source_map import SourceTags
from crossarm.convert.strings import TEXT_PIECE, Strings, same_regardless_of_case
from crossarm.convert.system_data import SystemData
from crossarm.convert.tp_numbers import NUMBER_TYPES as _NUMBERS
from crossarm.convert.tp_numbers import ascii_text, decimal, fmt_number, operand, register_value
from crossarm.convert.unsupported import (
    RAPID_DATA,
    RAPID_INSTRUCTIONS,
    RoutineUse,
    handles_files_or_sockets,
    no_tp_equivalent,
    text_todo,
)
from crossarm.convert.values import (
    Evaluator,
    Frame,
    JointTarget,
    Load,
    NotInBackup,
    RobTarget,
    Symbols,
    Unresolvable,
    unit_quaternion,
)
from crossarm.convert.wrappers import CallMismatch, MoveRoutine, find_move_routines, parameters
from crossarm.fanuc.tp import (
    Attributes,
    CartesianPosition,
    Instruction,
    JointPosition,
    Motion,
    Position,
    Program,
)
from crossarm.geometry import (
    Pose,
    mat_mul,
    matrix_to_quat,
    matrix_to_wpr,
    rot_x,
    rot_y,
    rot_z,
    wpr_to_matrix,
)
from crossarm.karel import PROGRAMS as KAREL_PROGRAMS
from crossarm.karel import called as karel_called
from crossarm.rapid import nodes as n
from crossarm.rapid.eio import Signal
from crossarm.rapid.to_pseudo import format_expr
from crossarm.rapid.walk import walk_statements

if TYPE_CHECKING:
    from crossarm.convert.setup import FrameSetup
    from crossarm.convert.taught import Taught

REMARK_MAX = 32  # characters after '!' shown on the pendant
MESSAGE_MAX = 24  # MESSAGE[...] text length: longer texts are silently cut by the controller (ROBOGUIDE probe)
REGISTER_COMMENT_MAX = 16
# The options of WaitDI / WaitDO / WaitUntil that only show a message on the FlexPendant while waiting (\Visualize
# and its companions); \UIActiveSignal, which sets an output while the message is shown, is not one of them.
VISUALIZE_OPTIONS = frozenset({"VISUALIZE", "HEADER", "MESSAGE", "MSGARRAY", "ICON", "IMAGE", "VISUALIZETIME"})
WAIT_CLOCK = "WaitTimer"  # the register a wait with a MaxTime reads its TIMER into
TEST_VALUE = "TestValue"  # the register a TEST on anything but a register is selected on
SELECT_INDENT = " " * len("SELECT ")  # a SELECT's next lines, as the controller stores them (ROBOGUIDE)
NO_LOAD_KG = 0.001  # RAPID's load0 / tool0 placeholder mass: no real payload declared

_NEGATED = {"=": "<>", "<>": "=", "<": ">=", ">=": "<", ">": "<=", "<=": ">"}
_ARITHMETIC = {"+", "-", "*", "/", "DIV", "MOD"}
# The data kept in a register: a byte is a whole number from 0 to 255, which R[n] holds as it holds a num.
_SIGNAL_PREFIX = re.compile(r"^[dD][iIoO](?=[_0-9A-Z])")


# ---------------------------------------------------------------------------
# Result objects (consumed by the CLI and the report)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Note:
    program: str  # TP program name ("" for global notes)
    rapid_line: int | None
    kind: str  # "TODO" (not converted) | "WARNING" (converted with an assumption)
    message: str
    category: str = Blocker.OTHER  # the blocker the report groups this note under


@dataclass(frozen=True, slots=True)
class MoveRoutineUse:
    """A routine wrapping a move, as this conversion treated it (see crossarm.convert.wrappers)."""

    name: str
    instruction: str  # "MoveL"...
    calls: int
    converted: bool  # its calls written as the move, or left TODO
    pure: bool  # it does nothing but the move
    also_does: str  # RAPID text of what else it does, shortened ("" when pure)


@dataclass(frozen=True, slots=True)
class PointInfo:
    number: int
    source: str  # RAPID expression
    rapid_line: int
    uf: int
    ut: int
    value: CartesianPosition | JointPosition
    # The position registers the frames were loaded from, when above what the controller holds (FrameInfo.bank):
    # with uf/ut, which frame the point is in (crossarm.convert.taught).
    uf_bank: int | None = None
    ut_bank: int | None = None


@dataclass(frozen=True, slots=True)
class ProgramInfo:
    program: Program
    module: str
    routine: str
    points: tuple[PointInfo, ...]
    # The RAPID line each TP line was written from (crossarm.convert.source_map), None where no statement
    # wrote it; empty for a program no routine was translated into. And the routine's first line.
    sources: tuple[int | None, ...] = ()
    routine_line: int = 0


@dataclass(frozen=True, slots=True)
class Allocation:
    number: int
    rapid_name: str
    fixed: bool  # pinned by the mapping file
    detail: str = ""
    key: str = ""  # what the mapping file names it by when not its RAPID name: Routine.counter, CROSSARM.x


@dataclass(frozen=True, slots=True)
class FrameInfo:
    number: int
    rapid_name: str
    frame: Frame | None
    problem: str = ""
    # Above what the controller holds: kept in PR[bank] (SETUP_FRAMES stores it there) and loaded into
    # UTOOL[slot] / UFRAME[slot] by the programs before each use. None: selected by its own number.
    bank: int | None = None
    slot: int | None = None


@dataclass(frozen=True, slots=True)
class ComputedFrame:
    """A frame the programs compute from fixed values, worked out at conversion time (crossarm.convert.compute).

    SETUP_FRAMES stores it in PR[number]; the programs load it where the RAPID computes it. One register
    per distinct value, whatever frames it is loaded into. `key` is the value as the mapping file pins it.
    """

    key: str  # "x,y,z,w,p,r", 3 decimals
    values: tuple[float, float, float, float, float, float]
    number: int | None  # None: no position register left for it (its loads stay TODO)
    fixed: bool  # pinned by the mapping file
    uses: tuple[tuple[str, str, str, int], ...]  # ("UTOOL" | "UFRAME", RAPID data, TP program, RAPID line)


@dataclass(frozen=True, slots=True)
class GripPayload:
    """A payload schedule GripLoad selects: a tool holding a part, or the tool alone (GripLoad load0)."""

    key: str  # "tool+load", as the mapping file pins it; the tool alone: "tool"
    number: int | None  # None: no schedule left (its GripLoad stay TODO)
    tool: str
    load: str | None  # None: the tool alone, whose schedule is its UTOOL number
    payload: Payload
    fixed: bool  # pinned by the mapping file
    uses: tuple[tuple[str, int], ...]  # (TP program, RAPID line)


@dataclass(frozen=True, slots=True)
class PointArray:
    """An array of points the programs index at run time: SETUP_FRAMES keeps it in consecutive position
    registers from `base`, row after row as RAPID lays it out, and the programs read it as PR[R[n]]."""

    name: str
    dims: tuple[int, ...]
    values: tuple[CartesianPosition, ...]
    base: int | None  # None: no run of free position registers long enough
    fixed: bool  # pinned by the mapping file


@dataclass(frozen=True, slots=True)
class NumberArray:
    """An array of numbers the programs index at run time: SETUP_FRAMES keeps it in consecutive registers from
    `base`, row after row, and the programs read it as R[R[n]]."""

    name: str
    dims: tuple[int, ...]
    values: tuple[float, ...]
    base: int | None  # None: no run of free registers long enough
    fixed: bool  # pinned by the mapping file


@dataclass(frozen=True, slots=True)
class Capacity:
    """How much of one controller resource the conversion needs, against what it holds."""

    resource: str  # "UTOOL", "R", ...
    used: int  # distinct numbers allocated
    highest: int  # highest number allocated
    limit: int | None  # from ConversionConfig.limits; None: not configured (I/O depends on the cell)
    over: tuple[str, ...] = ()  # RAPID names that got a number above the limit
    taken: int = 0  # numbers already used on the controller (ConversionConfig.reserved)

    @property
    def fits(self) -> bool:
        return not self.over


# Motion settings: what FANUC does without them, or where they need a person (see motion_setting()).
_MOTION_SETTINGS = frozenset({"CONFL", "CONFJ", "SINGAREA", "CIRPATHMODE", "ACCSET", "VELSET"})
_INTERRUPTS = frozenset({"IDELETE", "ISIGNALDI", "ISIGNALDO", "ISIGNALGI", "ISIGNALGO", "ISIGNALAI", "ISIGNALAO",
                         "ITIMER", "IPERS", "IWATCH", "ISLEEP", "IENABLE", "IDISABLE", "IERROR"})
# Interrupt instructions left TODO, and why (ISignalDI, ISignalDO and IPers convert: arm()).
_INTERRUPT_GAPS = {
    **GAPS,
    "IENABLE": "RAPID holds the interrupts back while disabled; a condition monitor would lose them",
    "IDISABLE": "RAPID holds the interrupts back while disabled; a condition monitor would lose them",
}
_CHANGING = frozenset({"INCR", "DECR", "ADD", "CLEAR"})  # written as the assignment they make: _as_assignment
NO_GROUP = "*,*,*,*,*"  # DEFAULT_GROUP of a program that moves no robot: a TRAP, a condition program
SR_LIMIT = 25  # string registers of a controller (ROBOGUIDE: SR[26] does not exist)
TEXT_PROGRAM = "CA_TEXT"  # the program loading a text into a string register (crossarm.convert.strings)
TEXT_KEY = "CROSSARM.TEXT"  # its key in the mapping file (programs)
# RAPID text functions CrossArm writes with TP's string instructions (crossarm.convert.strings).
_TEXT_WORK = frozenset({"STRLEN", "STRMATCH", "STRPART", "NUMTOSTR", "VALTOSTR"})
# RAPID functions giving a text: an expression using one is a text, converted or not.
_TEXT_FUNCTIONS = frozenset({"STRPART", "NUMTOSTR", "VALTOSTR", "DNUMTOSTR", "STRMAP", "BYTETOSTR", "ARGNAME",
                             "CTIME", "CDATE", "GETTASKNAME", "GETMECUNITNAME", "ERRSTR", "STRFORMAT"})
PULSE_MAX_S = 25.5  # the longest PULSE a FANUC output takes (ROBOGUIDE: 25.6 is refused, ASBN-092)
PULSE_DEFAULT_S = 0.2  # RAPID PulseDO without \PLength
# Lines after which an array index held in a register is worked out again: the program may arrive there from
# elsewhere, or a called program change any register. A line writing a register only drops the indices it reads.
_CHANGES_INDEX = ("LBL[", "CALL ", "FOR ", "ENDFOR", "ELSE", "ENDIF", "SELECT ", "JMP ", "END")
_WRITES_REGISTER = re.compile(r"R\[(\d+)")


def _reads(operands: Iterable[str]) -> set[int] | None:
    """The registers an index is worked out from; None if it reads an input, which changes by itself."""
    if any(not re.fullmatch(r"\(?-?[\d.]+\)?|R\[\d+(:[^\]]*)?\]|AR\[\d+\]", o) for o in operands):
        return None
    return {int(m[1]) for o in operands for m in [_WRITES_REGISTER.match(o)] if m}
# SearchL: how it stops, and the input level its skip condition waits for, with whether RAPID searches for a
# change of the input (an error when the input is at that level at the start).
_SEARCH_STOPS = frozenset({"STOP", "PSTOP", "SSTOP"})
_SEARCH_LEVELS = {"POSFLANK": ("ON", True), "NEGFLANK": ("OFF", True), "HIGHLEVEL": ("ON", False),
                  "LOWLEVEL": ("OFF", False)}  # fmt: skip
# mm/s: a move with a skip latching the position (PR[k]=LPOS) keeps its speed up to this; faster, the controller
# slows it down to about this (ROBOGUIDE: 120 and 250 mm/s run at the speed of 100, the manual says 250)
SKIP_SPEED_MAX = 100
SKIP_OVERSHOOT = "6.4 mm past at 50 mm/s"  # where a skip stops before coming back (ROBOGUIDE, R-1000iA/80F)
# Moves setting an output when the robot is on the point: written as the move, then the output.
_SET_ON_ARRIVAL = frozenset({"MOVELDO", "MOVEJDO", "MOVECDO"})
PAYLOAD_SCHEDULES = 10  # PAYLOAD[1-10] on a standard controller (ROBOGUIDE: PAYLOAD[11] loads, stops when run)
# Where the tool is among the unnamed arguments of the instructions that move with one besides MoveX.
_TOOL_ARGUMENT = {"MOVELDO": 3, "MOVEJDO": 3, "MOVECDO": 4, "MOVELAO": 3, "MOVEJAO": 3, "MOVECAO": 4,
                  "MOVELGO": 3, "MOVEJGO": 3, "MOVECGO": 4, "TRIGGL": 4, "TRIGGJ": 4, "TRIGGC": 5,
                  "SEARCHL": 4, "SEARCHJ": 4, "SEARCHC": 5}  # fmt: skip


def _bare(register: str) -> str:
    """R[12] for R[12:name]: a speed or a CNT in a register is written without its comment, as measured."""
    return register.split(":", 1)[0] + "]" if ":" in register else register


@dataclass(frozen=True)
class ZoneUse:
    """How a RAPID zone was written at one speed: the CNT, and the corner cuts it was matched on."""

    tp: str  # FINE or CNTn
    abb_cut: float | None = None  # mm: how close the RAPID move comes to the corner (zone_mapping "measured")
    fanuc_cut: float | None = None  # mm: how close the FANUC one does with that CNT
    capped: bool = False  # CNT100 rounds less than the RAPID zone


@dataclass
class ConversionResult:
    programs: list[ProgramInfo] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    registers: list[Allocation] = field(default_factory=list)
    flags: list[Allocation] = field(default_factory=list)
    string_registers: list[Allocation] = field(default_factory=list)  # SR keeping the strings the programs change
    digital_outputs: list[Allocation] = field(default_factory=list)
    digital_inputs: list[Allocation] = field(default_factory=list)
    group_outputs: list[Allocation] = field(default_factory=list)
    group_inputs: list[Allocation] = field(default_factory=list)
    analog_outputs: list[Allocation] = field(default_factory=list)
    timers: list[Allocation] = field(default_factory=list)  # RAPID clocks
    grip_payloads: list[GripPayload] = field(default_factory=list)  # schedules GripLoad selects
    point_registers: list[Allocation] = field(default_factory=list)  # PR a robtarget argument is passed in
    point_arrays: list[PointArray] = field(default_factory=list)  # arrays of points indexed at run time
    number_arrays: list[NumberArray] = field(default_factory=list)  # arrays of numbers indexed at run time
    flag_arrays: list[NumberArray] = field(default_factory=list)  # arrays of bools, in consecutive flags (1.0 = ON)
    uframes: list[FrameInfo] = field(default_factory=list)
    utools: list[FrameInfo] = field(default_factory=list)
    computed_frames: list[ComputedFrame] = field(default_factory=list)  # in the order the programs first load them
    speeds: dict[tuple[str, str], str] = field(default_factory=dict)  # (RAPID speed, motion) -> TP
    # (zone, speed, motion, speed of the next move when faster, else "") -> TP
    zones: dict[tuple[str, str, str, str], "ZoneUse"] = field(default_factory=dict)
    skipped_routines: list[tuple[str, str, str]] = field(default_factory=list)  # module, routine, reason
    capacity: list[Capacity] = field(default_factory=list)
    shared_with: list[str] = field(default_factory=list)  # other tasks numbered from the same R/F/I/O tables
    move_routines: list[MoveRoutineUse] = field(default_factory=list)  # the called ones, most called first
    inlined: Counter[str] = field(default_factory=Counter)  # bool FUNC -> conditions written as its test
    from_system: list[str] = field(default_factory=list)  # Module.Routine of system modules written: called
    wait_clock: tuple[str, str] | None = None  # (TIMER[n], R[m]) timing the waits with a MaxTime, when used
    setup: "FrameSetup | None" = None  # the program that sets the frames on the robot (set by the pipeline)
    coverage: Coverage = field(default_factory=lambda: Coverage(()))  # instructions converted, by area
    # Records kept field by field (crossarm.convert.records): data -> (registers, flags) its fields take.
    records: dict[str, tuple[int, int]] = field(default_factory=dict)
    # The program loading a text into a string register (crossarm.convert.strings), when one is.
    text_program: str | None = None
    # The TP name of each program written that other programs call or arm, by its key in the mapping file
    # (programs): a routine's name, an interrupt's (its relay INTERRUPT.relay), CROSSARM.TEXT.
    program_keys: dict[str, str] = field(default_factory=dict)
    # The RAPID source of each module, by upper-case module name: the report shows it next to the TP.
    rapid_sources: dict[str, list[str]] = field(default_factory=dict)
    # Routines the integrator provides as TP or KAREL programs (external_routines, crossarm.convert.external): what
    # each program has to do and where it is called; and the routines CrossArm could not write, which may be.
    provided: list[ProvidedProgram] = field(default_factory=list)
    provided_candidates: list[Candidate] = field(default_factory=list)
    # The positions taught on the robot kept, or not, from an earlier conversion (crossarm.convert.taught; set by the
    # pipeline when asked: --keep-taught).
    taught: "Taught | None" = None
    # --karel: the programs of CrossArm's KAREL library the programs call (crossarm.karel). Without it: how many
    # TODO it would convert (karel_would()).
    karel_programs: list[str] = field(default_factory=list)
    karel_todo: int = 0

    @property
    def todo_count(self) -> int:
        return sum(1 for note in self.notes if note.kind == "TODO")

    def payloads(self) -> list[FrameInfo]:
        """Tools carrying a declared load: more than the 1 g RAPID puts in its load0 placeholder."""
        return [f for f in self.utools if f.frame and f.frame.load and f.frame.load.mass > NO_LOAD_KG]

    def unknown_payloads(self) -> list[FrameInfo]:
        """Tools built at run time: their load is not known either."""
        return [f for f in self.utools if f.frame is None]

    def grouped(self, kind: str) -> list[tuple[str, int, str]]:
        """Notes of that kind by category, most frequent first: (category, count, most common message).

        This is what turns several hundred TODO lines into the handful of jobs
        that actually stand between the backup and a running program.
        """
        counts: dict[str, Counter[str]] = defaultdict(Counter)
        for note in self.notes:
            if note.kind == kind:
                counts[note.category][note.message.split(" — `")[0]] += 1
        ranked = sorted(counts.items(), key=lambda kv: -sum(kv[1].values()))
        return [(category, sum(msgs.values()), msgs.most_common(1)[0][0]) for category, msgs in ranked]

    def clean_programs(self) -> int:
        """Programs converted without a single TODO."""
        with_todo = {note.program for note in self.notes if note.kind == "TODO"}
        return sum(1 for info in self.programs if info.program.name not in with_todo)


# ---------------------------------------------------------------------------
# Number allocation
# ---------------------------------------------------------------------------


class NumberTable:
    """RAPID name -> FANUC number: pinned by the user, else allocated in order of first use,
    skipping the numbers already used on the controller (`reserved`).

    `defer`: while a statement CrossArm converts only since texts are kept in string registers is written,
    what it numbers first gets a placeholder (_DEFERRED and up), numbered by finish(): the programs without
    texts keep the numbers they had. Asked for again by another statement, it gets its number there."""

    def __init__(self, fixed: dict[str, int], first: int, reserved: Iterable[int] = ()) -> None:
        self.fixed = fixed
        self.first = first
        self.reserved = frozenset(reserved)
        self.skip: set[int] = set()  # taken by CrossArm for its own use (the TIMER timing the waits)
        self.assigned: dict[str, Allocation] = {}
        self.by_name: set[int] = set()  # numbers a keyed register took from its RAPID name (1.0-1.2 files)
        self.defer = False
        self.pending: dict[str, int] = {}  # key -> placeholder, while deferred
        self.resolved: dict[int, int] = {}  # placeholder -> number
        self._next = _DEFERRED + 1000 * next(_TABLES)  # this table's placeholders

    def number(self, name: str, key: str | None = None, detail: str = "", after_pinned: bool = False,
               top: int | None = None) -> int:  # fmt: skip
        """`after_pinned`: a number past every one the mapping file pins, when it does not pin this one (a
        field of a record: a mapping file written before records were converted never names it). `top`: the
        highest free number up to it instead of the lowest (the scratch string registers).

        `key` tells apart what shares a RAPID name: the FOR counter `i` of each routine (`MAIN.i`), the
        registers CrossArm uses itself (`CROSSARM.TESTVALUE`). The mapping file names those by their key.

        Mapping files written by 1.0 to 1.2 named them by their RAPID name only: such a name still pins its
        number, to the first register of that name, so that a file given back gives the numbers it gave.
        """
        given, key = key, (key or name).upper()
        if key in self.pending and not self.defer:  # first used where it was deferred: numbered here, as before
            placeholder = self.pending.pop(key)
            del self.assigned[key]
            self.resolved[placeholder] = number = self.number(name, given, detail, after_pinned, top)
            return number
        if key in self.assigned:
            return self.assigned[key].number
        taken = {a.number for a in self.assigned.values()}
        old = name.upper()
        if key in self.fixed and not (key == old and self.fixed[key] in self.by_name):
            number, fixed = self.fixed[key], True
        elif key != old and old in self.fixed and self.fixed[old] not in taken:
            number, fixed = self.fixed[old], True
            self.by_name.add(number)
        elif self.defer:
            self.pending[key] = number = self._next
            self._next += 1
            self.assigned[key] = Allocation(number, name, False, detail, given if given and key != old else "")
            return number
        else:
            used = set(self.fixed.values()) | {a.number for a in self.assigned.values()} | self.reserved | self.skip
            number, fixed = self.first, False
            if after_pinned and self.fixed:
                number = max(self.first, max(self.fixed.values()) + 1)
            step = 1
            if top is not None:
                number, step = top, -1
            while number in used:
                number += step
        self.assigned[key] = Allocation(number, name, fixed, detail, given if given and key != old else "")
        return number

    def release(self, key: str) -> None:
        """Give a number back: one past what the controller holds, not used after all."""
        self.assigned.pop(key.upper(), None)

    def finish(self, top: int | None) -> dict[int, int]:
        """Number what only deferred statements use: from `top` down (what the controller holds), so that the
        numbers of the tasks converted next stay the same; past the others when the count is not known.
        Returns placeholder -> number, for every placeholder numbered so far."""
        for key, placeholder in list(self.pending.items()):
            allocation = self.assigned.pop(key)
            del self.pending[key]
            self.resolved[placeholder] = self.number(allocation.rapid_name, allocation.key or None, allocation.detail,
                                                     top=top)  # fmt: skip
        return dict(self.resolved)

    def allocations(self) -> list[Allocation]:
        return sorted(self.assigned.values(), key=lambda a: a.number)


_DEFERRED = 100_000_000  # placeholders of numbers deferred (NumberTable.defer): 9 digits and more
_TABLES = itertools.count()
_PLACEHOLDER = re.compile(r"(?<=\[)\d{9,}(?=[\]:])")


class TableView:
    """One task's window on a NumberTable shared by the whole controller.

    Numbers come from the shared table, so two tasks never get the same number for
    different data, and the same name (a PERS shared between tasks, one physical signal)
    gets the same number in both. allocations() lists only what this task used, so each
    task's report and mapping file stay about that task.
    """

    def __init__(self, table: NumberTable) -> None:
        self.table = table
        self.keys: set[str] = set()

    @property
    def fixed(self) -> dict[str, int]:
        return self.table.fixed

    @property
    def reserved(self) -> frozenset[int]:
        return self.table.reserved

    def number(self, name: str, key: str | None = None, detail: str = "", after_pinned: bool = False,
               top: int | None = None) -> int:  # fmt: skip
        self.keys.add((key or name).upper())
        return self.table.number(name, key, detail, after_pinned, top)

    def release(self, key: str) -> None:
        self.keys.discard(key.upper())
        self.table.release(key)

    def finish(self, top: int | None) -> dict[int, int]:
        return self.table.finish(top)

    def allocations(self) -> list[Allocation]:
        return sorted((a for k, a in self.table.assigned.items() if k in self.keys), key=lambda a: a.number)


@dataclass
class ControllerScope:
    """What is global to one FANUC controller: registers, flags, I/O and program names.

    An ABB backup is one controller. On FANUC, R[], F[] and the I/O are shared by every
    program it runs, motion or background, and all its programs live in one name space:
    loading a second MAIN.LS replaces the first. So all tasks of a backup are converted
    against one instance, which also starts with the names of the programs already on
    the target robot. Frames are not in it: each robot of a multi-robot cell has its own.
    """

    registers: NumberTable
    flags: NumberTable
    douts: NumberTable
    dins: NumberTable
    gouts: NumberTable
    gins: NumberTable
    aouts: NumberTable
    timers: NumberTable
    program_names: set[str] = field(default_factory=set)  # TP names taken: on the robot, or by a task
    existing_programs: frozenset[str] = frozenset()  # of which: already on the target robot
    given_programs: set[str] = field(default_factory=set)  # of which: given to a program of this conversion
    # What the programs of every task can change: a PERS is shared by all tasks (crossarm.convert.compute).
    # None: only the task being converted is known.
    written: Written | None = None
    strings: NumberTable | None = None  # SR[n]; None: made from the configuration when first needed
    # The first register of each PERS array of numbers kept in registers: the tasks share a PERS, and so its block.
    array_bases: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_config(cls, cfg: ConversionConfig, existing_programs: Iterable[str] = ()) -> "ControllerScope":
        taken = {resource: numbers.keys() for resource, numbers in cfg.reserved.items()}
        existing = frozenset(name.upper() for name in existing_programs)
        return cls(
            NumberTable(cfg.registers, cfg.first_register, taken.get("R", ())),
            NumberTable(cfg.flags, cfg.first_flag, taken.get("F", ())),
            NumberTable(cfg.digital_outputs, cfg.first_digital_output, taken.get("DO", ())),
            NumberTable(cfg.digital_inputs, cfg.first_digital_input, taken.get("DI", ())),
            NumberTable(cfg.group_outputs, cfg.first_group_output, taken.get("GO", ())),
            NumberTable(cfg.group_inputs, cfg.first_group_input, taken.get("GI", ())),
            NumberTable(cfg.analog_outputs, cfg.first_analog_output, taken.get("AO", ())),
            NumberTable(cfg.timers, cfg.first_timer, taken.get("TIMER", ())),
            set(existing),
            existing,
            strings=NumberTable(cfg.string_registers, cfg.first_string_register, taken.get("SR", ())),
        )


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def remark_lines(text: str) -> list[str]:
    """A RAPID comment -> one or more TP remarks of at most 32 characters."""
    text = ascii_text(text).rstrip()
    if len(text) <= REMARK_MAX:
        return ["!" + text]
    chunks, current = [], ""
    for word in text.split(" "):
        while len(word) > REMARK_MAX:  # a single very long word, e.g. "!=========="
            if current:
                chunks.append(current)
                current = ""
            chunks.append(word[:REMARK_MAX])
            word = word[REMARK_MAX:]
        candidate = f"{current} {word}" if current else word
        if len(candidate) > REMARK_MAX:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return ["!" + c for c in chunks]


def suffixed(base: str, taken: set[str] | frozenset[str], max_length: int) -> str:
    """base, or base with a suffix (_2, _3...) while that name is taken."""
    candidate, suffix = base, 1
    while candidate in taken:
        suffix += 1
        candidate = f"{base[: max_length - len(str(suffix)) - 1]}_{suffix}"
    return candidate


def tp_program_name(name: str, max_length: int) -> str:
    cleaned = re.sub(r"[^A-Z0-9_]", "_", ascii_text(name).upper())
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "P" + cleaned
    return cleaned[:max_length]


def round_half_up(value: float) -> int:
    """12.5 -> 13 as on a calculator (Python's round() gives 12: banker's rounding)."""
    return math.floor(value + 0.5)


def fmt_seconds(value: float) -> str:
    """Controller layout for WAIT times: width 6, 2 decimals, no leading zero ('   .30')."""
    text = f"{value:6.2f}"
    return text.replace(" 0.", "  .", 1) if abs(value) < 1 else text


def _comment(name: str) -> str:
    return ascii_text(name)[:REGISTER_COMMENT_MAX].replace("]", ")")


# Writing a frame, a position or a payload at run time is a different job from writing an ordinary
# record field: each has its own blocker, told by the data's type or, failing that, by the field.
_FRAME_TYPES = frozenset({"tooldata", "wobjdata"})
_POSITION_TYPES = frozenset({"robtarget", "jointtarget", "pose", "pos", "orient", "confdata", "robjoint", "extjoint"})
_FRAME_FIELDS = frozenset({"tframe", "uframe", "oframe", "robhold"})
_POSITION_FIELDS = frozenset({"trans", "rot", "robconf", "robax", "extax"})


def _type_blocker(type_name: str | None) -> str:
    """The blocker of an assignment to a whole data of that type."""
    if type_name in _FRAME_TYPES:
        return Blocker.RUNTIME_FRAME
    if type_name in _POSITION_TYPES:
        return Blocker.RUNTIME_POSITION
    return Blocker.PAYLOAD if type_name == "loaddata" else Blocker.VALUE


def _assign_blocker(target: n.Expr, type_of) -> str:
    """Any field of the chain counts: 'tool.tload.mass' changes a payload, 'p.trans.x' a position."""
    fields = set()
    while isinstance(target, n.Component | n.Index):
        if isinstance(target, n.Component):
            fields.add(target.field.lower())
        target = target.base
    root = type_of(target.name) if isinstance(target, n.Name) else None
    if "tload" in fields or root == "loaddata":
        return Blocker.PAYLOAD
    if root in _FRAME_TYPES or fields & _FRAME_FIELDS:
        return Blocker.RUNTIME_FRAME
    if root in _POSITION_TYPES or fields & _POSITION_FIELDS:
        return Blocker.RUNTIME_POSITION
    return Blocker.RECORD


# ---------------------------------------------------------------------------
# Converter (shared state across programs)
# ---------------------------------------------------------------------------


class Converter:
    def __init__(
        self,
        modules: list[n.Module],
        config: ConversionConfig | None = None,
        sources: dict[str, str] | None = None,
        signals: dict[str, Signal] | None = None,
        shared: ControllerScope | None = None,
    ) -> None:
        """`sources` (module name -> RAPID text) lets TODO entries quote the original line.
        `signals` (from EIO.cfg, upper-cased names) gives the real type of each I/O signal.
        `shared`: the controller's registers, flags and I/O, when other tasks of the same
        backup are converted too; None for a conversion on its own."""
        self.modules = modules
        self.config = config or ConversionConfig()
        self.eio = signals or {}
        self.source_lines = {name.upper(): text.splitlines() for name, text in (sources or {}).items()}
        self.symbols = Symbols.from_modules(modules)
        self.evaluator = Evaluator(self.symbols)
        cfg = self.config
        shared = self.shared = shared or ControllerScope.from_config(cfg)
        self.computer = Computer(modules, self.symbols, shared.written or Written.of(modules))
        self.records = Records(modules, self.symbols, self.computer.layouts, self.computer.written,
                               self._fixed_value, Written.of(modules) if shared.written else None)  # fmt: skip
        self.recursive = recursive(modules)  # routines that can call themselves back: no record of their own
        self.strings = Strings(modules, self.symbols, self.computer.written, self._fixed_value,
                               Written.of(modules) if shared.written else None)  # fmt: skip
        self.effects = Effects(modules)
        # Frames computed at conversion time: value key -> uses; each use is (kind, RAPID data, program, line,
        # statement), and a program line loading it reads `PR[{CF:use}]` until its register is known (convert()).
        self.computed: dict[str, list[int]] = {}
        self.computed_uses: list[tuple[str, str, str, int, n.Stmt, tuple[float, ...]]] = []
        # GripLoad: (tool, or None for the task's one tool; load name, or None to release; its value; program;
        # RAPID line; statement). A program line selecting it reads `PAYLOAD[{PL:use}]` until _place_payloads().
        self.payload_uses: list[tuple[n.Expr | None, str | None, Load | None, str, int, n.Stmt]] = []
        # Position registers robtarget arguments are passed in: upper-cased "ROUTINE.PARAMETER" -> as written.
        # Program lines read `PR[{PA:KEY}]` until _place_points() numbers them.
        self.point_keys: dict[str, str] = {}
        # Arrays of points indexed at run time: upper-cased name -> (name, dims, values). Lines read
        # `{PB:NAME:k}` for their first register plus k until _place_points() numbers them.
        self.arrays: dict[str, tuple[str, tuple[int, ...], tuple[CartesianPosition, ...]]] = {}
        # Arrays of numbers indexed at run time, likewise: `{RB:NAME:k}` until _place_number_arrays().
        self.number_arrays: dict[str, tuple[str, tuple[int, ...], tuple[float, ...]]] = {}
        # Arrays of bools the programs change or index at run time: `{FB:NAME:k}` until _place_number_arrays().
        self.flag_arrays: dict[str, tuple[str, tuple[int, ...], tuple[float, ...]]] = {}
        self.array_statements: dict[str, set[int]] = {}  # array -> id() of the statements reading or writing it
        self.shared_arrays: set[str] = set()  # arrays of numbers that are PERS of the task: one block for all tasks
        self.frames_in_moves: dict[str, set[str]] = {"UF": set(), "UT": set()}  # upper-case names, _plan_slots
        self.registers = TableView(shared.registers)
        self.flags = TableView(shared.flags)
        self.douts = TableView(shared.douts)
        self.dins = TableView(shared.dins)
        self.gouts = TableView(shared.gouts)
        self.gins = TableView(shared.gins)
        self.aouts = TableView(shared.aouts)
        self.timers = TableView(shared.timers)
        if shared.strings is None:
            shared.strings = NumberTable(cfg.string_registers, cfg.first_string_register,
                                         cfg.reserved.get("SR", {}).keys())  # fmt: skip
        self.texts = TableView(shared.strings)
        self.text_over: dict[str, str] = {}  # strings no string register is left for: name -> where first
        self.trap_side: set[str] = set()  # routines a TRAP runs: scratch string registers of their own
        self.both_sides: set[str] = set()  # ... that the programs also call
        self.scratch_texts: set[str] = set()  # the scratch string registers, as the programs write them
        # Frames are per robot: each task starts its own.
        taken = {resource: numbers.keys() for resource, numbers in cfg.reserved.items()}
        self.uframes = NumberTable(cfg.uframes, cfg.first_uframe, taken.get("UFRAME", ()))
        self.utools = NumberTable(cfg.utools, cfg.first_utool, taken.get("UTOOL", ()))
        self.frames: dict[tuple[str, int], FrameInfo] = {}
        self.slots: dict[str, int] = {}  # "UT" / "UF" -> the number frames above the limit are loaded into
        self._banks, _ = self.config.free_position_registers()
        self._banks = self._banks[1:]  # the first free one is SETUP_FRAMES' scratch register
        self.written_registers: set[int] = set()  # assigned or used as FOR variable
        self.result = ConversionResult()
        self.result.rapid_sources = self.source_lines
        self._warned: set[str] = set()
        self.inlined: list[tuple[str, str, int]] = []  # FUNC copied into a call: (FUNC, program, line), func_inline
        self.inline_texts: dict[int, str] = {}  # id of a statement made by func_inline: its RAPID text
        self.do_names, self.di_names = self._signals_by_usage()
        self.program_names: dict[str, str] = {}  # routine (upper) -> TP name, set by convert()
        self.move_routines = find_move_routines(modules)
        # PROCs with parameters: their AR[n] layout, or why they cannot be converted.
        records = {name: fields for name, fields in self.computer.layouts.layouts.items() if name not in LAYOUTS}
        self.signatures: dict[str, Signature | str] = {
            r.name.upper(): signature(r, records) for m in modules for r in m.routines if r.kind == "PROC" and r.params
        }
        # A zone some calls pass fine for: the routine writes its moves through it FINE, or both ways.
        calls = [(layout, stmt) for m in modules for r in m.routines for stmt in walk_statements(r.body)
                 if isinstance(stmt, n.ProcCall) and isinstance(layout := self.signatures.get(stmt.name.upper()), Signature)]
        for name, fine in fine_given(calls, self._fine_now).items():  # fmt: skip
            routine = next(r for m in modules for r in m.routines if r.kind == "PROC" and r.name.upper() == name)
            self.signatures[name] = signature(routine, records, fine)
        self.procs = {r.name.upper(): r for m in modules for r in m.routines if r.kind == "PROC"}
        # Routines the integrator provides as programs (external_routines): upper-case name -> the entry, its
        # record in the result; RAPID's own instructions are not routines (said once, left alone).
        self.externals: dict[str, ProvidedRoutine] = {}
        self.provided: dict[str, ProvidedProgram] = {}
        self.not_written: set[str] = set()  # of which: routines this task would have written
        self._provided_entries(modules)
        self.routine_use = RoutineUse(self.procs | self.computer.functions, self.externals,
                                      KAREL_FILES if self.config.karel else (), self.config.karel)
        self.move_routine_calls: Counter[str] = Counter()
        # Interrupts (crossarm.convert.interrupts): upper-case intnum -> what the programs do with it, set by
        # convert(); the WHEN conditions each is armed on; the data a TRAP changes, never taken as known.
        self.interrupts: dict[str, Interrupt] = {}
        self.conditions: dict[str, list[str]] = {}
        self.volatile: set[str] = set()
        self.no_group: set[str] = set()  # routines a TRAP calls: written without a motion group
        self.watched: dict[str, str] = {}  # IPers interrupt (upper) -> the register it watches, as armed
        # Points the programs work out at run time, kept in position registers: 'NAME' for module data,
        # 'ROUTINE.NAME' for a routine's own (runtime_points()).
        self.runtime_points: dict[str, str] = {}  # -> 'robtarget' or 'jointtarget'
        self.not_converted: set[int] = set()  # id() of the statements that ended up in a TODO, for coverage
        self.record_uses: dict[str, tuple[set[int], set[int]]] = {}  # record data -> its registers, flags
        self.parameters: set[str] = set()  # of the routine being translated (upper case)
        self.inliner = Inliner(modules, self._const_bool, self._inlined,
                               lambda name: self.symbols.is_local(name) or name.upper() in self.parameters,
                               self._const_field)  # fmt: skip

    def _provided_entries(self, modules: list[n.Module]) -> None:
        """The routines of external_routines this backup has or calls: what each program has to do."""
        declared = {r.name.upper(): (m, r) for m in reversed(modules) for r in m.routines}
        existing = self.shared.existing_programs
        for key, entry in self.config.external_routines.items():
            module, routine = declared.get(key, (None, None))
            if routine is None and key in RAPID_INSTRUCTIONS:
                self.note("", None, "WARNING", f"external_routines names {entry.name}, an instruction of RAPID, not a"
                                               " routine: left out", Blocker.OTHER)  # fmt: skip
                continue
            if routine is not None and routine.kind == "TRAP":
                self.note("", None, "WARNING", f"external_routines names {routine.name}, a TRAP: an interrupt runs it,"
                                               " no program calls it: left out", Blocker.OTHER)  # fmt: skip
                continue
            self.externals[key] = entry
            use = ProvidedProgram(
                routine.name if routine is not None else entry.name, entry.program,
                module.name if module is not None else None,
                f"{routine.kind} {routine.name}({routine.params})" if routine is not None else "", "",
                function=routine.kind == "FUNC" if routine is not None else entry.returns is not None,
                returns=provided_returns(routine, entry),
                on_robot=entry.program in existing if existing else None,
            )  # fmt: skip
            if routine is not None and routine.kind in ("PROC", "FUNC"):
                layout = declared_layout(routine, 1 if routine.kind == "FUNC" else 0)
                if isinstance(layout, str):
                    use.problem = layout
                else:
                    use.layout = layout
                    use.arguments = arguments_of(layout, True, use.returns)
            self.provided[key] = use

    def _fine_now(self, expr: n.Expr) -> bool | None:
        """Whether a zone passed to a routine is fine, None when it is not known before the programs are written."""
        try:
            return self.evaluator.zone(expr).fine
        except (Unresolvable, TypeError, ValueError):
            return None

    # -- entry point -------------------------------------------------------

    def convert(self, routines: list[str] | None = None, program_modules: set[str] | None = None) -> ConversionResult:
        """`program_modules` (upper-case names): only their routines become programs, the other
        modules are data. Default: every module without the SYSMODULE attribute."""
        wanted = {r.upper() for r in routines} if routines else None
        everything = [r for m in self.modules for r in m.routines]
        self.interrupts = scan_interrupts(everything, self.procs, set(self.move_routines))
        self.runtime_points = find_runtime_points(self, everything)
        if self.config.karel:  # the library's programs: a routine of the same name is renamed
            self.shared.program_names.update(KAREL_PROGRAMS)
        selected: list[tuple[n.Module, n.Routine]] = []
        skipped: list[n.Routine] = []
        for module in self.modules:
            if program_modules is not None:
                is_system = module.name.upper() not in program_modules
            else:
                is_system = "SYSMODULE" in module.attributes
            for routine in module.routines:
                if wanted is not None:
                    if routine.name.upper() not in wanted:
                        continue
                elif is_system:
                    continue  # system modules: data and utilities, converted only on request
                if routine.name.upper() in self.externals:
                    self.not_written.add(routine.name.upper())
                    continue  # the integrator provides it (external_routines): not written
                reason = self._skip_reason(routine, self.signatures.get(routine.name.upper()))
                first = next((m for m, r in selected if r.name.upper() == routine.name.upper()), None)
                if first is not None:  # two LOCAL routines of one name: one program name, one file
                    reason = (f"{first.name} has a routine of the same name, converted: routines of one name "
                              "in several modules are not")  # fmt: skip
                if reason:
                    self.result.skipped_routines.append((module.name, routine.name, reason))
                    skipped.append(routine)
                    continue
                selected.append((module, routine))
        if wanted is None:
            selected += self._called_from_system(selected)
        self._plan_slots([routine for _, routine in selected])
        # Names once the programs are known: only those actually written claim a name on the controller.
        self.program_names = self._program_names([routine for _, routine in selected])
        self._name_conditions(selected)
        self._text_sides(selected)
        for module, routine in selected:
            translator = _RoutineTranslator(self, module, routine, self.program_names[routine.name.upper()])
            self.result.programs.append(translator.run())
        if wanted:
            found = {info.routine.upper() for info in self.result.programs}
            found |= {r.upper() for _, r, _ in self.result.skipped_routines}
            for missing in sorted(wanted - found):
                self.note("", None, "TODO", f"routine '{missing}' not found in the given modules")

        self._write_conditions()
        self._write_text_program()
        self._number_deferred()
        self._controller_comments()
        self._place_computed()
        place_karel_frames(self)  # before the registers are numbered: they stay placeholders until then
        inlined_notes(self)
        self._place_points()
        self._place_number_arrays()
        self._place_payloads()
        res = self.result
        res.registers = self.registers.allocations()
        res.flags = self.flags.allocations()
        res.digital_outputs = self.douts.allocations()
        res.digital_inputs = self.dins.allocations()
        res.group_outputs = self.gouts.allocations()
        res.group_inputs = self.gins.allocations()
        res.analog_outputs = self.aouts.allocations()
        res.timers = self.timers.allocations()
        res.string_registers = self.texts.allocations()
        res.uframes = sorted((f for (k, _), f in self.frames.items() if k == "UF"), key=lambda f: f.number)
        res.utools = sorted((f for (k, _), f in self.frames.items() if k == "UT"), key=lambda f: f.number)
        self.result.records = {owner: (len(r), len(f)) for owner, (r, f) in sorted(self.record_uses.items())}
        self._report_provided([routine for _, routine in selected])
        self._check_capacity()
        self._report_move_routines()
        declared = {r.name.upper() for m in self.modules for r in m.routines}
        # A routine wrapping a move is counted where it is called, as a FUNC is: not as a routine left out.
        left_out = [r for r in skipped if r.name.upper() not in self.move_routines]
        res.coverage = measure([r for _, r in selected], left_out, self.not_converted, declared, set(self.move_routines))
        if self.config.karel:
            res.karel_programs = karel_called(line.text for info in res.programs for line in info.program.lines
                                              if isinstance(line, Instruction))  # fmt: skip
        return res

    def _report_provided(self, selected: list[n.Routine]) -> None:
        """The provided programs this task calls or would have written, with where they are called and the registers
        they give back in; and the routines CrossArm could not write, as candidates for external_routines."""
        calls = re.compile(r"^CALL ([A-Z0-9_]+)\b")
        written: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for info in self.result.programs:
            for i, line in enumerate(info.program.lines):
                found = calls.match(line.text) if isinstance(line, Instruction) else None
                rapid = info.sources[i] if i < len(info.sources) else None
                if found is not None and rapid is not None and (info.program.name, rapid) not in written[found[1]]:
                    written[found[1]].append((info.program.name, rapid))
        registers = {(a.key or a.rapid_name).upper(): a.number for a in self.result.registers}
        plain = RoutineUse(self.procs | self.computer.functions) if self.externals else self.routine_use
        # the routines to offer: with --karel, one using only files is converted, not offered
        offered = RoutineUse(self.procs | self.computer.functions, (), KAREL_FILES if self.config.karel else (),
                             self.config.karel) if self.externals else self.routine_use
        for key, use in self.provided.items():
            use.calls = list(written.get(use.program, []))
            if use.module is None:
                use.why = MISSING_WHY
            elif (inside := plain.inside(key)) is not None:
                use.why = f"it calls {inside}"
            for argument in use.arguments or ():
                if argument.returned:
                    slot = argument.name if use.module is not None else f"arg{argument.register[3:-1]}"
                    if (number := registers.get(f"{use.program}.{slot}".upper())) is not None:
                        use.returned[argument.name] = number
            if use.calls or use.todo or key in self.not_written:
                self.result.provided.append(use)
        found = candidates(selected, self.procs, {r.name.upper() for m in self.modules for r in m.routines},
                           RAPID_INSTRUCTIONS, set(self.move_routines), offered._uses, self.symbols.type_of)  # fmt: skip
        self.result.provided_candidates = [c for c in found if c.name.upper() not in self.externals]

    def _plan_slots(self, routines: list[n.Routine]) -> None:
        """Reserve one frame number for the frames above what the controller holds, when there will be some.

        A standard controller has 10 tool frames and 9 user frames; a large backup can use more, and
        a program selecting UTOOL_NUM=11 is refused when loaded. Frames past the
        limit are kept in position registers instead and loaded into one reserved number before use:
        `UTOOL[10]=PR[95]` then `UTOOL_NUM=10`. Counted before converting, from the frames the moves name,
        so that the reserved number is not first given to a frame of its own.
        """
        used: dict[str, set[str]] = {"UF": set(), "UT": set()}
        for routine in routines:
            for stmt in walk_statements(routine.body):
                move = stmt if isinstance(stmt, n.Move) else None
                if isinstance(stmt, n.ProcCall) and stmt.name.upper() in self.move_routines:
                    wrapper = self.move_routines[stmt.name.upper()]
                    if self.converts_calls(wrapper):
                        try:
                            move = wrapper.expand(stmt)
                        except CallMismatch:
                            move = None
                if move is None:
                    continue
                wobj = move.wobj if move.wobj is not None else n.Name(move.span, "wobj0")
                layout = self.signatures.get(routine.name.upper())
                for kind, expr in (("UF", wobj), ("UT", move.tool)):
                    if isinstance(layout, Signature) and isinstance(expr, n.Name) and layout.frame(expr.name):
                        continue  # a frame the routine is given: numbered where it is called
                    if isinstance(expr, n.Name):
                        used[kind].add(expr.name.upper())
        self.frames_in_moves = used
        for kind, resource, table in (("UF", "UFRAME", self.uframes), ("UT", "UTOOL", self.utools)):
            limit = self.config.limits.get(resource)
            if limit is None:
                continue
            automatic = [name for name in used[kind] if name not in table.fixed]
            free = [k for k in range(table.first, limit + 1)
                    if k not in table.fixed.values() and k not in table.reserved]  # fmt: skip
            # A mapping file given back pins the banked frames at the numbers past the limit it was written with
            # (every version so far): they still mean banks, loaded into the same reserved number.
            pinned_over = any(table.fixed[name] > limit for name in used[kind] if name in table.fixed)
            if (len(automatic) > len(free) or pinned_over) and free and self._banks:  # no register: over, as before
                self.slots[kind] = free[-1]
                table.reserved = table.reserved | {free[-1]}

    def declared_frame(self, kind: str, expr: n.Expr) -> Frame:
        """A frame as declared (or saved) in the backup: what SETUP_FRAMES sets, whatever a routine did to it since.
        A routine that computes it loads its value where it does (`_RoutineTranslator.computed`)."""
        known, self.evaluator.known = self.evaluator.known, None
        try:
            return self.evaluator.wobj(expr) if kind == "UF" else self.evaluator.tool(expr)
        finally:
            self.evaluator.known = known

    def computed_frame(self, kind: str, rapid_name: str, pose: Pose, program: str, line: int, stmt: n.Stmt) -> str:
        """The register a computed frame is loaded from, as `PR[{CF:n}]` until convert() numbers it."""
        (x, y, z), (w, p, r) = pose.pos, pose.wpr()
        values = tuple(round(v, 3) + 0.0 for v in (x, y, z, w, p, r))  # + 0.0: no -0.0
        key = frame_key(values)
        use = len(self.computed_uses)
        self.computed_uses.append((kind, rapid_name, program, line, stmt, values))
        self.computed.setdefault(key, []).append(use)
        return f"PR[{{CF:{use}}}]"

    def _place_computed(self) -> None:
        """Number the registers of the computed frames and write them into the programs.

        After the frame banks, which take the free registers from the top down: the next free ones
        down, unless the mapping file pins a value's register. Numbered once every frame is known, so
        that the banks keep the registers they had before frames were computed. A value with no
        register left is not loaded: its loads become TODO."""
        if not self.computed:
            return
        pinned = self.config.frame_registers
        banks = {info.bank for info in self.frames.values() if info.bank is not None}
        scratch = self.config.free_position_registers()[0][:1]
        free = [k for k in self._banks if k not in pinned.values()]
        numbers: dict[str, int | None] = {}
        for key in self.computed:
            if key in pinned:
                numbers[key] = pinned[key]
                clash = "SETUP_FRAMES' scratch register" if pinned[key] in scratch else (
                    "a frame bank" if pinned[key] in banks else "")  # fmt: skip
                users = self.config.reserved.get("PR", {}).get(pinned[key])
                if users is not None:
                    clash = "the robot's programs" + (f" ({', '.join(users[:3])})" if users else "")
                if clash:
                    self.note("", None, "WARNING", f"frame_registers pins PR[{pinned[key]}] for the computed frame "
                                                   f"{key}, but {clash} also use it", Blocker.TAKEN)  # fmt: skip
            else:
                numbers[key] = free.pop(0) if free else None
        load = re.compile(r"^(UTOOL|UFRAME)\[\{(UT|UF):([^}]*)\}\]=PR\[\{CF:(\d+)\}\]$")
        key_of = {use: key for key, uses in self.computed.items() for use in uses}
        for info in self.result.programs:
            lines = info.program.lines
            for i, line in enumerate(lines):
                found = load.match(line.text) if isinstance(line, Instruction) else None
                if found is None:
                    continue
                resource, kind, name, use = found[1], found[2], found[3], int(found[4])
                number = numbers[key_of[use]]
                _, rapid_name, program, rapid_line, stmt, _ = self.computed_uses[use]
                if number is None:
                    text = f"TODO l.{rapid_line} {rapid_name} computed"
                    lines[i] = Instruction(("!" + ascii_text(text)[:REMARK_MAX]).rstrip())
                    self.not_converted.update(id(s) for s in walk_statements((stmt,)))
                    self.note(program, rapid_line, "TODO", f"{resource} {rapid_name} is computed at conversion time,"
                              " but no position register is left to keep its value in", Blocker.CAPACITY)  # fmt: skip
                    continue
                table = self.uframes if kind == "UF" else self.utools
                allocation = table.assigned.get(name)
                frame = self.frames.get((kind, allocation.number)) if allocation else None
                if frame is None:  # no move selects it after all: nothing to load
                    lines[i] = Instruction(("!" + ascii_text(f"{rapid_name} not used by a move")[:REMARK_MAX]).rstrip())
                elif frame.bank is not None:
                    lines[i] = Instruction(f"PR[{frame.bank}]=PR[{number}]")
                else:
                    lines[i] = Instruction(f"{resource}[{frame.number}]=PR[{number}]")
        for key, uses in self.computed.items():
            self.result.computed_frames.append(ComputedFrame(
                key, self.computed_uses[uses[0]][5], numbers[key], key in pinned,  # type: ignore[arg-type]
                tuple(("UFRAME" if u[0] == "UF" else "UTOOL", u[1], u[2], u[3]) for u in map(self.computed_uses.__getitem__, uses)),
            ))  # fmt: skip

    def point_frames(self, routine: str, parameter: str, seen: frozenset[str] = frozenset()) -> tuple[n.Expr | None, n.Expr | None]:
        """The tool and work object a point parameter is moved to with, followed into the routines it is passed
        on to; (None, None) if no routine moves to it."""
        layout = self.signatures.get(routine.upper())
        key = f"{routine}.{parameter}".upper()
        if not isinstance(layout, Signature) or key in seen:
            return None, None
        frames = layout.frames_of(parameter)
        if frames != (None, None) or routine.upper() not in self.procs:
            return frames
        for stmt in walk_statements(self.procs[routine.upper()].body):
            callee = self.signatures.get(stmt.name.upper()) if isinstance(stmt, n.ProcCall) else None
            if not isinstance(callee, Signature):
                continue
            given = [a.value for a in stmt.args if a.name is None]  # type: ignore[union-attr]
            for value, slot in zip(given, callee.required, strict=False):
                if slot.kind == "robtarget" and isinstance(value, n.Name) and value.name.upper() == parameter.upper():
                    found = self.point_frames(callee.routine, slot.name, seen | {key})
                    if found != (None, None):
                        return found
        return None, None

    def point_register(self, key: str) -> str:
        """The position register the point `ROUTINE.PARAMETER` is passed in, as `PR[{PA:KEY}]` until numbered."""
        self.point_keys.setdefault(key.upper(), key)
        return f"PR[{{PA:{key.upper()}}}]"

    def _place_points(self) -> None:
        """Number the position registers of the robtarget arguments, after the frame banks and the computed
        frames (numbered first, so that theirs do not move), unless the mapping file pins them."""
        if not self.point_keys and not self.arrays:
            return
        pinned = self.config.point_registers
        taken = {f.number for f in self.result.computed_frames if f.number is not None}
        taken |= set(self.config.frame_registers.values()) | set(pinned.values())
        for key, (_name, _dims, values) in self.arrays.items():  # the whole block of an array the mapping file pins
            if key in self.config.point_arrays:
                taken |= set(range(self.config.point_arrays[key], self.config.point_arrays[key] + len(values)))
        free = [k for k in self._banks if k not in taken]
        used: set[str] = set()  # a register asked for by a statement then left TODO is in no program: none for it
        for info in self.result.programs:
            for line in info.program.lines:
                text = line.text if isinstance(line, Instruction) else f"{line.target} {line.via or ''} {line.options}"
                used.update(re.findall(r"\{PA:([^}:]*)\}", text))
        numbers = {key: pinned.get(key) or (free.pop(0) if free else None) for key in self.point_keys if key in used}
        bases: dict[str, int | None] = {}
        for key, (_name, _dims, values) in self.arrays.items():
            if key in self.config.point_arrays:
                bases[key] = self.config.point_arrays[key]
                continue
            run = _consecutive(free, len(values))  # free is from the top down: the run's lowest register first
            bases[key] = run[0] if run else None
            free = [k for k in free if k not in run]
        placeholder = re.compile(r"\{(PA|PB):([^}:]*)(?::(-?\d+))?\}")

        def number(match: re.Match[str]) -> str:
            found = numbers[match[2]] if match[1] == "PA" else bases[match[2]]
            if found is None:
                raise LookupError(match[2])
            return str(found + int(match[3] or 0))

        for info in self.result.programs:
            lines = info.program.lines
            for i, line in enumerate(lines):
                try:
                    if isinstance(line, Instruction) and ("{PA:" in line.text or "{PB:" in line.text):
                        lines[i] = Instruction(placeholder.sub(number, line.text), line.pad)
                    elif isinstance(line, Motion) and "{P" in line.target + (line.via or "") + line.options:
                        via = placeholder.sub(number, line.via) if line.via else line.via
                        lines[i] = dataclasses.replace(line, target=placeholder.sub(number, line.target), via=via,
                                                       options=placeholder.sub(number, line.options))  # fmt: skip
                except LookupError as missing:
                    lines[i] = Instruction(("!" + ascii_text(f"TODO no PR left for {missing}")[:REMARK_MAX]).rstrip())
                    what = self.point_keys.get(str(missing.args[0])) or self.arrays[str(missing.args[0])][0]
                    self.note(info.program.name, None, "TODO", f"no position register left for the point(s) {what}",
                              Blocker.CAPACITY)  # fmt: skip
        self.result.point_registers = sorted(
            (Allocation(number, self.point_keys[key], key in pinned) for key, number in numbers.items() if number),
            key=lambda a: a.number)  # fmt: skip
        self.result.point_arrays = [PointArray(name, dims, values, bases[key], key in self.config.point_arrays)
                                    for key, (name, dims, values) in self.arrays.items()]  # fmt: skip

    def _place_number_arrays(self) -> None:
        """Number the register blocks of the arrays of numbers, then the flag blocks of the arrays of bools."""
        self.result.number_arrays = self._place_blocks("R", self.number_arrays, self.registers.table,
                                                       self.config.number_arrays, 200)  # fmt: skip
        self.result.flag_arrays = self._place_blocks("F", self.flag_arrays, self.flags.table, self.config.flag_arrays,
                                                     1024)  # fmt: skip

    def _place_blocks(self, kind: str, arrays: dict[str, tuple[str, tuple[int, ...], tuple[float, ...]]],
                      table: NumberTable, pinned: dict[str, int], default_limit: int) -> list[NumberArray]:  # fmt: skip
        """Number the blocks of `kind` (R, F) the arrays are kept in: the highest free run, from the top down, or
        pinned by the mapping file; kept out of the numbers given automatically afterwards. Lines read
        `{RB:NAME:k}` (`{FB:...}` for flags) until then."""
        if not arrays:
            return []
        limit = self.config.limits.get(kind, default_limit)
        used = set(table.fixed.values()) | {a.number for a in table.assigned.values()} | table.reserved | table.skip
        free = [k for k in range(limit, 0, -1) if k not in used]
        bases: dict[str, int | None] = {}
        for key, (_name, _dims, values) in arrays.items():
            shared = key if kind == "R" else f"{kind}:{key}"  # 1.2 files: the register blocks by their name alone
            if key in pinned:
                bases[key] = pinned[key]
            elif key in self.shared_arrays and shared in self.shared.array_bases:  # a PERS another task placed
                bases[key] = self.shared.array_bases[shared]
            else:
                run = _consecutive(free, len(values))
                bases[key] = run[0] if run else None
                free = [k for k in free if k not in run]
            if bases[key] is not None:
                table.skip.update(range(bases[key], bases[key] + len(values)))  # type: ignore[operator]
                if key in self.shared_arrays:
                    self.shared.array_bases[shared] = bases[key]  # type: ignore[assignment]
            else:  # its statements are not converted
                for ids in self.array_statements.get(key, ()):
                    self.not_converted.add(ids)
        mark = "RB" if kind == "R" else "FB"
        placeholder = re.compile(r"\{" + mark + r":([^}:]*):(-?\d+)\}")

        def number(match: re.Match[str]) -> str:
            found = bases[match[1]]
            if found is None:
                raise LookupError(match[1])
            return str(found + int(match[2]))

        for info in self.result.programs:
            lines = info.program.lines
            for i, line in enumerate(lines):
                if isinstance(line, Instruction) and "{" + mark + ":" in line.text:
                    try:
                        lines[i] = Instruction(placeholder.sub(number, line.text), line.pad)
                    except LookupError as missing:
                        name = arrays[str(missing.args[0])][0]
                        lines[i] = Instruction(("!" + ascii_text(f"TODO no {kind} left for {name}")[:REMARK_MAX]).rstrip())
                        what = "registers" if kind == "R" else "flags"
                        self.note(info.program.name, None, "TODO", f"no run of free {what} left for the array {name}",
                                  Blocker.CAPACITY)  # fmt: skip
        return [NumberArray(name, dims, values, bases[key], key in pinned) for key, (name, dims, values) in arrays.items()]

    def _place_payloads(self) -> None:
        """Number the payload schedules GripLoad selects and write them into the programs.

        The tool alone takes its UTOOL number, as the report's payload table says. A tool holding a part
        takes a schedule of its own, from the top down past the tools' numbers, unless the mapping file
        pins it. Done once every tool has its number."""
        if not self.payload_uses:
            return
        limit = self.config.limits.get("PAYLOAD", PAYLOAD_SCHEDULES)
        tools = {f.rapid_name.upper(): f for (kind, _), f in self.frames.items() if kind == "UT"}
        movers = [f for f in tools.values() if f.frame is not None and f.frame.robhold]
        pinned = self.config.payloads
        taken = ({a.number for a in self.utools.assigned.values()} | set(self.config.reserved.get("PAYLOAD", {}))
                 | set(pinned.values()))  # fmt: skip
        free = [k for k in range(limit, 0, -1) if k not in taken]
        schedules: dict[str, GripPayload] = {}
        numbers: list[int | None] = []
        for tool_expr, load, part, program, line, _stmt in self.payload_uses:
            if tool_expr is None and len(movers) == 1:
                tool_expr = n.Name(n.Span(line, 0), movers[0].rapid_name)
            if tool_expr is None:
                numbers.append(None)
                self.note(program, line, "TODO", f"GripLoad: no move after it says which tool carries the load, and"
                          f" this task moves {len(movers)} tools", Blocker.PAYLOAD)  # fmt: skip
                continue
            tool = format_expr(tool_expr)
            info = tools.get(tool.upper())
            try:
                frame = self.declared_frame("UT", tool_expr)
            except Unresolvable as exc:
                numbers.append(None)
                self.note(program, line, "TODO", f"GripLoad: tool {tool} not known ({exc})", Blocker.PAYLOAD)
                continue
            key = tool if load is None else f"{tool}+{load}"
            if key.upper() not in schedules:
                if load is None:  # the tool's own schedule: its UTOOL number, when the controller has it
                    number = info.number if info is not None and info.number <= limit else None
                else:
                    number = pinned.get(key.upper()) or (free.pop(0) if free else None)
                schedules[key.upper()] = GripPayload(key, number, tool, load, combined(frame, part),
                                                     key.upper() in pinned, ())  # fmt: skip
            found = schedules[key.upper()]
            schedules[key.upper()] = GripPayload(found.key, found.number, found.tool, found.load, found.payload,
                                                 found.fixed, (*found.uses, (program, line)))  # fmt: skip
            numbers.append(found.number)
            if found.number is None:
                why = (f"the {limit} payload schedules are taken" if load is not None else
                       f"tool {tool} has no UTOOL number of its own up to {limit}")  # fmt: skip
                self.note(program, line, "TODO", f"GripLoad {load or 'load0'}: {why}", Blocker.CAPACITY)
        placeholder = re.compile(r"^PAYLOAD\[\{PL:(\d+)\}\]$")
        for info_program in self.result.programs:
            lines = info_program.program.lines
            for i, text_line in enumerate(lines):
                found_use = placeholder.match(text_line.text) if isinstance(text_line, Instruction) else None
                if found_use is None:
                    continue
                use = int(found_use[1])
                number = numbers[use]
                if number is None:
                    _, load, _, _, rapid_line, stmt = self.payload_uses[use]
                    text = f"TODO l.{rapid_line} GripLoad {load or 'load0'}"
                    lines[i] = Instruction(("!" + ascii_text(text)[:REMARK_MAX]).rstrip())
                    self.not_converted.update(id(s) for s in walk_statements((stmt,)))
                else:
                    lines[i] = Instruction(f"PAYLOAD[{number}]")
        self.result.grip_payloads = sorted(schedules.values(), key=lambda s: (s.number is None, s.number or 0))

    def selection(self, kind: str, number: int) -> tuple[int, int | None]:
        """(number to select, PR to load it from first): a frame above the limit is loaded into its slot."""
        info = self.frames[(kind, number)]
        return (info.slot, info.bank) if info.bank is not None and info.slot is not None else (number, None)

    def _called_from_system(self, selected: list[tuple[n.Module, n.Routine]]) -> list[tuple[n.Module, n.Routine]]:
        """Routines of the system modules that the programs call, directly or not: written too.

        System modules are data and utilities, not programs; but a program calling one of their
        routines needs it on the robot, or its CALL fails when it runs.
        """
        by_name = {r.name.upper(): (m, r) for m in reversed(self.modules) for r in m.routines if r.kind == "PROC"}
        done = {r.name.upper() for _, r in selected}
        added: list[tuple[n.Module, n.Routine]] = []
        todo = [r for _, r in selected]
        while todo:
            for stmt in walk_statements(todo.pop().body):
                if not isinstance(stmt, n.ProcCall):
                    continue
                key = stmt.name.upper()
                if key in done or key not in by_name or key in self.move_routines or key in self.externals:
                    continue  # a move routine's calls are written as its move, not as a CALL; a provided one's,
                    # as a CALL to the integrator's program
                done.add(key)
                module, routine = by_name[key]
                if self._skip_reason(routine, self.signatures.get(key)):
                    continue  # its calls stay TODO, with the reason
                added.append((module, routine))
                todo.append(routine)
        self.result.from_system = [f"{m.name}.{r.name}" for m, r in added]
        return added

    def converts_calls(self, routine: MoveRoutine) -> bool:
        """Whether calls to this move routine are written as its move: mapping file, else only if pure."""
        return self.config.move_routines.get(routine.name.upper(), routine.pure)

    def also_does(self, routine: MoveRoutine) -> str:
        """What a move routine does besides its move, as a short RAPID excerpt.

        A change to the point comes first, even deep in a condition: it is what makes the converted
        move go somewhere else than the robot did (e.g. a point chosen from a parameter).
        """
        lines = self.source_lines.get(routine.module.upper(), [])

        def text(stmt: n.Stmt) -> str:
            line = stmt.span.line
            source = lines[line - 1].split("!", 1)[0].strip() if 0 < line <= len(lines) else ""
            return (source or _source(stmt)).rstrip(";").rstrip()

        locals_ = {local for local, _ in routine.copies}
        changes = [
            s for s in walk_statements(routine.extra)
            if isinstance(s, n.Assign) and isinstance(s.target, n.Name) and s.target.name.upper() in locals_
        ]  # fmt: skip
        # The assignment itself, not its source line: a one-line IF shares that line with it.
        parts = [f"changes the point: {s.target.name}:={format_expr(s.value)}" for s in changes[:2]]  # type: ignore[union-attr]
        parts += [text(s) for s in routine.extra[: max(0, 2 - len(parts))]]
        more = len(routine.extra) - (len(parts) - len(changes[:2]))
        return "; ".join(parts) + (f" (+{more} more)" if more > 0 else "")

    def _report_move_routines(self) -> None:
        for name, calls in self.move_routine_calls.most_common():
            routine = self.move_routines[name]
            self.result.move_routines.append(MoveRoutineUse(
                routine.name, routine.instruction, calls, self.converts_calls(routine), routine.pure,
                "" if routine.pure else self.also_does(routine),
            ))  # fmt: skip
        declared = {r.name.upper() for m in self.modules for r in m.routines}
        for name, wanted in sorted(self.config.move_routines.items()):
            if wanted and name in declared and name not in self.move_routines:
                self.note("", None, "WARNING",
                          f"move_routines: {name} is not a routine CrossArm recognises as one move "
                          "(exactly one MoveJ/MoveL/MoveC/MoveAbsJ taking its point, speed, zone and tool "
                          "from the parameters): its calls stay TODO", Blocker.MOVE_ROUTINE)  # fmt: skip

    def wait_clock(self) -> tuple[str, str]:
        """(TIMER[n], R[m]) for timing waits with a MaxTime: the highest timer the robot's programs do not use.

        $WAITTMOUT, the time limit of WAIT ... TIMEOUT, is write-protected for TP programs (VARS-010 on
        ROBOGUIDE), so a wait is timed by a loop reading a timer instead. One timer serves every wait:
        they never overlap within a task.
        """
        if self.result.wait_clock is None:
            used = set(self.config.reserved.get("TIMER", {})) | set(self.timers.fixed.values())
            used |= {a.number for a in self.timers.table.assigned.values()}
            free = [i for i in range(self.config.limits.get("TIMER", 10), 0, -1) if i not in used]
            if not free:
                raise Untranslatable("wait with MaxTime: every TIMER is used on the robot", Blocker.WAIT_TIMEOUT)
            self.timers.table.skip.add(free[0])
            self.result.wait_clock = (f"TIMER[{free[0]}]", self.written_register(WAIT_CLOCK, key="CROSSARM.WAITCLOCK"))
        return self.result.wait_clock

    def _fixed_value(self, expr: n.Expr) -> Any:
        """The value of an expression of fixed data, whatever routine is being written (Unresolvable if none)."""
        scope, self.computer.scope = self.computer.scope, (lambda name: None)
        try:
            return self.computer.value(expr).value
        finally:
            self.computer.scope = scope

    def _const_field(self, expr: n.Expr) -> bool | None:
        """A bool field of a record no program changes, for conditions: its value; None for anything else."""
        found = self.records.field(expr)
        if found is None or found.indexed or found.type != "bool" or self.records.changed(found):
            return None
        try:
            value = self.records.initial(found)
        except Unresolvable:
            return None
        if not isinstance(value, bool):
            return None
        self.saved_value(found, value)
        return value

    def saved_value(self, found: Field, value: Any) -> None:
        """A field of a PERS read as saved: said once per data, the first field read named."""
        if found.root.storage == "PERS":
            shown = value if isinstance(value, bool) else fmt_number(value) if isinstance(value, float) else value
            self.warn_once(f"saved:{found.root.name.upper()}", "", None,
                           f"{found.root.name}, a PERS no program changes: its fields are written as saved in the"
                           f" backup where they are read ({found.name} {shown}...); a value set on the ABB controller"
                           " since is not",
                           Blocker.SAVED_VALUE)  # fmt: skip

    def field_number(self, found: Field, flag: bool, program: str | None) -> str:
        """R[n:...] / F[n:...] keeping a field of a record. `program`: the routine's own record, named
        Routine.data.field (a routine's data and another's may share a name), else None."""
        name = found.name if program is None else f"{program}.{found.name}"
        detail = ""
        if program is None and found.root.storage == "VAR" and found.root.init is not None:
            try:
                value = self.records.initial(found)
                detail = f"RAPID VAR initial value {value if isinstance(value, bool) else fmt_number(value)}:" \
                         " set it on the controller"
            except (Unresolvable, TypeError, ValueError):
                pass
        table = self.flags if flag else self.registers
        number = table.number(name, detail=detail, after_pinned=True)
        owner = found.root.name if program is None else f"{program}.{found.root.name}"
        uses = self.record_uses.setdefault(owner, (set(), set()))
        uses[1 if flag else 0].add(number)
        if not flag:
            self.written_registers.add(number)
        return f"{'F' if flag else 'R'}[{number}:{_comment(name)}]"

    def _const_bool(self, name: str) -> bool | None:
        decl = self.symbols.get(name)
        if decl is not None and decl.storage == "CONST" and isinstance(decl.init, n.Bool):
            return decl.init.value
        return None

    def _inlined(self, key: str) -> None:
        if key == REAL_CONTROLLER:
            self.warn_once("robos", "", None,
                           "RobOS() taken as TRUE: the programs are made to run on a real robot (in RobotStudio it"
                           " is FALSE, so what the backup does only in simulation is left out)",
                           Blocker.REAL_CONTROLLER)  # fmt: skip
        else:
            names = {r.name.upper(): r.name for r in self.inliner.functions.values()}
            self.result.inlined[names[key]] += 1

    def _check_capacity(self) -> None:
        """Compare what the conversion allocated with what the controller holds.

        Allocation is automatic and unbounded, so a big backup quietly produces
        numbers such as UTOOL 19 that no standard controller has. Better to say it
        here than to have it fail when the programs are loaded.
        """
        res = self.result
        tables = [
            ("UFRAME", self.uframes), ("UTOOL", self.utools), ("R", self.registers), ("F", self.flags),
            ("DO", self.douts), ("DI", self.dins), ("GO", self.gouts), ("GI", self.gins), ("AO", self.aouts),
            ("TIMER", self.timers), ("SR", self.texts),
        ]  # fmt: skip
        for resource, table in tables:
            allocations = table.allocations()
            self._check_taken(resource, allocations)
            limit = self.config.limits.get(resource)
            taken = sum(1 for n in table.reserved if n > 0)
            if not allocations or (limit is None and not taken):
                continue  # nothing to compare: no limit (I/O depends on the cell), nothing taken
            kind = {"UFRAME": "UF", "UTOOL": "UT"}.get(resource)
            banked = {a.number for a in allocations if kind and (info := self.frames.get((kind, a.number))) and info.bank}
            over = () if limit is None else tuple(a.rapid_name for a in allocations
                                                  if a.number > limit and a.number not in banked)  # fmt: skip
            if banked:
                infos = sorted((self.frames[(kind, number)] for number in banked), key=lambda f: f.number)  # type: ignore[index]
                _, checked = self.config.free_position_registers()
                self.note(
                    "", None, "WARNING",
                    f"{len(infos)} {resource} above the {limit} the controller holds ({', '.join(f.rapid_name for f in infos[:5])}"
                    f"{', ...' if len(infos) > 5 else ''}) are kept in PR[{infos[-1].bank}] to PR[{infos[0].bank}] and loaded"
                    f" into {resource}[{infos[0].slot}] before each use; SETUP_FRAMES.LS stores them. "
                    + ("Those registers are free on the robot." if checked else
                       "Give the FANUC robot's backup to check those registers are free on the robot.")
                    + (f" A frame touched up on the pendant in {resource}[{infos[0].slot}] is overwritten at its next"
                       f" use: to select every frame directly, raise the controller's number of {resource} at a"
                       f" Controlled Start (${'SCR.$MAXNUMUTOOL' if resource == 'UTOOL' else 'SCR.$MAXNUMUFRAM'}) and"
                       f' set "limits": {{"{resource}": n}} in crossarm_mapping.json.'),
                    Blocker.CAPACITY,
                )  # fmt: skip
            res.capacity.append(
                Capacity(resource, len(allocations), max(a.number for a in allocations), limit, over, taken)
            )
            if over:
                self.note(
                    "", None, "WARNING",
                    f"{len(over)} {resource} number(s) above the configured limit of {limit} "
                    f"({', '.join(over[:5])}{', ...' if len(over) > 5 else ''}): pin them with a mapping file, "
                    "reuse frames, or raise the limit if the controller has the option",
                    Blocker.CAPACITY,
                )  # fmt: skip
        self._check_position_registers()

    def _check_position_registers(self) -> None:
        """The position registers CrossArm takes: SETUP_FRAMES' scratch one, the frame banks, the computed frames."""
        banks = [info.bank for info in self.frames.values() if info.bank is not None]
        computed = self.result.computed_frames
        if not banks and not computed and not self.result.point_registers and not self.result.point_arrays:
            return
        numbers = set(self.config.free_position_registers()[0][:1]) | set(banks)
        numbers |= {f.number for f in computed if f.number is not None}
        numbers |= {a.number for a in self.result.point_registers}
        for array in self.result.point_arrays:
            if array.base is not None:
                numbers |= set(range(array.base, array.base + len(array.values)))
        over = tuple(f"{f.uses[0][1]} ({f.key})" for f in computed if f.number is None)
        taken = len(self.config.reserved.get("PR", {}))
        self.result.capacity.append(
            Capacity("PR", len(numbers) + len(over), max(numbers), self.config.limits.get("PR"), over, taken)
        )

    def _check_taken(self, resource: str, allocations: list[Allocation]) -> None:
        """A number pinned in the mapping file that the controller already uses.

        Automatic numbers never land there. A pinned one can, and that is often on
        purpose — the gripper output already exists on the new cell as DO[3], and the
        RAPID signal is mapped onto it — so this is a warning, not a refusal. For a
        register or a frame it is more likely a clash, hence the programs are named.
        Number 0 is left out: UFRAME_NUM=0 is the world frame, shared by definition.
        """
        users = self.config.reserved.get(resource, {})
        for a in allocations:
            if a.fixed and a.number > 0 and a.number in users:
                by = f" by {', '.join(users[a.number][:4])}{', ...' if len(users[a.number]) > 4 else ''}"
                self.note(
                    "", None, "WARNING",
                    f"{resource}[{a.number}] is pinned for {a.rapid_name} but already used on the controller"
                    f"{by if users[a.number] else ''}: intended if it is the same signal or frame, a clash otherwise",
                    Blocker.TAKEN,
                )  # fmt: skip

    def _skip_reason(self, routine: n.Routine, layout: "Signature | str | None") -> str:
        if routine.kind == "TRAP":
            used = [i for i in self.interrupts.values() if routine.name.upper() in i.traps]
            if any(not i.problem for i in used):
                return ""
            return used[0].problem if used else "TRAP not connected to any interrupt (no CONNECT)"
        if routine.kind != "PROC":
            return f"{routine.kind} routines have no TP program equivalent"
        if isinstance(layout, str):
            return f"parameters not converted: {layout}"
        if routine.name.upper() in self.move_routines:  # never called: its calls are its move, or TODO
            return "it wraps one move: its calls are written as that move, not as a CALL"
        return ""

    def _program_names(self, converted: list[n.Routine]) -> dict[str, str]:
        """TP name of every routine: the ones written, then the others (CALL targets only).

        A written program must not take a name already on the controller: one of the target
        robot's programs, or one given to another task of the same backup. Loading it would
        replace that program. Such a program gets a suffix, and the report says why.
        Routines that are not written claim no name, so they never push a real one aside.
        """
        names: dict[str, str] = {}
        mine: set[str] = set()  # names given in this task
        max_len = self.config.program_name_max_length
        claimed = self.shared.program_names

        for routine in converted:
            key = routine.name.upper()
            if key in names:
                continue
            name, base = self.program_name(routine.name, tp_program_name(routine.name, max_len), claimed | mine)
            if name != base:
                if base == self.config.programs.get(key):
                    why = f"the mapping file gives it {base}, the name of another program of this conversion"
                elif base in {e.program for e in self.externals.values()}:
                    why = f"the mapping file gives {base} to a program the integrator provides (external_routines)"
                elif base in mine:
                    why = "another routine of this task has the same name once shortened"
                elif base in self.shared.existing_programs:
                    why = f"the FANUC robot already has a program {base}, which loading it would replace"
                else:
                    why = f"another task of this backup already writes {base}.LS"
                self.note(name, None, "WARNING", f"routine {routine.name} written as {name}.LS: {why}",
                          Blocker.RENAMED)  # fmt: skip
            mine.add(name)
            claimed.add(name)
            self.shared.given_programs.add(name)
            self.result.program_keys[routine.name] = name
            names[key] = name
        for key, entry in self.externals.items():  # provided: called by the name of the integrator's program
            names.setdefault(key, entry.program)
        for module in self.modules:  # not written: only called by name
            for routine in module.routines:
                key = routine.name.upper()
                if key not in names:
                    names[key] = self.config.programs.get(key) or suffixed(tp_program_name(routine.name, max_len),
                                                                           mine, max_len)  # fmt: skip
                    mine.add(names[key])
        return names

    def program_name(self, key: str, base: str, taken: set[str]) -> tuple[str, str]:
        """(name, start) of a program CrossArm writes: the name the mapping file gives it (programs), kept even if
        the FANUC robot has a program of that name (an earlier conversion loaded it, and the programs on the robot
        call it: said so); else base, with a suffix while taken. start: the name it started from. A name the
        mapping file gives another program is taken."""
        pinned = self.config.programs.get(key.upper())
        if pinned is not None and pinned not in self.shared.given_programs:
            if pinned in self.shared.existing_programs:
                self.note(pinned, None, "WARNING",
                          f"the mapping file names {key} {pinned}, and the FANUC robot already has a program {pinned}:"
                          " loading it replaces that one, intended if an earlier conversion loaded it, a clash"
                          " otherwise", Blocker.TAKEN)  # fmt: skip
            return pinned, pinned
        start = pinned or base
        others = {name for k, name in self.config.programs.items() if k != key.upper()}
        others |= {entry.program for entry in self.externals.values()}  # the integrator's programs
        return suffixed(start, taken | others, self.config.program_name_max_length), start

    def _name_conditions(self, selected: list[tuple[n.Module, n.Routine]]) -> None:
        """A condition program for each interrupt whose TRAP is written, named after the interrupt."""
        written = {r.name.upper(): r for _, r in selected if r.kind == "TRAP"}
        max_len = self.config.program_name_max_length
        taken = set(self.program_names.values()) | self.shared.program_names
        for interrupt in self.interrupts.values():
            if interrupt.problem or interrupt.trap not in written:
                continue
            name, _ = self.program_name(interrupt.name, tp_program_name(interrupt.name, max_len), taken)
            taken.add(name)
            self.shared.program_names.add(name)
            self.shared.given_programs.add(name)
            self.result.program_keys[interrupt.name] = name
            interrupt.program = name
            if interrupt.shared:  # a relay: notes the interrupt, calls the TRAP, arms the condition again
                key = f"{interrupt.name}.relay"
                relay, _ = self.program_name(key, tp_program_name(f"{interrupt.name}_T", max_len), taken)
                taken.add(relay)
                self.shared.program_names.add(relay)
                self.shared.given_programs.add(relay)
                self.result.program_keys[key] = relay
                interrupt.relay = relay
            self.volatile |= changed_by(written[interrupt.trap], self.procs)
            self.no_group |= called_by(written[interrupt.trap], self.procs)

    def _write_conditions(self) -> None:
        """The condition programs, once the programs have armed them: `WHEN DI[3]=ON+,CALL TRAP`.

        An interrupt armed nowhere the conversion wrote gets none: its TRAP and the lines ending it
        then say so instead of arming a program that is not there."""
        modules = {r.name.upper(): m.name for m in self.modules for r in m.routines}
        for key, interrupt in self.interrupts.items():
            if not interrupt.program:
                continue
            conditions = self.conditions.get(key)
            if not conditions:
                for info in self.result.programs:
                    lines = info.program.lines
                    for i, line in enumerate(lines):
                        if isinstance(line, Instruction) and line.text in (f"MONITOR {interrupt.program}",
                                                                          f"MONITOR END {interrupt.program}"):  # fmt: skip
                            lines[i] = Instruction(("!" + f"{interrupt.name} not armed"[: REMARK_MAX - 1]).rstrip())
                continue
            trap = self.program_names[interrupt.trap]
            attrs = Attributes(comment=ascii_text(interrupt.name)[:16], created=self.config.timestamp,
                               default_group=NO_GROUP)  # fmt: skip
            if interrupt.relay:
                relay = [f"{self.pers_copy(interrupt)}={self.watched[key]}"] if key in self.watched else []
                relay += [f"{self.intno()}={interrupt.number}", f"CALL {trap}"]
                relay += [] if interrupt.single else [f"MONITOR {interrupt.program}"]
                program = Program(interrupt.relay, [Instruction(text) for text in relay], [],
                                  dataclasses.replace(attrs))  # fmt: skip
                self.result.programs.append(ProgramInfo(program, modules.get(interrupt.trap, ""),
                                                        f"{interrupt.name} (relay)", ()))  # fmt: skip
                trap = interrupt.relay
            lines = [Instruction(f"WHEN {condition},CALL {trap}") for condition in conditions]
            program = Program(interrupt.program, list(lines), [], attrs, condition=True)
            self.result.programs.append(ProgramInfo(program, modules.get(interrupt.trap, ""), interrupt.name, ()))
            self.note(interrupt.program, None, "WARNING",
                      f"interrupt {interrupt.name} watched by the condition monitor {interrupt.program} (MONITOR), which"
                      " checks its condition periodically: a signal change within 0.05 s of MONITOR, or held less"
                      " than 0.02 s, can be missed (ROBOGUIDE); RAPID catches both", Blocker.MONITOR)  # fmt: skip

    def intno(self) -> str:
        """The register a relay notes its interrupt in, what INTNO reads in a TRAP several interrupts share."""
        return self.written_register("IntNo", key="CROSSARM.INTNO")

    def pers_copy(self, interrupt: Interrupt) -> str:
        """The register an IPers condition compares the watched data with: its value when last seen."""
        return self.written_register(f"{interrupt.name}Seen", key=f"CROSSARM.IPERS.{interrupt.name.upper()}")

    def _signals_by_usage(self) -> tuple[set[str], set[str]]:
        """Signal names whose direction is known from the instructions using them."""
        outputs: set[str] = set()
        inputs: set[str] = set()
        for module in self.modules:
            for routine in module.routines:
                for stmt in walk_statements(routine.body):
                    if isinstance(stmt, n.SetSignal) and isinstance(stmt.signal, n.Name):
                        outputs.add(stmt.signal.name.upper())
                    elif isinstance(stmt, n.ProcCall) and stmt.name.upper() in ("ISIGNALDI", "ISIGNALDO"):
                        first = next((a.value for a in stmt.args if a.name is None), None)
                        if isinstance(first, n.Name):
                            (inputs if stmt.name.upper() == "ISIGNALDI" else outputs).add(first.name.upper())
                    elif isinstance(stmt, n.ProcCall) and stmt.name.upper() in ("SEARCHL", "SEARCHJ", "SEARCHC"):
                        first = next((a.value for a in stmt.args if a.name is None), None)
                        if isinstance(first, n.Name):
                            inputs.add(first.name.upper())
                    elif isinstance(stmt, n.ProcCall) and stmt.name.upper() in _SET_ON_ARRIVAL:
                        signal = [a.value for a in stmt.args if a.name is None][-2:-1]
                        if signal and isinstance(signal[0], n.Name):
                            outputs.add(signal[0].name.upper())
                    elif isinstance(stmt, n.ProcCall) and stmt.args and isinstance(stmt.args[0].value, n.Name):
                        name = stmt.args[0].value.name.upper()
                        if stmt.name.upper() in ("SETDO", "PULSEDO", "WAITDO"):
                            outputs.add(name)
                        elif stmt.name.upper() == "WAITDI":
                            inputs.add(name)
        return outputs, inputs

    # -- strings (crossarm.convert.strings) -----------------------------------

    def _numbered(self) -> list[tuple[str, TableView]]:
        return [("R", self.registers), ("F", self.flags), ("DO", self.douts), ("DI", self.dins), ("GO", self.gouts),
                ("GI", self.gins), ("AO", self.aouts), ("TIMER", self.timers)]  # fmt: skip

    def deferring(self, on: bool) -> bool:
        """Defer the numbers a statement takes first (NumberTable.defer); returns what it was."""
        previous = self.registers.table.defer
        for _, view in self._numbered():
            view.table.defer = on
        return previous

    def _number_deferred(self) -> None:
        """Number what only the statements converted with texts use, and write the numbers in their place."""
        numbers: dict[int, int] = {}
        for resource, view in self._numbered():
            numbers |= view.finish(self.config.limits.get(resource))
        if not numbers:
            return

        def number(text: str) -> str:
            return _PLACEHOLDER.sub(lambda m: str(numbers.get(int(m[0]), m[0])), text)

        for info in self.result.programs:
            lines = info.program.lines
            for i, line in enumerate(lines):
                if isinstance(line, Instruction):
                    lines[i] = Instruction(number(line.text), line.pad)
                else:
                    lines[i] = dataclasses.replace(line, target=number(line.target), speed=number(line.speed),
                                                   termination=number(line.termination), options=number(line.options),
                                                   via=number(line.via) if line.via else line.via)  # fmt: skip
        self.written_registers = {numbers.get(k, k) for k in self.written_registers}
        self.record_uses = {owner: ({numbers.get(k, k) for k in r}, {numbers.get(k, k) for k in f})
                            for owner, (r, f) in self.record_uses.items()}  # fmt: skip
        self.result.notes = [dataclasses.replace(note, message=number(note.message)) for note in self.result.notes]
        if self.result.wait_clock:
            self.result.wait_clock = (number(self.result.wait_clock[0]), number(self.result.wait_clock[1]))

    def _text_sides(self, selected: list[tuple[n.Module, n.Routine]]) -> None:
        """The routines a TRAP runs, and those the programs run too. A TRAP can stop a program between the
        line loading a text into a scratch register and the line reading it: what a TRAP runs loads its
        texts into scratch registers of its own."""
        traps = {r.name.upper() for _, r in selected if r.kind == "TRAP"}
        self.trap_side = traps | self.no_group
        main: set[str] = set()
        for _, routine in selected:
            if routine.kind != "TRAP" and routine.name.upper() not in self.trap_side:
                main |= {routine.name.upper()} | called_by(routine, self.procs)
        self.both_sides = self.trap_side & main

    def string_register(self, name: str, key: str | None = None) -> str:
        """SR[n:name] keeping a string the programs change; a TODO when the controller has none left."""
        limit = self.config.limits.get("SR", SR_LIMIT)
        number = self.texts.number(name, key)
        if number > limit:
            self.texts.release(key or name)
            self.text_over.setdefault(key or name, name)
            raise Untranslatable(f"{name}: no string register left, the controller has {limit} (SR[1] to"
                                 f" SR[{limit}]): see the TODO listing the strings", Blocker.CAPACITY)  # fmt: skip
        return f"SR[{number}]"  # the controller keeps no comment of a string register (ROBOGUIDE)

    def text_scratch(self, slot: int, trap: bool) -> str:
        """A scratch string register, from the top: a text is loaded into it just before it is read, and never
        kept from one instruction to the next. What a TRAP runs has its own (_text_sides)."""
        name = ("TrapText" if trap else "Text") + ("" if slot == 1 else str(slot))
        key = f"CROSSARM.{name.upper()}"
        limit = self.config.limits.get("SR", SR_LIMIT)
        number = self.texts.number(name, key, top=limit)
        if not 0 < number <= limit:
            self.texts.release(key)
            self.text_over.setdefault(key, name)
            raise Untranslatable(f"no string register left for the scratch register {name}, the controller has"
                                 f" {limit}", Blocker.CAPACITY)  # fmt: skip
        self.scratch_texts.add(f"SR[{number}]")
        return f"SR[{number}]"

    def text_program(self) -> str:
        """The program loading a text into a string register, named when first used: a program the robot or
        a routine already has keeps its name, this one takes a suffix."""
        if self.result.text_program is None:
            taken = self.shared.program_names | set(self.program_names.values())
            base = tp_program_name(TEXT_PROGRAM, self.config.program_name_max_length)
            name, base = self.program_name(TEXT_KEY, base, taken)
            if name != base:
                why = (f"the FANUC robot already has a program {base}, which loading it would replace"
                       if base in self.shared.existing_programs else f"{base} is the name of another program")  # fmt: skip
                self.note(name, None, "WARNING", f"the program loading texts is written as {name}.LS: {why}",
                          Blocker.RENAMED)  # fmt: skip
            self.shared.program_names.add(name)
            self.shared.given_programs.add(name)
            self.result.program_keys[TEXT_KEY] = name
            self.result.text_program = name
        return self.result.text_program

    def _write_text_program(self) -> None:
        """The program loading a text into a string register, once per task, when a program loads one:
        `CALL CA_TEXT(3,'IDLE',0)`. A line cannot write a text in a string register (ROBOGUIDE refuses
        `SR[3]='IDLE'`); a program given it as an argument can. AR[3]=1 adds it at the end (a text of more
        than 38 characters, given in pieces). No motion group: a TRAP can call it."""
        if self.result.text_program is not None:
            lines = ["!Text AR[2] into SR[AR[1]]", "!AR[3]=1: added at its end", "IF AR[3]=1,JMP LBL[1]",
                     "SR[AR[1]]=AR[2]", "END", "LBL[1]", "SR[AR[1]]=SR[AR[1]]+AR[2]"]  # fmt: skip
            attrs = Attributes(comment="CrossArm text", created=self.config.timestamp, default_group=NO_GROUP)
            program = Program(self.result.text_program, [Instruction(text) for text in lines], [], attrs)
            self.result.programs.append(ProgramInfo(program, "", TEXT_PROGRAM, ()))
        traps = [a for a in self.texts.allocations() if a.key.startswith("CROSSARM.TRAPTEXT")]
        if traps:
            self.note("", None, "WARNING", "what the TRAPs run loads its texts into "
                      f"{' and '.join(f'SR[{a.number}]' for a in traps)}, apart from the scratch string registers of"
                      " the programs: a TRAP can stop a program between the line loading a text and the line"
                      " reading it", Blocker.TEXT)  # fmt: skip
        if self.text_over:
            names = sorted(self.text_over.values(), key=str.upper)
            limit = self.config.limits.get("SR", SR_LIMIT)
            self.note("", None, "TODO", f"{len(names)} string(s) without a string register, the controller has"
                      f" {limit} (SR[1] to SR[{limit}]): {', '.join(names)}. Their uses are TODO: pin fewer strings,"
                      ' or raise "limits": {"SR": n} if the controller has more', Blocker.CAPACITY)  # fmt: skip

    # -- shared services -----------------------------------------------------

    def note(self, program: str, line: int | None, kind: str, message: str, category: str = Blocker.OTHER) -> None:
        self.result.notes.append(Note(program, line, kind, message, category))

    def warn_once(self, key: str, program: str, line: int | None, message: str,
                  category: str = Blocker.OTHER) -> None:  # fmt: skip
        if key not in self._warned:
            self._warned.add(key)
            self.note(program, line, "WARNING", message, category)

    def frame_number(self, kind: str, expr: n.Expr | None, program: str, line: int) -> int:
        """UFRAME (kind "UF") or UTOOL ("UT") number for a wobj/tool argument."""
        if expr is None:
            expr = n.Name(n.Span(line, 0), "wobj0")
        if not isinstance(expr, n.Name):
            raise Untranslatable(f"{'work object' if kind == 'UF' else 'tool'} must be a named data: {format_expr(expr)}", Blocker.RUNTIME_FRAME)
        table = self.uframes if kind == "UF" else self.utools
        number = table.number(expr.name)
        key = (kind, number)
        if key not in self.frames:
            try:
                frame = self.declared_frame(kind, expr)
                problem = ""
                if kind == "UF" and frame.robhold:
                    problem = "robot-held work object (stationary tool): not supported, frame values not usable"
                elif kind == "UT" and not frame.robhold:
                    problem = "stationary tool (robhold FALSE): not supported, frame values not usable"
                elif kind == "UT":
                    frame = tool_on_flange(frame, self.config.tool_pin)
            except Unresolvable as exc:
                frame, problem = None, str(exc)
            limit = self.config.limits.get("UFRAME" if kind == "UF" else "UTOOL")
            bank = slot = None
            if kind in self.slots and limit is not None and number > limit:
                if not self._banks:
                    raise Untranslatable(f"{expr.name}: {'UFRAME' if kind == 'UF' else 'UTOOL'} {number} is above the"
                                         f" {limit} the controller holds, and no position register is left to keep it"
                                         " in", Blocker.CAPACITY)  # fmt: skip
                bank, slot = self._banks.pop(0), self.slots[kind]
            self.frames[key] = FrameInfo(number, expr.name, frame, problem, bank, slot)
            if frame is not None and frame.saved and not problem:
                what = "work object" if kind == "UF" else "tool"
                self.note(
                    program, line, "WARNING",
                    f"{what} {expr.name}: value as saved in the backup ({', '.join(frame.saved)} changed by the "
                    "programs at run time, e.g. by a calibration): check it on the robot",
                    Blocker.SAVED_FRAME,
                )  # fmt: skip
        if self.frames[key].problem.startswith(("robot-held", "stationary")):
            raise Untranslatable(self.frames[key].problem, Blocker.STATIONARY)
        return number

    def _controller_comments(self) -> None:
        """Keep only the comments the controller keeps when it loads the program.

        Observed on ROBOGUIDE round trips: a register comment is stored only when
        the register is written (assignment, FOR); flag comments are never stored.
        Dropping the others makes the output identical to the controller's view.
        """
        def register(match: re.Match[str]) -> str:
            return match[0] if int(match[1]) in self.written_registers else f"R[{match[1]}]"

        for info in self.result.programs:
            lines = info.program.lines
            for i, line in enumerate(lines):
                if isinstance(line, Instruction) and not line.text.startswith("!"):
                    text = re.sub(r"R\[(\d+):[^\]]*\]", register, line.text)
                    lines[i] = Instruction(re.sub(r"F\[(\d+):[^\]]*\]", r"F[\1]", text))

    def written_register(self, name: str, key: str | None = None) -> str:
        text = self.register(name, key)
        self.written_registers.add(int(text[2 : text.index(":")]))
        return text

    def register(self, name: str, key: str | None = None) -> str:
        decl = self.symbols.get(name)
        detail = ""
        if decl is not None and decl.init is not None:
            detail = f"RAPID {decl.storage} initial value {format_expr(decl.init)}: set it on the controller"
        return f"R[{self.registers.number(name, key, detail)}:{_comment(name)}]"

    def flag(self, name: str) -> str:
        return f"F[{self.flags.number(name)}:{_comment(name)}]"

    def signal(self, expr: n.Expr, program: str, line: int) -> str | None:
        """'DI[n]' / 'DO[n]' if expr designates a digital signal, else None."""
        if isinstance(expr, n.FuncCall) and expr.name.upper() in ("DINPUT", "DOUTPUT", "TESTDI") and len(expr.args) == 1:
            arg = expr.args[0].value  # TestDI(di): TRUE when the input is 1, as DI[n]=ON
            if isinstance(arg, n.Name):
                table, prefix = (self.douts, "DO") if expr.name.upper() == "DOUTPUT" else (self.dins, "DI")
                return f"{prefix}[{table.number(arg.name)}]"
            return None
        if not isinstance(expr, n.Name) or self.symbols.get(expr.name) is not None:
            return None
        key = expr.name.upper()
        # Priority: mapping file, then EIO.cfg, then how the program uses it, then its name.
        if key in self.config.digital_inputs:
            return f"DI[{self.dins.number(expr.name)}]"
        if key in self.config.digital_outputs:
            return f"DO[{self.douts.number(expr.name)}]"
        if key in self.eio:
            sig = self.eio[key]
            detail = f"EIO.cfg: {sig.signal_type}, device {sig.device or '-'}, map {sig.device_map or '-'}"
            if sig.signal_type == "DI":
                return f"DI[{self.dins.number(expr.name, detail=detail)}]"
            if sig.signal_type == "DO":
                return f"DO[{self.douts.number(expr.name, detail=detail)}]"
            if sig.signal_type == "GI":
                return None  # not a digital signal: read as a value, GI[n] (_RoutineTranslator.numeric)
            raise Untranslatable(f"'{expr.name}' is a {sig.signal_type} signal: group/analog I/O is not converted", Blocker.SIGNAL)
        if self.eio:
            self.warn_once(f"signal-eio:{key}", program, line, f"'{expr.name}' is not declared in EIO.cfg",
                           Blocker.SIGNAL)
        if key in self.di_names:
            return f"DI[{self.dins.number(expr.name)}]"
        if key in self.do_names:
            return f"DO[{self.douts.number(expr.name)}]"
        match = _SIGNAL_PREFIX.match(expr.name)
        if match:
            is_input = match.group().upper() == "DI"
            self.warn_once(
                f"signal:{key}", program, line,
                f"'{expr.name}' assumed to be a digital {'input' if is_input else 'output'} from its name",
                Blocker.SIGNAL,
            )  # fmt: skip
            table, prefix = (self.dins, "DI") if is_input else (self.douts, "DO")
            return f"{prefix}[{table.number(expr.name)}]"
        return None


# ---------------------------------------------------------------------------
# One RAPID routine -> one TP program
# ---------------------------------------------------------------------------


class _RoutineTranslator(RuntimePoints, RoutineCalls, KarelPoses, KarelFiles, FrameFields, FrameWrites, FuncInline,
                         LateCalls, SystemData):
    def __init__(self, conv: Converter, module: n.Module, routine: n.Routine, tp_name: str) -> None:
        self.c = conv
        self.module = module
        self.routine = routine
        self.name = tp_name
        self.lines: list[Instruction | Motion] = []
        self.tags = SourceTags()  # the RAPID line each of them comes from, for the report
        self.positions: list[Position] = []
        self.points: list[PointInfo] = []
        self._point_keys: dict[tuple, int] = {}
        self.active_uf: tuple[int, int | None] | None = None  # (number, PR it was loaded from)
        self.active_ut: tuple[int, int | None] | None = None
        self.loop_vars: dict[str, str] = {}  # RAPID FOR variable -> register text
        layout = conv.signatures.get(routine.name.upper())
        self.args: Signature | None = layout if isinstance(layout, Signature) else None  # its parameters: AR[n]
        self.copies: dict[str, str] = {}  # parameters it changes: upper name -> register holding the copy
        # id() of a provided function's call being assigned -> (its result register, what it returns): calls.py
        self.provided_results: dict[int, tuple[str, str]] = {}
        self.given: dict[str, str] = {}  # its speeds and corners given as arguments ('V.TCP') -> their register
        self.both_ways: str | None = None  # the move being written: the register of a CNT some calls pass fine for
        self._on_timeout: OnTimeout | None | bool = False  # what its ERROR handler does when a wait times out
        self.timed_waits = 0  # waits with \MaxTime written with the handler's timeout path
        self.error_jumps: tuple[int, int] | None = None  # (RETRY, TRYNEXT) labels while writing that path
        self.strict = 0  # >0: a statement that cannot be converted fails the enclosing one instead of a TODO
        self.after: tuple[n.Stmt, ...] = ()  # what follows the statement being written, in its block
        self.last_tool: n.Expr | None = None  # the tool of the last move written, while it is still selected
        # The array element R[PointIndex] points to, while nothing has changed it: (array, index operands).
        self.point_index: tuple[str, tuple[str, ...]] | None = None
        # Elements of arrays of numbers whose index a register holds: (array, index operands) -> 'R[R[n]]'.
        self.number_index: dict[tuple[str, tuple[str, ...]], str] = {}
        self.number_slots: set[str] = set()  # the index registers the statement being written reads
        self.index_reads: dict[tuple[str, tuple[str, ...]], set[int]] = {}  # cached index -> registers it reads
        self.next_speed: n.Expr | None = None  # the speed of the move after the one being written, if a move
        self.next_label = 1
        # What the routine's data holds at the statement being written (crossarm.convert.compute): upper-case
        # name -> Typed, or Unknown (and why) when it depends on the run. Its own data from its declaration on,
        # module data once the routine sets it. Anything else is read as declared, if nothing changes it.
        self.known: dict[str, Typed | Unknown] = {}
        self.local_names: set[str] = set()
        # A TRAP: the interrupt it serves, and what it ends with (arming its condition program again).
        served = [i for i in conv.interrupts.values() if i.program and i.trap == routine.name.upper()]
        self.served = served if routine.kind == "TRAP" else []  # the interrupts it serves, converted
        self.interrupt = served[0] if len(self.served) == 1 and not served[0].shared else None  # served directly
        self.epilogue: list[str] = []
        self.stepless = False  # writing a condition read again and again (a wait): no calculation before it
        self.time_flag: str | None = None  # the bool a wait's \\TimeFlag sets (max_time, wait)
        self.text_slots: set[int] = set()
        self.current: n.Stmt | None = None  # the innermost statement being written
        self.text_params = frozenset(p.name for g in parse_params(routine.params) or [] for p in g)

    def run(self) -> ProgramInfo:
        self.c.symbols.enter_routine(self.routine)
        read = parameters(self.routine.params)
        self.c.parameters = set(read[0]) | read[1] if read else set()
        self.c.computer.scope, self.c.evaluator.known = self.scope, self.known_value
        self.c.evaluator.fields = self.field_value
        try:
            return self._run()
        finally:
            self.c.computer.scope, self.c.evaluator.known = (lambda name: None), None
            self.c.evaluator.fields = None

    def _run(self) -> ProgramInfo:
        for text in remark_lines(f"RAPID {self.module.name}.{self.routine.name}"):
            self.emit(text)
        parts = [f for s in self.args.slots if s.kind == "record" for f in s.fields] if self.args else []
        for slot in [*self.args.slots, *parts] if self.args else ():  # a record's num components it changes too
            if slot.key in self.args.copied:  # type: ignore[union-attr]
                register = self.c.written_register(slot.name, key=f"{self.name}.{slot.name}")
                self.copies[slot.key] = register
                self.emit(f"{register}={self.args.register(slot.key)}")  # type: ignore[union-attr]
        for slot in self.args.arguments if self.args else ():
            if slot.kind in MOTION_ARGUMENTS:  # a move takes no AR[n] as its speed or CNT (measured)
                register = self.c.written_register(slot.name, key=f"{self.name}.{slot.name}")
                self.given[slot.key] = register
                self.emit(f"{register}={self.args.register(slot.key)}")  # type: ignore[union-attr]
        if self.interrupt is not None:
            self._trap_prologue(self.interrupt)
        self.block(self.routine.body)
        for text in self.epilogue:
            self.emit(text)
        for handler in self.routine.handlers:
            start = len(self.lines)
            self.handler(handler)
            self.tags.tag(self.lines, start, handler.span.line)
        attrs = Attributes(comment=ascii_text(self.routine.name)[:16], created=self.c.config.timestamp)
        # A TRAP runs as a task of its own while the program it interrupted holds the robot (interrupts.called_by)
        if self.routine.kind == "TRAP" or self.routine.name.upper() in self.c.no_group:
            attrs.default_group = NO_GROUP
        program = Program(self.name, self.lines, self.positions, attrs)
        return ProgramInfo(program, self.module.name, self.routine.name, tuple(self.points),
                           self.tags.of(self.lines), self.routine.span.line)  # fmt: skip

    def _trap_prologue(self, interrupt: Interrupt) -> None:
        """An IPers TRAP first notes the value that fired it; every TRAP but a \\Single one arms its
        condition program again as it ends: the controller disarms it when it fires (ROBOGUIDE)."""
        if interrupt.kinds == {"PERS"} and interrupt.watched is not None:
            try:
                self.emit(f"{self.c.pers_copy(interrupt)}={operand(self.numeric(interrupt.watched))}")
            except (Untranslatable, Unresolvable):
                pass  # IPers itself stays TODO, with why
        if not interrupt.single:
            self.epilogue = [f"MONITOR {interrupt.program}"]

    # -- output helpers --------------------------------------------------------

    # -- data known at this point ---------------------------------------------------

    def scope(self, name: str) -> Typed | Unknown | None:
        """For crossarm.convert.compute: the routine's own value of a data, Unknown, or None (read it as declared)."""
        key = name.upper()
        if key in self.c.volatile:
            return None  # a TRAP may change it at any time: read it where it is kept
        if key in self.known:
            return self.known[key]
        if key in self.loop_vars:
            return Unknown("is a FOR loop counter")
        if key in self.c.parameters:
            raise Unresolvable(f"'{name}' is a parameter of the routine: its value comes from the caller")
        return None

    def known_value(self, name: str):
        """For the Evaluator: the value of a data this routine set, None if it did not."""
        found = None if name.upper() in self.c.volatile else self.known.get(name.upper())
        if isinstance(found, Unknown):
            raise found.error(name)
        if isinstance(found, Typed) and (hole := first_hole(found.value)) is not None:  # a field not known here
            raise hole.error()
        return found.value if isinstance(found, Typed) else None

    def forget(self, stmts: Iterable[n.Stmt], why: Unknown) -> None:
        """What these statements may change is no longer known: they ran, or might have."""
        names, anything = self.c.effects.of(stmts)
        for name in names:
            self.known[name] = why
            if f"{name}#ROT" in self.known:  # the orientation of a point kept in a register goes with it
                self.known[f"{name}#ROT"] = why
        if anything:
            for name in self.known:
                if name not in self.local_names:
                    self.known[name] = why

    def merge(self, line: int, *states: dict[str, Typed | Unknown], what: str = "IF") -> None:
        """After an IF or a TEST: what every path left the same is known, the rest is not."""
        merged: dict[str, Typed | Unknown] = {}
        differs = Unknown(f"is set differently in the branches of the {what} at l.{line}")
        for name in set().union(*states):
            values = [state.get(name, differs) for state in states]
            first = values[0]
            if all(isinstance(v, Typed) and v == first for v in values):
                merged[name] = first
            else:  # measured on one path: a calibration whichever way
                merged[name] = next((v for v in values if isinstance(v, Unknown) and v.measured), differs)
        self.known = merged

    def emit(self, text: str) -> None:
        self.lines.append(Instruction(text))
        if text.startswith(_CHANGES_INDEX):  # the program may arrive here from elsewhere, or a register have changed
            self.point_index = None
            self.number_index = {}
            self.index_reads = {}
        elif written := _WRITES_REGISTER.match(text):  # R[n]=...: the indices read from R[n], or held in it, are stale
            number = int(written[1])
            self.index_reads = {k: v for k, v in self.index_reads.items() if number not in v}
            if self.point_index is not None and self.point_index not in self.index_reads:
                self.point_index = None
            self.number_index = {k: v for k, v in self.number_index.items() if k in self.index_reads}
        if text.startswith(("LBL[", "CALL ")):
            # A jump can land on a label from anywhere, and a called program can select other frames
            # (UTOOL_NUM is the controller's, not the program's): the active frames are no longer known.
            self.active_uf = self.active_ut = None

    def todo(self, stmt: n.Stmt, reason: str, category: str = Blocker.OTHER) -> None:
        line = stmt.span.line
        source = " ".join((stmt.raw if isinstance(stmt, n.Unsupported) else self.rapid_text(stmt)).split())
        self.emit(("!" + ascii_text(f"TODO l.{line} {source.rstrip(';')}")[:REMARK_MAX]).rstrip())  # as the controller stores it
        self.c.not_converted.update(id(s) for s in walk_statements((stmt,)))
        self.c.note(self.name, line, "TODO", f"{reason} — `{source[:80]}`", category)
        # A search stops on a contact: the point it records is measured on the robot too
        measured = category == Blocker.CALIBRATION or (
            isinstance(stmt, n.ProcCall) and stmt.name.upper() in ("SEARCHL", "SEARCHJ", "SEARCHC"))  # fmt: skip
        why = Unknown(f"is {'measured on the robot' if measured else 'set'} at l.{line} (left TODO)", measured)
        if not self.forget_field(stmt, why):  # a field of a tool or work object: that field alone (frame_fields)
            self.forget((stmt,), why)
        path = path_of(stmt.target) if isinstance(stmt, n.Assign) else None
        if isinstance(stmt, n.ProcCall) and stmt.name.upper() == "SEARCHL":  # the point it finds
            found = [a.value for a in stmt.args if a.name is None][1:2]
            path = (found[0].name.upper(),) if found and isinstance(found[0], n.Name) else None
        if path and self.runtime_key(path[0]):  # its register was not set: what reads it must not move there
            self.known[f"{path[0]}#UNSET"] = self.known.get(path[0], Unknown(f"is set at l.{line} (left TODO)"))
        if isinstance(stmt, n.Unsupported) and stmt.kind == "LABEL":  # jumped to from anywhere: nothing is known
            self.known = dict.fromkeys(self.known, Unknown(f"may hold anything at the label at l.{line}"))

    def rapid_text(self, stmt: n.Stmt) -> str:
        """The RAPID source line of a statement (comment stripped), or a re-print of it."""
        if (made := self.c.inline_texts.get(id(stmt))) is not None:  # a statement of an inlined FUNC
            return made
        lines = self.c.source_lines.get(self.module.name.upper())
        if lines and 0 < stmt.span.line <= len(lines):
            text = lines[stmt.span.line - 1]
            if '"' not in text:
                text = text.split("!", 1)[0]
            return text.strip()
        return _source(stmt)

    def warn(self, stmt: n.Stmt, message: str, category: str = Blocker.OTHER) -> None:
        self.c.note(self.name, stmt.span.line, "WARNING", message, category)

    def label(self) -> int:
        number = self.next_label
        self.next_label += 1
        return number

    # -- statements -------------------------------------------------------------

    def block(self, stmts: tuple[n.Stmt, ...]) -> None:
        for i, stmt in enumerate(stmts):
            # The move that follows a move, past what the robot does not stop for: a corner into a faster
            # move is rounded more.
            following = next_move(stmts, i)
            self.next_speed = following.speed if following is not None else None
            self.after = stmts[i + 1 :]
            self.number_slots = set()
            self.text_slots: set[int] = set()  # the scratch string registers the statement being written uses
            outer, self.current = self.current, stmt
            if self.strict:
                self.stmt(stmt)
                self.current = outer
                continue
            checkpoint = (len(self.lines), len(self.positions), len(self.points), self.active_uf, self.active_ut)
            deferred = self.c.deferring(self.c.registers.table.defer or self.text_new(stmt))
            try:
                self.stmt(stmt)
            except (Untranslatable, Unresolvable) as exc:
                self._rollback(checkpoint)
                # An Unresolvable that reaches here is always a value we could not work out.
                measured = Blocker.CALIBRATION if isinstance(exc, MeasuredAtRunTime) else Blocker.VALUE
                none = no_tp_equivalent(stmt, self.c.procs.keys() | self.c.computer.functions.keys(),
                                         self.c.symbols.type_of, KAREL_FILES if self.c.config.karel else (),
                                         self.c.config.karel)
                text = text_todo(stmt, self.c.procs.keys() | self.c.computer.functions.keys())
                if none is not None:
                    self.todo(stmt, none, Blocker.NO_TP_EQUIVALENT)
                elif text is not None:
                    self.todo(stmt, text, Blocker.VALUE)
                elif (name := self.not_declared(exc)) is not None:
                    self.todo(stmt, str(self.not_in_backup(name, "data")), Blocker.MISSING)
                elif (getattr(exc, "category", measured) in (Blocker.VALUE, Blocker.CALIBRATION)
                      and (through := self.c.routine_use.of(stmt)) is not None):  # fmt: skip
                    self.todo(stmt, through, Blocker.NO_TP_EQUIVALENT)  # the value is a file's or a socket's
                else:
                    self.todo(stmt, str(exc), getattr(exc, "category", measured))
            except Exception as exc:  # noqa: BLE001 - one statement must never cost the whole backup
                # A bug in CrossArm on an unusual statement. Without this, the exception would end
                # the whole task: a hundred programs lost for one line. It becomes a TODO that
                # says where, so it can be reported, and the conversion goes on.
                self._rollback(checkpoint)
                where = traceback.extract_tb(exc.__traceback__)[-1]
                self.todo(stmt, f"CrossArm internal error, please report it: {type(exc).__name__}: {exc} "
                                f"(at {Path(where.filename).name}:{where.lineno})", Blocker.INTERNAL)  # fmt: skip
            finally:
                self.c.deferring(deferred)
                self.current = outer
            self.tags.tag(self.lines, checkpoint[0], stmt.span.line)

    def not_declared(self, exc: BaseException) -> str | None:
        """The data a statement failed on because no module of the backup declares it, if that is why: the
        lookup that failed may be what the error was raised from (a value given up on for that reason)."""
        seen: BaseException | None = exc
        for _ in range(8):
            if seen is None:
                return None
            if isinstance(seen, NotInBackup) and self.absent(seen.name):
                return seen.name
            seen = seen.__cause__ or seen.__context__
        return None

    def absent(self, name: str) -> bool:
        """No module of the backup declares this data, and it is neither the routine's own, nor RAPID's, nor a
        signal CrossArm knows of."""
        key = name.upper()
        params = parse_params(self.routine.params)
        if params is None and self.routine.params.strip():
            return False  # its parameters cannot be read: it may be one
        if self.c.symbols.get(name) is not None or key in self.local_names or key in self.loop_vars:
            return False
        if any(p.name.upper() == key for group in params or [] for p in group):
            return False
        c = self.c
        return not (key in PREDEFINED or key in RAPID_DATA or key.startswith("ERR_") or key in c.eio
                    or key in c.config.digital_inputs or key in c.config.digital_outputs or key in c.di_names
                    or key in c.do_names or _SIGNAL_PREFIX.match(name) or key in c.procs
                    or key in c.computer.functions)  # fmt: skip

    def not_in_backup(self, name: str, what: str) -> "Untranslatable":
        """What to add to the backup for a routine or data none of its modules declares."""
        text = f"{what} '{name}' is not in the backup: add the module that declares it (system module, option, other task)"
        if what == "data" and not self.c.eio:
            text += ", or EIO.cfg if it is a signal"
        return Untranslatable(text, Blocker.MISSING)

    def _rollback(self, checkpoint: tuple) -> None:
        """Drop what a statement emitted before failing: its lines, the P[n] it created, the frames it selected."""
        lines, positions, points, self.active_uf, self.active_ut = checkpoint
        self.point_index = None
        self.number_index = {}
        self.index_reads = {}
        del self.lines[lines:]
        del self.positions[positions:]
        del self.points[points:]
        self._point_keys = {k: v for k, v in self._point_keys.items() if v <= positions}

    def stmt(self, s: n.Stmt) -> None:
        if self.c.externals and (why := self.provided_function(s)) is not None:
            raise Untranslatable(why, Blocker.PROVIDED_FUNCTION)
        match s:
            case n.Comment(text=text):
                for remark in remark_lines(text):
                    self.emit(remark)
            case n.DataDecl():
                self.local_decl(s)
            case n.Move():
                self.move(s)
            case n.SetSignal(signal=signal, value=value):
                self.emit(f"{self.output(signal, s)}={'ON' if value else 'OFF'}")
            case n.WaitTime(seconds=seconds, options=options):
                if options:
                    self.warn(s, f"WaitTime options ignored: {' '.join(a.name or '' for a in options)}",
                              Blocker.OPTIONS_IGNORED)
                value = self.single(seconds, bare=True)
                self.emit(f"WAIT {value}" if value.startswith(("R[", "AR[")) else f"WAIT {fmt_seconds(float(value))}(sec)")
            case n.ProcCall():
                self.call(s)
                self.forget((s,), Unknown(f"may be changed by the call at l.{s.span.line}"))
            case n.Assign():
                self.assign(s)
            case n.If():
                self.if_stmt(s.branches, s.else_body)
            case n.For():
                self.for_stmt(s)
            case n.While():
                self.while_stmt(s)
            case n.Test():
                self.test_stmt(s)
            case n.Return(value=None):
                for text in self.epilogue:
                    self.emit(text)
                self.emit("END")
            case n.Exit():
                self.emit("ABORT")
            case n.Unsupported(kind="RETRY") if self.error_jumps:
                self.emit(f"JMP LBL[{self.error_jumps[0]}]")
            case n.Unsupported(kind="TRYNEXT") if self.error_jumps:
                self.emit(f"JMP LBL[{self.error_jumps[1]}]")
            case n.Unsupported(kind="CONNECT"):
                self.connect(s)
            case n.Unsupported(kind="LATE_BINDING"):
                self.late_call(s)  # convert.late_calls
            case n.Unsupported() if self.strict:
                raise Untranslatable(s.reason, Blocker.rapid(s.kind))
            case n.Unsupported():
                self.todo(s, s.reason, Blocker.rapid(s.kind))
            case _:
                raise Untranslatable(f"{type(s).__name__} has no TP mapping", Blocker.OTHER)

    def local_decl(self, decl: n.DataDecl) -> None:
        # Positions and other data are resolved on use; num/bool locals become registers/flags.
        key, type_name = decl.name.upper(), decl.type_name.lower()
        self.local_names.add(key)
        try:  # RAPID sets a routine's VAR each time the routine starts: its initial value, else zeros
            if decl.init is not None:
                value = self.c.computer.value(decl.init).value
            elif decl.dims:
                raise Unresolvable("array")
            else:
                value = self.c.computer.layouts.default(type_name)
            self.known[key] = Typed(value, type_name, len(decl.dims))
        except Unresolvable as exc:
            self.known[key] = Unknown(f"has an initial value only known at run time ({exc})")
        if self.c.records.is_record(type_name) and not decl.dims:
            self.local_record(decl)
            return
        if type_name == "string" and not decl.dims:
            self.local_text(decl)
            return
        if decl.init is None or decl.dims:
            return
        if (key := self.runtime_key(decl.name)) is not None:  # set when the routine starts, as RAPID does
            self.runtime_assign(n.Assign(decl.span, n.Name(decl.span, decl.name), decl.init), key, (key,))
            return
        if decl.type_name.lower() in _NUMBERS:
            self.emit(f"{self.c.written_register(decl.name)}={operand(self.numeric(decl.init))}")
        elif decl.type_name.lower() == "bool":
            self.set_flag(lambda: self.c.flag(decl.name), decl.init)

    def local_record(self, decl: n.DataDecl) -> None:
        """A record of the routine: the fields the programs change, set to their initial value where the routine
        starts (RAPID sets a routine's VAR again at each call). Not one of a routine calling itself back, nor
        one with other fields than num and bool: their uses stay TODO."""
        whole = Field(decl, (), decl.type_name.lower())
        kept = [leaf for leaf in self.c.records.leaves(whole) if self.c.records.changed(leaf)]
        if not kept:
            return
        try:
            program = self.record_owner(whole)
        except Untranslatable:
            return
        numbers = []
        for leaf in kept:
            value = self.c.records.initial(leaf)
            register = self.c.field_number(leaf, leaf.type == "bool", program)
            numbers.append(register.split(":")[0] + "]")
            self.emit(f"{register}=({'ON' if value else 'OFF'})" if leaf.type == "bool" else f"{register}={operand(register_value(float(value)))}")
        self.c.warn_once(
            f"local:{self.name}.{decl.name.upper()}", self.name, decl.span.line,
            f"{self.routine.name}.{decl.name}, a record of the routine, is kept in {', '.join(numbers)}: set to its"
            " initial value where the routine starts, as RAPID does at each call. Registers are global: any"
            " program can read them, and one routine calling another that calls it back would share them",
            Blocker.LOCAL_RECORD,
        )  # fmt: skip

    # -- motion -------------------------------------------------------------------

    def move(self, m: n.Move) -> None:
        line = m.span.line
        # Resolve everything first: a failure must not leave a half-created point behind.
        if m.kind is n.MoveKind.ABSJ:
            held = m.wobj is not None and self._stationary("UF", m.wobj)
            # Numbered as before this move was converted: the work object, then the tool unless the work object stopped it.
            uf, ut = self.joint_frame("UF", m.wobj, line), self.joint_frame("UT", m.tool, line, number=not held)
        elif (given := self.given_frames(m)) != (None, None):  # the routine was given its tool or work object
            uf = (given[0], None) if given[0] else self.c.selection("UF", self.c.frame_number("UF", m.wobj, self.name, line))
            ut = (given[1], None) if given[1] else self.c.selection("UT", self.c.frame_number("UT", m.tool, self.name, line))
            self.last_tool = m.tool
        else:
            uf = self.c.selection("UF", self.c.frame_number("UF", m.wobj, self.name, line))
            ut = self.c.selection("UT", self.c.frame_number("UT", m.tool, self.name, line))
            self.last_tool = m.tool
        motion = "J" if m.kind in (n.MoveKind.J, n.MoveKind.ABSJ) else m.kind.value
        evaluator = self.c.evaluator
        to_point, options = m.to_point, ""
        if motion in ("J", "L") and m.kind is not n.MoveKind.ABSJ and (offset := self.tool_offset(m.to_point)):
            to_point, options = offset
        passed = self.passed_point(to_point, "CROSSARM.POINT") if m.kind is not n.MoveKind.ABSJ else self.joints_kept(to_point)
        passed_via = self.passed_point(m.via_point, "CROSSARM.VIA") if m.via_point is not None else None
        if passed and passed_via and passed.startswith("PR[R[") and passed_via.startswith("PR[R["):
            raise Untranslatable("MoveC through two elements of arrays indexed at run time: one index register"
                                 " holds one of them at a time", Blocker.RUNTIME_POSITION)  # fmt: skip
        if passed is not None:
            to_value = None
        else:
            to_value = evaluator.jointtarget(m.to_point) if m.kind is n.MoveKind.ABSJ else evaluator.robtarget(m.to_point)
        via_value = evaluator.robtarget(m.via_point) if m.via_point is not None and passed_via is None else None
        if isinstance(to_value, JointTarget) and len(to_value.joints) < 6:
            raise Untranslatable(f"jointtarget with {len(to_value.joints)} axes", Blocker.MOTION)
        self.both_ways = None
        speed, termination = self.given_motion(m, motion) if self.given else (None, None)
        if speed is None:
            speed, rapid_speed, fanuc_speed = self.speed(m.speed, motion)
        if termination is None:
            termination = self.termination(m.zone, m.speed, motion, rapid_speed, fanuc_speed, self.next_speed)
        given = self.given_frames(m)
        ignored = [a.name for a in m.options if a.name and a.name.upper() != "NOEOFFS"
                   and not (given[0] and a.name.upper() == "WOBJ")]  # fmt: skip
        if ignored:
            self.warn(m, f"motion options ignored: {', '.join(ignored)}", Blocker.OPTIONS_IGNORED)

        if given != (None, None):  # a P is recorded in one tool: its points in registers, moved to in the frames given
            via = passed_via or (self.frame_free(m.via_point, via_value, line) if via_value is not None else None)
            target = passed or self.frame_free(to_point, to_value, line)  # type: ignore[arg-type]
        else:
            via = passed_via or (self.point(m.via_point, via_value, uf, ut, line) if via_value is not None else None)
            target = passed or self.point(m.to_point, to_value, uf, ut, line)  # type: ignore[arg-type]
        for selected, active, kind in ((uf, self.active_uf, "UFRAME"), (ut, self.active_ut, "UTOOL")):
            if selected != active:
                number, bank = selected
                if bank is not None:  # above what the controller holds: loaded into the reserved number
                    self.emit(f"{kind}[{number}]=PR[{bank}]")
                self.emit(f"{kind}_NUM={number}")
        self.active_uf, self.active_ut = uf, ut
        if self.both_ways is None:
            self.lines.append(Motion(motion, target, speed, termination, via, options))
            return
        # A zone some calls pass fine for (101): a TP move is FINE or CNT as written, so it is written both ways.
        fine, after = self.label(), self.label()
        self.emit(f"IF {self.both_ways}>100,JMP LBL[{fine}]")
        self.lines.append(Motion(motion, target, speed, termination, via, options))
        for text in (f"JMP LBL[{after}]", f"LBL[{fine}]"):
            self.lines.append(Instruction(text))  # jumped to from just above: the frames selected are still these
        self.lines.append(Motion(motion, target, speed, "FINE", via, options))
        self.lines.append(Instruction(f"LBL[{after}]"))

    def given_frames(self, m: n.Move) -> tuple[str | None, str | None]:
        """(work object, tool) the move takes from the routine's parameters, as their AR[n]; None for a named
        frame. `\\WObj?wObj` is the work object the routine was given, 0 (wobj0) when it was not."""
        if self.args is None:
            return None, None
        wobj = m.wobj if m.wobj is not None else next(
            (a.value for a in m.options if (a.name or "").upper() == "WOBJ" and a.conditional), None)  # fmt: skip
        uf = self.args.frame(wobj.name) if isinstance(wobj, n.Name) else None
        ut = self.args.frame(m.tool.name) if isinstance(m.tool, n.Name) else None
        if (uf or ut) and m.kind is n.MoveKind.ABSJ:
            raise Untranslatable("MoveAbsJ with a tool or work object the routine is given: the controller refuses a"
                                 " joint point recorded in another tool than the one selected (INTP-253)",
                                 Blocker.RUNTIME_FRAME)  # fmt: skip
        return uf, ut

    def frame_free(self, expr: n.Expr, value: RobTarget, line: int) -> str:
        """A point moved to with a frame the routine is given: kept in a position register SETUP_FRAMES sets, as
        the controller refuses a P recorded in another tool than the one selected (INTP-253); a move to a
        register takes the frames selected when it runs (point probe)."""
        (x, y, z), (w, p, r) = value.pose.pos, value.pose.wpr()
        position = CartesianPosition(x, y, z, w, p, r, self.config_string(value, line))
        name = f"{self.routine.name}.{format_expr(expr)}"
        base = key = re.sub(r"[^A-Z0-9_.]+", "_", name.upper())
        suffix = 1
        while key in self.c.arrays and self.c.arrays[key][2] != (position,):  # the same text, another value
            suffix += 1
            key = f"{base}_{suffix}"
        self.c.arrays.setdefault(key, (name, (1,), (position,)))
        return f"PR[{{PB:{key}:0}}]"

    def tool_offset(self, expr: n.Expr) -> tuple[n.Expr, str] | None:
        """RelTool() of a point given at run time (a routine's point parameter, an array element): the point
        moved to as it is, with `Tool_Offset,PR[m]`, the displacement and rotations in the tool frame, as
        RelTool makes them (TP frame probe: Tool_Offset composes in the tool frame, rotations included). PR[m]
        is a copy of the point with its six components set: a component of a register never set is refused.
        None for anything else: RelTool() of a point known at conversion time is worked out then."""
        if not (isinstance(expr, n.FuncCall) and expr.name.upper() == "RELTOOL"):
            return None
        positional = [a.value for a in expr.args if a.name is None]
        options = {(a.name or "").upper(): a.value for a in expr.args if a.name is not None}
        if len(positional) != 4 or None in positional or not set(options) <= {"RX", "RY", "RZ"}:
            return None
        source = self.point_source(positional[0])  # type: ignore[arg-type]
        if source is None:
            return None
        try:
            turns = {axis: self.c.evaluator.constant_number(value) for axis, value in options.items() if value}
        except Unresolvable as exc:
            raise Untranslatable(f"RelTool rotation only known at run time ({exc}): TP cannot compute the W, P, R"
                                 " it makes", Blocker.RUNTIME_POSITION) from exc  # fmt: skip
        # RAPID turns about the tool's own axes, x then y then z: R.Rx.Ry.Rz (geometry.Pose.rel_tool)
        turned = mat_mul(rot_x(turns.get("RX", 0.0)), mat_mul(rot_y(turns.get("RY", 0.0)), rot_z(turns.get("RZ", 0.0))))
        wpr = [round(angle, 3) + 0.0 for angle in matrix_to_wpr(turned)]
        register = self.c.point_register("CROSSARM.TOOLOFFSET")
        self.emit(f"{register}={source}")
        for axis, value in enumerate(positional[1:], start=1):  # each worked out just before its line
            step, negated = self.displacement(value)  # type: ignore[arg-type]
            self.emit(f"{register[:-1]},{axis}]={f'{step}*(-1)' if negated else step}")
        for axis, angle in enumerate(wpr, start=4):
            self.emit(f"{register[:-1]},{axis}]={operand(fmt_number(angle))}")
        return positional[0], f"Tool_Offset,{register}"  # type: ignore[return-value]

    def displacement(self, value: n.Expr) -> tuple[str, bool]:
        """A component of an Offs() or RelTool() displacement, and whether it is to be negated: `-h` is
        (AR[2], True), a register TP cannot negate in place; `-50` is ((-50), False)."""
        if isinstance(value, n.UnaryOp) and value.op == "-":
            try:
                return operand(self.numeric(value)), False
            except Untranslatable:
                return self.single(value.operand), True
        return self.single(value), False

    def passed_point(self, expr: n.Expr, scratch: str, into: str | None = None) -> str | None:
        """The position register a move goes to when its point is not a P[] of the program: a robtarget parameter
        of the routine (the register the caller set) or an element of an array of points indexed at run time
        (PR[R[n]]). For Offs() of one, a copy offset along the work object's axes, component by component as Offs
        adds; in `into` when given (a point passed on). None when the point is an ordinary one."""
        base, offsets = expr, None
        if (isinstance(expr, n.FuncCall) and expr.name.upper() == "OFFS" and len(expr.args) == 4
                and all(a.name is None and a.value is not None for a in expr.args)):  # fmt: skip
            base, offsets = expr.args[0].value, [a.value for a in expr.args[1:]]
        source = self.point_source(base)  # type: ignore[arg-type]
        if source is None and offsets is not None and (fixed := self._offset_base(expr, base)) is not None:
            # Offs() of a point known now by what is only known at run time: `MoveL Offs(pCorner,nCol*L,0,0)`
            copy = into or self.c.point_register(scratch)
            self.emit(f"{copy}={self.known_point(base, fixed, expr.span.line)}")  # type: ignore[arg-type]
            self.add_offsets(copy, offsets)  # type: ignore[arg-type]
            return copy
        if source is None:
            points = {s.key for s in self.args.slots if s.kind == "robtarget"} if self.args else set()
            if {word.upper() for word in re.findall(r"[A-Za-z_]\w*", format_expr(expr))} & points:
                raise Untranslatable(f"'{format_expr(expr)}': a point passed to the routine is moved to as it is,"
                                     " with Offs() or RelTool(), and passed on as it is or with Offs()",
                                     Blocker.RUNTIME_POSITION)  # fmt: skip
            return None
        if offsets is None and into is None:
            return source
        copy = into or self.c.point_register(scratch)
        if copy != source:  # a point offset in its own register (pAt:=Offs(pAt,...)) is not copied first
            self.emit(f"{copy}={source}")
        self.add_offsets(copy, offsets or [])  # type: ignore[arg-type]
        return copy

    def _offset_base(self, expr: n.Expr, base: n.Expr | None) -> RobTarget | None:
        """The point Offs() offsets when it is known now while the offsets are not; None otherwise (all known:
        worked out whole, as a P)."""
        try:
            self.c.evaluator.robtarget(expr)
            return None
        except Unresolvable:
            pass
        try:
            return self.c.evaluator.robtarget(base)  # type: ignore[arg-type]
        except Unresolvable:
            return None

    def add_offsets(self, register: str, offsets: list[n.Expr]) -> None:
        """Offs() on a position register: each displacement added to its component, worked out just before its
        line (a calculation made in a scratch register first must not be overwritten by the next one's)."""
        for axis, value in enumerate(offsets, start=1):
            offset, negated = self.displacement(value)
            if offset != "0":  # one operator: `+` and `*` in one calculation are refused (ASBN-040)
                self.emit(f"{register[:-1]},{axis}]={register[:-1]},{axis}]{'-' if negated else '+'}{offset}")

    def point_source(self, expr: n.Expr) -> str | None:
        """PR[k] for a robtarget parameter, PR[R[n]] for an array of points indexed at run time (the index worked
        out in a register first); None for anything else."""
        if (result := self.provided_point(expr)) is not None:  # a provided function's point (calls.py)
            return result
        if isinstance(expr, n.Name) and self.args and self.args.kind(expr.name) == "robtarget":
            return self.c.point_register(f"{self.args.routine}.{expr.name}")
        if isinstance(expr, n.Name) and (key := self.runtime_key(expr.name)):
            self.runtime_set(expr.name)
            return self.c.point_register(key)
        if not (isinstance(expr, n.Index) and isinstance(expr.base, n.Name)):
            return None
        decl = self.c.symbols.get(expr.base.name)
        if decl is None or decl.type_name.lower() != "robtarget" or len(decl.dims) != len(expr.indices):
            return None
        try:
            [self.c.evaluator.constant_number(i) for i in expr.indices]
            return None  # a fixed element: a point like any other
        except Unresolvable:
            pass
        self._fixed_array(decl, expr, "points", Blocker.RUNTIME_POSITION)
        key = self._point_array(decl, expr.span.line)
        dims = self.c.arrays[key][1]
        indices = [self.numeric(i) for i in expr.indices]
        register = self.c.written_register("PointIndex", key="CROSSARM.POINTINDEX")
        bare = f"PR[{register.split(':')[0]}]]" if ":" in register else f"PR[{register}]"
        if self.point_index == (key, tuple(indices)):  # worked out already, and nothing changed it since
            return bare
        # Row after row, as RAPID lays an array out: {i,j} of {a,b} is the (i-1)*b + j-th element.
        self.emit(f"{register}={operand(indices[0])}")
        for size, index in zip(dims[1:], indices[1:], strict=True):
            self.emit(f"{register}={register}*{size}")
            self.emit(f"{register}={register}+{operand(index)}")
        stride = sum(math.prod(dims[k + 1:]) for k in range(len(dims)))  # what the 1-based indices add up to
        self.emit(f"{register}={register}+{{PB:{key}:{-stride}}}")
        reads = _reads(indices)
        if reads is not None:  # kept while none of the registers it reads, nor its own, is written
            self.point_index = (key, tuple(indices))
            self.index_reads[self.point_index] = reads | {int(_WRITES_REGISTER.match(register)[1])}  # type: ignore[index]
        return bare

    def number_element(self, expr: n.Index, write: bool = False) -> str | None:
        """R[R[n]] for an element of an array of numbers kept in registers at an index only known at run time, the
        index worked out in a register first; R[base+k] at a fixed index of an array the programs change (`write`:
        the element an assignment sets). None for anything else (a fixed index of an array no program changes is
        read as a constant)."""
        return self.array_element(expr, write, "num")

    def flag_element(self, expr: n.Expr, write: bool = False) -> str | None:
        """F[R[n]] / F[base+k] for an element of an array of bools kept in flags, as number_element() for numbers
        (ROBOGUIDE: F[R[n]] loads, is read and set)."""
        return self.array_element(expr, write, "bool") if isinstance(expr, n.Index) else None

    def array_element(self, expr: n.Index, write: bool, kind: str) -> str | None:
        """The element of an array of numbers (kind num, in registers) or bools (bool, in flags), number_element()."""
        if not isinstance(expr.base, n.Name):
            return None
        decl = self.c.symbols.get(expr.base.name)
        if decl is None or decl.type_name.lower() != kind or len(decl.dims) != len(expr.indices):
            return None
        prefix, mark, store = ("R", "RB", self.c.number_arrays) if kind in ("num", "iodev") else ("F", "FB",
                                                                                            self.c.flag_arrays)
        changed = self.c.computer.written.where((decl.name.upper(),), kind)
        try:
            fixed = [self.c.evaluator.constant_number(i) for i in expr.indices]
            if not changed and not write:
                return None
        except Unresolvable:
            fixed = None
        key = decl.name.upper()
        if key not in store:
            store[key] = self._number_array(decl, expr, changed)
            if decl.storage == "PERS" and decl.scope is None:
                self.c.shared_arrays.add(key)
        if self.current is not None:
            self.c.array_statements.setdefault(key, set()).update(id(s) for s in walk_statements((self.current,)))
        dims = store[key][1]
        if fixed is not None:  # R[base+k]: the element's own register
            if any(not float(i).is_integer() or not 1 <= i <= size for i, size in zip(fixed, dims, strict=True)):
                raise Untranslatable(f"{format_expr(expr)}: index out of the array ({', '.join(map(str, dims))})",
                                     Blocker.VALUE)  # fmt: skip
            flat = 0
            for i, size in zip(fixed, dims, strict=True):
                flat = flat * size + int(i) - 1
            return f"{prefix}[{{{mark}:{key}:{flat}}}]"
        indices = tuple(self._index(i) for i in expr.indices)
        if (key, indices) in self.number_index:  # worked out already: its register is this statement's too
            self.number_slots.add(self.number_index[(key, indices)])
            return prefix + self.number_index[(key, indices)][1:]
        slot = 1  # the first index register this statement does not read yet: two elements, two registers
        while True:
            name = "NumberIndex" if slot == 1 else f"NumberIndex{slot}"
            register = self.c.written_register(name, key=f"CROSSARM.{name.upper()}")
            bare = register.split(":")[0] + "]" if ":" in register else register
            if f"R[{bare}]" not in self.number_slots:
                break
            slot += 1
        self.number_slots.add(f"R[{bare}]")
        self.number_index = {k: v for k, v in self.number_index.items() if v != f"R[{bare}]"}
        self.emit(f"{register}={operand(indices[0])}")
        for size, index in zip(dims[1:], indices[1:], strict=True):
            self.emit(f"{register}={register}*{size}")
            self.emit(f"{register}={register}+{operand(index)}")
        stride = sum(math.prod(dims[k + 1:]) for k in range(len(dims)))
        self.emit(f"{register}={register}+{{{mark}:{key}:{-stride}}}")
        reads = _reads(indices)
        if reads is not None:
            self.number_index[(key, indices)] = f"R[{bare}]"
            self.index_reads[(key, indices)] = reads | {int(_WRITES_REGISTER.match(register)[1])}  # type: ignore[index]
        return f"{prefix}[{bare}]"

    def _index(self, expr: n.Expr) -> str:
        """An index as one operand: worked out in scratch registers first when it is a calculation (`i+1`), in
        slots of their own, past those a calculation of the statement may hold."""
        try:
            return self.numeric(expr)
        except Untranslatable:
            if self.stepless or not isinstance(expr, n.BinaryOp | n.UnaryOp):
                raise
            return self.single(expr, 8, bare=True)

    def _number_array(self, decl: n.DataDecl, expr: n.Expr, changed: str | None) -> tuple[str, tuple[int, ...], tuple[float, ...]]:
        """(name, dims, values) of an array of numbers kept in registers, which SETUP_FRAMES sets to `values`: those
        it holds, or, for one the programs change, those it is declared with (zeros without), as a register is set
        once on the controller where RAPID sets a VAR again when the program starts."""
        bools = decl.type_name.lower() == "bool"
        what, block = ("bools", "flags") if bools else ("numbers", "registers")
        if not changed:
            self._fixed_array(decl, expr, what, Blocker.VALUE)
        elif self.c.symbols.is_local(decl.name):
            raise Untranslatable(f"{decl.name}: an array of {what} of a routine, changed by it: RAPID sets it again at"
                                 f" each call, a block of {block} keeps the last values", Blocker.VALUE)  # fmt: skip
        try:
            dims = tuple(int(self.c.evaluator.constant_number(d)) for d in decl.dims)
            if not changed:
                flat = self.c.evaluator.value(n.Name(expr.span, decl.name))
            elif decl.init is not None:
                flat = self.c.evaluator.value(decl.init)
            else:
                flat = False if bools else 0.0
                for size in reversed(dims):
                    flat = [flat] * size
            for _ in dims[1:]:
                flat = [v for row in flat for v in row]
            if bools and not all(isinstance(v, bool) for v in flat):
                raise TypeError("not TRUE or FALSE")
            values = tuple(float(v) for v in flat)
        except (Unresolvable, TypeError, ValueError) as exc:
            raise Untranslatable(f"{decl.name}: not an array of fixed {what} ({exc})", Blocker.VALUE) from exc
        for value in values:  # written in R[n] by SETUP_FRAMES
            register_value(value)
        if changed:
            first = "saved in the backup" if decl.storage == "PERS" else "declared, once: RAPID sets a VAR again when the program starts from main"
            self.c.warn_once(f"changed-array:{decl.name.upper()}", self.name, expr.span.line,
                             f"{decl.name}, an array the programs change ({changed}), is kept in a block of {block}"
                             f" read and written as {'F' if bools else 'R'}[R[n]]; SETUP_FRAMES sets the values {first}",
                             Blocker.VALUE)  # fmt: skip
        return decl.name, dims, values

    def _fixed_array(self, decl: n.DataDecl, expr: n.Expr, what: str, category: str) -> None:
        """An array SETUP_FRAMES can keep in registers: a CONST, or a PERS no program changes (a table the operator
        sets, as the registers are on FANUC: kept at the values saved in the backup, and said so)."""
        where = self.c.computer.written.where((decl.name.upper(),), decl.type_name.lower())
        # A VAR no program changes holds its declared values: set again when the program starts, to the same.
        if where is not None or decl.storage == "VAR" and decl.init is None:
            why = f"changed by the programs ({where})" if where else "a VAR without values, set when the program runs"
            raise Untranslatable(f"{format_expr(expr)}: an array of {what} indexed at run time is kept in registers when"
                                 f" no program changes it; {decl.name} is {why}", category)  # fmt: skip
        if decl.storage == "PERS":
            self.c.warn_once(f"pers-array:{decl.name.upper()}", self.name, expr.span.line,
                             f"{decl.name}: PERS array kept in registers with the values saved in the backup, which"
                             " SETUP_FRAMES sets; on the robot they are changed there, as the PERS was", Blocker.SAVED_FRAME)  # fmt: skip

    def _point_array(self, decl: n.DataDecl, line: int) -> str:
        """The array's values, each element converted like a point (CONFIG included), once per conversion."""
        key = decl.name.upper()
        if key in self.c.arrays:
            return key
        try:
            dims = tuple(int(self.c.evaluator.constant_number(d)) for d in decl.dims)
        except Unresolvable as exc:
            raise Untranslatable(f"{decl.name}: array size not fixed ({exc})", Blocker.RUNTIME_POSITION) from exc
        try:
            data = self.c.evaluator.value(n.Name(n.Span(line, 0), decl.name))
        except Unresolvable as exc:
            raise Untranslatable(f"{decl.name}: {exc}", Blocker.RUNTIME_POSITION) from exc
        values = []
        for flat in range(math.prod(dims)):
            position, rest = [], flat
            for size in reversed(dims):
                position.insert(0, rest % size + 1)
                rest //= size
            try:
                element = data
                for i in position:
                    element = element[i - 1]
                (x, y, z), q, conf, _extax = element
                q = unit_quaternion(q, f"{decl.name}{{{','.join(map(str, position))}}}")
                value = RobTarget(Pose((x, y, z), q), tuple(int(c) for c in conf))  # type: ignore[arg-type]
            except Unresolvable as exc:
                raise Untranslatable(str(exc), Blocker.RUNTIME_POSITION) from exc
            except (TypeError, ValueError, IndexError) as exc:
                raise Untranslatable(f"{decl.name}{{{','.join(map(str, position))}}}: malformed robtarget",
                                     Blocker.RUNTIME_POSITION) from exc  # fmt: skip
            (x, y, z), (w, p, r) = value.pose.pos, value.pose.wpr()
            values.append(CartesianPosition(x, y, z, w, p, r, self.config_string(value, line)))
        self.c.arrays[key] = (decl.name, dims, tuple(values))
        return key

    def joint_frame(self, kind: str, expr: n.Expr | None, line: int, number: bool = True) -> tuple[int, int | None]:
        """The frame a MoveAbsJ selects. A joint target does not depend on the tool or the work object, so a
        stationary tool or a robot-held work object, which TP has no frame for, does not stop the move: it is
        made with the frame already selected, or tool0 / wobj0. The controller still wants the point's frame
        numbers to be the selected ones, joint point or not (INTP-253 on ROBOGUIDE).

        `number`: give the stationary frame its number all the same, as the conversions that left this move
        TODO did, so that the automatic numbers of the other frames stay what they were."""
        if expr is None or not self._stationary(kind, expr):
            return self.c.selection(kind, self.c.frame_number(kind, expr, self.name, line))
        if number:
            try:
                self.c.frame_number(kind, expr, self.name, line)
            except Untranslatable:
                pass  # numbered, then refused: what is wanted here
        active = self.active_uf if kind == "UF" else self.active_ut
        what = "work object" if kind == "UF" else "tool"
        self.c.warn_once(
            f"absj-{kind}:{self.name}:{format_expr(expr).upper()}", self.name, line,
            f"MoveAbsJ with the {'robot-held' if kind == 'UF' else 'stationary'} {what} {format_expr(expr)}: a joint"
            f" target does not depend on the {what}, so the move is made with the {what} selected before it, else"
            f" {'wobj0' if kind == 'UF' else 'tool0'}; the {what} itself (a remote TCP on FANUC) is not converted",
            Blocker.STATIONARY,
        )  # fmt: skip
        if active is not None:
            return active
        neutral = n.Name(expr.span, "wobj0" if kind == "UF" else "tool0")
        return self.c.selection(kind, self.c.frame_number(kind, neutral, self.name, line))

    def _stationary(self, kind: str, expr: n.Expr) -> bool:
        """A stationary tool / robot-held work object, told without numbering it: FANUC never selects it."""
        if not isinstance(expr, n.Name):
            return False
        try:
            frame = self.c.declared_frame(kind, expr)
        except Unresolvable:
            return False
        return frame.robhold if kind == "UF" else not frame.robhold

    def point(self, expr: n.Expr, value: RobTarget | JointTarget, uf_selected: tuple[int, int | None],
              ut_selected: tuple[int, int | None], line: int) -> str:  # fmt: skip
        source = format_expr(expr)
        # The value too: a point the routine computes can hold another value further on.
        key = (source.upper(), uf_selected, ut_selected, value)
        uf, ut = uf_selected[0], ut_selected[0]
        if key in self._point_keys:
            return f"P[{self._point_keys[key]}]"
        number = len(self._point_keys) + 1
        self._point_keys[key] = number
        if isinstance(value, JointTarget):
            if self.c.config.joint_mapping:
                joints = fanuc_joints(value.joints, self.c.config.tool_pin)
                half = " +180" if self.c.config.tool_pin == TOOL_PIN_DEFAULT else ""
                message = (
                    "joint targets (MoveAbsJ) converted with the measured axis conventions (J3 absolute, "
                    f"J4/J5/J6 reversed{half and ', J6' + half}): same posture, but the TCP lands elsewhere on "
                    "another robot model, check joint limits and clearances"
                )
            else:
                joints = tuple(value.joints[:6])
                message = "joint_mapping is off: joint targets (MoveAbsJ) copied axis by axis, re-teach them"
            tp_value: CartesianPosition | JointPosition = JointPosition(joints)
            self.c.warn_once("joint-targets", self.name, line, message, Blocker.AXIS_CONVENTION)
        else:
            (x, y, z), (w, p, r) = value.pose.pos, value.pose.wpr()
            faceplate = self.written_faceplate((x, y, z, w, p, r), uf_selected[0], ut_selected[0])
            tp_value = CartesianPosition(x, y, z, w, p, r, self.config_string(value, line, faceplate))
        self.positions.append(Position(number, uf, ut, tp_value))
        self.points.append(PointInfo(number, source, line, uf, ut, tp_value, uf_selected[1], ut_selected[1]))
        return f"P[{number}]"

    def written_faceplate(self, point: tuple[float, ...], uf: int, ut: int) -> Pose | None:
        """The faceplate in the world frame as the controller will work it out: UFRAME * P * inverse(UTOOL),
        from the values as written (3 decimals). None when a frame is not known at conversion time."""

        def pose(values: tuple[float, ...]) -> Pose:
            x, y, z, w, p, r = (round(v, 3) for v in values)
            return Pose((x, y, z), matrix_to_quat(wpr_to_matrix(w, p, r)))

        frames = []
        for kind, number in (("UF", uf), ("UT", ut)):
            info = self.c.frames.get((kind, number))
            if kind == "UF" and number == 0:
                frames.append(Pose((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)))
            elif info is None or info.frame is None:
                return None
            else:
                frames.append(pose((*info.frame.pose.pos, *info.frame.pose.wpr())))
        uframe, utool = frames
        return uframe.compose(pose(point)).compose(utool.inverse())

    def config_string(self, target: RobTarget, line: int, faceplate: Pose | None = None) -> str:
        cfg = self.c.config
        if not cfg.config_mapping:
            self.c.warn_once(
                "config", self.name, line,
                f"config_mapping is off: every point uses CONFIG '{cfg.default_config}', check the arm posture",
                Blocker.AXIS_CONVENTION,
            )  # fmt: skip
            return cfg.default_config
        try:
            boundary = faceplate is not None and j6_on_turn_boundary(faceplate, target.conf)
            text = fanuc_config(target.conf, cfg.tool_pin, boundary)
        except UnsupportedConfdata as exc:
            self.c.warn_once(f"confdata:{line}", self.name, line, f"{exc}: CONFIG '{cfg.default_config}' used",
                             Blocker.AXIS_CONVENTION)
            return cfg.default_config
        self.c.warn_once(
            "config-mapped", self.name, line,
            "CONFIG derived from ABB confdata (measured conventions, see docs). A different robot model can "
            "need a different posture to reach the same point, and the J6 turn number assumes the tool's pin is "
            f"in the {cfg.tool_pin} hole of the faceplate (tool_pin): check reachability in ROBOGUIDE",
            Blocker.AXIS_CONVENTION,
        )  # fmt: skip
        return text

    def speed(self, expr: n.Expr, motion: str) -> tuple[str, float, float]:
        """The TP speed, the RAPID TCP speed (mm/s) and the TP one as a number (% for J, mm/s otherwise)."""
        speed = self.c.evaluator.speed(expr)
        cfg = self.c.config
        if motion == "J":
            value = max(1, min(100, round_half_up(speed.v_tcp / cfg.joint_speed_ref_mm_s * 100)))
            text = f"{value}%"
        else:
            value = max(1, round_half_up(speed.v_tcp))
            text = f"{value}mm/sec"
        self.c.result.speeds[(speed.name, motion)] = text
        return text, speed.v_tcp, value

    def given_motion(self, m: n.Move, motion: str) -> tuple[str | None, str | None]:
        """The speed and the termination of a move that takes them from the routine's speeddata and zonedata
        parameters, in the registers they were copied to: `R[k]mm/sec`, `R[k]%`, `CNT R[m]` with the CNT the
        caller worked out. None for what the move does not take from them."""
        layout: Signature = self.args  # type: ignore[assignment]
        speed_slot = layout.given_speed(m.speed, motion)
        speed = f"{_bare(self.given[speed_slot.key])}{'%' if motion == 'J' else 'mm/sec'}" if speed_slot else None
        zone_given = isinstance(m.zone, n.Name) and layout.kind(m.zone.name) == "zonedata"
        if zone_given and m.zone.name.upper() in layout.fine_zones:  # type: ignore[union-attr]
            return speed, "FINE"  # every call passes fine
        if not zone_given and (speed_slot is None or self.c.evaluator.zone(m.zone).fine):
            return speed, ("FINE" if speed_slot is not None else None)
        corner = layout.given_corner(motion, m.zone, m.speed, self.next_speed)
        if corner is None:  # a move the signature did not see: an ERROR handler's
            raise Untranslatable("a move at a speed or zone given as argument, out of the routine's body", Blocker.CALL_ARGS)
        self.both_ways = self.given[corner.key] if corner.fine else None
        return speed, f"CNT {_bare(self.given[corner.key])}"

    def termination(self, expr: n.Expr, speed_expr: n.Expr, motion: str, rapid_speed: float, fanuc_speed: float,
                    next_speed: n.Expr | None = None) -> str:  # fmt: skip
        """FINE or the CNT for the zone. Into a faster move, the FANUC rounds a corner more than at the
        zoned move's own speed (measured by tools/make_path_probe.py): the CNT is then matched at the
        next move's speed, which rounds no more than the ABB."""
        zone = self.c.evaluator.zone(expr)
        cfg = self.c.config
        use, then = ZoneUse("FINE"), ""
        if not zone.fine and cfg.zone_mapping == "linear":
            use = ZoneUse(f"CNT{max(0, min(100, round_half_up(zone.radius_mm * cfg.cnt_per_mm)))}")
        elif not zone.fine:
            try:
                following = self.c.evaluator.speed(next_speed) if next_speed is not None else None
            except Unresolvable:
                following = None  # a speed only known when the program runs: this move's own
            if following is not None and following.v_tcp > rapid_speed > 0:
                then = following.name
                fanuc_speed *= following.v_tcp / rapid_speed
            found = corner(cfg.motion_profile, motion, zone.radius_mm, rapid_speed, fanuc_speed)
            use = ZoneUse(f"CNT{found.cnt}", found.abb_cut, found.fanuc_cut, found.capped)
        speed_name = self.c.evaluator.speed(speed_expr).name
        self.c.result.zones[(zone.name, speed_name, motion, then)] = use
        return use.tp

    # -- I/O, calls, waits ------------------------------------------------------

    def output(self, expr: n.Expr, stmt: n.Stmt) -> str:
        ref = self.c.signal(expr, self.name, stmt.span.line)
        if ref is None or not ref.startswith("DO"):
            raise Untranslatable(f"'{format_expr(expr)}' is not a known digital output", Blocker.SIGNAL)
        return ref

    def call(self, call: n.ProcCall) -> None:
        name = call.name.upper()
        positional = [a.value for a in call.args if a.name is None]
        options = [a for a in call.args if a.name is not None]

        if name == "STOP":
            if call.args:
                options_text = " ".join(f"\\{a.name}" for a in call.args if a.name)
                self.c.warn_once(f"stop:{self.name}", self.name, call.span.line,
                                 f"Stop options ({options_text}) have no PAUSE equivalent and are ignored",
                                 Blocker.OPTIONS_IGNORED)  # fmt: skip
            self.emit("PAUSE")
        elif name == "SETDO" and len(positional) == 2 and not options:
            self.emit(f"{self.output(positional[0], call)}={self.on_off(positional[1])}")
        elif name in ("WAITDI", "WAITDO") and len(positional) == 2:
            limit = self.max_time(call, options)
            ref = self.c.signal(positional[0], self.name, call.span.line)
            if ref is None:
                raise Untranslatable(f"'{format_expr(positional[0])}' is not a known signal", Blocker.SIGNAL)
            state = self.on_off(positional[1])
            other = "OFF" if state == "ON" else "ON"
            self.wait(f"WAIT {ref}={state}", f"{ref}={state}", f"{ref}={other}", limit)
        elif name == "WAITUNTIL" and len(positional) == 1:
            limit = self.max_time(call, options)
            test = self.simplify(positional[0])
            if isinstance(test, n.Bool):
                if not test.value:
                    raise Untranslatable("WaitUntil on a condition that is never true", Blocker.CONDITION)
                return  # always true: nothing to wait for
            self.stepless = True  # a calculation made once before the wait would not follow the data
            try:
                positive = self.condition(test)
                negative = self.condition(test, negate=True) if limit else ""
            finally:
                self.stepless = False
            self.wait(f"WAIT ({positive})", positive, negative, limit)
        elif name == "TPERASE" and not call.args:
            pass  # the FANUC pendant has no user-screen clear: nothing to emit
        elif name == "TPWRITE" and len(positional) == 1:
            self.message(call, positional[0], options)
        elif name == "SETGO" and len(positional) == 2 and not options:
            target, value = self.group(positional[0], "GO", call.span.line), operand(self.numeric(positional[1]))
            if value.startswith("GI["):  # GO[4]=GI[3] does not load (ASBN-092): through a register
                copy = self.c.written_register("GroupCopy", key="CROSSARM.GROUPCOPY")
                self.emit(f"{copy}={value}")
                value = copy
            self.emit(f"{target}={value}")
        elif name == "PULSEDO" and len(positional) == 1:
            self.pulse(call, positional[0], options)
        elif name == "GRIPLOAD" and len(positional) == 1 and not options:
            self.grip_load(call, positional[0])
        elif name == "INVERTDO" and len(positional) == 1 and not options:
            signal = self.output(positional[0], call)
            self.emit(f"{signal}=(!{signal})")
        elif name == "SETAO" and len(positional) == 2 and not options:
            self.analog(call, positional[0], positional[1])
        elif name in _SET_ON_ARRIVAL:
            self.move_and_set(call, name, positional, options)
        elif name == "SEARCHL":
            self.search(call, positional, options)
        elif name == "WAITROB" and not positional and len(options) == 1 and options[0].name.upper() in ("INPOS", "ZEROSPEED"):
            self.wait_robot(call, options[0].name)
        elif name in ("CLKRESET", "CLKSTART", "CLKSTOP") and len(positional) == 1 and not options:
            self.emit(f"{self.clock(positional[0])}={name[3:]}")
        elif name in _CHANGING and not options and len(positional) == (2 if name == "ADD" else 1):
            self.assign(_as_assignment(call, name, positional))
        elif name in _MOTION_SETTINGS:
            self.motion_setting(call, name, positional, options)
        elif name in ("ISIGNALDI", "ISIGNALDO", "IPERS"):
            self.arm(call, name, positional, options)
        elif name in ("ISLEEP", "IDELETE", "IWATCH") and len(positional) == 1 and not options:
            self.monitor(call, name, positional[0])
        elif name in _INTERRUPTS:
            why = _INTERRUPT_GAPS.get(name, "a condition monitor watches digital signals and registers only")
            raise Untranslatable(f"{call.name}: {why}", Blocker.INTERRUPT)
        elif name in self.c.externals:
            self.provided_call(call, self.c.externals[name])
        elif name == "CALLBYVAR" and name not in self.c.procs:
            self.late_call(call)  # convert.late_calls
        elif name == "SETSYSDATA" and name not in self.c.procs:
            self.set_sys_data(call)  # convert.system_data
        elif self.c.config.karel and name in FILE_INSTRUCTIONS and name not in self.c.procs:
            self.file_statement(call, name)  # convert.karel_files
        elif name in self.c.move_routines:
            self.routine_move(call, self.c.move_routines[name])
        elif isinstance(self.c.signatures.get(name), Signature) and name in self.c.program_names:
            self.call_with_args(call, self.c.signatures[name])  # type: ignore[arg-type]
        elif isinstance(self.c.signatures.get(name), str) and (through := self.c.routine_use.of(call)) is not None:
            raise Untranslatable(through, Blocker.NO_TP_EQUIVALENT)  # its files or sockets, before its parameters
        elif isinstance(self.c.signatures.get(name), str) and (frame := self.c.routine_use.byte_buffer(call, self.routine.body)):
            raise Untranslatable(frame, Blocker.NO_TP_EQUIVALENT)  # a byte array it is given is a socket or file frame
        elif isinstance(self.c.signatures.get(name), str):
            raise Untranslatable(f"{call.name} is not converted: {self.c.signatures[name]}", Blocker.CALL_ARGS)
        elif name not in self.c.procs and name not in self.c.computer.functions and name not in RAPID_INSTRUCTIONS:
            raise self.not_in_backup(call.name, "routine")
        elif call.args:
            raise Untranslatable(f"call to {call.name} with arguments has no mapping", Blocker.CALL_ARGS)
        elif name in self.c.program_names:
            self.emit(f"CALL {self.c.program_names[name]}")
        else:
            raise Untranslatable(f"'{call.name}' is not a routine of the converted modules (system instruction?)", Blocker.CALL_ARGS)

    def move_and_set(self, call: n.ProcCall, name: str, positional: list[n.Expr], options: list[n.Arg]) -> None:
        """MoveLDO / MoveJDO / MoveCDO to a fine point: the move, then the output. RAPID sets it at the point
        when the robot stops there; the line after a FINE move runs once the robot stands on the point
        (ROBOGUIDE: DO[1] ON with the TCP 0.000 mm from it). Through a zone RAPID sets it in the middle of
        the corner path, which no TP line does: TODO."""
        count = 7 if name == "MOVECDO" else 6
        if len(positional) != count:
            raise Untranslatable(f"{call.name}: {len(positional)} arguments, {count} expected", Blocker.MOTION)
        *move_args, signal, value = positional
        zone = move_args[-2]
        if not self.fine(zone):
            raise Untranslatable(f"{call.name} through a zone ({format_expr(zone)}): RAPID sets the output in the middle"
                                 " of the corner path, TP at a time or distance before the point", Blocker.MOTION)  # fmt: skip
        wobj = next((a.value for a in options if a.name.upper() == "WOBJ"), None)
        others = tuple(a for a in options if a.name.upper() != "WOBJ")
        kind = {"MOVELDO": n.MoveKind.L, "MOVEJDO": n.MoveKind.J, "MOVECDO": n.MoveKind.C}[name]
        via = move_args[0] if kind is n.MoveKind.C else None
        to, speed, zone, tool = move_args[-4:]
        self.move(n.Move(call.span, kind, to, speed, zone, tool, via, wobj, others))
        self.emit(f"{self.output(signal, call)}={self.on_off(value)}")

    def search(self, call: n.ProcCall, positional: list[n.Expr], options: list[n.Arg]) -> None:
        """SearchL as a skip: `SKIP CONDITION DI[n]=ON`, then the move to the point with `Skip,LBL[m],PR[k]=LPOS`,
        PR[k] the search point's register (a point known at run time). Measured (ROBOGUIDE): the move stops
        where the input switches and PR[k] is the TCP there; never switched, the robot reaches the point and the
        program jumps to LBL[m]. The skip condition is a level: RAPID's search for a change (\\PosFlank, the
        default, \\NegFlank) checks the input is not at that level at the start first. \\Sup and no stop
        option: RAPID goes on to the point, the FANUC once stopped moves on to it. Where RAPID stops with an
        error (nothing found, the input already at the level), a MESSAGE and PAUSE; resumed, the search again."""
        line = call.span.line
        switches = {a.name.upper() for a in options if a.value is None}
        if "FLANKS" in switches:
            raise Untranslatable("SearchL \\Flanks: TP's skip condition waits for one level of the input, not for"
                                 " either change", Blocker.CALIBRATION)  # fmt: skip
        stops, levels = switches & _SEARCH_STOPS, switches & set(_SEARCH_LEVELS)
        flying = not stops
        if len(stops) + ("SUP" in switches) > 1 or len(levels) > 1:
            raise Untranslatable("SearchL with options RAPID does not take together", Blocker.CALIBRATION)
        if len(positional) != 5:
            raise Untranslatable(f"SearchL: {len(positional)} arguments, 5 expected", Blocker.CALIBRATION)
        if any(h.kind == "ERROR_HANDLER" for h in self.routine.handlers):
            raise Untranslatable("SearchL in a routine with an ERROR handler: RAPID runs it when nothing is found or"
                                 " the input is already on, and handlers are not converted", Blocker.HANDLER)  # fmt: skip
        signal, found, to, speed, tool = positional
        din = self.c.signal(signal, self.name, line)
        if din is None or not din.startswith("DI["):
            raise Untranslatable(f"SearchL on {format_expr(signal)}: TP's skip condition is written on a digital input"
                                 " here", Blocker.CALIBRATION)  # fmt: skip
        key = self.runtime_key(found.name) if isinstance(found, n.Name) else None
        if key is None:
            raise Untranslatable(f"SearchL: the search point {format_expr(found)} is kept in a position register when"
                                 " it is a robtarget data of its own (not an array element, not a CONST)",
                                 Blocker.CALIBRATION)  # fmt: skip
        _, _, fanuc_speed = self.speed(speed, "L")
        if fanuc_speed > SKIP_SPEED_MAX:
            raise Untranslatable(f"SearchL at {fanuc_speed:g} mm/s: the FANUC skip records the position up to"
                                 f" {SKIP_SPEED_MAX} mm/s, the controller slowing a faster move down to that (measured):"
                                 " searching slower changes what is measured and the cycle time", Blocker.CALIBRATION)  # fmt: skip
        level, edge = _SEARCH_LEVELS[next(iter(levels), "POSFLANK")]
        register = self.c.point_register(key)
        wobj = next((a.value for a in options if a.name.upper() == "WOBJ"), None)
        others = tuple(a for a in options if a.name.upper() not in {"WOBJ", "SUP", *_SEARCH_STOPS, *_SEARCH_LEVELS})
        move = n.Move(call.span, n.MoveKind.L, to, speed, n.Name(call.span, "fine"), tool, None, wobj, others)
        retry, missed, done = self.label(), self.label(), self.label()
        early = self.label() if edge else None
        self.emit(f"LBL[{retry}]")
        if early is not None:
            self.emit(f"IF ({din}={level}),JMP LBL[{early}]")
        self.emit(f"SKIP CONDITION {din}={level}")
        self.move(move)
        motion = self.lines[-1]
        if not isinstance(motion, Motion) or motion.options:
            raise Untranslatable(f"SearchL to {format_expr(to)}: a skip on a move with an offset is not written",
                                 Blocker.CALIBRATION)  # fmt: skip
        self.lines[-1] = dataclasses.replace(motion, options=f"Skip,LBL[{missed}],{register}=LPOS")
        if flying:
            self.move(move)
        self.emit(f"JMP LBL[{done}]")
        for label, why in ((early, f"input {level.lower()}"), (missed, "no hit")):
            if label is not None:
                self.emit(f"LBL[{label}]")
                self.emit(f"MESSAGE[{f'SearchL l.{line}: {why}'[:MESSAGE_MAX]}]")
                self.emit("PAUSE")
                self.emit(f"JMP LBL[{retry}]")
        self.emit(f"LBL[{done}]")
        self.known.pop(f"{found.name.upper()}#UNSET", None)  # type: ignore[union-attr]
        self.known[f"{found.name.upper()}#ROT"] = Unknown(f"is measured on the robot at l.{line}", measured=True)  # type: ignore[union-attr]
        stop = (f"the FANUC stops past where {din} switched and comes back to it ({SKIP_OVERSHOOT}), RAPID stops past"
                f" it and stays: check the stopping distance at {fanuc_speed:g} mm/s, mostly for a search by contact,"
                " where the tool pushes into the part")  # fmt: skip
        if flying:
            stop = ("RAPID goes on to the point without stopping; the FANUC stops where the input switched, then goes"
                    f" on to it ({SKIP_OVERSHOOT} first){' and does not check for a second switch, which RAPID stops on with an error' if 'SUP' in switches else ''}")  # fmt: skip
        errors = "nothing found, the input already at the level at the start" if edge else "nothing found"
        self.warn(call, f"SearchL as a skip ({din}={level}, {found.name} kept in a position register): {stop}. Where RAPID stops"
                        f" with an error ({errors}), the program shows a MESSAGE and pauses; resumed, it searches"
                        " again", Blocker.SEARCH)  # fmt: skip

    def fine(self, zone: n.Expr) -> bool:
        """Whether a zone stops the robot on the point: fine, or a zonedata with finep TRUE."""
        if isinstance(zone, n.Name) and zone.name.upper() == "FINE":
            return True
        try:
            value = self.c.evaluator.value(zone)
        except Unresolvable:
            return False
        return isinstance(value, list) and bool(value) and value[0] is True

    def wait_robot(self, call: n.ProcCall, option: str) -> None:
        """WaitRob \\InPos or \\ZeroSpeed after a FINE move: TP runs the line after a FINE move once the robot
        stands on the point, so there is nothing to wait for. After a move through a zone, or when the program
        may arrive from elsewhere (a label, a call), TP has no wait for the robot to stop: TODO."""
        for line in reversed(self.lines):
            if isinstance(line, Motion):
                if line.termination == "FINE":
                    self.emit(f"!WaitRob {option}: FINE before")
                    return
                break
            if line.text.startswith(("LBL[", "CALL ", "ENDIF", "ENDFOR", "ELSE")):
                break
        raise Untranslatable(f"WaitRob \\{option}: TP has no wait for the robot to stop; the move before it must be"
                             " FINE", Blocker.MOTION)  # fmt: skip

    # -- interrupts: condition monitors ----------------------------------------------

    def _interrupt(self, name: str, what: str) -> Interrupt:
        """The interrupt an instruction names, if its TRAP is written; else why it stays TODO."""
        interrupt = self.c.interrupts.get(name.upper())
        if interrupt is None or not interrupt.program:
            why = interrupt.problem if interrupt is not None and interrupt.problem else "its TRAP is not converted"
            raise Untranslatable(f"{what}: {why}", Blocker.INTERRUPT)
        return interrupt

    def connect(self, stmt: n.Unsupported) -> None:
        """CONNECT: nothing on FANUC, where the condition program names the TRAP it calls."""
        pair = connected(stmt)
        if pair is None:
            raise Untranslatable(stmt.reason, Blocker.INTERRUPT)
        self._interrupt(pair[0], "CONNECT")

    def arm(self, call: n.ProcCall, name: str, positional: list[n.Expr], options: list[n.Arg]) -> None:
        """ISignalDI / ISignalDO / IPers: the condition its program watches, then `MONITOR` to arm it."""
        armed = arming(call)
        if armed is None or len(positional) != (2 if name == "IPERS" else 3):
            raise Untranslatable(f"{call.name} with these arguments is not converted", Blocker.INTERRUPT)
        interrupt = self._interrupt(armed[0], call.name)
        other = next((a.name for a in options if (a.name or "").upper() not in SINGLE_OPTIONS), None)
        if other:
            raise Untranslatable(f"{call.name}\\{other} is not converted", Blocker.INTERRUPT)
        before: list[str] = []
        if name == "IPERS":
            watched = operand(self.numeric(positional[0]))
            if not watched.startswith("R["):
                raise Untranslatable(f"IPers on {format_expr(positional[0])}: a condition monitor compares registers", Blocker.INTERRUPT)
            seen = self.c.pers_copy(interrupt)
            conditions, before = [f"{watched}<>{seen}"], [f"{seen}={watched}"]
            self.c.watched[armed[0].upper()] = watched
        else:
            kind = name[-2:]
            ref = self.c.signal(positional[0], self.name, call.span.line)
            if ref is None or not ref.startswith(kind):
                raise Untranslatable(f"'{format_expr(positional[0])}' is not a known digital "
                                     f"{'input' if kind == 'DI' else 'output'}", Blocker.SIGNAL)  # fmt: skip
            trigger = positional[1]
            value = "2" if isinstance(trigger, n.Name) and trigger.name.upper() == "EDGE" else self.numeric(trigger)
            edges = {"1": ["ON+"], "0": ["OFF-"], "2": ["ON+", "OFF-"]}.get(value)
            if edges is None:
                raise Untranslatable(f"{call.name} on a value only known at run time", Blocker.INTERRUPT)
            conditions = [f"{ref}={edge}" for edge in edges]
        armed_on = self.c.conditions.setdefault(armed[0].upper(), conditions)
        if armed_on != conditions:
            raise Untranslatable(f"{call.name}: interrupt {interrupt.name} is armed elsewhere on"
                                 f" {', '.join(armed_on)}, and its condition program holds one", Blocker.INTERRUPT)  # fmt: skip
        for text in before:
            self.emit(text)
        self.emit(f"MONITOR {interrupt.program}")

    def monitor(self, call: n.ProcCall, name: str, target: n.Expr) -> None:
        """ISleep / IDelete: `MONITOR END`; IWatch: `MONITOR` again."""
        if not isinstance(target, n.Name):
            raise Untranslatable(f"{call.name} on {format_expr(target)}", Blocker.INTERRUPT)
        interrupt = self._interrupt(target.name, call.name)
        if name != "IWATCH":
            self.emit(f"MONITOR END {interrupt.program}")
            return
        if interrupt.kinds == {"PERS"} and interrupt.watched is not None:
            self.emit(f"{self.c.pers_copy(interrupt)}={operand(self.numeric(interrupt.watched))}")
        self.emit(f"MONITOR {interrupt.program}")

    # -- waits with a time limit, error handlers ------------------------------------

    def max_time(self, call: n.ProcCall, options: list[n.Arg]) -> float | None:
        """The \\MaxTime of a wait, in seconds; None without one. With \\TimeFlag, the bool it sets when the time
        runs out (no error then) goes to wait() in `time_flag`. The FlexPendant visualisation options are dropped with
        a warning (the pendant shows nothing while the robot waits); any other option is not converted."""
        self.time_flag = None
        shown = [a for a in options if (a.name or "").upper() in VISUALIZE_OPTIONS]
        if shown:
            names = " ".join("\\" + (a.name or "") for a in shown)
            self.c.warn_once(f"visualize:{self.name}:{call.span.line}", self.name, call.span.line,
                             f"{call.name} {names}: the FlexPendant message shown"
                             " while waiting is dropped (the wait is converted)", Blocker.OPTIONS_IGNORED)  # fmt: skip
            options = [a for a in options if a not in shown]
        if not options:
            return None
        given = {(a.name or "").upper(): a for a in options}
        if set(given) - {"MAXTIME", "TIMEFLAG"} or "MAXTIME" not in given or given["MAXTIME"].value is None:
            other = next((a.name for a in options if (a.name or "").upper() not in ("MAXTIME", "TIMEFLAG")), "TimeFlag")
            raise Untranslatable(f"{call.name} with {other} is not converted", Blocker.WAIT_TIMEOUT)
        flag = given.get("TIMEFLAG")
        if flag is not None:
            if not (isinstance(flag.value, n.Name) and self.c.symbols.type_of(flag.value.name) == "bool"):
                raise Untranslatable(f"{call.name}: \\TimeFlag must be bool data", Blocker.WAIT_TIMEOUT)
        elif self.on_timeout() is None:
            raise Untranslatable(f"{call.name} with MaxTime: this routine's ERROR handler does not say what to do when"
                                 " the time runs out (the error goes to the caller)", Blocker.WAIT_TIMEOUT)  # fmt: skip
        try:
            limit = self.c.evaluator.constant_number(given["MAXTIME"].value)
        except Unresolvable as exc:
            raise Untranslatable(f"MaxTime must be a constant: {exc}", Blocker.WAIT_TIMEOUT) from exc
        self.time_flag = flag.value.name if flag is not None else None  # type: ignore[union-attr]
        return limit

    def wait(self, text: str, test: str, untested: str, limit: float | None) -> None:
        """A WAIT; with a time limit, a loop timing it, then the ERROR handler's timeout path.

        `test` / `untested`: the condition waited for, and its negation. TP cannot set the time limit of
        WAIT ... TIMEOUT per wait ($WAITTMOUT is write-protected for programs), so the wait polls:

            TIMER[10]=RESET / TIMER[10]=START
            LBL[1] / R[9]=TIMER[10] / IF (DI[1]=OFF AND R[9]<2) THEN / JMP LBL[1] / ENDIF

        Past it, the condition either came true, or time ran out: then the handler's path runs, RETRY
        jumping back to the wait and TRYNEXT past it; the end of the handler ends the routine.
        """
        if limit is None:
            self.emit(text)
            return
        flag, self.time_flag = self.time_flag, None
        path = self.on_timeout() if flag is None else None
        assert flag is not None or isinstance(path, OnTimeout)  # max_time() checked it
        timer, clock = self.c.wait_clock()
        steps = [s for s in path.steps if not isinstance(s, n.Comment)] if path is not None else []
        next_only = flag is not None or (len(steps) == 1 and isinstance(steps[0], n.Unsupported)
                                         and steps[0].kind == "TRYNEXT")  # fmt: skip
        retry = None if next_only else self.label()
        if retry is not None:
            self.emit(f"LBL[{retry}]")
        self.emit(f"{timer}=RESET")
        self.emit(f"{timer}=START")
        poll = self.label()
        self.emit(f"LBL[{poll}]")
        self.emit(f"{clock}={timer}")
        waiting = f"({untested})" if " AND " in untested or " OR " in untested else untested
        self.emit(f"IF ({waiting} AND {clock}<{decimal(fmt_number(limit))}) THEN")
        self.emit(f"JMP LBL[{poll}]")
        self.emit("ENDIF")
        self.emit(f"{timer}=STOP")
        self.timed_waits += 1
        if flag is not None:  # \\TimeFlag: TRUE when the time ran out, and the program goes on
            self.emit(f"{self.c.flag(flag)}=({clock}>={decimal(fmt_number(limit))})")
            return
        if retry is None:
            return  # TRYNEXT: on time or not, go on
        after = self.label()
        self.emit(f"IF ({test}) THEN")
        self.emit(f"JMP LBL[{after}]")
        self.emit("ENDIF")
        self.error_jumps, self.strict = (retry, after), self.strict + 1
        try:
            self.block(path.steps)
        finally:
            self.error_jumps, self.strict = None, self.strict - 1
        self.forget(path.steps, Unknown("may be changed where a wait times out"))  # ran only if the time ran out
        if not leaves(path.steps):
            self.emit("END")  # the end of an error handler returns from the routine
        self.emit(f"LBL[{after}]")

    def on_timeout(self) -> OnTimeout | None:
        if self._on_timeout is False:
            handlers = [h for h in self.routine.handlers if h.kind == "ERROR_HANDLER"]
            stmts = handler_body(handlers[0]) if handlers else None
            self._on_timeout = on_timeout(stmts) if stmts is not None else None
        return self._on_timeout  # type: ignore[return-value]

    def handler(self, handler: n.Unsupported) -> None:
        """An ERROR / UNDO / BACKWARD section: a TODO, unless TP does the same without it."""
        if handler.kind == "BACKWARD_HANDLER":
            self.warn(handler, "BACKWARD handler left out: it only runs when the routine is stepped backwards on the"
                               " pendant", Blocker.HANDLER)  # fmt: skip
            return
        if handler.kind == "ERROR_HANDLER":
            stmts = handler_body(handler)
            if stmts is not None and only_passes_on(stmts):
                self.warn(handler, "ERROR handler only passes errors on (RAISE): nothing to convert here; the caller's"
                                   " handler, if any, is reported with the caller", Blocker.HANDLER)  # fmt: skip
                return
            waits = sum(1 for s in walk_statements(self.routine.body) if _max_time_wait(s))
            path = self.on_timeout()
            if path is not None and path.only and waits and self.timed_waits == waits:
                self.warn(handler, f"ERROR handler written at the timeout of its {waits} wait(s) with MaxTime; on"
                                   " FANUC any other error stops the program with an alarm", Blocker.HANDLER)  # fmt: skip
                return
            if self.timed_waits:
                self.todo(handler, "ERROR handler: its timeout part is written at the waits, the rest is not converted",
                          Blocker.rapid(handler.kind))  # fmt: skip
                return
            why = self.c.routine_use.inside(self.routine.name) if stmts is not None else None
            if why is not None and handles_files_or_sockets(stmts, self.c.symbols.type_of, self.c.routine_use):
                self.todo(handler, f"ERROR handler of a routine using {why}", Blocker.NO_TP_EQUIVALENT)
                return
        self.todo(handler, handler.reason, Blocker.rapid(handler.kind))

    def routine_move(self, call: n.ProcCall, routine: MoveRoutine) -> None:
        """A call to a routine wrapping one move, written as that move when that is allowed."""
        self.c.move_routine_calls[routine.name.upper()] += 1
        if not self.c.converts_calls(routine):
            raise Untranslatable(
                f"{routine.name} makes a {routine.instruction} but also does more ({self.c.also_does(routine)}): "
                f'set "move_routines": {{"{routine.name}": true}} in the mapping file to convert its calls as '
                f"{routine.instruction}", Blocker.MOVE_ROUTINE,
            )  # fmt: skip
        try:
            move = routine.expand(call)
        except CallMismatch as exc:
            raise Untranslatable(f"call to {routine.name} not converted as {routine.instruction}: {exc}",
                                 Blocker.MOVE_ROUTINE) from exc  # fmt: skip
        self.move(move)
        if not routine.pure:
            self.c.warn_once(
                f"move-routine:{self.name}:{routine.name.upper()}", self.name, call.span.line,
                f"{routine.name} converted as {routine.instruction} (mapping file): what it does besides the "
                f"move is not converted ({self.c.also_does(routine)})", Blocker.MOVE_ROUTINE_ASSUMED,
            )  # fmt: skip

    def message(self, call: n.ProcCall, text_expr: n.Expr, options: list[n.Arg]) -> None:
        """TPWrite -> MESSAGE[fixed text]. MESSAGE cannot show a variable: values (\\Num, \\Pos,
        ValToStr...) are left out and listed in a warning, so the operator still sees the text."""
        fixed, dropped = self.split_text(text_expr)
        dropped += [f"\\{a.name}:={format_expr(a.value)}" if a.value else f"\\{a.name}" for a in options]
        text = ascii_text(fixed).replace("[", "(").replace("]", ")").strip()
        if not text:
            if dropped:
                raise Untranslatable("TPWrite shows only a value: MESSAGE cannot display variables", Blocker.MESSAGE_VALUE)
            return
        if dropped and self.c.config.tpwrite_values == "todo":
            raise Untranslatable(f"TPWrite shows a value ({', '.join(dropped)}): MESSAGE cannot display variables", Blocker.MESSAGE_VALUE)
        if dropped:
            self.warn(call, f"TPWrite value not shown (MESSAGE displays fixed text only): {', '.join(dropped)}",
                      Blocker.MESSAGE_VALUE)
        if len(text) > MESSAGE_MAX:
            self.warn(call, f"TPWrite text cut to {MESSAGE_MAX} characters (FANUC MESSAGE limit): '{text}'",
                      Blocker.MESSAGE_CUT)
            text = text[:MESSAGE_MAX].rstrip()
        self.emit(f"MESSAGE[{text}]")

    def split_text(self, expr: n.Expr) -> tuple[str, list[str]]:
        """(fixed text, parts only known at run time) of a string expression."""
        match expr:
            case n.String(value=value):
                return value, []
            case n.BinaryOp(op="+", left=left, right=right):
                left_text, left_dropped = self.split_text(left)
                right_text, right_dropped = self.split_text(right)
                return left_text + right_text, left_dropped + right_dropped
            case n.Name(name=name):
                decl = self.c.symbols.get(name)
                if decl is not None and decl.storage == "CONST" and isinstance(decl.init, n.String):
                    return decl.init.value, []
            case n.Component():  # a record's text no program changes: pdHousing.name
                try:
                    found = self.c.computer.value(expr)
                except Unresolvable:
                    found = None
                if found is not None and isinstance(found.value, str):
                    return found.value, []
        return "", [format_expr(expr)]

    def group(self, expr: n.Expr, kind: str, line: int) -> str:
        """GO[n] / GI[n] for a group signal (kind 'GO' or 'GI', implied by the instruction)."""
        if not isinstance(expr, n.Name):
            raise Untranslatable(f"group signal must be a name: {format_expr(expr)}", Blocker.SIGNAL)
        key = expr.name.upper()
        fixed = self.c.config.group_outputs if kind == "GO" else self.c.config.group_inputs
        table = self.c.gouts if kind == "GO" else self.c.gins
        detail = ""
        if key not in fixed and key in self.c.eio:
            sig = self.c.eio[key]
            if sig.signal_type != kind:
                raise Untranslatable(f"'{expr.name}' is a {sig.signal_type} signal in EIO.cfg, not {kind}", Blocker.SIGNAL)
            detail = f"EIO.cfg: {kind}, device {sig.device or '-'}, map {sig.device_map or '-'}"
        elif key not in fixed and self.c.eio:
            self.c.warn_once(f"signal-eio:{key}", self.name, line, f"'{expr.name}' is not declared in EIO.cfg",
                             Blocker.SIGNAL)
        return f"{kind}[{table.number(expr.name, detail=detail)}]"

    def pulse(self, call: n.ProcCall, signal: n.Expr, options: list[n.Arg]) -> None:
        """PulseDO -> DO[n]=PULSE,0.2sec. FANUC takes tenths of a second, 0.1 to 25.5 (ROBOGUIDE rounds
        0.25 to 0.3, drops a length below 0.05 for its default, refuses 25.6): the length is rounded
        there, and said so when it moves. PULSE sets the output ON whatever it was, as PulseDO \\High."""
        length = PULSE_DEFAULT_S
        for option in options:
            key = (option.name or "").upper()
            if key == "HIGH":
                continue
            if key != "PLENGTH" or option.value is None:
                raise Untranslatable(f"PulseDO with \\{option.name} is not converted", Blocker.OPTIONS_IGNORED)
            try:
                length = self.c.evaluator.constant_number(option.value)
            except Unresolvable as exc:
                raise Untranslatable(f"PulseDO length only known at run time ({exc})", Blocker.VALUE) from exc
        if length > PULSE_MAX_S:
            raise Untranslatable(f"PulseDO of {fmt_number(length)} s: a FANUC PULSE lasts {PULSE_MAX_S} s at most",
                                 Blocker.SIGNAL)  # fmt: skip
        tenths = max(1, math.floor(length * 10 + 0.5))
        if abs(tenths / 10 - length) > 1e-9:
            self.warn(call, f"PulseDO of {fmt_number(length)} s written {tenths / 10:.1f} s: FANUC pulses last whole"
                            " tenths of a second", Blocker.IO_ROUNDED)  # fmt: skip
        self.emit(f"{self.output(signal, call)}=PULSE,{tenths / 10:.1f}sec")

    def grip_load(self, call: n.ProcCall, load: n.Expr) -> None:
        """GripLoad -> PAYLOAD[n]: the schedule of the tool with the part (load0: the tool alone).

        A FANUC schedule is all the flange carries, so the tool matters: the one the moves after it use
        (RAPID adds the load to whichever tool moves), else the one selected, else the task's only tool."""
        released = isinstance(load, n.Name) and load.name.upper() == "LOAD0"
        part = None
        if not released:
            try:
                mass, cog, aom, ix, iy, iz = self.c.computer.value(load).value
                part = Load(float(mass), tuple(cog), tuple(aom), (ix, iy, iz))  # type: ignore[arg-type]
            except Unresolvable as exc:
                raise Untranslatable(f"GripLoad {format_expr(load)}: load only known at run time ({exc})",
                                     Blocker.PAYLOAD) from exc  # fmt: skip
            except (TypeError, ValueError) as exc:
                raise Untranslatable(f"GripLoad {format_expr(load)}: not a loaddata", Blocker.PAYLOAD) from exc
        use = len(self.c.payload_uses)
        name = None if released else format_expr(load)
        self.c.payload_uses.append((self._carrying_tool(), name, part, self.name, call.span.line, call))
        self.emit(f"PAYLOAD[{{PL:{use}}}]")

    def _carrying_tool(self) -> n.Expr | None:
        """The tool the moves after a GripLoad use, up to the next one; None: decided when the task is known."""
        tools: list[n.Expr] = []
        for stmt in walk_statements(self.after):
            if isinstance(stmt, n.ProcCall) and stmt.name.upper() == "GRIPLOAD":
                break
            if isinstance(stmt, n.Move) and stmt.tool is not None:
                tools.append(stmt.tool)
            elif isinstance(stmt, n.ProcCall) and (index := _TOOL_ARGUMENT.get(stmt.name.upper())) is not None:
                unnamed = [a.value for a in stmt.args if a.name is None and a.value is not None]
                if index < len(unnamed):
                    tools.append(unnamed[index])
        names = {format_expr(t).upper() for t in tools}
        if len(names) > 1:
            raise Untranslatable(f"GripLoad: the moves after it use {len(names)} tools ({', '.join(sorted(names))}),"
                                 " a FANUC payload goes with one", Blocker.PAYLOAD)  # fmt: skip
        if tools:
            return tools[0]
        return self.last_tool if self.active_ut is not None else None

    def analog(self, call: n.ProcCall, signal: n.Expr, value: n.Expr) -> None:
        """SetAO -> AO[n]=counts. RAPID gives the logical value, a FANUC analog output takes the module's
        counts: the scale comes from the mapping file (analog_scales), else the line stays TODO."""
        if not isinstance(signal, n.Name):
            raise Untranslatable(f"analog signal must be a name: {format_expr(signal)}", Blocker.SIGNAL)
        key = signal.name.upper()
        eio = self.c.eio.get(key)
        if eio is not None and eio.signal_type != "AO":
            raise Untranslatable(f"'{signal.name}' is a {eio.signal_type} signal in EIO.cfg, not AO", Blocker.SIGNAL)
        scale = self.c.config.analog_scales.get(key)
        detail = f"EIO.cfg: AO, device {eio.device or '-'}, map {eio.device_map or '-'}" if eio else ""
        target = f"AO[{self.c.aouts.number(signal.name, detail=detail)}]"
        if scale is None:
            raise Untranslatable(f"analog output {signal.name}: FANUC takes the module's counts, RAPID its logical"
                                 f" value: set analog_scales.{signal.name} (counts per RAPID unit) in the mapping"
                                 " file", Blocker.SIGNAL)  # fmt: skip
        try:
            counts = self.c.evaluator.constant_number(value) * scale
            self.emit(f"{target}={operand(register_value(round(counts)))}")
            return
        except Unresolvable:
            pass
        copy = self.c.written_register("AnalogCopy", key="CROSSARM.ANALOGCOPY")
        self.emit(f"{copy}={self.arithmetic(value)}")  # AO[n]=R[1]/10 does not load: through a register
        if scale != 1:
            self.emit(f"{copy}={copy}*{operand(fmt_number(scale))}")
        self.emit(f"{target}={copy}")

    def clock(self, expr: n.Expr) -> str:
        """TIMER[n] for a RAPID clock variable."""
        if not isinstance(expr, n.Name) or self.c.symbols.type_of(expr.name) != "clock":
            raise Untranslatable(f"'{format_expr(expr)}' is not a clock of the backup", Blocker.VALUE)
        return f"TIMER[{self.c.timers.number(expr.name)}]"

    def motion_setting(self, call: n.ProcCall, name: str, positional: list[n.Expr], options: list[n.Arg]) -> None:
        """ConfL, ConfJ, SingArea, CirPathMode: nothing where FANUC does the same, a warning where it does it
        its own way. AccSet and VelSet slow the robot down: dropping them would run it faster than the ABB,
        so they stay TODO unless they only set the defaults back."""
        switches = {(a.name or "").upper() for a in options}
        numbers: list[float] = []
        for value in positional:
            try:
                numbers.append(self.c.evaluator.constant_number(value))
            except Unresolvable as exc:
                raise Untranslatable(f"{call.name} with a value only known at run time ({exc})",
                                     Blocker.MOTION_SETTING) from exc  # fmt: skip
        if name in ("CONFL", "CONFJ"):
            if "OFF" in switches:
                self.warn(call, f"{call.name}\\Off left out: FANUC moves to each point with its CONFIG; where RAPID let"
                                " the arm change configuration, check the moves after it", Blocker.MOTION_SETTING)  # fmt: skip
        elif name == "SINGAREA":
            if switches - {"OFF"}:
                self.warn(call, f"{call.name} left out: FANUC has no such setting; check the moves after it near the"
                                " wrist singularity (J5 near 0)", Blocker.MOTION_SETTING)  # fmt: skip
        elif name == "CIRPATHMODE":
            if switches - {"PATHFRAME"}:
                self.warn(call, f"{call.name} left out: FANUC turns the tool along a circle its own way; check the"
                                " circles after it", Blocker.MOTION_SETTING)  # fmt: skip
        elif name == "ACCSET":
            if len(numbers) < 2 or min(numbers[:2]) < 100:
                raise Untranslatable(f"{call.name} {', '.join(fmt_number(v) for v in numbers)}: acceleration reduced;"
                                     " add ACC to the moves it covers (FANUC motion option)", Blocker.MOTION_SETTING)  # fmt: skip
        elif name == "VELSET":
            if not numbers or numbers[0] < 100:
                raise Untranslatable(f"{call.name}: speeds scaled in RAPID; scale the moves it covers",
                                     Blocker.MOTION_SETTING)  # fmt: skip
            if len(numbers) > 1:
                self.warn(call, f"{call.name}: the {fmt_number(numbers[1])} mm/s cap on the TCP speed is left out",
                          Blocker.MOTION_SETTING)  # fmt: skip

    def on_off(self, expr: n.Expr) -> str:
        value = expr.value if isinstance(expr, n.Number | n.Bool) else None
        if value in (0, False):
            return "OFF"
        if value in (1, True):
            return "ON"
        raise Untranslatable(f"signal value must be 0 or 1, got {format_expr(expr)}", Blocker.SIGNAL)

    # -- data -----------------------------------------------------------------------

    def assign(self, a: n.Assign) -> None:
        if self.c.externals and (call := self.provided_result_call(a)) is not None:  # x := F(args), F provided
            self.provided_assign(a, call)
            return
        if (part := self.component(a.target)) is not None and part in self.copies:  # g.count := ..., g a record
            self.emit(f"{self.copies[part]}={self.arithmetic(a.value)}")  # parameter: its component's copy
            return
        path = path_of(a.target)
        if path and (key := self.runtime_key(path[0])):
            self.runtime_assign(a, key, path)
            return
        root_type = self.c.symbols.type_of(path[0]) if path else None
        if root_type in _FRAME_TYPES | _POSITION_TYPES and path and path[0] not in self.copies:
            self.computed(a, root_type)
            return
        if (found := self.c.records.field(a.target)) is not None:
            self.record_assign(a, found)
            return
        if isinstance(a.target, n.Index) and root_type == "bool" and isinstance(a.target.base, n.Name) \
                and len(self.c.symbols.get(a.target.base.name).dims) == len(a.target.indices):  # type: ignore[union-attr]  # fmt: skip
            self.set_flag(lambda: self.flag_element(a.target, write=True), a.value)  # type: ignore[arg-type, return-value]
            self.known[path[0]] = Unknown(f"is set at l.{a.span.line}")  # type: ignore[index]
            return
        if isinstance(a.target, n.Index) and root_type == "string":
            raise Untranslatable(f"{format_expr(a.target)}: arrays of strings are not kept in string registers, of"
                                 f" which the controller has {self.c.config.limits.get('SR', SR_LIMIT)}",
                                 Blocker.TEXT)  # fmt: skip
        if isinstance(a.target, n.Index) and (element := self.number_element(a.target, write=True)) is not None:
            self.emit(f"{element}={self.arithmetic(a.value)}")
            self.known[path[0]] = Unknown(f"is set at l.{a.span.line}")  # type: ignore[index]
            return
        if not isinstance(a.target, n.Name):
            raise Untranslatable("assignment to a record component or array element",
                                 _assign_blocker(a.target, self.c.symbols.type_of))  # fmt: skip
        if a.target.name.upper() in self.copies:  # a parameter the routine changes: its register copy
            self.emit(f"{self.copies[a.target.name.upper()]}={self.arithmetic(a.value)}")
            return
        type_name = self.c.symbols.type_of(a.target.name)
        if a.target.name.upper() in self.loop_vars:
            raise Untranslatable("assignment to a FOR loop variable", Blocker.VALUE)
        if type_name in _NUMBERS:
            self.emit(f"{self.c.written_register(a.target.name)}={self.arithmetic(a.value)}")
        elif type_name == "string" and (register := self.text_register(a.target)) is not None:
            self.load_text(a.value, register, (1, 2))
            return
        elif type_name == "bool":
            self.set_flag(lambda: self.c.flag(a.target.name), a.value)  # type: ignore[union-attr]
        elif type_name is None and self.absent(a.target.name):
            raise self.not_in_backup(a.target.name, "data")
        else:
            raise Untranslatable(f"assignment of {type_name or 'undeclared data'} '{a.target.name}'",
                                 _type_blocker(type_name))  # fmt: skip
        try:  # a register keeps its value for the computations that read it further on
            name, value = self.c.computer.assigned(a)
            self.known[name] = value
        except Unresolvable:
            self.known[a.target.name.upper()] = Unknown(f"is set at l.{a.span.line} from a value only known at run time")

    # -- strings (crossarm.convert.strings) ------------------------------------------

    def is_text(self, expr: n.Expr | None) -> bool:
        """Whether an expression is a text: a string, string data or parameter, a function giving one."""
        match expr:
            case n.String():
                return True
            case n.BinaryOp(op="+", left=left, right=right):
                return self.is_text(left) or self.is_text(right)
            case n.Name(name=name):
                if self.args and self.args.kind(name) == "string":
                    return True
                return self.c.symbols.type_of(name) == "string"
            case n.FuncCall(name=fn):
                routine = self.c.computer.functions.get(fn.upper())
                if routine is not None:
                    return (routine.return_type or "").lower() == "string"
                return fn.upper() in _TEXT_FUNCTIONS
            case n.Component():
                if (field := self.component(expr)) is not None:  # a field of the routine's record parameter
                    return self.args.kind(field) == "string"  # type: ignore[union-attr]
                found = self.c.records.field(expr)
                return found is not None and found.type == "string"
        return False

    def text_new(self, stmt: n.Stmt) -> bool:
        """Whether a statement converts only since strings are kept in string registers: it declares, reads or
        sets a string the programs change, works a text out (StrLen, StrPart, NumToStr...) or compares texts.
        What it numbers first is numbered after the rest (NumberTable.defer): the programs without texts keep
        their numbers. Its own expressions only: the statements it holds are written one by one."""
        if isinstance(stmt, n.DataDecl):
            return stmt.type_name.lower() == "string" and not stmt.dims and self._changed_text(stmt.name)
        for node in nodes(stmt):
            if isinstance(node, n.Name) and self._changed_text(node.name):
                return True
            if isinstance(node, n.FuncCall) and node.name.upper() in _TEXT_WORK and node.name.upper() not in self.c.computer.functions:
                try:
                    self.c.computer.value(node)
                except Unresolvable:
                    return True
            if (isinstance(node, n.BinaryOp) and node.op in ("=", "<>", "+")
                    and (self.is_text(node.left) or self.is_text(node.right))
                    and not (self._fixed(node.left) and self._fixed(node.right))):  # fmt: skip
                return True
        return False

    def _changed_text(self, name: str) -> bool:
        decl = self.c.symbols.get(name)
        if decl is None or decl.type_name.lower() != "string" or decl.dims or (self.args and self.args.kind(name)):
            return False
        return self.c.strings.changed(decl, self.routine.name if self.c.symbols.is_local(name) else None) is not None

    def _fixed(self, expr: n.Expr) -> bool:
        """A text known at conversion time, told without numbering anything."""
        match expr:
            case n.String():
                return True
            case n.BinaryOp(op="+", left=left, right=right):
                return self._fixed(left) and self._fixed(right)
            case n.Name(name=name):
                return not (self.args and self.args.kind(name)) and not self._changed_text(name)
            case n.Component():
                if self.component(expr) is not None:
                    return False
                try:
                    return isinstance(self.c.computer.value(expr).value, str)
                except Unresolvable:
                    return False
        return False

    def fold_texts(self, expr: n.Expr) -> n.Expr:
        """A condition with each comparison of two texts known at conversion time written as its value:
        `IF sMode="AUTO"` with a CONST sMode is code switched on or off by hand, as `IF TRUE`."""
        match expr:
            case n.UnaryOp(op="NOT", operand=operand):
                inner = self.fold_texts(operand)
                return n.Bool(expr.span, not inner.value) if isinstance(inner, n.Bool) else n.UnaryOp(expr.span, "NOT", inner)
            case n.BinaryOp(op="AND" | "OR", left=left, right=right):
                a, b = self.fold_texts(left), self.fold_texts(right)
                for known, other in ((a, b), (b, a)):
                    if isinstance(known, n.Bool):
                        if known.value == (expr.op == "OR"):
                            return known  # TRUE OR x, FALSE AND x
                        return other
                return n.BinaryOp(expr.span, expr.op, a, b)
        if (self.text_comparison(expr) and expr.op in ("=", "<>")  # type: ignore[attr-defined]
                and self._fixed(expr.left) and self._fixed(expr.right)):  # type: ignore[attr-defined]  # fmt: skip
            left, right = self.fixed_text(expr.left), self.fixed_text(expr.right)  # type: ignore[attr-defined]
            if left is not None and right is not None:
                return n.Bool(expr.span, (left == right) == (expr.op == "="))  # type: ignore[attr-defined]
        return expr

    def text_comparison(self, expr: n.Expr) -> bool:
        return isinstance(expr, n.BinaryOp) and expr.op in _NEGATED and (self.is_text(expr.left) or self.is_text(expr.right))

    def has_text(self, expr: n.Expr) -> bool:
        """Whether a condition compares texts, alone or with AND / OR / NOT."""
        match expr:
            case n.UnaryOp(op="NOT", operand=operand):
                return self.has_text(operand)
            case n.BinaryOp(op="AND" | "OR", left=left, right=right):
                return self.has_text(left) or self.has_text(right)
        return self.text_comparison(expr)

    def jump_if(self, expr: n.Expr, label: int, truth: bool = True) -> None:
        """Lines jumping to LBL[label] when the condition is `truth`, else going on: a text comparison is
        `IF SR[a]=SR[b],JMP LBL[n]`, the only form TP has for one; AND and OR are jumps too."""
        match expr:
            case n.UnaryOp(op="NOT", operand=operand):
                self.jump_if(operand, label, not truth)
                return
            case n.BinaryOp(op="AND" | "OR", left=left, right=right):
                if (expr.op == "AND") == truth:  # both sides decide: past the first when it does not hold
                    past = self.label()
                    self.jump_if(left, past, not truth)
                    self.jump_if(right, label, truth)
                    self.emit(f"LBL[{past}]")
                else:  # either side decides
                    self.jump_if(left, label, truth)
                    self.jump_if(right, label, truth)
                return
        if self.text_comparison(expr):
            self.jump_on_text(expr, label, truth)  # type: ignore[arg-type]
        else:
            self.emit(f"IF ({self.condition(expr, negate=not truth)}),JMP LBL[{label}]")

    def jump_on_text(self, expr: n.BinaryOp, label: int, truth: bool) -> None:
        """`IF SR[a]=SR[b],JMP LBL[label]` for a comparison of two texts (RAPID has = and <> only). TP compares
        regardless of case: converted when no text of one side can differ from one of the other by case alone."""
        if expr.op not in ("=", "<>"):
            raise Untranslatable(f"texts compared with '{expr.op}': RAPID compares texts with = and <> only",
                                 Blocker.CONDITION)  # fmt: skip
        if not (self.is_text(expr.left) and self.is_text(expr.right)):
            raise Untranslatable(f"a text compared with a value of another type: {format_expr(expr)}", Blocker.CONDITION)
        equal = (expr.op == "=") == truth  # jump when the texts are equal
        left, right = self.fixed_text(expr.left), self.fixed_text(expr.right)
        if left is not None and right is not None:  # both known: the comparison is
            if (left == right) == equal:
                self.emit(f"JMP LBL[{label}]")
            return
        routine = self.routine.name
        alphabets = [self.c.strings.alphabet(side, routine, self.text_params) for side in (expr.left, expr.right)]
        if same_regardless_of_case(*alphabets) and not self.names_compared:  # a routine name: any case
            raise Untranslatable(f"TP compares texts regardless of case ('A' = 'a'), RAPID does not: "
                                 f"'{format_expr(expr.left)}' and '{format_expr(expr.right)}' can differ by case "
                                 "alone", Blocker.CONDITION)  # fmt: skip
        first = self.text_source(expr.left, (1, 2))
        second = self.text_source(expr.right, (2,) if first in self.c.scratch_texts else (1, 2))
        if first.startswith("AR[") and second.startswith("AR["):  # measured with a string register first
            copy = self.text_scratch(1)
            self.emit(f"{copy}={first}")
            first = copy
        elif first.startswith("AR["):
            first, second = second, first
        self.emit(f"IF {first}{'=' if equal else '<>'}{second},JMP LBL[{label}]")

    def fixed_text(self, expr: n.Expr) -> str | None:
        """The text of an expression known at conversion time: a string, a CONST, a string no program changes;
        None when it depends on the run."""
        match expr:
            case n.String(value=value):
                return value
            case n.BinaryOp(op="+", left=left, right=right):
                a, b = self.fixed_text(left), self.fixed_text(right)
                return None if a is None or b is None else a + b
            case n.Name(name=name):
                if (self.args and self.args.kind(name)) or self.text_register(expr) is not None:
                    return None
                decl = self.c.symbols.get(name)
                if decl is not None and decl.type_name.lower() == "string" and decl.init is None and not decl.dims:
                    return ""  # RAPID starts a string empty
            case n.Component():
                if self.text_register(expr) is not None:
                    return None
            case _:
                return None
        try:
            found = self.c.computer.value(expr).value
        except Unresolvable:
            return None
        return found if isinstance(found, str) else None

    def text_register(self, expr: n.Expr) -> str | None:
        """SR[n] keeping a string the programs change, or AR[n] for a text parameter of the routine; None for
        anything else (a string no program changes is its value)."""
        if isinstance(expr, n.Component) and (field := self.component(expr)) is not None:
            return self.args.register(field) if self.args.kind(field) == "string" else None  # type: ignore[union-attr]
        if not isinstance(expr, n.Name):
            return None
        if self.args and self.args.kind(expr.name) == "string":
            return self.args.register(expr.name)
        decl = self.c.symbols.get(expr.name)
        if decl is None or decl.type_name.lower() != "string" or decl.dims:
            return None
        local = self.c.symbols.is_local(expr.name)
        if not self.c.strings.changed(decl, self.routine.name if local else None):
            return None
        if not local:
            return self.c.string_register(decl.name)
        if self.routine.name.upper() in self.c.recursive:
            raise Untranslatable(f"{decl.name}, a string of a routine calling itself back: one string register"
                                 " would be shared by the calls under way", Blocker.TEXT)  # fmt: skip
        return self.c.string_register(decl.name, key=f"{self.name}.{decl.name}")

    def text_scratch(self, slot: int) -> str:
        self.text_slots.add(slot)
        return self.c.text_scratch(slot, self.routine.kind == "TRAP" or self.routine.name.upper() in self.c.trap_side)

    def text_source(self, expr: n.Expr, free: tuple[int, ...]) -> str:
        """The register holding a text, SR[n] or AR[n], loaded into a scratch one first (from `free`) when the
        text is worked out."""
        found = self.text_register(expr)
        if found is not None:
            return found
        if not free:
            raise Untranslatable(f"'{format_expr(expr)}': more texts worked out in one instruction than TP has"
                                 " scratch string registers for", Blocker.TEXT)  # fmt: skip
        scratch = self.text_scratch(free[0])
        self.load_text(expr, scratch, free[1:])
        return scratch

    def text_arg(self, call: n.FuncCall, index: int) -> n.Expr:
        positional = [a.value for a in call.args if a.name is None]
        if index >= len(positional) or positional[index] is None:
            raise Untranslatable(f"{call.name}: argument {index + 1} is missing", Blocker.VALUE)
        return positional[index]  # type: ignore[return-value]

    def load_text(self, expr: n.Expr, into: str, free: tuple[int, ...]) -> None:
        """Lines setting the string register `into` (SR[n:...]) to the text of `expr`; scratch registers from
        `free` for what is worked out on the way."""
        fixed = self.fixed_text(expr)
        if fixed is not None:
            self.load_literal(fixed, into, expr)
            return
        found = self.text_register(expr)
        if found is not None:
            if found != into:
                self.emit(f"{into}={found}")
            return
        match expr:
            case n.BinaryOp(op="+"):
                parts = self._text_parts(expr)
                if any(self.text_register(p) == into for p in parts[1:]):  # s:="x"+s: worked out apart first
                    if not free:
                        raise Untranslatable(f"'{format_expr(expr)}': no scratch string register left", Blocker.TEXT)
                    scratch = self.text_scratch(free[0])
                    self.load_text(expr, scratch, free[1:])
                    self.emit(f"{into}={scratch}")
                    return
                self.load_text(parts[0], into, free)
                for part in parts[1:]:
                    fixed = self.fixed_text(part)
                    if fixed is not None:
                        self.load_literal(fixed, into, part, append=True)
                    else:
                        self.emit(f"{into}={into}+{self.text_source(part, free)}")
                return
            case n.FuncCall(name=fn) if fn.upper() not in self.c.computer.functions:
                self.text_function(expr, into, free)  # type: ignore[arg-type]
                return
            case n.FuncCall(name=fn):
                raise Untranslatable(f"text '{format_expr(expr)}' is given by {fn}, a function of the backup: a TP"
                                     " program returns no value, the function's text is written only when it is"
                                     " known at conversion time", Blocker.VALUE)  # fmt: skip
            case n.Index(base=n.Name(name=name)) if self.c.symbols.type_of(name) == "string":
                raise Untranslatable(f"text '{format_expr(expr)}': an element of an array of texts, where CrossArm"
                                     " keeps texts one by one in string registers", Blocker.TEXT)  # fmt: skip
        raise Untranslatable(f"text '{format_expr(expr)}' is only known at run time", Blocker.VALUE)

    def _text_parts(self, expr: n.Expr) -> list[n.Expr]:
        """a+b+c, the texts known at conversion time next to each other put together: ["ab", s] for "a"+"b"+s."""
        if isinstance(expr, n.BinaryOp) and expr.op == "+":
            flat = self._text_parts(expr.left) + self._text_parts(expr.right)
        else:
            return [expr]
        parts: list[n.Expr] = []
        for part in flat:
            previous = self.fixed_text(parts[-1]) if parts else None
            current = self.fixed_text(part)
            if previous is not None and current is not None:
                parts[-1] = n.String(part.span, previous + current)
            else:
                parts.append(part)
        return parts

    def load_literal(self, text: str, into: str, expr: n.Expr, append: bool = False) -> None:
        """A text written in the program, into a string register: through the program loading texts, 38
        characters at a time (a longer one in pieces added at the end). An apostrophe ends a TP text: it is
        written as a backquote."""
        if self.routine.name.upper() in self.c.both_sides:
            raise Untranslatable(f"{self.routine.name} is run by a TRAP and by the programs: a TRAP stopping it "
                                 "between the line loading a text and the line reading it would load its own over "
                                 "it", Blocker.TEXT)  # fmt: skip
        if not text.isascii() or any(ord(c) < 32 for c in text):
            raise Untranslatable(f"text '{format_expr(expr)}' has a character TP texts do not have", Blocker.TEXT)
        if "'" in text:
            self.c.note(self.name, expr.span.line, "WARNING", f"'{text}' written with a backquote for each apostrophe:"
                        " an apostrophe ends a TP text", Blocker.TEXT)  # fmt: skip
            text = text.replace("'", "`")
        number = into[3:-1]
        program = self.c.text_program()
        if not text:
            if not append:  # one character, then none from past it: CALL X(n,'',0) is stored '...' (ROBOGUIDE)
                self.emit(f"CALL {program}({number},'x',0)")
                self.emit(f"{into}=SUBSTR {into},2,0")
            return
        for i in range(0, len(text), TEXT_PIECE):
            self.emit(f"CALL {program}({number},'{text[i : i + TEXT_PIECE]}',{1 if append or i else 0})")

    def text_function(self, call: n.FuncCall, into: str, free: tuple[int, ...]) -> None:
        """StrPart -> SUBSTR; NumToStr(n,0) and ValToStr(n) of a number only ever whole -> SR=R."""
        name = call.name.upper()
        if name == "STRPART":
            source = self.text_source(self.text_arg(call, 0), free)
            start = self.single(self.text_arg(call, 1), 1, bare=True)
            length = self.single(self.text_arg(call, 2), 2, bare=True)
            self.emit(f"{into}=SUBSTR {source},{start},{length}")
            return
        if name in ("NUMTOSTR", "VALTOSTR"):
            value = self.text_arg(call, 0)
            if name == "NUMTOSTR":
                decimals = self.text_arg(call, 1)
                try:
                    whole = self.c.evaluator.constant_number(decimals) == 0
                except Unresolvable:
                    whole = False
                if not whole or any(a.name is not None for a in call.args):
                    raise Untranslatable(f"{call.name} with decimals: TP writes a number held as a real with six"
                                         " decimals, whatever RAPID asks for", Blocker.VALUE)  # fmt: skip
            elif isinstance(value, n.Name) and (kind := self.c.symbols.type_of(value.name)) not in (None, *_NUMBERS):
                raise Untranslatable(f"{call.name} of a {kind}: TP writes numbers only", Blocker.VALUE)
            try:
                whole_value = self.c.evaluator.constant_number(value)
            except Unresolvable:
                whole_value = None
            if whole_value is not None and float(whole_value).is_integer():
                self.load_literal(str(int(whole_value)), into, value)
                return
            if not self.c.strings.integral(value, self.routine.name):
                raise Untranslatable(f"{call.name}({format_expr(value)}): TP writes a number held as a real with six"
                                     " decimals ('2.500000', '3.000000'): converted for a number the programs only"
                                     " ever give whole numbers", Blocker.VALUE)  # fmt: skip
            register = self.single(value, 1)
            if not register.startswith("R["):
                copy = self.c.written_register("Calc1", key="CROSSARM.CALC1")
                self.emit(f"{copy}={register}")
                register = copy
            self.emit(f"{into}={register}")
            return
        raise Untranslatable(f"{call.name}: no TP string instruction does what it does", Blocker.VALUE)

    def local_text(self, decl: n.DataDecl) -> None:
        """A string of the routine the programs change: set to its initial value where the routine starts, as
        RAPID does at each call. Its string register is shared by every call."""
        register = self.text_register(n.Name(decl.span, decl.name))
        if register is None:
            return
        self.load_text(decl.init if decl.init is not None else n.String(decl.span, ""), register, (1, 2))
        self.c.warn_once(
            f"text:{self.name}.{decl.name.upper()}", self.name, decl.span.line,
            f"{self.routine.name}.{decl.name}, a string of the routine, is kept in {register}: set to"
            " its initial value where the routine starts, as RAPID does at each call. The register is the"
            " controller's: every call of the routine shares it", Blocker.TEXT,
        )  # fmt: skip

    def text_number(self, call: n.FuncCall, slot: int) -> str:
        """StrLen -> STRLEN, StrMatch from the first character -> FINDSTR, worked out in R[n:Calc<slot>]. FINDSTR
        gives 0 when the pattern is not there, RAPID StrLen+1: set so on a line of its own."""
        text = self.text_arg(call, 0)
        if call.name.upper() == "STRLEN" and (fixed := self.fixed_text(text)) is not None:
            return str(len(fixed))
        register = self.c.written_register(f"Calc{slot}", key=f"CROSSARM.CALC{slot}")
        if call.name.upper() == "STRLEN":
            self.emit(f"{register}=STRLEN {self.text_source(text, (1, 2))}")
            return register
        try:
            start = self.c.evaluator.constant_number(self.text_arg(call, 1))
        except Unresolvable:
            start = None
        if start != 1:
            raise Untranslatable(f"{call.name} from character '{format_expr(self.text_arg(call, 1))}': FINDSTR searches"
                                 " from the first only", Blocker.VALUE)  # fmt: skip
        pattern = self.text_arg(call, 2)
        alphabets = [self.c.strings.alphabet(side, self.routine.name, self.text_params) for side in (text, pattern)]
        if same_regardless_of_case(*alphabets):
            raise Untranslatable(f"FINDSTR searches regardless of case ('A' finds 'a'), StrMatch does not: "
                                 f"'{format_expr(text)}' and '{format_expr(pattern)}' can differ by case alone",
                                 Blocker.VALUE)  # fmt: skip
        source = self.text_source(text, (1, 2))
        found = self.text_source(pattern, (2,) if source in self.c.scratch_texts else (1, 2))
        done = self.label()
        self.emit(f"{register}=FINDSTR {source},{found}")
        self.emit(f"IF {register}<>0,JMP LBL[{done}]")
        self.emit(f"{register}=STRLEN {source}")
        self.emit(f"{register}={register}+1")
        self.emit(f"LBL[{done}]")
        return register

    # -- records (crossarm.convert.records) ------------------------------------------

    def record_owner(self, found: Field) -> str | None:
        """This program's name when the record is the routine's own data, None for module data."""
        if not self.c.symbols.is_local(found.root.name):
            return None
        if any(leaf.type not in SCALARS for leaf in self.c.records.leaves(Field(found.root, (), found.root.type_name.lower()))):
            raise Untranslatable(f"{found.root.name}: a record of the routine is converted when all its fields are"
                                 " num or bool", Blocker.RECORD)  # fmt: skip
        if self.routine.name.upper() in self.c.recursive:
            raise Untranslatable(f"{found.root.name}: a record of a routine that calls itself back: the registers"
                                 " would be shared by its calls", Blocker.RECORD)  # fmt: skip
        return self.name

    def field_value(self, expr: n.Expr) -> Any:
        """For the Evaluator: the value of a record field written as its value (no program changes it, or a
        speed or zone every write sets the same); None for any other expression. Unresolvable when it
        changes at run time."""
        found = self.c.records.field(expr)
        if found is None or found.indexed or self.c.records.is_record(found.type):
            return None
        if found.within is not None:  # a component of a speed or zone field: of its value
            value, type_name = self.motion_value(found.within), found.within.type
            for name in found.path[len(found.within.path):]:
                index, type_name = self.c.computer.layouts.field(type_name, name)
                value = value[index]
            return value
        if found.type in MOTION:
            return self.motion_value(found)
        where = self.c.records.changed(found)
        if where is not None:
            raise Unresolvable(f"'{found.name}' is changed by the programs ({where})")
        value = self.c.records.initial(found)
        self.c.saved_value(found, value)
        return value

    def motion_value(self, found: Field) -> Any:
        """A speed or zone field: the value no program changes, or the one every write gives it."""
        if self.c.records.changed(found) is None:
            value = self.c.records.initial(found)
            self.c.saved_value(found, value)
            return value
        same = self.c.records.same_value(found)
        if isinstance(same, str):
            raise Unresolvable(f"{found.name}: {same}: a speed or zone field is converted when every write gives"
                               " it the same value")  # fmt: skip
        value, writes = same
        before = self.c.records.read_before(found, writes)
        try:
            initial = self.c.records.initial(found)
        except Unresolvable:
            initial = None
        if before is not None or initial != value:
            self.c.warn_once(
                f"field:{found.name.upper()}", "", None,
                f"{found.name} is set at {', '.join(writes)} and written as that value in the moves"
                + (f": it is read at {before} before it is set, where the ABB robot still has its"
                   f" {'declared' if found.root.init is not None else 'zero'} value" if before else
                   ": right once that routine has run"),
                Blocker.RECORD_VALUE,
            )  # fmt: skip
        return value

    def record_assign(self, a: n.Assign, found: Field) -> None:
        """An assignment to a record data, a record in it or one of its fields: one line per field kept."""
        if found.indexed:
            raise Untranslatable(f"{format_expr(a.target)}: an array of records is not converted", Blocker.RECORD)
        program = self.record_owner(found)
        leaves = self.c.records.leaves(found)
        sources = [a.value] if leaves == [found] else self.record_sources(a.value, found, leaves)
        written = len(self.lines)
        for leaf, source in zip(leaves, sources, strict=True):
            self.field_assign(leaf, source, program)
        if len(self.lines) == written:  # only speeds and zones, written as their value in the moves
            self.emit(("!" + ascii_text(f"l.{a.span.line} {self.rapid_text(a).rstrip(';')}")[:REMARK_MAX]).rstrip())
        try:
            name, value = self.c.computer.assigned(a)
            self.known[name] = value
        except Unresolvable:
            self.known[found.key[0]] = Unknown(f"is set at l.{a.span.line} from a value only known at run time")

    def set_flag(self, target: Callable[[], str], value: n.Expr) -> None:
        """A flag set to a bool value: `F[n]=(ON)` for one known at conversion time (a CONST, a field no program
        changes), `F[n]=(F[m])` for another flag, `F[n]=(R[1]<5 AND DI[2]=ON)` for a condition, as TP's mixed
        logic writes it (ROBOGUIDE: NOT, AND, OR, nested parentheses, outputs, registers, flags load and give the
        condition's value). A comparison of texts, which TP makes in a jump only: OFF, then ON past the jump.
        `target` numbers the flag set, once what it is set from is numbered."""
        source = self.fold_texts(self.simplify(value))
        if isinstance(source, n.Bool):
            self.emit(f"{target()}=({'ON' if source.value else 'OFF'})")
        elif (other := self.bool_flag(source)) is not None:
            self.emit(f"{target()}=({other})")
        elif self.has_text(source):
            flag = target()
            done = self.label()
            self.emit(f"{flag}=(OFF)")
            self.jump_if(source, done, False)
            self.emit(f"{flag}=(ON)")
            self.emit(f"LBL[{done}]")
        else:
            condition = self.condition(source)
            self.emit(f"{target()}=({condition})")

    def bool_flag(self, expr: n.Expr) -> str | None:
        """F[n:...] keeping a bool data or a bool field the programs change; None for anything else."""
        if isinstance(expr, n.Name) and self.c.symbols.type_of(expr.name) == "bool":
            return self.c.flag(expr.name)
        if (element := self.flag_element(expr)) is not None:
            return element
        found = self.c.records.field(expr)
        if found is not None and found.type == "bool" and not found.indexed and self.c.records.changed(found):
            return self.c.field_number(found, True, self.record_owner(found))
        return None

    def record_sources(self, value: n.Expr, found: Field, leaves: list[Field]) -> list[n.Expr]:
        """For a record set as a whole: the value of each of its fields, from a list of values or another record."""
        other = self.c.records.field(value)
        if other is not None and other.type == found.type and not other.indexed:
            out = []
            for leaf in leaves:
                source: n.Expr = value
                for name in leaf.path[len(found.path):]:
                    source = n.Component(value.span, source, name)
                out.append(source)
            return out
        if isinstance(value, n.Aggregate):
            out = []
            for leaf in leaves:
                item: n.Expr = value
                type_name = found.type
                for name in leaf.path[len(found.path):]:
                    index, type_name = self.c.computer.layouts.field(type_name, name)
                    if not isinstance(item, n.Aggregate) or index >= len(item.items):
                        raise Untranslatable(f"{format_expr(value)}: not a {found.type}", Blocker.RECORD)
                    item = item.items[index]
                out.append(item)
            return out
        raise Untranslatable(f"{found.name} set to {format_expr(value)}: a whole record is converted from another"
                             " record or a list of values", Blocker.RECORD)  # fmt: skip

    def field_assign(self, leaf: Field, value: n.Expr, program: str | None) -> None:
        if leaf.within is not None:
            raise Untranslatable(f"{leaf.name}: a component of a speed or zone field is not converted", Blocker.RECORD)
        if leaf.type == "num":
            self.emit(f"{self.c.field_number(leaf, False, program)}={self.arithmetic(value)}")
        elif leaf.type == "bool":
            self.set_flag(lambda: self.c.field_number(leaf, True, program), value)
        elif leaf.type in MOTION:
            try:
                self.motion_value(leaf)
            except Unresolvable as exc:
                raise Untranslatable(str(exc), Blocker.RECORD) from exc
        elif leaf.type == "string":
            raise Untranslatable(f"string field {leaf.name}: a string of a record is not kept in a string register", Blocker.VALUE)
        else:
            blocker = _type_blocker(leaf.type) if leaf.type in _FRAME_TYPES | _POSITION_TYPES else Blocker.RECORD
            raise Untranslatable(f"{leaf.type} field {leaf.name}: not converted", blocker)

    def computed(self, a: n.Assign, root_type: str) -> None:
        """A frame or a position the routine computes: worked out now if every input is fixed
        (crossarm.convert.compute), else TODO with the input that is not. A frame a move selects is then
        loaded where the RAPID computes it, from the register SETUP_FRAMES sets: `UTOOL[3]=PR[95]`."""
        target = format_expr(a.target)
        is_frame = root_type in _FRAME_TYPES
        if not isinstance(a.target, n.Name) and _assign_blocker(a.target, self.c.symbols.type_of) == Blocker.PAYLOAD:
            raise Untranslatable(f"payload {target} changed at run time: select a PAYLOAD schedule on the FANUC"
                                 " (PAYLOAD[n]) where the RAPID changes it", Blocker.PAYLOAD)  # fmt: skip
        category = _type_blocker(root_type) if isinstance(a.target, n.Name) else _assign_blocker(a.target, self.c.symbols.type_of)
        what = f"{'frame' if is_frame else 'position'} {target}"
        line = a.span.line
        remark = ("!" + ascii_text(f"l.{line} {self.rapid_text(a).rstrip(';')}")[:REMARK_MAX]).rstrip()
        if is_frame and self.field_without_frame(a, remark):  # ufprog, ufmec, a field kept as declared: no frame
            return
        if self.provided_point(a.value) is not None:  # a provided function's pose (calls.py): loaded, or a part of it
            if is_frame and (self.frame_written(a, root_type, remark, False) or self.frame_at_run_time(a, root_type, remark)):
                return
            raise Untranslatable(f"{what} set to {format_expr(a.value)}: a provided function's result is written to num"
                                 " data, a point or pose kept in a position register, a frame's uframe or tframe, or"
                                 " its trans", category)  # fmt: skip
        try:
            root, new = self.c.computer.assigned(a)
        except MeasuredAtRunTime as exc:
            if self.func_inlined(a, root_type, exc, what, category):  # a FUNC of the backup: convert.func_inline
                return
            if is_frame and self.frame_written(a, root_type, remark, True, str(exc)):  # part by part, or copied: frame_writes
                return
            if is_frame and self._kept_frame(a) and self.frame_at_run_time(a, root_type, remark):  # convert.karel_poses
                return
            raise Untranslatable(self.measured_why(a, root_type, what, exc), Blocker.CALIBRATION) from exc
        except Unresolvable as exc:
            if self.func_inlined(a, root_type, exc, what, category):
                return
            if is_frame and self.frame_written(a, root_type, remark, self.measured_point(a.value) is not None, str(exc)):
                return
            if is_frame and self._kept_frame(a) and self.frame_at_run_time(a, root_type, remark):
                return
            if is_frame and (measured := self.measured_point(a.value)) is not None:  # a point set to CRobT()
                raise Untranslatable(self.measured_why(a, root_type, what, measured), Blocker.CALIBRATION) from exc
            raise Untranslatable(f"{what} computed from data only known at run time: {exc}", category) from exc
        if is_frame:
            if (hole := self.frame_unknown(a, root_type, root, new)) is not None:  # a field the frame needs
                if self.oframe_written(a, root_type, remark, new):  # the uframe at run time: frame_writes
                    return
                if hole.measured:
                    raise Untranslatable(self.measured_why(a, root_type, what, hole.error()), Blocker.CALIBRATION)
                raise Untranslatable(f"{what} computed from data only known at run time: {hole.why}", category)
            kind = "UT" if root_type == "tooldata" else "UF"
            pose = self._fanuc_frame(kind, new, target)
            decl = self.c.symbols.get(root)
            if root in self.c.frames_in_moves[kind] and decl is not None:
                token = self.c.computed_frame(kind, decl.name, pose, self.name, line, a)
                self.emit(remark)
                self.emit(f"{'UTOOL' if kind == 'UT' else 'UFRAME'}[{{{kind}:{root}}}]={token}")
                if kind == "UT":
                    self.active_ut = None
                    self._payload_change(a, decl.name, new)
                else:
                    self.active_uf = None
                self.known[root] = new
                self.known.pop(f"{root}#FRAME", None)  # loaded whole: the robot holds it (frame_writes)
                return
        self.emit(remark)
        self.known[root] = new

    def _kept_frame(self, a: n.Assign) -> bool:
        """Whether a frame set at run time may be loaded from a position register: with --karel; without, from a
        pose kept in one (a provided function's result: convert.external), the oframe the identity."""
        return self.c.config.karel or self.kept_pose_key(a.value) is not None

    def measured_point(self, value: n.Expr) -> MeasuredAtRunTime | None:
        """"'pMeas' is measured on the robot at l.4" when the value reads a point kept in a position register
        that was read on the robot (CRobT, as LPOS), or derives from one; None otherwise."""
        for node in expr_nodes(value):
            if isinstance(node, n.Name) and self.runtime_key(node.name) is not None:
                turn = self.known.get(f"{node.name.upper()}#ROT")
                if isinstance(turn, Unknown) and turn.measured:
                    return MeasuredAtRunTime(f"'{node.name}' {turn.reason}")
        return None

    def measured_why(self, a: n.Assign, root_type: str, what: str, exc: MeasuredAtRunTime) -> str:
        """Why a frame or a position read on the robot (computed() of it) stays TODO."""
        return measured_reason(what, root_type, root_type in _FRAME_TYPES, exc, bool(self.c.computer.robot_reads(a.value)))

    def _fanuc_frame(self, kind: str, new: Typed, target: str) -> Pose:
        """A computed tooldata / wobjdata as the FANUC frame: the tool on the faceplate, uframe x oframe."""
        try:
            if kind == "UT":
                robhold, tframe, _load = new.value
                if not robhold:
                    raise Untranslatable(f"{target}: stationary tool (robhold FALSE): not supported", Blocker.STATIONARY)
                return tool_on_flange(Frame(to_pose(tframe), True, target), self.c.config.tool_pin).pose
            robhold, _ufprog, _ufmec, uframe, oframe = new.value
            if robhold:
                raise Untranslatable(f"{target}: robot-held work object: not supported", Blocker.STATIONARY)
            return to_pose(uframe).compose(to_pose(oframe))
        except (TypeError, ValueError, Unresolvable) as exc:
            raise Untranslatable(f"{target}: not a valid frame ({exc})", Blocker.VALUE) from exc

    def _payload_change(self, a: n.Assign, name: str, new: Typed) -> None:
        """A computed tool carrying another load than the one declared: FANUC keeps payloads apart from frames."""
        try:
            mass = float(new.value[2][0])
            declared = self.c.declared_frame("UT", n.Name(a.span, name)).load
        except (TypeError, ValueError, IndexError, Unresolvable):
            return
        if declared is None or abs(declared.mass - mass) > 1e-6:
            self.warn(a, f"tool {name}: its load changes here ({mass:g} kg): FANUC keeps payloads apart from tool"
                         " frames, select the PAYLOAD schedule for it (PAYLOAD[n])", Blocker.PAYLOAD)  # fmt: skip

    def arithmetic(self, expr: n.Expr) -> str:
        """Right-hand side of R[n]=...: a value or ONE arithmetic operation, as TP allows; what a larger
        calculation needs before it is worked out in scratch registers first (single())."""
        try:
            return decimal(operand(register_value(self.c.evaluator.constant_number(expr))))
        except Unresolvable:
            pass
        if isinstance(expr, n.FuncCall) and expr.name.upper() == "STRLEN" and expr.name.upper() not in self.c.computer.functions:
            fixed = self.fixed_text(self.text_arg(expr, 0))
            return str(len(fixed)) if fixed is not None else f"STRLEN {self.text_source(self.text_arg(expr, 0), (1, 2))}"
        if (joint := self.joint_axis(expr, 1, operation=True)) is not None:  # an axis of a jointtarget kept in PR
            return joint
        if isinstance(expr, n.BinaryOp) and expr.op in _ARITHMETIC:
            left, right = self.single(expr.left, 1), self.single(expr.right, 2)
            op = f" {expr.op} " if expr.op in ("DIV", "MOD") else expr.op
            return f"{left}{op}{right}"
        return self.single(expr, 1)

    def single(self, expr: n.Expr, slot: int = 1, bare: bool = False) -> str:
        """One TP operand for a value: itself when TP reads it as one, else worked out in the scratch register
        R[n:Calc<slot>], one operation per line: TP refuses `+` and `*` in one calculation (ASBN-040) and a
        calculation going on after parentheses. The left side is worked out in the slot, the right one in
        the next slots, which never overwrite it. `bare`: a negative constant without its parentheses, as
        WaitTime and SUBSTR take it."""
        if (joint := self.joint_axis(expr, slot)) is not None:  # an axis of a jointtarget kept in PR, in Calc<slot>
            return joint
        if (isinstance(expr, n.FuncCall) and expr.name.upper() in ("STRLEN", "STRMATCH")
                and expr.name.upper() not in self.c.computer.functions):  # fmt: skip
            try:
                return decimal(operand(register_value(self.c.evaluator.constant_number(expr))))
            except Unresolvable:
                pass
            if self.stepless:
                raise Untranslatable(f"{expr.name} in a condition read again and again: TP works it out on a line"
                                     " of its own", Blocker.CONDITION)  # fmt: skip
            return self.text_number(expr, slot)
        try:
            return decimal(self.numeric(expr) if bare else operand(self.numeric(expr)))
        except Untranslatable:
            if self.stepless or not isinstance(expr, n.BinaryOp | n.UnaryOp):
                raise
            if isinstance(expr, n.UnaryOp) and expr.op != "-" or isinstance(expr, n.BinaryOp) and expr.op not in _ARITHMETIC:
                raise
        register = self.c.written_register(f"Calc{slot}", key=f"CROSSARM.CALC{slot}")
        if isinstance(expr, n.UnaryOp):  # -(a*b)
            self.emit(f"{register}={self.single(expr.operand, slot)}*(-1)")
            return register
        left, right = self.single(expr.left, slot), self.single(expr.right, slot + 1)
        op = f" {expr.op} " if expr.op in ("DIV", "MOD") else expr.op
        self.emit(f"{register}={left}{op}{right}")
        return register

    def numeric(self, expr: n.Expr) -> str:
        """A single TP numeric operand: a constant (CONST or literal), a register or a group input."""
        if (result := self.provided_operand(expr)) is not None:  # a provided function's result (calls.py)
            return result
        if isinstance(expr, n.FuncCall) and expr.name.upper() == "GINPUT" and len(expr.args) == 1 and expr.args[0].value:
            return self.group(expr.args[0].value, "GI", expr.span.line)
        if isinstance(expr, n.FuncCall) and expr.name.upper() == "CLKREAD" and expr.args and expr.args[0].value:
            if any(a.name is not None and a.name.upper() != "HIGHRES" for a in expr.args[1:]):
                raise Untranslatable(f"{format_expr(expr)}: only \\HighRes is converted", Blocker.OPTIONS_IGNORED)
            return self.clock(expr.args[0].value)  # seconds, as ClkRead (wait probe: 1.000000 after 1 s)
        if isinstance(expr, n.Index) and (element := self.number_element(expr)) is not None:
            return element
        if isinstance(expr, n.Name) and (number := self.interrupt_value(expr)) is not None:
            return number
        if isinstance(expr, n.Name):
            key = expr.name.upper()
            if key in self.loop_vars:
                return self.loop_vars[key]
            if key in self.copies:
                return self.copies[key]
            if self.args and self.args.kind(key) == "num":
                return self.args.register(key)  # type: ignore[return-value]
            decl = self.c.symbols.get(expr.name)
            if decl is not None and decl.type_name.lower() in _NUMBERS and decl.storage != "CONST":
                return self.c.register(expr.name)
            # A group input read by its name, as RAPID allows: IF giCode>0 is IF GInput(giCode)>0.
            eio = self.c.eio.get(key)
            if decl is None and (key in self.c.config.group_inputs or (eio is not None and eio.signal_type == "GI")):
                return self.group(expr, "GI", expr.span.line)
        if (axis := self.runtime_axis(expr)) is not None:
            return axis
        if (field := self.component(expr)) and self.args.kind(field) == "num":  # type: ignore[union-attr]
            return self.copies.get(field) or self.args.register(field)  # type: ignore[union-attr, return-value]
        found = self.c.records.field(expr)
        if found is not None and found.type == "num" and not found.indexed and found.within is None                 and self.c.records.changed(found):  # fmt: skip
            return self.c.field_number(found, False, self.record_owner(found))
        try:
            return register_value(self.c.evaluator.constant_number(expr))
        except Unresolvable as exc:
            if isinstance(expr, n.Component):  # a record's number no program changes: pdHousing.passes
                try:
                    found = self.c.computer.value(expr).value
                except Unresolvable:
                    found = None
                if isinstance(found, int | float) and not isinstance(found, bool):
                    return register_value(float(found))
            try:
                fixed = fixed_math(self.c.computer, expr)  # Pow(2, nRings): TP has no power
            except Unresolvable as why:
                raise Untranslatable(f"'{format_expr(expr)}' is not a simple numeric value ({why})",
                                     Blocker.VALUE) from why  # fmt: skip
            if fixed is not None:
                self.saved_pers(fixed[1], expr)
                return register_value(fixed[0])
            kind = self.c.symbols.type_of(expr.name) if isinstance(expr, n.Name) else None
            if kind in _POSITION_TYPES | _FRAME_TYPES or self.c.records.is_record(kind):
                raise Untranslatable(f"'{expr.name}' is a {kind}: TP compares and calculates numbers, not a"  # type: ignore[union-attr]
                                     f" whole {kind}", Blocker.CONDITION) from exc  # fmt: skip
            raise Untranslatable(f"'{format_expr(expr)}' is not a simple numeric value ({exc})", Blocker.VALUE) from exc

    def saved_pers(self, names: list[str], expr: n.Expr) -> None:
        """A WARNING, once per data, for each PERS a value worked out at conversion time read as saved."""
        for name in names:
            decl = self.c.symbols.get(name)
            shown = format_expr(decl.init) if decl is not None and decl.init is not None else "?"
            self.c.warn_once(f"saved:{name.upper()}", self.name, expr.span.line,
                             f"{name}, a PERS no program changes, is read at its value saved in the backup ({shown})"
                             f" to work out {format_expr(expr)}, which TP cannot calculate; a value set on the ABB"
                             " controller since is not", Blocker.SAVED_VALUE)  # fmt: skip

    def interrupt_value(self, expr: n.Name) -> str | None:
        """An intnum as a number (its interrupt's, interrupts.Interrupt.number), and INTNO in a TRAP: the register
        its relays note that number in. None for any other name."""
        key = expr.name.upper()
        decl = self.c.symbols.get(expr.name)
        if decl is None and key == "INTNO":
            if not self.served:
                raise Untranslatable("INTNO outside a TRAP converted", Blocker.INTERRUPT)
            return self.c.intno()  # a TRAP reading INTNO is called through relays, which set it (interrupts.scan)
        if decl is not None and decl.type_name.lower() == "intnum" and key in self.c.interrupts:
            return str(self.c.interrupts[key].number)
        return None

    def component(self, expr: n.Expr) -> str | None:
        """'PART.PASSES' for `part.passes` when `part` is a record parameter of this routine, passed as its
        components (crossarm.convert.arguments); None otherwise."""
        if not (isinstance(expr, n.Component) and isinstance(expr.base, n.Name) and self.args is not None):
            return None
        if self.args.kind(expr.base.name) != "record":
            return None
        key = f"{expr.base.name}.{expr.field}".upper()
        return key if self.args.kind(key) else None

    # -- control flow -----------------------------------------------------------------

    def if_stmt(self, branches: tuple[n.IfBranch, ...], else_body: tuple[n.Stmt, ...]) -> None:
        """IF/ELSEIF/ELSE. A branch on a constant is code switched on or off by hand (`IF FALSE THEN`):
        what never runs is left out with a remark, what always runs is converted without a test."""
        live: list[n.IfBranch] = []
        for branch in branches:
            written = branch.condition
            test = self.fold_texts(self.simplify(written))
            if not isinstance(test, n.Bool):
                live.append(n.IfBranch(test, branch.body))
            elif test.value:  # IF TRUE: it always runs, the branches after it never do
                if not isinstance(written, n.Bool):
                    self.emit(f"!l.{written.span.line} IF always TRUE: no test")
                else_body = branch.body
                break
            elif isinstance(written, n.Bool):
                self.emit(f"!l.{written.span.line} IF FALSE: never runs")
            else:
                self.emit(f"!l.{written.span.line} IF never TRUE: left out")
        if live and any(self.has_text(b.condition) for b in live):
            self._jump_chain(tuple(live), else_body)
        elif live:
            self._if_chain(tuple(live), else_body)
        else:
            self.block(else_body)

    def _jump_chain(self, branches: tuple[n.IfBranch, ...], else_body: tuple[n.Stmt, ...]) -> None:
        """IF/ELSEIF/ELSE comparing texts, with jumps: TP compares string registers only in `IF SR[a]=SR[b],JMP`,
        never inside `IF (...) THEN`. Each branch is skipped when its condition is false, and ends with a jump
        past the others."""
        end = self.label()
        known = dict(self.known)
        states = []
        for i, branch in enumerate(branches):
            last = i == len(branches) - 1 and not else_body
            skip = end if last else self.label()
            self.jump_if(branch.condition, skip, False)
            self.block(branch.body)
            states.append(self.known)
            self.known = dict(known)
            if not last:
                self.emit(f"JMP LBL[{end}]")
                self.emit(f"LBL[{skip}]")
        if else_body:
            self.block(else_body)
        states.append(self.known)
        self.emit(f"LBL[{end}]")
        self.merge(branches[0].condition.span.line, *states)

    def _if_chain(self, branches: tuple[n.IfBranch, ...], else_body: tuple[n.Stmt, ...]) -> None:
        """Each branch starts from the frames selected before the IF; after it, only what every path agrees on
        is known: a frame selected in one branch only must be selected again."""
        first, rest = branches[0], branches[1:]
        start = (self.active_uf, self.active_ut)
        known = dict(self.known)
        self.emit(f"IF ({self.condition(first.condition)}) THEN")
        self.block(first.body)
        ends = [(self.active_uf, self.active_ut)]
        self.active_uf, self.active_ut = start
        after_first, self.known = self.known, dict(known)
        if rest:  # ELSEIF -> ELSE + nested IF (TP has no ELSEIF)
            self.emit("ELSE")
            self._if_chain(rest, else_body)
        elif else_body:
            self.emit("ELSE")
            self.block(else_body)
        ends.append((self.active_uf, self.active_ut))
        self.merge(first.condition.span.line, after_first, self.known)
        self.emit("ENDIF")
        (uf1, ut1), (uf2, ut2) = ends
        self.active_uf = uf1 if uf1 == uf2 else None
        self.active_ut = ut1 if ut1 == ut2 else None

    def for_stmt(self, loop: n.For) -> None:
        step = 1.0 if loop.step is None else self.c.evaluator.constant_number(loop.step)
        if step not in (1.0, -1.0):
            raise Untranslatable("FOR with a STEP other than 1 or -1 (TP FOR only counts by 1)", Blocker.LOOP)
        key = loop.var.upper()
        register = self.c.written_register(loop.var, key=f"{self.name}.{loop.var}")
        # A negative bound in parentheses: ROBOGUIDE refuses FOR R[1]=-2 TO 2 (ASBN-092).
        start, end = operand(self.numeric(loop.start)), operand(self.numeric(loop.end))
        self.emit(f"FOR {register}={start} {'TO' if step > 0 else 'DOWNTO'} {end}")
        self.loop_vars[key] = register
        self.active_uf = self.active_ut = None  # the second turn starts where the first one ended
        changes = Unknown(f"changes in the loop at l.{loop.span.line}")
        self.forget(loop.body, changes)  # so does what the data holds
        try:
            self.block(loop.body)
        finally:
            del self.loop_vars[key]
        self.emit("ENDFOR")
        self.active_uf = self.active_ut = None  # zero turns, or several
        self.forget(loop.body, changes)

    def while_stmt(self, loop: n.While) -> None:
        loop = n.While(loop.span, self.fold_texts(self.simplify(loop.condition)), loop.body)
        if isinstance(loop.condition, n.Bool) and not loop.condition.value:
            self.emit(f"!l.{loop.span.line} WHILE FALSE: never runs")
            return
        top = self.label()
        changes = Unknown(f"changes in the loop at l.{loop.span.line}")
        self.forget(loop.body, changes)  # each turn starts from what the one before left
        if isinstance(loop.condition, n.Bool) and loop.condition.value:
            self.emit(f"LBL[{top}]")
            self.block(loop.body)
            self.emit(f"JMP LBL[{top}]")
            self.forget(loop.body, changes)
            return
        exit_label = self.label()
        self.emit(f"LBL[{top}]")
        if self.has_text(loop.condition):  # texts are compared in IF ...,JMP only
            self.jump_if(loop.condition, exit_label, False)
        else:
            self.emit(f"IF ({self.condition(loop.condition, negate=True)}) THEN")
            self.emit(f"JMP LBL[{exit_label}]")
            self.emit("ENDIF")
        self.block(loop.body)
        self.emit(f"JMP LBL[{top}]")
        self.emit(f"LBL[{exit_label}]")
        self.forget(loop.body, changes)

    def test_stmt(self, test: n.Test) -> None:
        """TEST/CASE -> SELECT, one line per CASE value, then the branches behind labels.

        Measured on ROBOGUIDE: the first line whose value is equal wins, as the first CASE does in RAPID;
        with no ELSE and no value equal, the program goes on after the SELECT, and so does a CALL made on a
        SELECT line once it returns. A branch that is a single CALL is made on its SELECT line.
        """
        line = test.span.line
        if not test.cases:  # nothing to compare: the DEFAULT always runs
            self.block(test.default or ())
            return
        values = [[self._case_value(v) for v in case.values] for case in test.cases]
        subject = self.numeric(test.subject)
        try:  # a constant: the branch is known now
            self._constant_test(test, float(subject), values)
            return
        except ValueError:
            pass
        if not re.fullmatch(r"R\[[^\]]*\]", subject):  # SELECT reads a register only
            register = self.c.written_register(TEST_VALUE, key="CROSSARM.TESTVALUE")
            self.emit(f"{register}={subject}")
            subject = register
        start, known = (self.active_uf, self.active_ut), dict(self.known)
        bodies = [case.body for case in test.cases] + ([test.default] if test.default is not None else [])
        branches: list[list[Instruction | Motion]] = []
        ends: list[dict[str, Typed | Unknown]] = [] if test.default is not None else [known]
        for body in bodies:  # each branch starts from what held before the TEST
            self.active_uf, self.active_ut = start
            self.known = dict(known)
            mark = len(self.lines)
            self.block(body)
            branches.append(self.lines[mark:])
            del self.lines[mark:]
            ends.append(self.known)
        end = self.label()
        actions: list[str] = []
        behind: list[tuple[int, list[Instruction | Motion], tuple[n.Stmt, ...]]] = []  # the branches after the SELECT
        for body, lines in zip(bodies, branches, strict=True):
            if not lines:
                actions.append(f"JMP LBL[{end}]")
            elif len(lines) == 1 and isinstance(lines[0], Instruction) and lines[0].text.startswith("CALL "):
                actions.append(lines[0].text)
            else:
                behind.append((self.label(), lines, body))
                actions.append(f"JMP LBL[{behind[-1][0]}]")
        select, seen = [], set()
        for case_values, action in zip(values, actions, strict=False):
            for value in case_values:
                if value not in seen:  # the controller would take the first one anyway
                    seen.add(value)
                    select.append(f"={value},{action}")
        if test.default is not None:
            select.append(f"ELSE,{actions[-1]}")
        self.emit(f"SELECT {subject}{select[0]}")
        for text in select[1:]:
            self.emit(SELECT_INDENT + text)
        # Past the SELECT: no value equal and no ELSE, or back from a CALL made on a SELECT line.
        after_select = test.default is None or any(a.startswith("CALL ") for a in actions)
        used = any(a == f"JMP LBL[{end}]" for a in actions)
        if behind and after_select:
            self.emit(f"JMP LBL[{end}]")
            used = True
        for i, (label, lines, body) in enumerate(behind):
            self.emit(f"LBL[{label}]")
            self.lines.extend(lines)
            if i < len(behind) - 1 and not leaves(body):
                self.emit(f"JMP LBL[{end}]")
                used = True
        if used or behind:
            self.emit(f"LBL[{end}]")
        self.active_uf = self.active_ut = None  # a branch, or the CALL made on a SELECT line, may select others
        self.merge(line, *ends, what="TEST")

    def _case_value(self, expr: n.Expr) -> str:
        """A CASE value as a SELECT line writes it: a constant, `(-1)`, `.5` (as ROBOGUIDE stores them)."""
        if isinstance(expr, n.String):
            raise Untranslatable("TEST on a string: TP SELECT compares a register with numbers", Blocker.CONDITION)
        if isinstance(expr, n.Name) and (number := self.interrupt_value(expr)) is not None:
            return number  # CASE iStop: the interrupt's number
        try:
            return decimal(operand(register_value(self.c.evaluator.constant_number(expr))))
        except Unresolvable as exc:
            raise Untranslatable(f"CASE value '{format_expr(expr)}' is not known at conversion time: TP SELECT "
                                 "compares with constants", Blocker.VALUE) from exc  # fmt: skip

    def _constant_test(self, test: n.Test, subject: float, values: list[list[str]]) -> None:
        """TEST on a constant: code switched by hand, like IF FALSE. The branch it takes, without a SELECT."""
        line = test.span.line
        for case, case_values in zip(test.cases, values, strict=True):
            if any(float(v.strip("()")) == subject for v in case_values):
                self.emit(f"!l.{line} TEST {fmt_number(subject)}: one CASE")
                self.block(case.body)
                return
        self.emit(f"!l.{line} TEST {fmt_number(subject)}: " + ("DEFAULT" if test.default is not None else "no CASE"))
        self.block(test.default or ())

    # -- conditions (TP mixed logic) --------------------------------------------------

    def simplify(self, expr: n.Expr) -> n.Expr:
        """The condition with the backup's bool functions written as their test (crossarm.convert.inline).

        When a function was, a remark keeps the RAPID text: `IF (DI[5]=OFF)` alone would not say why.
        """
        calls = sum(self.c.result.inlined.values())
        simpler = self.c.inliner.simplify(expr)
        if sum(self.c.result.inlined.values()) > calls:
            self.emit(("!" + ascii_text(format_expr(expr))[:REMARK_MAX]).rstrip())
        return simpler

    def condition(self, expr: n.Expr, negate: bool = False) -> str:
        """RAPID boolean expression -> TP mixed-logic condition, without outer parentheses.

        Negation is pushed down (De Morgan, inverted comparisons) so the output
        never needs the '!' operator.
        """
        match expr:
            case n.UnaryOp(op="NOT", operand=operand):
                return self.condition(operand, not negate)
            case n.BinaryOp(op="AND" | "OR", left=left, right=right):
                op = expr.op if not negate else ("OR" if expr.op == "AND" else "AND")
                parts = []
                for side in (left, right):
                    text = self.condition(side, negate)
                    inner = side
                    while isinstance(inner, n.UnaryOp) and inner.op == "NOT":  # NOT (b OR c) is still an OR
                        inner = inner.operand
                    if isinstance(inner, n.BinaryOp) and inner.op in ("AND", "OR"):
                        text = f"({text})"
                    parts.append(text)
                return f"{parts[0]} {op} {parts[1]}"
            case n.BinaryOp(op=op, left=left, right=right) if op in _NEGATED:
                op = _NEGATED[op] if negate else op
                signal = self.c.signal(left, self.name, expr.span.line)
                if signal is not None:
                    if op not in ("=", "<>"):
                        raise Untranslatable(f"signal compared with '{op}'", Blocker.SIGNAL)
                    state = self.on_off(right)
                    if op == "<>":
                        state = "OFF" if state == "ON" else "ON"
                    return f"{signal}={state}"
                return f"{decimal(self.single(left, 1))}{op}{decimal(self.single(right, 2))}"  # (-2.5): operand()
            case n.Name(name=name) if self.args and self.args.kind(name) in ("bool", "switch"):
                return f"{self.args.register(name)}={0 if negate else 1}"
            case n.Component() if (field := self.component(expr)) and self.args.kind(field) == "bool":  # type: ignore[union-attr]
                return f"{self.args.register(field)}={0 if negate else 1}"  # type: ignore[union-attr]
            case n.FuncCall(name=fn, args=(n.Arg(value=n.Name(name=name), name=None),)) if (
                fn.upper() == "PRESENT" and self.args and self.args.kind(name) == "switch"
            ):
                return f"{self.args.register(name)}={0 if negate else 1}"
            case n.Name(name=name) if self.c.symbols.type_of(name) == "bool":
                return f"{self.c.flag(name)}={'OFF' if negate else 'ON'}"
            case n.Index() if (element := self.flag_element(expr)) is not None:
                return f"{element}={'OFF' if negate else 'ON'}"
            case n.Component() if (found := self.c.records.field(expr)) is not None and found.type == "bool" \
                    and not found.indexed and self.c.records.changed(found):  # fmt: skip
                return f"{self.c.field_number(found, True, self.record_owner(found))}={'OFF' if negate else 'ON'}"
            case n.Name() | n.FuncCall():
                signal = self.c.signal(expr, self.name, expr.span.line)
                if signal is not None:
                    return f"{signal}={'OFF' if negate else 'ON'}"
                if isinstance(expr, n.Name) and self.absent(expr.name):  # IF bReady ...: declared nowhere
                    raise self.not_in_backup(expr.name, "data")
        raise Untranslatable(f"condition not convertible: {format_expr(expr)}", Blocker.CONDITION)


def _as_assignment(call: n.ProcCall, name: str, positional: list[n.Expr]) -> n.Assign:
    """Incr n -> n:=n+1, Decr n -> n:=n-1, Add n,v -> n:=n+v, Clear n -> n:=0."""
    target, span = positional[0], call.span
    one = n.Number(span, 1, "1")
    value = {"INCR": n.BinaryOp(span, "+", target, one), "DECR": n.BinaryOp(span, "-", target, one),
             "ADD": n.BinaryOp(span, "+", target, positional[-1]), "CLEAR": n.Number(span, 0, "0")}[name]  # fmt: skip
    return n.Assign(span, target, value)


def _consecutive(free: list[int], count: int) -> list[int]:
    """The highest run of `count` consecutive numbers in `free` (listed from the top down), lowest first; [] if none."""
    numbers = set(free)
    for top in free:
        run = list(range(top - count + 1, top + 1))
        if all(k in numbers for k in run):
            return run
    return []


def _max_time_wait(stmt: n.Stmt) -> bool:
    return (isinstance(stmt, n.ProcCall) and stmt.name.upper() in ("WAITUNTIL", "WAITDI", "WAITDO")
            and any((a.name or "").upper() == "MAXTIME" for a in stmt.args))  # fmt: skip


def _source(stmt: n.Stmt) -> str:
    """Short RAPID text of a statement, for TODO remarks and the report."""
    from crossarm.rapid.to_pseudo import _Printer

    printer = _Printer()
    printer.stmt(stmt, 0)
    return printer.lines[0].split("| ", 1)[1].strip() if printer.lines else type(stmt).__name__


def convert(
    modules: list[n.Module],
    config: ConversionConfig | None = None,
    routines: list[str] | None = None,
    sources: dict[str, str] | None = None,
    signals: dict[str, Signal] | None = None,
    program_modules: set[str] | None = None,
    shared: ControllerScope | None = None,
) -> ConversionResult:
    config = config or ConversionConfig()
    taken = (set(shared.program_names), set(shared.given_programs)) if shared is not None else None
    result = Converter(modules, config, sources, signals, shared).convert(routines, program_modules)
    if not config.karel and karel_candidates(modules, result):  # what --karel would convert: the same conversion with it
        scope = None  # numbered on its own: only its lines are compared, not its numbers
        if shared is not None and taken is not None:
            scope = ControllerScope.from_config(config, shared.existing_programs)
            scope.written = shared.written
            scope.program_names, scope.given_programs = taken  # its programs named as this task's are
        again = Converter(modules, dataclasses.replace(copy.deepcopy(config), karel=True), sources, signals, scope)
        result.karel_todo = karel_would(result, again.convert(routines, program_modules))
    return result

