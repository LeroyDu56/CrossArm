# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""RAPID interrupts converted to FANUC condition monitors (crossarm.convert.interrupts)."""

from datetime import datetime

from helpers import parse_module

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.translate import Blocker
from crossarm.fanuc.ls_parser import parse_ls
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid.eio import Signal

SIGNALS = {"DISTOP": Signal("diStop", "DI"), "DOLAMP": Signal("doLamp", "DO")}


def run(procs: str, data: str = "", routines: tuple[str, ...] = ("main", "tStop")):
    source = f"MODULE M\nVAR intnum iStop;\nVAR num nStops:=0;\n{data}\n{procs}\nENDMODULE\n"
    return convert([parse_module(source)], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=list(routines),
                   sources={"M": source}, signals=SIGNALS)  # fmt: skip


def program(result, name: str) -> list[str]:
    found = next(info.program for info in result.programs if info.program.name == name)
    lines = [getattr(line, "text", None) or f"{line.kind} {line.target}" for line in found.lines]
    return [line for line in lines if not line.startswith("!RAPID")]


def todos(result) -> list[str]:
    return [note.message for note in result.notes if note.kind == "TODO"]


MAIN = "PROC main()\nIDelete iStop;\nCONNECT iStop WITH tStop;\nISignalDI diStop,1,iStop;\nENDPROC\n"
TRAP = "TRAP tStop\nnStops:=nStops+1;\nENDTRAP\n"


def test_isignaldi_arms_a_condition_program_calling_the_trap():
    result = run(MAIN + TRAP)
    assert todos(result) == []
    assert program(result, "MAIN") == ["MONITOR END ISTOP", "MONITOR ISTOP"]  # IDelete, CONNECT (nothing), ISignalDI
    condition = next(info.program for info in result.programs if info.program.name == "ISTOP")
    assert condition.condition and condition.attributes.default_group == "*,*,*,*,*"
    assert [line.text for line in condition.lines] == ["WHEN DI[1]=ON+,CALL TSTOP"]


def test_the_trap_runs_without_a_motion_group_and_arms_its_condition_again():
    """The controller disarms a condition program when it fires; RAPID's interrupt stays armed."""
    result = run(MAIN + TRAP)
    trap = next(info.program for info in result.programs if info.program.name == "TSTOP")
    assert trap.attributes.default_group == "*,*,*,*,*"
    assert program(result, "TSTOP") == ["R[1:nStops]=R[1:nStops]+1", "MONITOR ISTOP"]


def test_a_single_interrupt_is_not_armed_again():
    result = run(MAIN.replace("ISignalDI ", "ISignalDI\\Single,") + TRAP)
    assert program(result, "TSTOP") == ["R[1:nStops]=R[1:nStops]+1"]


def test_a_return_in_the_trap_arms_it_again_first():
    trap = "TRAP tStop\nIF nStops>5 RETURN;\nnStops:=nStops+1;\nENDTRAP\n"
    lines = program(run(MAIN + trap), "TSTOP")
    assert lines[:3] == ["IF (R[1:nStops]>5) THEN", "MONITOR ISTOP", "END"]
    assert lines[-1] == "MONITOR ISTOP"


def test_falling_edge_and_both_edges():
    result = run(MAIN.replace("diStop,1", "diStop,0") + TRAP)
    assert [line.text for line in result.programs[-1].program.lines] == ["WHEN DI[1]=OFF-,CALL TSTOP"]
    result = run(MAIN.replace("diStop,1", "diStop,edge") + TRAP)
    assert [line.text for line in result.programs[-1].program.lines] == ["WHEN DI[1]=ON+,CALL TSTOP",
                                                                         "WHEN DI[1]=OFF-,CALL TSTOP"]  # fmt: skip


def test_isignaldo_watches_the_output():
    result = run(MAIN.replace("ISignalDI diStop", "ISignalDO doLamp") + TRAP)
    assert [line.text for line in result.programs[-1].program.lines] == ["WHEN DO[1]=ON+,CALL TSTOP"]


def test_ipers_compares_the_data_with_its_value_when_last_seen():
    main = "PROC main()\nCONNECT iStop WITH tStop;\nIPers nState,iStop;\nENDPROC\n"
    result = run(main + TRAP, data="PERS num nState:=0;")
    assert todos(result) == []
    assert program(result, "MAIN") == ["R[2:iStopSeen]=R[1]", "MONITOR ISTOP"]  # R[1]: nState, only read
    assert program(result, "TSTOP")[0] == "R[2:iStopSeen]=R[1]"
    assert [line.text for line in result.programs[-1].program.lines] == ["WHEN R[1]<>R[2:iStopSeen],CALL TSTOP"]


def test_isleep_and_iwatch_end_and_arm_the_monitor():
    main = MAIN.replace("ENDPROC", "ISleep iStop;\nIWatch iStop;\nENDPROC")
    assert program(run(main + TRAP), "MAIN")[-2:] == ["MONITOR END ISTOP", "MONITOR ISTOP"]


def test_data_a_trap_changes_is_never_taken_as_known():
    """The main program sets nStops to 0, but the TRAP may count it up at any time: a point offset by it
    is not worked out with 0, but offset by its register when the move runs."""
    home = "CONST robtarget pHome:=[[600,0,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];"
    tool = "PERS tooldata tGrip:=[TRUE,[[0,0,185.5],[1,0,0,0]],[2.4,[0,0,90],[1,0,0,0],0,0,0]];"
    main = MAIN.replace("ENDPROC", "nStops:=0;\nMoveL Offs(pHome,0,0,nStops),v100,fine,tGrip;\nENDPROC")
    result = run(main + TRAP, data=home + tool)
    assert todos(result) == []
    lines = program(result, "MAIN")
    assert "PR[99,3]=PR[99,3]+R[1:nStops]" in lines and lines[-1] == "L PR[99]"


def test_a_trap_that_moves_the_robot_stays_todo():
    """A condition monitor calls a program without a motion group."""
    trap = "TRAP tStop\nStopMove;\nClearPath;\nStartMove;\nENDTRAP\n"
    result = run(MAIN + trap)
    assert [n.category for n in result.notes if n.kind == "TODO"] == [Blocker.INTERRUPT] * 3
    assert "calls StopMove" in todos(result)[0]
    assert ("M", "tStop", next(r for _, name, r in result.skipped_routines if name == "tStop")) in result.skipped_routines
    assert not any(info.program.condition for info in result.programs)


def test_itimer_stays_todo_and_so_does_its_interrupt():
    main = "PROC main()\nIDelete iStop;\nCONNECT iStop WITH tStop;\nITimer 60,iStop;\nENDPROC\n"
    result = run(main + TRAP)
    assert len(todos(result)) == 3
    assert all("ITimer" in message for message in todos(result))


def test_an_interrupt_armed_nowhere_converted_ends_nothing():
    """Its ISignalDI stays TODO (a signal with no mapping): no condition program is written, and the lines
    that would arm or end it say so instead of naming a program that is not there."""
    main = MAIN.replace("ISignalDI diStop", "ISignalDI nStops")
    result = run(main + TRAP)
    assert not any(info.program.condition for info in result.programs)
    assert program(result, "MAIN")[0] == "!iStop not armed"
    assert "MONITOR ISTOP" not in program(result, "TSTOP")


SHARED = ("PROC main()\nCONNECT iStop WITH tStop;\nISignalDI diStop,1,iStop;\nCONNECT iOther WITH tStop;\n"
          "ISignalDI\\Single,diStop,0,iOther;\nENDPROC\n")  # fmt: skip


def test_a_trap_two_interrupts_share_is_called_through_a_relay_each():
    """The relay notes its interrupt (what INTNO reads), calls the TRAP and arms its own condition again, unless
    \\Single; the TRAP arms nothing itself."""
    trap = "TRAP tStop\nTEST INTNO\nCASE iStop:\nnStops:=nStops+1;\nCASE iOther:\nnStops:=nStops+10;\nENDTEST\nENDTRAP\n"
    result = run(SHARED + trap, data="VAR intnum iOther;")
    assert todos(result) == []
    programs = {info.program.name: [line.text for line in info.program.lines] for info in result.programs}
    assert programs["ISTOP"] == ["WHEN DI[1]=ON+,CALL ISTOP_T"]
    assert programs["IOTHER"] == ["WHEN DI[1]=OFF-,CALL IOTHER_T"]
    assert programs["ISTOP_T"] == ["R[1:IntNo]=1", "CALL TSTOP", "MONITOR ISTOP"]
    assert programs["IOTHER_T"] == ["R[1:IntNo]=2", "CALL TSTOP"]  # \\Single: not armed again
    trap_lines = programs["TSTOP"]
    assert "SELECT R[1:IntNo]=1,JMP LBL[2]" in trap_lines and not any("MONITOR" in t for t in trap_lines)


def test_a_trap_serving_one_interrupt_and_reading_intno_is_called_through_a_relay_too():
    """INTNO is the register the relay sets, whatever the TRAP serves: never a test on constants."""
    trap = "TRAP tStop\nIF INTNO=iStop nStops:=nStops+1;\nENDTRAP\n"
    result = run(MAIN + trap)
    assert program(result, "TSTOP")[0] == "IF (R[1:IntNo]=1) THEN"
    assert program(result, "ISTOP_T") == ["R[1:IntNo]=1", "CALL TSTOP", "MONITOR ISTOP"]


def test_the_condition_program_round_trips_through_the_ls_parser():
    condition = run(MAIN + TRAP).programs[-1].program
    text = write_ls(condition)
    assert text.startswith("/PROG  ISTOP\t  Cond\r\n")
    assert parse_ls(text).condition and write_ls(parse_ls(text)) == text


def test_monitor_warning_says_what_may_be_missed():
    result = run(MAIN + TRAP)
    (warning,) = [n for n in result.notes if n.category == Blocker.MONITOR]
    assert "0.05 s" in warning.message and warning.program == "ISTOP"


def test_a_routine_the_trap_calls_holds_no_motion_group_either():
    """The TRAP runs as a task of its own while the program it interrupted holds the robot: a program with a
    motion group called from it fails (ROBOGUIDE: INTP-222, PROG-040 Already locked by other task)."""
    trap = "TRAP tStop\nCount;\nENDTRAP\nPROC Count()\nnStops:=nStops+1;\nENDPROC\n"
    result = run(MAIN + trap, routines=("main", "tStop", "Count"))
    groups = {info.program.name: info.program.attributes.default_group for info in result.programs}
    assert groups["COUNT"] == groups["TSTOP"] == "*,*,*,*,*"
    assert groups["MAIN"] == "1,*,*,*,*"
