# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The taught positions section of crossarm_report.html (crossarm convert --keep-taught, crossarm.convert.taught).

What became of each point touched up on the robot: the counts first (each one a filter), then one folded table per
program, a row per point: its P[n], the RAPID point it comes from, its status, how far the taught point is from the
theoretical one, why, and a link to its RAPID line in the side-by-side view. On a large backup most points are
theoretical as before: by default only the others are shown (kept, to touch up again, new, gone, not compared), and
only the first programs with points to touch up again are open. Then the programs not read on the robot and the
positions the robot holds that CrossArm did not write (the new programs do not have them).

Without the script every row is there, folded by program.
"""

import html

from crossarm.convert.source_map import line_anchor
from crossarm.convert.taught import (
    AGAIN,
    GONE,
    KEPT,
    NEW,
    NOT_READ,
    RULE,
    THEORETICAL,
    Taught,
    TaughtPoint,
    foreign_by_program,
)
from crossarm.convert.translate import ConversionResult

# The order shown, and how each status is named on the page.
ORDER = (AGAIN, KEPT, NEW, THEORETICAL, GONE, NOT_READ)
LABELS = {
    AGAIN: "to touch up again",
    KEPT: "kept as touched up",
    NEW: "new, to touch up",
    THEORETICAL: "theoretical as before",
    GONE: "gone from the backup",
    NOT_READ: "not compared",
}
HINTS = {
    AGAIN: "touched up on the robot, but the ABB point or its frame changed: the new theoretical value is written",
    KEPT: "touched up on the robot and unchanged in the backup: the program holds the taught value, check only",
    NEW: "not in the earlier conversion: theoretical, to touch up",
    THEORETICAL: "not touched up on the robot: theoretical, as before",
    GONE: "in the earlier conversion, no longer in the backup's programs",
    NOT_READ: "their program, or the P[n], not read on the robot: theoretical",
}
SLUG = {AGAIN: "again", KEPT: "kept", NEW: "new", THEORETICAL: "theo", GONE: "gone", NOT_READ: "unread"}
OPEN_PROGRAMS = 5  # programs with points to touch up again shown open; the others folded
FOREIGN_SHOWN = 40  # P[n] named per program


def _e(text: object) -> str:
    return html.escape(str(text), quote=True)


def _line(point: TaughtPoint, lines: dict[tuple[str, int], int], anchors: set[tuple[str, int]], shown: set[str]) -> str:
    line = lines.get((point.program, point.number)) if point.number is not None else None
    if line and (point.program, line) in anchors:
        return f'<a href="#{_e(line_anchor(point.program, line))}">l.{line}</a>'
    if point.number is not None and point.program in shown:
        return f'<a href="#p-{_e(point.program)}">{f"l.{line}" if line else "program"}</a>'
    return "—"


def _row(point: TaughtPoint, lines: dict[tuple[str, int], int], anchors: set[tuple[str, int]], shown: set[str]) -> str:
    slug = SLUG[point.status]
    deviation = point.deviation() if point.status in (KEPT, AGAIN) else ""
    return (f'<tr class="st-{slug}" data-s="{_e(point.status)}"><td class="pt">{_e(point.where)}</td>'
            f"<td><code>{_e(point.rapid)}</code></td>"
            f'<td><span class="tag {slug}" title="{_e(HINTS[point.status])}">{_e(LABELS[point.status])}</span></td>'
            f'<td class="dev">{_e(deviation or "—")}</td><td>{_e(point.why)}</td>'
            f"<td>{_line(point, lines, anchors, shown)}</td></tr>")  # fmt: skip


def taught_section(taught: Taught, result: ConversionResult, where: str,
                   anchors: set[tuple[str, int]]) -> tuple[str, str, str]:  # fmt: skip
    """The section of the page: (id, menu label, HTML). `where`: the robot's programs, as the report names them;
    `anchors`: the RAPID lines the page shows (links lead there)."""
    counts = taught.counts()
    lines = {(info.program.name, p.number): p.rapid_line for info in result.programs for p in info.points}
    shown = {info.program.name for info in result.programs}
    cards = "".join(
        f'<button type="button" class="tcard st-{SLUG[s]}{" zero" if not counts[s] else ""}" data-status="{_e(s)}"'
        f' title="{_e(HINTS[s])}"><b>{counts[s]}</b><span>{_e(LABELS[s])}</span></button>'
        for s in ORDER
    )
    options = "".join(f'<option value="{_e(s)}">{_e(LABELS[s])} ({counts[s]})</option>' for s in ORDER)
    body = [
        "<h2>Taught positions</h2>",
        (f"<p>What became of the points touched up on the robot. {_e(RULE)} The distance is the taught point's from"
         " the theoretical one this conversion writes.</p>"),
        (f'<p class="tfrom">Earlier conversion: <code>{_e(taught.earlier)}</code><br>Programs on the robot:'
         f" {_e(where.replace('`', ''))}</p>"),
        f'<div class="tcards">{cards}</div>',
        ('<div class="bar js-only"><input id="t-text" type="search" placeholder="Filter points or programs"'
         ' aria-label="Filter points or programs"> <select id="t-status" aria-label="Status">'
         '<option value="look">All but theoretical as before</option><option value="">Every status</option>'
         f'{options}</select> <button type="button" id="t-open">Expand all</button>'
         ' <button type="button" id="t-close">Collapse all</button> <span id="t-count" class="muted"></span></div>'),
    ]  # fmt: skip
    if taught.arrays:
        body.append(f'<p class="muted">{taught.arrays} points of arrays kept in position registers are not compared:'
                    " SETUP_FRAMES sets their theoretical values again.</p>")  # fmt: skip
    by_program: dict[str, list[TaughtPoint]] = {}
    for point in taught.points:
        by_program.setdefault(point.program, []).append(point)
    opened = 0
    head = ('<colgroup><col class="c-pt"><col class="c-rp"><col class="c-st"><col class="c-dev"><col><col class="c-ln">'
            "</colgroup><thead><tr><th>Point</th><th>RAPID point</th><th>Status</th><th>Taught vs theoretical</th>"
            "<th>Why</th><th>RAPID line</th></tr></thead>")  # fmt: skip
    for name, points in by_program.items():
        here = {s: sum(1 for p in points if p.status == s) for s in ORDER}
        badges = "".join(f' <span class="tag {SLUG[s]}">{here[s]} {_e(LABELS[s])}</span>' for s in ORDER
                         if here[s] and s != THEORETICAL)  # fmt: skip
        if here[THEORETICAL]:
            badges += f' <span class="muted">{here[THEORETICAL]} theoretical</span>'
        is_open = bool(here[AGAIN]) and opened < OPEN_PROGRAMS
        opened += is_open
        rows = "".join(_row(p, lines, anchors, shown) for p in points)
        body.append(f'<details class="tprog" data-p="{_e(name)}"{" open" if is_open else ""}><summary>'
                    f'<span class="pn">{_e(name)}.LS</span>{badges}</summary><div class="table-wrap">'
                    f'<table class="taught">{head}<tbody>{rows}</tbody></table></div></details>')  # fmt: skip
    body.append('<p id="t-none" class="muted" hidden>Nothing but points theoretical as before: choose'
                " <i>Every status</i> to see them.</p>")  # fmt: skip
    if taught.unread:
        items = "".join(f"<li><code>{_e(name)}</code>: {_e(why)}</li>" for name, why in sorted(taught.unread.items()))
        body.append(f'<div class="an-box tbox"><h3>Programs not read on the robot ({len(taught.unread)})</h3>'
                    '<p class="muted">Their points are not compared: written theoretical. Give them as they are on'
                    f" the robot (.LS, or .TP with FANUC PrintTP) to keep their touch-ups.</p><ul>{items}</ul></div>")  # fmt: skip
    foreign = foreign_by_program(taught)
    if foreign:
        items = "".join(
            f"<li><code>{_e(name)}</code>: {', '.join(f'P[{n}]' for n in numbers[:FOREIGN_SHOWN])}"
            + (f" and {len(numbers) - FOREIGN_SHOWN} more" if len(numbers) > FOREIGN_SHOWN else "") + "</li>"
            for name, numbers in foreign.items()
        )
        body.append(f'<div class="an-box tbox"><h3>Positions on the robot CrossArm did not write'
                    f" ({len(taught.foreign)})</h3><p class=\"muted\">Added on the robot, not by CrossArm: the new"
                    " programs do not have them, loading them removes these positions. Note them first.</p>"
                    f"<ul>{items}</ul></div>")  # fmt: skip
    label = f"Taught positions ({counts[AGAIN]} again)" if counts[AGAIN] else "Taught positions"
    return "taught", label, "\n".join(body)


TAUGHT_CSS = """
.tcards { display: flex; flex-wrap: wrap; gap: 10px; margin: .8em 0; }
.tcard { font: inherit; text-align: left; cursor: pointer; color: var(--fg); background: var(--head); min-width: 128px;
  border: 1px solid var(--line); border-left: 5px solid var(--muted); border-radius: 8px; padding: 6px 14px; }
.tcard b { display: block; font-size: 1.45em; line-height: 1.2; }
.tcard span { color: var(--muted); font-size: .86em; }
.tcard.zero { opacity: .55; }
.tcard.on { outline: 2px solid var(--accent); outline-offset: 1px; }
.tcard.st-again { border-left-color: var(--todo); } .tcard.st-kept { border-left-color: var(--ok); }
.tcard.st-new { border-left-color: var(--accent); } .tcard.st-unread { border-left-color: var(--warn); }
.tag.again { color: var(--todo); } .tag.kept { color: var(--ok); } .tag.new { color: var(--accent); }
.tag.theo, .tag.gone { color: var(--muted); } .tag.unread { color: var(--warn); }
details.tprog { border: 1px solid var(--line); border-radius: 8px; margin: 8px 0; }
details.tprog > summary { cursor: pointer; padding: 6px 10px; background: var(--head); border-radius: 8px; }
details.tprog[open] > summary { border-bottom: 1px solid var(--line); border-radius: 8px 8px 0 0; }
details.tprog .table-wrap { margin: 0; }
p.tfrom { font-size: .84em; color: var(--muted); overflow-wrap: anywhere; margin: -.4em 0 .6em; }
table.taught { font-size: .88em; table-layout: fixed; }
table.taught col.c-pt { width: 9.5em; } table.taught col.c-rp { width: 18%; } table.taught col.c-st { width: 11.5em; }
table.taught col.c-dev { width: 13.5em; } table.taught col.c-ln { width: 7em; }
table.taught td { padding: 3px 8px; overflow-wrap: anywhere; }
table.taught td.pt, table.taught td.dev { white-space: nowrap; }
table.taught tr.st-again td { background: var(--todo-bg); }
.tbox { margin: 12px 0; } .tbox ul { margin: .3em 0; }
@media print { details.tprog { break-inside: auto; } }
"""

TAUGHT_JS = r"""
(function () {
  var d = document, box = d.getElementById('taught');
  if (!box) { return; }
  function $(id) { return d.getElementById(id); }
  var rows = [].slice.call(box.querySelectorAll('table.taught tbody tr'));
  var progs = [].slice.call(box.querySelectorAll('details.tprog')), cards = [].slice.call(box.querySelectorAll('.tcard'));
  rows.forEach(function (r) { r._text = (r.closest('details').dataset.p + ' ' + r.textContent).toLowerCase(); });
  function filter() {
    var q = $('t-text').value.trim().toLowerCase(), s = $('t-status').value, shown = 0;
    rows.forEach(function (r) {
      var ok = (!s || (s === 'look' ? r.dataset.s !== 'theoretical' : r.dataset.s === s)) && (!q || r._text.indexOf(q) >= 0);
      r.hidden = !ok;
      if (ok) { shown++; }
    });
    progs.forEach(function (p) { p.hidden = !p.querySelector('tbody tr:not([hidden])'); });
    cards.forEach(function (c) { c.classList.toggle('on', c.dataset.status === s); });
    $('t-none').hidden = !(shown === 0 && s === 'look' && !q && rows.length);
    $('t-count').textContent = shown + ' of ' + rows.length + ' points shown';
  }
  $('t-text').addEventListener('input', filter);
  $('t-status').addEventListener('input', filter);
  cards.forEach(function (c) {
    c.addEventListener('click', function () {
      var s = c.dataset.status;
      $('t-status').value = $('t-status').value === s ? 'look' : s;
      filter();
      progs.forEach(function (p) { if (!p.hidden && s !== 'theoretical') { p.open = true; } });
    });
  });
  $('t-open').addEventListener('click', function () { progs.forEach(function (p) { if (!p.hidden) { p.open = true; } }); });
  $('t-close').addEventListener('click', function () { progs.forEach(function (p) { p.open = false; }); });
  filter();
})();
"""
