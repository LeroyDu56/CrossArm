# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

""".LS layout. The joint-position program below mirrors the structure of a
controller export byte for byte; tests/fanuc/test_corpus_ls.py checks the writer
against a local corpus of exports when one is present.
"""

from datetime import datetime

import pytest

from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import (
    Attributes,
    CartesianPosition,
    Instruction,
    JointPosition,
    Motion,
    Position,
    Program,
)

JOINT_PROGRAM_LS = (
    "/PROG  SAMPLE\r\n"
    "/ATTR\r\n"
    "OWNER\t\t= MNEDITOR;\r\n"
    'COMMENT\t\t= "demo";\r\n'
    "PROG_SIZE\t= 0;\r\n"
    "CREATE\t\t= DATE 26-01-02  TIME 03:04:05;\r\n"
    "MODIFIED\t= DATE 26-01-02  TIME 03:04:05;\r\n"
    "FILE_NAME\t= ;\r\n"
    "VERSION\t\t= 0;\r\n"
    "LINE_COUNT\t= 2;\r\n"
    "MEMORY_SIZE\t= 0;\r\n"
    "PROTECT\t\t= READ_WRITE;\r\n"
    "TCD:  STACK_SIZE\t= 0,\r\n"
    "      TASK_PRIORITY\t= 50,\r\n"
    "      TIME_SLICE\t= 0,\r\n"
    "      BUSY_LAMP_OFF\t= 0,\r\n"
    "      ABORT_REQUEST\t= 0,\r\n"
    "      PAUSE_REQUEST\t= 0;\r\n"
    "DEFAULT_GROUP\t= 1,*,*,*,*;\r\n"
    "CONTROL_CODE\t= 00000000 00000000;\r\n"
    "/MN\r\n"
    "   1:J P[1] 100% FINE    ;\r\n"
    "   2:  !done ;\r\n"
    "/POS\r\n"
    "P[1]{\r\n"
    "   GP1:\r\n"
    "\tUF : 0, UT : 1,\t\r\n"
    "\tJ1=    10.000 deg,\tJ2=   -45.500 deg,\tJ3=     0.000 deg,\r\n"
    "\tJ4=     0.000 deg,\tJ5=   -90.000 deg,\tJ6=   180.000 deg\r\n"
    "};\r\n"
    "/END\r\n"
)


def make(lines, positions=(), **attrs) -> Program:
    attributes = Attributes(created=datetime(2026, 1, 2, 3, 4, 5), **attrs)
    return Program("SAMPLE", list(lines), list(positions), attributes)


def test_joint_program_matches_real_export_layout():
    program = make(
        [Motion("J", "P[1]", "100%", "FINE"), Instruction("!done")],
        [Position(1, 0, 1, JointPosition((10, -45.5, 0, 0, -90, 180)))],
        comment="demo",
    )
    assert write_ls(program) == JOINT_PROGRAM_LS


def test_empty_program_has_pos_right_after_mn():
    text = write_ls(make([]))
    assert "LINE_COUNT\t= 0;" in text
    assert "/MN\r\n/POS\r\n/END\r\n" in text


def test_instruction_and_blank_line_layout():
    text = write_ls(make([Instruction("UFRAME_NUM=1"), Instruction(""), Instruction("DO[1]=ON")]))
    assert "   1:  UFRAME_NUM=1 ;\r\n   2:   ;\r\n   3:  DO[1]=ON ;\r\n" in text


@pytest.mark.parametrize(("instruction", "terminator"), [
    ("CALL PICK", "    ;"), ("CALL PICK(1,2)", " ;"), ("R[1]=0", "    ;"), ("WAIT DI[1]=ON", "    ;"),
    ("WAIT (R[1]>2)", "    ;"), ("PR[100]=P[17]", "    ;"), ("PR[51]=LPOS", "    ;"), ("PR[71]=JPOS", "    ;"),
    ("PR[98]=PR[97]", "    ;"), ("PR[31]=UTOOL[1]", " ;"), ("UTOOL[1]=PR[100]", " ;"), ("UFRAME_NUM=1", " ;"),
    ("DO[1]=ON", " ;"),
])  # fmt: skip
def test_spaces_before_the_terminator_are_the_controllers(instruction, terminator):
    """As ROBOGUIDE stores each form (probe programs loaded, then read back from the robot)."""
    assert f"   1:  {instruction}{terminator}\r\n" in write_ls(make([Instruction(instruction)]))


def test_line_numbers_are_right_aligned_on_four_columns():
    text = write_ls(make([Instruction("!x")] * 12))
    assert "\r\n   9:  !x ;\r\n  10:  !x ;\r\n" in text


def test_linear_motion_with_cnt():
    text = write_ls(make([Motion("L", "P[2]", "500mm/sec", "CNT50")]))
    assert "   1:L P[2] 500mm/sec CNT50    ;\r\n" in text


def test_circular_motion_uses_a_continuation_line():
    text = write_ls(make([Motion("C", "P[3]", "200mm/sec", "FINE", via="P[2]")]))
    assert "   1:C P[2]    \r\n    :  P[3] 200mm/sec FINE    ;\r\n" in text
    assert "LINE_COUNT\t= 1;" in text  # one program line, two text lines


def test_circular_motion_without_via_is_rejected():
    with pytest.raises(ValueError):
        write_ls(make([Motion("C", "P[3]", "200mm/sec", "FINE")]))


def test_cartesian_position_block():
    pos = Position(3, 2, 1, CartesianPosition(600, -12.5, 900, 180, 0, -90))
    text = write_ls(make([Motion("J", "P[3]", "50%", "FINE")], [pos]))
    assert (
        "P[3]{\r\n"
        "   GP1:\r\n"
        "\tUF : 2, UT : 1,\t\tCONFIG : 'N U T, 0, 0, 0',\r\n"
        "\tX =   600.000  mm,\tY =   -12.500  mm,\tZ =   900.000  mm,\r\n"
        "\tW =   180.000 deg,\tP =     0.000 deg,\tR =   -90.000 deg\r\n"
        "};\r\n"
    ) in text


def test_macro_flag_and_appl_block():
    text = write_ls(make([], appl=("  ARC : TRUE ;",)))
    assert text.startswith("/PROG  SAMPLE\r\n")
    assert "CONTROL_CODE\t= 00000000 00000000;\r\n/APPL\r\n  ARC : TRUE ;\r\n/MN" in text
    macro = Program("M1", attributes=Attributes(created=datetime(2026, 1, 1)), macro=True)
    # Tab then two spaces: the form controllers write for a macro, not two tabs.
    assert write_ls(macro).startswith("/PROG  M1\t  Macro\r\n")


def test_empty_appl_section_is_not_the_same_as_none():
    """Real macros carry an /APPL header with nothing under it."""
    assert "/APPL" not in write_ls(make([]))
    assert "CONTROL_CODE\t= 00000000 00000000;\r\n/APPL\r\n/MN" in write_ls(make([], appl=()))


def test_negative_zero_is_written_as_an_exact_zero():
    """-(J2 + J3) can be -0.0; the controller never writes '-0.000'."""
    program = make([], positions=[Position(1, 0, 1, JointPosition((0.0, -30.0, -0.0, -0.0, -90.0, 180.0)))])
    text = write_ls(program)
    assert "-0.000" not in text
    assert "J3=     0.000 deg" in text


def test_output_is_pure_ascii():
    write_ls(make([Instruction("!ok")])).encode("ascii")
