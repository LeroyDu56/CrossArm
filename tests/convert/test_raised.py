# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Errors the program raises itself (convert.raised): a register set by the routine raising, tested after its CALL,
the caller's handler written there. Made-up names."""

from datetime import datetime

from helpers import parse_module

from crossarm.convert import ConversionConfig, convert

DATA = """    VAR errnum ERR_JAM:=-1;
    VAR errnum ERR_EMPTY:=-1;
    CONST errnum ERR_FIXED:=12;
    VAR num nCount:=0;
"""


def run(body: str):
    module = parse_module("MODULE M\n" + DATA + body + "\nENDMODULE\n")
    return convert([module], ConversionConfig(timestamp=datetime(2026, 1, 1)))


def lines(result, name: str) -> list[str]:
    info = next(i for i in result.programs if i.program.name == name)
    return [line.text for line in info.program.lines if not line.text.startswith("!")]


def notes(result, kind: str) -> list[str]:
    return [note.message for note in result.notes if note.kind == kind]


FEEDER = """
    PROC Feed()
        IF nCount>3 THEN
            RAISE ERR_JAM;
        ENDIF
        nCount:=nCount+1;
    ERROR
        RAISE;
    ENDPROC
"""


def test_raise_in_a_routine_passing_it_on_sets_the_register_and_ends():
    result = run(FEEDER + """
    PROC Cell()
        Feed;
        nCount:=0;
    ERROR
        IF ERRNO=ERR_JAM THEN
            TRYNEXT;
        ENDIF
    ENDPROC""")
    assert notes(result, "TODO") == []
    assert lines(result, "FEED")[:4] == ["R[1:Raised]=0", "IF (R[2:nCount]>3) THEN", "R[1:Raised]=10000", "END"]
    assert lines(result, "CELL") == [
        "CALL FEED", "IF R[1:Raised]=0,JMP LBL[2]", "R[3:ErrNo]=R[1:Raised]", "R[1:Raised]=0",
        "IF (R[3:ErrNo]=10000) THEN", "JMP LBL[2]", "ENDIF", "ABORT", "LBL[2]", "R[2:nCount]=0",
    ]
    assert any("written at the 1 line(s) raising" in w for w in notes(result, "WARNING"))
    from crossarm.convert.html_report import build_html_report

    page = build_html_report(result, ConversionConfig(), ["m.mod"], title="t")
    assert "Reserved by CrossArm: the error a routine ends with" in page and "Reserved by CrossArm: ERRNO" in page
    assert "ERROR handlers converted in part" in page


def test_without_a_handler_the_error_stops_the_program():
    # RobotStudio: an error raised in a routine without an ERROR handler stops the program, its caller's handler
    # does not run.
    result = run(FEEDER + """
    PROC Lone()
        RAISE ERR_EMPTY;
    ENDPROC
    PROC Plain()
        Feed;
        nCount:=0;
    ENDPROC""")
    assert notes(result, "TODO") == []
    assert lines(result, "LONE") == ["ABORT"]
    assert lines(result, "PLAIN") == ["CALL FEED", "IF R[1:Raised]=0,JMP LBL[1]", "ABORT", "LBL[1]", "R[2:nCount]=0"]


def test_retry_is_counted_and_raise_in_the_body_goes_to_the_own_handler():
    result = run(FEEDER + """
    PROC Again()
        Feed;
    ERROR
        TEST ERRNO
        CASE ERR_JAM:
            RETRY;
        ENDTEST
    ENDPROC
    PROC Own()
        RAISE ERR_FIXED;
        nCount:=2;
    ERROR
        IF ERRNO=ERR_FIXED THEN
            nCount:=ERRNO;
            TRYNEXT;
        ENDIF
    ENDPROC""")
    assert notes(result, "TODO") == []
    again = lines(result, "AGAIN")
    assert again[:3] == ["R[3:AgainRetries]=0", "LBL[1]", "CALL FEED"]
    assert "IF R[3:AgainRetries]<=4,JMP LBL[1]" in again
    own = lines(result, "OWN")
    assert own[:3] == ["R[1:Raised]=12", "R[4:ErrNo]=R[1:Raised]", "R[1:Raised]=0"]  # a CONST errnum: its value
    assert own[3:] == ["IF (R[4:ErrNo]=12) THEN", "R[2:nCount]=R[4:ErrNo]", "JMP LBL[2]", "ENDIF", "ABORT", "LBL[2]",
                       "R[2:nCount]=2"]  # fmt: skip


def test_book_err_no_is_a_remark_and_system_errors_stay_todo():
    result = run(FEEDER + """
    PROC Init()
        BookErrNo ERR_JAM;
    ENDPROC
    PROC Divide()
        nCount:=nCount/0;
    ERROR
        IF ERRNO=ERR_DIVZERO THEN
            TRYNEXT;
        ENDIF
    ENDPROC
    PROC Other()
        RAISE ERR_UNKNOWN_HERE;
    ENDPROC""")
    init = next(i for i in result.programs if i.program.name == "INIT")
    assert "!ERR_JAM is error 10000" in [line.text for line in init.program.lines]
    todo = notes(result, "TODO")
    assert any("ERROR handlers are not supported" in t for t in todo)  # the system's error: alarm on FANUC
    assert any("only the program's own errors" in t for t in todo)


def test_a_handler_no_raised_error_reaches_is_converted():
    result = run("""
    PROC Check()
        RAISE ERR_EMPTY;
    ENDPROC
    PROC Station()
        Check;
        nCount:=1;
    ERROR
        IF ERRNO=ERR_EMPTY THEN
            TRYNEXT;
        ENDIF
    ENDPROC""")
    assert notes(result, "TODO") == []
    assert lines(result, "STATION") == ["CALL CHECK", "R[1:nCount]=1"]  # CHECK stops the program: ABORT
    assert any("none of which reaches it" in w for w in notes(result, "WARNING"))
