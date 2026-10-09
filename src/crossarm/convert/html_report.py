# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""ConversionResult -> crossarm_report.html, the report to work from on site.

One self-contained page: its style and script are in it, it loads nothing (cells are often offline) and
reads from file:// in any browser. Without its script every section is still there; the script adds the
filters, the search and the jumps from a TODO to its place.

    Analysis         the first screen: the decision and the rule it follows, what to do first, where the TODO
                     come from, the share converted by area, the controller resources near their limit
                     (crossarm.convert.analysis); the rest of the page is the detail behind it
    Taught positions with --keep-taught: what became of each point touched up on the robot, program by program
                     (crossarm.convert.taught_report)
    Summary          the figures, then the summary of the Markdown report
    Checklist        commissioning on the FANUC cell, in order, ticked off in the browser (crossarm.convert.checklist);
                     folded until opened
    Items to review  every TODO and warning, filtered by kind, cause and program, or searched
    RAPID and TP     each program, its RAPID routine and the TP written from it side by side, line by line
                     (crossarm.convert.source_map), the lines left TODO marked with their cause and why
    Details          the rest of the Markdown report: programs, frames, registers, speeds, points

Each section is one function returning (id, menu label, HTML); a new section is one more entry in
build_html_report. Every text from the backup is escaped.
"""

import html
import re
from collections import Counter, defaultdict

from crossarm.convert import analysis
from crossarm.convert.analysis import capacity_status, near_limit, priority_actions, top_causes, verdict
from crossarm.convert.checklist import CHECKLIST_CSS, CHECKLIST_JS, checklist_section
from crossarm.convert.config import ConversionConfig
from crossarm.convert.coverage import fmt_percent
from crossarm.convert.html import CSS as MARKDOWN_CSS
from crossarm.convert.html import inline, markdown_body
from crossarm.convert.report import EVALUATION_NOTICE, report_parts
from crossarm.convert.source_map import Row, line_anchor, side_by_side, tp_text
from crossarm.convert.taught_report import TAUGHT_CSS, TAUGHT_JS, taught_section
from crossarm.convert.translate import ConversionResult, Note, ProgramInfo
from crossarm.fanuc.ktrans import KarelExport
from crossarm.fanuc.maketp import TpExport
from crossarm.licence import LicenceStatus

Section = tuple[str, str, str]  # (id, menu label, HTML)

_END = re.compile(r"^\s*END(PROC|FUNC|TRAP)\b", re.IGNORECASE)


def _e(text: object) -> str:
    return html.escape(str(text), quote=True)


def routine_end(source: list[str], first: int) -> int:
    """The line of the ENDPROC (ENDFUNC, ENDTRAP) closing the routine starting at `first`."""
    for number in range(first, len(source) + 1):
        if _END.match(source[number - 1].split("!", 1)[0]):
            return number
    return len(source)


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
    todo, warnings = _counts(result.notes)
    notes: dict[str, list[Note]] = defaultdict(list)
    for note in result.notes:
        notes[note.program].append(note)
    index, views = [], []
    for info in result.programs:
        name = info.program.name
        routine = f"{info.module}.{info.routine}" if info.module else info.routine
        index.append(f'<tr data-p="{_e(name)}" data-r="{_e(routine)}" data-todo="{todo[name]}"><td><a href="#p-{_e(name)}">{_e(name)}.LS</a>'
                     f"</td><td>{_e(routine)}</td><td>{len(info.program.lines)}</td><td>{len(info.points)}</td>"
                     f"<td>{todo[name] or ''}</td><td>{warnings[name] or ''}</td></tr>")  # fmt: skip
        views.append(f'<details class="prog" id="p-{_e(name)}" data-p="{_e(name)}" data-r="{_e(routine)}"'
                     f' data-todo="{todo[name]}">'
                     f'<summary><span class="pn">{_e(name)}.LS</span> <span class="muted">{_e(routine)}</span>'
                     f"{_badges(todo[name], warnings[name])}</summary>"
                     f"{_program_view(info, result, notes[name], lead, anchors)}</details>")  # fmt: skip
    body = [
        "<h2>RAPID and TP side by side</h2>",
        ("<p>Each program as written in its <code>.LS</code> file, next to the RAPID routine it comes from: every"
        " RAPID line on the left, the TP lines written from it on the right (numbered as in the <code>.LS</code>)."
        " A TP line written further down for a RAPID line already shown (an <code>ENDIF</code>, a branch moved"
        " behind its <code>SELECT</code>) is marked ↑. Lines left TODO are marked, with their cause and why.</p>"),
        ('<div class="bar js-only"><input id="p-text" type="search" placeholder="Filter programs" aria-label="Filter'
        ' programs"> <label><input id="p-todo" type="checkbox"> with TODO only</label>'
        ' <button type="button" id="p-open">Expand all</button> <button type="button" id="p-close">Collapse all'
         "</button></div>"),
        '<div class="table-wrap"><table class="index"><thead><tr><th>TP program</th><th>RAPID routine</th>'
        "<th>Lines</th><th>Points</th><th>TODO</th><th>Warnings</th></tr></thead><tbody>"
        + "".join(index) + "</tbody></table></div>",
        *views,
    ]  # fmt: skip
    return "code", "RAPID and TP", "\n".join(body)


# ---------------------------------------------------------------------------
# Items to review
# ---------------------------------------------------------------------------


def _review_section(result: ConversionResult, anchors: set[tuple[str, int]]) -> Section:
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
    body = [
        "<h2>Items to review</h2>",
        ("<p>TODO: not converted, to write by hand. Warning: converted on an assumption, to check. The RAPID line"
         " leads to its place in the programs below.</p>"),
        ('<div class="bar js-only"><input id="f-text" type="search" placeholder="Search" aria-label="Search">'
        ' <select id="f-kind" aria-label="Kind"><option value="">TODO and warnings</option>'
        '<option value="TODO">TODO</option><option value="WARNING">Warnings</option></select>'
        f' <select id="f-cause" aria-label="Cause"><option value="">Every cause</option>{cause_options}</select>'
        f' <select id="f-prog" aria-label="Program"><option value="">Every program</option>{program_options}</select>'
        ' <button type="button" id="f-reset">Reset</button> <span id="f-count" class="muted"></span></div>'),
        '<div class="table-wrap"><table class="review"><thead><tr><th>Program</th><th>RAPID line</th><th>Kind</th>'
        "<th>Cause</th><th>Detail</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        if rows else '<p class="muted">None.</p>',
    ]  # fmt: skip
    return "review", f"Items to review ({len(rows)})", "\n".join(body)


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


def _analysis_section(result: ConversionResult, notice: list[str], anchors: set[tuple[str, int]],
                      targets: set[str], checklist_items: int, licence_note: list[str] = ()) -> Section:  # fmt: skip
    """The decision first, then what to do; every figure leads to its detail further down. `licence_note`: the
    evaluation copy's notice, right under the decision."""
    decision = verdict(result)
    coverage = result.coverage
    programs = len(result.programs)
    clean = result.clean_programs()
    warnings = sum(1 for note in result.notes if note.kind == "WARNING")
    shown = {info.program.name for info in result.programs}
    stats = [
        (fmt_percent(coverage.percent) if coverage.total else "—",
         f"of the {coverage.total:,} RAPID instructions converted" if coverage.total else "no RAPID instruction"),
        (f"{clean} / {programs}", f"programs with no TODO, {programs - clean} with TODO"),
        (str(result.todo_count), f"TODO, {warnings} warning{'s' if warnings != 1 else ''}"),
    ]  # fmt: skip
    blocking = "".join(f"<li>{_e(cause)}</li>" for cause in sorted(analysis.BLOCKING))
    why = (f'<details class="why"><summary>How this is decided</summary><p>{_e(analysis.explanation())}</p>'
           f'<ul class="cols">{blocking}</ul></details>')  # fmt: skip
    areas = "".join(
        f'<li title="{share.converted:,} of {share.total:,} converted"><span>{_e(share.area)}</span>'
        f'<span class="meter ok"><span style="width:{share.percent:g}%"></span></span>'
        f"<b>{_e(fmt_percent(share.percent))}</b></li>"
        for share in coverage.shares
    )
    body = [
        "<h2>Analysis</h2>",
        f'<div class="verdict lv-{decision.level.replace(" ", "-")}"><div class="vmain">',
        '<div class="vstats">' + "".join(f"<div><b>{_e(v)}</b><span>{_e(label)}</span></div>" for v, label in stats)
        + "</div>",
        f'<p class="decision"><span class="vtag">{_e(decision.level)}</span> {_e(decision.sentence)}</p>',
        f'<p class="rule">{_e(decision.rule)}</p>{why}'
        + (f'<p class="karel-use">{inline(analysis.karel_use(result))}</p>' if analysis.karel_use(result) else "")
        + "</div>",
        (f'<div class="vareas"><h3>Converted by area</h3><ul class="areas">{areas}</ul></div>' if areas else ""),
        "</div>",
        (f'<div class="licence-note">{markdown_body(chr(10).join(licence_note))}</div>' if licence_note else ""),
    ]  # fmt: skip

    actions = []
    for action in priority_actions(result):
        href = action.href if action.href[1:] in targets else "#details"
        cause = f' data-cause="{_e(action.cause)}"' if action.cause and href == "#review" else ""
        actions.append(f'<li><b>{inline(action.title)}</b><span class="how">: {inline(action.detail)}</span>'
                       f' <a class="more" href="{_e(href)}"{cause}>{_e(action.label)} →</a></li>')  # fmt: skip
    causes = []
    for cause in top_causes(result):
        tag = ' <span class="tag todo">blocking</span>' if cause.blocking else ""
        example = cause.example
        causes.append(
            f'<li><span><a href="#review" data-cause="{_e(cause.category)}">{_e(cause.category)}</a>{tag}</span>'
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
               ' <a href="#summary">the summary</a>.</p>' if causes_left > 0 else "")
            + "</div>"
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
            f"</tr></thead><tbody>{rows}</tbody></table></div>"
            '<p class="muted">Every resource: <a href="#capacity">controller capacity</a> in the summary.</p></div>'
        )  # fmt: skip
    elif result.capacity:
        body.append('<p class="muted" id="an-capacity">Controller capacity: every resource well within its limit'
                    ' (<a href="#capacity">the figures</a>).</p>')  # fmt: skip
    review = sum(1 for _ in result.notes)
    links = [
        ("#taught", "Taught positions"),
        ("#ck-fold", f"The commissioning checklist ({checklist_items} items)"),
        ("#review", f"Items to review ({review})"),
        ("#code", "RAPID ↔ TP, program by program"),
        ("#summary", "Summary figures"),
        ("#details", "Details: frames, registers, points"),
    ]
    body.append('<p class="go">' + " · ".join(f'<a href="{href}">{_e(text)}</a>' for href, text in links
                                              if href[1:] in targets) + "</p>")  # fmt: skip
    body.append(f'<div class="notice">{markdown_body(chr(10).join(notice))}</div>')
    return "analysis", "Analysis", "\n".join(body)


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
            f'<li><a href="#review" data-cause="{_e(category)}">{_e(category)}</a>'
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


def _details_section(parts: dict[str, list[str]], extra: str) -> Section:
    keys = ("programs", "frames", "registers", "motion", "points")
    markdown = "\n".join(line for key in keys for line in parts.get(key, ())) + "\n" + extra
    ids = {"Programs to provide": "provided"}
    return "details", "Details", markdown_body(markdown, ids)


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
        html_head += (f'\n<details class="srcs"><summary>Every source file ({len(sources)})</summary>'
                      f"<p>{every}</p></details>")  # fmt: skip
    return html_head


_CSS = """
:root { --row: #fafbfc; --todo-bg: #fff1e5; --warn-bg: #fff8db; --ok: #1a7f37; --mark: #8250df; --bad: #cf222e; }
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
#analysis > h2 { margin: .5em 0 0; font-size: 1.2em; border-bottom: 0; }
.verdict { display: grid; grid-template-columns: minmax(0, 3fr) minmax(260px, 2fr); gap: 8px 28px;
  border: 1px solid var(--line); border-left: 6px solid var(--muted); border-radius: 8px; padding: 12px 18px;
  background: var(--head); margin: .6em 0 1em; }
.lv-ready { border-left-color: var(--ok); } .lv-workable { border-left-color: var(--warn); }
.lv-not-ready { border-left-color: var(--bad); }
.vstats { display: flex; flex-wrap: wrap; gap: 6px 28px; }
.vstats b { display: block; font-size: 1.7em; line-height: 1.15; }
.vstats span { color: var(--muted); font-size: .88em; }
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
ul.top { list-style: none; padding: 0; margin: 0; }
ul.top li { display: grid; grid-template-columns: minmax(0, 1fr) 80px 2.6em 3em; gap: 2px 10px; align-items: center;
  padding: 3px 0; border-bottom: 1px solid var(--line); }
ul.top li > b, ul.top li > .muted { text-align: right; }
ul.top .ex { grid-column: 1 / -1; font-size: .84em; color: var(--muted); overflow-wrap: anywhere; }
td.over { color: var(--bad); font-weight: 600; }
p.go { margin: .4em 0 1em; }
.notice blockquote { font-size: .88em; }
details.fold > summary { cursor: pointer; font-weight: 600; color: var(--accent); padding: 6px 0; }
@media (max-width: 760px) { .verdict { grid-template-columns: 1fr; } .an-grid { grid-template-columns: 1fr; } }
nav.menu { position: sticky; top: 0; z-index: 2; background: var(--bg); border-bottom: 1px solid var(--line);
           padding: 8px 0; display: flex; flex-wrap: wrap; gap: 4px 18px; }
nav.menu a { color: var(--accent); text-decoration: none; font-weight: 600; }
section { scroll-margin-top: 48px; }
[id] { scroll-margin-top: 56px; }
a { color: var(--accent); }
table.review th { white-space: nowrap; }
.js-only { display: none; }
.js .js-only { display: flex; }
.bar { flex-wrap: wrap; gap: 8px; align-items: center; margin: .6em 0; }
.bar input[type=search] { min-width: 16em; }
.bar input, .bar select, .bar button { font: inherit; font-size: .92em; padding: 4px 8px; color: var(--fg);
  background: var(--bg); border: 1px solid var(--line); border-radius: 6px; }
.bar button { cursor: pointer; background: var(--head); }
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
table.sbs th { position: sticky; top: 40px; z-index: 1; }
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
          --warn: #6b4300; --todo-bg: #fff1e5; --warn-bg: #fff8db; --accent: #000; }
  nav.menu, .bar { display: none !important; }
  main { max-width: none; padding: 0; }
  table.sbs th { position: static; }
  tr, .card, .verdict, ol.actions li, ul.top li { break-inside: avoid; }
  .vtag { color: #fff; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
"""

_JS = r"""
(function () {
  var d = document;
  d.documentElement.classList.add('js');
  function $(id) { return d.getElementById(id); }
  function openTo(el) { for (var p = el; p; p = p.parentElement) { if (p.tagName === 'DETAILS') { p.open = true; } } }
  function go() {
    var id = decodeURIComponent(location.hash.slice(1)), el = id && $(id);
    if (!el) { return; }
    openTo(el);
    el.scrollIntoView({block: el.tagName === 'TR' ? 'center' : 'start'});
    if (el.tagName === 'TR') { el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); }
  }
  window.addEventListener('hashchange', go);
  d.addEventListener('click', function (ev) {
    var a = ev.target.closest && ev.target.closest('a[href^="#"]');
    if (!a) { return; }
    if (a.dataset.cause !== undefined && $('f-cause')) { $('f-cause').value = a.dataset.cause; $('f-kind').value = 'TODO'; review(); }
    if (a.dataset.prog !== undefined && $('f-prog')) {
      $('f-text').value = ''; $('f-cause').value = ''; $('f-kind').value = 'TODO'; $('f-prog').value = a.dataset.prog; review();
    }
    if (a.getAttribute('href') === location.hash) { setTimeout(go, 0); }
  });

  // Items to review: kind, cause, program and text.
  var rows = [].slice.call(d.querySelectorAll('table.review tbody tr'));
  rows.forEach(function (r) { r._text = r.textContent.toLowerCase(); });
  function review() {
    if (!$('f-text')) { return; }
    var q = $('f-text').value.trim().toLowerCase(), k = $('f-kind').value, c = $('f-cause').value, p = $('f-prog').value;
    var shown = 0;
    rows.forEach(function (r) {
      var ok = (!k || r.dataset.k === k) && (!c || r.dataset.c === c) && (!p || r.dataset.p === p) && (!q || r._text.indexOf(q) >= 0);
      r.hidden = !ok;
      if (ok) { shown++; }
    });
    $('f-count').textContent = shown + ' of ' + rows.length + ' shown';
  }
  ['f-text', 'f-kind', 'f-cause', 'f-prog'].forEach(function (id) { if ($(id)) { $(id).addEventListener('input', review); } });
  if ($('f-reset')) {
    $('f-reset').addEventListener('click', function () {
      ['f-text', 'f-kind', 'f-cause', 'f-prog'].forEach(function (id) { $(id).value = ''; });
      review();
    });
  }

  // Programs side by side: filter by name, TODO only, expand or collapse.
  var progs = [].slice.call(d.querySelectorAll('details.prog')), index = [].slice.call(d.querySelectorAll('table.index tbody tr'));
  function programs() {
    if (!$('p-text')) { return; }
    var q = $('p-text').value.trim().toLowerCase(), todo = $('p-todo').checked;
    progs.concat(index).forEach(function (el) {
      var name = (el.dataset.p + ' ' + el.dataset.r).toLowerCase();
      el.hidden = (todo && el.dataset.todo === '0') || (q && name.indexOf(q) < 0);
    });
  }
  if ($('p-text')) {
    $('p-text').addEventListener('input', programs);
    $('p-todo').addEventListener('change', programs);
    $('p-open').addEventListener('click', function () { progs.forEach(function (p) { if (!p.hidden) { p.open = true; } }); });
    $('p-close').addEventListener('click', function () { progs.forEach(function (p) { p.open = false; }); });
  }
  review();
  go();
})();
"""


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
    sections = [
        _summary_section(result, parts["summary"]),
        checklist,
        _review_section(result, anchors),
        code,
        _details_section(parts, extra),
    ]
    taught = result.taught
    if taught is not None and (taught.points or taught.unread or taught.foreign):  # right after the analysis
        sections.insert(0, taught_section(result.taught, result, taught_where, anchors))
    # Last, but shown first: its links lead to what the other sections hold.
    targets = {sid for sid, _, _ in sections} | set(re.findall(r'\bid="([^"]+)"', "".join(b for _, _, b in sections)))
    items = checklist[2].count("<li data-id=")
    sections.insert(0, _analysis_section(result, parts["notice"], anchors, targets, items, licence_note))
    menu = "".join(f'<a href="#{_e(sid)}">{_e(label)}</a>' for sid, label, _ in sections)
    page = "\n".join(f'<section id="{_e(sid)}">\n{body}\n</section>' for sid, _, body in sections)
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_e(title)}</title>\n<style>{MARKDOWN_CSS}{_CSS}{CHECKLIST_CSS}{TAUGHT_CSS}</style>\n</head>\n<body><main>\n"
        f'<header class="top">\n{_header(parts["head"], sources)}\n</header>\n'
        f'<nav class="menu" aria-label="Sections">{menu}</nav>\n{page}\n'
        f"</main>\n<script>{_JS}{CHECKLIST_JS}{TAUGHT_JS}</script>\n</body>\n</html>\n"
    )
