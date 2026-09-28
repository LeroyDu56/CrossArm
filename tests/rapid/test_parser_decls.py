# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

from helpers import parse_module

from crossarm.rapid import nodes as n
from crossarm.rapid.to_pseudo import format_expr

ROBTARGET = (
    "CONST robtarget pA:=[[-589.768,-899.714,1155.975],[0.437807,-0.744409,0.434575,-0.255585],"
    "[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];"
)


def only_decl(source: str) -> n.DataDecl:
    module = parse_module(f"MODULE M\n{source}\nENDMODULE")
    (decl,) = module.declarations
    return decl


def test_module_header_and_attributes():
    module = parse_module("MODULE x_DATA(SYSMODULE, NOSTEPIN)\nENDMODULE")
    assert (module.name, module.attributes, module.body) == ("x_DATA", ("SYSMODULE", "NOSTEPIN"), ())


def test_robtarget_is_four_nested_aggregates():
    decl = only_decl(ROBTARGET)
    assert (decl.storage, decl.type_name, decl.name) == ("CONST", "robtarget", "pA")
    assert isinstance(decl.init, n.Aggregate)
    trans, rot, conf, extax = decl.init.items
    assert [len(part.items) for part in (trans, rot, conf, extax)] == [3, 4, 4, 6]
    # Negative coordinates are unary minus applied to a literal.
    x = trans.items[0]
    assert isinstance(x, n.UnaryOp) and x.op == "-" and x.operand.value == 589.768
    assert extax.items[0].value == 9e9 and extax.items[0].text == "9E+09"


def test_scopes_and_storage_classes():
    module = parse_module(
        "MODULE M\n"
        "LOCAL PERS speeddata vSlow:=[100,30,500,50];\n"
        "TASK PERS wobjdata wCur:=[FALSE,TRUE,\"\",[[0,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];\n"
        "VAR num counter;\n"
        "ENDMODULE"
    )
    summary = [(d.scope, d.storage, d.type_name, d.name, d.init is None) for d in module.declarations]
    assert summary == [
        ("LOCAL", "PERS", "speeddata", "vSlow", False),
        ("TASK", "PERS", "wobjdata", "wCur", False),
        (None, "VAR", "num", "counter", True),
    ]


def test_array_declaration():
    decl = only_decl('LOCAL CONST string Msg{2}:=["a","b"];')
    assert [format_expr(d) for d in decl.dims] == ["2"]
    assert [item.value for item in decl.init.items] == ["a", "b"]


def test_trailing_comment_follows_declaration():
    module = parse_module(f"MODULE M\n{ROBTARGET}  ! 90deg - front right\nENDMODULE")
    decl, comment = module.body
    assert isinstance(decl, n.DataDecl)
    assert comment == n.Comment(comment.span, " 90deg - front right")
    assert comment.span.line == decl.span.line


def test_routine_kinds():
    module = parse_module(
        "MODULE M\n"
        "PROC p() ENDPROC\n"
        "LOCAL FUNC num f() RETURN 1; ENDFUNC\n"
        "TRAP t ENDTRAP\n"
        "ENDMODULE"
    )
    assert [(r.kind, r.name, r.return_type, r.scope) for r in module.routines] == [
        ("PROC", "p", None, None),
        ("FUNC", "f", "num", "LOCAL"),
        ("TRAP", "t", None, None),
    ]


def test_parameters_are_kept_as_raw_text():
    module = parse_module(
        "MODULE M\n"
        "PROC Measure(INOUT tooldata Tool,\\switch X1|switch X2\n"
        "             \\num Tol)\nENDPROC\nENDMODULE"
    )
    assert module.routines[0].params == "INOUT tooldata Tool,\\switch X1|switch X2 \\num Tol"


def test_local_declarations_inside_routine():
    module = parse_module("MODULE M\nPROC p()\nVAR jointtarget j;\nVAR num a:=2;\nENDPROC\nENDMODULE")
    body = module.routines[0].body
    assert [(d.type_name, d.name) for d in body] == [("jointtarget", "j"), ("num", "a")]
