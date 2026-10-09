# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Which RAPID line each TP line was written from: the HTML report shows them side by side.

The translator tags the lines a statement wrote once the statement is done. The statements nested in it
are done first and tag their own lines, so each TP line carries the line of the innermost RAPID statement
that wrote it (an IF's ENDIF the IF's, the moves inside it their own). A tag follows the line object, so a
line moved afterwards (the branches of a TEST written behind its SELECT) keeps it. When the program is
complete the tags are read into ProgramInfo.sources, one per TP line, None for a line no statement wrote
(the routine's header remark, the copies of its parameters). Nothing of it reaches the .LS files.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import quote, unquote

from crossarm.fanuc.tp import Motion


class SourceTags:
    """The RAPID line of each TP line a routine's translator wrote, by line object."""

    __slots__ = ("_tags",)

    def __init__(self) -> None:
        # id(line) -> (line, RAPID line). The line is held, so its id cannot be reused by another object.
        self._tags: dict[int, tuple[object, int]] = {}

    def tag(self, lines: Sequence[object], start: int, rapid_line: int) -> None:
        """Lines from `start` on that no statement nested in this one tagged come from `rapid_line`."""
        tags = self._tags
        for i in range(start, len(lines)):
            line = lines[i]
            if id(line) not in tags:
                tags[id(line)] = (line, rapid_line)

    def of(self, lines: Sequence[object]) -> tuple[int | None, ...]:
        """The RAPID line of each of these lines, None where no statement wrote it."""
        out: list[int | None] = []
        for line in lines:
            found = self._tags.get(id(line))
            out.append(found[1] if found is not None and found[0] is line else None)
        return tuple(out)


@dataclass(frozen=True, slots=True)
class Row:
    """One row of the side-by-side view: a RAPID line and the TP lines written from it."""

    rapid: int | None  # the RAPID line, None for TP lines no statement wrote
    tp: tuple[int, ...]  # indices into the program's lines (0-based)
    again: bool = False  # a RAPID line shown above: TP lines it wrote further down (an ENDIF, a moved branch)


def side_by_side(sources: Sequence[int | None], first: int, last: int) -> list[Row]:
    """RAPID lines first..last of a routine aligned with the TP lines written from them, in TP order.

    The lines a program starts with before any statement (its header remark, its parameters copied)
    go with the routine's first line. Every RAPID line is shown once, in order; a line that wrote nothing (a declaration, a blank line, an
    ENDIF) has a row with no TP line. TP lines from a RAPID line already shown get a row of their own,
    marked `again`, where they sit in the program.
    """
    rows: list[Row] = []
    shown = first  # the next RAPID line not shown yet
    i, count = 0, len(sources)
    while i < count:
        line = sources[i]
        j = i + 1
        while j < count and sources[j] == line:
            j += 1
        group = tuple(range(i, j))
        if line is None and i == 0 and first <= last:  # the routine's header remark, its parameters copied
            rows.append(Row(first, group))
            shown = first + 1
        elif line is None:
            rows.append(Row(None, group))
        elif shown <= line <= last:
            rows.extend(Row(k, ()) for k in range(shown, line))
            rows.append(Row(line, group))
            shown = line + 1
        else:
            rows.append(Row(line, group, again=True))
        i = j
    rows.extend(Row(k, ()) for k in range(shown, last + 1))
    return rows


def tp_text(line: object) -> list[str]:
    """A TP line as the .LS shows it, without number and ';': two lines for a circular move."""
    if isinstance(line, Motion):
        tail = f"{line.speed} {line.termination}" + (f" {line.options}" if line.options else "")
        if line.kind == "C":
            return [f"C {line.via}", f"   {line.target} {tail}"]
        return [f"{line.kind} {line.target} {tail}"]
    return [getattr(line, "text", str(line))]


def line_anchor(program: str, line: int) -> str:
    """The id of a RAPID line in the report page: its row in the program's side-by-side view."""
    return f"L-{program}-{line}"


TODO_FILTERS = ("kind", "cause", "prog", "q")  # what a link to the items to review may filter on


def todo_href(*, cause: str = "", prog: str = "", kind: str = "", q: str = "") -> str:
    """A link to the report's items to review, filtered: '#todo&cause=...&prog=...'. The page shows the TODO
    (kind=WARNING for the warnings, kind=all for both), of that cause and program, matching q."""
    given = {"kind": kind, "cause": cause, "prog": prog, "q": q}
    return "#todo" + "".join(f"&{key}={quote(given[key], safe='')}" for key in TODO_FILTERS if given[key])


def parse_todo_href(href: str) -> dict[str, str] | None:
    """The filters of a todo_href link (as the page's script reads location.hash); None for another link."""
    parts = href.lstrip("#").split("&")
    if parts[0] != "todo":
        return None
    out = {}
    for part in parts[1:]:
        key, _, value = part.partition("=")
        if key in TODO_FILTERS:
            out[key] = unquote(value)
    return out
