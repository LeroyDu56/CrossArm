# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID lexer: source text -> tokens (+ comments kept aside).

The lexer never raises: an unexpected character becomes a diagnostic and is
skipped, so that a single odd byte cannot hide the rest of a program.
"""

import re
from dataclasses import dataclass

from crossarm.diagnostics import Diagnostic, Severity, Span
from crossarm.rapid.tokens import OPERATORS, RESERVED_WORDS, CommentToken, Token, TokenKind

# Letters of any script are kept in a name (a real project names a routine `Ñ`): the branch in run() and this
# pattern must agree, or the lexer would raise on a character one accepts and the other does not.
_IDENT_RE = re.compile(r"[^\W\d]\w*")
_DIGITS = "0123456789"  # str.isdigit() also accepts '²', which _NUMBER_RE does not
# 12, 1.5, 1., .5, 9E+09, 1.62369E-05, and integers in hexadecimal, octal, binary: 0xFF00, 0o17, 0b101
_NUMBER_RE = re.compile(r"0[xX][0-9a-fA-F]+|0[oO][0-7]+|0[bB][01]+|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


@dataclass(frozen=True, slots=True)
class LexResult:
    tokens: list[Token]  # always ends with an EOF token
    comments: list[CommentToken]
    diagnostics: list[Diagnostic]


def tokenize(text: str) -> LexResult:
    return _Lexer(text).run()


class _Lexer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.line = 1
        self.line_start = 0
        self.tokens: list[Token] = []
        self.comments: list[CommentToken] = []
        self.diagnostics: list[Diagnostic] = []

    def run(self) -> LexResult:
        self._skip_legacy_header()
        text = self.text
        while self.pos < len(text):
            ch = text[self.pos]
            if ch == "\n":
                self.pos += 1
                self.line += 1
                self.line_start = self.pos
            elif ch in " \t\f\v":
                self.pos += 1
            elif ch == "!":
                self._comment()
            elif ch == '"':
                self._string()
            elif ch in _DIGITS or (ch == "." and text[self.pos + 1 : self.pos + 2] in tuple(_DIGITS)):
                self._match(_NUMBER_RE, TokenKind.NUMBER)
            elif ch.isalpha() or ch == "_":
                self._word()
            elif not self._operator():
                self._error(f"unexpected character {ch!r}")
                self.pos += 1
        self.tokens.append(Token(TokenKind.EOF, "", "", self.line, self._col(), self.pos, self.pos))
        return LexResult(self.tokens, self.comments, self.diagnostics)

    def _col(self) -> int:
        return self.pos - self.line_start + 1

    def _skip_legacy_header(self) -> None:
        """Older .mod/.prg exports start with a '%%%  VERSION:1 LANGUAGE:ENGLISH %%%' block."""
        stripped = self.text.lstrip()
        if not stripped.startswith("%%%"):
            return
        first = self.text.index("%%%")
        second = self.text.find("%%%", first + 3)
        if second == -1:
            return
        end = second + 3
        self.line += self.text.count("\n", 0, end)
        self.line_start = self.text.rfind("\n", 0, end) + 1
        self.pos = end

    def _emit(self, kind: TokenKind, start: int, value: str | None = None) -> None:
        raw = self.text[start : self.pos]
        col = start - self.line_start + 1
        self.tokens.append(Token(kind, raw, raw if value is None else value, self.line, col, start, self.pos))

    def _match(self, regex: re.Pattern[str], kind: TokenKind) -> None:
        m = regex.match(self.text, self.pos)
        assert m is not None
        start, self.pos = self.pos, m.end()
        self._emit(kind, start)

    def _word(self) -> None:
        m = _IDENT_RE.match(self.text, self.pos)
        assert m is not None
        start, self.pos = self.pos, m.end()
        upper = m.group().upper()
        if upper in RESERVED_WORDS:
            self._emit(TokenKind.KEYWORD, start, upper)
        else:
            self._emit(TokenKind.IDENT, start)

    def _string(self) -> None:
        # RAPID strings: "" is an escaped quote, \\ an escaped backslash. No multi-line strings.
        start = self.pos
        self.pos += 1
        chars: list[str] = []
        text = self.text
        while True:
            if self.pos >= len(text) or text[self.pos] == "\n":
                self._error("unterminated string literal", start)
                break
            ch = text[self.pos]
            if ch == '"':
                if text[self.pos + 1 : self.pos + 2] == '"':
                    chars.append('"')
                    self.pos += 2
                    continue
                self.pos += 1
                break
            if ch == "\\" and text[self.pos + 1 : self.pos + 2] == "\\":
                chars.append("\\")
                self.pos += 2
                continue
            chars.append(ch)
            self.pos += 1
        self._emit(TokenKind.STRING, start, "".join(chars))

    def _comment(self) -> None:
        start = self.pos
        end = self.text.find("\n", start)
        if end == -1:
            end = len(self.text)
        self.comments.append(CommentToken(self.text[start + 1 : end], self.line, self._col(), start))
        self.pos = end

    def _operator(self) -> bool:
        for op in OPERATORS:
            if self.text.startswith(op, self.pos):
                start = self.pos
                self.pos += len(op)
                self._emit(TokenKind.OP, start)
                return True
        return False

    def _error(self, message: str, at: int | None = None) -> None:
        offset = self.pos if at is None else at
        span = Span(self.line, offset - self.line_start + 1)
        self.diagnostics.append(Diagnostic(Severity.ERROR, message, span))
