# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Token definitions for the RAPID lexer."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    IDENT = auto()
    KEYWORD = auto()
    NUMBER = auto()
    STRING = auto()
    OP = auto()  # operators and punctuation
    EOF = auto()


# RAPID reserved words (ABB Technical reference manual, "Reserved words").
# RAPID is case-insensitive: keywords are matched upper-cased.
RESERVED_WORDS = frozenset(
    """
    ALIAS AND BACKWARD CASE CONNECT CONST DEFAULT DIV DO ELSE ELSEIF
    ENDFOR ENDFUNC ENDIF ENDMODULE ENDPROC ENDRECORD ENDTEST ENDTRAP ENDWHILE
    ERROR EXIT FALSE FOR FROM FUNC GOTO IF INOUT LOCAL MOD MODULE NOSTEPIN
    NOT NOVIEW OR PERS PROC RAISE READONLY RECORD RETRY RETURN STEP SYSMODULE
    TEST THEN TO TRAP TRUE TRYNEXT UNDO VAR VIEWONLY WHILE WITH XOR
    """.split()  # noqa: SIM905 - kept as a readable word table
)

# Longest first, so that ":=" wins over ":" and "<>" over "<".
OPERATORS = (
    ":=", "<>", "<=", ">=",
    "+", "-", "*", "/", "=", "<", ">",
    "(", ")", "[", "]", "{", "}",
    ",", ";", ":", ".", "\\", "|", "?", "%",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str  # exact source text
    value: str  # keywords upper-cased, strings unescaped, otherwise == text
    line: int
    col: int
    start: int  # offsets into the source string, for raw-text slicing
    end: int

    def is_kw(self, *words: str) -> bool:
        return self.kind is TokenKind.KEYWORD and self.value in words

    def is_op(self, *ops: str) -> bool:
        return self.kind is TokenKind.OP and self.value in ops

    def describe(self) -> str:
        if self.kind is TokenKind.EOF:
            return "end of file"
        return f"'{self.text}'"


@dataclass(frozen=True, slots=True)
class CommentToken:
    """A '!' comment. Kept out of the token stream, re-attached by the parser."""

    text: str  # without the leading '!'
    line: int
    col: int
    start: int
