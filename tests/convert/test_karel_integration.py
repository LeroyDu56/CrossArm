# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""--karel with the rest: sockets stay TODO and say why, the analysis says what --karel converts and what it does
not, the routines offered for external_routines leave out what --karel converts."""

from datetime import datetime

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.analysis import priority_actions
from crossarm.convert.blockers import Blocker
from crossarm.convert.external import ProvidedRoutine
from crossarm.convert.unsupported import KAREL_SOCKETS
from crossarm.rapid import parse_text

STAMP = datetime(2026, 1, 1)
MODULE = """MODULE KS
  VAR iodev logF;
  VAR socketdev sock;
  PROC Main()
    LogLine "x";
    SendLine "y";
    Missing 1;
  ENDPROC
  PROC LogLine(string text)
    Open "HOME:" \\File:="log.txt", logF \\Append;
    Write logF, text;
    Close logF;
  ENDPROC
  PROC SendLine(string text)
    SocketSend sock \\Str:=text;
  ENDPROC
ENDMODULE
"""


def conversion(karel: bool, **config):
    parsed = parse_text(MODULE, path="KS.mod")
    assert parsed.module is not None, parsed.diagnostics
    return convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=karel, **config), sources={"KS": MODULE})


def todo(result) -> list:
    return [note for note in result.notes if note.kind == "TODO"]


def test_with_karel_sockets_stay_todo_and_say_karel_does_not_convert_them():
    on = conversion(True)
    sockets = [note for note in todo(on) if "sockets:" in note.message]
    assert sockets and all(note.category == Blocker.NO_TP_EQUIVALENT for note in sockets)
    assert all(KAREL_SOCKETS in note.message for note in sockets)
    assert "client tags configured on the robot" in KAREL_SOCKETS
    assert on.karel_programs == ["CA_FILE"]
    off = conversion(False)
    assert not any(KAREL_SOCKETS in note.message for note in todo(off))  # without it, as before
    assert any("SocketSend: sockets: TP has no network messaging —" in note.message for note in todo(off))


def test_what_karel_would_convert_leaves_the_sockets_out():
    off, on = conversion(False), conversion(True)
    assert off.karel_todo == len(todo(off)) - len(todo(on)) > 0
    left = {(note.program, note.rapid_line) for note in todo(on)}
    assert all((note.program, note.rapid_line) in left for note in todo(off) if "sockets:" in note.message)


def test_the_analysis_says_what_karel_converts_and_that_sockets_stay_todo():
    off = priority_actions(conversion(False))
    again = next(a for a in off if a.title.startswith("Convert again with `--karel`"))
    assert again.detail.startswith(f"{conversion(False).karel_todo} TODO converted then")
    assert "(.pc) before the .LS" in again.detail and "R632" in again.detail and "Sockets stay TODO" in again.detail
    on = priority_actions(conversion(True))
    assert not any(a.title.startswith("Convert again") for a in on)
    load = next(a for a in on if a.title.startswith("Load the 1 KAREL program"))
    assert ".pc of the KAREL folder before the .LS" in load.detail and "R632" in load.detail
    redo = next(a for a in on if a.title == "Redo what TP has nothing for on the FANUC side")
    assert "Sockets stay TODO with `--karel`" in redo.detail


def test_the_routines_offered_leave_out_what_karel_converts():
    provided = {"MISSING": ProvidedRoutine("Missing", "MISSING_TP")}
    for given in ({}, provided):  # with or without external_routines already given
        off = {c.name for c in conversion(False, external_routines=given).provided_candidates}
        on = {c.name for c in conversion(True, external_routines=given).provided_candidates}
        assert {"LogLine", "SendLine"} <= off
        assert "SendLine" in on and "LogLine" not in on  # files: converted by CA_FILE; sockets: not


def test_a_routine_given_in_external_routines_is_never_converted_by_karel():
    provided = {"LOGLINE": ProvidedRoutine("LogLine", "LOGLINE_TP")}
    result = conversion(True, external_routines=provided)
    names = {info.program.name for info in result.programs}
    assert "LOGLINE" not in names and result.karel_programs == []
    assert any(use.program == "LOGLINE_TP" and use.calls for use in result.provided)
