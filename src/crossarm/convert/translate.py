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

import math
import re
import traceback
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from crossarm.convert.arguments import Signature, signature
from crossarm.convert.compute import (
    Computer,
    Effects,
    MeasuredAtRunTime,
    Typed,
    Unknown,
    Written,
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
from crossarm.convert.handlers import OnTimeout, leaves, on_timeout, only_passes_on
from crossarm.convert.handlers import body as handler_body
from crossarm.convert.inline import REAL_CONTROLLER, Inliner
from crossarm.convert.motion import corner
from crossarm.convert.values import Evaluator, Frame, JointTarget, RobTarget, Symbols, Unresolvable
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
from crossarm.geometry import Pose, matrix_to_quat, wpr_to_matrix
from crossarm.rapid import nodes as n
from crossarm.rapid.eio import Signal
from crossarm.rapid.to_pseudo import format_expr
from crossarm.rapid.walk import walk_statements

if TYPE_CHECKING:
    from crossarm.convert.setup import FrameSetup

REMARK_MAX = 32  # characters after '!' shown on the pendant
MESSAGE_MAX = 24  # MESSAGE[...] text length: longer texts are silently cut by the controller (ROBOGUIDE probe)
REGISTER_COMMENT_MAX = 16
WAIT_CLOCK = "WaitTimer"  # the register a wait with a MaxTime reads its TIMER into
TEST_VALUE = "TestValue"  # the register a TEST on anything but a register is selected on
SELECT_INDENT = " " * len("SELECT ")  # a SELECT's next lines, as the controller stores them (ROBOGUIDE)
NO_LOAD_KG = 0.001  # RAPID's load0 / tool0 placeholder mass: no real payload declared

_NEGATED = {"=": "<>", "<>": "=", "<": ">=", ">=": "<", ">": "<=", "<=": ">"}
_ARITHMETIC = {"+", "-", "*", "/", "DIV", "MOD"}
_SIGNAL_PREFIX = re.compile(r"^[dD][iIoO](?=[_0-9A-Z])")


class Blocker:
    """What an integrator has to solve, rather than the individual line it happened on.

    A large backup produces hundreds of TODO entries that come down to a handful of
    causes. Every TODO carries one of these so the report can group them and show
    which chunks of work are worth doing next.
    """

    CALL_ARGS = "routine call with arguments"
    MOVE_ROUTINE = "move made inside a routine of the backup"
    MOVE_ROUTINE_ASSUMED = "routine converted as the move it makes"
    SAVED_FRAME = "frame value as saved in the backup"
    RUNTIME_FRAME = "frame or tool built at run time"
    RUNTIME_POSITION = "position built at run time"
    CALIBRATION = "frame or position measured on the robot (calibration)"
    PAYLOAD = "payload changed at run time"
    STATIONARY = "stationary tool or robot-held work object"
    RECORD = "record component or array element"
    CONDITION = "condition not convertible"
    VALUE = "value not known at conversion time"
    SIGNAL = "I/O signal without a mapping"
    WAIT_TIMEOUT = "wait with a timeout"
    MESSAGE_VALUE = "TPWrite showing a value"
    MESSAGE_CUT = "TPWrite text longer than MESSAGE allows"
    CAPACITY = "more numbers used than the controller holds"
    TAKEN = "pinned number already used on the controller"
    RENAMED = "program renamed so as not to replace another"
    MOTION = "motion without a TP equivalent"
    LOOP = "loop without a TP equivalent"
    AXIS_CONVENTION = "posture converted with the measured axis conventions"
    REAL_CONTROLLER = "RobOS() taken as TRUE (real controller)"
    HANDLER = "error handler: other errors stop the program"
    OPTIONS_IGNORED = "instruction options dropped"
    MOTION_SETTING = "motion setting (ConfL, SingArea, AccSet, VelSet...)"
    INTERRUPT = "interrupt (CONNECT, ISignalDI...) and its TRAP"
    IO_ROUNDED = "I/O written approximately (pulse length)"
    INTERNAL = "CrossArm internal error"
    OTHER = "other"

    @staticmethod
    def rapid(kind: str) -> str:
        """Category for a construct the parser left out of scope: 'ERROR_HANDLER' -> 'RAPID error handler'."""
        if kind == "CONNECT":
            return Blocker.INTERRUPT
        return "RAPID " + kind.replace("_", " ").lower()


class Untranslatable(Exception):
    """This RAPID construct has no faithful TP equivalent in the current scope.

    `category` is the Blocker it belongs to; the report groups TODO entries by it.
    """

    def __init__(self, message: str, category: str = Blocker.OTHER) -> None:
        super().__init__(message)
        self.category = category


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


@dataclass(frozen=True, slots=True)
class ProgramInfo:
    program: Program
    module: str
    routine: str
    points: tuple[PointInfo, ...]


@dataclass(frozen=True, slots=True)
class Allocation:
    number: int
    rapid_name: str
    fixed: bool  # pinned by the mapping file
    detail: str = ""


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


# Statements a zoned move blends past: the next move after them is the one the corner leads into.
_BLENDED_PAST = frozenset({"SET", "RESET", "SETDO", "SETGO", "SETAO", "PULSEDO", "INVERTDO"})
# Motion settings: what FANUC does without them, or where they need a person (see motion_setting()).
_MOTION_SETTINGS = frozenset({"CONFL", "CONFJ", "SINGAREA", "CIRPATHMODE", "ACCSET", "VELSET"})
_INTERRUPTS = frozenset({"IDELETE", "ISIGNALDI", "ISIGNALDO", "ISIGNALGI", "ISIGNALGO", "ISIGNALAI", "ISIGNALAO",
                         "ITIMER", "IPERS", "IWATCH", "ISLEEP", "IENABLE", "IDISABLE", "IERROR"})
PULSE_MAX_S = 25.5  # the longest PULSE a FANUC output takes (ROBOGUIDE: 25.6 is refused, ASBN-092)
PULSE_DEFAULT_S = 0.2  # RAPID PulseDO without \PLength


def _passed_through(stmt: n.Stmt) -> bool:
    return isinstance(stmt, n.Comment) or (isinstance(stmt, n.ProcCall) and stmt.name.upper() in _BLENDED_PAST)


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
    digital_outputs: list[Allocation] = field(default_factory=list)
    digital_inputs: list[Allocation] = field(default_factory=list)
    group_outputs: list[Allocation] = field(default_factory=list)
    group_inputs: list[Allocation] = field(default_factory=list)
    analog_outputs: list[Allocation] = field(default_factory=list)
    timers: list[Allocation] = field(default_factory=list)  # RAPID clocks
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
    skipping the numbers already used on the controller (`reserved`)."""

    def __init__(self, fixed: dict[str, int], first: int, reserved: Iterable[int] = ()) -> None:
        self.fixed = fixed
        self.first = first
        self.reserved = frozenset(reserved)
        self.skip: set[int] = set()  # taken by CrossArm for its own use (the TIMER timing the waits)
        self.assigned: dict[str, Allocation] = {}

    def number(self, name: str, key: str | None = None, detail: str = "") -> int:
        key = (key or name).upper()
        if key in self.assigned:
            return self.assigned[key].number
        if key in self.fixed:
            number, fixed = self.fixed[key], True
        else:
            used = set(self.fixed.values()) | {a.number for a in self.assigned.values()} | self.reserved | self.skip
            number, fixed = self.first, False
            while number in used:
                number += 1
        self.assigned[key] = Allocation(number, name, fixed, detail)
        return number

    def allocations(self) -> list[Allocation]:
        return sorted(self.assigned.values(), key=lambda a: a.number)


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

    def number(self, name: str, key: str | None = None, detail: str = "") -> int:
        self.keys.add((key or name).upper())
        return self.table.number(name, key, detail)

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
    # What the programs of every task can change: a PERS is shared by all tasks (crossarm.convert.compute).
    # None: only the task being converted is known.
    written: Written | None = None

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
        )


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def ascii_text(text: str) -> str:
    """TP files are ASCII: strip accents, replace anything else."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return folded.replace('"', "'").replace(";", ",")


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


def operand(text: str) -> str:
    """A negative constant in parentheses, as the controller writes it in an assignment, a calculation or
    a CALL argument: `R[1]=(-2.5)`, `CALL P((-2.5))`. ROBOGUIDE refuses `CALL P(-2.5)`, and rewrites
    `R[1]=-2.5` with the parentheses. Conditions keep the bare form: it writes `IF (R[1]<-2.5)`."""
    return f"({text})" if text.startswith("-") else text


def decimal(text: str) -> str:
    """A constant below 1 as the controller stores it in a CALL argument or a condition: `.5`, `(-.5)`,
    not `0.5` (ROBOGUIDE, argument and wait probes). Anything else is returned as it is."""
    return re.sub(r"^(\(?-?)0\.", r"\1.", text)


def fmt_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


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
        self.effects = Effects(modules)
        # Frames computed at conversion time: value key -> uses; each use is (kind, RAPID data, program, line,
        # statement), and a program line loading it reads `PR[{CF:use}]` until its register is known (convert()).
        self.computed: dict[str, list[int]] = {}
        self.computed_uses: list[tuple[str, str, str, int, n.Stmt, tuple[float, ...]]] = []
        self.frames_in_moves: dict[str, set[str]] = {"UF": set(), "UT": set()}  # upper-case names, _plan_slots
        self.registers = TableView(shared.registers)
        self.flags = TableView(shared.flags)
        self.douts = TableView(shared.douts)
        self.dins = TableView(shared.dins)
        self.gouts = TableView(shared.gouts)
        self.gins = TableView(shared.gins)
        self.aouts = TableView(shared.aouts)
        self.timers = TableView(shared.timers)
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
        self._warned: set[str] = set()
        self.do_names, self.di_names = self._signals_by_usage()
        self.program_names: dict[str, str] = {}  # routine (upper) -> TP name, set by convert()
        self.move_routines = find_move_routines(modules)
        # PROCs with parameters: their AR[n] layout, or why they cannot be converted.
        self.signatures: dict[str, Signature | str] = {
            r.name.upper(): signature(r) for m in modules for r in m.routines if r.kind == "PROC" and r.params
        }
        self.move_routine_calls: Counter[str] = Counter()
        self.not_converted: set[int] = set()  # id() of the statements that ended up in a TODO, for coverage
        self.parameters: set[str] = set()  # of the routine being translated (upper case)
        self.inliner = Inliner(modules, self._const_bool, self._inlined,
                               lambda name: self.symbols.is_local(name) or name.upper() in self.parameters)  # fmt: skip

    # -- entry point -------------------------------------------------------

    def convert(self, routines: list[str] | None = None, program_modules: set[str] | None = None) -> ConversionResult:
        """`program_modules` (upper-case names): only their routines become programs, the other
        modules are data. Default: every module without the SYSMODULE attribute."""
        wanted = {r.upper() for r in routines} if routines else None
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
                reason = self._skip_reason(routine, self.signatures.get(routine.name.upper()))
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
        for module, routine in selected:
            translator = _RoutineTranslator(self, module, routine, self.program_names[routine.name.upper()])
            self.result.programs.append(translator.run())
        if wanted:
            found = {info.routine.upper() for info in self.result.programs}
            found |= {r.upper() for _, r, _ in self.result.skipped_routines}
            for missing in sorted(wanted - found):
                self.note("", None, "TODO", f"routine '{missing}' not found in the given modules")

        self._controller_comments()
        self._place_computed()
        res = self.result
        res.registers = self.registers.allocations()
        res.flags = self.flags.allocations()
        res.digital_outputs = self.douts.allocations()
        res.digital_inputs = self.dins.allocations()
        res.group_outputs = self.gouts.allocations()
        res.group_inputs = self.gins.allocations()
        res.analog_outputs = self.aouts.allocations()
        res.timers = self.timers.allocations()
        res.uframes = sorted((f for (k, _), f in self.frames.items() if k == "UF"), key=lambda f: f.number)
        res.utools = sorted((f for (k, _), f in self.frames.items() if k == "UT"), key=lambda f: f.number)
        self._check_capacity()
        self._report_move_routines()
        declared = {r.name.upper() for m in self.modules for r in m.routines}
        # A routine wrapping a move is counted where it is called, as a FUNC is: not as a routine left out.
        left_out = [r for r in skipped if r.name.upper() not in self.move_routines]
        res.coverage = measure([r for _, r in selected], left_out, self.not_converted, declared, set(self.move_routines))
        return res

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
                for kind, expr in (("UF", wobj), ("UT", move.tool)):
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
            if len(automatic) > len(free) and free and self._banks:  # no register to keep them in: over, as before
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
                if key in done or key not in by_name or key in self.move_routines:
                    continue  # a move routine's calls are written as its move, not as a CALL
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
            ("TIMER", self.timers),
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
        if not banks and not computed:
            return
        numbers = set(self.config.free_position_registers()[0][:1]) | set(banks)
        numbers |= {f.number for f in computed if f.number is not None}
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

    @staticmethod
    def _skip_reason(routine: n.Routine, layout: "Signature | str | None") -> str:
        if routine.kind != "PROC":
            return f"{routine.kind} routines have no TP program equivalent"
        if isinstance(layout, str):
            return f"parameters not converted: {layout}"
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

        def unique(base: str, taken: set[str]) -> str:
            candidate, suffix = base, 1
            while candidate in taken:
                suffix += 1
                candidate = f"{base[: max_len - len(str(suffix)) - 1]}_{suffix}"
            return candidate

        for routine in converted:
            key = routine.name.upper()
            if key in names:
                continue
            base = tp_program_name(routine.name, max_len)
            name = unique(base, claimed | mine)
            if name != base:
                if base in mine:
                    why = "another routine of this task has the same name once shortened"
                elif base in self.shared.existing_programs:
                    why = f"the FANUC robot already has a program {base}, which loading it would replace"
                else:
                    why = f"another task of this backup already writes {base}.LS"
                self.note(name, None, "WARNING", f"routine {routine.name} written as {name}.LS: {why}",
                          Blocker.RENAMED)  # fmt: skip
            mine.add(name)
            claimed.add(name)
            names[key] = name
        for module in self.modules:  # not written: only called by name
            for routine in module.routines:
                key = routine.name.upper()
                if key not in names:
                    names[key] = unique(tp_program_name(routine.name, max_len), mine)
                    mine.add(names[key])
        return names

    def _signals_by_usage(self) -> tuple[set[str], set[str]]:
        """Signal names whose direction is known from the instructions using them."""
        outputs: set[str] = set()
        inputs: set[str] = set()
        for module in self.modules:
            for routine in module.routines:
                for stmt in walk_statements(routine.body):
                    if isinstance(stmt, n.SetSignal) and isinstance(stmt.signal, n.Name):
                        outputs.add(stmt.signal.name.upper())
                    elif isinstance(stmt, n.ProcCall) and stmt.args and isinstance(stmt.args[0].value, n.Name):
                        name = stmt.args[0].value.name.upper()
                        if stmt.name.upper() in ("SETDO", "PULSEDO", "WAITDO"):
                            outputs.add(name)
                        elif stmt.name.upper() == "WAITDI":
                            inputs.add(name)
        return outputs, inputs

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
        if isinstance(expr, n.FuncCall) and expr.name.upper() in ("DINPUT", "DOUTPUT") and len(expr.args) == 1:
            arg = expr.args[0].value
            if isinstance(arg, n.Name):
                table, prefix = (self.dins, "DI") if expr.name.upper() == "DINPUT" else (self.douts, "DO")
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


class _RoutineTranslator:
    def __init__(self, conv: Converter, module: n.Module, routine: n.Routine, tp_name: str) -> None:
        self.c = conv
        self.module = module
        self.routine = routine
        self.name = tp_name
        self.lines: list[Instruction | Motion] = []
        self.positions: list[Position] = []
        self.points: list[PointInfo] = []
        self._point_keys: dict[tuple, int] = {}
        self.active_uf: tuple[int, int | None] | None = None  # (number, PR it was loaded from)
        self.active_ut: tuple[int, int | None] | None = None
        self.loop_vars: dict[str, str] = {}  # RAPID FOR variable -> register text
        layout = conv.signatures.get(routine.name.upper())
        self.args: Signature | None = layout if isinstance(layout, Signature) else None  # its parameters: AR[n]
        self.copies: dict[str, str] = {}  # parameters it changes: upper name -> register holding the copy
        self._on_timeout: OnTimeout | None | bool = False  # what its ERROR handler does when a wait times out
        self.timed_waits = 0  # waits with \MaxTime written with the handler's timeout path
        self.error_jumps: tuple[int, int] | None = None  # (RETRY, TRYNEXT) labels while writing that path
        self.strict = 0  # >0: a statement that cannot be converted fails the enclosing one instead of a TODO
        self.next_speed: n.Expr | None = None  # the speed of the move after the one being written, if a move
        self.next_label = 1
        # What the routine's data holds at the statement being written (crossarm.convert.compute): upper-case
        # name -> Typed, or Unknown (and why) when it depends on the run. Its own data from its declaration on,
        # module data once the routine sets it. Anything else is read as declared, if nothing changes it.
        self.known: dict[str, Typed | Unknown] = {}
        self.local_names: set[str] = set()

    def run(self) -> ProgramInfo:
        self.c.symbols.enter_routine(self.routine)
        read = parameters(self.routine.params)
        self.c.parameters = set(read[0]) | read[1] if read else set()
        self.c.computer.scope, self.c.evaluator.known = self.scope, self.known_value
        try:
            return self._run()
        finally:
            self.c.computer.scope, self.c.evaluator.known = (lambda name: None), None

    def _run(self) -> ProgramInfo:
        for text in remark_lines(f"RAPID {self.module.name}.{self.routine.name}"):
            self.emit(text)
        for slot in self.args.slots if self.args else ():
            if slot.key in self.args.copied:  # type: ignore[union-attr]
                register = self.c.written_register(slot.name, key=f"{self.name}.{slot.name}")
                self.copies[slot.key] = register
                self.emit(f"{register}={self.args.register(slot.key)}")  # type: ignore[union-attr]
        self.block(self.routine.body)
        for handler in self.routine.handlers:
            self.handler(handler)
        attrs = Attributes(comment=ascii_text(self.routine.name)[:16], created=self.c.config.timestamp)
        program = Program(self.name, self.lines, self.positions, attrs)
        return ProgramInfo(program, self.module.name, self.routine.name, tuple(self.points))

    # -- output helpers --------------------------------------------------------

    # -- data known at this point ---------------------------------------------------

    def scope(self, name: str) -> Typed | Unknown | None:
        """For crossarm.convert.compute: the routine's own value of a data, Unknown, or None (read it as declared)."""
        key = name.upper()
        if key in self.known:
            return self.known[key]
        if key in self.loop_vars:
            return Unknown("is a FOR loop counter")
        if key in self.c.parameters:
            raise Unresolvable(f"'{name}' is a parameter of the routine: its value comes from the caller")
        return None

    def known_value(self, name: str):
        """For the Evaluator: the value of a data this routine set, None if it did not."""
        found = self.known.get(name.upper())
        if isinstance(found, Unknown):
            raise found.error(name)
        return found.value if isinstance(found, Typed) else None

    def forget(self, stmts: Iterable[n.Stmt], why: Unknown) -> None:
        """What these statements may change is no longer known: they ran, or might have."""
        names, anything = self.c.effects.of(stmts)
        for name in names:
            self.known[name] = why
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
        self.forget((stmt,), Unknown(f"is {'measured on the robot' if measured else 'set'} at l.{line} (left TODO)", measured))
        if isinstance(stmt, n.Unsupported) and stmt.kind == "LABEL":  # jumped to from anywhere: nothing is known
            self.known = dict.fromkeys(self.known, Unknown(f"may hold anything at the label at l.{line}"))

    def rapid_text(self, stmt: n.Stmt) -> str:
        """The RAPID source line of a statement (comment stripped), or a re-print of it."""
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
            following = next((s for s in stmts[i + 1 :] if not _passed_through(s)), None)
            self.next_speed = following.speed if isinstance(stmt, n.Move) and isinstance(following, n.Move) else None
            if self.strict:
                self.stmt(stmt)
                continue
            checkpoint = (len(self.lines), len(self.positions), len(self.points), self.active_uf, self.active_ut)
            try:
                self.stmt(stmt)
            except (Untranslatable, Unresolvable) as exc:
                self._rollback(checkpoint)
                # An Unresolvable that reaches here is always a value we could not work out.
                measured = Blocker.CALIBRATION if isinstance(exc, MeasuredAtRunTime) else Blocker.VALUE
                self.todo(stmt, str(exc), getattr(exc, "category", measured))
            except Exception as exc:  # noqa: BLE001 - one statement must never cost the whole backup
                # A bug in CrossArm on an unusual statement. Without this, the exception would end
                # the whole task: a hundred programs lost for one line. It becomes a TODO that
                # says where, so it can be reported, and the conversion goes on.
                self._rollback(checkpoint)
                where = traceback.extract_tb(exc.__traceback__)[-1]
                self.todo(stmt, f"CrossArm internal error, please report it: {type(exc).__name__}: {exc} "
                                f"(at {Path(where.filename).name}:{where.lineno})", Blocker.INTERNAL)  # fmt: skip

    def _rollback(self, checkpoint: tuple) -> None:
        """Drop what a statement emitted before failing: its lines, the P[n] it created, the frames it selected."""
        lines, positions, points, self.active_uf, self.active_ut = checkpoint
        del self.lines[lines:]
        del self.positions[positions:]
        del self.points[points:]
        self._point_keys = {k: v for k, v in self._point_keys.items() if v <= positions}

    def stmt(self, s: n.Stmt) -> None:
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
                value = self.numeric(seconds)
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
                self.emit("END")
            case n.Exit():
                self.emit("ABORT")
            case n.Unsupported(kind="RETRY") if self.error_jumps:
                self.emit(f"JMP LBL[{self.error_jumps[0]}]")
            case n.Unsupported(kind="TRYNEXT") if self.error_jumps:
                self.emit(f"JMP LBL[{self.error_jumps[1]}]")
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
        if decl.init is None or decl.dims:
            return
        if decl.type_name.lower() == "num":
            self.emit(f"{self.c.written_register(decl.name)}={operand(self.numeric(decl.init))}")
        elif decl.type_name.lower() == "bool" and isinstance(decl.init, n.Bool):
            self.emit(f"{self.c.flag(decl.name)}=({'ON' if decl.init.value else 'OFF'})")

    # -- motion -------------------------------------------------------------------

    def move(self, m: n.Move) -> None:
        line = m.span.line
        # Resolve everything first: a failure must not leave a half-created point behind.
        if m.kind is n.MoveKind.ABSJ:
            held = m.wobj is not None and self._stationary("UF", m.wobj)
            # Numbered as before this move was converted: the work object, then the tool unless the work object stopped it.
            uf, ut = self.joint_frame("UF", m.wobj, line), self.joint_frame("UT", m.tool, line, number=not held)
        else:
            uf = self.c.selection("UF", self.c.frame_number("UF", m.wobj, self.name, line))
            ut = self.c.selection("UT", self.c.frame_number("UT", m.tool, self.name, line))
        motion = "J" if m.kind in (n.MoveKind.J, n.MoveKind.ABSJ) else m.kind.value
        evaluator = self.c.evaluator
        to_value = evaluator.jointtarget(m.to_point) if m.kind is n.MoveKind.ABSJ else evaluator.robtarget(m.to_point)
        via_value = evaluator.robtarget(m.via_point) if m.via_point is not None else None
        if isinstance(to_value, JointTarget) and len(to_value.joints) < 6:
            raise Untranslatable(f"jointtarget with {len(to_value.joints)} axes", Blocker.MOTION)
        speed, rapid_speed, fanuc_speed = self.speed(m.speed, motion)
        termination = self.termination(m.zone, m.speed, motion, rapid_speed, fanuc_speed, self.next_speed)
        ignored = [a.name for a in m.options if a.name and a.name.upper() != "NOEOFFS"]
        if ignored:
            self.warn(m, f"motion options ignored: {', '.join(ignored)}", Blocker.OPTIONS_IGNORED)

        via = self.point(m.via_point, via_value, uf, ut, line) if via_value is not None else None
        target = self.point(m.to_point, to_value, uf, ut, line)
        for selected, active, kind in ((uf, self.active_uf, "UFRAME"), (ut, self.active_ut, "UTOOL")):
            if selected != active:
                number, bank = selected
                if bank is not None:  # above what the controller holds: loaded into the reserved number
                    self.emit(f"{kind}[{number}]=PR[{bank}]")
                self.emit(f"{kind}_NUM={number}")
        self.active_uf, self.active_ut = uf, ut
        self.lines.append(Motion(motion, target, speed, termination, via))

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
        self.points.append(PointInfo(number, source, line, uf, ut, tp_value))
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
            positive = self.condition(test)
            self.wait(f"WAIT ({positive})", positive, self.condition(test, negate=True) if limit else "", limit)
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
        elif name == "INVERTDO" and len(positional) == 1 and not options:
            signal = self.output(positional[0], call)
            self.emit(f"{signal}=(!{signal})")
        elif name == "SETAO" and len(positional) == 2 and not options:
            self.analog(call, positional[0], positional[1])
        elif name in ("CLKRESET", "CLKSTART", "CLKSTOP") and len(positional) == 1 and not options:
            self.emit(f"{self.clock(positional[0])}={name[3:]}")
        elif name in _MOTION_SETTINGS:
            self.motion_setting(call, name, positional, options)
        elif name in _INTERRUPTS:
            raise Untranslatable(f"{call.name}: interrupts have no TP equivalent (a background logic or a KAREL"
                                 " condition handler would do what the TRAP does)", Blocker.INTERRUPT)  # fmt: skip
        elif name in self.c.move_routines:
            self.routine_move(call, self.c.move_routines[name])
        elif isinstance(self.c.signatures.get(name), Signature) and name in self.c.program_names:
            self.call_with_args(call, self.c.signatures[name])  # type: ignore[arg-type]
        elif isinstance(self.c.signatures.get(name), str):
            raise Untranslatable(f"{call.name} is not converted: {self.c.signatures[name]}", Blocker.CALL_ARGS)
        elif call.args:
            raise Untranslatable(f"call to {call.name} with arguments has no mapping", Blocker.CALL_ARGS)
        elif name in self.c.program_names:
            self.emit(f"CALL {self.c.program_names[name]}")
        else:
            raise Untranslatable(f"'{call.name}' is not a routine of the converted modules (system instruction?)", Blocker.CALL_ARGS)

    # -- waits with a time limit, error handlers ------------------------------------

    def max_time(self, call: n.ProcCall, options: list[n.Arg]) -> float | None:
        """The \\MaxTime of a wait, in seconds; None without one. Any other option is not converted."""
        if not options:
            return None
        if len(options) != 1 or (options[0].name or "").upper() != "MAXTIME" or options[0].value is None:
            raise Untranslatable(f"{call.name} with {options[0].name} is not converted", Blocker.WAIT_TIMEOUT)
        if self.on_timeout() is None:
            raise Untranslatable(f"{call.name} with MaxTime: this routine's ERROR handler does not say what to do when"
                                 " the time runs out (the error goes to the caller)", Blocker.WAIT_TIMEOUT)  # fmt: skip
        try:
            return self.c.evaluator.constant_number(options[0].value)
        except Unresolvable as exc:
            raise Untranslatable(f"MaxTime must be a constant: {exc}", Blocker.WAIT_TIMEOUT) from exc

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
        path = self.on_timeout()
        assert isinstance(path, OnTimeout)  # max_time() checked it
        timer, clock = self.c.wait_clock()
        steps = [s for s in path.steps if not isinstance(s, n.Comment)]
        next_only = len(steps) == 1 and isinstance(steps[0], n.Unsupported) and steps[0].kind == "TRYNEXT"
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
        self.todo(handler, handler.reason, Blocker.rapid(handler.kind))

    def call_with_args(self, call: n.ProcCall, layout: Signature) -> None:
        """CALL NAME(a,b,...): required arguments in order, then 1 / 0 for every optional switch."""
        positional = [a for a in call.args if a.name is None]
        required = [s for s in layout.slots if s.kind != "switch"]
        if len(positional) != len(required):
            raise Untranslatable(f"{len(positional)} arguments given, {call.name} takes {len(required)}", Blocker.CALL_ARGS)
        given = {a.name.upper(): a for a in call.args if a.name is not None}
        unknown = set(given) - {s.key for s in layout.slots if s.kind == "switch"}
        if unknown:
            raise Untranslatable(f"{call.name} has no switch \\{min(unknown)}", Blocker.CALL_ARGS)
        values = [self.argument(a.value, slot) for a, slot in zip(positional, required, strict=True)]
        for slot in layout.slots[len(required):]:
            arg = given.get(slot.key)
            if arg is None:
                values.append("0")
            elif arg.conditional:  # \Check?Check: passed on only when this routine was given it
                forwarded = self.args.register(arg.value.name) if self.args and isinstance(arg.value, n.Name) else None
                if forwarded is None:
                    raise Untranslatable(f"\\{arg.name}?... does not name a switch of this routine", Blocker.CALL_ARGS)
                values.append(forwarded)
            else:
                values.append("1")
        self.emit(f"CALL {self.c.program_names[call.name.upper()]}({','.join(values)})")

    def argument(self, expr: n.Expr | None, slot) -> str:
        """One TP CALL argument: a constant, a register, or this routine's own AR[n]."""
        if expr is None:
            raise Untranslatable(f"argument {slot.name} is missing", Blocker.CALL_ARGS)
        if isinstance(expr, n.Name) and self.args and self.args.register(expr.name):
            return self.args.register(expr.name)  # type: ignore[return-value]
        if slot.kind == "bool":
            if isinstance(expr, n.Bool):
                return "1" if expr.value else "0"
            decl = self.c.symbols.get(expr.name) if isinstance(expr, n.Name) else None
            if decl is not None and decl.storage == "CONST" and isinstance(decl.init, n.Bool):
                return "1" if decl.init.value else "0"
            raise Untranslatable(f"argument {slot.name}: '{format_expr(expr)}' must be TRUE, FALSE or a bool "
                                 "argument (a flag cannot be passed)", Blocker.CALL_ARGS)  # fmt: skip
        try:
            text = operand(self.numeric(expr))
        except Untranslatable as exc:
            raise Untranslatable(f"argument {slot.name}: {exc}", Blocker.CALL_ARGS) from exc
        return decimal(text)  # CALL P(.5), not CALL P(0.5)

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
            self.emit(f"{target}={operand(fmt_number(round(counts)))}")
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
        path = path_of(a.target)
        root_type = self.c.symbols.type_of(path[0]) if path else None
        if root_type in _FRAME_TYPES | _POSITION_TYPES and path and path[0] not in self.copies:
            self.computed(a, root_type)
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
        if type_name == "num":
            self.emit(f"{self.c.written_register(a.target.name)}={self.arithmetic(a.value)}")
        elif type_name == "bool" and isinstance(a.value, n.Bool):
            self.emit(f"{self.c.flag(a.target.name)}=({'ON' if a.value.value else 'OFF'})")
        else:
            raise Untranslatable(f"assignment of {type_name or 'undeclared data'} '{a.target.name}'",
                                 _type_blocker(type_name))  # fmt: skip
        try:  # a register keeps its value for the computations that read it further on
            name, value = self.c.computer.assigned(a)
            self.known[name] = value
        except Unresolvable:
            self.known[a.target.name.upper()] = Unknown(f"is set at l.{a.span.line} from a value only known at run time")

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
        try:
            root, new = self.c.computer.assigned(a)
        except MeasuredAtRunTime as exc:
            raise Untranslatable(
                f"{what} measured on the robot when the program runs (a calibration): {exc}. TP reads the position"
                " (PR[n]=LPOS) but cannot compute a frame from it (no pose product, inverse or angle function):"
                " set this frame with the FANUC frame setup, or in KAREL", Blocker.CALIBRATION,
            ) from exc  # fmt: skip
        except Unresolvable as exc:
            raise Untranslatable(f"{what} computed from data only known at run time: {exc}", category) from exc
        line = a.span.line
        remark = ("!" + ascii_text(f"l.{line} {self.rapid_text(a).rstrip(';')}")[:REMARK_MAX]).rstrip()
        if is_frame:
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
                return
        self.emit(remark)
        self.known[root] = new

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
        """Right-hand side of R[n]=...: a value or ONE arithmetic operation, as TP allows."""
        try:
            return operand(fmt_number(self.c.evaluator.constant_number(expr)))
        except Unresolvable:
            pass
        if isinstance(expr, n.BinaryOp) and expr.op in _ARITHMETIC:
            left, right = operand(self.numeric(expr.left)), operand(self.numeric(expr.right))
            op = f" {expr.op} " if expr.op in ("DIV", "MOD") else expr.op
            return f"{left}{op}{right}"
        return operand(self.numeric(expr))

    def numeric(self, expr: n.Expr) -> str:
        """A single TP numeric operand: a constant (CONST or literal), a register or a group input."""
        if isinstance(expr, n.FuncCall) and expr.name.upper() == "GINPUT" and len(expr.args) == 1 and expr.args[0].value:
            return self.group(expr.args[0].value, "GI", expr.span.line)
        if isinstance(expr, n.FuncCall) and expr.name.upper() == "CLKREAD" and expr.args and expr.args[0].value:
            if any(a.name is not None and a.name.upper() != "HIGHRES" for a in expr.args[1:]):
                raise Untranslatable(f"{format_expr(expr)}: only \\HighRes is converted", Blocker.OPTIONS_IGNORED)
            return self.clock(expr.args[0].value)  # seconds, as ClkRead (wait probe: 1.000000 after 1 s)
        if isinstance(expr, n.Name):
            key = expr.name.upper()
            if key in self.loop_vars:
                return self.loop_vars[key]
            if key in self.copies:
                return self.copies[key]
            if self.args and self.args.kind(key) == "num":
                return self.args.register(key)  # type: ignore[return-value]
            decl = self.c.symbols.get(expr.name)
            if decl is not None and decl.type_name.lower() == "num" and decl.storage != "CONST":
                return self.c.register(expr.name)
            # A group input read by its name, as RAPID allows: IF giCode>0 is IF GInput(giCode)>0.
            eio = self.c.eio.get(key)
            if decl is None and (key in self.c.config.group_inputs or (eio is not None and eio.signal_type == "GI")):
                return self.group(expr, "GI", expr.span.line)
        try:
            return fmt_number(self.c.evaluator.constant_number(expr))
        except Unresolvable as exc:
            raise Untranslatable(f"'{format_expr(expr)}' is not a simple numeric value ({exc})", Blocker.VALUE) from exc

    # -- control flow -----------------------------------------------------------------

    def if_stmt(self, branches: tuple[n.IfBranch, ...], else_body: tuple[n.Stmt, ...]) -> None:
        """IF/ELSEIF/ELSE. A branch on a constant is code switched on or off by hand (`IF FALSE THEN`):
        what never runs is left out with a remark, what always runs is converted without a test."""
        live: list[n.IfBranch] = []
        for branch in branches:
            written = branch.condition
            test = self.simplify(written)
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
        if live:
            self._if_chain(tuple(live), else_body)
        else:
            self.block(else_body)

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
        loop = n.While(loop.span, self.simplify(loop.condition), loop.body)
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
        try:
            return decimal(operand(fmt_number(self.c.evaluator.constant_number(expr))))
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
                return f"{decimal(self.numeric(left))}{op}{decimal(self.numeric(right))}"
            case n.Name(name=name) if self.args and self.args.kind(name) in ("bool", "switch"):
                return f"{self.args.register(name)}={0 if negate else 1}"
            case n.FuncCall(name=fn, args=(n.Arg(value=n.Name(name=name), name=None),)) if (
                fn.upper() == "PRESENT" and self.args and self.args.kind(name) == "switch"
            ):
                return f"{self.args.register(name)}={0 if negate else 1}"
            case n.Name(name=name) if self.c.symbols.type_of(name) == "bool":
                return f"{self.c.flag(name)}={'OFF' if negate else 'ON'}"
            case n.Name() | n.FuncCall():
                signal = self.c.signal(expr, self.name, expr.span.line)
                if signal is not None:
                    return f"{signal}={'OFF' if negate else 'ON'}"
        raise Untranslatable(f"condition not convertible: {format_expr(expr)}", Blocker.CONDITION)


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
    return Converter(modules, config, sources, signals, shared).convert(routines, program_modules)
