# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""What the window says, in plain words: kept apart from Tkinter so it can be tested.

The desktop app is used by people who will not read a log. Each step tells them
what CrossArm understood from their input, and the result tells them what needs
their attention first, in the order they should deal with it.
"""

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from crossarm.convert.analysis import Verdict, blocking_causes, decide, todo_causes
from crossarm.convert.translate import Blocker
from crossarm.fanuc.maketp import FOLDER as TP_FOLDER
from crossarm.fanuc.usage import ControllerUsage
from crossarm.pipeline import Inspection, RunOutput

RESOURCE_NAMES = {
    "UFRAME": "User frames (UFRAME)", "UTOOL": "Tool frames (UTOOL)", "R": "Registers (R)",
    "PR": "Position registers (PR)", "F": "Flags (F)", "DO": "Digital outputs (DO)",
    "DI": "Digital inputs (DI)", "GO": "Group outputs (GO)", "GI": "Group inputs (GI)", "TIMER": "Timers (TIMER)",
}  # fmt: skip


def plural(count: int, word: str, words: str | None = None) -> str:
    return f"{count} {word if count == 1 else (words or word + 's')}"


def describe_source(info: Inspection) -> str:
    """'ABB backup "Cell A": 2 robot tasks, 32 RAPID modules. I/O types read from EIO.cfg (210 signals).'"""
    if info.kind == "backup":
        tasks = ", ".join(f"{name} ({count})" for name, count in info.tasks)
        text = (f'ABB backup "{info.name}": {plural(len(info.tasks), "robot task")}, '
                f"{plural(info.modules, 'RAPID module')} — {tasks}.")  # fmt: skip
    elif len(info.tasks) > 1:  # modules of the same name in several folders: a task per folder
        tasks = ", ".join(f"{name} ({count})" for name, count in info.tasks)
        text = (f"{plural(info.modules, 'RAPID module')} ({info.name}), modules of the same name in several "
                f"folders: {plural(len(info.tasks), 'folder')} converted apart — {tasks}.")  # fmt: skip
    else:
        text = f"{plural(info.modules, 'RAPID module')} ({info.name})."
    if info.eio_signals is not None:
        text += f" I/O types read from EIO.cfg ({plural(info.eio_signals, 'signal')})."
    else:
        text += " No EIO.cfg: I/O types are guessed from how the programs use them."
    return text


def describe_controller(usage: ControllerUsage) -> str:
    """'25 programs read. Already in use, left free: UTOOL 3, R 40, DO 32.'"""
    if not usage.programs:
        return "No FANUC program found in it."
    text = f"{plural(len(usage.programs), 'program')} read."
    summary = usage.summary()
    text += " Nothing in use to avoid." if summary == "none" else f" Already in use, left free: {summary}."
    return text


WARN, INFO, GOOD = "warn", "info", "good"


@dataclass
class Summary:
    programs: int
    ready: int  # converted with no TODO
    to_review: int  # TODO entries
    folder: Path
    converted: float | None = None  # percent of the RAPID instructions converted; None: nothing to count
    # (level, text), most important first. WARN: must be dealt with before the programs are
    # loaded or run; INFO: where the work is; GOOD: something that went as it should.
    attention: list[tuple[str, str]] = field(default_factory=list)
    report: Path | None = None
    # The decision, every task counted together, by the rule of the report's analysis (crossarm.convert.analysis).
    decision: Verdict | None = None


def summarize(run: RunOutput) -> Summary:
    ready = sum(t.result.clean_programs() for t in run.tasks if t.result)
    report = next((t.report_html for t in run.tasks if t.report_html), None)
    coverage = run.coverage
    summary = Summary(run.programs, ready, run.todo, run.folder, coverage.percent if coverage.total else None,
                      report=report)  # fmt: skip
    several = len(run.tasks) > 1
    attention = summary.attention
    notes = [note for t in run.tasks if t.result for note in t.result.notes]
    summary.decision = decide(
        programs=run.programs, percent=coverage.percent, todo=run.todo, blocking=blocking_causes(notes),
        over=[c.resource for t in run.tasks if t.result for c in t.result.capacity if not c.fits],
        causes=todo_causes(notes),
    )  # fmt: skip

    # 1. What stops the programs from loading at all.
    for task in run.tasks:
        where = f"{task.task}: " if several else ""
        for c in task.result.capacity if task.result else []:
            if not c.fits:
                attention.append((WARN, (
                    f"{where}{RESOURCE_NAMES.get(c.resource, c.resource)}: {c.highest} needed, "
                    f"the controller holds {c.limit}. Pin numbers in the mapping file or raise the limit."
                )))  # fmt: skip
    # 1b. What the robot must know before it moves: nothing in the programs sets the payload.
    payloads = sum(len(t.result.payloads()) + len(t.result.unknown_payloads()) for t in run.tasks if t.result)
    if payloads:
        text = (f"Set the payload of {plural(payloads, 'tool')} on the robot (PAYLOAD) before running: "
                "mass and centre of gravity are in the report.")  # fmt: skip
        attention.append((WARN, text))
    # 1c. A bug in CrossArm, caught on one statement: the rest was converted, this must be reported.
    internal = sum(1 for t in run.tasks if t.result for n in t.result.notes if n.category == Blocker.INTERNAL)
    if internal:
        text = (f"{plural(internal, 'statement')} hit an internal error in CrossArm and {'is' if internal == 1 else 'are'}"
                " marked TODO: please send the report and crossarm_log.txt so it can be fixed.")  # fmt: skip
        attention.append((WARN, text))
    # 2. Code that was not read.
    errors = sum(len(t.syntax_errors) for t in run.tasks)
    if errors:
        verb = "was" if errors == 1 else "were"
        text = f"{plural(errors, 'RAPID statement')} could not be read and {verb} skipped: listed at the end of the report."
        attention.append((WARN, text))
    # 2b. The frames: one program sets them all, rather than every value typed on the pendant.
    setups = [t.result.setup.program.name for t in run.tasks
              if t.result and t.result.setup and t.result.setup.program]  # fmt: skip
    if setups:
        frames = sum(len(t.result.setup.written) for t in run.tasks if t.result and t.result.setup)
        text = (f"{' and '.join(f'{name}.LS' for name in setups)} set{'s' if len(setups) == 1 else ''} the"
                f" {plural(frames, 'tool and user frame')} on the robot: run {'it' if len(setups) == 1 else 'them'}"
                " once before the programs instead of typing the values in.")  # fmt: skip
        attention.append((INFO, text))
    # 2c. Programs the user did not ask for, but which the others call.
    called = sum(len(t.result.from_system) for t in run.tasks if t.result)
    if called:
        text = (f"{plural(called, 'routine')} of the system modules {'is' if called == 1 else 'are'} written too:"
                " the programs call them, so the robot needs them.")  # fmt: skip
        attention.append((INFO, text))
    # 2d. Frames past what the controller holds: loaded from position registers, which must stay free.
    banked = [f for t in run.tasks if t.result for f in [*t.result.utools, *t.result.uframes] if f.bank is not None]
    if banked:
        registers = sorted(f.bank for f in banked if f.bank is not None)
        text = (f"{plural(len(banked), 'tool or user frame')} past what the controller holds "
                f"{'is' if len(banked) == 1 else 'are'} kept in PR[{registers[0]}] to PR[{registers[-1]}] and loaded "
                "before use: keep those registers free, or raise the controller's number of frames and set it "
                "under limits in the mapping file.")  # fmt: skip
        attention.append((INFO, text))
    # 1d. Speeds and zones measured on another arm than the target's.
    config = run.config
    if config is not None and config.target_robot and not config.motion_profile_source:
        attention.append((WARN, (
            f"Target robot {config.target_robot}: speeds and zones were measured on the "
            f"{config.motion_profile.name}, and another arm can differ by twice as much. Check joint speeds and "
            "corners on the robot, or measure it (see the report)."
        )))  # fmt: skip
    # 2e. Corners the FANUC cannot round as much as the ABB did at that speed.
    capped = sum(1 for t in run.tasks if t.result for use in t.result.zones.values() if use.capped)
    if capped:
        text = (f"{plural(capped, 'zone')} {'is' if capped == 1 else 'are'} rounder on the ABB than CNT100 at the same"
                " speed: the FANUC path stays closer to those points (listed in the report).")  # fmt: skip
        attention.append((INFO, text))
    # 3. Numbers pinned onto the robot's own.
    taken = sum(1 for t in run.tasks if t.result for n in t.result.notes if n.category == Blocker.TAKEN)
    if taken:
        verb = "is" if taken == 1 else "are"
        text = (f"{plural(taken, 'number')} pinned in your mapping file {verb} already used on the FANUC robot: "
                "intended if it is the same signal or frame.")  # fmt: skip
        attention.append((INFO, text))
    renamed = sum(1 for t in run.tasks if t.result for n in t.result.notes if n.category == Blocker.RENAMED)
    if renamed:
        text = (f"{plural(renamed, 'program')} renamed so as not to replace a program of the same name "
                "on the robot or in another task: listed in the report.")  # fmt: skip
        attention.append((INFO, text))
    # 4. Where the manual work is. Moves made inside the backup's own routines first: one line in the
    # mapping file converts them all, and on some backups they are most of the TODO.
    waiting: dict[str, int] = {}
    for task in run.tasks:
        for use in task.result.move_routines if task.result else []:
            if not use.converted:
                waiting[use.name] = waiting.get(use.name, 0) + use.calls
    if waiting:
        calls = sum(waiting.values())
        names = ", ".join(sorted(waiting, key=lambda name: -waiting[name])[:4]) + (", ..." if len(waiting) > 4 else "")
        text = (f"{plural(calls, 'move')} {'is' if calls == 1 else 'are'} made inside routines that also do something"
                f" else ({names}), so they are not converted yet: choose below which ones to convert as moves.")  # fmt: skip
        attention.append((INFO, text))
    blockers: Counter[str] = Counter()
    for task in run.tasks:
        for category, count, _ in task.result.grouped("TODO") if task.result else []:
            blockers[category] += count
    blockers.pop(Blocker.rapid("SYNTAX_ERROR"), None)  # already said in 2.
    if waiting:
        blockers.pop(Blocker.MOVE_ROUTINE, None)  # just said
    if blockers:
        category, count = blockers.most_common(1)[0]
        attention.append((INFO, f"Most items to review come from: {category} ({count * 100 // run.todo} %)."))
    elif run.programs and not errors:
        attention.append((GOOD, "Nothing to review: every routine was converted."))
    # 5. The numbering.
    if run.controller is not None:
        attention.append((GOOD, f"Numbers already used on the FANUC robot were left free ({run.controller.summary()})."))
    elif run.programs:
        attention.append((INFO, "No FANUC backup was given: numbering starts at 1 and may clash with the robot's own."))
    # 6. The binary .TP copies, when asked for.
    exports = [t.tp for t in run.tasks if t.tp is not None]
    problem = next((e.problem for e in exports if e.problem), "")
    refused = sum(len(e.refused) for e in exports)
    made = sum(len(e.made) for e in exports)
    if problem:
        attention.append((WARN, f"No .TP written: {problem}. The .LS programs are written as usual."))
    elif refused:
        attention.append((WARN, f"MakeTP refused {plural(refused, 'program')}: see the report; load their .LS instead."))
    if made:
        text = f"{plural(made, 'program')} also written as .TP in the {TP_FOLDER} folder, ready to copy to a USB stick."
        attention.append((GOOD, text))
    return summary


__all__ = [
    "GOOD", "INFO", "RESOURCE_NAMES", "WARN", "Summary", "describe_controller", "describe_source", "plural", "summarize",
]  # fmt: skip
