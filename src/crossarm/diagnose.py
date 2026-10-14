# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""`crossarm diagnose`: what CrossArm understood and converted of a backup, without any of the backup's content.

    crossarm diagnose BACKUP|FILES [-o DIR] [--fanuc ...]  ->  DIR/crossarm_diag.json + DIR/crossarm_diag.md

The backup is converted as `crossarm convert` would (pipeline.run, into a temporary folder deleted afterwards: no
program is written next to the input), then described by counts only. This module is the ONLY place deciding what a
diagnostic holds, and it holds what the ALLOW-LIST below names, nothing else:

    - the CrossArm version, the operating system (family and release), Python, whether CrossArm.exe ran, the day;
    - the RobotWare version, the ABB options (with their ABB code) and robot models of the backup (system_info.py);
    - counts: tasks, modules (program / system), routines (PROC / FUNC / TRAP), lines, files not read, syntax errors;
    - RAPID's own instructions and functions by name (public ABB vocabulary): how often each is used, and how many of
      those uses were converted, converted with a warning (partial), left TODO, inside a statement left TODO, or in
      no program (and why, from a fixed list: REASONS); the columns add up on every row;
    - calls of the backup's own routines, never by name: `user_proc(num,robtarget,\\switch)`, the parameters reduced
      to their types; calls of routines the backup does not hold: `missing_proc` (argument count only);
    - data types: RAPID's own by name; the backup's records as `record_1`, `record_2`... with their fields' types;
    - TODO and warnings by cause (the causes of the report, a fixed list); the share converted, overall, by area and
      per task (`task_1`, `task_2`...: never the task's name), each task's verdict;
    - control constructs (IF, FOR, WHILE, TEST, GOTO, handlers, TRAP...) and the deepest nesting of blocks;
    - signals: how many of each type (DI, DO, GI, GO, AI, AO), the sections of EIO.cfg and their record counts (the
      bus and device kinds, as ABB names the sections), never a name, a label or an address;
    - CrossArm's internal errors: the exception's type, where in CrossArm (file:line:function), and the RAPID around
      the statement reduced to token categories (<IDENT>, <NUM>, <STR>; RAPID's reserved words, its own instruction and
      function names and punctuation as written). Never the exception's message: it may quote the RAPID.

Never written: a file, folder, module, routine, task, data, signal or device name, a comment, a string, a number of
the backup, a path, the time of day, the licence. tests/test_diagnose_privacy.py checks it on every backup at hand.
crossarm_diag.md is made from crossarm_diag.json alone (`markdown`): the user reads exactly what they would send.

SCHEMA_VERSION: a later version adds keys, never removes or redefines one (docs/diagnostic.md).
"""

import json
import platform
import re
import sys
import tempfile
import zipfile
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, fields
from datetime import date
from pathlib import Path

from crossarm import __version__, pipeline
from crossarm.backup import open_source
from crossarm.convert import ConversionConfig
from crossarm.convert.analysis import WorkablePath, path_to_workable, verdict
from crossarm.convert.blockers import Blocker
from crossarm.convert.external import RAPID_FUNCTIONS
from crossarm.convert.unsupported import NO_TP, RAPID_INSTRUCTIONS
from crossarm.rapid import ParseResult
from crossarm.rapid import nodes as n
from crossarm.rapid.eio import eio_records, find_eio
from crossarm.rapid.lexer import tokenize
from crossarm.rapid.source import read_source
from crossarm.rapid.system_info import read_system
from crossarm.rapid.tokens import RESERVED_WORDS, TokenKind
from crossarm.rapid.walk import split_params, walk_statements
from crossarm.summary import run_path
from crossarm.support import InternalError, crossarm_frame, recording_internal

SCHEMA_VERSION = 4
DIAG_JSON = "crossarm_diag.json"
DIAG_MD = "crossarm_diag.md"
WINDOW = 10  # tokens kept on each side of a statement CrossArm failed on

# RAPID's own data types (RobotWare 6 and 7 technical reference, data types): kept by name.
NATIVE_TYPES = frozenset("""
    aiotrigg anytype bool btnres busstate buttondata byte cameradev cameratarget cfgdomain clock cnvcmd confdata
    corrdescr cssframe datapos dionum dir dnum egmident egm_minmax errdomain errnum errstr errtype event_type
    exec_level extjoint handler_type icondata identno inposdata intnum iodev iounit_state jointtarget listitem loaddata
    loadidnum loadsession mecunit motsetdata num opcalc opnum orient paridnum paridvalidnum pathrecid pos pose progdisp
    rawbytes restartdata rmqheader rmqmessage rmqslot robjoint robtarget sensor sensorstate shapedata signalai signalao
    signaldi signaldo signalgi signalgo signalorigin socketdev socketstatus speeddata stoppointdata string stringdig
    switch symnum syncident system_data taskid tasks testsignal tooldata tpnum trapdata triggdata triggflag triggios
    triggiosdnum triggstrgo tunetype uishownum wobjdata wzstamp zonedata accdata
""".split())  # noqa: SIM905 - kept as a readable word table
NATIVE_FUNCTIONS = RAPID_FUNCTIONS | frozenset(NO_TP) | frozenset({"DIM", "PRESENT", "VALTOSTR", "ARGNAME"})
SIGNAL_TYPES = ("DI", "DO", "GI", "GO", "AI", "AO")
CONTROL = ("IF", "IF_compact", "FOR", "WHILE", "TEST", "RETURN", "EXIT", "GOTO", "LABEL", "RAISE", "RETRY", "TRYNEXT",
           "CONNECT", "LATE_BINDING", "ERROR_HANDLER", "UNDO_HANDLER", "BACKWARD_HANDLER", "TRAP")  # fmt: skip
_KIND = re.compile(r"^[A-Z][A-Z_]{1,29}$")  # the parser's tags for what it keeps as raw text (GOTO, RECORD...)
_SECTION = re.compile(r"^[A-Z][A-Z0-9_]{0,39}$")
_MODES = ("INOUT", "VAR", "PERS")
_KNOWN_CAUSES = frozenset(value for key, value in vars(Blocker).items() if key.isupper() and isinstance(value, str))
_RAPID_CAUSE = re.compile(r"^RAPID [a-z ]{2,40}$")  # Blocker.rapid(kind) of a parser tag
OTHER_CAUSE = "other (cause not listed)"


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------


# Why a use is in no program: a fixed list (schema 2; schema 3 tells the FUNCs apart). Each use of the code CrossArm
# does not write gets one.
SYSTEM_MODULE = "system module"  # a routine of a system module no program calls: converted only on request
LEFT_OUT = "routine left out"  # a TRAP no interrupt connects, parameters not converted, a routine of the same name
MOVE_ROUTINE = "wraps one move"  # its calls are written as its move: counted where it is called
# A FUNC not written as a program (schema 3; schema 2 had them all as "FUNC computed or inlined"):
FUNC_COMPUTED = "FUNC computed at conversion"  # each call converted: its value worked out when converting
FUNC_INLINED = "FUNC inlined"  # its body copied into its calls, or a bool FUNC written as its test in the conditions
FUNC_TODO = "FUNC left TODO at its calls"  # called by converted code, a call left TODO
FUNC_NEVER_CALLED = "FUNC never called"  # no call in the code converted
PROVIDED = "provided by the integrator"  # external_routines
NOT_COMPLETED = "conversion did not complete"
NOT_COUNTED = "other"
CONDITION_ONLY = "condition only"  # status() of an instruction whose condition alone is TODO (never in the output)
REASONS = (SYSTEM_MODULE, LEFT_OUT, MOVE_ROUTINE, FUNC_COMPUTED, FUNC_INLINED, FUNC_TODO, FUNC_NEVER_CALLED, PROVIDED,
           NOT_COMPLETED, NOT_COUNTED)


@dataclass
class Use:
    """How often one instruction, function or call is used, and what the conversion made of those uses:
    occurrences == converted + partial + todo + inside_todo + not_converted, for every row."""

    occurrences: int = 0
    converted: int = 0
    partial: int = 0  # converted with a warning on its line
    todo: int = 0  # the statement carrying a TODO itself
    inside_todo: int = 0  # in a statement left TODO as a whole (an IF whose condition is TODO): counted there
    not_converted: int = 0  # in code no program is written from, for the reasons below
    not_converted_by: Counter = field(default_factory=Counter)

    def add(self, status: str, reason: str | None = None) -> None:
        self.occurrences += 1
        setattr(self, status, getattr(self, status) + 1)
        if status == "not_converted":
            self.not_converted_by[reason or NOT_COUNTED] += 1

    def data(self) -> dict[str, object]:
        out: dict[str, object] = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "not_converted_by"}
        out["not_converted_by"] = {r: self.not_converted_by[r] for r in REASONS if self.not_converted_by[r]}
        return out


@dataclass
class _Inventory:
    instructions: dict[str, Use] = field(default_factory=dict)
    functions: dict[str, Use] = field(default_factory=dict)
    user_calls: dict[str, Use] = field(default_factory=dict)
    data_types: dict[str, Counter] = field(default_factory=dict)
    control: Counter = field(default_factory=Counter)
    depth: int = 0

    def use(self, table: dict[str, Use], key: str, status: str, reason: str | None) -> None:
        table.setdefault(key, Use()).add(status, reason)


class _Names:
    """The backup's own vocabulary, to tell RAPID's names from the user's, and the generic names they get."""

    def __init__(self, modules: list[n.Module]) -> None:
        self.routines: dict[str, n.Routine] = {}
        for module in modules:
            for routine in module.routines:
                self.routines.setdefault(routine.name.upper(), routine)
        self.records: dict[str, str] = {}  # record type (upper) -> record_k
        self.record_fields: dict[str, list[str]] = {}  # record_k -> raw field types
        self.aliases = 0
        for module in modules:
            for item in module.body:
                if isinstance(item, n.Unsupported) and item.kind == "RECORD":
                    name, types = _record(item.raw)
                    if name and name.upper() not in self.records:
                        key = f"record_{len(self.records) + 1}"
                        self.records[name.upper()] = key
                        self.record_fields[key] = types
                elif isinstance(item, n.Unsupported) and item.kind == "ALIAS":
                    self.aliases += 1

    def type_name(self, name: str) -> str:
        lower = name.lower()
        if lower in NATIVE_TYPES:
            return lower
        return self.records.get(name.upper(), "user_type")

    def records_data(self) -> dict[str, list[str]]:
        return {key: [self.type_name(t) for t in types] for key, types in self.record_fields.items()}

    def signature(self, routine: n.Routine) -> str:
        parts = [self._param(part) for part in split_params(routine.params)] if routine.params else []
        kind = "user_func" if routine.kind == "FUNC" else "user_trap" if routine.kind == "TRAP" else "user_proc"
        tail = f"->{self.type_name(routine.return_type)}" if routine.kind == "FUNC" and routine.return_type else ""
        return f"{kind}({','.join(parts)}){tail}"

    def _param(self, part: str) -> str:
        optional = part.startswith("\\")
        out = []
        for alt in part.lstrip("\\").split("|"):
            dims = re.search(r"\{([^}]*)\}", alt)
            words = re.findall(r"[^\W\d]\w*", re.sub(r"\{[^}]*\}", "", alt))
            modes = [w.upper() for w in words if w.upper() in _MODES]
            rest = [w for w in words if w.upper() not in _MODES]
            text = " ".join([*modes, self.type_name(rest[0]) if rest else "?"])
            if dims:
                text += "{" + ",".join("*" for _ in dims[1].split(",")) + "}"
            out.append(text)
        return ("\\" if optional else "") + "|".join(out)


def _record(raw: str) -> tuple[str | None, list[str]]:
    """('pallet', ['num', 'robtarget']) from 'RECORD pallet num rows; robtarget origin; ENDRECORD'."""
    tokens = [t for t in tokenize(raw).tokens if t.kind is not TokenKind.EOF]
    if len(tokens) < 2 or not tokens[0].is_kw("RECORD"):
        return None, []
    types, field_tokens = [], []
    for token in tokens[2:]:
        if token.is_kw("ENDRECORD"):
            break
        if token.is_op(";"):
            if len(field_tokens) >= 2 and field_tokens[0].kind is TokenKind.IDENT:
                types.append(field_tokens[0].value)
            field_tokens = []
        else:
            field_tokens.append(token)
    return tokens[1].value, types


def _expressions(stmt: n.Stmt) -> list[object]:
    """The expressions a statement holds itself, not those of the statements in its blocks."""
    out: list[object] = []
    for f in fields(stmt):
        if f.name in ("span", "body", "else_body", "default"):
            continue
        value = getattr(stmt, f.name)
        if f.name == "branches":
            out += [branch.condition for branch in value]
        elif f.name == "cases":
            out += [v for case in value for v in case.values]
        else:
            out.append(value)
    return out


def _calls(node: object) -> Iterator[n.FuncCall]:
    """Every function call of an expression (arguments included)."""
    stack = [node]
    while stack:
        item = stack.pop()
        if isinstance(item, tuple | list):
            stack.extend(item)
        elif isinstance(item, n.FuncCall):
            yield item
            stack.extend(item.args)
        elif hasattr(item, "__dataclass_fields__") and not isinstance(item, str | n.Comment):
            stack.extend(getattr(item, f.name) for f in fields(item) if f.name != "span")


def _depth(stmts: Iterable[n.Stmt]) -> int:
    deepest = 0
    for stmt in stmts:
        match stmt:
            case n.If():
                inner = max([_depth(b.body) for b in stmt.branches] + [_depth(stmt.else_body)])
            case n.For() | n.While():
                inner = _depth(stmt.body)
            case n.Test():
                inner = max([_depth(c.body) for c in stmt.cases] + [_depth(stmt.default or ())])
            case _:
                continue
        deepest = max(deepest, 1 + inner)
    return deepest


def _instruction(stmt: n.Stmt, names: _Names) -> tuple[str, str] | None:
    """('instructions', 'MOVEL'), ('user_calls', 'user_proc(num)'), ...; None for what is not an instruction."""
    match stmt:
        case n.Comment() | n.DataDecl():
            return None
        case n.Move():
            return "instructions", {"J": "MOVEJ", "L": "MOVEL", "C": "MOVEC", "ABSJ": "MOVEABSJ"}[stmt.kind.value]
        case n.SetSignal():
            return "instructions", "SET" if stmt.value else "RESET"
        case n.WaitTime():
            return "instructions", "WAITTIME"
        case n.Assign():
            return "instructions", "assignment"
        case n.If() | n.For() | n.While() | n.Test() | n.Return() | n.Exit():
            return "instructions", type(stmt).__name__.upper()
        case n.Unsupported():
            return "instructions", stmt.kind if _KIND.match(stmt.kind) else "UNREAD"
        case n.ProcCall():
            key = stmt.name.upper()
            if key in names.routines:
                return "user_calls", names.signature(names.routines[key])
            if key in RAPID_INSTRUCTIONS:
                return "instructions", key
            return "user_calls", f"missing_proc/{len(stmt.args)}"
    return "instructions", "other"


def _function(call: n.FuncCall, names: _Names) -> tuple[str, str]:
    key = call.name.upper()
    if key in names.routines and names.routines[key].kind == "FUNC":
        return "user_calls", names.signature(names.routines[key])
    if key in NATIVE_FUNCTIONS:
        return "functions", key
    return "user_calls", f"missing_func/{len(call.args)}"


def _control(stmt: n.Stmt, control: Counter) -> None:
    match stmt:
        case n.If():
            control["IF_compact" if stmt.compact else "IF"] += 1
        case n.For() | n.While() | n.Test() | n.Return() | n.Exit():
            control[type(stmt).__name__.upper()] += 1
        case n.Unsupported() if stmt.kind in CONTROL:
            control[stmt.kind] += 1


def _blocks(stmt: n.Stmt) -> list[n.Stmt]:
    """The statements of a statement's blocks (one level), as walk_statements visits them."""
    match stmt:
        case n.If():
            return [s for branch in stmt.branches for s in branch.body] + list(stmt.else_body)
        case n.For() | n.While():
            return list(stmt.body)
        case n.Test():
            return [s for case in stmt.cases for s in case.body] + list(stmt.default or ())
    return []


def _count_module(module: n.Module, names: _Names, inv: _Inventory, status) -> None:
    """Everything one module holds, each instruction's status asked of `status(module, routine, stmt)`:
    (status, reason). A TODO is counted once, on the statement carrying it: what its blocks hold, and the functions
    it calls, are inside_todo."""

    def count(stmt: n.Stmt, routine: n.Routine, inside: bool) -> None:
        if isinstance(stmt, n.DataDecl):
            _declare(stmt, names, inv)
        _control(stmt, inv.control)
        what = _instruction(stmt, names)
        if what is None:
            return
        state, reason = ("inside_todo", None) if inside else status(module, routine, stmt)
        whole = state == "todo" and reason != CONDITION_ONLY  # else only its condition is TODO: its blocks converted
        reason = None if state == "todo" else reason
        inv.use(getattr(inv, what[0]), what[1], state, reason)
        if not isinstance(stmt, n.Unsupported):
            for call in _calls(_expressions(stmt)):
                table, key = _function(call, names)
                inv.use(getattr(inv, table), key, "inside_todo" if state == "todo" else state, reason)
        for child in _blocks(stmt):
            count(child, routine, inside or whole or state == "inside_todo")

    for item in module.body:
        if isinstance(item, n.DataDecl):
            _declare(item, names, inv)
    for routine in module.routines:
        if routine.kind == "TRAP":
            inv.control["TRAP"] += 1
        inv.depth = max(inv.depth, _depth(routine.body))
        for stmt in [*routine.body, *routine.handlers]:
            count(stmt, routine, False)


def _declare(decl: n.DataDecl, names: _Names, inv: _Inventory) -> None:
    counts = inv.data_types.setdefault(names.type_name(decl.type_name), Counter())
    counts[decl.storage] += 1
    if decl.dims:
        counts["arrays"] += 1


# ---------------------------------------------------------------------------
# Internal errors
# ---------------------------------------------------------------------------

_VOCABULARY = RAPID_INSTRUCTIONS | NATIVE_FUNCTIONS | frozenset(t.upper() for t in NATIVE_TYPES)


def token_window(text: str, line: int | None) -> str:
    """The RAPID around `line`, WINDOW tokens on each side, as categories: 'IF <IDENT> > <NUM> THEN MOVEL <IDENT> ,'.
    RAPID's reserved words, its own instruction, function and data type names, and punctuation are kept as written."""
    if line is None or not text:
        return ""
    tokens = [t for t in tokenize(text).tokens if t.kind is not TokenKind.EOF]
    at = next((i for i, t in enumerate(tokens) if t.line >= line), len(tokens))
    out = []
    for token in tokens[max(0, at - WINDOW) : at + WINDOW + 1]:
        if token.kind is TokenKind.KEYWORD and token.value in RESERVED_WORDS:
            out.append(token.value)
        elif token.kind is TokenKind.IDENT:
            out.append(token.value.upper() if token.value.upper() in _VOCABULARY else "<IDENT>")
        elif token.kind is TokenKind.NUMBER:
            out.append("<NUM>")
        elif token.kind is TokenKind.STRING:
            out.append("<STR>")
        elif token.kind is TokenKind.OP:
            out.append(token.value)
        else:
            out.append("?")
    return " ".join(out)


def _internal_errors(recorded: list[InternalError], sources: dict[str, str]) -> list[dict]:
    """Each bug once per place in the RAPID, then grouped: type, where in CrossArm, stage, the tokens around."""
    sites = dict.fromkeys(recorded)  # the same statement fails again when its module is converted alone
    grouped: Counter[tuple[str, str, str, str]] = Counter()
    for error in sites:
        window = token_window(sources.get(error.module.upper(), ""), error.line) if error.stage == "statement" else ""
        grouped[(error.kind, error.where, error.stage, window)] += 1
    return [{"type": kind, "where": where, "stage": stage, "tokens": window, "count": count}
            for (kind, where, stage, window), count in sorted(grouped.items())]  # fmt: skip


# ---------------------------------------------------------------------------
# The diagnostic
# ---------------------------------------------------------------------------


def environment() -> dict[str, object]:
    return {
        "os": platform.system() or "unknown",
        "os_release": platform.release() or "",
        "python": platform.python_version(),
        "exe": bool(getattr(sys, "frozen", False)),
        "day": date.today().isoformat(),
    }


def _cause(category: str) -> str:
    return category if category in _KNOWN_CAUSES or _RAPID_CAUSE.match(category) else OTHER_CAUSE


def _by_cause(notes, kind: str) -> dict[str, int]:
    counts = Counter(_cause(note.category) for note in notes if note.kind == kind)
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def _path(path: WorkablePath) -> dict[str, object]:
    """Schema 4: the blocking causes and their TODO, the causes to solve for a workable verdict (the fewest, easiest
    first), the instructions to convert besides, and the verdict with --karel when it differs (null otherwise).
    Causes by their fixed names (_cause)."""
    data = path.data()
    for key in ("blocking_causes", "causes_to_workable"):
        data[key] = {_cause(cause): count for cause, count in data[key].items()}  # type: ignore[union-attr]
    return data


def _uses(table: dict[str, Use]) -> dict[str, dict[str, int]]:
    return {key: table[key].data() for key in sorted(table, key=lambda k: (-table[k].occurrences, k))}


def _signals(eio: Path | None) -> dict[str, object]:
    if eio is None:
        return {"eio": False}
    try:
        records = eio_records(read_source(eio).text)
    except OSError:
        return {"eio": False}
    types = Counter()
    for section, attrs in records:
        if section == "EIO_SIGNAL" and "Name" in attrs:
            kind = attrs.get("SignalType", "").upper()
            types[kind if kind in SIGNAL_TYPES else "other"] += 1
    sections = Counter(section if _SECTION.match(section) else "other" for section, _ in records)
    return {"eio": True, "by_type": {k: types[k] for k in (*SIGNAL_TYPES, "other") if types[k]},
            "eio_sections": dict(sorted(sections.items()))}  # fmt: skip


def _status_table(result) -> tuple[dict[tuple, bool | str], set[tuple[str, int]]]:
    """(module, routine, line, col, node) -> converted (CONDITION_ONLY: an instruction whose condition alone is TODO,
    its blocks converted), for each instruction coverage counted; (module, line) of the warnings."""
    statuses: dict[tuple, bool | str] = {}
    for module in result.modules:
        for routine in module.routines:
            for stmt in [*walk_statements(routine.body), *routine.handlers]:
                if id(stmt) in result.instructions:
                    key = (module.name.upper(), routine.name.upper(), stmt.span.line, stmt.span.col, type(stmt).__name__)
                    statuses[key] = CONDITION_ONLY if id(stmt) in result.gated_ids else result.instructions[id(stmt)]
    module_of = {info.program.name: info.module.upper() for info in result.programs}
    warned = {(module_of[note.program], note.rapid_line) for note in result.notes
              if note.kind == "WARNING" and note.program in module_of and note.rapid_line is not None}  # fmt: skip
    return statuses, warned


def diagnose(paths: list[Path], config: ConversionConfig | None = None, eio: Path | None = None,
             fanuc: list[Path] | None = None) -> dict:  # fmt: skip
    """The diagnostic of what `paths` hold. Raises what pipeline.run raises for an input it cannot read (OSError,
    ValueError); a CrossArm bug during the conversion is in the diagnostic instead."""
    config = config or ConversionConfig()
    rapid, detected = pipeline.split_fanuc(list(paths))
    out = None
    with recording_internal() as recorded, tempfile.TemporaryDirectory(prefix="crossarm_diag_") as temp:
        try:
            out = pipeline.run(list(paths), Path(temp) / "out", config, None, eio, log=lambda _line: None, fanuc=fanuc)
        except (OSError, ValueError, zipfile.BadZipFile):
            raise
        except Exception as exc:  # noqa: BLE001 - the bug is what the diagnostic reports
            recorded.append(InternalError(type(exc).__name__, crossarm_frame(exc), "run"))
        with open_source(rapid) as source:
            system = read_system(source.root)
            eio_path = eio or source.eio or (find_eio(rapid) if source.kind == "files" else None)
            signals = _signals(eio_path)
            kind = source.kind
            parsed_tasks = [(task, pipeline._parse_task(task)) for task in source.tasks if task.files]
        results = {t.task: t.result for t in out.tasks} if out is not None else {}

        inv = _Inventory()
        tasks, sources = [], {}
        modules_count = Counter()
        routines_count = Counter()
        lines = files_not_read = syntax_errors = 0
        all_modules = [p.module for _, (parsed, _) in parsed_tasks for p in parsed if p.module is not None]
        for number, (task, (parsed, errors)) in enumerate(parsed_tasks, 1):
            files_not_read += len(task.files) - len(parsed)
            syntax_errors += len(errors) - (len(task.files) - len(parsed))
            modules = [p.module for p in parsed if p.module is not None]
            names = _Names(modules)
            result = results.get(task.name)
            statuses, warned = _status_table(result) if result is not None else ({}, set())

            skipped = ({(m.upper(), r.upper()): why for m, r, why in result.skipped_routines}
                       if result is not None else {})  # fmt: skip
            funcs = _func_reasons(modules, statuses, result) if result is not None else {}

            def status(module: n.Module, routine: n.Routine, stmt: n.Stmt, system: bool, statuses=statuses,
                       warned=warned, skipped=skipped, funcs=funcs,
                       done=result is not None) -> tuple[str, str | None]:  # fmt: skip
                why = skipped.get((module.name.upper(), routine.name.upper()))
                if why is not None:  # no program, no TODO (coverage counts a PROC or TRAP left out not converted)
                    if routine.kind == "FUNC":
                        return "not_converted", funcs.get(routine.name.upper(), FUNC_NEVER_CALLED)
                    return "not_converted", MOVE_ROUTINE if why.startswith("it wraps one move") else LEFT_OUT
                key = (module.name.upper(), routine.name.upper(), stmt.span.line, stmt.span.col, type(stmt).__name__)
                if key in statuses:
                    if statuses[key] == CONDITION_ONLY:
                        return "todo", CONDITION_ONLY
                    if not statuses[key]:
                        return "todo", None
                    return ("partial" if (module.name.upper(), stmt.span.line) in warned else "converted"), None
                return "not_converted", _not_converted(routine, system, done, config, funcs)

            task_routines = 0
            for parsed_file in parsed:
                module = parsed_file.module
                sources.setdefault(module.name.upper(), parsed_file.text)
                lines += parsed_file.text.count("\n") + (1 if parsed_file.text and not parsed_file.text.endswith("\n") else 0)
                is_sys = _is_system(module, parsed_file, task)
                modules_count["system" if is_sys else "program"] += 1
                for routine in module.routines:
                    routines_count[routine.kind] += 1
                    task_routines += 1
                _count_module(module, names, inv, lambda m, r, s, is_sys=is_sys, status=status: status(m, r, s, is_sys))
            entry: dict[str, object] = {"task": f"task_{number}", "modules": len(modules), "routines": task_routines}
            if result is not None:
                entry.update({
                    "programs": len(result.programs), "instructions": result.coverage.total,
                    "converted_percent": result.coverage.percent if result.coverage.total else None,
                    "todo": result.todo_count, "warnings": sum(1 for x in result.notes if x.kind == "WARNING"),
                    "verdict": verdict(result).level,
                    **_path(path_to_workable(result)),
                })  # fmt: skip
            tasks.append(entry)
        names_all = _Names(all_modules)

        conversion: dict[str, object] = {"completed": out is not None}
        if out is not None:
            notes = [note for t in out.tasks if t.result for note in t.result.notes]
            coverage = out.coverage
            conversion.update({
                "programs": out.programs, "todo": out.todo, "warnings": sum(t.warnings for t in out.tasks),
                "instructions": coverage.total, "converted_percent": coverage.percent if coverage.total else None,
                "converted_by_area": {share.area: share.percent for share in coverage.shares},
                "todo_by_cause": _by_cause(notes, "TODO"), "warnings_by_cause": _by_cause(notes, "WARNING"),
            })  # fmt: skip
            path = run_path(out)
            if path is not None:  # schema 4: every task counted together, as the window's decision
                conversion.update({"verdict": path.level, **_path(path)})
        statements = [use for table in (inv.instructions, inv.user_calls) for use in table.values()]
        on_statements = sum(use.todo for use in statements)
        if out is not None:  # each TODO once: on the statement carrying it, or on none (a routine not found...)
            conversion["todo_on_instructions"] = on_statements
            conversion["todo_not_on_an_instruction"] = out.todo - on_statements
        not_converted = sum((use.not_converted_by for use in statements), Counter())
        conversion["not_converted_by"] = {r: not_converted[r] for r in REASONS if not_converted[r]}
        conversion["tasks"] = tasks

        return {
            "schema_version": SCHEMA_VERSION,
            "crossarm": __version__,
            "environment": environment(),
            "input": {
                "kind": kind,
                "tasks": len(parsed_tasks),
                "modules": {"program": modules_count["program"], "system": modules_count["system"]},
                "routines": {k: routines_count[k] for k in ("PROC", "FUNC", "TRAP")},
                "lines": lines,
                "files_not_read": files_not_read,
                "syntax_errors": syntax_errors,
                "options": {"map": bool(config.mapping_folder), "eio": eio_path is not None,
                            "fanuc": bool(fanuc or detected), "karel": config.karel},
            },
            "system": {"robotware": system.robotware, "options": system.options, "robots": system.robots,
                       "other_product_lines": system.other_lines, "read_from": system.sources},
            "conversion": conversion,
            "instructions": _uses(inv.instructions),
            "functions": _uses(inv.functions),
            "user_calls": _uses(inv.user_calls),
            "data_types": {key: dict(sorted(inv.data_types[key].items())) for key in sorted(inv.data_types)},
            "records": names_all.records_data(),
            "aliases": names_all.aliases,
            "control": {**{k: inv.control[k] for k in CONTROL if inv.control[k]}, "max_nesting": inv.depth},
            "signals": signals,
            "internal_errors": _internal_errors(recorded, sources),
        }


def _not_converted(routine: n.Routine, system: bool, done: bool, config: ConversionConfig,
                   funcs: dict[str, str]) -> str:  # fmt: skip
    """Why a statement of a routine no program holds is not converted."""
    if not done:
        return NOT_COMPLETED
    if routine.name.upper() in {k.upper() for k in config.external_routines}:
        return PROVIDED
    if routine.kind == "FUNC":
        return funcs.get(routine.name.upper(), FUNC_NEVER_CALLED)
    if system:
        return SYSTEM_MODULE
    return NOT_COUNTED


def _func_reasons(modules: list[n.Module], statuses: dict[tuple, bool | str], result) -> dict[str, str]:
    """Why each FUNC of the task has no program, by upper-case name (schema 3): inlined (its body copied into its
    calls, or written as its test), left TODO at its calls (a call in converted code left TODO), computed at
    conversion (every such call converted), never called (no call in the code converted). The calls made by a FUNC
    with no program count as its own calls do: computed or inlined, they are converted; left TODO, TODO."""
    inlined = {k.upper() for k, v in result.inlined.items() if v} | {k.upper() for k, v in result.inlined_sites.items()
                                                                       if v}  # fmt: skip
    funcs = {r.name.upper(): (m, r) for m in reversed(modules) for r in m.routines if r.kind == "FUNC"}
    seen: dict[str, set[str]] = {}

    def key(module: n.Module, routine: n.Routine, stmt: n.Stmt) -> tuple:
        return (module.name.upper(), routine.name.upper(), stmt.span.line, stmt.span.col, type(stmt).__name__)

    def visit(module: n.Module, routine: n.Routine, stmts: Iterable[n.Stmt], forced: str | None) -> None:
        for stmt in stmts:
            state, whole = forced, forced == "todo"
            if forced is None:
                value = statuses.get(key(module, routine, stmt))
                if value is not None:
                    state = "todo" if value is False or value == CONDITION_ONLY else "converted"
                    whole = value is False
            if state is not None and not isinstance(stmt, n.Unsupported):
                for call in _calls(_expressions(stmt)):
                    seen.setdefault(call.name.upper(), set()).add(state)
            visit(module, routine, _blocks(stmt), "todo" if whole else forced)

    programmed = set()
    for module in modules:
        for routine in module.routines:
            statements = [*walk_statements(routine.body), *routine.handlers]
            if any(key(module, routine, stmt) in statuses for stmt in statements):
                programmed.add(routine.name.upper())
                visit(module, routine, [*routine.body, *routine.handlers], None)

    def reason(name: str) -> str:
        if name in inlined:
            return FUNC_INLINED
        states = seen.get(name, set())
        return FUNC_TODO if "todo" in states else FUNC_COMPUTED if "converted" in states else FUNC_NEVER_CALLED

    reasons: dict[str, str] = {}
    for _ in range(len(funcs) + 1):  # a FUNC called by a FUNC with no program: until nothing changes
        now = {name: reason(name) for name in funcs if name not in programmed}
        if now == reasons:
            break
        reasons = now
        for name, why in now.items():
            if why != FUNC_NEVER_CALLED:
                module, routine = funcs[name]
                visit(module, routine, [*routine.body, *routine.handlers], "todo" if why == FUNC_TODO else "converted")
    return reasons


def _is_system(module: n.Module, parsed: ParseResult, task) -> bool:
    if task.data_files and Path(parsed.path) in set(task.data_files):
        return True
    return any(attr.upper() == "SYSMODULE" for attr in module.attributes)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def write(diag: dict, folder: Path) -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    as_json, as_md = folder / DIAG_JSON, folder / DIAG_MD
    as_json.write_text(json.dumps(diag, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    as_md.write_text(markdown(diag), encoding="utf-8")
    return as_json, as_md


def _cell(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:g} %"
    return str(value).replace("|", "\\|")


def _table(head: list[str], rows: Iterable[list[object]]) -> list[str]:
    rows = list(rows)
    if not rows:
        return ["(none)", ""]
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return [*out, ""]


def _reasons(counts: dict[str, int]) -> str:
    return ", ".join(f"{reason} {count}" for reason, count in counts.items()) or "-"


def _uses_table(title: str, table: dict[str, dict]) -> list[str]:
    """Uses = Converted + Partial + TODO + Inside TODO + Not converted, on every row."""
    head = ["Name", "Uses", "Converted", "Partial", "TODO", "Inside TODO", "Not converted", "Why not converted"]
    return [f"## {title}", "", *_table(head, ([k, v["occurrences"], v["converted"], v["partial"], v["todo"],
                                               v["inside_todo"], v["not_converted"], _reasons(v["not_converted_by"])]
                                              for k, v in table.items()))]  # fmt: skip


def _path_lines(conv: dict) -> list[str]:
    """Schema 4: the verdict, its blocking causes and what would make it workable (older diagnostics: nothing)."""
    if "blocking_causes" not in conv:
        return []
    lines = [f"- Verdict: {conv['verdict']}, blocking causes: " + (", ".join(f"{k} {v}" for k, v in
             conv["blocking_causes"].items()) or "none")]  # fmt: skip
    if conv["causes_to_workable"] or conv["instructions_to_workable"]:
        lines.append("- To workable: " + ", ".join([*(f"{k} {v}" for k, v in conv["causes_to_workable"].items()),
                     *([f"{conv['instructions_to_workable']} instructions"] if conv["instructions_to_workable"] else [])]))  # fmt: skip
    if conv["verdict_with_karel"]:
        lines.append(f"- Verdict with --karel: {conv['verdict_with_karel']}")
    return lines


def markdown(diag: dict) -> str:
    """crossarm_diag.md, made from the diagnostic alone: what the user reads is what they would send."""
    env, inp, system, conv = diag["environment"], diag["input"], diag["system"], diag["conversion"]
    lines = [
        "# CrossArm diagnostic report",
        "",
        "Counts only: no name, comment, text, number or path of the backup is in this report or in crossarm_diag.json.",
        "",
        f"- Schema version: {diag['schema_version']}",
        f"- CrossArm {diag['crossarm']}, Python {env['python']}, {env['os']} {env['os_release']}"
        + (", CrossArm.exe" if env["exe"] else "") + f", {env['day']}",
        (f"- Input: {inp['kind']}, {inp['tasks']} task(s), {inp['modules']['program']} program module(s), "
        f"{inp['modules']['system']} system module(s), {inp['lines']} lines"),
        "- Routines: " + ", ".join(f"{v} {k}" for k, v in inp["routines"].items()),
        f"- Files not read: {inp['files_not_read']}, syntax errors: {inp['syntax_errors']}",
        "- Options: " + ", ".join(f"{k} {_cell(v)}" for k, v in inp["options"].items()),
        "",
        "## System",
        "",
        f"- RobotWare: {system['robotware'] or 'not found'}",
        "- Options: " + ("; ".join(system["options"]) or "none found"),
        "- Robots: " + ("; ".join(system["robots"]) or "none found"),
        f"- Other product lines (not kept): {system['other_product_lines']}",
        "",
        "## Conversion",
        "",
    ]
    if conv["completed"]:
        lines += [
            f"- Programs: {conv['programs']}, TODO: {conv['todo']}, warnings: {conv['warnings']}",
            f"- Instructions: {conv['instructions']}, converted: {_cell(conv['converted_percent'])}",
            (f"- TODO on an instruction: {conv['todo_on_instructions']}, "
             f"not on an instruction: {conv['todo_not_on_an_instruction']}"),
            f"- Instructions in no program: {_reasons(conv['not_converted_by'])}",
            *_path_lines(conv),
            "",
            *_table(["Area", "Converted"], ([k, v] for k, v in conv["converted_by_area"].items())),
            "### TODO by cause", "",
            *_table(["Cause", "TODO"], ([k, v] for k, v in conv["todo_by_cause"].items())),
            "### Warnings by cause", "",
            *_table(["Cause", "Warnings"], ([k, v] for k, v in conv["warnings_by_cause"].items())),
        ]  # fmt: skip
    else:
        lines += ["The conversion did not complete: see Internal errors.", ""]
    task_head = ["Task", "Modules", "Routines", "Programs", "Instructions", "Converted", "TODO", "Warnings", "Verdict"]
    task_keys = ["task", "modules", "routines", "programs", "instructions", "converted_percent", "todo", "warnings",
                 "verdict"]  # fmt: skip
    lines += ["### Tasks", "", *_table(task_head, ([t.get(k) for k in task_keys] for t in conv["tasks"]))]
    lines += _uses_table("RAPID instructions", diag["instructions"])
    lines += _uses_table("RAPID functions", diag["functions"])
    lines += _uses_table("Calls of the backup's routines (by parameter types)", diag["user_calls"])
    lines += ["## Data types", "", *_table(["Type", "Declarations"],
                                           ([k, ", ".join(f"{s} {c}" for s, c in v.items())]
                                            for k, v in diag["data_types"].items()))]  # fmt: skip
    lines += ["## Records", "", *_table(["Record", "Field types"],
                                        ([k, ", ".join(v)] for k, v in diag["records"].items()))]  # fmt: skip
    lines += [f"Aliases: {diag['aliases']}", ""]
    lines += ["## Control constructs", "", *_table(["Construct", "Count"], ([k, v] for k, v in diag["control"].items()))]
    sig = diag["signals"]
    lines += ["## Signals", ""]
    if sig["eio"]:
        lines += [*_table(["Type", "Signals"], ([k, v] for k, v in sig["by_type"].items())),
                  *_table(["EIO.cfg section", "Records"], ([k, v] for k, v in sig["eio_sections"].items()))]  # fmt: skip
    else:
        lines += ["No EIO.cfg read.", ""]
    lines += ["## Internal errors", "", *_table(["Type", "Where in CrossArm", "Stage", "RAPID around (categories)",
                                                 "Count"],
                                                ([e["type"], e["where"], e["stage"], e["tokens"] or "-", e["count"]]
                                                 for e in diag["internal_errors"]))]  # fmt: skip
    return "\n".join(lines).rstrip("\n") + "\n"


def default_folder(paths: list[Path]) -> Path:
    """crossarm_diag_<name> next to the input: the name is only in the local path, never in the files."""
    first = Path(paths[0]).resolve()
    name = first.stem if first.is_file() else first.name
    return first.parent / f"crossarm_diag_{name or 'input'}"


__all__ = ["DIAG_JSON", "DIAG_MD", "SCHEMA_VERSION", "default_folder", "diagnose", "markdown", "token_window", "write"]
