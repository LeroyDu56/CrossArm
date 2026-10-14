# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""StopMove / StartMove written as CALL CA_STOPMOVE with --karel, in the program and in a TRAP
(crossarm.convert.stop_move, crossarm.convert.interrupts)."""

import re
from datetime import datetime

from helpers import parse_module

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.interrupts import KAREL_HINT
from crossarm.convert.translate import Blocker
from crossarm.fanuc.ls_writer import write_ls
from crossarm.karel import PROGRAMS, source
from crossarm.rapid.eio import Signal

SIGNALS = {"DIGUARD": Signal("diGuard", "DI"), "DIGO": Signal("diGo", "DI"), "DOLAMP": Signal("doLamp", "DO")}
POINTS = ("CONST robtarget pA:=[[800,0,900],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];\n"
          "CONST robtarget pB:=[[800,300,900],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];\n"
          "VAR intnum iGuard;\nVAR intnum iBack;\n")  # fmt: skip


def run(procs: str, karel: bool = True, routines: tuple[str, ...] | None = None):
    text = f"MODULE M\n{POINTS}{procs}\nENDMODULE\n"
    return convert([parse_module(text)], ConversionConfig(timestamp=datetime(2026, 1, 1), karel=karel),
                   routines=list(routines) if routines else None, sources={"M": text}, signals=SIGNALS)  # fmt: skip


def lines(result, name: str) -> list[str]:
    found = next(info.program for info in result.programs if info.program.name == name)
    texts = [getattr(line, "text", None) or f"{line.kind} {line.target}" for line in found.lines]
    return [t for t in texts if not t.startswith(("!RAPID", "UFRAME_NUM", "UTOOL_NUM"))]


def program(result, name: str):
    return next(info.program for info in result.programs if info.program.name == name)


def flags(texts: list[str]) -> list[str]:
    """Lines with the flag the TRAPs set while the robot is paused written F[P], a signal as read F[S]."""
    paused = {m[1] for t in texts if (m := re.fullmatch(r"F\[(\d+)\]=\((ON|OFF)\)", t))}
    return [re.sub(r"F\[(\d+)\]", lambda m: "F[P]" if m[1] in paused else "F[S]", t) for t in texts]


def todos(result) -> list[tuple[str, str]]:
    return [(note.message, note.category) for note in result.notes if note.kind == "TODO"]


IN_LINE = ("PROC main()\nMoveL pA,v500,z50,tool0;\nStopMove;\nWaitDI diGo,1;\nStartMove;\n"
           "MoveL pB,v500,fine,tool0;\nENDPROC\n")  # fmt: skip
ARMING = "PROC main()\nIDelete iGuard;\nCONNECT iGuard WITH tGuard;\nISignalDI diGuard,1,iGuard;\nENDPROC\n"
PAIRED = "TRAP tGuard\nStopMove;\nSetDO doLamp,1;\nWaitDI diGuard,0;\nSetDO doLamp,0;\nStartMove;\nENDTRAP\n"


def test_in_line_stop_and_start_are_karel_stop_and_resume():
    result = run(IN_LINE)
    assert todos(result) == []
    assert lines(result, "MAIN") == ["L P[1]", "CALL CA_STOPMOVE(1,0)", "WAIT DI[1]=ON", "CALL CA_STOPMOVE(0,0)",
                                     "L P[2]"]  # fmt: skip
    assert result.karel_calls == {"CA_STOPMOVE": {"MAIN": 2}}
    warned = [note.message for note in result.notes if note.kind == "WARNING" and "StopMove" in note.message]
    assert len(warned) == 1 and "near the end of a CNT move" in warned[0]


def test_without_karel_they_stay_todo_and_say_karel_converts_them():
    result = run(IN_LINE, karel=False)
    assert [category for _, category in todos(result)] == [Blocker.MOTION, Blocker.MOTION]
    assert all("converts with --karel" in message for message, _ in todos(result))
    assert result.karel_todo == 2


def test_a_move_before_start_move_leaves_the_stop_todo():
    """KAREL STOP does not hold the next move (ROBOGUIDE): RAPID waits for StartMove, FANUC would go."""
    result = run(IN_LINE.replace("WaitDI diGo,1;", "MoveL pB,v500,fine,tool0;"))
    assert [message.split(":")[0] for message, _ in todos(result)] == ["StopMove followed by a move (l.9) before StartMove"]
    assert "CALL CA_STOPMOVE(0,0)" in lines(result, "MAIN")  # StartMove alone: nothing stopped, nothing happens


def test_a_stop_never_started_again_in_its_routine_stays_todo():
    result = run(IN_LINE.replace("StartMove;\nMoveL pB,v500,fine,tool0;\n", ""))
    assert "no StartMove after it in main" in todos(result)[0][0]


def test_quick_is_a_normal_stop_and_all_motion_tasks_is_not_converted():
    quick = run(IN_LINE.replace("StopMove;", "StopMove\\Quick;"))
    assert todos(quick) == [] and "CALL CA_STOPMOVE(1,0)" in lines(quick, "MAIN")
    assert any("normal deceleration" in note.message for note in quick.notes if note.kind == "WARNING")
    every = run(IN_LINE.replace("StopMove;", "StopMove\\AllMotionTasks;"))
    assert "AllMotionTasks" in todos(every)[0][0]
    reset = run(IN_LINE.replace("StartMove;", "StopMoveReset;\nStartMove;"))
    assert [category for _, category in todos(reset)] == [Blocker.MOTION]


def test_a_trap_pausing_the_motion_pauses_the_program_and_ignores_pause_requests():
    result = run(ARMING + PAIRED)
    assert todos(result) == []
    assert flags(lines(result, "TGUARD")) == [
        "LBL[1]", "F[S]=(DI[1])",  # where to run it again from, and its signal as it read it
        "CALL CA_STOPMOVE(1,1)", "F[P]=(ON)", "DO[1]=ON", "WAIT DI[1]=OFF", "DO[1]=OFF", "CALL CA_STOPMOVE(0,1)",
        "F[P]=(OFF)",
        # still paused (a StartMove it did not reach): back off, then on again, as ISignalDI fires
        "IF (F[P]=OFF),JMP LBL[2]", "IF (F[S]=OFF),JMP LBL[3]", "WAIT DI[1]=OFF", "LBL[3]", "WAIT DI[1]=ON",
        "JMP LBL[1]", "LBL[2]", "MONITOR IGUARD"]  # fmt: skip
    trap = program(result, "TGUARD")
    assert trap.attributes.default_group == "*,*,*,*,*" and trap.attributes.pause_request == 2
    assert "PAUSE_REQUEST\t= 2;" in write_ls(trap)
    assert program(result, "MAIN").attributes.pause_request == 0
    warned = [note.message for note in result.notes if note.kind == "WARNING" and "StopMove" in note.message]
    assert len(warned) == 1 and "pendant shows that program paused" in warned[0]


def test_the_start_can_be_in_a_routine_the_trap_calls():
    trap = "TRAP tGuard\nStopMove;\nGoOn;\nENDTRAP\nPROC GoOn()\nWaitDI diGuard,0;\nStartMove;\nENDPROC\n"
    result = run(ARMING + trap)
    assert todos(result) == []
    assert flags(lines(result, "GOON")) == ["WAIT DI[1]=OFF", "CALL CA_STOPMOVE(0,1)", "F[P]=(OFF)"]
    assert program(result, "TGUARD").attributes.pause_request == 2


def test_a_stop_in_one_trap_waits_for_the_trap_starting_the_motion_again():
    """No condition monitor fires while its program is paused (ROBOGUIDE): the stopping TRAP waits for the other
    one's signal and runs it."""
    arming = ARMING.replace("ENDPROC", "CONNECT iBack WITH tBack;\nISignalDI diGo,1,iBack;\nENDPROC")
    traps = "TRAP tGuard\nStopMove;\nClearPath;\nENDTRAP\nTRAP tBack\nStartMove;\nENDTRAP\n"
    result = run(arming + traps)
    assert todos(result) == []
    assert flags(lines(result, "TGUARD")) == [
        "CALL CA_STOPMOVE(1,1)", "F[P]=(ON)", "!l.15 ClearPath",
        "LBL[2]", "IF (F[P]=OFF),JMP LBL[1]", "F[S]=(DI[2])", "IF (F[S]=OFF),JMP LBL[3]", "WAIT DI[2]=OFF", "LBL[3]",
        "WAIT DI[2]=ON", "CALL TBACK", "JMP LBL[2]", "LBL[1]", "MONITOR IGUARD"]  # fmt: skip
    assert flags(lines(result, "TBACK")) == ["CALL CA_STOPMOVE(0,1)", "F[P]=(OFF)", "MONITOR IBACK"]
    assert program(result, "TBACK").attributes.pause_request == 2
    assert any("ClearPath" in note.message for note in result.notes if note.kind == "WARNING")


def test_a_trap_starting_or_stopping_as_its_signal_changes_runs_again_on_each_change():
    trap = "TRAP tGuard\nIF diGuard=1 THEN\nStartMove;\nELSE\nStopMove;\nENDIF\nENDTRAP\n"
    result = run(ARMING.replace("diGuard,1,", "diGuard,edge,") + trap)
    assert todos(result) == []
    body = flags(lines(result, "TGUARD"))
    assert body[:2] == ["LBL[1]", "F[S]=(DI[1])"] and "JMP LBL[1]" in body
    assert body[body.index("IF (F[S]=ON),JMP LBL[3]") + 1 : body.index("JMP LBL[1]")] == [
        "WAIT DI[1]=ON", "JMP LBL[4]", "LBL[3]", "WAIT DI[1]=OFF", "LBL[4]"]  # fmt: skip


def test_what_cannot_wait_for_the_start_stays_todo():
    alone = "TRAP tGuard\nStopMove;\nENDTRAP\n"
    assert "no TRAP armed on a digital signal starts it again" in todos(run(ARMING + alone))[0][0]
    arming = ARMING.replace("ENDPROC", "CONNECT iBack WITH tBack;\nISignalDI diGo,1,iBack;\nENDPROC")
    two = "TRAP tBack\nStartMove;\nENDTRAP\nTRAP tOther\nStartMove;\nENDTRAP\n"
    arming = arming.replace("ENDPROC", "CONNECT iOther WITH tOther;\nISignalDI diGo,0,iOther;\nENDPROC")
    result = run(arming + alone + two, routines=None)
    assert any("several TRAPs start it again" in message for message, _ in todos(result))
    clear = "TRAP tGuard\nClearPath;\nStopMove;\nStartMove;\nENDTRAP\n"
    assert "ClearPath (l.12) with no StopMove before it" in todos(run(ARMING + clear))[0][0]


def test_without_karel_the_trap_says_karel_converts_it():
    messages = [message for message, category in todos(run(ARMING + PAIRED, karel=False))]
    assert messages and all(KAREL_HINT in message for message in messages)
    stored = PAIRED.replace("StartMove;", "StorePath;\nStartMove;")
    assert not any(KAREL_HINT in message for message, _ in todos(run(ARMING + stored, karel=False)))
    assert any("calls StorePath" in message for message, _ in todos(run(ARMING + stored)))


def test_a_shared_trap_stopping_the_motion_stays_todo():
    arming = ARMING.replace("ENDPROC", "CONNECT iBack WITH tGuard;\nISignalDI diGo,1,iBack;\nENDPROC")
    assert any("serves several interrupts" in message for message, _ in todos(run(arming + PAIRED)))


def test_the_library_program():
    text = source(PROGRAMS["CA_STOPMOVE"].source)
    assert "STOP GROUP[1]" in text and "RESUME GROUP[1]" in text
    assert "PAUSE_TASK(task, TRUE, TRUE, status)" in text and "CONT_TASK(task, status)" in text
    assert "POST_ERR_L" not in text and "ERSEV_ABORTL" not in text


def test_a_trap_a_system_module_routine_connects_is_written_with_it():
    """A program calling a system module's routine gets it written; an interrupt that routine arms, its TRAP too."""
    library = parse_module("MODULE Guards(SYSMODULE)\nVAR intnum iLib;\nPROC ArmGuard()\nIDelete iLib;\n"
                           "CONNECT iLib WITH tLib;\nISignalDI diGuard,edge,iLib;\nENDPROC\nTRAP tLib\n"
                           "IF diGuard=1 THEN\nStartMove;\nELSE\nStopMove;\nENDIF\nENDTRAP\nENDMODULE\n")  # fmt: skip
    main = parse_module("MODULE M\nPROC main()\nArmGuard;\nENDPROC\nENDMODULE\n")
    result = convert([main, library], ConversionConfig(timestamp=datetime(2026, 1, 1), karel=True), signals=SIGNALS)
    assert todos(result) == []
    assert {"ARMGUARD", "TLIB", "ILIB"} <= {info.program.name for info in result.programs}
    assert program(result, "TLIB").attributes.pause_request == 2
