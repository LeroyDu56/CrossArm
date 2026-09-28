# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

""".LS parser: the contract is write_ls(parse_ls(text)) == text.

That property is what lets CrossArm be checked without a controller. It holds on
every .LS file committed here — CrossArm's own output and the programs ROBOGUIDE
exported back — and test_corpus_ls.py checks it on a local corpus of controller exports.
"""

from datetime import datetime

import pytest
from helpers import FIXTURES

from crossarm.fanuc.ls_parser import LSFormatError, controller_number, parse_ls, read_ls
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import CartesianPosition, Instruction, JointPosition, Motion

COMMITTED = sorted(p for p in FIXTURES.rglob("*") if p.suffix.lower() == ".ls")

HEADER = (
    "/PROG  SAMPLE\r\n/ATTR\r\nOWNER\t\t= MNEDITOR;\r\nCOMMENT\t\t= \"demo\";\r\nPROG_SIZE\t= 0;\r\n"
    "CREATE\t\t= DATE 26-01-02  TIME 03:04:05;\r\nMODIFIED\t= DATE 26-01-02  TIME 03:04:05;\r\n"
    "FILE_NAME\t= ;\r\nVERSION\t\t= 0;\r\nLINE_COUNT\t= {n};\r\nMEMORY_SIZE\t= 0;\r\nPROTECT\t\t= READ_WRITE;\r\n"
    "TCD:  STACK_SIZE\t= 0,\r\n      TASK_PRIORITY\t= 50,\r\n      TIME_SLICE\t= 0,\r\n"
    "      BUSY_LAMP_OFF\t= 0,\r\n      ABORT_REQUEST\t= 0,\r\n      PAUSE_REQUEST\t= 0;\r\n"
    "DEFAULT_GROUP\t= 1,*,*,*,*;\r\nCONTROL_CODE\t= 00000000 00000000;\r\n"
)


def ls(mn: list[str], pos: str = "", n: int | None = None, header: str = HEADER) -> str:
    """A .LS file around `mn`: each item is what follows 'nnnn:' and gets numbered, except
    continuation lines ('    :...') and blank lines, which are written as given."""
    body, number = [], 0
    for item in mn:
        if item.startswith("    :") or not item.strip():
            body.append(item)
        else:
            number += 1
            body.append(f"{number:4d}:{item}")
    text = "".join(line + "\r\n" for line in body)
    return header.format(n=number if n is None else n) + "/MN\r\n" + text + "/POS\r\n" + pos + "/END\r\n"


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", COMMITTED, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_committed_ls_file_round_trips_byte_for_byte(path):
    text = path.read_bytes().decode("ascii")
    assert write_ls(parse_ls(text)) == text


def test_the_committed_files_include_controller_exports():
    """The property is only worth something if it also holds on files a controller wrote."""
    assert any(p.parent.name == "roboguide_export" for p in COMMITTED)
    assert any("CONFIG" in p.read_text(encoding="ascii") for p in COMMITTED)  # cartesian /POS


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------


def test_header_fields():
    program = parse_ls(ls(["  !hello ;"]))
    a = program.attributes
    assert program.name == "SAMPLE" and not program.macro
    assert a.comment == "demo" and a.owner == "MNEDITOR" and a.protect == "READ_WRITE"
    assert a.created == datetime(2026, 1, 2, 3, 4, 5)
    assert a.file_name == "" and a.appl is None


def test_values_a_generator_would_not_write_are_kept():
    """Controller exports can have STACK_SIZE 500, a read-only program, LINE_COUNT unrelated to the body."""
    header = HEADER.replace("STACK_SIZE\t= 0", "STACK_SIZE\t= 500").replace("READ_WRITE", "READ")
    text = ls(["  !only line ;"], n=53, header=header)
    program = parse_ls(text)
    assert program.attributes.stack_size == 500
    assert program.attributes.protect == "READ"
    assert program.attributes.line_count == 53
    assert write_ls(program) == text


def test_macro_and_an_empty_appl_section():
    header = HEADER.replace("/PROG  SAMPLE", "/PROG  SAMPLE\t  Macro") + "/APPL\r\n"
    text = ls([], header=header)
    program = parse_ls(text)
    assert program.macro and program.attributes.appl == ()
    assert write_ls(program) == text


def test_appl_lines_keep_stray_line_feeds():
    """A real CRLF export carried bare LFs inside /APPL: splitting on them would lose them."""
    header = HEADER + "/APPL\r\n\nAPPL_NAME;\r\n  ARC : TRUE ;\n\r\n"
    text = ls([], header=header)
    assert parse_ls(text).attributes.appl == ("\nAPPL_NAME;", "  ARC : TRUE ;\n")
    assert write_ls(parse_ls(text)) == text


# ---------------------------------------------------------------------------
# /MN
# ---------------------------------------------------------------------------


def test_instructions_keep_the_spaces_before_the_terminator():
    """Controller exports use anything from 0 to 18 spaces; the parser does not guess a rule."""
    text = ls(["  DO[1]=ON ;", "  CALL PICK    ;", "  LBL[10:Retry]      ;", "  !note;"])
    lines = parse_ls(text).lines
    assert lines == [Instruction("DO[1]=ON", 1), Instruction("CALL PICK", 4),
                     Instruction("LBL[10:Retry]", 6), Instruction("!note", 0)]  # fmt: skip
    assert write_ls(parse_ls(text)) == text


def test_empty_and_indented_lines():
    text = ls(["  SELECT R[1]=1,JMP LBL[1] ;", "         =2,JMP LBL[2] ;", "   ;"])
    lines = parse_ls(text).lines
    assert lines[1] == Instruction("       =2,JMP LBL[2]", 1)  # continuation indent kept in the text
    assert lines[2] == Instruction("")
    assert write_ls(parse_ls(text)) == text


def test_motions():
    text = ls([
        "J P[1] 100% FINE    ;",
        "L PR[2:Home pos] 500mm/sec CNT50 ACC80    ;",
        "C P[3]    ",
        "    :  P[4] 200mm/sec FINE    ;",
    ])  # fmt: skip
    j, lin, c = parse_ls(text).lines
    assert j == Motion("J", "P[1]", "100%", "FINE", pad=4)
    assert lin == Motion("L", "PR[2:Home pos]", "500mm/sec", "CNT50", options="ACC80", pad=4)
    assert (c.kind, c.via, c.target, c.speed) == ("C", "P[3]", "P[4]", "200mm/sec")
    assert write_ls(parse_ls(text)) == text


def test_trailing_blank_lines_in_mn_are_kept():
    """Two lines of two spaces between the last instruction and /POS, as a controller can write."""
    text = ls(["  !last ;", "  ", "  "], n=1)
    program = parse_ls(text)
    assert len(program.lines) == 1 and program.mn_extra == ("  ", "  ")
    assert write_ls(program) == text


# ---------------------------------------------------------------------------
# /POS
# ---------------------------------------------------------------------------

JOINT = (
    "P[1]{\r\n   GP1:\r\n\tUF : 0, UT : 1,\t\r\n"
    "\tJ1=     0.000 deg,\tJ2=   -30.000 deg,\tJ3=     -.000 deg,\r\n"
    "\tJ4=      .500 deg,\tJ5=   -90.000 deg,\tJ6=   180.000 deg\r\n};\r\n"
)
CARTESIAN = (
    "P[2]{\r\n   GP1:\r\n\tUF : 1, UT : 2,\t\tCONFIG : 'F U T, 0, 0, -1',\r\n"
    "\tX =   812.350  mm,\tY =  -245.100  mm,\tZ =   405.000  mm,\r\n"
    "\tW =  -179.293 deg,\tP =      .000 deg,\tR =   -90.000 deg\r\n};\r\n"
)


def test_positions():
    text = ls(["J P[1] 100% FINE    ;", "L P[2] 500mm/sec FINE    ;"], JOINT + CARTESIAN)
    joint, cart = parse_ls(text).positions
    assert (joint.number, joint.uf, joint.ut) == (1, 0, 1)
    assert isinstance(joint.value, JointPosition) and joint.value.joints[4] == -90.0
    assert isinstance(cart.value, CartesianPosition)
    assert (cart.uf, cart.ut, cart.value.config) == (1, 2, "F U T, 0, 0, -1")
    assert cart.value.x == 812.35
    assert write_ls(parse_ls(text)) == text


def test_numbers_that_round_to_zero_are_not_zero():
    assert controller_number("0.000") == 0.0
    assert 0 < controller_number(".000") < 1e-6
    assert -1e-6 < controller_number("-.000") < 0
    assert controller_number("-.500") == -0.5


# ---------------------------------------------------------------------------
# What is refused, with a line number
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "where", "why"),
    [
        ("an alarm history listing\r\n", 1, "/PROG"),
        (ls(["  DO[1]=ON ;", "  DO[2]=ON ;"]).replace("   2:", "   3:"), 23, "line number 3"),
        (ls(["  DO[1]=ON"]), 22, "without ';'"),
        (ls(["J P[1] 100%    ;"]), 22, "termination"),
        (ls([], JOINT.replace("P[1]{", 'P[1:"Home"]{')), 23, "comments"),
        (ls([], JOINT.replace("GP1:", "GP2:")), 24, "group 1"),
        (ls(["  !x ;"]).replace("OWNER", "SURPRISE"), 3, "unknown /ATTR field"),
        (ls(["  !x ;"]) + "junk\r\n", 25, "after /END"),
    ],
    ids=["not-a-program", "numbering", "no-terminator", "no-termination", "pos-comment", "group-2",
         "unknown-field", "after-end"],
)  # fmt: skip
def test_what_is_not_understood_is_refused_not_guessed(text, where, why):
    with pytest.raises(LSFormatError, match=why) as info:
        parse_ls(text)
    assert info.value.line == where


def test_read_ls(tmp_path):
    path = tmp_path / "P.LS"
    path.write_bytes(ls(["  !x ;"]).encode("ascii"))
    assert read_ls(path).lines == [Instruction("!x", 1)]
