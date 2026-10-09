# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""How the report's programs are put in front of the reader: in folders, and each one with its TODO in sight.

A large backup writes hundreds of programs; one line each is a wall nobody reads. The report shows them in
virtual folders instead, by the start of their name (PICK_A, PICK_B, PICK_C: PICK*), which is how a cell's
programs are named; those sharing their start with fewer than MIN_FOLDER - 1 others go by the RAPID module they
come from, and the rest in one folder of their own. A folder holds MIN_FOLDER programs at least.

In a program, the TODO-only view keeps the rows with a TODO or warning and CONTEXT rows on each side; each run
of rows left out becomes one separator ("... 12 lines converted ..."), unless it is shorter than MIN_GAP rows (the
separator would take the room the rows do). A run of MIN_SAME rows or more in a row with the same warning and no
TODO (a calibration routine, every line converted on the same assumption) keeps its first row, and the others
become one separator too ("... 12 lines with the same warning: X ..."): the TODO-only view stays short on a program
that is mostly warnings.

Nothing here reaches the .LS files, the mapping file or the Markdown report: the HTML report only.
"""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

MIN_FOLDER = 3  # programs a folder holds at least
CONTEXT = 2  # rows kept on each side of a row with a TODO or warning, in the TODO-only view
MIN_GAP = 3  # fewer rows left out than this are shown: a separator would be as long
MIN_SAME = 4  # rows in a row with the same warning, at least, for all but the first to be folded

PREFIX, MODULE, OTHER = "prefix", "module", "other"
_START = re.compile(r"[A-Za-z]+")


@dataclass(frozen=True, slots=True)
class Folder:
    """A virtual folder of programs: by the start of their name, by RAPID module, or the others."""

    kind: str  # PREFIX, MODULE or OTHER
    key: str  # the start of the names (upper case), the module, or ""
    programs: tuple[str, ...]  # in the order given

    @property
    def label(self) -> str:
        if self.kind == PREFIX:
            return f"{self.key}*"
        if self.kind == MODULE:
            return f"module {self.key}"
        return "Other programs"


def name_start(name: str) -> str:
    """The start of a program's name a folder groups by: its letters up to the first digit or underscore."""
    found = _START.match(name)
    return found[0].upper() if found else ""


def folders(programs: Sequence[tuple[str, str]]) -> list[Folder]:
    """(program, RAPID module) -> folders, in the order of their first program: by name start when MIN_FOLDER
    programs share it, else by module when MIN_FOLDER of the programs left come from it, else "Other programs"
    (last). A backup where this makes no folder at all (every program in the others) gets [] : a list, not folders."""
    starts = Counter(start for name, _ in programs if (start := name_start(name)))
    by_start = {name: start for name, _ in programs if starts[start := name_start(name)] >= MIN_FOLDER and start}
    modules = Counter(module for name, module in programs if name not in by_start and module)
    found: dict[tuple[str, str], list[str]] = {}
    for name, module in programs:
        if name in by_start:
            key = (PREFIX, by_start[name])
        elif module and modules[module] >= MIN_FOLDER:
            key = (MODULE, module)
        else:
            key = (OTHER, "")
        found.setdefault(key, []).append(name)
    out = [Folder(kind, key, tuple(names)) for (kind, key), names in found.items() if kind != OTHER]
    if not out:
        return []
    if (OTHER, "") in found:
        out.append(Folder(OTHER, "", tuple(found[OTHER, ""])))
    return out


@dataclass(frozen=True, slots=True)
class Run:
    """Rows start..end - 1 of a program's view: shown in the TODO-only view, or left out behind one separator."""

    start: int
    end: int
    shown: bool
    same: str = ""  # left out as repeats of the row before: the warning they all have


def _repeats(same: Sequence[str | None], min_same: int) -> list[str]:
    """Each row's warning when it repeats the one before in a run of min_same rows or more, else ""."""
    out = [""] * len(same)
    i = 0
    while i < len(same):
        j = i + 1
        if same[i]:
            while j < len(same) and same[j] == same[i]:
                j += 1
            if j - i >= min_same:
                out[i + 1:j] = [same[i]] * (j - i - 1)  # type: ignore[list-item]
        i = j
    return out


def todo_only(marked: Sequence[bool], context: int = CONTEXT, min_gap: int = MIN_GAP,
              same: Sequence[str | None] | None = None, min_same: int = MIN_SAME) -> list[Run]:  # fmt: skip
    """The rows of a program's view (True: a TODO or warning) as runs shown or left out in its TODO-only view.
    No row marked: one run left out (the program has nothing to review: its full view is the one shown).
    `same`: each row's warning when it has warnings and no TODO (None otherwise): min_same rows or more in a row
    with the same one keep the first, the others are left out as one run naming it (Run.same)."""
    count = len(marked)
    folded = _repeats(same, min_same) if same is not None else [""] * count
    keep = [False] * count
    for i, mark in enumerate(marked):
        if mark:
            for k in range(max(0, i - context), min(count, i + context + 1)):
                keep[k] = True
    state = ["" if not keep[i] else "+" for i in range(count)]
    for i, label in enumerate(folded):
        if label:
            state[i] = "=" + label
    runs: list[Run] = []
    i = 0
    while i < count:
        j = i + 1
        while j < count and state[j] == state[i]:
            j += 1
        if state[i].startswith("="):
            runs.append(Run(i, j, False, state[i][1:]))
            i = j
            continue
        shown = state[i] == "+" or (j - i < min_gap and any(marked))
        if runs and runs[-1].shown and shown:
            runs[-1] = Run(runs[-1].start, j, True)
        else:
            runs.append(Run(i, j, shown))
        i = j
    return runs
