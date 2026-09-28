# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

import pytest
from helpers import parse_body, parse_stmt

from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_arg, format_expr

# --------------------------------------------------------------------------
# Motion
# --------------------------------------------------------------------------


def test_movel_arguments_by_role():
    move = parse_stmt("MoveL p10,v500,z10,tGripper\\WObj:=wobj1;")
    assert isinstance(move, n.Move)
    assert move.kind is n.MoveKind.L
    roles = [format_expr(e) for e in (move.to_point, move.speed, move.zone, move.tool, move.wobj)]
    assert roles == ["p10", "v500", "z10", "tGripper", "wobj1"]
    assert move.via_point is None and move.options == ()


def test_movej_with_function_target_and_no_wobj():
    move = parse_stmt("MoveJ Offs(pPick,0,0,100), v1000, z50, tool0;")
    assert move.kind is n.MoveKind.J
    assert format_expr(move.to_point) == "Offs(pPick, 0, 0, 100)"
    assert move.wobj is None


def test_movec_has_via_point():
    move = parse_stmt("MoveC pMid,pEnd,v300,fine,tool0;")
    assert move.kind is n.MoveKind.C
    assert (format_expr(move.via_point), format_expr(move.to_point)) == ("pMid", "pEnd")


def test_moveabsj_keeps_switch_in_options():
    move = parse_stmt("MoveAbsJ jPark\\NoEOffs,vFast,fine,tCurrent\\WObj:=wCurrent;")
    assert move.kind is n.MoveKind.ABSJ
    assert [format_arg(a) for a in move.options] == ["\\NoEOffs"]
    assert format_expr(move.wobj) == "wCurrent"


def test_move_keywords_are_case_insensitive():
    assert parse_stmt("movel p,v,z,t;").kind is n.MoveKind.L


def test_conditional_wobj_argument_stays_an_option():
    move = parse_stmt("MoveL p,v,z,t\\wobj?wobj;")
    assert move.wobj is None
    assert [format_arg(a) for a in move.options] == ["\\wobj?wobj"]


def test_move_with_wrong_arity_falls_back_to_generic_call():
    from crossarm.rapid import parse_text

    result = parse_text("MODULE T\nPROC p()\nMoveL p10,v100;\nENDPROC\nENDMODULE")
    (stmt,) = result.module.routines[0].body
    assert isinstance(stmt, n.ProcCall)
    assert "expected 4" in result.diagnostics[0].message


# --------------------------------------------------------------------------
# I/O, waits, calls
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("source", "value"), [("Set doGrip;", 1), ("Reset doGrip;", 0), ("RESET doGrip;", 0)])
def test_set_reset(source, value):
    stmt = parse_stmt(source)
    assert stmt == n.SetSignal(stmt.span, n.Name(stmt.signal.span, "doGrip"), value)


def test_waittime_with_optional_inpos():
    stmt = parse_stmt("WaitTime\\InPos,0.5;")
    assert isinstance(stmt, n.WaitTime)
    assert format_expr(stmt.seconds) == "0.5"
    assert [a.name for a in stmt.options] == ["InPos"]


def test_call_without_arguments():
    assert parse_stmt("InitCell;") == n.ProcCall(parse_stmt("InitCell;").span, "InitCell")


def test_call_with_arguments_and_switches():
    stmt = parse_stmt('SetZone\\Release\\Outer;')
    assert [format_arg(a) for a in stmt.args] == ["\\Release", "\\Outer"]
    stmt = parse_stmt('TPWrite "Slot "\\Num:=n;')
    assert [format_arg(a) for a in stmt.args] == ['"Slot "', "\\Num:=n"]


def test_multiline_call_with_optional_args():
    stmt = parse_stmt(
        'answer:=UIMessageBox(\n  \\Header:="T"\n  \\MsgArray:=["a",\n  "b"]\n  \\Icon:=iconWarning);'
    )
    assert isinstance(stmt, n.Assign)
    assert [a.name for a in stmt.value.args] == ["Header", "MsgArray", "Icon"]


# --------------------------------------------------------------------------
# Control flow
# --------------------------------------------------------------------------


def test_if_elseif_else():
    stmt = parse_stmt("IF a=1 THEN\n  Stop;\nELSEIF a=2 THEN\n  Stop;\n  Stop;\nELSE\n  EXIT;\nENDIF")
    assert isinstance(stmt, n.If) and not stmt.compact
    assert [format_expr(b.condition) for b in stmt.branches] == ["a = 1", "a = 2"]
    assert [len(b.body) for b in stmt.branches] == [1, 2]
    assert isinstance(stmt.else_body[0], n.Exit)


def test_compact_if():
    stmt = parse_stmt("IF doRetract=1 OR doGate=1 InitCell;")
    assert stmt.compact
    assert format_expr(stmt.branches[0].condition) == "doRetract = 1 OR doGate = 1"
    assert stmt.branches[0].body[0].name == "InitCell"


def test_for_with_and_without_step():
    loop = parse_stmt("FOR i FROM 1 TO 10 DO\n  Stop;\nENDFOR")
    assert (loop.var, format_expr(loop.start), format_expr(loop.end), loop.step) == ("i", "1", "10", None)
    loop = parse_stmt("FOR nX FROM 0 TO 20 STEP 2 DO\nENDFOR")
    assert format_expr(loop.step) == "2" and loop.body == ()


def test_while_and_test():
    stmt = parse_stmt("WHILE TRUE DO\n  TEST n\n  CASE 1, 2:\n    Stop;\n  DEFAULT:\n    EXIT;\n  ENDTEST\nENDWHILE")
    (test,) = stmt.body
    assert isinstance(test, n.Test)
    assert [format_expr(v) for v in test.cases[0].values] == ["1", "2"]
    assert isinstance(test.default[0], n.Exit)


def test_nested_blocks_keep_comments_in_place():
    body = parse_body("IF a THEN\n  ! inside\n  Stop;\nENDIF\n! after")
    if_stmt, after = body
    assert isinstance(if_stmt.branches[0].body[0], n.Comment)
    assert after.text == " after"


# --------------------------------------------------------------------------
# Assignments and expressions
# --------------------------------------------------------------------------


def test_assignment_to_record_component_and_array_element():
    stmt = parse_stmt("pPlace.trans.z:=pPlace.trans.z+2.5;")
    assert format_expr(stmt.target) == "pPlace.trans.z"
    stmt = parse_stmt("reg{i,2}:=0;")
    assert isinstance(stmt.target, n.Index) and len(stmt.target.indices) == 2


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("a + b * c", "a + b * c"),
        ("(a + b) * c", "(a + b) * c"),
        ("a - (b - c)", "a - (b - c)"),
        ("a = 1 AND b = 2 OR c", "a = 1 AND b = 2 OR c"),
        ("a AND (b OR c)", "a AND (b OR c)"),
        ("NOT a = b", "NOT a = b"),
        ("-x DIV 2", "-x DIV 2"),
        ("DOutput(doGate)=0", "DOutput(doGate) = 0"),
        ("GInput(GI_L)/nScale<>0", "GInput(GI_L) / nScale <> 0"),
    ],
)
def test_expression_precedence_round_trips(source, expected):
    stmt = parse_stmt(f"x:={source};")
    assert format_expr(stmt.value) == expected


def test_precedence_tree_shape():
    value = parse_stmt("x:=a OR b AND c;").value
    assert value.op == "OR" and value.right.op == "AND"
    value = parse_stmt("x:=NOT a = b;").value
    assert value.op == "NOT" and value.operand.op == "="
