# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""StopMove and StartMove: the robot's motion paused and resumed, in the program and in a TRAP (--karel; a mixin
of the routine translator).

    StopMove;                 CALL CA_STOPMOVE(1,0)      in the program moving the robot: KAREL STOP
    WaitDI diGo, 1;           WAIT DI[4]=ON
    StartMove;                CALL CA_STOPMOVE(0,0)      KAREL RESUME

    TRAP tGuard               (condition monitor's TRAP, PAUSE_REQUEST = 2: it ignores pause requests)
        StopMove;             CALL CA_STOPMOVE(1,1)      the task holding the robot paused (PAUSE_TASK)
                              F[5:Robot paused]=ON
        WaitDI diGuard, 0;    WAIT DI[3]=OFF
        StartMove;            CALL CA_STOPMOVE(0,1)      and continued (CONT_TASK)
                              F[5:Robot paused]=OFF
                              IF F[5]=OFF,JMP LBL[2]     still paused: wait for the change that starts it again
                              ...                        (see resume_epilogue), then run that TRAP

TP has no instruction stopping the robot's motion. Measured on ROBOGUIDE (R-1000iA/80F V10.10, KAREL R632):
- in the moving program, KAREL STOP stops the motion under way, RESUME goes on with it on the same path, to the same
  point; with nothing stopped, or twice, neither does anything. STOP does not hold the moves after it: the next
  move line goes (RAPID waits for StartMove), so a StopMove converts only when the same routine starts the motion
  again before any move. TP runs the line after a CNT move near its end only (9 mm before the point at 100 mm/s),
  RAPID earlier: the robot stops further along the same path.
- a TRAP runs as a task without a motion group: KAREL HOLD from it stops the robot, but UNHOLD and RESUME fail
  (INTP-350 / INTP-353, PROG-040 Already locked by other task), and STOP does not hold it. PAUSE_TASK of the task
  holding the robot stops the motion, CONT_TASK resumes it where it stopped, to the same point (0.000 mm); the
  TRAP is paused with that task unless its program ignores pause requests by command (PAUSE_REQUEST = 2; 1 or 4 is
  not enough). No condition monitor fires while its program is paused, not even for a change made meanwhile once
  it goes on: a TRAP leaving the motion stopped waits for the signal of the interrupt that starts it again and runs
  its TRAP itself (crossarm.convert.interrupts.Interrupt.resumer), the program's own logic waiting meanwhile
  (RAPID's runs on to its next move).
- ClearPath after a StopMove in a TRAP: a remark; the move paused goes on to its point (RAPID plans it again from
  where the robot stopped, along the same line for a linear move).
ExitCycle (--karel), in the program or in a TRAP: CALL CA_EXITCYCLE(1), which starts itself as a task of its own
(RUN_TASK) that aborts the task holding the robot (ABORT_TASK, motion cancelled) and runs it again from its first
line, the caller waiting to be aborted with it: measured on ROBOGUIDE, in line and in a TRAP after a StopMove
(PAUSE_TASK); aborting it directly from the TRAP ends the TRAP too, nothing runs again; a task aborted while paused
stays aborted when RUN_TASK follows at once (it accepts): 0.1 s first.
Without --karel all of them stay TODO.
"""

from crossarm.convert.blockers import Blocker, Untranslatable
from crossarm.convert.interrupts import Interrupt, motion_stops, moves
from crossarm.rapid import nodes as n
from crossarm.rapid.walk import walk_statements

PROGRAM = "CA_STOPMOVE"
EXIT_PROGRAM = "CA_EXITCYCLE"  # RAPID ExitCycle (--karel)
INSTRUCTIONS = frozenset({"STOPMOVE", "STARTMOVE", "CLEARPATH", "STOPMOVERESET", "STARTMOVERETRY"})
IGNORE_PAUSE = 2  # PAUSE_REQUEST of a TRAP pausing the robot: it runs on while the program it paused waits
PAUSED_KEY = "CROSSARM.STOPPED"  # the flag a TRAP sets while the robot is paused (mapping key, flags)
SEEN_KEY = "CROSSARM.STOPMOVE."  # + interrupt: its signal as the TRAP waiting for it last read it
_NOT_CONVERTED = {
    "STOPMOVERESET": "it clears the stop state of a motion stopped by StopMove; a FANUC motion has none to clear",
    "STARTMOVERETRY": "StartMove and RETRY of an error handler in one; not converted",
}


class StopMoves:
    """The routine translator's part that writes StopMove / StartMove (mixed into it): needs c, emit(), label(),
    routine, name, epilogue."""

    def stop_move(self, call: n.ProcCall, name: str) -> None:
        if name in _NOT_CONVERTED:
            raise Untranslatable(f"{call.name}: {_NOT_CONVERTED[name]}", Blocker.MOTION)
        options = {(a.name or "").upper() for a in call.args if a.name is not None}
        if any(a.name is None for a in call.args) or not options <= {"QUICK", "ALLMOTIONTASKS"}:
            raise Untranslatable(f"{call.name} with these arguments is not converted", Blocker.MOTION)
        if "ALLMOTIONTASKS" in options:
            raise Untranslatable(f"{call.name} \\AllMotionTasks: CrossArm stops and starts the robot of the program"
                                 " only", Blocker.MOTION)  # fmt: skip
        if not self.c.config.karel:  # type: ignore[attr-defined]
            raise Untranslatable(f"{call.name}: TP has no instruction stopping the robot's motion and resuming it;"
                                 f" converts with --karel (CrossArm's KAREL program {PROGRAM})", Blocker.MOTION)  # fmt: skip
        routine = self.routine.name.upper()  # type: ignore[attr-defined]
        trap = self.routine.kind == "TRAP" or routine in self.c.trap_side  # type: ignore[attr-defined]
        if trap and routine in self.c.both_sides:  # type: ignore[attr-defined]
            raise Untranslatable(f"{call.name} in a routine both a TRAP and the programs call: stopping the robot"
                                 " is written differently in each", Blocker.MOTION)  # fmt: skip
        if name == "CLEARPATH":
            self._clear_path(call, trap)
            return
        if not trap and name == "STOPMOVE":
            self._started_again(call)
        stop = 1 if name == "STOPMOVE" else 0
        self.emit(f"CALL {PROGRAM}({stop},{1 if trap else 0})")  # type: ignore[attr-defined]
        if trap:
            self.emit(f"{self.paused_flag()}=({'ON' if stop else 'OFF'})")  # type: ignore[attr-defined]
        if "QUICK" in options:
            self.c.warn_once(f"stopmove-quick:{self.name}", self.name, call.span.line,  # type: ignore[attr-defined]
                             "StopMove \\Quick: the robot stops with its normal deceleration",
                             Blocker.OPTIONS_IGNORED)  # fmt: skip
        if name != "STOPMOVE":
            return
        if trap:
            why = ("pauses the program holding the robot, motion included, until a StartMove of a TRAP continues it"
                   " where it stopped (ROBOGUIDE); meanwhile the pendant shows that program paused, its logic waits"
                   " too (RAPID's runs on to its next move), and the TRAP's program ignores pause requests by command"
                   " (PAUSE_REQUEST = 2) to run on")  # fmt: skip
        else:
            why = ("stops the motion under way, and StartMove resumes it on the same path (ROBOGUIDE); TP runs this"
                   " line near the end of a CNT move only, RAPID earlier: the robot stops further along the path")
        self.c.warn_once(f"stopmove:{self.name}", self.name, call.span.line,  # type: ignore[attr-defined]
                         f"StopMove: CrossArm's KAREL program {PROGRAM} {why}", Blocker.OTHER)

    def exit_cycle(self, call: n.ProcCall) -> None:
        """ExitCycle, in the program or in a TRAP (--karel): CALL CA_EXITCYCLE(1), which aborts the task holding the
        robot and runs it again from its first line; the line after the CALL never runs (measured 1.14-02)."""
        if call.args:
            raise Untranslatable(f"{call.name} with arguments is not converted", Blocker.MOTION)
        if not self.c.config.karel:  # type: ignore[attr-defined]
            raise Untranslatable(f"{call.name}: TP cannot end the cycle and start the program again from its first"
                                 f" line; converts with --karel (CrossArm's KAREL program {EXIT_PROGRAM})",
                                 Blocker.MOTION)  # fmt: skip
        routine = self.routine.name.upper()  # type: ignore[attr-defined]
        trap = self.routine.kind == "TRAP" or routine in self.c.trap_side  # type: ignore[attr-defined]
        stops = motion_stops(self.routine, self.c.procs)  # type: ignore[attr-defined]
        if trap and any(c.name.upper() == "STOPMOVE" for c in stops):
            self.emit(f"{self.paused_flag()}=(OFF)")  # type: ignore[attr-defined]  # the robot no longer paused
        self.emit(f"CALL {EXIT_PROGRAM}(1)")  # type: ignore[attr-defined]
        self.c.warn_once(f"exitcycle:{self.name}", self.name, call.span.line,  # type: ignore[attr-defined]
                         f"ExitCycle: CrossArm's KAREL program {EXIT_PROGRAM} aborts the program holding the robot,"
                         " its motion cancelled, and runs it again from its first line (ABORT_TASK, RUN_TASK,"
                         " ROBOGUIDE): the program started on the robot, which may call the one converted from"
                         " RAPID's main routine; data keep their values, as in RAPID. The robot goes from where it"
                         " stopped to the first move of the cycle: check that path", Blocker.OTHER)  # fmt: skip

    def paused_flag(self) -> str:
        number = self.c.flags.number("Robot paused", PAUSED_KEY, "", by_name=False)  # type: ignore[attr-defined]
        return f"F[{number}:Robot paused]"

    def _clear_path(self, call: n.ProcCall, trap: bool) -> None:
        """ClearPath in a TRAP, after its StopMove (crossarm.convert.interrupts.unpaired): a remark."""
        if not trap:
            raise Untranslatable("ClearPath: CrossArm writes it in a TRAP after a StopMove only", Blocker.MOTION)
        self.emit(f"!l.{call.span.line} ClearPath")  # type: ignore[attr-defined]
        self.c.warn_once(f"clearpath:{self.name}", self.name, call.span.line,  # type: ignore[attr-defined]
                         "ClearPath: the move paused goes on to its point when the motion starts again (RAPID plans"
                         " it again from where the robot stopped: the same line for a linear move)", Blocker.OTHER)  # fmt: skip

    # -- a TRAP leaving the robot paused waits for the interrupt that starts it again -------------------------------

    def resume_prologue(self, interrupt: Interrupt) -> None:
        """A TRAP starting the motion again itself: a label to run it again from, and its signal as it reads it."""
        if interrupt.resumer != interrupt.name.upper():
            return
        self.resume_top = self.label()  # type: ignore[attr-defined]
        self.emit(f"LBL[{self.resume_top}]")  # type: ignore[attr-defined]
        signal, _ = self._resumer_signal(interrupt)
        self.emit(f"{self._seen_flag(interrupt)}=({signal})")  # type: ignore[attr-defined]

    def resume_epilogue(self, interrupt: Interrupt) -> list[str]:
        """Lines ending a TRAP that stops the robot: while it is paused, wait for the change of the signal that
        starts it again, then run that TRAP (this one from the top, or the other one), as its interrupt would."""
        resumer = self.c.interrupts[interrupt.resumer]  # type: ignore[attr-defined]
        signal, edges = self._resumer_signal(resumer)
        seen = self._seen_flag(resumer)
        done = self.label()  # type: ignore[attr-defined]
        wait = 0 if resumer is interrupt else self.label()  # type: ignore[attr-defined]
        lines = [] if resumer is interrupt else [f"LBL[{wait}]"]
        lines.append(f"IF ({self.paused_flag()}=OFF),JMP LBL[{done}]")
        if resumer is not interrupt:
            lines.append(f"{seen}=({signal})")
        if edges == {"ON+", "OFF-"}:  # any change of what it read
            on, after = self.label(), self.label()  # type: ignore[attr-defined]
            lines += [f"IF ({seen}=ON),JMP LBL[{on}]", f"WAIT {signal}=ON", f"JMP LBL[{after}]", f"LBL[{on}]",
                      f"WAIT {signal}=OFF", f"LBL[{after}]"]  # fmt: skip
        else:  # one edge: back first if it is already there
            level, other = ("ON", "OFF") if edges == {"ON+"} else ("OFF", "ON")
            skip = self.label()  # type: ignore[attr-defined]
            lines += [f"IF ({seen}={other}),JMP LBL[{skip}]", f"WAIT {signal}={other}", f"LBL[{skip}]",
                      f"WAIT {signal}={level}"]  # fmt: skip
        if resumer is interrupt:
            lines.append(f"JMP LBL[{self.resume_top}]")  # type: ignore[attr-defined]
        else:
            trap = self.c.program_names[resumer.trap]  # type: ignore[attr-defined]
            lines += [f"CALL {trap}", f"JMP LBL[{wait}]"]
        lines.append(f"LBL[{done}]")
        what = "it runs again" if resumer is interrupt else f"it runs TRAP {resumer.trap}"
        self.c.warn_once(f"stopmove-wait:{self.name}", self.name, None,  # type: ignore[attr-defined]
                         f"{self.name} waits while the robot is paused for {signal} to change as {resumer.name} fires,"
                         f" then {what}: no condition monitor fires while the program it paused waits (ROBOGUIDE)",
                         Blocker.MONITOR)  # fmt: skip
        return lines

    def _seen_flag(self, interrupt: Interrupt) -> str:
        key = f"{SEEN_KEY}{interrupt.name.upper()}"
        number = self.c.flags.number(key, key, "", by_name=False)  # type: ignore[attr-defined]
        return f"F[{number}]"

    def _resumer_signal(self, interrupt: Interrupt) -> tuple[str, set[str]]:
        """'DI[3]', {'ON+'} / {'OFF-'} / both: the signal an interrupt starting the motion is armed on."""
        assert interrupt.signal is not None and interrupt.trigger is not None
        ref = self.c.signal(interrupt.signal, self.name, self.routine.span.line)  # type: ignore[attr-defined]
        trigger = interrupt.trigger
        if isinstance(trigger, n.Name) and trigger.name.upper() == "EDGE":
            value = "2"
        else:
            value = self.numeric(trigger)  # type: ignore[attr-defined]
        edges = {"1": {"ON+"}, "0": {"OFF-"}, "2": {"ON+", "OFF-"}}.get(value)
        if ref is None or edges is None:
            raise Untranslatable(f"TRAP of {interrupt.name}: its signal or its value is not known", Blocker.INTERRUPT)
        return ref.split(":", 1)[0] + "]" if ":" in ref else ref, edges

    def _started_again(self, call: n.ProcCall) -> None:
        """A StopMove in the moving program: the same routine must call StartMove after it, before any move
        (KAREL STOP does not hold the next move, RAPID does)."""
        found = False
        for stmt in walk_statements(self.routine.body):  # type: ignore[attr-defined]
            if stmt is call:
                found = True
                continue
            if not found:
                continue
            if isinstance(stmt, n.ProcCall) and stmt.name.upper() == "STARTMOVE":
                return
            if isinstance(stmt, n.Move) or (isinstance(stmt, n.ProcCall) and self._moving(stmt)):
                raise Untranslatable(f"StopMove followed by a move (l.{stmt.span.line}) before StartMove: on FANUC the"
                                     " move would go at once (KAREL STOP does not hold the next move)", Blocker.MOTION)  # fmt: skip
        raise Untranslatable(f"StopMove with no StartMove after it in {self.routine.name}: on FANUC the next move"  # type: ignore[attr-defined]
                             " would go at once (KAREL STOP does not hold the next move)", Blocker.MOTION)  # fmt: skip

    def _moving(self, call: n.ProcCall) -> bool:
        name = call.name.upper()
        if name in self.c.move_routines:  # type: ignore[attr-defined]
            return True
        if name.startswith(("MOVE", "SEARCH", "TRIGG")):
            return True
        procs = self.c.procs  # type: ignore[attr-defined]
        return name in procs and bool(moves(procs[name], procs, set(self.c.move_routines)))  # type: ignore[attr-defined]


__all__ = ["EXIT_PROGRAM", "IGNORE_PAUSE", "INSTRUCTIONS", "PAUSED_KEY", "PROGRAM", "SEEN_KEY", "StopMoves"]
