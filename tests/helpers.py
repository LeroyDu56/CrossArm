# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Small parsing helpers shared by the test modules."""

from pathlib import Path

from crossarm.rapid import nodes as n
from crossarm.rapid import parse_text

FIXTURES = Path(__file__).parent / "fixtures"


def parse_module(source: str) -> n.Module:
    """Parse and assert there is no diagnostic at all."""
    result = parse_text(source)
    assert result.diagnostics == (), [str(d) for d in result.diagnostics]
    assert result.module is not None
    return result.module


def parse_body(statements: str, declarations: str = "") -> tuple[n.Stmt, ...]:
    """Wrap statements in MODULE/PROC and return the routine body."""
    module = parse_module(f"MODULE T\n{declarations}\nPROC main()\n{statements}\nENDPROC\nENDMODULE\n")
    return module.routines[0].body


def parse_stmt(statement: str) -> n.Stmt:
    body = parse_body(statement)
    assert len(body) == 1, body
    return body[0]
