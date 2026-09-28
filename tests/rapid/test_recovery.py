# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Out-of-scope constructs and broken input must never stop the parse."""

from helpers import parse_body, parse_module

from crossarm.diagnostics import Severity
from crossarm.rapid import nodes as n
from crossarm.rapid import parse_text


def kinds(stmts) -> list[str]:
    return [s.kind if isinstance(s, n.Unsupported) else type(s).__name__ for s in stmts]


def test_record_is_skipped_as_a_whole():
    module = parse_module("MODULE M\nRECORD r\n  num a;\n  string b;\nENDRECORD\nVAR num x;\nENDMODULE")
    record, decl = module.body
    assert record.kind == "RECORD"
    assert record.raw.startswith("RECORD r") and record.raw.endswith("ENDRECORD")
    assert decl.name == "x"


def test_alias_is_unsupported():
    module = parse_module("MODULE M\nALIAS num Level;\nENDMODULE")
    assert module.body[0].kind == "ALIAS"


def test_error_and_backward_handlers_are_attached_to_routine():
    module = parse_module(
        "MODULE M\nPROC p()\n  Stop;\nBACKWARD\n  MoveL a,b,c,d;\nERROR\n  IF ERRNO=1 RETRY;\n  RAISE;\nENDPROC\nENDMODULE"
    )
    routine = module.routines[0]
    assert kinds(routine.body) == ["ProcCall"]
    assert [h.kind for h in routine.handlers] == ["BACKWARD_HANDLER", "ERROR_HANDLER"]
    assert "RAISE;" in routine.handlers[1].raw


def test_goto_label_raise_late_binding():
    body = parse_body('GOTO lbl;\nlbl:\nRAISE ERR_X;\n%"P"+ValToStr(n)+"_C"%;\nStop;')
    assert kinds(body) == ["GOTO", "LABEL", "RAISE", "LATE_BINDING", "ProcCall"]


def test_bad_statement_is_skipped_and_parsing_continues():
    result = parse_text("MODULE M\nPROC p()\n  Stop;\n  x := := 3;\n  Set doA;\nENDPROC\nENDMODULE")
    body = result.module.routines[0].body
    assert kinds(body) == ["ProcCall", "SYNTAX_ERROR", "SetSignal"]
    assert body[1].raw == "x := := 3;"
    assert [d.severity for d in result.diagnostics] == [Severity.ERROR]
    assert result.diagnostics[0].span.line == 4


def test_bad_statement_inside_block_does_not_swallow_endif():
    result = parse_text("MODULE M\nPROC p()\n  IF a THEN\n    x := ;\n  ENDIF\n  Stop;\nENDPROC\nENDMODULE")
    if_stmt, stop = result.module.routines[0].body
    assert kinds(if_stmt.branches[0].body) == ["SYNTAX_ERROR"]
    assert isinstance(stop, n.ProcCall)


def test_broken_compound_header_is_skipped_with_its_block():
    result = parse_text("MODULE M\nPROC p()\n  IF THEN\n    Stop;\n  ENDIF\n  Set doA;\nENDPROC\nENDMODULE")
    body = result.module.routines[0].body
    assert kinds(body) == ["SYNTAX_ERROR", "SetSignal"]
    assert body[0].raw.endswith("ENDIF")


def test_broken_routine_structure_is_isolated_to_that_routine():
    # Missing ENDIF: the first routine is lost, the second one survives.
    result = parse_text("MODULE M\nPROC a()\n  IF x THEN\n    Stop;\nENDPROC\nPROC b()\n  Stop;\nENDPROC\nENDMODULE")
    assert result.module is not None
    first, second = result.module.body
    assert isinstance(first, n.Unsupported) and first.kind == "SYNTAX_ERROR"
    assert isinstance(second, n.Routine) and second.name == "b"
    assert not result.ok


def test_missing_module_header():
    result = parse_text("PROC p()\nENDPROC")
    assert result.module is None
    assert "expected MODULE" in result.diagnostics[0].message
