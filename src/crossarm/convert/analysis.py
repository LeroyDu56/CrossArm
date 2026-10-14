# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The decision first: is the conversion workable, and what to do first.

A large backup gives a report of hundreds of TODO, points and checklist items. Before any of that, the
reader wants to know whether the programs can be taken to production and where the work is. This module
works that out from a ConversionResult; the reports show it first (crossarm.convert.html_report, report).

The decision is not a judgement: it applies the fixed rule below, and the reports print the rule and the
figures it was applied to under the sentence.

    ready       nothing left TODO (and nothing over the controller's capacity)
    workable    at least MIN_CONVERTED % of the RAPID instructions converted, and at most MAX_BLOCKING
                blocking causes
    not ready   otherwise

A TODO cause is blocking when the robot's path or the cell's logic depends on something CrossArm cannot
know from the backup (what the robot measures or computes while it runs, what an interrupt does): it needs
a solution designed on the FANUC side before the cell runs. Every other cause is work to plan: it has a
known fix that the report gives (provide a module, map a signal, choose in the window, write the line by
hand, redo an error handler or a dialog the FANUC way).
"""

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from crossarm.convert import triage
from crossarm.convert.blockers import Blocker
from crossarm.convert.condition_gates import MARK
from crossarm.convert.config import ConversionConfig
from crossarm.convert.coverage import fmt_percent
from crossarm.convert.taught import AGAIN, KEPT
from crossarm.convert.translate import Capacity, ConversionResult, Note, VerdictFigures
from crossarm.convert.unsupported import KAREL_SOCKETS, NO_TP_FAMILIES

# ---------------------------------------------------------------------------
# The rule: its thresholds and the blocking causes, in this one place.
# ---------------------------------------------------------------------------

MIN_CONVERTED = 85.0  # % of the RAPID instructions converted, at least, for a workable conversion
MAX_BLOCKING = 3  # blocking causes, at most, for a workable conversion
NEAR_LIMIT = 0.8  # a controller resource is shown once this share of its limit is used

BLOCKING = frozenset({
    Blocker.CALIBRATION,  # a frame or position the robot measures while it runs (searches included)
    Blocker.RUNTIME_FRAME,  # a frame or tool computed while it runs
    Blocker.RUNTIME_POSITION,  # a position computed while it runs
    Blocker.INTERRUPT,  # an interrupt and its TRAP
    Blocker.MONITOR,
    Blocker.SEARCH,
    Blocker.STATIONARY,  # stationary tool, robot-held work object
    Blocker.MOTION,  # a move TP has no form for
    Blocker.PROVIDED_FUNCTION,  # a FUNC provided as a program, inside an expression: TP gives no value back
    Blocker.INTERNAL,  # a CrossArm bug: nobody knows the fix until it is reported
})  # fmt: skip

READY, WORKABLE, NOT_READY, EMPTY = "ready", "workable", "not ready", "empty"


@dataclass(frozen=True, slots=True)
class Verdict:
    level: str  # READY, WORKABLE, NOT_READY, EMPTY
    sentence: str  # the decision, one sentence
    rule: str  # the rule applied, and the figures it was applied to
    blocking: tuple[tuple[str, int], ...]  # blocking causes and their TODO, most first

    @property
    def headline(self) -> str:
        """The decision without its detail, for the window (the report names the causes)."""
        if self.level == WORKABLE and self.blocking:
            return (f"Workable with touch-up and planned work, plus {_plural(len(self.blocking), 'blocking cause')}"
                    " to solve on the FANUC side.")  # fmt: skip
        return {READY: "Ready for commissioning.", WORKABLE: "Workable with touch-up and planned work.",
                NOT_READY: "Not ready for production without major work.", EMPTY: "Nothing converted."}[self.level]  # fmt: skip

    @property
    def brief(self) -> str:
        """The rule in a few words, for the window: 'Rule: workable from 85 % converted and at most 3 blocking
        causes (here 2).'"""
        return (f"Rule: workable from {MIN_CONVERTED:g} % converted and at most {MAX_BLOCKING} blocking causes"
                f" (here {len(self.blocking)}).")  # fmt: skip


def _names(items: list[str], limit: int = 3) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" and {len(items) - limit} more" if len(items) > limit else "")


def _plural(count: int, word: str, words: str | None = None) -> str:
    return f"{count} {word if count == 1 else (words or word + 's')}"


def rule_text() -> str:
    return (f"ready when every instruction is converted; workable when at least {MIN_CONVERTED:g} % of the RAPID"
            f" instructions are converted and at most {MAX_BLOCKING} causes are blocking; not ready otherwise")  # fmt: skip


def explanation() -> str:
    """How the decision is made, in words, for the reports."""
    return (f"Fixed thresholds: at least {MIN_CONVERTED:g} % of the RAPID instructions converted and at most"
            f" {MAX_BLOCKING} blocking causes for a workable conversion. A cause is blocking when the robot's path or"
            " the cell's logic depends on something CrossArm cannot know from the backup (what the robot measures or"
            " computes while it runs, what an interrupt does): it needs a solution designed on the FANUC side. Every"
            " other cause is work to plan, with a known fix: provide a module, map a signal, choose in the window,"
            " write the line by hand, redo an error handler or a dialog the FANUC way. Blocking causes:")  # fmt: skip


def decide(*, programs: int, percent: float, todo: int, blocking: list[tuple[str, int]], over: list[str],
           causes: list[tuple[str, int]] | None = None) -> Verdict:  # fmt: skip
    """The decision, from the figures alone: `blocking` the blocking causes with their TODO, most first; `over`
    the controller resources over their limit; `causes` every TODO cause, most first (to name the work)."""
    blocking = list(blocking)
    figures = f"{fmt_percent(percent)} converted, {_plural(len(blocking), 'blocking cause')}"
    rule = f"Rule: {rule_text()}. Here: {figures}."
    if not programs:
        return Verdict(EMPTY, "Nothing converted: no routine of the input was written as a TP program.",
                       f"Rule: {rule_text()}. Here: no program written.", ())  # fmt: skip
    named = [name for name, _ in blocking]
    if not todo and not over and percent >= 100:
        return Verdict(READY, "Ready for commissioning: load the programs, set the frames and touch up the points.",
                       rule, ())  # fmt: skip
    if percent >= MIN_CONVERTED and len(blocking) <= MAX_BLOCKING:
        if blocking:
            sentence = (f"Workable with touch-up and planned work, plus {_plural(len(blocking), 'blocking cause')}"
                        f" to solve on the FANUC side: {_names(named)}.")  # fmt: skip
        elif todo:
            sentence = (f"Workable with touch-up and planned work: {_plural(todo, 'TODO', 'TODO')} with a known fix, no"
                        " blocking cause.")  # fmt: skip
        elif over:
            sentence = "Workable with touch-up once the controller's capacity is sorted out: no TODO left."
        else:
            sentence = ("Workable with touch-up: no TODO left, but some routines were not converted (listed under"
                        " Programs).")  # fmt: skip
        return Verdict(WORKABLE, sentence, rule, tuple(blocking))
    work = []
    if percent < MIN_CONVERTED:
        mostly = [name for name, _ in causes or ()][:2]
        work.append(f"the {fmt_percent(round(100 - percent, 1))} of the instructions not converted"
                    + (f" (mostly {' and '.join(mostly)})" if mostly else " (routines not converted, listed under"
                       " Programs)"))  # fmt: skip
    if len(blocking) > MAX_BLOCKING:
        work.append(f"{_plural(len(blocking), 'blocking cause')} ({_names(named)})")
    return Verdict(NOT_READY, f"Not ready for production without major work on {' and '.join(work)}.", rule,
                   tuple(blocking))  # fmt: skip


def todo_causes(notes: list[Note]) -> list[tuple[str, int]]:
    """TODO causes and their count, most first (ties by name, for a stable order)."""
    counts = Counter(note.category for note in notes if note.kind == "TODO")
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def blocking_causes(notes: list[Note]) -> list[tuple[str, int]]:
    return [(cause, count) for cause, count in todo_causes(notes) if cause in BLOCKING]


def verdict(result: ConversionResult) -> Verdict:
    return decide(programs=len(result.programs), percent=result.coverage.percent, todo=result.todo_count,
                  blocking=blocking_causes(result.notes), over=[c.resource for c in result.capacity if not c.fits],
                  causes=todo_causes(result.notes))  # fmt: skip


def figures_verdict(figures: VerdictFigures) -> Verdict:
    """The verdict of a conversion known by its figures alone (ConversionResult.with_karel)."""
    causes = list(figures.causes)
    return decide(programs=figures.programs, percent=figures.percent, todo=figures.todo,
                  blocking=[(c, k) for c, k in causes if c in BLOCKING], over=list(figures.over), causes=causes)  # fmt: skip


# ---------------------------------------------------------------------------
# The path to a workable verdict: what would change it (the rule above is not changed by it)
# ---------------------------------------------------------------------------

KAREL_OPTION = "R632"  # the controller option KAREL programs need


@dataclass(frozen=True, slots=True)
class WorkablePath:
    """What stands between a 'not ready' conversion and a workable one, by the rule above."""

    level: str  # the verdict now
    blocking: tuple[tuple[str, int], ...]  # the blocking causes and their TODO, most first
    to_solve: tuple[tuple[str, int], ...]  # the fewest blocking causes to solve for at most MAX_BLOCKING, easiest first
    instructions: int  # RAPID instructions to convert besides, for MIN_CONVERTED % (0: the share converted is enough)
    total: int  # RAPID instructions in all
    karel: Verdict | None  # the verdict the same conversion gets with --karel (None: not computed, or no change)

    @property
    def needed(self) -> bool:
        """Whether there is a path to show: the verdict is not ready."""
        return self.level == NOT_READY

    def text(self) -> str:
        """'Path to workable: solve 1 of the 4 blocking causes, the fewest TODO first: interrupt (3 TODO).' The
        causes to solve, the instructions to convert besides, and what --karel would give; '' when workable."""
        if not self.needed:
            return ""
        parts = []
        if self.to_solve:
            count = len(self.to_solve)
            which = "the one with the fewest TODO" if count == 1 else "the fewest TODO first"
            parts.append(f"solve {count} of the {len(self.blocking)} blocking causes ({MAX_BLOCKING} are allowed),"
                         f" {which}: {'; '.join(f'{c}: {_todo(k)}' for c, k in self.to_solve)}.")  # fmt: skip
        if self.instructions:
            parts.append(("Then convert" if parts else "convert") + f" {self.instructions:,} more of the"
                         f" {self.total:,} RAPID instructions ({MIN_CONVERTED:g} % at least"
                         + ("; solving these causes counts towards it)." if self.to_solve else ")."))  # fmt: skip
        sentence = "Path to workable: " + " ".join(parts)
        if self.karel is not None:
            sentence += " " + karel_sentence(self.karel)
        return sentence

    def data(self) -> dict[str, object]:
        """For crossarm diagnose: the blocking causes, the causes to solve, by cause name (a fixed list)."""
        return {"blocking_causes": dict(self.blocking), "causes_to_workable": dict(self.to_solve),
                "instructions_to_workable": self.instructions,
                "verdict_with_karel": None if self.karel is None else self.karel.level}  # fmt: skip


def karel_sentence(decision: Verdict) -> str:
    """'With --karel and the KAREL option R632, the conversion is workable.'"""
    level = {READY: "ready", WORKABLE: "workable"}.get(decision.level)
    head = f"With --karel and the KAREL option {KAREL_OPTION}"
    if level is not None:
        return f"{head}, the conversion is {level} ({decision.rule.split('Here: ', 1)[-1].rstrip('.')})."
    return f"{head}, it stays not ready ({decision.rule.split('Here: ', 1)[-1].rstrip('.')})."


def workable_path(figures: VerdictFigures, with_karel: VerdictFigures | None = None) -> WorkablePath:
    """The blocking causes to solve (the fewest for at most MAX_BLOCKING; among them those with the fewest TODO,
    then by family, then by name), the instructions to convert besides for MIN_CONVERTED %, and the verdict
    `with_karel` (the figures of the same conversion with --karel) gives, when it differs."""
    decision = figures_verdict(figures)
    blocking = tuple(decision.blocking)
    excess = max(0, len(blocking) - MAX_BLOCKING)
    easiest = sorted(blocking, key=lambda ck: (ck[1], triage.family(ck[0]), ck[0]))
    needed = -(-int(MIN_CONVERTED * 10) * figures.total // 1000)  # the fewest converted for MIN_CONVERTED %
    instructions = max(0, needed - figures.converted) if figures.total else 0
    karel = None
    if with_karel is not None:
        other = figures_verdict(with_karel)
        karel = other if other.level != decision.level else None
    if decision.level != NOT_READY:
        excess, instructions = 0, 0
    return WorkablePath(decision.level, blocking, tuple(easiest[:excess]), instructions, figures.total, karel)


def path_to_workable(result: ConversionResult) -> WorkablePath:
    """workable_path of a conversion; --karel's verdict when it was worked out (converted without it)."""
    return workable_path(VerdictFigures.of(result), result.with_karel)


# ---------------------------------------------------------------------------
# Where the TODO come from
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Cause:
    category: str
    count: int
    share: float  # % of the TODO
    example: Note  # the first note of its most common case
    blocking: bool


def top_causes(result: ConversionResult, limit: int = 5) -> list[Cause]:
    todo = [note for note in result.notes if note.kind == "TODO"]
    by_cause: dict[str, list[Note]] = defaultdict(list)
    for note in sorted(todo, key=lambda x: (x.program, x.rapid_line or 0)):
        by_cause[note.category].append(note)
    out = []
    for category, count in todo_causes(result.notes)[:limit]:
        notes = by_cause[category]
        common = Counter(note.message.split(" — `")[0] for note in notes).most_common(1)[0][0]
        example = next(note for note in notes if note.message.split(" — `")[0] == common)
        out.append(Cause(category, count, count * 100 / len(todo), example, category in BLOCKING))
    return out


def near_limit(capacity: list[Capacity]) -> list[Capacity]:
    """The controller resources over their limit, or close to it: the only ones worth a look first."""
    return [c for c in capacity
            if not c.fits or (c.limit and c.used + c.taken >= NEAR_LIMIT * c.limit)]  # fmt: skip


def capacity_status(c: Capacity) -> str:
    if not c.fits:
        return f"over by {len(c.over)}: {_names(list(c.over), 4)}"
    if c.limit is not None and c.used > c.limit:
        return "above the limit: those past it are kept in position registers and loaded before use"
    return f"{c.used + c.taken} of {c.limit} used" + (f" ({c.taken} already taken on the robot)" if c.taken else "")


# ---------------------------------------------------------------------------
# What to do first
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Action:
    title: str  # what to do, short (Markdown inline: `code` and **bold**)
    detail: str  # how, and where it applies (Markdown inline)
    href: str  # where it is detailed, in the HTML report
    label: str  # that place, in words (the Markdown report has no links)
    cause: str = ""  # the cause the list of items to review is filtered on, when href is #review
    causes: tuple[str, ...] = ()  # every TODO cause it covers: its TODO are exactly those of these causes
    todo: int = 0  # the TODO it concerns, exactly (0: it is not about TODO lines)
    programs: tuple[str, ...] = ()  # the programs those TODO are in
    who: tuple[str, ...] = ()  # who acts (triage.WHO)
    option: str = ""  # the robot option, when who names one ("R632")
    snippet: str = ""  # entries to paste in crossarm_mapping.json (external_routines)

    @property
    def impact(self) -> str:
        """triage.COSMETIC when every cause it covers changes only what the operator reads, else PRODUCTION."""
        return triage.impact(self.causes)

    @property
    def who_text(self) -> str:
        return " · ".join(f"{who} {self.option}" if who == triage.OPTION and self.option else who for who in self.who)

    @property
    def meta(self) -> str:
        """'7 TODO concerned · who acts: ABB backup (add a module) · FANUC integrator' (· cosmetic)."""
        parts = [f"{self.todo} TODO concerned"] if self.todo else []
        if self.who:
            parts.append(f"who acts: {self.who_text}")
        if self.causes and self.impact == triage.COSMETIC:
            parts.append("cosmetic: the cell runs without it")
        return " · ".join(parts)


def _concerning(notes: list[Note]) -> dict:
    """The fields of an Action about these TODO: their causes (most first), count and programs."""
    causes = Counter(note.category for note in notes)
    return {"causes": tuple(c for c, _ in sorted(causes.items(), key=lambda kv: (-kv[1], kv[0]))),
            "todo": len(notes), "programs": tuple(sorted({note.program for note in notes if note.program}))}  # fmt: skip


def _who(causes: Iterable[str], *who: str) -> tuple[str, ...]:
    """who, and 'a later CrossArm version may help' when one of the causes is one it may convert."""
    return (*who, triage.LATER) if any(cause in triage.LATER_CAUSES for cause in causes) else who


MAX_ACTIONS = 7
MIN_ACTIONS = 3

_ERRORS = frozenset({Blocker.HANDLER, *(Blocker.rapid(kind) for kind in (
    "ERROR_HANDLER", "UNDO_HANDLER", "BACKWARD_HANDLER", "RAISE", "RETRY", "TRYNEXT"))})  # fmt: skip
# Blocking causes taken together in one action: (causes, what to do, how).
_DESIGN = (
    ((Blocker.CALIBRATION, Blocker.RUNTIME_FRAME), "Decide how the FANUC cell gets what the robot measures",
     "frames and positions measured or computed while it runs (calibration, searches)"),
    ((Blocker.RUNTIME_POSITION,), "Rebuild the positions computed at run time",
     "in position registers by hand, or as taught points"),
    ((Blocker.INTERRUPT, Blocker.MONITOR), "Redo the interrupts left TODO", "TRAP routines, the FANUC way"),
)  # fmt: skip
_MISSING_NAME = re.compile(r"^(?:routine|data|function|procedure)?\s*'([^']+)' is not in the backup")


def _programs(notes: list[Note]) -> str:
    return _in(note.program for note in notes)


def _in(programs: Iterable[str]) -> str:
    """' in `A`, `B`, `C`, `D` and 3 more': the programs touched, a few named."""
    names = sorted({name for name in programs if name})
    return f" in {_names([f'`{name}`' for name in names], 4)}" if names else ""


def _missing_names(notes: list[Note]) -> list[str]:
    names: Counter[str] = Counter()
    for note in notes:
        found = _MISSING_NAME.search(note.message)
        if found:
            names[found.group(1)] += 1
    return [name for name, _ in names.most_common()]


def _no_tp_kinds(notes: list[Note]) -> list[str]:
    kinds: Counter[str] = Counter()
    for note in notes:
        for why in NO_TP_FAMILIES:
            if why.split(":")[0] in note.message:
                kinds[why.split(":")[0]] += 1
                break
    return [kind for kind, _ in kinds.most_common()]


def karel_use(result: ConversionResult) -> str:
    """What --karel did on this run, so that nobody takes it for having converted everything: each KAREL program
    called, from which programs, how often. "" without --karel."""
    if result.karel_calls is None:
        return ""
    if not result.karel_calls:
        return "`--karel`: no KAREL program used on this run; every program is TP only."
    parts = []
    for name, callers in result.karel_calls.items():
        total = sum(callers.values())
        shown = [f"`{program}` ({count})" for program, count in callers.items()]
        parts.append(f"`{name}` {_plural(total, 'call')} in {_names(shown, 4)}")
    calling = len({program for callers in result.karel_calls.values() for program in callers})
    return (f"`--karel` on this run: {'; '.join(parts)}. {calling} of {_plural(len(result.programs), 'program')} call"
            f"{'s' if calling == 1 else ''} KAREL; everything else is TP, and what stays TODO is not converted by"
            " KAREL either.")  # fmt: skip


def func_programs_use(result: ConversionResult) -> str:
    """The FUNCs of the backup written as TP programs (crossarm.convert.func_programs), each with its calls; ""
    for none."""
    if not result.func_calls:
        return ""
    shown = [f"`{name}()` as `{result.program_keys.get(name, name)}` ({_plural(len(sites), 'call')})"
             for name, sites in sorted(result.func_calls.items(), key=lambda kv: (-len(kv[1]), kv[0]))]  # fmt: skip
    return (f"{_plural(len(result.func_calls), 'FUNC')} of the backup written as TP programs: {_names(shown, 4)};"
            " a line reading one first runs `CALL F(args,k)`, the result left in R[k] (PR[k] for a robtarget).")


_FUNC_TODO = re.compile(r"(\w+)\(\) is written as a program only when its whole body converts")


def _todo(count: int) -> str:
    return f"{count} TODO"


def touch_up_counts(result: ConversionResult) -> tuple[int, int, int]:
    """(points written, kept as touched up on the robot, to touch up again): the points to touch up on the robot are
    the first less the second, the third among them."""
    taught = result.taught
    points = sum(len(info.points) for info in result.programs)
    kept = len(taught.of(KEPT)) if taught is not None else 0
    again = len(taught.of(AGAIN)) if taught is not None else 0
    return points, kept, again


def priority_actions(result: ConversionResult, config: ConversionConfig | None = None) -> list[Action]:
    """MIN_ACTIONS to MAX_ACTIONS things to do, the ones that unblock the most first: what keeps the programs from
    loading, what the backup lacks, the blocking causes, what to redo the FANUC way, the rest by hand; touching up
    the points last, as on site. Each says the TODO it concerns, exactly, and who acts (crossarm.convert.triage);
    `config` names the example programs of external_routines as the controller takes them."""
    by_cause: dict[str, list[Note]] = defaultdict(list)
    for note in result.notes:
        if note.kind == "TODO":
            by_cause[note.category].append(note)
    done: set[str] = set()  # causes an action covers
    actions: list[Action] = []
    integrator, backup = triage.INTEGRATOR, triage.BACKUP
    snippet, candidates = triage.external_example(result, config)

    over = [c for c in result.capacity if not c.fits]
    if over:
        shown = "; ".join(f"{c.resource} {c.highest} needed, {'—' if c.limit is None else c.limit} held" for c in over)
        actions.append(Action(
            "Bring the numbers within the controller", f"{shown}: the programs do not load otherwise. Pin them in"
            " `crossarm_mapping.json`, reuse frames, or raise `limits` if the controller has more.",
            "#an-capacity", "Controller capacity", who=(integrator,)))  # fmt: skip
    internal = by_cause.get(Blocker.INTERNAL, [])
    done.add(Blocker.INTERNAL)
    if internal:
        actions.append(Action(
            "Send the report and `crossarm_log.txt`", f"{_plural(len(internal), 'statement')} hit an internal error"
            " in CrossArm: a CrossArm bug, left TODO.", "#review", "Items to review", Blocker.INTERNAL,
            **_concerning(internal), who=(triage.LATER,)))  # fmt: skip
    missing = by_cause.get(Blocker.MISSING, [])
    done.add(Blocker.MISSING)
    if missing:
        names = _missing_names(missing)
        actions.append(Action(
            f"Provide the {_plural(len(names), 'routine or data', 'routines and data')} the backup does not have"
            if names else "Provide the routines and data the backup does not have",
            (f"{_names([f'`{n}`' for n in names], 4)}; {_todo(len(missing))}. " if names else f"{_todo(len(missing))}. ")
            + "Add the modules that declare them and convert again"
            + (f", or name a TP or KAREL program for a routine in `external_routines`: {_plural(candidates, 'candidate')}"
               " listed in `crossarm_mapping.json`" if candidates else "") + ".",
            "#review", "Items to review", Blocker.MISSING, **_concerning(missing), who=(backup, integrator),
            snippet=snippet))  # fmt: skip
        snippet = ""
    loaded = by_cause.get(Blocker.LOADED_MODULE, [])
    done.add(Blocker.LOADED_MODULE)
    if loaded:  # crossarm.convert.module_loads: files the RAPID loads from the disk, not in the input
        paths = list(dict.fromkeys(m.path for m in result.loaded_missing if m.path))
        late = len({(m.program, m.line) for m in result.loaded_missing if not m.path})
        shown = _names([f"`{path}`" for path in paths], 6)
        actions.append(Action(
            f"Add the {_plural(len(paths), 'module file')} the programs load to the input" if paths else
            "Add the modules the programs load at run time to the input",
            (f"{shown} (Load, StartLoad): the backup does not hold {'them' if len(paths) > 1 else 'it'}. " if paths
             else "") + (f"{_plural(late, 'load names its file', 'loads name their file')} at run time: add every"
                         " module it may load. " if late else "")
            + "Copy the files next to the other modules of the backup (or into the .zip) and convert again: their"
            f" programs are then converted with the others; {_todo(len(loaded))}{_programs(loaded)}.",
            "#review", "Items to review", Blocker.LOADED_MODULE, **_concerning(loaded), who=(backup,)))  # fmt: skip
    safety = by_cause.get(Blocker.SAFETY, [])
    done.add(Blocker.SAFETY)
    if safety or result.world_zones or result.safety_options:  # crossarm.convert.world_zones
        zones = [f"`{zone.name}`" for zone in result.world_zones]
        parts = []
        if zones:
            parts.append(f"{_plural(len(zones), 'world zone')} the RAPID sets up ({_names(zones, 4)})")
        if result.safety_options:
            parts.append("the ABB system lists " + _names([f"`{o}`" for o in result.safety_options], 3))
        actions.append(Action(
            "Set up the robot's safety and zones in DCS, then validate them",
            "; ".join(parts) + ". CrossArm converts no safety function: set them up again on the FANUC (DCS"
            " Cartesian or Joint Position Check, safe I/O, or its interference check zones) and validate them on the"
            " robot before production" + (f"; {_todo(len(safety))}{_programs(safety)}" if safety else "") + ".",
            "#ck-safety", "Checklist: Safety and world zones",
            **(_concerning(safety) if safety else {}), who=(integrator,)))  # fmt: skip
    if result.provided:
        names = [f"`{use.program}`" for use in result.provided]
        actions.append(Action(
            f"Write and load the {_plural(len(names), 'program')} to provide",
            f"{_names(names, 4)}: CrossArm calls them and does not write them (`external_routines`)."
            + (" A function writes its result in the register its last argument names (R[AR[n]] for a num,"
               " PR[AR[n]] for a pose or a point), which the caller reads back."
               if any(use.function and use.returns for use in result.provided) else ""),
            "#ck-provided", "Checklist: Programs to provide", who=(integrator,)))  # fmt: skip
    if result.karel_programs:
        names = [f"`{name}`" for name in result.karel_programs]
        actions.append(Action(
            f"Load the {_plural(len(names), 'KAREL program')} before the programs that call {'them' if len(names) > 1 else 'it'}",
            f"{_names(names, 4)}, of CrossArm's KAREL library (`--karel`): load each .pc of the KAREL folder before"
            " the .LS (compile the .kl with ktrans first where there is no .pc); a real robot needs the KAREL option"
            " (R632).", "#ck-karel", "Checklist: KAREL programs", who=(integrator, triage.OPTION),
            option="R632"))  # fmt: skip

    if result.remote_tcp:  # crossarm.convert.remote_tcp: an option the programs need to load
        pairs = [f"`{tool}` UFRAME[{uf}] + `{wobj}` UTOOL[{ut}]" for tool, wobj, uf, ut in result.remote_tcp]
        actions.append(Action(
            "Check that the robot has the Remote TCP option (J624)",
            f"{_names(pairs, 3)}: the moves with a stationary tool and a work object the robot holds are written with"
            " RTCP (the user frame selected is the stationary tool, the tool frame the work object, each point the"
            " part seen from the tool); a controller without the option does not take them.",
            "#ck-frames", "Checklist: Frames and tools", who=(integrator, triage.OPTION), option="J624"))  # fmt: skip
    if result.gated:  # crossarm.convert.condition_gates
        marked = [note for note in result.notes if note.kind == "TODO" and MARK in note.message]
        slots = [f"`{g.slot}`" for g in result.gated]
        actions.append(Action(
            f"Set the {_plural(len(result.gated), 'condition')} CrossArm could not convert",
            f"{_names(slots, 4)}: each IF, WHILE, TEST or FOR is written with its blocks, and skipped until the line"
            " before it sets its flag (a register for a TEST's value or a FOR's bound) in place of the `JMP` the remark"
            " names; "
            f"{_todo(len(marked))}{_programs(marked)}.", "#ck-conditions", "Checklist: Conditions to set",
            todo=len(marked), programs=tuple(sorted({note.program for note in marked if note.program})),
            who=(integrator,)))  # fmt: skip

    design = []
    for causes, title, how in _DESIGN:
        notes = [note for cause in causes for note in by_cause.get(cause, [])]
        done.update(causes)
        if notes:
            first = max(causes, key=lambda c: len(by_cause.get(c, [])))
            design.append((len(notes), Action(
                title, f"{how}: {_todo(len(notes))}{_programs(notes)}. Blocking: CrossArm cannot know them from the"
                " backup.", "#review", "Items to review", first, **_concerning(notes),
                who=_who(causes, integrator))))  # fmt: skip
    rest = [(cause, by_cause[cause]) for cause in sorted(BLOCKING) if cause not in done and by_cause.get(cause)]
    done.update(BLOCKING)
    if rest:
        rest.sort(key=lambda kv: -len(kv[1]))
        notes = [note for _, group in rest for note in group]
        design.append((len(notes), Action(
            "Solve the blocking causes on the FANUC side",
            "; ".join(f"{cause}: {_todo(len(notes))}{_programs(notes)}" for cause, notes in rest[:3])
            + (f"; and {len(rest) - 3} more" if len(rest) > 3 else "") + ".",
            "#review", "Items to review", rest[0][0], **_concerning(notes),
            who=_who((c for c, _ in rest), integrator))))  # fmt: skip
    actions += [action for _, action in sorted(design, key=lambda x: -x[0])]
    if result.karel_todo:  # converted without --karel: what it would convert
        sockets = any(note.kind == "TODO" and "sockets:" in note.message for note in result.notes)
        actions.append(Action(
            "Convert again with `--karel` for the poses computed at run time, the text files and StopMove",
            f"{_todo(result.karel_todo)} converted then by CrossArm's KAREL programs (PoseMult, PoseInv, RelTool,"
            " DefFrame of poses kept in position registers, frames loaded from them; text files written with Open,"
            " Write, Close on UD1:; StopMove / StartMove pausing the robot, in the program and in a TRAP). Load the"
            " KAREL programs (.pc) before the .LS; a real robot needs the KAREL"
            " option (R632)." + (" Sockets stay TODO with it." if sockets else ""), "#review", "Items to review",
            todo=result.karel_todo, who=(integrator, triage.OPTION), option="R632"))  # fmt: skip

    inlined = [note for note in result.notes if note.category == Blocker.INLINED]
    if inlined:
        found = [re.match(r"FUNC (\w+)\(\) of the backup is inlined at (\d+)", note.message) for note in inlined]
        shown = [f"`{match[1]}()` ({match[2]})" for match in found if match]
        actions.append(Action(
            f"Convert again after a change of the {_plural(len(inlined), 'FUNC')} copied into their calls",
            f"{_names(shown, 4)} call sites: CrossArm writes the body of each into every call, so a change of one in"
            " the RAPID changes nothing on the robot until the backup is converted again, with the same mapping file.",
            "#review", "Items to review", Blocker.INLINED, who=(integrator,)))  # fmt: skip
    unwritten: dict[str, list[Note]] = defaultdict(list)
    for note in result.notes:
        if note.kind == "TODO" and (match := _FUNC_TODO.search(note.message)):
            unwritten[match[1]].append(note)
    if unwritten:
        notes = [note for group in unwritten.values() for note in group]
        shown = [f"`{name}()` ({_todo(len(group))})" for name, group in sorted(unwritten.items(),
                                                                          key=lambda kv: (-len(kv[1]), kv[0]))]  # fmt: skip
        actions.append(Action(
            f"Finish the {_plural(len(unwritten), 'FUNC')} not written as TP programs",
            f"{_names(shown, 4)}: CrossArm writes a FUNC of the backup as a TP program only when its whole body"
            " converts, and each TODO names the first line of its body that does not, and why. Rewrite that part,"
            " or provide the FUNC as a program of your own (`external_routines` with `returns`), then convert again.",
            "#review", "Items to review", todo=len(notes),
            programs=tuple(sorted({note.program for note in notes if note.program})),
            who=_who((note.category for note in notes), integrator)))  # fmt: skip
    banked = [f for f in (*result.utools, *result.uframes) if f.bank is not None]
    if banked:
        slots = sorted({f"{'UTOOL' if f in result.utools else 'UFRAME'}[{f.slot}]" for f in banked})
        actions.append(Action(
            f"Keep the position registers of the {_plural(len(banked), 'frame')} past the controller's limit",
            f"{_names([f'`{f.rapid_name}` PR[{f.bank}]' for f in banked], 4)}: kept there by SETUP_FRAMES and loaded"
            f" into {_names(slots, 2)} before each use; leave them alone, and give the mapping file back to keep them"
            " (CrossArm 1.0 to 1.7 selected such frames by number when given it back: convert again).",
            "#ck-frames", "Checklist: Frames and tools", who=(integrator,)))  # fmt: skip

    errors = [note for cause in sorted(_ERRORS) for note in by_cause.get(cause, [])]
    done.update(_ERRORS)
    if errors:
        first = max(sorted(_ERRORS), key=lambda c: len(by_cause.get(c, [])))
        actions.append(Action(
            "Redo the error handling on the FANUC side",
            f"{_todo(len(errors))} on RAPID ERROR handlers, RAISE, RETRY...{_programs(errors)}. TP has no error"
            " handler: not a CrossArm bug, decide what the FANUC cell does on each error.",
            "#review", "Items to review", first, **_concerning(errors), who=(integrator,)))  # fmt: skip
    no_tp = by_cause.get(Blocker.NO_TP_EQUIVALENT, [])
    done.add(Blocker.NO_TP_EQUIVALENT)
    if no_tp:
        kinds = _no_tp_kinds(no_tp)
        actions.append(Action(
            "Redo what TP has nothing for on the FANUC side",
            f"{_plural(len(no_tp), 'RAPID instruction')}" + (f" ({_names(kinds, 3)})" if kinds else "")
            + ": not a CrossArm bug. A TP or KAREL program can stand in for a routine (`external_routines`)."
            + (" Sockets stay TODO with `--karel`: KAREL socket messaging needs client tags configured on the robot."
               if any(KAREL_SOCKETS in note.message for note in no_tp) else ""),
            "#review", "Items to review", Blocker.NO_TP_EQUIVALENT, **_concerning(no_tp), who=(integrator,),
            snippet=snippet))  # fmt: skip
    waiting = [use for use in result.move_routines if not use.converted]
    done.add(Blocker.MOVE_ROUTINE)
    if waiting:
        calls = sum(use.calls for use in waiting)
        actions.append(Action(
            "Choose which routines that move are converted as their move",
            f"{_plural(calls, 'call')} to {_names([f'`{use.name}`' for use in waiting], 3)}: in the window after the"
            " conversion, or `move_routines` in `crossarm_mapping.json`.",
            "#review", "Items to review", Blocker.MOVE_ROUTINE, **_concerning(by_cause.get(Blocker.MOVE_ROUTINE, [])),
            who=(integrator,)))  # fmt: skip
    signals = by_cause.get(Blocker.SIGNAL, [])
    done.add(Blocker.SIGNAL)
    if signals:
        actions.append(Action(
            "Map the I/O signals left TODO", f"{_todo(len(signals))}: give their numbers and types in"
            " `crossarm_mapping.json`, or the backup's EIO.cfg.", "#review", "Items to review", Blocker.SIGNAL,
            **_concerning(signals), who=(integrator,)))  # fmt: skip
    others = [(cause, notes) for cause, notes in by_cause.items() if cause not in done]
    cosmetic = [note for cause, notes in others if cause in triage.COSMETIC_CAUSES for note in notes]
    others = sorted(((cause, len(notes)) for cause, notes in others if cause not in triage.COSMETIC_CAUSES),
                    key=lambda kv: (-kv[1], kv[0]))  # fmt: skip
    if others:
        notes = [note for cause, _ in others for note in by_cause[cause]]
        actions.append(Action(
            f"Finish the other {_todo(sum(n for _, n in others))} by hand",
            f"{_names([c for c, _ in others], 3)}, program by program.",
            "#ck-todo", "Checklist: TODO lines to finish by hand", **_concerning(notes),
            who=_who((c for c, _ in others), integrator)))  # fmt: skip
    if cosmetic:
        actions.append(Action(
            f"Finish the {_plural(len(cosmetic), 'operator message')} left TODO when convenient",
            f"{_names(sorted({note.category for note in cosmetic}), 2)}: the cell moves and works the same; only"
            " what the pendant shows differs.", "#ck-todo", "Checklist: TODO lines to finish by hand",
            **_concerning(cosmetic), who=(integrator,)))  # fmt: skip

    last = []  # every conversion ends on the robot
    taught = result.taught
    again = taught.of(AGAIN) if taught is not None else []
    if again:
        per_program = Counter(p.program for p in again)
        programs = [f"`{name}` ({n})" for name, n in per_program.most_common()]
        far = max((p.deviation_mm() or 0.0 for p in again), default=0.0)
        last.append(Action(
            f"Touch up again the {_plural(len(again), 'point')} that changed",
            f"their ABB position or frame changed since the conversion the robot was taught from, in"
            f" {_names(programs, 4)}" + (f"; the earlier touch-ups are up to {far:.1f} mm from the new points" if far
                                         else "") + ".",
            "#taught", "Taught positions", who=(integrator,)))  # fmt: skip
    points, kept, _ = touch_up_counts(result)
    if points:
        left = points - kept - len(again)
        if left:
            last.append(Action(
                f"Touch up the {_plural(left, 'point')} on the robot" if not taught else
                f"Touch up the {_plural(left, 'theoretical point')} on the robot",
                "once the frames are set; they are the ABB's, as theoretical points"
                + (f"; {kept} keep the position touched up on the robot: check them only" if kept else "") + ".",
                "#ck-points", "Checklist: Points to touch up", who=(integrator,)))  # fmt: skip
        elif kept:
            last.append(Action(
                f"Check the {_plural(kept, 'point')} kept as touched up on the robot",
                "unchanged in the backup: the programs hold the taught values.",
                "#ck-points", "Checklist: Points to touch up", who=(integrator,)))  # fmt: skip
    actions = actions[: MAX_ACTIONS - len(last)] + last
    fillers = []
    if result.setup is not None and result.setup.program is not None:
        fillers.append(Action(f"Run `{result.setup.program.name}.LS` once", "it sets the tool and user frames on the"
                              " robot.", "#ck-frames", "Checklist: Frames and tools", who=(integrator,)))  # fmt: skip
    warnings = sum(1 for note in result.notes if note.kind == "WARNING")
    if warnings:
        fillers.append(Action(f"Check the {_plural(warnings, 'warning')}", "converted on an assumption.", "#review",
                              "Items to review", who=(integrator,)))  # fmt: skip
    if result.programs:
        fillers.append(Action("Load every program before running any", "a CALL to a program the robot does not have"
                              " fails when it runs.", "#ck-load", "Checklist: Load the programs", who=(integrator,)))  # fmt: skip
    while len(actions) < MIN_ACTIONS and fillers:
        actions.append(fillers.pop(0))
    return actions


def business(result: ConversionResult) -> str:
    """The sentence under the share converted by area (crossarm.convert.triage.business_sentence)."""
    return triage.business_sentence(result.coverage, todo_causes(result.notes))


def outlook(result: ConversionResult) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """The TODO causes TP has nothing for, and those a later CrossArm version may help with (triage.outlook)."""
    return triage.outlook(todo_causes(result.notes))


def counts_text(result: ConversionResult) -> str:
    """'763 TODO + 117 warnings': the items to review, said as what they are."""
    warnings = sum(1 for note in result.notes if note.kind == "WARNING")
    return f"{result.todo_count:,} TODO + {_plural(warnings, 'warning')}"


def analysis_markdown(result: ConversionResult, config: ConversionConfig | None = None) -> list[str]:
    """The analysis in the Markdown report: the decision, its rule, what to do first, capacity near the limit."""
    decision = verdict(result)
    path = path_to_workable(result)
    coverage = result.coverage
    clean = result.clean_programs()
    sentence = business(result)
    lines = [
        "## Analysis",
        "",
        f"- **{decision.sentence}**",
        *([f"- **{path.text()}**"] if path.needed else []),
        f"- {decision.rule}",
        *([f"- {fmt_percent(coverage.percent)} of the {coverage.total:,} RAPID instructions converted."]
          if coverage.total else []),
        *([f"- {sentence}"] if sentence else []),
        *([f"- {karel_use(result)}"] if karel_use(result) else []),
        *([f"- {func_programs_use(result)}"] if func_programs_use(result) else []),
        (f"- {clean} of {len(result.programs)} programs with no TODO, {len(result.programs) - clean} with TODO"
         f" ({_plural(result.todo_count, 'TODO', 'TODO')})."),
        *([f"- {result.since.text()}"] if result.since is not None else []),
        "",
    ]  # fmt: skip
    actions = priority_actions(result, config)
    if actions:
        lines += ["### What to do first", ""]
        for n, action in enumerate(actions, 1):
            meta = f" _{action.meta}._" if action.meta else ""
            lines.append(f"{n}. **{action.title}**: {action.detail} ({action.label}.){meta}")
            if action.snippet:
                lines += ["", ("   In `crossarm_mapping.json`, under `external_routines`, these entries (the program"
                               " names are suggestions: name the TP or KAREL programs you write):"), "", "   ```json",
                          *(f"   {line}" for line in action.snippet.splitlines()), "   ```", ""]  # fmt: skip
        lines.append("")
    no_tp, later = outlook(result)
    if no_tp or later:
        lines += ["### What is left, by outlook", ""]
        for title, causes in ((triage.NO_TP_TITLE, no_tp), (triage.LATER_TITLE, later)):
            if causes:
                lines.append(f"- **{title}**: " + ", ".join(f"{cause} ({n})" for cause, n in causes) + ".")
        lines.append("")
    near = near_limit(result.capacity)
    if near:
        lines += ["### Controller capacity near or over the limit", "",
                  "| Resource | Used | Limit | Status |", "|---|---|---|---|"]  # fmt: skip
        lines += [f"| {c.resource} | {c.used} | {'—' if c.limit is None else c.limit} | {capacity_status(c)} |"
                  for c in near]
        lines.append("")
        for proposal in triage.renumbering(result, config or ConversionConfig()):
            edit = f" Edit: `{json.dumps(proposal.edit)}`." if proposal.edit else ""
            lines.append(f"- {proposal.resource}: {proposal.text}{edit}")
        if lines[-1]:
            lines.append("")
    return lines
