# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""ConversionResult -> crossarm_report.html, the report to work from on site.

One self-contained page: its style and script are in it, it loads nothing (cells are often offline) and
reads from file:// in any browser. It opens as a cockpit: a line kept at the top of the screen says where the
conversion stands (decision, share converted, TODO, blocking causes, points to touch up) above the sections'
menu, the analysis says what to do first, and every other section is one folded line saying what it holds.

    Analysis         the first screen: the decision and the rule it follows, what to do first, where the TODO
                     come from, the share converted by area, the controller resources near their limit
                     (crossarm.convert.analysis); the rest of the page is the detail behind it
    Taught positions with --keep-taught: what became of each point touched up on the robot, program by program
                     (crossarm.convert.taught_report)
    Checklist        commissioning on the FANUC cell, in order, ticked off in the browser (crossarm.convert.checklist)
    Items to review  every TODO and warning, filtered by kind, cause and program, or searched, 50 at a time
    RAPID and TP     each program, its RAPID routine and the TP written from it side by side, line by line
                     (crossarm.convert.source_map), the lines left TODO marked with their cause and why; the
                     programs with no TODO in one line, shown on demand
    Points           one line per program, its points on demand
    Summary          the figures, then the summary of the Markdown report
    Details          the rest of the Markdown report: programs, frames, registers, speeds, what the run added

A large backup is tens of thousands of lines: the folded sections hold them as inert <template> elements the
script turns into the page only when their fold is opened (the browser lays out the first screen alone). Three
views of the same page, chosen at the top, fold it differently: synthesis (the analysis alone), integrator (the
checklist, the items to review and the programs with TODO open too), detail (every section open; programs and
points still one fold each). Links '#todo&cause=..&prog=..' (todo_href) open the items to review filtered.
Without its script the page shows the analysis and says the lists are in the Markdown report.

Each section is one function returning (id, menu label, HTML); a new section is one more entry in
build_html_report. Every text from the backup is escaped.
"""

import html
import json
import re
from collections import Counter, defaultdict

from crossarm import __version__
from crossarm.convert import analysis, triage
from crossarm.convert.analysis import (
    Action,
    business,
    capacity_status,
    counts_text,
    near_limit,
    outlook,
    priority_actions,
    top_causes,
    touch_up_counts,
    verdict,
)
from crossarm.convert.checklist import CHECKLIST_CSS, CHECKLIST_JS, checklist_section
from crossarm.convert.config import ConversionConfig
from crossarm.convert.coverage import MOTION, fmt_percent
from crossarm.convert.html import CSS as MARKDOWN_CSS
from crossarm.convert.html import inline, markdown_body
from crossarm.convert.report import EVALUATION_NOTICE, report_parts
from crossarm.convert.source_map import Row, line_anchor, side_by_side, todo_href, tp_text
from crossarm.convert.taught import AGAIN, KEPT
from crossarm.convert.taught_report import TAUGHT_CSS, TAUGHT_JS, taught_section
from crossarm.convert.translate import ConversionResult, Note, ProgramInfo
from crossarm.fanuc.ktrans import KarelExport
from crossarm.fanuc.maketp import TpExport
from crossarm.fanuc.tp import CartesianPosition
from crossarm.licence import LicenceStatus

Section = tuple[str, str, str]  # (id, menu label, HTML)

REVIEW_PAGE = 50  # items to review shown at a time
SYNTHESIS, INTEGRATOR, DETAIL = "s", "i", "d"  # the page's views; a fold opens in the views it lists (data-depth)
VIEWS = ((SYNTHESIS, "Synthesis"), (INTEGRATOR, "Integrator"), (DETAIL, "Detail"))

_END = re.compile(r"^\s*END(PROC|FUNC|TRAP)\b", re.IGNORECASE)
_MARKDOWN_REPORT = "crossarm_report.md"


def _e(text: object) -> str:
    return html.escape(str(text), quote=True)


def _s(count: int, word: str) -> str:
    return f"{count:,} {word}{'' if count == 1 else 's'}"


def routine_end(source: list[str], first: int) -> int:
    """The line of the ENDPROC (ENDFUNC, ENDTRAP) closing the routine starting at `first`."""
    for number in range(first, len(source) + 1):
        if _END.match(source[number - 1].split("!", 1)[0]):
            return number
    return len(source)


# ---------------------------------------------------------------------------
# Folds: what the page holds but does not lay out until asked
# ---------------------------------------------------------------------------

_NOSCRIPT = ("<noscript><p class=\"muted\">This list is shown by the page's script, which this browser does not run:"
             f" the same is in <code>{_MARKDOWN_REPORT}</code>, written with this page.</p></noscript>")  # fmt: skip


def lazy(body: str) -> str:
    """`body` kept inert: the script makes it part of the page when the fold holding it is first opened."""
    return f"<template data-lazy>{body}</template>{_NOSCRIPT}"


def _fold(section: Section, line: str, depth: str, *, fold_id: str = "") -> Section:
    """The section as one folded line: its heading and `line` (what it holds, as figures); its body lazy.
    `depth`: the views it is open in (SYNTHESIS, INTEGRATOR, DETAIL letters)."""
    sid, label, body = section
    found = re.match(r"\s*<h2([^>]*)>(.*?)</h2>\s*", body, re.DOTALL)
    attributes, heading, rest = (found[1], found[2], body[found.end():]) if found else ("", _e(label), body)
    ident = f' id="{_e(fold_id)}"' if fold_id else ""
    return sid, label, (f'<details class="sec"{ident} data-depth="{depth}"><summary><h2{attributes}>{heading}</h2>'
                        f' <span class="sline">{line}</span></summary>\n{lazy(rest)}\n</details>')  # fmt: skip


# ---------------------------------------------------------------------------
# RAPID and TP side by side
# ---------------------------------------------------------------------------


def _note_rows(notes: list[Note]) -> str:
    out = []
    for note in notes:
        kind = "todo" if note.kind == "TODO" else "warn"
        out.append(f'<tr class="note {kind}"><td></td><td colspan="3"><span class="tag {kind}">{_e(note.kind)}</span>'
                   f' <span class="cause">{_e(note.category)}</span> {inline(note.message)}</td></tr>')  # fmt: skip
    return "".join(out)


def _program_view(info: ProgramInfo, result: ConversionResult, notes: list[Note], lead: list[str],
                  anchors: set[tuple[str, int]]) -> str:  # fmt: skip
    """One program: RAPID on the left, TP on the right, a row per RAPID line."""
    name = info.program.name
    lines = info.program.lines
    offset = 0 if info.program.condition else len(lead)
    source = result.rapid_sources.get(info.module.upper()) if info.sources else None
    if source and 0 < info.routine_line <= len(source):
        rows = side_by_side(info.sources, info.routine_line, routine_end(source, info.routine_line))
    else:  # written by CrossArm, from no single routine: the TP only
        rows, source = ([Row(None, tuple(range(len(lines))))] if lines else []), None
    by_line: dict[int, list[Note]] = defaultdict(list)
    for note in notes:
        if note.rapid_line:
            by_line[note.rapid_line].append(note)
    shown = {row.rapid for row in rows if row.rapid is not None and not row.again}
    loose = [note for note in notes if note.rapid_line not in shown]

    out = []
    if loose:  # notes on the routine as a whole, or on a line outside it (a declaration of the module)
        out.append('<table class="sbs loose"><tbody>' + _note_rows(loose) + "</tbody></table>")
    out.append('<table class="sbs"><colgroup><col class="cn"><col class="cc"><col class="cn"><col class="cc">'
               "</colgroup><thead><tr><th>l.</th><th>RAPID</th><th>l.</th><th>TP</th></tr></thead><tbody>")  # fmt: skip
    if offset:
        numbers = "\n".join(str(k) for k in range(1, offset + 1))
        out.append(f'<tr class="mark"><td></td><td></td><td class="n">{numbers}</td>'
                   f'<td class="c">{_e(chr(10).join(lead))}</td></tr>')  # fmt: skip
    for row in rows:
        numbers, texts = [], []
        for i in row.tp:
            for k, text in enumerate(tp_text(lines[i])):
                numbers.append(str(i + 1 + offset) if k == 0 else "")
                texts.append(text)
        tp_cells = f'<td class="n">{chr(10).join(numbers)}</td><td class="c">{_e(chr(10).join(texts))}</td>'
        if row.rapid is None:
            out.append(f"<tr><td></td><td></td>{tp_cells}</tr>")
            continue
        if row.again:
            out.append(f'<tr class="again"><td class="n">{row.rapid}</td><td class="c up">↑</td>{tp_cells}</tr>')
            continue
        here = by_line.get(row.rapid, [])
        kind = ' class="todo"' if any(n.kind == "TODO" for n in here) else ' class="warn"' if here else ""
        text = source[row.rapid - 1] if source and row.rapid <= len(source) else ""
        anchors.add((name, row.rapid))
        out.append(f'<tr id="{_e(line_anchor(name, row.rapid))}"{kind}><td class="n">{row.rapid}</td>'
                   f'<td class="c">{_e(text.rstrip())}</td>{tp_cells}</tr>')  # fmt: skip
        out.append(_note_rows(here))
    out.append("</tbody></table>")
    return "".join(out)


def _counts(notes: list[Note]) -> tuple[Counter[str], Counter[str]]:
    todo, warnings = Counter[str](), Counter[str]()
    for note in notes:
        (todo if note.kind == "TODO" else warnings)[note.program] += 1
    return todo, warnings


def _badges(todo: int, warnings: int) -> str:
    out = f' <span class="tag todo">{todo} TODO</span>' if todo else ' <span class="tag ok">no TODO</span>'
    if warnings:
        out += f' <span class="tag warn">{warnings} warning{"s" if warnings > 1 else ""}</span>'
    return out


def _code_section(result: ConversionResult, lead: list[str], anchors: set[tuple[str, int]]) -> Section:
    """Programs with TODO first in sight; those with none in one line, shown on demand; each program's view
    built when it is opened."""
    todo, warnings = _counts(result.notes)
    notes: dict[str, list[Note]] = defaultdict(list)
    for note in result.notes:
        notes[note.program].append(note)
    index, views = [], []
    for info in result.programs:
        name = info.program.name
        routine = f"{info.module}.{info.routine}" if info.module else info.routine
        ready = "" if todo[name] else " data-ready"
        index.append(f'<tr data-p="{_e(name)}" data-r="{_e(routine)}" data-todo="{todo[name]}"{ready}>'
                     f'<td><a href="#p-{_e(name)}">{_e(name)}.LS</a>'
                     f"</td><td>{_e(routine)}</td><td>{len(info.program.lines)}</td><td>{len(info.points)}</td>"
                     f"<td>{todo[name] or ''}</td><td>{warnings[name] or ''}</td></tr>")  # fmt: skip
        views.append(f'<details class="prog" id="p-{_e(name)}" data-p="{_e(name)}" data-r="{_e(routine)}"'
                     f' data-todo="{todo[name]}"{ready}>'
                     f'<summary><span class="pn">{_e(name)}.LS</span> <span class="muted">{_e(routine)}</span>'
                     f"{_badges(todo[name], warnings[name])}</summary>"
                     f"{lazy(_program_view(info, result, notes[name], lead, anchors))}</details>")  # fmt: skip
    ready = sum(1 for info in result.programs if not todo[info.program.name])
    with_todo = len(result.programs) - ready
    ready_line = (
        f'<p class="ready"><span class="tag ok">ready</span> <b>{_s(ready, "program")} ready as is</b>: no TODO, to'
        f' load and check. <button type="button" class="js-only-inline" id="p-ready">show them</button></p>'
        if ready and with_todo else ""
    )  # fmt: skip
    body = [
        "<h2>RAPID and TP side by side</h2>",
        ("<p>Each program as written in its <code>.LS</code> file, next to the RAPID routine it comes from: every"
        " RAPID line on the left, the TP lines written from it on the right (numbered as in the <code>.LS</code>)."
        " A TP line written further down for a RAPID line already shown (an <code>ENDIF</code>, a branch moved"
        " behind its <code>SELECT</code>) is marked ↑. Lines left TODO are marked, with their cause and why.</p>"),
        ready_line,
        ('<div class="bar js-only"><input id="p-text" type="search" placeholder="Filter programs" aria-label="Filter'
        ' programs"> <button type="button" id="p-open">Expand the programs shown</button> <button type="button"'
        ' id="p-close">Collapse all</button> <span id="p-count" class="muted"></span></div>'),
        '<div id="p-box">' if with_todo else '<div id="p-box" class="show-ready">',
        '<div class="table-wrap"><table class="index"><thead><tr><th>TP program</th><th>RAPID routine</th>'
        "<th>Lines</th><th>Points</th><th>TODO</th><th>Warnings</th></tr></thead><tbody>"
        + "".join(index) + "</tbody></table></div>",
        *views,
        "</div>",
    ]  # fmt: skip
    return "code", "RAPID and TP", "\n".join(body)


# ---------------------------------------------------------------------------
# Items to review
# ---------------------------------------------------------------------------


def _review_section(result: ConversionResult, anchors: set[tuple[str, int]]) -> Section:
    """Every TODO and warning as an inert row; the script shows REVIEW_PAGE of those the filters keep at a time."""
    notes = sorted(result.notes, key=lambda x: (x.program, x.rapid_line or 0))
    programs = sorted({note.program for note in notes if note.program})
    shown = {info.program.name for info in result.programs}
    causes = Counter(note.category for note in notes)
    rows = []
    for note in notes:
        kind = "todo" if note.kind == "TODO" else "warn"
        if note.program and note.rapid_line and (note.program, note.rapid_line) in anchors:
            where = f'<a href="#{_e(line_anchor(note.program, note.rapid_line))}">{note.rapid_line}</a>'
        elif note.program in shown:
            where = f'<a href="#p-{_e(note.program)}">{note.rapid_line or "—"}</a>'
        else:
            where = str(note.rapid_line or "—")
        rows.append(f'<tr data-k="{_e(note.kind)}" data-c="{_e(note.category)}" data-p="{_e(note.program)}">'
                    f"<td>{_e(note.program or '—')}</td><td>{where}</td><td class=\"kind-{_e(note.kind)}\">"
                    f'<span class="tag {kind}">{_e(note.kind)}</span></td><td>{_e(note.category)}</td>'
                    f"<td>{inline(note.message)}</td></tr>")  # fmt: skip
    cause_options = "".join(f'<option value="{_e(c)}">{_e(c)} ({count})</option>' for c, count in causes.most_common())
    program_options = "".join(f'<option value="{_e(p)}">{_e(p)}</option>' for p in programs)
    default = "TODO" if result.todo_count else ""  # the TODO first; the warnings when there is no TODO
    body = [
        "<h2>Items to review</h2>",
        ("<p>TODO: not converted, to write by hand. Warning: converted on an assumption, to check. The RAPID line"
         " leads to its place in the programs.</p>"),
        ('<div class="bar js-only"><input id="f-text" type="search" placeholder="Search" aria-label="Search">'
        f' <select id="f-kind" aria-label="Kind" data-default="{default}"><option value="">TODO and warnings</option>'
        f'<option value="TODO"{" selected" if default else ""}>TODO</option><option value="WARNING">Warnings</option>'
        "</select>"
        f' <select id="f-cause" aria-label="Cause"><option value="">Every cause</option>{cause_options}</select>'
        f' <select id="f-prog" aria-label="Program"><option value="">Every program</option>{program_options}</select>'
        ' <button type="button" id="f-reset" title="The TODO of every cause and program">Reset</button> <span id="f-count" class="muted"></span></div>'),
        ('<div class="table-wrap"><table class="review"><thead><tr><th>Program</th><th>RAPID line</th><th>Kind</th>'
         '<th>Cause</th><th>Detail</th></tr></thead><tbody id="f-body"></tbody></table></div>'
         f'<template id="f-rows" data-page="{REVIEW_PAGE}">{"".join(rows)}</template>'
         '<p class="more"><button type="button" id="f-more" hidden>Show more</button></p>')
        if rows else '<p class="muted">None.</p>',
    ]  # fmt: skip
    return "review", f"Items to review ({len(rows)})", "\n".join(body)


# ---------------------------------------------------------------------------
# Points
# ---------------------------------------------------------------------------


def _point_value(value: object) -> str:
    if isinstance(value, CartesianPosition):
        v = value
        return f"X {v.x:.3f} Y {v.y:.3f} Z {v.z:.3f} W {v.w:.3f} P {v.p:.3f} R {v.r:.3f}"
    return "J " + " ".join(f"{j:.3f}" for j in value.joints)  # type: ignore[attr-defined]


def _points_section(result: ConversionResult, anchors: set[tuple[str, int]]) -> Section | None:
    """One line per program with its count of points, frames and RAPID lines; its points when it is opened."""
    programs = [info for info in result.programs if info.points]
    if not programs:
        return None
    lines = []
    for info in programs:
        name = info.program.name
        frames = sorted({f"{p.uf}/{p.ut}" for p in info.points})
        rapid = sorted(p.rapid_line for p in info.points if p.rapid_line)
        search = " ".join([name, *(p.source for p in info.points)]).lower()
        rows = []
        for p in info.points:
            line = str(p.rapid_line or "—")
            if p.rapid_line and (name, p.rapid_line) in anchors:
                line = f'<a href="#{_e(line_anchor(name, p.rapid_line))}">{p.rapid_line}</a>'
            rows.append(f"<tr><td>P[{p.number}]</td><td><code>{_e(p.source)}</code></td><td>{line}</td>"
                        f'<td>{_e(p.uf)}/{_e(p.ut)}</td><td class="v">{_e(_point_value(p.value))}</td></tr>')  # fmt: skip
        where = f"RAPID lines {rapid[0]}–{rapid[-1]}" if len(rapid) > 1 else f"RAPID line {rapid[0]}" if rapid else ""
        lines.append(
            f'<details class="pts" data-p="{_e(name)}" data-s="{_e(search)}"><summary><span class="pn">{_e(name)}.LS'
            f'</span> <b>{_s(len(info.points), "point")}</b> <span class="muted">UF/UT {_e(", ".join(frames))}'
            f'{" · " + where if where else ""}</span></summary>'
            + lazy('<div class="table-wrap"><table class="points"><thead><tr><th>P</th><th>RAPID target</th>'
                   "<th>RAPID line</th><th>UF/UT</th><th>Value (theoretical)</th></tr></thead><tbody>"
                   + "".join(rows) + "</tbody></table></div>")
            + "</details>"
        )  # fmt: skip
    body = [
        "<h2>Points</h2>",
        ("<p>The ABB's points, written as theoretical points: touch them up on the robot once the frames are set."
         " One line per program: open it for its points, or search a program or a RAPID target.</p>"),
        ('<div class="bar js-only"><input id="pt-text" type="search" placeholder="Program or RAPID target"'
         ' aria-label="Search points"> <span id="pt-count" class="muted"></span></div>'),
        '<div id="pt-box">' + "".join(lines) + "</div>",
    ]  # fmt: skip
    return "points", "Points", "\n".join(body)


# ---------------------------------------------------------------------------
# Analysis: the first screen
# ---------------------------------------------------------------------------


def _line_link(program: str, line: int | None, anchors: set[tuple[str, int]], shown: set[str]) -> str:
    """'PROG l.12', leading to that line when the page shows it."""
    text = f"{program} l.{line}" if line else program or "whole conversion"
    if program and line and (program, line) in anchors:
        return f'<a href="#{_e(line_anchor(program, line))}">{_e(text)}</a>'
    if program in shown:
        return f'<a href="#p-{_e(program)}">{_e(text)}</a>'
    return _e(text)


MAX_LINK_PROGRAMS = 8  # an action's link names its programs up to this many (the causes alone keep the same items)


def _action(action: Action, targets: set[str]) -> str:
    """One thing to do: its verb and how; then the TODO it concerns, leading to the items to review filtered on its
    causes (and programs), who acts, cosmetic when the cell runs without it, and where it is detailed."""
    href = action.href if action.href.split("&")[0][1:] in targets else "#details"
    filtered = ""
    if action.causes and action.todo and "review" in targets:
        programs = action.programs if len(action.programs) <= MAX_LINK_PROGRAMS else ()
        filtered = todo_href(cause=action.causes, prog=programs)
    elif action.cause and href == "#review":
        href = todo_href(cause=action.cause)
    meta = []
    if action.todo:
        count = f"{action.todo:,} TODO concerned"
        meta.append(f'<a class="n" href="{_e(filtered)}">{count} →</a>' if filtered else f'<b class="n">{count}</b>')
    if action.who:
        meta.append(f'<span class="who">Who acts: {_e(action.who_text)}</span>')
    if action.causes and action.impact == triage.COSMETIC:
        meta.append('<span class="tag cos" title="The cell moves and works the same without it">cosmetic</span>')
    if not (filtered and href == "#review"):
        meta.append(f'<a class="more" href="{_e(href)}">{_e(action.label)} →</a>')
    snippet = ""
    if action.snippet:
        shown = action.snippet.count("\n") + 1
        snippet = (
            '<details class="ext"><summary><code>external_routines</code>: an example to paste'
            f" ({shown} of the candidates)</summary>"
            '<p class="muted">In <code>crossarm_mapping.json</code>, under <code>"external_routines"</code>, put these'
            " entries in place of theirs (<code>\"program\": null</code>). The program names are suggestions: name the TP"
            " or KAREL programs you write.</p>"
            f'<pre class="snip"><code>{_e(action.snippet)}</code></pre>'
            '<p class="js-only"><button type="button" class="copy">Copy</button> <span class="copied muted"'
            ' aria-live="polite"></span></p></details>'
        )  # fmt: skip
    return (f'<li><b>{inline(action.title)}</b><span class="how">: {inline(action.detail)}</span>'
            f'<span class="ameta">{" · ".join(meta)}</span>{snippet}</li>')  # fmt: skip


def _outlook(result: ConversionResult, shown: int = 4) -> str:
    """The TODO causes TP has nothing for, and those a later CrossArm version may help with: two short lines."""
    no_tp, later = outlook(result)
    lines = []
    for title, causes in ((triage.NO_TP_TITLE, no_tp), (triage.LATER_TITLE, later)):
        if causes:
            links = [f'<a href="{_e(todo_href(cause=c))}">{_e(c)}</a> ({n})' for c, n in causes[:shown]]
            more = f" and {len(causes) - shown} more" if len(causes) > shown else ""
            lines.append(f"<li><b>{_e(title)}</b>: {', '.join(links)}{more}</li>")
    return f'<ul class="outlook">{"".join(lines)}</ul>' if lines else ""


def _renumbering(result: ConversionResult, config: ConversionConfig | None) -> str:
    """The ways to bring the resources over their limit within the controller, as keys of the mapping file."""
    proposals = triage.renumbering(result, config or ConversionConfig())
    if not proposals:
        return ""
    items = "".join(
        f"<li><b>{_e(p.resource)}</b>: {inline(p.text)}"
        + (f' Edit: <code class="edit">{_e(json.dumps(p.edit))}</code>' if p.edit else "") + "</li>"
        for p in proposals
    )
    return ('<h3 class="renum">Proposed renumbering: keys to edit in <code>crossarm_mapping.json</code>, then convert'
            f' again with it</h3><ul class="renum">{items}</ul>')  # fmt: skip


def _analysis_section(result: ConversionResult, notice: list[str], anchors: set[tuple[str, int]],
                      targets: set[str], checklist_items: int, licence_note: list[str] = (),
                      config: ConversionConfig | None = None) -> Section:  # fmt: skip
    """The decision first, then what to do; every figure leads to its detail further down. `licence_note`: the
    evaluation copy's notice, right under the decision."""
    decision = verdict(result)
    coverage = result.coverage
    programs = len(result.programs)
    clean = result.clean_programs()
    warnings = sum(1 for note in result.notes if note.kind == "WARNING")
    shown = {info.program.name for info in result.programs}
    motion = next((share for share in coverage.shares if share.area == MOTION), None)
    # What is converted as plainly as what is left: (figure, label, class, link)
    stats = [
        (fmt_percent(coverage.percent) if coverage.total else "—",
         f"of the {coverage.total:,} RAPID instructions converted" if coverage.total else "no RAPID instruction",
         "good", ""),
        *([(fmt_percent(motion.percent), f"of the {motion.total:,} motion instructions converted", "good", "")]
          if motion else []),
        (f"{clean} / {programs}", "programs ready as is (no TODO)", "good", "#code"),
        (str(result.todo_count), f"TODO, {warnings} warning{'s' if warnings != 1 else ''}", "left", "#todo"),
    ]  # fmt: skip
    blocking = "".join(f"<li>{_e(cause)}</li>" for cause in sorted(analysis.BLOCKING))
    why = (f'<details class="why" data-depth="{DETAIL}"><summary>How this is decided</summary>'
           f'<p>{_e(analysis.explanation())}</p><ul class="cols">{blocking}</ul></details>')  # fmt: skip
    areas = "".join(
        f'<li title="{share.converted:,} of {share.total:,} converted"><span>{_e(share.area)}</span>'
        f'<span class="meter ok"><span style="width:{share.percent:g}%"></span></span>'
        f"<b>{_e(fmt_percent(share.percent))}</b></li>"
        for share in coverage.shares
    )

    def stat(value: str, label: str, kind: str, href: str) -> str:
        inner = f'<b class="{kind}">{_e(value)}</b><span>{_e(label)}</span>'
        return f'<a class="stat" href="{href}">{inner}</a>' if href else f"<div>{inner}</div>"

    body = [
        "<h2>Analysis</h2>",
        f'<div class="verdict lv-{decision.level.replace(" ", "-")}"><div class="vmain">',
        '<div class="vstats">' + "".join(stat(*s) for s in stats) + "</div>",
        f'<p class="decision"><span class="vtag">{_e(decision.level)}</span> {_e(decision.sentence)}</p>',
        f'<p class="rule">{_e(decision.rule)}</p>{why}'
        + (f'<p class="karel-use">{inline(analysis.karel_use(result))}</p>' if analysis.karel_use(result) else "")
        + "</div>",
        (f'<div class="vareas"><h3>Converted by area</h3><ul class="areas">{areas}</ul>'
         + (f'<p class="biz">{_e(business(result))}</p>' if business(result) else "") + "</div>" if areas else ""),
        "</div>",
        (f'<div class="licence-note">{markdown_body(chr(10).join(licence_note))}</div>' if licence_note else ""),
    ]  # fmt: skip

    actions = [_action(action, targets) for action in priority_actions(result, config)]
    causes = []
    for cause in top_causes(result):
        tag = ' <span class="tag todo">blocking</span>' if cause.blocking else ""
        example = cause.example
        causes.append(
            f'<li><span><a href="{_e(todo_href(cause=cause.category))}">{_e(cause.category)}</a>'
            f' <span class="fam">{_e(triage.family(cause.category))}</span>{tag}</span>'
            f'<span class="meter"><span style="width:{max(2, round(cause.share))}%"></span></span>'
            f'<b>{cause.count}</b><span class="muted">{cause.share:.0f} %</span>'
            f'<span class="ex">e.g. {_line_link(example.program, example.rapid_line, anchors, shown)}:'
            f" {inline(_short(example.message.split(' — `')[0]))}</span></li>"
        )
    causes_left = len({note.category for note in result.notes if note.kind == "TODO"}) - len(causes)
    grid = ['<div class="an-grid">']
    if actions:
        grid.append(f'<div class="an-box"><h3>What to do first</h3><ol class="actions">{"".join(actions)}</ol></div>')
    if causes:
        grid.append(
            '<div class="an-box"><h3>Where the TODO come from</h3><ul class="top">' + "".join(causes) + "</ul>"
            + (f'<p class="muted">{causes_left} other cause{"s" if causes_left > 1 else ""}: see'
               ' <a href="#todo">the items to review</a>.</p>' if causes_left > 0 else "")
            + _outlook(result) + "</div>"
        )  # fmt: skip
    grid.append("</div>")
    body.append("".join(grid))

    near = near_limit(result.capacity)
    if near:
        rows = "".join(
            f"<tr><td>{_e(c.resource)}</td><td>{c.used}</td><td>{'—' if c.limit is None else c.limit}</td>"
            f'<td class="{"over" if not c.fits else ""}">{_e(capacity_status(c))}</td></tr>'
            for c in near
        )
        body.append(
            '<div class="an-box" id="an-capacity"><h3>Controller capacity: near or over the limit</h3>'
            '<div class="table-wrap"><table><thead><tr><th>Resource</th><th>Used</th><th>Limit</th><th>Status</th>'
            f"</tr></thead><tbody>{rows}</tbody></table></div>{_renumbering(result, config)}"
            '<p class="muted">Every resource: <a href="#capacity">controller capacity</a> in the summary.</p></div>'
        )  # fmt: skip
    elif result.capacity:
        body.append('<p class="muted" id="an-capacity">Controller capacity: every resource well within its limit'
                    ' (<a href="#capacity">the figures</a>).</p>')  # fmt: skip
    links = [
        ("#taught", "Taught positions"),
        ("#ck-fold", f"The commissioning checklist ({checklist_items} items)"),
        ("#review", f"Items to review ({counts_text(result)})"),
        ("#code", "RAPID ↔ TP, program by program"),
        ("#points", "Points, program by program"),
        ("#summary", "Summary figures"),
        ("#details", "Details: frames, registers, speeds"),
    ]
    body.append('<p class="go">' + " · ".join(f'<a href="{href}">{_e(text)}</a>' for href, text in links
                                              if href[1:] in targets) + "</p>")  # fmt: skip
    body.append(f'<div class="notice">{markdown_body(chr(10).join(notice))}</div>')
    return "analysis", "Analysis", "\n".join(body)


# ---------------------------------------------------------------------------
# The line kept at the top: where things stand, the menu, the view
# ---------------------------------------------------------------------------


def _cockpit(result: ConversionResult, config: ConversionConfig, menu: list[tuple[str, str]]) -> str:
    """Verdict · % converted · TODO · blocking causes · points to touch up · version and date; then the menu."""
    decision = verdict(result)
    coverage = result.coverage
    points, kept, again = touch_up_counts(result)
    touch = points - kept
    blocking = len(decision.blocking)
    level = decision.level.replace(" ", "-")
    parts = [
        f'<span class="vtag lv-{_e(level)}">{_e(decision.level)}</span>',
        (f'<span><b>{_e(fmt_percent(coverage.percent))}</b> converted</span>' if coverage.total
         else '<span class="muted">nothing to convert</span>'),
        f'<a href="#todo"><b>{result.todo_count:,}</b> TODO</a>',
        f'<a href="#analysis"><b>{blocking}</b> blocking cause{"" if blocking == 1 else "s"}</a>',
        (f'<a href="#points"><b>{touch:,}</b> point{"" if touch == 1 else "s"} to touch up'
         + (f" ({again} again)" if again else "") + "</a>" if points else ""),
    ]  # fmt: skip
    views = "".join(f'<option value="{v}">{_e(label)}</option>' for v, label in VIEWS)
    line = " <span class=\"dot\">·</span> ".join(p for p in parts if p)
    return (
        '<div class="cockpit" id="cockpit">'
        f'<div class="cline">{line}'
        f'<span class="ver">CrossArm {_e(__version__)} · {config.timestamp:%Y-%m-%d %H:%M}</span>'
        '<label class="view js-only-inline">View <select id="depth" aria-label="View: how much the page opens">'
        f"{views}</select></label></div>"
        '<nav class="menu" aria-label="Sections">'
        + "".join(f'<a href="{_e(href)}">{_e(label)}</a>' for href, label in menu)
        + "</nav></div>"
    )  # fmt: skip


# ---------------------------------------------------------------------------
# Summary, details, page
# ---------------------------------------------------------------------------


def _summary_section(result: ConversionResult, summary: list[str]) -> Section:
    warnings = sum(1 for note in result.notes if note.kind == "WARNING")
    coverage = result.coverage
    cards = [
        (f"{result.clean_programs()} / {len(result.programs)}", "programs with no TODO"),
        *([(fmt_percent(coverage.percent), f"of {coverage.total:,} RAPID instructions converted")]
          if coverage.total else []),
        (str(result.todo_count), "TODO, not converted"),
        (str(warnings), "warnings, converted on an assumption"),
    ]  # fmt: skip
    body = ["<h2>Summary</h2>", '<div class="cards">' + "".join(
        f'<div class="card"><b>{_e(value)}</b><span>{_e(label)}</span></div>' for value, label in cards) + "</div>"]
    groups = result.grouped("TODO")
    if groups:
        top = groups[0][1]
        bars = "".join(
            f'<li><a href="{_e(todo_href(cause=category))}">{_e(category)}</a>'
            f'<span class="meter"><span style="width:{max(2, round(count * 100 / top))}%"></span></span>'
            f"<b>{count}</b></li>"
            for category, count, _ in groups
        )
        body += ["<h3>TODO by cause</h3>", f'<ul class="causes">{bars}</ul>']
    # The Markdown summary as it is, without its heading: the counts again, coverage by area, assumptions...
    if summary and summary[0].startswith("## "):
        summary = summary[1:]
    body.append(markdown_body("\n".join(summary), {"Controller capacity": "capacity"}))
    return "summary", "Summary", "\n".join(body)


_KAREL_HEADING = "KAREL programs (--karel)"


def _details_section(parts: dict[str, list[str]], extra: str) -> Section:
    keys = ("programs", "frames", "registers", "motion")  # the points have their own section
    markdown = "\n".join(line for key in keys for line in parts.get(key, ())) + "\n" + extra
    ids = {"Programs to provide": "provided", _KAREL_HEADING: "karel"}
    return "details", "Details", "<h2>Details</h2>\n" + markdown_body(markdown, ids)


def _short(text: str, width: int = 110) -> str:
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


_SOURCES_SHOWN = 6


def _header(head: list[str], sources: list[str]) -> str:
    """The head of the Markdown report, compact: on a large backup its list of sources is folded."""
    many = len(sources) > _SOURCES_SHOWN
    if many:
        short = ", ".join(f"`{s}`" for s in sources[:3]) + f" and {len(sources) - 3} more"
        head = [f"- Sources: {short}" if line.startswith("- Sources: ") else line for line in head]
    html_head = markdown_body("\n".join(head))
    if many:
        every = ", ".join(f"<code>{_e(s)}</code>" for s in sources)
        html_head += (f'\n<details class="srcs" data-depth="{DETAIL}"><summary>Every source file ({len(sources)})'
                      f"</summary><p>{every}</p></details>")  # fmt: skip
    return html_head


_CSS = """
:root { --row: #fafbfc; --todo-bg: #fff1e5; --warn-bg: #fff8db; --ok: #1a7f37; --mark: #8250df; --bad: #cf222e;
  --stick: 92px; }
@media (prefers-color-scheme: dark) {
  :root { --row: #11161d; --todo-bg: #3a2414; --warn-bg: #33290f; --ok: #3fb950; --mark: #a371f7; --bad: #f85149; }
}
main { max-width: 1400px; padding-top: 14px; }
header.top h1 { margin: 0 0 .15em; font-size: 1.5em; padding-bottom: .15em; }
header.top ul { list-style: none; padding: 0; margin: .2em 0 .4em; display: flex; flex-wrap: wrap; gap: 0 1.5em;
  color: var(--muted); font-size: .88em; }
header.top blockquote { margin: .4em 0; padding: .35em .9em; font-size: .92em; }
details.srcs { font-size: .85em; color: var(--muted); margin: 0 0 .4em; }
.licence-note blockquote { margin: -.4em 0 1em; padding: .35em .9em; font-size: .92em; }
.verdict .karel-use { font-size: .9em; margin: .3em 0 0; }
details.srcs summary { cursor: pointer; }
p.nojs { border: 1px solid var(--warn); border-radius: 8px; padding: 8px 14px; background: var(--warn-bg); }
.cockpit { position: sticky; top: 0; z-index: 3; background: var(--bg); border-bottom: 1px solid var(--line);
  padding: 6px 0 2px; }
.cline { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; }
.cline a { text-decoration: none; color: var(--fg); }
.cline a:hover b { text-decoration: underline; }
.cline .dot { color: var(--muted); }
.cline .ver { margin-left: auto; color: var(--muted); font-size: .85em; }
.cline .vtag { vertical-align: 0; }
.vtag.lv-ready { background: var(--ok); } .vtag.lv-workable { background: var(--warn); }
.vtag.lv-not-ready { background: var(--bad); }
label.view { font-size: .88em; color: var(--muted); }
label.view select { font: inherit; color: var(--fg); background: var(--bg); border: 1px solid var(--line);
  border-radius: 6px; padding: 2px 6px; }
#analysis > h2 { margin: .5em 0 0; font-size: 1.2em; border-bottom: 0; }
.verdict { display: grid; grid-template-columns: minmax(0, 3fr) minmax(260px, 2fr); gap: 8px 28px;
  border: 1px solid var(--line); border-left: 6px solid var(--muted); border-radius: 8px; padding: 12px 18px;
  background: var(--head); margin: .6em 0 1em; }
.lv-ready { border-left-color: var(--ok); } .lv-workable { border-left-color: var(--warn); }
.lv-not-ready { border-left-color: var(--bad); }
.vstats { display: flex; flex-wrap: wrap; gap: 6px 28px; }
.vstats > * { display: block; color: inherit; text-decoration: none; }
.vstats b { display: block; font-size: 1.7em; line-height: 1.15; }
.vstats b.good { color: var(--ok); } .vstats b.left { color: var(--todo); }
.vstats span { color: var(--muted); font-size: .88em; }
a.stat:hover span { text-decoration: underline; }
p.decision { font-size: 1.12em; font-weight: 600; margin: .6em 0 .2em; }
.vtag { display: inline-block; text-transform: uppercase; font-size: .72em; letter-spacing: .04em; font-weight: 700;
  padding: .1em .55em; border-radius: 4px; color: #fff; background: var(--muted); vertical-align: .12em; }
.lv-ready .vtag { background: var(--ok); } .lv-workable .vtag { background: var(--warn); }
.lv-not-ready .vtag { background: var(--bad); }
@media (prefers-color-scheme: dark) { .vtag { color: #0d1117; } }
p.rule { font-size: .86em; color: var(--muted); margin: .2em 0; }
details.why { font-size: .86em; color: var(--muted); }
details.why summary { cursor: pointer; }
ul.cols { columns: 2 16em; margin: .2em 0; }
.vareas h3, .an-box h3 { margin: 0 0 .4em; font-size: 1em; }
ul.areas { list-style: none; padding: 0; margin: 0; }
ul.areas li { display: grid; grid-template-columns: 9.5em 1fr 4em; gap: 8px; align-items: center; font-size: .9em; }
ul.areas b { text-align: right; font-weight: 600; }
.meter.ok span { background: var(--ok); }
.an-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; margin: 0 0 1em; }
.an-box { border: 1px solid var(--line); border-radius: 8px; padding: 10px 16px; }
ol.actions { margin: 0; padding-left: 1.4em; }
ol.actions li { margin: 0 0 .45em; }
a.more { white-space: nowrap; font-size: .9em; }
ol.actions .how { color: var(--muted); font-size: .94em; }
.ameta { display: block; font-size: .84em; color: var(--muted); margin-top: 1px; }
.ameta a.n, .ameta b.n { font-weight: 600; }
.tag.cos { color: var(--muted); font-weight: 600; }
.fam { font-size: .74em; color: var(--muted); border: 1px solid var(--line); border-radius: 9px; padding: 0 .45em;
  white-space: nowrap; vertical-align: .1em; }
p.biz { margin: .55em 0 0; font-size: .9em; font-weight: 600; }
ul.outlook { list-style: none; padding: 0; margin: .5em 0 0; font-size: .86em; }
ul.outlook li { margin: .2em 0; }
details.ext { font-size: .9em; margin: .15em 0 .2em; }
details.ext summary { cursor: pointer; color: var(--accent); }
details.ext p { margin: .3em 0; }
pre.snip { margin: .3em 0; padding: 6px 10px; overflow-x: auto; font-size: .9em; }
button.copy { font: inherit; padding: 2px 12px; color: var(--fg); background: var(--head); border: 1px solid var(--line);
  border-radius: 6px; cursor: pointer; }
h3.renum { font-size: .95em; margin: .8em 0 .3em; }
ul.renum { margin: 0 0 .4em; padding-left: 1.2em; font-size: .9em; }
code.edit { white-space: nowrap; }
ul.top { list-style: none; padding: 0; margin: 0; }
ul.top li { display: grid; grid-template-columns: minmax(0, 1fr) 80px 2.6em 3em; gap: 2px 10px; align-items: center;
  padding: 3px 0; border-bottom: 1px solid var(--line); }
ul.top li > b, ul.top li > .muted { text-align: right; }
ul.top .ex { grid-column: 1 / -1; font-size: .84em; color: var(--muted); overflow-wrap: anywhere; }
td.over { color: var(--bad); font-weight: 600; }
p.go { margin: .4em 0 1em; }
.notice blockquote { font-size: .88em; }
details.sec { border: 1px solid var(--line); border-radius: 8px; margin: 10px 0; padding: 0 16px 8px; }
details.sec:not([open]) { padding-bottom: 0; }
details.sec > summary { cursor: pointer; list-style: none; display: flex; flex-wrap: wrap; align-items: baseline;
  gap: 2px 14px; margin: 0 -16px; padding: 9px 16px; border-radius: 8px; background: var(--head); }
details.sec > summary::-webkit-details-marker { display: none; }
details.sec > summary::before { content: "\\25B8"; color: var(--accent); width: .8em; margin-right: -6px;
  font-size: 1.25em; line-height: 1; }
details.sec[open] > summary::before { content: "\\25BE"; }
details.sec[open] > summary { border-bottom: 1px solid var(--line); border-radius: 8px 8px 0 0; margin-bottom: 8px; }
details.sec > summary h2 { margin: 0; padding: 0; border: 0; font-size: 1.12em; }
.sline { color: var(--muted); font-size: .92em; }
.sline b { color: var(--fg); }
p.ready { margin: .6em 0; }
#p-box:not(.show-ready) [data-ready] { display: none; }
details.pts { border-bottom: 1px solid var(--line); }
details.pts > summary { cursor: pointer; padding: 5px 4px; }
details.pts > summary b { margin: 0 .6em; }
table.points td.v { font: .9em ui-monospace, Consolas, "Courier New", monospace; white-space: nowrap; }
p.more { margin: .4em 0 1em; }
p.more button { font: inherit; padding: 4px 14px; color: var(--fg); background: var(--head);
  border: 1px solid var(--line); border-radius: 6px; cursor: pointer; }
@media (max-width: 760px) { .verdict { grid-template-columns: 1fr; } .an-grid { grid-template-columns: 1fr; }
  .cline .ver { margin-left: 0; } }
nav.menu { display: flex; flex-wrap: wrap; gap: 2px 18px; padding: 4px 0 2px; }
nav.menu a { color: var(--accent); text-decoration: none; font-weight: 600; font-size: .95em; }
section { scroll-margin-top: var(--stick); }
[id] { scroll-margin-top: calc(var(--stick) + 8px); }
a { color: var(--accent); }
table.review th { white-space: nowrap; }
.js-only, .js-only-inline { display: none !important; }
.js .js-only { display: flex !important; }
.js .js-only-inline { display: inline-block !important; }
.bar { flex-wrap: wrap; gap: 8px; align-items: center; margin: .6em 0; }
.bar input[type=search] { min-width: 16em; }
.bar input, .bar select, .bar button, p.ready button { font: inherit; font-size: .92em; padding: 4px 8px;
  color: var(--fg); background: var(--bg); border: 1px solid var(--line); border-radius: 6px; }
.bar button, p.ready button { cursor: pointer; background: var(--head); }
.cards { display: flex; flex-wrap: wrap; gap: 12px; margin: 1em 0; }
.card { border: 1px solid var(--line); border-radius: 8px; padding: 10px 16px; min-width: 150px; background: var(--head); }
.card b { display: block; font-size: 1.6em; line-height: 1.2; }
.card span { color: var(--muted); font-size: .9em; }
ul.causes { list-style: none; padding: 0; margin: .5em 0 1.5em; max-width: 900px; }
ul.causes li { display: grid; grid-template-columns: minmax(12em, 24em) 1fr 3.5em; gap: 10px; align-items: center;
  padding: 2px 0; }
ul.causes b { text-align: right; }
.meter { height: 10px; background: var(--code); border-radius: 5px; overflow: hidden; }
.meter span { display: block; height: 100%; background: var(--todo); }
.tag { display: inline-block; font-size: .78em; font-weight: 700; padding: 0 .5em; border-radius: 9px;
  border: 1px solid currentColor; white-space: nowrap; }
.tag.todo { color: var(--todo); } .tag.warn { color: var(--warn); } .tag.ok { color: var(--ok); }
.cause { font-weight: 600; }
details.prog { border: 1px solid var(--line); border-radius: 8px; margin: 8px 0; }
details.prog > summary { cursor: pointer; padding: 6px 10px; background: var(--head); border-radius: 8px; }
details.prog[open] > summary { border-bottom: 1px solid var(--line); border-radius: 8px 8px 0 0; }
.pn { font-weight: 700; font-family: ui-monospace, Consolas, "Courier New", monospace; }
table.sbs { table-layout: fixed; border: 0; font-size: .86em; }
table.sbs.loose { margin-bottom: 4px; }
table.sbs col.cn { width: 3.6em; } table.sbs col.cc { width: 50%; }
table.sbs th { position: sticky; top: var(--stick); z-index: 1; }
table.sbs td { border: 0; border-bottom: 1px solid var(--line); padding: 1px 6px; }
table.sbs td.n { color: var(--muted); text-align: right; white-space: pre; user-select: none;
  font: .95em ui-monospace, Consolas, "Courier New", monospace; }
table.sbs td.c { white-space: pre-wrap; overflow-wrap: anywhere;
  font: .95em ui-monospace, Consolas, "Courier New", monospace; }
table.sbs tr.todo td { background: var(--todo-bg); }
table.sbs tr.warn td { background: var(--warn-bg); }
table.sbs tr.note td { font-size: .95em; padding: 3px 8px 5px; }
table.sbs tr.note.todo td { background: var(--todo-bg); }
table.sbs tr.note.warn td { background: var(--warn-bg); }
table.sbs td.up { color: var(--muted); }
table.sbs tr.mark td.c { color: var(--mark); }
tr.flash td { animation: flash 2s ease-out; }
@keyframes flash { from { background: var(--accent); } }
@media print {
  :root { --bg: #fff; --fg: #000; --muted: #555; --line: #bbb; --head: #f2f2f2; --code: #eee; --todo: #a04a00;
          --warn: #6b4300; --todo-bg: #fff1e5; --warn-bg: #fff8db; --accent: #000; --ok: #1a7f37; }
  .cockpit { position: static; border-bottom: 1px solid var(--line); }
  nav.menu, .bar, .js .bar, label.view, .js label.view, p.more, p.ready button, .js p.ready button,
  button.copy { display: none !important; }
  main { max-width: none; padding: 0; }
  table.sbs th { position: static; }
  tr, .card, .verdict, ol.actions li, ul.top li, details.sec > summary { break-inside: avoid; }
  .vtag { color: #fff; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
"""

_JS = r"""
(function () {
  var d = document, root = d.documentElement;
  root.classList.add('js');
  function $(id) { return d.getElementById(id); }
  function each(list, fn) { Array.prototype.forEach.call(list, fn); }

  // Lazy blocks: a long list waits, inert, in a <template data-lazy> until the fold holding it is opened.
  function owner(t) { return t.parentElement ? t.parentElement.closest('details') : null; }
  function buildIn(el) {
    var n = 0;
    each(el.querySelectorAll('template[data-lazy]'), function (t) {
      if (owner(t) === el) { t.parentNode.replaceChild(t.content, t); n++; }
    });
    if (n) { el.dispatchEvent(new CustomEvent('crossarm:built', {bubbles: true})); }
  }
  function open(el) { buildIn(el); el.open = true; }
  d.addEventListener('toggle', function (ev) { if (ev.target.open) { buildIn(ev.target); } }, true);
  function openTo(el) { for (var p = el; p; p = p.parentElement) { if (p.tagName === 'DETAILS' && !p.open) { open(p); } } }
  function holds(frag, id) {
    if (frag.getElementById(id)) { return true; }
    var ts = frag.querySelectorAll('template[data-lazy]');
    for (var i = 0; i < ts.length; i++) { if (holds(ts[i].content, id)) { return true; } }
    return false;
  }
  function reveal(id) {  // builds the folds an id is in, outermost first
    for (var guard = 0; !$(id) && guard < 8; guard++) {
      var ts = d.querySelectorAll('template[data-lazy]'), hit = null;
      for (var i = 0; i < ts.length && !hit; i++) { if (holds(ts[i].content, id)) { hit = ts[i]; } }
      if (!hit) { return null; }
      var o = owner(hit);
      if (o) { openTo(o); } else { hit.parentNode.replaceChild(hit.content, hit); }
    }
    return $(id);
  }

  // The address: '#id' leads to it, opening what holds it; '#todo&cause=..&prog=..' opens the items filtered.
  function dec(s) { try { return decodeURIComponent(s); } catch (e) { return s; } }
  function where() {
    var raw = location.hash.slice(1).split('&'), q = {};
    for (var i = 1; i < raw.length; i++) {
      var k = raw[i].indexOf('=');
      if (k > 0) { q[raw[i].slice(0, k)] = dec(raw[i].slice(k + 1)); }
    }
    return {id: dec(raw[0]), q: q, filtered: raw.length > 1};
  }
  function go() {
    var h = where();
    if (!h.id) { return; }
    if (h.id === 'todo') { showReview(h.q); return; }
    var el = reveal(h.id);
    if (!el) { return; }
    if (el.tagName === 'SECTION') { var f = el.querySelector('details.sec'); if (f) { open(f); } }
    openTo(el);
    if (el.closest('[data-ready]') && $('p-box')) { ready(true); }
    el.scrollIntoView({block: el.tagName === 'TR' ? 'center' : 'start'});
    if (el.tagName === 'TR') { el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); }
  }
  window.addEventListener('hashchange', go);
  d.addEventListener('click', function (ev) {
    var a = ev.target.closest && ev.target.closest('a[href^="#"]');
    if (a && a.getAttribute('href') === location.hash) { setTimeout(go, 0); }
  });

  // Items to review: kind, cause, program and text; shown a page at a time.
  var R = null, PAGE = 50, limit = 0, TOTAL = {todo: 0, warn: 0};
  function any(sel, v) { return !sel || sel.split('|').indexOf(v) >= 0; }  // several causes or programs: '|'
  function reviewInit() {
    var t = $('f-rows');
    if (R || !t) { return; }
    PAGE = +t.getAttribute('data-page') || PAGE;
    R = [].slice.call(t.content.children);
    R.forEach(function (r) { r._text = r.textContent.toLowerCase(); if (r.dataset.k === 'TODO') { TOTAL.todo++; } else { TOTAL.warn++; } });
    ['f-text', 'f-kind', 'f-cause', 'f-prog'].forEach(function (id) { $(id).addEventListener('input', function () { review(); }); });
    $('f-reset').addEventListener('click', function () {
      ['f-text', 'f-cause', 'f-prog'].forEach(function (id) { $(id).value = ''; });
      $('f-kind').value = $('f-kind').getAttribute('data-default');
      review();
    });
    $('f-more').addEventListener('click', function () { review(true); });
    review();
  }
  function review(more) {
    if (!R) { return; }
    limit = more ? limit + PAGE : PAGE;
    var q = $('f-text').value.trim().toLowerCase(), k = $('f-kind').value, c = $('f-cause').value, p = $('f-prog').value;
    var match = R.filter(function (r) {
      return (!k || r.dataset.k === k) && any(c, r.dataset.c) && any(p, r.dataset.p) && (!q || r._text.indexOf(q) >= 0);
    });
    var body = $('f-body'), frag = d.createDocumentFragment(), shown = Math.min(limit, match.length);
    while (body.firstChild) { body.removeChild(body.firstChild); }
    match.slice(0, shown).forEach(function (r) { frag.appendChild(r); });
    body.appendChild(frag);
    var what = {TODO: ' TODO', WARNING: ' warnings'}[k] || ' items';
    $('f-count').textContent = shown + ' of ' + match.length + what + ' shown' + (match.length < R.length
      ? ' (in all: ' + TOTAL.todo + ' TODO + ' + TOTAL.warn + ' warning' + (TOTAL.warn === 1 ? '' : 's') + ')' : '');
    var left = match.length - shown, btn = $('f-more');
    btn.hidden = !left;
    btn.textContent = 'Show ' + Math.min(PAGE, left) + ' more (' + left + ' left)';
  }
  function choose(id, value) {  // a value with '|' (several causes or programs) gets an option of its own
    var s = $(id), ok = !value;
    each(s.querySelectorAll('option.several'), function (o) { if (o.value !== value) { s.removeChild(o); } });
    each(s.options, function (o) { if (o.value === value) { ok = true; } });
    if (!ok && value.indexOf('|') > 0) {
      var o = d.createElement('option'), parts = value.split('|');
      o.className = 'several'; o.value = value;
      o.textContent = id === 'f-prog' ? parts.length + ' programs: ' + parts.join(', ') : parts.join(' + ');
      s.appendChild(o); ok = true;
    }
    s.value = ok ? value : '';
  }
  function showReview(q) {
    var sec = $('review');
    if (!sec) { return; }
    var f = sec.querySelector('details.sec');
    if (f) { open(f); }
    reviewInit();
    if (R) {
      var k = {all: '', TODO: 'TODO', WARNING: 'WARNING'}[q.kind];
      $('f-kind').value = k === undefined ? $('f-kind').getAttribute('data-default') : k;
      choose('f-cause', q.cause || ''); choose('f-prog', q.prog || '');
      $('f-text').value = q.q || '';
      review();
    }
    sec.scrollIntoView({block: 'start'});
  }

  // Programs side by side: the ready ones on demand, a filter by name, expand or collapse.
  var P = null;
  function ready(on) {
    var box = $('p-box'), b = $('p-ready');
    if (!box) { return; }
    box.classList.toggle('show-ready', on);
    if (b) { b.textContent = on ? 'hide them' : 'show them'; }
  }
  function programsInit() {
    if (P || !$('p-text')) { return; }
    P = [].slice.call(d.querySelectorAll('#p-box details.prog, #p-box table.index tbody tr'));
    function programs() {
      var q = $('p-text').value.trim().toLowerCase(), n = 0;
      P.forEach(function (el) {
        var name = (el.dataset.p + ' ' + el.dataset.r).toLowerCase();
        el.hidden = !!q && name.indexOf(q) < 0;
        if (!el.hidden && el.tagName === 'DETAILS') { n++; }
      });
      $('p-count').textContent = q ? n + ' matching' : '';
      if (q) { ready(true); }
    }
    $('p-text').addEventListener('input', programs);
    if ($('p-ready')) { $('p-ready').addEventListener('click', function () { ready(!$('p-box').classList.contains('show-ready')); }); }
    $('p-open').addEventListener('click', function () {
      P.forEach(function (p) { if (p.tagName === 'DETAILS' && p.offsetParent !== null) { open(p); } });
    });
    $('p-close').addEventListener('click', function () { P.forEach(function (p) { p.open = false; }); });
  }

  // Points: one line per program, searched by program or RAPID target.
  var PT = null;
  function pointsInit() {
    if (PT || !$('pt-text')) { return; }
    PT = [].slice.call(d.querySelectorAll('#pt-box details.pts'));
    $('pt-text').addEventListener('input', function () {
      var q = this.value.trim().toLowerCase(), n = 0;
      PT.forEach(function (el) { el.hidden = !!q && el.dataset.s.indexOf(q) < 0; if (!el.hidden) { n++; } });
      $('pt-count').textContent = n + ' of ' + PT.length + ' programs';
    });
  }
  d.addEventListener('crossarm:built', function () { reviewInit(); programsInit(); pointsInit(); });

  // Copy: the example's text to the clipboard; where the browser refuses, selected, for Ctrl+C.
  d.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('button.copy');
    if (!b) { return; }
    var box = b.closest('details, li, div'), code = box && box.querySelector('pre code'), say = b.nextElementSibling;
    if (!code) { return; }
    function tell(t) { if (say) { say.textContent = t; } }
    function select() {
      try {
        var r = d.createRange(), sel = window.getSelection();
        r.selectNodeContents(code); sel.removeAllRanges(); sel.addRange(r);
        tell('Selected: press Ctrl+C to copy.');
      } catch (e) { tell('Select the text and copy it.'); }
    }
    var settled = false, late = null;
    function end(ok) { if (!settled) { settled = true; clearTimeout(late); if (ok) { tell('Copied.'); } else { select(); } } }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        late = setTimeout(function () { end(false); }, 800);  // a browser that neither copies nor refuses
        navigator.clipboard.writeText(code.textContent).then(function () { end(true); }, function () { end(false); });
      } else { end(false); }
    } catch (e) { end(false); }
  });

  // The view: synthesis, integrator or detail, each opening its own folds (data-depth). Kept in this browser.
  function view(v, quiet) {
    if (['s', 'i', 'd'].indexOf(v) < 0) { v = 's'; }
    each(d.querySelectorAll('[data-depth]'), function (el) {
      var on = el.getAttribute('data-depth').indexOf(v) >= 0;
      if (on && !el.open) { open(el); } else if (!on && el.open) { el.open = false; }
    });
    root.setAttribute('data-view', v);
    if ($('depth')) { $('depth').value = v; }
    if (!quiet) { try { window.localStorage.setItem('crossarm-view', v); } catch (e) { /* not kept */ } }
  }
  window.CrossArm = {open: open, reveal: reveal, view: view};
  function start() {
    each(d.querySelectorAll('details[open]'), buildIn);
    var v = 's';
    try { v = window.localStorage.getItem('crossarm-view') || 's'; } catch (e) { v = 's'; }
    view(v, true);
    if ($('depth')) { $('depth').addEventListener('change', function () { view(this.value); }); }
    go();
  }
  if (d.readyState === 'loading') { d.addEventListener('DOMContentLoaded', start); } else { setTimeout(start, 0); }
})();
"""

_NOJS = (f'<noscript><p class="nojs">This page\'s script is off in this browser: the analysis below is complete, the'
         " lists folded under it (checklist, items to review, programs, points, details) are shown by the script."
         f" Everything is also in <code>{_MARKDOWN_REPORT}</code>, written with this page.</p></noscript>")  # fmt: skip


def build_html_report(result: ConversionResult, config: ConversionConfig, sources: list[str],
                      licence: LicenceStatus | None = None, *, title: str, extra: str = "",
                      lead: list[str] | None = None, tp: TpExport | None = None, tp_where: str = "",
                      taught_where: str = "", karel: KarelExport | None = None, karel_where: str = "") -> str:  # fmt: skip
    """The page. `extra`: Markdown the pipeline adds to the report (the .TP export, syntax errors);
    `lead`: the lines the pipeline writes first in each program (the licence mark), numbered before the rest;
    `tp`: the .TP export when one was asked for, in `tp_where` (the TP folder, as the report names it);
    `taught_where`: the robot's programs read for --keep-taught (result.taught), as the report names them;
    `karel`: the KAREL programs written (--karel), in `karel_where`."""
    parts = dict(report_parts(result, config, sources, licence))
    # The evaluation copy's notice: under the decision, where everyone reading the report looks (the Markdown
    # report keeps it in its head).
    licence_note = [line for line in parts["head"] if line.startswith(EVALUATION_NOTICE)]
    parts["head"] = [line for line in parts["head"] if line not in licence_note]
    anchors: set[tuple[str, int]] = set()
    code = _code_section(result, lead or [], anchors)  # first: the review links to the lines it shows
    checklist = checklist_section(result, config, anchors, identity=f"{title}|{'|'.join(sources)}", tp=tp,
                                  tp_where=tp_where, karel=karel, karel_where=karel_where)  # fmt: skip
    review = _review_section(result, anchors)
    points = _points_section(result, anchors)
    todo, warnings = result.todo_count, sum(1 for note in result.notes if note.kind == "WARNING")
    with_todo = len({note.program for note in result.notes if note.kind == "TODO"} & {i.program.name for i in result.programs})
    ready = len(result.programs) - with_todo
    items = checklist[2].count("<li data-id=")
    groups = checklist[2].count('<div class="ckg"')
    key = re.search(r'<div id="ck" data-key="([0-9a-f]+)"', checklist[2])
    total_points, kept, again = touch_up_counts(result)

    sections = []
    taught = result.taught
    if taught is not None and (taught.points or taught.unread or taught.foreign):  # right after the analysis
        counts = taught.counts()
        line = (f"<b>{counts[AGAIN]}</b> to touch up again · <b>{counts[KEPT]}</b> kept as touched up · "
                f"{_s(len(taught.points), 'point')} compared")  # fmt: skip
        sections.append(_fold(taught_section(taught, result, taught_where, anchors), line, INTEGRATOR + DETAIL))
    sections.append(_fold(checklist, (
        f'<span id="ck-sum" data-key="{key[1] if key else ""}" data-total="{items}">{_s(items, "item")}</span>'
        f" in {_s(groups, 'group')}, in the order of the commissioning"), INTEGRATOR + DETAIL, fold_id="ck-fold"))
    sid, label, body = _fold(review, (f"<b>{todo:,}</b> TODO · <b>{warnings:,}</b> warning{'s' if warnings != 1 else ''},"
                                      f" {REVIEW_PAGE} at a time, by cause and program"), INTEGRATOR + DETAIL)
    sections.append((sid, label, '<span id="todo"></span>' + body))
    sections.append(_fold(code, (f"<b>{ready:,}</b> program{'s' if ready != 1 else ''} ready as is ·"
                                 f" <b>{with_todo:,}</b> with TODO"), INTEGRATOR + DETAIL))
    if points is not None:
        line = (f"<b>{total_points:,}</b> point{'s' if total_points != 1 else ''} in"
                f" {_s(sum(1 for i in result.programs if i.points), 'program')}"
                + (f" · {kept:,} kept as touched up" if kept else "") + (f" · {again:,} to touch up again" if again
                                                                         else ""))  # fmt: skip
        sections.append(_fold(points, line, DETAIL))
    sections.append(_fold(_summary_section(result, parts["summary"]),
                          "the figures, TODO by cause, assumptions, controller capacity", DETAIL))
    details_line = "programs, frames and tools, registers and I/O, speeds and zones"
    if _KAREL_HEADING in extra:
        details_line += ", KAREL programs"
    if extra.strip() and "Binary .TP programs" in extra:
        details_line += ", .TP export"
    sections.append(_fold(_details_section(parts, extra), details_line, DETAIL))
    # Last, but shown first: its links lead to what the other sections hold.
    targets = {sid for sid, _, _ in sections} | set(re.findall(r'\bid="([^"]+)"', "".join(b for _, _, b in sections)))
    sections.insert(0, _analysis_section(result, parts["notice"], anchors, targets, items, licence_note, config))

    menu = [("#analysis", "Analysis")]
    if result.capacity:
        menu.append(("#an-capacity", "Capacity"))
    for sid, label, _ in sections[1:]:
        if sid == "review":
            menu.append(("#todo", f"TODO ({todo:,})"))
        elif sid == "code":
            menu.append(("#code", "Programs"))
        elif sid != "details":
            menu.append((f"#{sid}", label))
    if "karel" in targets:
        menu.append(("#karel", "KAREL"))
    menu.append(("#details", "Details"))
    page = "\n".join(f'<section id="{_e(sid)}">\n{body}\n</section>' for sid, _, body in sections)
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_e(title)}</title>\n<style>{MARKDOWN_CSS}{_CSS}{CHECKLIST_CSS}{TAUGHT_CSS}</style>\n</head>\n<body><main>\n"
        f'<header class="top">\n{_header(parts["head"], sources)}\n</header>\n'
        f"{_cockpit(result, config, menu)}\n{_NOJS}\n{page}\n"
        f"</main>\n<script>{_JS}{CHECKLIST_JS}{TAUGHT_JS}</script>\n</body>\n</html>\n"
    )
