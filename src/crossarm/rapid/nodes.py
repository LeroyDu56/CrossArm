# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID abstract syntax tree.

The tree mirrors RAPID faithfully and contains no FANUC concept: mapping to TP
is the job of a later layer. Nodes are immutable; child sequences are tuples.

Three families of statements:
  * V1 conversion targets, typed precisely: Move, SetSignal, WaitTime,
    ProcCall (no arguments), If, For, Assign, Comment, DataDecl.
  * Structural statements parsed so that the V1 statements they contain stay
    visible (e.g. the main loop is a WHILE): While, Test, Return, Exit, and
    ProcCall with arguments.
  * Unsupported: constructs deliberately left out of V1 (RECORD, error
    handlers, GOTO, late binding...). Their raw source text is preserved.
"""

from dataclasses import dataclass
from enum import Enum

from crossarm.diagnostics import Span

# --------------------------------------------------------------------------
# Expressions
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Number:
    span: Span
    value: int | float
    text: str  # as written, e.g. "9E+09"


@dataclass(frozen=True, slots=True)
class String:
    span: Span
    value: str


@dataclass(frozen=True, slots=True)
class Bool:
    span: Span
    value: bool


@dataclass(frozen=True, slots=True)
class Name:
    span: Span
    name: str


@dataclass(frozen=True, slots=True)
class Aggregate:
    """Array/record literal: [x, y, z] — robtargets are nested aggregates."""

    span: Span
    items: tuple["Expr", ...]


@dataclass(frozen=True, slots=True)
class Component:
    """Record field access: p10.trans.x"""

    span: Span
    base: "Expr"
    field: str


@dataclass(frozen=True, slots=True)
class Index:
    """Array element: reg{2} or matrix{i, j}"""

    span: Span
    base: "Expr"
    indices: tuple["Expr", ...]


@dataclass(frozen=True, slots=True)
class UnaryOp:
    span: Span
    op: str  # "-", "+", "NOT"
    operand: "Expr"


@dataclass(frozen=True, slots=True)
class BinaryOp:
    span: Span
    op: str  # arithmetic, comparison, AND/OR/XOR, DIV/MOD — keywords upper-cased
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True, slots=True)
class Arg:
    """One argument of a procedure or function call.

    positional:          value set, name None             MoveL p10, ...
    optional:            name and value set               \\WObj:=wobj1
    switch:              name set, value None             \\NoEOffs
    conditional:         name and value, conditional=True \\WObj?wobj
    """

    span: Span
    value: "Expr | None"
    name: str | None = None
    conditional: bool = False


@dataclass(frozen=True, slots=True)
class FuncCall:
    span: Span
    name: str
    args: tuple[Arg, ...]


Expr = Number | String | Bool | Name | Aggregate | Component | Index | UnaryOp | BinaryOp | FuncCall

# --------------------------------------------------------------------------
# Statements
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Comment:
    span: Span
    text: str


@dataclass(frozen=True, slots=True)
class DataDecl:
    """CONST robtarget p10 := [...];  LOCAL PERS num n := 0;  VAR string s{3};"""

    span: Span
    storage: str  # "CONST" | "VAR" | "PERS"
    type_name: str
    name: str
    dims: tuple[Expr, ...] = ()
    init: Expr | None = None
    scope: str | None = None  # "LOCAL" | "TASK" | None


class MoveKind(Enum):
    J = "J"  # MoveJ
    L = "L"  # MoveL
    C = "C"  # MoveC
    ABSJ = "ABSJ"  # MoveAbsJ (joint target)


@dataclass(frozen=True, slots=True)
class Move:
    """MoveJ / MoveL / MoveC / MoveAbsJ with its arguments identified by role."""

    span: Span
    kind: MoveKind
    to_point: Expr
    speed: Expr
    zone: Expr
    tool: Expr
    via_point: Expr | None = None  # MoveC circle point
    wobj: Expr | None = None
    options: tuple[Arg, ...] = ()  # remaining optional args: \Conc, \V, \Z, \NoEOffs...


@dataclass(frozen=True, slots=True)
class SetSignal:
    """Set sig; (value 1) / Reset sig; (value 0)"""

    span: Span
    signal: Expr
    value: int


@dataclass(frozen=True, slots=True)
class WaitTime:
    span: Span
    seconds: Expr
    options: tuple[Arg, ...] = ()  # \InPos


@dataclass(frozen=True, slots=True)
class ProcCall:
    """Any other procedure call. V1 conversion only covers calls without args."""

    span: Span
    name: str
    args: tuple[Arg, ...] = ()


@dataclass(frozen=True, slots=True)
class Assign:
    span: Span
    target: Expr
    value: Expr


@dataclass(frozen=True, slots=True)
class IfBranch:
    condition: Expr
    body: tuple["Stmt", ...]


@dataclass(frozen=True, slots=True)
class If:
    """IF/ELSEIF/ELSE/ENDIF. compact=True for the one-line form 'IF cond stmt;'."""

    span: Span
    branches: tuple[IfBranch, ...]  # IF + each ELSEIF, in order
    else_body: tuple["Stmt", ...] = ()
    compact: bool = False


@dataclass(frozen=True, slots=True)
class For:
    span: Span
    var: str
    start: Expr
    end: Expr
    step: Expr | None
    body: tuple["Stmt", ...]


@dataclass(frozen=True, slots=True)
class While:
    span: Span
    condition: Expr
    body: tuple["Stmt", ...]


@dataclass(frozen=True, slots=True)
class TestCase:
    values: tuple[Expr, ...]
    body: tuple["Stmt", ...]


@dataclass(frozen=True, slots=True)
class Test:
    """TEST expr CASE a, b: ... DEFAULT: ... ENDTEST"""

    span: Span
    subject: Expr
    cases: tuple[TestCase, ...]
    default: tuple["Stmt", ...] | None = None


@dataclass(frozen=True, slots=True)
class Return:
    span: Span
    value: Expr | None = None


@dataclass(frozen=True, slots=True)
class Exit:
    span: Span


@dataclass(frozen=True, slots=True)
class Unsupported:
    """A construct outside the V1 scope, or one the parser could not read.

    kind is a stable tag (RECORD, ERROR_HANDLER, GOTO, LATE_BINDING, SYNTAX_ERROR...),
    raw is the exact source text so nothing is silently lost.
    """

    span: Span
    kind: str
    reason: str
    raw: str


Stmt = (
    Comment | DataDecl | Move | SetSignal | WaitTime | ProcCall | Assign
    | If | For | While | Test | Return | Exit | Unsupported
)  # fmt: skip

# --------------------------------------------------------------------------
# Routines and modules
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Routine:
    span: Span
    kind: str  # "PROC" | "FUNC" | "TRAP"
    name: str
    body: tuple[Stmt, ...]
    params: str = ""  # raw parameter list; parameterised routines are out of V1 scope
    return_type: str | None = None  # FUNC only
    scope: str | None = None  # "LOCAL" | None
    handlers: tuple[Unsupported, ...] = ()  # ERROR / UNDO / BACKWARD sections


ModuleItem = Comment | DataDecl | Routine | Unsupported


@dataclass(frozen=True, slots=True)
class Module:
    span: Span
    name: str
    attributes: tuple[str, ...]  # SYSMODULE, NOSTEPIN, ...
    body: tuple[ModuleItem, ...]  # source order is preserved

    @property
    def routines(self) -> tuple[Routine, ...]:
        return tuple(item for item in self.body if isinstance(item, Routine))

    @property
    def declarations(self) -> tuple[DataDecl, ...]:
        return tuple(item for item in self.body if isinstance(item, DataDecl))
