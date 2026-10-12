# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""`crossarm anonymize`: a copy of a backup that can be shared, holding only what CrossArm reads, renamed and purged.

    crossarm anonymize BACKUP|FILES [-o FILE.zip] [--seed N] [--keep-geometry] [--scramble-tools]
                       [--write-mapping FILE]

The zip converts as the backup does (same programs, TODO by cause, points, same diagnostic: tests/test_anonymize.py
checks it on every backup at hand), but none of the backup's names, texts or comments is in it. This module is the
ONLY place deciding what an anonymized backup holds:

    - what CrossArm reads, nothing else: the RAPID modules (a backup keeps its RAPID/TASKn/PROGMOD|SYSMOD layout),
      SYSPAR/EIO.cfg reduced to each signal's name, type and device and to the sections' records (renamed), and
      BACKINFO/backinfo.txt reduced to the task names (renamed), the RobotWare version, the ABB options (with their
      code) and the robot models. HOME, License, system.xml, *.bin, dates, paths, the system's name and serial
      number: left out. Each file in the zip has a fixed date and the entries are sorted;
    - every name of the backup renamed the same way everywhere (case does not matter in RAPID): MOD_1, PROC_12,
      FUNC_3, TRAP_2, REC_1, FIELD_4, PARAM_2, TOOL_3, WOBJ_1, PT_17, JT_2, NUM_5, DO_5, DI_2, GO_1, TASK_1, EXT_3
      (a name the backup uses without declaring it)... A name keeps what a rule of CrossArm reads in it: a signal
      name starting with di/do keeps that start, an ERR_ name keeps ERR_;
    - never renamed: RAPID's reserved words, its own instructions, functions, data types, predefined data (tool0,
      wobj0, load0, v1000, z50, fine...), constants and error numbers (NATIVE_NAMES), the components of RAPID's own
      data types after a dot (.trans, .uframe...), and the optional arguments of RAPID's own instructions
      (\\WObj, \\Conc...): they are RAPID's vocabulary, not the cell's;
    - comments removed (one holding semicolons keeps them alone, `!;;`: coverage.weight counts an error handler's
      instructions by its semicolons); each text replaced by a code of the same length (SA_____), keeping its
      apostrophes, semicolons and whether it has a character TP texts lack: a text equal to a name of the
      backup becomes that name's new name, a text starting the name of routines called by their name built at run
      time (`CallByVar "Station_", n`, `%"Station_" + NumToStr(n, 0)%`) is renamed with those routines; a text with no
      letter and at most one digit (",", " ", "1") is kept;
    - positions moved (unless --keep-geometry): each robtarget by a random offset of its frame (the work object
      its moves name, wobj0 otherwise: the same offset for every point of a frame, orientations kept), each work
      object's user frame by the offset of wobj0; tools kept unless --scramble-tools. A pose at 0,0,0 is kept.
      Joint positions (jointtarget, MoveAbsJ) and positions written in an instruction rather than declared are not
      moved: see LIMIT. Every other number is kept (speeds, zones,
      offsets, counters: the conversion depends on them);
    - anonymize_report.md in the zip: counts only. The table of correspondence (original -> new) is written only
      with --write-mapping, to a file of its own, never in the zip. The offsets are random; --seed N makes them
      repeatable (same input and seed: the same bytes). The seed is never written in the zip.
"""

import io
import json
import random
import re
import zipfile
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from crossarm import __version__
from crossarm.backup import open_source, task_names
from crossarm.convert.compute import PREDEFINED
from crossarm.convert.config import ConversionConfig
from crossarm.convert.karel_files import PREDEFINED_DIRECTORIES
from crossarm.convert.translate import tp_program_name
from crossarm.convert.unsupported import RAPID_DATA, RAPID_INSTRUCTIONS
from crossarm.diagnose import NATIVE_FUNCTIONS, NATIVE_TYPES, SIGNAL_TYPES
from crossarm.rapid.eio import eio_records, find_eio
from crossarm.rapid.lexer import tokenize
from crossarm.rapid.source import read_source
from crossarm.rapid.system_info import read_system
from crossarm.rapid.tokens import Token, TokenKind

REPORT = "anonymize_report.md"
DEFAULT_NAME = "crossarm_anonymized"
LIMIT = ("Joint positions (jointtarget, MoveAbsJ) are not moved while the robtargets are, so the cell's geometry no "
         "longer holds together: the conversion stays equivalent, but an anonymized backup cannot be used to check "
         "paths in ROBOGUIDE unless it is made with --keep-geometry. Positions written in an instruction rather "
         "than declared are kept as they are.")  # fmt: skip
MAPPING_WARNING = ("Keep this file: it reverses the anonymization (original names, texts and position offsets). "
                   "Never send it with the anonymized backup.")  # fmt: skip

# RAPID's own constants, error numbers and record components: kept as written (RobotWare 6 and 7 technical
# reference). A name the backup uses that is in none of CrossArm's tables is renamed (EXT_n): the conversion does
# not depend on it, CrossArm does not know it.
_CONSTANTS = """
    HIGH LOW EDGE DISKHOME DISKRAM DISKTEMP STR_DIGIT STR_UPPER STR_LOWER STR_WHITE EOF EOF_BIN EOF_NUM END_OF_LIST
    ROB_1 ROB_2 ROB_3 ROB_4 ROB_5 ROB_6 ROB_ID PI VMAX TASK STEMPTY STILLEGAL BTNNONE BTNOK BTNABRTRTRYIGN
    BTNOKCANCEL BTNRETRYCANCEL BTNYESNO BTNYESNOCANCEL BTN_NONE BTN_OK BTN_ABORT BTN_RETRY BTN_IGNORE BTN_CANCEL
    BTN_YES BTN_NO ICONNONE ICONINFO ICONWARNING ICONERROR COMMON_ERR OP_STATE SYSTEM_ERR HARDWARE_ERR PROGRAM_ERR
    MOTION_ERR OPERATOR_ERR IO_COM_ERR USER_DEF_ERR SYNTAX_ERR PROCESS_ERR CFG_ERR OPTION_PROD_ERR ARCWELD_ERR
    SPOTWELD_ERR PAINT_ERR PICKWARE_ERR TYPE_ALL TYPE_ERR TYPE_WARN TYPE_STATE EE_POWERON EE_START EE_STOP EE_QSTOP
    EE_RESTART EE_RESET EE_STEP EE_STEP_FWD EE_STEP_BWD EE_BEFORE_INIT EE_AFTER_INIT EE_BEFORE_RESET EE_AFTER_RESET
    EIO_DOMAIN MMC_DOMAIN MOC_DOMAIN PROC_DOMAIN SIO_DOMAIN SYS_DOMAIN USINT UINT UDINT ULINT SINT INT DINT LINT
    TP_LATEST TP_PROGRAM TP_SCREENVIEWER OP_AUTO OP_MAN_PROG OP_MAN_TEST OP_UNDEF RUN_CONT_CYCLE RUN_INSTR_FWD
    RUN_INSTR_BWD RUN_SIM RUN_STEP_MOVE RUN_UNDEF C_MOTSET C_PROGDISP CSS_X CSS_Y CSS_Z CSS_XY CSS_XZ CSS_YZ
    CSS_XYZ CSS_XYRZ CSS_POSX CSS_NEGX CSS_POSY CSS_NEGY CSS_POSZ CSS_NEGZ CSS_REFTOOL CSS_REFWOBJ STOP_PATH
    LOAD_PAYL LOAD_TOOL GAP_SERVICE_TYPE GAP_PROGRAM_TYPE ERR_X
""".split()  # noqa: SIM905 - kept as a readable word table
_ERRORS = """
    ACC_TOO_LOW ALRDYCNT ALRDY_MOVING AO_LIM ARGDUPCND ARGNAME ARGNOTPER ARGNOTVAR ARGTYPE ARGVALERR AXIS_ACT AXIS_IND
    AXIS_MOVING AXIS_PAR BUSSTATE BWDLIMIT CALLIO_INTER CALLPROC CFG_INTERNAL CFG_LIMIT CFG_ILLTYPE CFG_NOTFND
    CFG_OUTOFBOUNDS CFG_WRITEFILE CNTNOTVAR CNV_NOT_ACT CNV_CONNECT CNV_DROPPED COLL_STOP COMM_EXT COMM_INIT
    COMM_INIT_FAILED CONC_MAX DATA_RECV DEV_MAXTIME DIPLAG_LIM DIVZERO EXECPHR FILEACC FILEEXIST FILEOPEN FILNOTFND
    FNCNORET FRAME GO_LIM ILLDIM ILLQUAT ILLRAISE INOISSAFE INOMAX INT_NOTVAL INT_MAXVAL INVDIM IODISABLE
    IODN_TIMEOUT IOENABLE IOERROR LINKREF LOADED LOADID_FATAL LOADID_RETRY LOADNO_INUSE LOADNO_NOUSE MAXINTVAL MODULE
    MOD_NOT_LOADED MOD_NOTLOADED MSG_PENDING NAME_INVALID NO_ALIASIO_DEF NORUNUNIT NOTARR NOTEQDIM NOTINTVAL NOTPRES
    NOTSAVED NOT_MOVETASK NUM_LIMIT OUTOFBND OVERFLOW PATH PATHDIST PATH_STOP PERSSUPSEARCH PID_MOVESTOP
    PID_RAISE_PP PRGMEMFULL PROCSIGNAL_OFF PROGSTOP RANYBIN_CHK RANYBIN_EOF RCVDATA REFUNKDAT REFUNKFUN REFUNKPRC
    REFUNKTRP RMQ_DIM RMQ_FULL RMQ_INVALID RMQ_INVMSG RMQ_MSGSIZE RMQ_NAME RMQ_NOMSG RMQ_TIMEOUT RMQ_VALUE ROBLIMIT
    SC_WRITE SIGSUPSEARCH SIG_NAME SIG_NOT_VALID SOCK_ADDR_INVALID SOCK_CLOSED SOCK_TIMEOUT SOCK_NET_UNREACH
    SOCK_ADDR_INUSE SOCK_UNSPEC SPEEDLIM_VALUE SPEED_REFRESH_LIM STARTMOVE STORE_PROF STRTOOLNG SYMBOL_TYPE
    SYM_ACCESS SYNCMOVEOFF SYNCMOVEON SYNTAX TASKNAME TP_DIBREAK TP_DOBREAK TP_MAXTIME TP_NO_CLIENT TRUSTLEVEL
    TXTNOEXIST UDPUC_COMM UISHOW_FATAL UISHOW_FULL UNIT_PAR UNKINO UNKPROC UNLOAD USE_PROF WAITSYNCTASK
    WAIT_MAXTIME WHL_SEARCH WHLSEARCH WOBJ_MOVING
""".split()  # noqa: SIM905 - kept as a readable word table
NATIVE_NAMES = (
    RAPID_INSTRUCTIONS | NATIVE_FUNCTIONS | frozenset(t.upper() for t in NATIVE_TYPES) | frozenset(PREDEFINED)
    | RAPID_DATA | frozenset(PREDEFINED_DIRECTORIES) | frozenset(_CONSTANTS) | frozenset("ERR_" + e for e in _ERRORS)
)  # fmt: skip
NATIVE_COMPONENTS = frozenset("""
    TRANS ROT ROBCONF EXTAX X Y Z Q1 Q2 Q3 Q4 CF1 CF4 CF6 CFX EAX_A EAX_B EAX_C EAX_D EAX_E EAX_F ROBAX RAX_1 RAX_2
    RAX_3 RAX_4 RAX_5 RAX_6 ROBHOLD TFRAME TLOAD MASS COG AOM IX IY IZ UFPROG UFMEC UFRAME OFRAME V_TCP V_ORI V_LEAX
    V_REAX FINEP PZONE_TCP PZONE_ORI PZONE_EOFFS ZONE_ORI ZONE_LEAX ZONE_REAX TYPE PROGSYNCH INPOS STOPTIME
    FOLLOWTIME SIGNAL RELATION CHECKVALUE PDISP EOFFS DOMAIN NUMBER
""".split())  # noqa: SIM905 - kept as a readable word table

PROGRAM_NAME_LENGTH = ConversionConfig().program_name_max_length
_SIGNAL_PREFIX = re.compile(r"^[dD][iIoO](?=[_0-9A-Z])")  # translate._SIGNAL_PREFIX: a signal by its name
_STORAGE = ("CONST", "VAR", "PERS")
_STATEMENT_START = ("THEN", "ELSE", "DO", "ENDIF", "ENDFOR", "ENDWHILE", "ENDTEST", "ERROR", "UNDO", "BACKWARD")
_TYPE_CATEGORY = {
    "TOOLDATA": "TOOL", "WOBJDATA": "WOBJ", "LOADDATA": "LOAD", "ROBTARGET": "PT", "JOINTTARGET": "JT", "NUM": "NUM",
    "DNUM": "NUM", "BOOL": "FLAG", "STRING": "TXT", "SPEEDDATA": "SPEED", "ZONEDATA": "ZONE", "POS": "POSE",
    "POSE": "POSE", "ORIENT": "POSE", "INTNUM": "INTR", "SIGNALDI": "DI", "SIGNALDO": "DO", "SIGNALGI": "GI",
    "SIGNALGO": "GO", "SIGNALAI": "AI", "SIGNALAO": "AO", "ERRNUM": "ERRNUM",
}  # fmt: skip
_POSED = ("ROBTARGET", "WOBJDATA", "TOOLDATA")  # data whose declared value holds a position CrossArm may move
_SYMBOLS = "#$&*+-=@~^:/<>?"
_SAFE_HEADER = re.compile(r"^[\s%A-Za-z0-9:._]*$")
_EIO_HEADER = re.compile(r"^EIO:CFG_[\d.]+:[\d:]*$")
_SIGNAL_TYPE = re.compile(r"^[A-Z]{2}$")


# ---------------------------------------------------------------------------
# Reading the tokens: what each name is
# ---------------------------------------------------------------------------


@dataclass
class _Ident:
    index: int  # in the file's tokens
    role: str  # "name" | "field" | "named" (an optional argument \X)
    owners: tuple[str, ...] = ()  # "named": the routine(s) it may be an argument of, the likeliest first


@dataclass
class _Decl:
    type_name: str
    name: str
    start: int  # first token of the value, after :=
    end: int  # the ;


@dataclass
class _File:
    """One RAPID file of the input, as tokens, and what reading them found."""

    task: int
    system: bool
    suffix: str
    text: str
    source: str = ""  # where it was in the input: for --write-mapping only
    tokens: list[Token] = field(default_factory=list)
    comments: int = 0
    comment_spans: list[tuple[int, int]] = field(default_factory=list)
    idents: list[_Ident] = field(default_factory=list)
    decls: list[_Decl] = field(default_factory=list)
    module: str | None = None
    frames: list[tuple[set[str], str | None]] = field(default_factory=list)  # (names, \WObj) of each statement


class _Reader:
    """Walks one file's tokens: the role of each name, the declarations, the work object each statement names."""

    def __init__(self, file: _File, declare) -> None:
        self.f = file
        self.declare = declare  # declare(upper name, spelling, category)

    def run(self) -> None:
        tokens = self.f.tokens
        header = False
        header_depth = 0
        header_end = trap_name = -1
        record = False
        decl: dict | None = None
        depth = 0
        calls: list[tuple[str, int]] = []
        head: str | None = None
        head_ident = False
        statement_idents: list[str] = []
        statement_names: set[str] = set()
        statement_wobj: str | None = None
        prev: Token | None = None
        prev2: Token | None = None
        for i, t in enumerate(tokens):
            if t.kind is TokenKind.EOF:
                break
            start = (prev is None or prev.is_op(";", ":") or prev.is_kw(*_STATEMENT_START) or i - 1 == header_end
                     or i - 1 == trap_name)  # fmt: skip
            if start and not header:
                if statement_names:
                    self.f.frames.append((statement_names, statement_wobj))
                head, head_ident, depth, calls = None, False, 0, []
                statement_idents, statement_names, statement_wobj = [], set(), None
                if t.kind is TokenKind.IDENT:
                    head, head_ident = t.value.upper(), True
                elif t.kind is TokenKind.KEYWORD:
                    head = t.value
            nxt = tokens[i + 1] if i + 1 < len(tokens) else t
            if t.kind is TokenKind.IDENT:
                upper = t.value.upper()
                if prev is not None and prev.is_op("."):
                    self.f.idents.append(_Ident(i, "field"))
                elif prev is not None and prev.is_op("\\") and not header:
                    if depth > 0 and calls:
                        owners = (calls[-1][0],)
                    elif head is not None and head_ident:
                        owners = (head,)
                    else:
                        owners = tuple(reversed(statement_idents))
                    self.f.idents.append(_Ident(i, "named", owners))
                    if upper == "WOBJ" and nxt.is_op(":=", "?") and i + 2 < len(tokens):
                        value = tokens[i + 2]
                        if value.kind is TokenKind.IDENT:
                            statement_wobj = value.value.upper()
                elif record and nxt.is_op(";"):
                    self.f.idents.append(_Ident(i, "field"))
                    self.declare(upper, t.value, "FIELD", field_name=True)
                else:
                    self.f.idents.append(_Ident(i, "name"))
                    self._category(t, upper, prev, prev2, nxt, header, start, decl)
                    if depth == 0:
                        statement_idents.append(upper)
                    statement_names.add(upper)
                if decl is not None and not header:
                    if decl["type"] is None:
                        decl["type"] = upper
                    elif decl["name"] is None:
                        decl["name"] = upper
                if prev is not None and prev.is_kw("TRAP"):
                    trap_name = i
            elif t.kind is TokenKind.KEYWORD:
                if t.value == "MODULE" and nxt.kind is TokenKind.IDENT and self.f.module is None:
                    self.f.module = nxt.value.upper()
                elif t.value == "RECORD":
                    record = True
                elif t.value == "ENDRECORD":
                    record = False
                elif t.value in _STORAGE and not header and depth == 0:
                    decl = {"type": None, "name": None, "start": None}
            elif t.kind is TokenKind.OP:
                if t.value == "(":
                    opens_header = (prev is not None and prev.kind is TokenKind.IDENT and prev2 is not None
                                    and (prev2.is_kw("PROC", "FUNC") or (prev2.kind is TokenKind.IDENT
                                                                         and i >= 3 and tokens[i - 3].is_kw("FUNC"))))  # fmt: skip
                    if opens_header and not header:
                        header, header_depth = True, depth
                    elif prev is not None and prev.kind is TokenKind.IDENT:
                        calls.append((prev.value.upper(), depth))
                    depth += 1
                elif t.value == ")":
                    depth = max(0, depth - 1)
                    calls = [c for c in calls if c[1] < depth]
                    if header and depth == header_depth:
                        header, header_end = False, i
                elif t.value == ":=" and decl is not None and decl["start"] is None:
                    decl["start"] = i + 1
                elif t.value == ";":
                    if decl is not None and decl["start"] is not None and decl["type"] and decl["name"]:
                        self.f.decls.append(_Decl(decl["type"], decl["name"], decl["start"], i))
                    decl = None
            prev2, prev = prev, t
        if statement_names:
            self.f.frames.append((statement_names, statement_wobj))

    def _category(self, t: Token, upper: str, prev, prev2, nxt, header: bool, start: bool, decl) -> None:
        declare = self.declare
        if prev is None:
            return
        if prev.is_kw("MODULE"):
            declare(upper, t.value, "MOD")
        elif prev.is_kw("PROC"):
            declare(upper, t.value, "PROC")
        elif prev.is_kw("TRAP"):
            declare(upper, t.value, "TRAP")
        elif prev2 is not None and prev2.is_kw("FUNC") and prev.kind is TokenKind.IDENT:
            declare(upper, t.value, "FUNC")
        elif prev.is_kw("RECORD"):
            declare(upper, t.value, "REC")
        elif prev2 is not None and prev2.is_kw("ALIAS") and prev.kind is TokenKind.IDENT:
            declare(upper, t.value, "TYPE")
        elif prev.is_kw("FOR"):
            declare(upper, t.value, "IDX")
        elif prev.is_kw("GOTO") or (start and nxt.is_op(":")):
            declare(upper, t.value, "LABEL")
        elif header and nxt.is_op(",", ")", "|", "{"):
            declare(upper, t.value, "PARAM")
        elif (decl is not None and decl["type"] is not None and decl["name"] is None and prev.kind is TokenKind.IDENT
              and not header):  # fmt: skip
            declare(upper, t.value, _TYPE_CATEGORY.get(decl["type"], "DATA"))


# ---------------------------------------------------------------------------
# The new names
# ---------------------------------------------------------------------------


def _letters(k: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA..."""
    out = ""
    k += 1
    while k:
        k, rest = divmod(k - 1, 26)
        out = chr(65 + rest) + out
    return out


class _Names:
    def __init__(self) -> None:
        self.category: dict[str, str] = {}  # upper -> category, the first declaration's
        self.spelling: dict[str, str] = {}
        self.order: list[str] = []  # names in the order first declared, then first used
        self.fields: dict[str, str] = {}  # field upper -> spelling
        self.field_order: list[str] = []
        self.used: set[str] = set()  # every name of the input, upper: a new name must be none of them
        self.new: dict[str, str] = {}
        self.new_fields: dict[str, str] = {}

    def declare(self, upper: str, spelling: str, category: str, field_name: bool = False) -> None:
        if field_name:
            if upper not in self.fields:
                self.fields[upper] = spelling
                self.field_order.append(upper)
            return
        if upper not in self.category:
            self.category[upper] = category
            self.spelling[upper] = spelling
            self.order.append(upper)

    def use(self, upper: str, spelling: str) -> None:
        if upper not in self.category:
            self.declare(upper, spelling, "EXT")

    def assign(self, fixed: dict[str, str]) -> None:
        """The new names, numbered in the order of the originals and zero-padded (MOD_01... when there are ten or
        more): files and routines sort as the originals did, and CrossArm reads them in that order."""
        counters: Counter[str] = Counter()
        taken = set(self.used) | {v.upper() for v in fixed.values()}
        renamed = [u for u in self.order if u not in NATIVE_NAMES and u not in fixed]
        fields = [u for u in self.field_order if u not in NATIVE_COMPONENTS]
        sizes = Counter(self.category[u] for u in renamed) + Counter({"FIELD": len(fields)})

        def fresh(category: str) -> str:
            while True:
                counters[category] += 1
                name = f"{category}_{counters[category]:0{len(str(sizes[category] or 1))}d}"
                if name.upper() not in taken:
                    taken.add(name.upper())
                    return name

        for upper in self.order:
            if upper in NATIVE_NAMES:
                continue
            if upper in fixed:
                self.new[upper] = fixed[upper]
                continue
            new = fresh(self.category[upper])
            self.new[upper] = _keep_rules(self.spelling[upper], new, taken)
        for upper in fields:
            self.new_fields[upper] = fresh("FIELD")
        self._same_programs(fixed, taken)

    def _same_programs(self, fixed: dict[str, str], taken: set[str]) -> None:
        """Routines whose TP program names are the same once shortened (tp_program_name: 36 characters, A-Z 0-9 _)
        keep that clash: CrossArm then renames all but the first, with a warning, as it did for the originals."""
        groups: dict[str, list[str]] = {}
        for upper in self.order:
            if self.category.get(upper) in ("PROC", "FUNC", "TRAP") and upper in self.new and upper not in fixed:
                groups.setdefault(tp_program_name(self.spelling[upper], PROGRAM_NAME_LENGTH), []).append(upper)
        for members in groups.values():
            if len(members) < 2:
                continue
            base = self.new[members[0]].ljust(PROGRAM_NAME_LENGTH, "X")
            for k, upper in enumerate(members):
                self.new[upper] = base if k == 0 else f"{base}_{_letters(k - 1)}"
                taken.add(self.new[upper].upper())


def _keep_rules(original: str, new: str, taken: set[str]) -> str:
    """The new name keeps what CrossArm reads in a name: a signal by its di/do start, an error number by ERR_."""
    out = new
    if _SIGNAL_PREFIX.match(original) and not (_SIGNAL_PREFIX.match(new) and new[:2].upper() == original[:2].upper()):
        out = f"{original[:2].upper()}_{new}"
    elif not _SIGNAL_PREFIX.match(original) and _SIGNAL_PREFIX.match(new):
        out = f"N_{new}"
    if original.upper().startswith("ERR_") and not out.upper().startswith("ERR_"):
        out = f"ERR_{out}"
    taken.add(out.upper())
    return out


# ---------------------------------------------------------------------------
# Texts
# ---------------------------------------------------------------------------


class _Texts:
    """Each distinct text of the input -> its replacement."""

    def __init__(self, names: _Names, prefixes: dict[str, str], suffixes: dict[str, str]) -> None:
        self.names, self.prefixes, self.suffixes = names, prefixes, suffixes
        self.new: dict[str, str] = {}
        self.codes = 0
        self.kept: set[str] = set()
        self.short: Counter[int] = Counter()

    def reserve(self, values: Iterable[str]) -> None:
        self.kept = {v for v in values if _plain(v)}

    def replace(self, value: str) -> str:
        if value in self.new:
            return self.new[value]
        upper = value.upper()
        if _plain(value):
            out = value
        elif upper in self.prefixes:
            out = self.prefixes[upper]
        elif upper in self.suffixes:
            out = self.suffixes[upper]
        elif upper in self.names.new:
            out = self.names.new[upper]
        else:
            out = self._code(value)
        self.new[value] = out
        return out

    def _code(self, value: str) -> str:
        marks = ("'" if "'" in value else "") + ("°" if not value.isascii() or any(ord(c) < 32 for c in value) else "")
        marks += ";" * value.count(";")  # an error handler counts its instructions by its semicolons (coverage)
        length = len(value)
        if length - len(marks) <= 2:
            body_length = max(1, length - len(marks))
            while True:
                k = self.short[body_length]
                self.short[body_length] += 1
                if k >= len(_SYMBOLS) ** body_length:
                    break
                body = "".join(_SYMBOLS[(k // len(_SYMBOLS) ** p) % len(_SYMBOLS)] for p in range(body_length))
                if body + marks not in self.kept and body + marks not in self.new.values():
                    return body + marks
        core = "S" + _letters(self.codes)
        self.codes += 1
        return core + "_" * max(0, length - len(core) - len(marks)) + marks


def _plain(value: str) -> bool:
    """A text with no letter and at most one digit (',', ' ', '1'): kept, it says nothing of the cell."""
    return not any(c.isalpha() for c in value) and sum(c.isdigit() for c in value) <= 1


def _late_names(routines: Iterable[str], texts: set[str], names: _Names) -> tuple[dict[str, str], dict[str, str],
                                                                                    dict[str, str]]:  # fmt: skip
    """Routines a call by a name built at run time can name: prefix + digits (+ suffix), the prefix a text of the
    backup. (prefix -> new, suffix -> new, routine -> new name)."""
    prefixes: dict[str, str] = {}
    suffixes: dict[str, str] = {}
    routine_names: dict[str, str] = {}
    candidates = sorted((t for t in texts if t and any(c.isalpha() for c in t)), key=lambda t: (-len(t), t))
    for routine in routines:
        for text in candidates:
            if routine == text or not routine.startswith(text):
                continue
            match = re.fullmatch(r"(\d+)(\w*)", routine[len(text):])
            if not match or (match[2] and match[2] not in texts):
                continue
            prefix = prefixes.setdefault(text, f"LB{_letters(len(prefixes))}_")
            suffix = ""
            if match[2]:
                suffix = suffixes.setdefault(match[2], f"_LS{_letters(len(suffixes))}")
            routine_names[routine] = prefix + match[1] + suffix
            break
    for text, new in prefixes.items():
        if text in names.category:  # the prefix is also a name: it takes the prefix's new text as its name
            routine_names.setdefault(text, new)
    return prefixes, suffixes, routine_names


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


def _component(tokens: list[Token], j: int) -> tuple[int, int, float] | None:
    """(first token, past the last, value) of a signed decimal number at tokens[j]."""
    sign, k = 1.0, j
    if k < len(tokens) and tokens[k].is_op("-", "+"):
        sign = -1.0 if tokens[k].value == "-" else 1.0
        k += 1
    if k >= len(tokens) or tokens[k].kind is not TokenKind.NUMBER:
        return None
    try:
        value = float(tokens[k].text)
    except ValueError:  # hexadecimal, octal, binary: not a coordinate
        return None
    return j, k + 1, sign * value


def _poses(tokens: list[Token], start: int, end: int) -> list[list[tuple[int, int, float]]]:
    """Each `[[x,y,z],[` of a declared value: the x, y, z of a robtarget, a user frame, a tool frame."""
    out = []
    i = start
    while i < end - 1:
        if tokens[i].is_op("[") and tokens[i + 1].is_op("["):
            j, parts = i + 2, []
            for n_part in range(3):
                found = _component(tokens, j)
                if found is None:
                    break
                parts.append(found)
                j = found[1]
                if not tokens[j].is_op("," if n_part < 2 else "]"):
                    break
                j += 1
            if len(parts) == 3 and tokens[j - 1].is_op("]") and tokens[j].is_op(",") and tokens[j + 1].is_op("["):
                out.append(parts)
                i = j
                continue
        i += 1
    return out


def _number(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _offset(seed: int, key: str, low: int, high: int) -> tuple[float, float, float]:
    rng = random.Random(f"{seed}:{key}")
    return tuple(rng.choice((-1, 1)) * (rng.randint(low, high) + rng.randint(1, 999) / 1000) for _ in range(3))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# The anonymization
# ---------------------------------------------------------------------------


@dataclass
class Anonymized:
    files: dict[str, bytes]  # path in the zip -> content
    report: str
    mapping: dict
    counts: dict[str, object]

    def zip_bytes(self) -> bytes:
        """The zip, the same bytes for the same files: fixed dates, sorted entries."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(self.files):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0o644 << 16
                archive.writestr(info, self.files[name], compresslevel=9)
        return buffer.getvalue()


def anonymize(paths: list[Path], seed: int | None = None, keep_geometry: bool = False, scramble_tools: bool = False,
              eio: Path | None = None) -> Anonymized:  # fmt: skip
    """The anonymized copy of what `paths` hold. Raises what open_source raises for an input it cannot read."""
    if seed is None:
        seed = random.SystemRandom().randrange(2**63)
    names = _Names()
    files: list[_File] = []
    read_paths: set[Path] = set()
    not_read = 0
    with open_source(list(paths)) as source:
        kind = source.kind
        root = source.root
        eio_path = eio or source.eio or (find_eio([Path(p) for p in paths]) if kind == "files" else None)
        system = read_system(root)
        backinfo_tasks = task_names(root) if root is not None else {}
        task_folders: list[str] = []
        for number, task in enumerate(source.tasks):
            folder = ""
            if root is not None and task.files:
                folder = task.files[0].relative_to(root / "RAPID").parts[0]
            task_folders.append(folder)
            for path in task.files:
                try:
                    text = read_source(path).text
                except OSError:
                    not_read += 1
                    continue
                read_paths.add(path)
                where = path.relative_to(root).as_posix() if root is not None else path.name
                files.append(_File(number, path in set(task.data_files), path.suffix.lower(), text, where))
                if not files[-1].suffix:
                    files[-1].suffix = ".mod"
        records = []
        if eio_path is not None:
            try:
                records = eio_records(read_source(eio_path).text)
                read_paths.add(Path(eio_path).resolve())
            except OSError:
                records = []
        left_out = _left_out(paths, root, read_paths, kind)
        task_list = [t.name for t in source.tasks]
        stems = [Path(p).stem for t in source.tasks for p in t.files if p in read_paths]

    # EIO first: its signals have the best categories (DI, DO...)
    for section, attrs in records:
        if section == "EIO_SIGNAL" and "Name" in attrs:
            kind_ = attrs.get("SignalType", "").upper()
            names.declare(attrs["Name"].upper(), attrs["Name"], kind_ if kind_ in SIGNAL_TYPES else "SIG")
    for section, attrs in records:
        if section != "EIO_SIGNAL" and "Name" in attrs:
            names.declare(attrs["Name"].upper(), attrs["Name"], "DEV")
        if section == "EIO_SIGNAL" and attrs.get("Device"):
            names.declare(attrs["Device"].upper(), attrs["Device"], "DEV")

    texts: list[str] = []
    for file in files:
        lexed = tokenize(file.text)
        file.tokens = lexed.tokens
        file.comments = len(lexed.comments)
        file.comment_spans = [(c.start, _line_end(file.text, c.start)) for c in lexed.comments]
        _Reader(file, names.declare).run()
        for token in file.tokens:
            if token.kind is TokenKind.IDENT:
                names.used.add(token.value.upper())
            elif token.kind is TokenKind.STRING:
                texts.append(token.value)
    for file, stem in zip(files, stems, strict=True):
        if file.module is None:
            names.declare(stem.upper(), stem, "MOD")
            file.module = stem.upper()
    for name in task_list:
        if name.upper() != "FILES":
            names.declare(name.upper(), name, "TASK")
    routines = {u for u, c in names.category.items() if c in ("PROC", "FUNC", "TRAP")}
    for file in files:
        for ident in file.idents:
            token = file.tokens[ident.index]
            if ident.role == "name" or (ident.role == "named" and _user_owner(ident, routines) is not None):
                names.use(token.value.upper(), token.value)
            elif ident.role == "field" and token.value.upper() not in NATIVE_COMPONENTS:
                names.declare(token.value.upper(), token.value, "FIELD", field_name=True)

    prefixes, suffixes, late = _late_names(sorted(routines), {t.upper() for t in texts}, names)
    names.used |= {v.upper() for v in late.values()}
    names.assign(late)
    strings = _Texts(names, prefixes, suffixes)
    strings.reserve(texts)

    # Positions: the frame of each robtarget, the offset of each frame
    category = names.category
    frame_of: dict[str, str] = {}
    for file in files:
        for statement_names, wobj in file.frames:
            if wobj is None:
                continue
            for name in statement_names:
                if category.get(name) == "PT":
                    frame_of.setdefault(name, wobj)
    moved = Counter()
    offsets: dict[str, tuple[float, float, float]] = {}

    def frame_offset(frame: str) -> tuple[float, float, float]:
        key = names.new.get(frame, frame).upper()
        if key not in offsets:
            offsets[key] = _offset(seed, f"frame:{key}", 150, 900)
        return offsets[key]

    out_files: dict[str, bytes] = {}
    file_names: dict[str, str] = {}
    comments = strings_replaced = 0
    failed = 0
    used_paths: set[str] = set()
    for file in files:
        try:
            replacements = {} if keep_geometry else _positions(file, frame_of, frame_offset, scramble_tools, seed,
                                                               moved)  # fmt: skip
            text = _rewrite(file, names, strings, routines, replacements)
        except Exception:  # noqa: BLE001 - a file CrossArm cannot anonymize is left out, never written as it was
            failed += 1
            continue
        comments += file.comments
        strings_replaced += sum(1 for t in file.tokens if t.kind is TokenKind.STRING)
        module = names.new.get(file.module or "", file.module or "MODULE")
        if kind == "backup":
            folder = task_folders[file.task]
            folder = folder if re.fullmatch(r"TASK\d+", folder, re.IGNORECASE) else f"TASK{900 + file.task}"
            base = f"RAPID/{folder}/{'SYSMOD' if file.system else 'PROGMOD'}/"
        else:
            base = "" if len(task_list) == 1 else f"{names.new.get(task_list[file.task].upper(), f'TASK_{file.task + 1}')}/"
        path = _unique(f"{base}{module}{file.suffix}", used_paths)
        out_files[path] = text.encode("utf-8")
        file_names[file.source] = path

    if records:
        out_files["SYSPAR/EIO.cfg" if kind == "backup" else "EIO.cfg"] = _eio(records, names).encode("utf-8")
    if kind == "backup" and (backinfo_tasks or system.sources):
        out_files["BACKINFO/backinfo.txt"] = _backinfo(system, backinfo_tasks, names).encode("utf-8")

    counts = {
        "kind": kind,
        "tasks": len(task_list),
        "rapid_files": len(files) - failed,
        "not_anonymized": failed,
        "not_read": not_read,
        "left_out": left_out,
        "eio": bool(records),
        "backinfo": "BACKINFO/backinfo.txt" in out_files,
        "names": dict(sorted(Counter(names.category[u] for u in names.new).items())),
        "fields": len(names.new_fields),
        "kept_rapid_names": sum(1 for u in names.order if u in NATIVE_NAMES),
        "texts": len([v for v in strings.new if strings.new[v] != v]),
        "text_uses": strings_replaced,
        "texts_kept": len([v for v in strings.new if strings.new[v] == v]),
        "comments": comments,
        "geometry": not keep_geometry,
        "robtargets": moved["PT"],
        "frames": len(offsets),
        "user_frames": moved["WOBJ"],
        "tools": moved["TOOL"],
        "scramble_tools": scramble_tools and not keep_geometry,
    }
    report = _report(counts)
    out_files[REPORT] = report.encode("utf-8")
    mapping = {
        "warning": MAPPING_WARNING,
        "crossarm": __version__,
        "seed": seed,
        "names": {names.spelling[u]: names.new[u] for u in names.order if u in names.new},
        "categories": {names.new[u]: names.category[u] for u in names.order if u in names.new},
        "fields": {names.fields[u]: v for u, v in names.new_fields.items()},
        "texts": {k: v for k, v in strings.new.items() if k != v},
        "frame_offsets_mm": {k: list(v) for k, v in sorted(offsets.items())},
        "files": file_names,
    }
    return Anonymized(out_files, report, mapping, counts)


def _line_end(text: str, start: int) -> int:
    end = text.find("\n", start)
    return len(text) if end == -1 else end


def _unique(path: str, used: set[str]) -> str:
    stem, dot, suffix = path.rpartition(".")
    candidate, k = path, 1
    while candidate.upper() in used:
        k += 1
        candidate = f"{stem}_{k}{dot}{suffix}"
    used.add(candidate.upper())
    return candidate


def _left_out(paths: list[Path], root: Path | None, read: set[Path], kind: str) -> int:
    """Files of the input CrossArm does not read: not in the zip."""
    if kind == "backup" and root is not None:
        everything = [p for p in root.rglob("*") if p.is_file()]
    else:
        everything = [f for p in paths for f in (Path(p).rglob("*") if Path(p).is_dir() else [Path(p)]) if f.is_file()]
    resolved = {Path(p).resolve() for p in read}
    return sum(1 for p in everything if p.resolve() not in resolved and p.suffix.lower() != ".zip")


def _user_owner(ident: _Ident, routines: set[str]) -> str | None:
    for owner in ident.owners:
        if owner in routines:
            return owner
        if len(ident.owners) == 1:
            return None
    return None


def _positions(file: _File, frame_of: dict[str, str], frame_offset, scramble_tools: bool, seed: int,
               moved: Counter) -> dict[int, str]:  # fmt: skip
    """token index -> new text, for the x, y, z of the positions moved; '' for a sign token folded into a value."""
    out: dict[int, str] = {}
    tokens = file.tokens
    for decl in file.decls:
        if decl.type_name not in _POSED:
            continue
        poses = _poses(tokens, decl.start, decl.end)
        if decl.type_name == "ROBTARGET":
            offset = frame_offset(frame_of.get(decl.name, "WOBJ0"))
            chosen, kind = poses, "PT"
        elif decl.type_name == "WOBJDATA":
            offset = frame_offset("WOBJ0")
            chosen, kind = poses[:1], "WOBJ"  # the user frame; the object frame is kept
        else:
            if not scramble_tools:
                continue
            chosen, kind = poses[:1], "TOOL"
            offset = _offset(seed, "tool:" + ",".join(_number(p[2]) for p in chosen[0]) if chosen else "", 5, 60)
        for parts in chosen:
            if all(p[2] == 0 for p in parts):
                continue  # a pose at the origin says nothing of the cell
            for (first, past, value), delta in zip(parts, offset, strict=True):
                out[first] = _number(value + delta)
                for k in range(first + 1, past):
                    out[k] = ""
            moved[kind] += 1
    return out


def _rewrite(file: _File, names: _Names, strings: _Texts, routines: set[str], positions: dict[int, str]) -> str:
    text = file.text
    roles = {ident.index: ident for ident in file.idents}
    out: list[str] = []
    cursor = 0
    spans = iter(file.comment_spans)
    span = next(spans, None)
    for i, token in enumerate(file.tokens):
        pieces, at = [], cursor
        while span is not None and span[0] < token.start:
            if span[0] >= cursor:
                pieces.append(text[at : span[0]])
                semicolons = text.count(";", span[0], span[1])  # counted in an error handler (coverage.weight)
                pieces.append("!" + ";" * semicolons if semicolons else "")
                at = span[1]
            span = next(spans, None)
        pieces.append(text[at : token.start])
        gap = "".join(pieces)
        if cursor == 0 and gap.lstrip().startswith("%%%") and not _SAFE_HEADER.match(gap):
            gap = "\n" * gap.count("\n")
        out.append(gap)
        if token.kind is TokenKind.EOF:
            out.append(text[token.start :])
            break
        cursor = token.end
        if i in positions:
            out.append(positions[i])
        elif token.kind is TokenKind.IDENT:
            out.append(_ident(token, roles.get(i), names, routines))
        elif token.kind is TokenKind.STRING:
            new = strings.replace(token.value)
            out.append('"' + new.replace("\\", "\\\\").replace('"', '""') + '"')
        else:
            out.append(token.text)
    return "".join(out)


def _ident(token: Token, ident: _Ident | None, names: _Names, routines: set[str]) -> str:
    upper = token.value.upper()
    if ident is not None and ident.role == "field":
        return names.new_fields.get(upper, token.value)
    if ident is not None and ident.role == "named" and _user_owner(ident, routines) is None:
        return token.value
    return names.new.get(upper, token.value)


def _eio(records: list[tuple[str, dict[str, str]]], names: _Names) -> str:
    """EIO.cfg reduced to what CrossArm reads: each record kept (renamed), each signal's name, type and device."""
    lines = ["EIO:CFG_1.0:6:1::", "#"]
    section = None
    counters: Counter[str] = Counter()
    for name, attrs in records:
        if name != section:
            lines += [f"{name}:", ""]
            section = name
        if name == "EIO_SIGNAL":
            parts = []
            if "Name" in attrs:
                parts.append(f'-Name "{names.new.get(attrs["Name"].upper(), attrs["Name"])}"')
            kind = attrs.get("SignalType", "").upper()
            if _SIGNAL_TYPE.match(kind):
                parts.append(f'-SignalType "{kind}"')
            if attrs.get("Device"):
                parts.append(f'-Device "{names.new.get(attrs["Device"].upper(), "DEV")}"')
            lines += ["      " + " ".join(parts or ['-Name "SIG"']), ""]
        else:
            if "Name" in attrs:
                new = names.new.get(attrs["Name"].upper(), "DEV")
            else:
                counters[name] += 1
                new = f"RECORD_{counters[name]}"
            lines += [f'      -Name "{new}"', ""]
    return "\n".join(lines) + "\n"


def _backinfo(system, tasks: dict[str, str], names: _Names) -> str:
    lines = [">>PRODUCTS_ID:"]
    if system.robotware:
        lines.append(f"RobotWare Version: {system.robotware}")
    lines += [f"  {option}" for option in system.options] + [f"  {robot}" for robot in system.robots]
    lines.append("")
    for folder in sorted(tasks):
        lines.append(f">>{folder}: ({names.new.get(tasks[folder].upper(), tasks[folder])},,)")
    return "\n".join(lines) + "\n"


EIO_KEPT = "kept, reduced to each signal's name, type and device and to each section's records, renamed"
BACKINFO_KEPT = "task names (renamed), RobotWare version, ABB options and robot models only"


def _report(c: dict) -> str:
    by_category = ", ".join(f"{k} {v}" for k, v in c["names"].items()) or "none"
    if c["geometry"]:
        geometry = (f"moved: {c['robtargets']} robtarget(s) by a random offset of their frame ({c['frames']} "
                    f"frame(s)), {c['user_frames']} work object user frame(s); tools "
                    + (f"moved ({c['tools']})" if c["scramble_tools"] else "kept (add --scramble-tools to move them)")
                    + ". The offsets are random and are not written here.")  # fmt: skip
    else:
        geometry = "kept as written (--keep-geometry)."
    lines = [
        "# CrossArm anonymized backup",
        "",
        (f"Made by CrossArm {__version__} (`crossarm anonymize`). Counts only: the table of correspondence between "
         "the original names and the new ones is not in this archive."),
        "",
        (f"- Input: {c['kind']}, {c['tasks']} task(s); {c['rapid_files']} RAPID file(s) kept, renamed after their "
         f"module; {c['left_out']} other file(s) left out (CrossArm does not read them)"),
        (f"- RAPID files not read: {c['not_read']}; left out because CrossArm failed to anonymize them: "
         f"{c['not_anonymized']}"),
        "- EIO.cfg: " + (EIO_KEPT if c["eio"] else "none"),
        "- BACKINFO: " + (BACKINFO_KEPT if c["backinfo"] else "none"),
        f"- Names renamed: {sum(c['names'].values())} ({by_category}); record fields renamed: {c['fields']}",
        (f"- RAPID's own names kept as written: {c['kept_rapid_names']} (instructions, functions, data types, "
         "predefined data, constants, error numbers)"),
        (f"- Texts replaced: {c['texts']} distinct ({c['text_uses']} uses), each by a code of the same length; "
         f"texts kept (no letter, at most one digit): {c['texts_kept']}"),
        f"- Comments removed: {c['comments']}",
        f"- Positions: {geometry}",
        "- Numbers other than positions are kept (speeds, zones, offsets, counters): the conversion depends on them.",
        "",
        f"Limit: {LIMIT}",
    ]
    return "\n".join(lines) + "\n"


def default_output(paths: list[Path]) -> Path:
    """crossarm_anonymized.zip next to the input (_2, _3... when taken): the input's name is not in it."""
    first = Path(paths[0]).resolve()
    folder = first.parent
    candidate, k = folder / f"{DEFAULT_NAME}.zip", 1
    while candidate.exists():
        k += 1
        candidate = folder / f"{DEFAULT_NAME}_{k}.zip"
    return candidate


def write(result: Anonymized, output: Path, mapping_file: Path | None = None) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result.zip_bytes())
    if mapping_file is not None:
        mapping_file.parent.mkdir(parents=True, exist_ok=True)
        mapping_file.write_text(json.dumps(result.mapping, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


__all__ = ["LIMIT", "MAPPING_WARNING", "NATIVE_COMPONENTS", "NATIVE_NAMES", "REPORT", "Anonymized", "anonymize",
           "default_output", "write"]  # fmt: skip
