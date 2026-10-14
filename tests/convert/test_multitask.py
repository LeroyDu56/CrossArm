# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID's instructions for tasks or robots working together stay TODO, each saying what it is for and how the
FANUC cell does it (crossarm.convert.multitask), rather than a call with no mapping."""

from datetime import datetime

from helpers import parse_module

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.blockers import Blocker

SOURCE = """MODULE M
    PERS tasks tlBoth{2}:=[["T_ROB1"],["T_ROB2"]];
    VAR syncident syncIn;
    VAR syncident syncOut;
    PERS bool bGate:=FALSE;
    CONST robtarget pA:=[[600,0,400],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
    PROC main()
        WaitSyncTask syncIn,tlBoth;
        SyncMoveOn syncOut,tlBoth;
        MoveL pA\\ID:=10,v100,fine,tool0;
        SyncMoveOff syncIn;
        WaitTestAndSet bGate;
        bGate:=FALSE;
        IF IsSyncMoveOn() Stop;
    ENDPROC
    PROC WaitSyncTask(num n)
        WaitTime n;
    ENDPROC
ENDMODULE
"""


def todos(source: str) -> dict[int, tuple[str, str]]:
    result = convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), sources={"M": source})
    return {n.rapid_line: (n.category, n.message) for n in result.notes if n.kind == "TODO"}


def test_each_instruction_says_what_it_is_for():
    found = todos(SOURCE.replace("    PROC WaitSyncTask(num n)\n        WaitTime n;\n    ENDPROC\n", ""))
    assert found[8][0] == Blocker.NO_TP_EQUIVALENT and "a meeting point of RAPID tasks" in found[8][1]
    assert found[9][0] == found[11][0] == Blocker.MOTION and "coordinated motion of several robots" in found[9][1]
    assert found[12][0] == Blocker.NO_TP_EQUIVALENT and "a semaphore shared by RAPID tasks" in found[12][1]
    assert found[14][0] == Blocker.CONDITION  # a function in a condition: the IF written with its blocks
    assert not any("has no mapping" in message for _cause, message in found.values())


def test_a_routine_of_the_backup_of_the_same_name_is_its_own():
    found = todos(SOURCE.replace("WaitSyncTask syncIn,tlBoth;", "WaitSyncTask 1;"))
    assert 8 not in found
