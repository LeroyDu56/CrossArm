# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""ASCII .LS text -> FANUC TP program model: the reverse of ls_writer.

The contract is losslessness: for any file a controller exported,

    write_ls(parse_ls(text)) == text

That is what makes the parser trustworthy without a controller at hand. Every
committed .LS fixture and every file of the local test corpus is checked against it.
To hold it, the parser keeps what the controller wrote rather than what CrossArm
would write: the spaces before each ';', the task control values, the /APPL lines,
and '.000' / '-.000' (a value that rounds to zero but is not zero).

Anything it does not understand raises LSFormatError with the line number, instead
of being guessed or dropped: position comments, several motion groups and extended
axes are not modelled yet.
"""

import math
import re
from datetime import datetime
from pathlib import Path

from crossarm.fanuc.tp import (
    Attributes,
    CartesianPosition,
    Instruction,
    JointPosition,
    Line,
    Motion,
    Position,
    Program,
)


class LSFormatError(ValueError):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line


_PROG = re.compile(r"/PROG  (\S+)(\t  Macro)?")
_ATTR = re.compile(r"(?:TCD:)?\s*(\w+)\t+= (.*?)[;,]")
_NUMBERED = re.compile(r"\s*(\d+):(.*)")
_CONTINUATION = re.compile(r" {4}:(.*)")
_TERMINATED = re.compile(r"(.*?)( *);")
_MOTION_KINDS = frozenset("JLCA")

_POS_START = re.compile(r"P\[(\d+)\]\{")
_POS_FRAMES = re.compile(r"\tUF : (\d+), UT : (\d+),(?:\t|\t\tCONFIG : '([^']*)',)")
_NUMBER = r"\s*(-?\d*\.\d+)"
_CART_XYZ = re.compile(rf"\tX ={_NUMBER}  mm,\tY ={_NUMBER}  mm,\tZ ={_NUMBER}  mm,")
_CART_WPR = re.compile(rf"\tW ={_NUMBER} deg,\tP ={_NUMBER} deg,\tR ={_NUMBER} deg")
_JOINTS_1 = re.compile(rf"\tJ1={_NUMBER} deg,\tJ2={_NUMBER} deg,\tJ3={_NUMBER} deg,")
_JOINTS_2 = re.compile(rf"\tJ4={_NUMBER} deg,\tJ5={_NUMBER} deg,\tJ6={_NUMBER} deg")

_DATE = "DATE %y-%m-%d  TIME %H:%M:%S"
_INT_FIELDS = {
    "PROG_SIZE": "prog_size", "MEMORY_SIZE": "memory_size", "VERSION": "version",
    "STACK_SIZE": "stack_size", "TASK_PRIORITY": "task_priority", "TIME_SLICE": "time_slice",
    "BUSY_LAMP_OFF": "busy_lamp_off", "ABORT_REQUEST": "abort_request", "PAUSE_REQUEST": "pause_request",
}  # fmt: skip
_TEXT_FIELDS = {
    "OWNER": "owner", "FILE_NAME": "file_name", "PROTECT": "protect",
    "DEFAULT_GROUP": "default_group", "CONTROL_CODE": "control_code", "LOCAL_REGISTERS": "local_registers",
}  # fmt: skip


def controller_number(text: str) -> float:
    """A /POS number as the controller printed it.

    The controller writes '.000' or '-.000' for a value that rounds to zero but is
    not zero, and '0.000' only for an exact zero. Reading both as 0.0 would lose
    that, and the program would no longer write back identically: keep a value
    small enough to be irrelevant (1e-9 mm or deg) that prints the same way.
    """
    value = float(text)
    if value == 0 and text.strip() != "0.000":
        return math.copysign(1e-9, value)
    return value


def read_ls(path: str | Path) -> Program:
    data = Path(path).read_bytes()
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        text = data.decode("cp1252")  # hand-edited files sometimes carry accents in comments
    return parse_ls(text)


def parse_ls(text: str) -> Program:
    # Split on the file's own line ending only. Real CRLF exports carry stray bare LFs
    # inside /APPL; splitting on those too would lose them.
    return _Parser(text.split("\r\n" if "\r\n" in text else "\n")).program()


class _Parser:
    def __init__(self, lines: list[str]) -> None:
        if lines and lines[-1] == "":
            lines.pop()  # the final CRLF
        self.lines = lines
        self.i = 0

    # -- cursor ------------------------------------------------------------------

    def peek(self) -> str | None:
        return self.lines[self.i] if self.i < len(self.lines) else None

    def take(self) -> str:
        line = self.peek()
        if line is None:
            raise LSFormatError(self.i + 1, "unexpected end of file")
        self.i += 1
        return line

    def error(self, message: str) -> LSFormatError:
        return LSFormatError(self.i, message)  # self.i is 1-based once the line was taken

    def expect(self, literal: str) -> None:
        if self.take() != literal:
            raise self.error(f"expected {literal!r}")

    # -- sections ------------------------------------------------------------------

    def program(self) -> Program:
        m = _PROG.fullmatch(self.take())
        if not m:
            raise self.error("expected '/PROG  NAME'")
        name, macro = m[1], bool(m[2])
        self.expect("/ATTR")
        attributes = self.attributes()
        if self.peek() == "/APPL":
            self.take()
            appl = []
            while self.peek() is not None and not self.peek().startswith("/"):  # type: ignore[union-attr]
                appl.append(self.take())
            attributes.appl = tuple(appl)
        self.expect("/MN")
        lines, extra = self.body()
        self.expect("/POS")
        positions = self.positions()
        self.expect("/END")
        if self.peek() is not None:
            self.take()
            raise self.error("text after /END")
        return Program(name, lines, positions, attributes, macro, extra)

    def attributes(self) -> Attributes:
        attrs = Attributes()
        seen_created = False
        while self.peek() is not None and not self.peek().startswith("/"):  # type: ignore[union-attr]
            m = _ATTR.fullmatch(self.take())
            if not m:
                raise self.error("unreadable /ATTR line")
            key, value = m[1], m[2]
            if key in _INT_FIELDS:
                setattr(attrs, _INT_FIELDS[key], int(value))
            elif key in _TEXT_FIELDS:
                setattr(attrs, _TEXT_FIELDS[key], value)
            elif key == "COMMENT":
                if not (len(value) >= 2 and value[0] == value[-1] == '"'):
                    raise self.error("COMMENT must be quoted")
                attrs.comment = value[1:-1]
            elif key in ("CREATE", "MODIFIED"):
                try:
                    date = datetime.strptime(value, _DATE)
                except ValueError as exc:
                    raise self.error(f"{key}: {exc}") from exc
                if key == "CREATE":
                    attrs.created, seen_created = date, True
                else:
                    attrs.modified = date
            elif key == "LINE_COUNT":
                attrs.line_count = int(value)  # not always the number of /MN lines: kept as written
            else:
                raise self.error(f"unknown /ATTR field {key}")
        if not seen_created:
            raise self.error("/ATTR has no CREATE date")
        return attrs

    def body(self) -> tuple[list[Line], tuple[str, ...]]:
        lines: list[Line] = []
        extra: list[str] = []
        while self.peek() is not None and not self.peek().startswith("/"):  # type: ignore[union-attr]
            raw = self.take()
            if not raw.strip():
                extra.append(raw)  # blank lines are only accepted after the last numbered one
                continue
            m = _NUMBERED.fullmatch(raw)
            if not m or extra:
                raise self.error("expected a numbered /MN line")
            if int(m[1]) != len(lines) + 1:
                raise self.error(f"line number {m[1]}, expected {len(lines) + 1}")
            lines.append(self.line(m[2]))
        return lines, tuple(extra)

    def line(self, body: str) -> Line:
        if body[:1] in _MOTION_KINDS and body[1:2] == " ":
            return self.motion(body[0], body[2:])
        if body == "   ;":
            return Instruction("")
        if not body.startswith("  "):
            raise self.error("an instruction starts two spaces after the colon")
        m = _TERMINATED.fullmatch(body[2:])
        if not m:
            raise self.error("instruction without ';'")
        return Instruction(m[1], len(m[2]))

    def motion(self, kind: str, rest: str) -> Motion:
        via = None
        if kind == "C":
            via, tail = _token(rest)
            if tail.strip():
                raise self.error("unexpected text after the circle point")
            m = _CONTINUATION.fullmatch(self.take())
            if not m or not m[1].startswith("  "):
                raise self.error("a circular motion continues on a '    :' line")
            rest = m[1][2:]
        target, rest = _token(rest)
        m = _TERMINATED.fullmatch(rest)
        if not m:
            raise self.error("motion without ';'")
        speed, rest = _token(m[1])
        termination, options = _token(rest)
        if not termination:
            raise self.error("motion without a termination (FINE / CNT)")
        return Motion(kind, target, speed, termination, via, options, len(m[2]))

    def positions(self) -> list[Position]:
        positions = []
        while self.peek() is not None and not self.peek().startswith("/"):  # type: ignore[union-attr]
            positions.append(self.position())
        return positions

    def position(self) -> Position:
        start = self.take()
        m = _POS_START.fullmatch(start)
        if not m:
            if start.startswith("P["):
                raise self.error("position comments are not supported yet")
            raise self.error("expected 'P[n]{'")
        number = int(m[1])
        if self.take() != "   GP1:":
            raise self.error("only motion group 1 is supported")
        frames = _POS_FRAMES.fullmatch(self.take())
        if not frames:
            raise self.error("expected the 'UF : n, UT : n,' line")
        uf, ut, config = int(frames[1]), int(frames[2]), frames[3]
        first, second = self.take(), self.take()
        value: CartesianPosition | JointPosition
        if config is not None:
            xyz, wpr = _CART_XYZ.fullmatch(first), _CART_WPR.fullmatch(second)
            if not (xyz and wpr):
                raise self.error("expected X, Y, Z then W, P, R")
            x, y, z = (controller_number(v) for v in xyz.groups())
            w, p, r = (controller_number(v) for v in wpr.groups())
            value = CartesianPosition(x, y, z, w, p, r, config)
        else:
            j13, j46 = _JOINTS_1.fullmatch(first), _JOINTS_2.fullmatch(second)
            if not (j13 and j46):
                raise self.error("expected J1..J6 on two lines (extended axes are not supported yet)")
            value = JointPosition(tuple(controller_number(v) for v in j13.groups() + j46.groups()))
        self.expect("};")
        return Position(number, uf, ut, value)


def _token(text: str) -> tuple[str, str]:
    """First space-separated token, brackets kept whole ('PR[1:Home pos]'), and the rest
    as written, minus the one separating space."""
    depth = 0
    for i, ch in enumerate(text):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch == " " and depth == 0:
            return text[:i], text[i + 1 :]
    return text, ""


__all__ = ["LSFormatError", "controller_number", "parse_ls", "read_ls"]
