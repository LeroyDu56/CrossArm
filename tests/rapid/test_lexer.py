# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

import pytest

from crossarm.rapid.lexer import tokenize
from crossarm.rapid.tokens import TokenKind


def kinds_and_values(text: str) -> list[tuple[TokenKind, str]]:
    return [(t.kind, t.value) for t in tokenize(text).tokens if t.kind is not TokenKind.EOF]


@pytest.mark.parametrize("text", ["12", "1.5", "1.", ".5", "9E+09", "9E9", "1.62369E-05", "1E-09"])
def test_numbers(text):
    assert kinds_and_values(text) == [(TokenKind.NUMBER, text)]


def test_negative_number_is_unary_minus_then_number():
    assert kinds_and_values("-589.76") == [(TokenKind.OP, "-"), (TokenKind.NUMBER, "589.76")]


def test_keywords_are_case_insensitive_and_upper_cased():
    assert kinds_and_values("moveL endif EndProc") == [
        (TokenKind.IDENT, "moveL"),  # instructions are identifiers, not keywords
        (TokenKind.KEYWORD, "ENDIF"),
        (TokenKind.KEYWORD, "ENDPROC"),
    ]


def test_identifier_containing_a_keyword_stays_an_identifier():
    assert kinds_and_values("pApp_STEP1 ERROR_code") == [(TokenKind.IDENT, "pApp_STEP1"), (TokenKind.IDENT, "ERROR_code")]


def test_string_escapes():
    token = tokenize(r'"say ""hi"" \\ bye"').tokens[0]
    assert token.kind is TokenKind.STRING
    assert token.value == 'say "hi" \\ bye'


def test_unterminated_string_is_reported_not_raised():
    result = tokenize('TPWrite "oops\nStop;')
    assert [d.message for d in result.diagnostics] == ["unterminated string literal"]
    assert result.tokens[-2].value == ";"  # lexing continued on the next line


def test_multi_char_operators_win():
    assert [v for _, v in kinds_and_values("a:=b<>c<=d>=e")] == ["a", ":=", "b", "<>", "c", "<=", "d", ">=", "e"]


def test_comments_are_kept_aside_with_position():
    result = tokenize("x := 1;  ! set x\n! full line")
    assert [t.value for t in result.tokens[:-1]] == ["x", ":=", "1", ";"]
    assert [(c.text, c.line, c.col) for c in result.comments] == [(" set x", 1, 10), (" full line", 2, 1)]


def test_bang_inside_string_is_not_a_comment():
    result = tokenize('TPWrite "Hello!";')
    assert result.comments == []
    assert result.tokens[1].value == "Hello!"


def test_positions_are_one_based():
    tokens = tokenize("MODULE A\n  PROC").tokens
    assert [(t.line, t.col) for t in tokens[:3]] == [(1, 1), (1, 8), (2, 3)]


def test_legacy_percent_header_is_skipped_and_lines_preserved():
    tokens = tokenize("%%%\n  VERSION:1\n  LANGUAGE:ENGLISH\n%%%\n\nMODULE A").tokens
    assert (tokens[0].value, tokens[0].line) == ("MODULE", 6)


def test_unexpected_character_is_skipped_with_diagnostic():
    result = tokenize("a # b")
    assert [t.value for t in result.tokens[:-1]] == ["a", "b"]
    assert "unexpected character" in result.diagnostics[0].message
