# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A condition CrossArm cannot convert no longer takes its blocks with it (a mixin of the routine translator).

An IF, ELSEIF, WHILE or TEST whose test cannot be written in TP (the operating mode, an answer read from the
operator, a FUNC that does not convert...) is written whole, its blocks converted, with the test alone left to the
integrator: it reads a flag (a register for a TEST) CrossArm reserves for it, set by a line the integrator writes in
place of a jump. Until then, the jump skips the whole instruction: no block of it runs, the ELSE and the other
branches neither, as when the whole instruction was a TODO remark; a WHILE does not turn. A FOR whose bound cannot
be written counts to a reserved register the same way (translate.for_bound): skipped, it does not turn.

    IF OpMode() = OP_AUTO THEN                  !TODO l.12 IF OpMode() = OP_AUTO THEN
        MoveL pPick, v500, z10, tGrip;          !Replace JMP by F[3]=(...)
    ELSE                                        JMP LBL[2]
        Stop;                                   IF (F[3]=ON) THEN
    ENDIF                                       L P[1] 500mm/sec CNT10
                                                ELSE
                                                PAUSE
                                                ENDIF
                                                LBL[2]

    WHILE OpMode() <> OP_AUTO DO                LBL[1]
        WaitTime 1;                             !TODO l.20 WHILE OpMode() <> OP_AUTO DO
    ENDWHILE                                    !Replace JMP by F[4]=(...)
                                                JMP LBL[2]
                                                IF (F[4]=OFF) THEN    (F[4]: the condition)
                                                JMP LBL[2]
                                                ENDIF
                                                WAIT 1.00(sec)
                                                JMP LBL[1]
                                                LBL[2]

The line the integrator writes sets the flag where the instruction starts: before the IF for each of its tests (an
ELSEIF's too), at the top of each turn for a WHILE. Each jump, remark, flag and the IF / WHILE / SELECT reading it
are forms the programs already use (measured on ROBOGUIDE, `condgate` probe). The flag's mapping key is
`CROSSARM.CONDITION.<ROUTINE>.L<line>` (a register's for a TEST): a key added, as the 1.x mapping allows.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from crossarm.convert.blockers import Untranslatable
from crossarm.convert.compute import Unresolvable
from crossarm.convert.tp_numbers import ascii_text
from crossarm.fanuc.tp import Instruction
from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr

if TYPE_CHECKING:
    from crossarm.convert.translate import Converter

T = TypeVar("T")
KEY = "CROSSARM.CONDITION."  # the mapping key of a reserved flag or register: CROSSARM.CONDITION.MAIN.L12
GATE = "CrossArmCondition"  # the name the stand-in of a condition carries in the tree (never written)
CONDITION = {"IF": "condition", "WHILE": "condition", "TEST": "value", "FOR": "bound"}
# The words a TODO left this way carries: what the reports tell it by (crossarm.convert.analysis, checklist).
MARK = " is written with its blocks, its "


@dataclass(frozen=True, slots=True)
class GatedCondition:
    """A condition left to the integrator in an instruction written whole."""

    program: str  # the TP program
    line: int  # the RAPID line of the condition (an ELSEIF's own)
    statement_line: int  # the RAPID line of the instruction (IF, WHILE, TEST)
    slot: str  # 'F[3]', or 'R[40]' for a TEST's value
    rapid: str  # the RAPID condition (or TEST value), as written
    label: int  # the JMP LBL[label] line to replace
    reason: str  # why it is not converted
    category: str  # its cause (crossarm.convert.blockers.Blocker)
    what: str = "IF"  # the instruction: IF, WHILE, TEST, FOR (whose bound it is)


@dataclass(slots=True)
class _Pending:
    line: int
    slot: str
    rapid: str
    reason: str
    category: str
    what: str  # "IF", "WHILE", "TEST"


class ConditionGates:
    """The routine translator's part. Needs: c, name, lines, tags, strict, current, label(), emit(), todo_cause()."""

    c: "Converter"
    name: str
    strict: int
    gates: list[list[_Pending]]
    gate_names: dict[int, tuple[n.Expr, str]]
    gate_keys: set[str]
    gate_notes: list[int]

    def gate_open(self) -> int:
        """Starts an instruction whose conditions may be left to the integrator: where its gates go."""
        self.gates.append([])
        self.gate_notes.append(len(self.c.result.notes))
        return len(self.lines)  # type: ignore[attr-defined]

    def gate_drop(self) -> None:
        """The instruction failed as a whole (it is a TODO remark): its gates go with it."""
        self.gates.pop()
        self.gate_notes.pop()

    def gated(self, expr: n.Expr, write: Callable[[n.Expr], T], what: str = "IF") -> T:
        """write(expr), or, when the condition cannot be written, write() of the flag standing for it: the lines it
        wrote before failing are dropped. In a statement that must convert whole (strict), it fails."""
        if self.strict or not self.gates or self.is_gate(expr):
            return write(expr)
        mark = len(self.lines)  # type: ignore[attr-defined]
        try:
            return write(expr)
        except (Untranslatable, Unresolvable) as exc:
            del self.lines[mark:]  # type: ignore[attr-defined]
            return write(self.gate_flag(expr, exc, what))

    def gate_flag(self, expr: n.Expr, exc: BaseException, what: str = "IF") -> n.Expr:
        """The stand-in of a condition that cannot be written: a name the condition writer reads as its flag."""
        from crossarm.convert.translate import _comment

        text = " ".join(_text(expr).split())
        key = self._gate_key(expr.span.line)
        number = self.c.flags.number(text, key, "", by_name=False)
        slot = f"F[{number}]"
        self._pending(expr, exc, slot, text, what)
        stand_in = n.Name(expr.span, GATE)
        self.gate_names[id(stand_in)] = (stand_in, f"F[{number}:{_comment(text)}]")
        return stand_in

    def gate_register(self, expr: n.Expr, exc: BaseException, what: str = "TEST") -> str:
        """The register a TEST selects on (a FOR counts to) when its value cannot be written: R[n], set by the
        integrator."""
        from crossarm.convert.translate import _comment

        if self.strict or not self.gates:
            raise exc
        text = " ".join(_text(expr).split())
        key = self._gate_key(expr.span.line)
        number = self.c.registers.number(text, key, "")
        self._pending(expr, exc, f"R[{number}]", text, what)
        return f"R[{number}:{_comment(text)}]"

    def is_gate(self, expr: n.Expr) -> bool:
        found = self.gate_names.get(id(expr))
        return found is not None and found[0] is expr

    def gate_condition(self, expr: n.Expr, negate: bool) -> str | None:
        """'F[3]=ON' for the stand-in of a condition (OFF negated), None for any other expression."""
        found = self.gate_names.get(id(expr))
        if found is None or found[0] is not expr:
            return None
        return f"{found[1]}={'OFF' if negate else 'ON'}"

    def gate_close(self, top: int, end: int | None = None) -> int | None:
        """Writes the gates of the instruction started at `top`, each jumping to LBL[end] (a new label when None,
        which the caller writes after the instruction): the label, None when every condition was written."""
        from crossarm.convert.translate import REMARK_MAX

        pending, notes = self.gates.pop(), self.gate_notes.pop()
        if not pending:
            return None
        end = self.label() if end is None else end  # type: ignore[attr-defined]
        statement = self.current  # type: ignore[attr-defined]
        lines: list[Instruction] = []
        for gate in pending:
            source = self._source_line(gate.line) or f"{gate.what} {gate.rapid}"
            written = [Instruction(("!" + ascii_text(f"TODO l.{gate.line} {source.rstrip(';')}")[:REMARK_MAX]).rstrip()),
                       Instruction(f"!Replace JMP by {gate.slot}=(...)"),
                       Instruction(f"JMP LBL[{end}]")]  # fmt: skip
            self.tags.tag(written, 0, gate.line)  # type: ignore[attr-defined]
            lines += written
            self.c.result.gated.append(GatedCondition(self.name, gate.line, statement.span.line, gate.slot, gate.rapid,
                                                      end, gate.reason, gate.category, gate.what))  # fmt: skip
        self.lines[top:top] = lines  # type: ignore[attr-defined]
        first = pending[0]
        source = self._source_line(first.line) or f"{first.what} {first.rapid}"
        more = [f"l.{g.line} `{g.rapid[:40]}` ({g.slot})" for g in pending[1:]]
        reason = (f"{first.reason}; the {first.what} is written with its blocks, its {CONDITION[first.what]} left to"
                  f" set in {first.slot} by the line replacing JMP LBL[{end}] (until then the {first.what} is"
                  " skipped)")  # fmt: skip
        if more:
            reason += f"; also {', '.join(more)}"
        self.c.note(self.name, first.line, "TODO", f"{reason} — `{' '.join(source.split())[:80]}`", first.category)
        self.c.result.notes.insert(notes, self.c.result.notes.pop())  # before those of its blocks, in line order
        self.c.not_converted.add(id(statement))  # the instruction itself, not its blocks
        self.c.result.gated_ids.add(id(statement))
        return end

    def _pending(self, expr: n.Expr, exc: BaseException, slot: str, text: str, what: str) -> None:
        probe: n.Stmt
        if what == "TEST":
            probe = n.Test(expr.span, expr, ())
        elif what == "WHILE":
            probe = n.While(expr.span, expr, ())
        elif what == "FOR":
            probe = n.For(expr.span, "i", expr, expr, None, ())
        else:
            probe = n.If(expr.span, (n.IfBranch(expr, ()),), ())
        reason, category = self.todo_cause(probe, exc)  # type: ignore[attr-defined]
        self.gates[-1].append(_Pending(expr.span.line, slot, text, reason, category, what))

    def _gate_key(self, line: int) -> str:
        base = f"{KEY}{self.routine.name.upper()}.L{line}"  # type: ignore[attr-defined]
        key, k = base, 1
        while key in self.gate_keys:  # two conditions on one line
            k += 1
            key = f"{base}.{k}"
        self.gate_keys.add(key)
        return key

    def _source_line(self, line: int) -> str:
        lines = self.c.source_lines.get(self.module.name.upper())  # type: ignore[attr-defined]
        if lines and 0 < line <= len(lines):
            text = lines[line - 1]
            if '"' not in text:
                text = text.split("!", 1)[0]
            return " ".join(text.split())
        return ""


def _text(expr: n.Expr) -> str:
    return format_expr(expr)
