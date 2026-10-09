# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""How the reports sort what is left: each TODO cause's family, whether the cell can produce without it, who acts
on it and what may change it later; the one sentence under the share converted by area; and, for a controller
resource over its limit, the numbers to change in the mapping file.

Every class is defined here, in this one place, as crossarm.convert.analysis keeps the decision's thresholds: the
reports (analysis, html_report) only show what these give.
"""

import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from crossarm.convert.blockers import Blocker
from crossarm.convert.config import ConversionConfig
from crossarm.convert.coverage import MOTION, Coverage, fmt_percent
from crossarm.convert.translate import ConversionResult, suffixed, tp_program_name

# ---------------------------------------------------------------------------
# Families: what a cause is about, as a tag
# ---------------------------------------------------------------------------

CALIBRATION, FRAMES, MOVES, IO, HMI, DATA, FLOW = "calibration", "frames", "motion", "I/O", "operator HMI", "data", "program flow"  # fmt: skip
ERRORS, INTERRUPTS, SYSTEM, NUMBERING, CROSSARM, OTHER = "errors", "interrupts", "system", "numbering", "CrossArm", "other"  # fmt: skip

FAMILIES: dict[str, str] = {
    Blocker.CALIBRATION: CALIBRATION, Blocker.SEARCH: CALIBRATION,
    Blocker.RUNTIME_FRAME: FRAMES, Blocker.SAVED_FRAME: FRAMES, Blocker.STATIONARY: FRAMES, Blocker.PAYLOAD: FRAMES,
    Blocker.RUNTIME_POSITION: MOVES, Blocker.MOTION: MOVES, Blocker.MOTION_SETTING: MOVES,
    Blocker.MOVE_ROUTINE: MOVES, Blocker.MOVE_ROUTINE_ASSUMED: MOVES, Blocker.AXIS_CONVENTION: MOVES,
    Blocker.OPTIONS_IGNORED: MOVES,
    Blocker.SIGNAL: IO, Blocker.WAIT_TIMEOUT: IO, Blocker.IO_ROUNDED: IO,
    Blocker.MESSAGE_VALUE: HMI, Blocker.MESSAGE_CUT: HMI,
    Blocker.VALUE: DATA, Blocker.RECORD: DATA, Blocker.RECORD_VALUE: DATA, Blocker.SAVED_VALUE: DATA,
    Blocker.LOCAL_RECORD: DATA, Blocker.TEXT: DATA,
    Blocker.CALL_ARGS: FLOW, Blocker.CONDITION: FLOW, Blocker.LOOP: FLOW, Blocker.PROVIDED_FUNCTION: FLOW,
    Blocker.INLINED: FLOW,
    Blocker.HANDLER: ERRORS,
    Blocker.INTERRUPT: INTERRUPTS, Blocker.MONITOR: INTERRUPTS,
    Blocker.MISSING: SYSTEM, Blocker.NO_TP_EQUIVALENT: SYSTEM, Blocker.REAL_CONTROLLER: SYSTEM,
    Blocker.CAPACITY: NUMBERING, Blocker.TAKEN: NUMBERING, Blocker.RENAMED: NUMBERING,
    Blocker.INTERNAL: CROSSARM,
    Blocker.OTHER: OTHER,
}  # fmt: skip
# What a family is about, in the sentence under the share converted by area.
FAMILY_WORDS = {
    CALIBRATION: "what the robot measures (calibration, searches)",
    FRAMES: "tool and frame set-up",
    MOVES: "positions and moves computed at run time",
    IO: "I/O signals and waits",
    HMI: "operator messages",
    DATA: "data known only at run time",
    FLOW: "program flow (calls, conditions, jumps)",
    ERRORS: "error handling",
    INTERRUPTS: "interrupts",
    SYSTEM: "system routines and functions",
    NUMBERING: "controller numbering",
    CROSSARM: "CrossArm internal errors",
    OTHER: "other causes",
}
_RAPID_ERRORS = frozenset(Blocker.rapid(kind) for kind in (
    "ERROR_HANDLER", "UNDO_HANDLER", "BACKWARD_HANDLER", "RAISE", "RETRY", "TRYNEXT"))  # fmt: skip


def family(cause: str) -> str:
    """The family of a cause: 'I/O' for an I/O signal without a mapping. A RAPID construct out of the parser's scope
    (Blocker.rapid) is error handling for the error handlers, program flow otherwise (GOTO, labels...)."""
    if cause in FAMILIES:
        return FAMILIES[cause]
    if cause in _RAPID_ERRORS:
        return ERRORS
    return FLOW if cause.startswith("RAPID ") else OTHER


# ---------------------------------------------------------------------------
# Production or cosmetic: can the cell produce with the line left TODO?
# ---------------------------------------------------------------------------

PRODUCTION, COSMETIC = "needed for production", "cosmetic"
# Causes whose TODO change only what the operator reads: the cell moves and works the same without them.
COSMETIC_CAUSES = frozenset({
    Blocker.MESSAGE_VALUE,  # a TPWrite showing a value: the text is shown, the value is not
    Blocker.MESSAGE_CUT,  # a pendant message longer than the TP allows: shown cut
})  # fmt: skip


def impact(causes: Iterable[str]) -> str:
    """COSMETIC when every cause is, PRODUCTION otherwise (and for none: the work is on what the cell does)."""
    causes = list(causes)
    return COSMETIC if causes and all(cause in COSMETIC_CAUSES for cause in causes) else PRODUCTION


# ---------------------------------------------------------------------------
# Who acts
# ---------------------------------------------------------------------------

INTEGRATOR = "FANUC integrator"
BACKUP = "ABB backup (add a module)"
OPTION = "robot option"
LATER = "a later CrossArm version may help"
WHO = (INTEGRATOR, BACKUP, OPTION, LATER)


# ---------------------------------------------------------------------------
# Outlook: TP has nothing for it, or a later CrossArm version may convert it
# ---------------------------------------------------------------------------

# TP has no equivalent: the FANUC side redesigns it, whatever the converter does.
NO_TP_CAUSES = frozenset({
    Blocker.NO_TP_EQUIVALENT, Blocker.MOTION, Blocker.LOOP, Blocker.HANDLER, Blocker.PROVIDED_FUNCTION,
    *_RAPID_ERRORS,
})  # fmt: skip
# TP has the means; CrossArm does not convert these yet in every form. No promise, no date.
LATER_CAUSES = frozenset({
    Blocker.VALUE, Blocker.CONDITION, Blocker.RECORD, Blocker.CALL_ARGS, Blocker.RUNTIME_POSITION,
    Blocker.RUNTIME_FRAME, Blocker.WAIT_TIMEOUT, Blocker.MOTION_SETTING, Blocker.PAYLOAD, Blocker.TEXT,
    Blocker.OTHER, Blocker.INTERNAL, Blocker.rapid("GOTO"), Blocker.rapid("LABEL"),
})  # fmt: skip
NO_TP_TITLE = "No TP equivalent: redesign on the FANUC side"
LATER_TITLE = "A later CrossArm version may help"


def outlook(causes: Sequence[tuple[str, int]]) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """The TODO causes (with their count, most first) TP has nothing for, and those a later version may convert;
    the rest has a fix known now (provide a module, map a signal, touch up...) and is in neither."""
    return ([(c, n) for c, n in causes if c in NO_TP_CAUSES], [(c, n) for c, n in causes if c in LATER_CAUSES])


# ---------------------------------------------------------------------------
# The sentence under the share converted by area
# ---------------------------------------------------------------------------

FULLY, MOSTLY, LARGELY = 100.0, 95.0, 80.0  # motion converted: fully, mostly, largely; partly below
DOMINATES = 50.0  # % of the TODO: one family (or two) is most of what is left above this share


def business_sentence(coverage: Coverage, causes: Sequence[tuple[str, int]]) -> str:
    """What the figures say, in one sentence: how much of the motion is converted, then what most of the TODO is
    about. Built from the figures only ('Motion mostly converted (97.5 %); most of what is left is tool and frame
    set-up (60 of 80 TODO).'); "" with nothing converted to talk about."""
    parts = []
    motion = next((share for share in coverage.shares if share.area == MOTION and share.total), None)
    if motion is not None:
        level = ("fully" if motion.percent >= FULLY else "mostly" if motion.percent >= MOSTLY else
                 "largely" if motion.percent >= LARGELY else "only partly")  # fmt: skip
        parts.append(f"Motion {level} converted" + ("" if level == "fully" else f" ({fmt_percent(motion.percent)})"))
    total = sum(n for _, n in causes)
    if not total:
        if not parts:
            return ""
        parts.append("nothing left TODO")
    else:
        families: Counter[str] = Counter()
        for cause, n in causes:
            families[family(cause)] += n
        ranked = sorted(families.items(), key=lambda kv: (-kv[1], kv[0]))
        (first, a), rest = ranked[0], ranked[1:]
        if a == total:
            parts.append(f"all of what is left is {FAMILY_WORDS[first]} ({total} TODO)")
        elif a * 100 > DOMINATES * total:
            parts.append(f"most of what is left is {FAMILY_WORDS[first]} ({a} of {total} TODO)")
        elif rest and (a + rest[0][1]) * 100 > DOMINATES * total:
            second, b = rest[0]
            if a + b == total:
                parts.append(f"what is left is {FAMILY_WORDS[first]} and {FAMILY_WORDS[second]} ({total} TODO)")
            else:
                parts.append(f"what is left is mostly {FAMILY_WORDS[first]} and {FAMILY_WORDS[second]}"
                             f" ({a + b} of {total} TODO)")  # fmt: skip
        else:
            parts.append(f"what is left is spread over {len(ranked)} families, {FAMILY_WORDS[first]} first"
                         f" ({a} of {total} TODO)")  # fmt: skip
    sentence = "; ".join(parts) + "."
    return sentence[0].upper() + sentence[1:]


# ---------------------------------------------------------------------------
# external_routines: an example to paste, from this run's candidates
# ---------------------------------------------------------------------------

EXAMPLE_CANDIDATES = 3  # candidates in the example


def external_example(result: ConversionResult, config: ConversionConfig | None = None) -> tuple[str, int]:
    """The first EXAMPLE_CANDIDATES routines CrossArm could not write, as entries of `external_routines` with a
    suggested TP program name in place of null (one no program written here has), ready to paste over theirs in
    crossarm_mapping.json; and how many candidates there are. ("", 0) without any."""
    candidates = result.provided_candidates
    if not candidates:
        return "", 0
    max_length = (config or ConversionConfig()).program_name_max_length
    taken = {info.program.name for info in result.programs}
    entries = []
    for candidate in candidates[:EXAMPLE_CANDIDATES]:
        name = suffixed(tp_program_name(candidate.name, max_length), taken, max_length)
        taken.add(name)
        entry: dict[str, object] = {"program": name}
        if candidate.arguments is not None:
            entry["arguments"] = list(candidate.arguments)
        if candidate.returns is not None:
            entry["returns"] = candidate.returns
        entries.append(f"{json.dumps(candidate.name)}: {json.dumps(entry, ensure_ascii=False)}")
    return ",\n".join(entries), len(candidates)


# ---------------------------------------------------------------------------
# A controller resource over its limit: what to change in the mapping file
# ---------------------------------------------------------------------------

# The mapping file's key for each numbered resource (crossarm.convert.mapping.build_mapping), which is also the
# ConversionResult attribute holding its allocations.
MAPPING_KEYS = {
    "R": "registers", "F": "flags", "SR": "string_registers", "DO": "digital_outputs", "DI": "digital_inputs",
    "GO": "group_outputs", "GI": "group_inputs", "AO": "analog_outputs", "TIMER": "timers", "UFRAME": "uframes",
    "UTOOL": "utools",
}  # fmt: skip
_FIRST = {"UFRAME": 1}  # UFRAME 0 is the world frame, never given; every other number starts at 1
_SYSTEM_VARIABLE = {"UTOOL": "$SCR.$MAXNUMUTOOL", "UFRAME": "$SCR.$MAXNUMUFRAM"}


@dataclass(frozen=True, slots=True)
class Renumbering:
    """One way to bring a resource within the controller: what to do, and the mapping file's keys to edit."""

    resource: str
    text: str  # what to do and why it holds (Markdown inline)
    edit: dict[str, dict[str, object]]  # {mapping key: {name or resource: number}}, to edit in crossarm_mapping.json


def renumbering(result: ConversionResult, config: ConversionConfig) -> list[Renumbering]:
    """For each resource over its limit, the proposals that keep every other number as it is (the mapping file
    given back pins them all): move the names past the limit to numbers free under it; for frames, free position
    registers for the banks (a frame past the limit is then kept in a position register and loaded before each use,
    as CrossArm does since 1.8 when registers are free); else raise the limit, when the controller holds more."""
    out: list[Renumbering] = []
    for c in result.capacity:
        if c.fits or c.limit is None:
            continue
        resource, over = c.resource, list(c.over)
        if resource == "PR":
            out.append(Renumbering(resource, (
                f"{len(over)} computed frame value(s) found no free position register. Free position registers on"
                " the robot, or raise `limits.PR` if the controller holds more, and convert again."),
                {"limits": {"PR": c.limit + len(over)}}))  # fmt: skip
            continue
        key = MAPPING_KEYS.get(resource)
        allocations = getattr(result, key, []) if key else []
        used = {a.number for a in allocations}
        reserved = set(config.reserved.get(resource, {}))
        free = [k for k in range(_FIRST.get(resource, 1), c.limit + 1) if k not in used and k not in reserved]
        names = {a.rapid_name: (getattr(a, "key", "") or a.rapid_name) for a in allocations}
        if key and free:
            moved = over[: len(free)]
            out.append(Renumbering(resource, (
                f"{len(free)} {resource} number(s) under the limit of {c.limit} are free: pin "
                + ("them" if len(moved) == len(over) else f"{len(moved)} of the {len(over)}")
                + f" in `{key}`; every other number stays as it is."),
                {key: {names.get(name, name): number for name, number in zip(moved, free, strict=False)}}))  # fmt: skip
        if resource in ("UTOOL", "UFRAME"):
            banks = len(over) + 1  # the last number under the limit becomes the one they are loaded into
            free_pr, _ = config.free_position_registers()
            taken = sorted(config.reserved.get("PR", {}), reverse=True)[: banks + 1]
            programs = sorted({p for n in taken for p in config.reserved.get("PR", {}).get(n, ())})
            if len(free_pr) < banks + 1 and taken:
                shown = ", ".join(f"PR[{n}]" for n in taken)
                out.append(Renumbering(resource, (
                    f"Free {banks + 1} position registers on the robot ({shown}"
                    + (f", used by {', '.join(f'`{p}`' for p in programs[:4])}" if programs else "")
                    + f"; one is SETUP_FRAMES' own) and convert again with the robot's programs: the {len(over) + 1}"
                    f" {resource} numbered past {c.limit - 1} are then kept in them and loaded into {resource}[{c.limit}]"
                    " before each use."),
                    {}))  # fmt: skip
            out.append(Renumbering(resource, (
                f"Raise the controller's number of {resource} to {c.highest} at a Controlled Start"
                f" (`{_SYSTEM_VARIABLE[resource]}`) and set it in `limits`: every frame is then selected directly."),
                {"limits": {resource: c.highest}}))  # fmt: skip
        elif not free:
            out.append(Renumbering(resource, (
                f"No {resource} number under the limit of {c.limit} is free: if the controller holds more, set"
                f" `limits.{resource}`; otherwise the programs need fewer of them."),
                {"limits": {resource: c.highest}}))  # fmt: skip
    return out
