# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The HTML report: RAPID and TP side by side, the TODO list, one page that loads nothing."""

import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

from crossarm import __version__, pipeline
from crossarm.convert import ConversionConfig, build_report, convert
from crossarm.convert.analysis import verdict
from crossarm.convert.checklist import CHECKLIST_JS
from crossarm.convert.coverage import fmt_percent
from crossarm.convert.html_report import REVIEW_PAGE, build_html_report, routine_end, tp_text
from crossarm.convert.source_map import Row, parse_todo_href, side_by_side, todo_href
from crossarm.fanuc.maketp import TpExport
from crossarm.fanuc.tp import Instruction, Motion
from crossarm.licence import LicenceStatus
from tests.helpers import parse_module

SOURCE = """MODULE Cell
CONST robtarget pHome:=[[900,100,700],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
VAR num nCount:=0;
PROC main()
  ! say <b>hello</b> & "bye"
  MoveJ pHome,v1000,z10,tool0;
  IF nCount>2 THEN
    nCount:=0;
  ENDIF
  TEST nCount
  CASE 1:
    nCount:=5;
  DEFAULT:
    nCount:=6;
  ENDTEST
  TPReadFK nCount,"<script>alert(1)</script>","A","B","C","D","E";
  nCount:=nCount+1;
ENDPROC
ENDMODULE
"""


def _convert(source: str = SOURCE):
    module = parse_module(source)
    return convert([module], ConversionConfig(), sources={module.name: source})


class _Page(HTMLParser):
    """What the tests look at in the page: ids, in-page links, tags that would load something."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.filters: list[dict[str, str]] = []  # the filters of the links to the items to review
        self.loads: list[str] = []
        self.scripts = 0
        self.stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            assert a["id"] not in self.ids, f"id {a['id']} twice"
            self.ids.add(a["id"])
        if tag == "a" and (a.get("href") or "").startswith("#"):
            self.links.append(a["href"][1:].split("&")[0])  # '#todo&cause=..': the filters are the page's script's
            if parse_todo_href(a["href"]):
                self.filters.append(parse_todo_href(a["href"]))
        if a.get("src") or tag == "link" or tag in ("iframe", "img", "object", "embed"):
            self.loads.append(tag)
        if tag == "script":
            self.scripts += 1


def test_each_tp_line_knows_the_rapid_line_it_was_written_from():
    result = _convert()
    info = result.programs[0]
    lines = info.program.lines
    assert len(info.sources) == len(lines) and info.routine_line == 4
    by_text = {tp_text(line)[0]: source for line, source in zip(lines, info.sources, strict=True)}
    assert by_text["!RAPID Cell.main"] is None  # the header remark: no statement wrote it
    assert next(s for line, s in zip(lines, info.sources, strict=True) if isinstance(line, Motion)) == 6
    assert by_text["R[1:nCount]=0"] == 8
    assert by_text["ENDIF"] == 7  # the IF wrote it
    assert by_text["R[1:nCount]=5"] == 12 and by_text["R[1:nCount]=6"] == 14  # moved behind the SELECT, still theirs
    assert next(s for t, s in by_text.items() if t.startswith("SELECT")) == 10
    assert next(s for t, s in by_text.items() if t.startswith("!TODO l.16")) == 16
    assert by_text["R[1:nCount]=R[1:nCount]+1"] == 17


def test_an_error_handler_left_todo_is_on_its_error_line():
    result = _convert('MODULE M\nPROC p()\n  WaitTime 1;\nERROR\n  TPWrite "x";\n  RETRY;\nENDPROC\nENDMODULE\n')
    assert result.programs[0].sources == (None, 3, 4)


def test_side_by_side_shows_every_rapid_line_once_in_order():
    rows = side_by_side([None, 5, 5, 6, None, 5, 8], first=4, last=9)
    assert rows == [
        Row(4, (0,)),  # header lines go with the routine's first line
        Row(5, (1, 2)), Row(6, (3,)), Row(None, (4,)), Row(5, (5,), again=True),
        Row(7, ()), Row(8, (6,)), Row(9, ()),
    ]  # fmt: skip
    assert routine_end(["PROC a()", "  x:=1; ! ENDPROC", "ENDPROC", "ENDMODULE"], 1) == 3


def test_tp_lines_read_as_in_the_ls_file():
    assert tp_text(Instruction("R[1]=0")) == ["R[1]=0"]
    assert tp_text(Motion("L", "P[2]", "500mm/sec", "CNT50", options="ACC80")) == ["L P[2] 500mm/sec CNT50 ACC80"]
    assert tp_text(Motion("C", "P[3]", "100mm/sec", "FINE", via="P[2]")) == ["C P[2]", "   P[3] 100mm/sec FINE"]


def test_the_page_loads_nothing_escapes_the_backup_and_links_every_todo_to_its_line():
    result = _convert()
    licence = LicenceStatus(None)
    page = build_html_report(result, ConversionConfig(), ["cell.mod"], licence, title="CrossArm <test>",
                             lead=["!CrossArm EVALUATION copy"])  # fmt: skip
    parsed = _Page()
    parsed.feed(page)
    assert parsed.loads == [] and parsed.scripts == 1
    assert "http://" not in page and "https://" not in page and "@import" not in page
    assert "<script>alert" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<b>hello" not in page and "&lt;b&gt;hello&lt;/b&gt; &amp; &quot;bye&quot;" in page
    assert "<title>CrossArm &lt;test&gt;</title>" in page
    assert {"summary", "review", "code", "details", "p-MAIN", "L-MAIN-16"} <= parsed.ids
    assert set(parsed.links) <= parsed.ids  # no link leads nowhere
    assert "L-MAIN-16" in parsed.links  # the TODO, from the list to its line
    assert '<tr id="L-MAIN-16" class="todo">' in page
    # Under the verdict, before what to do first: always seen, the header only says the licence.
    analysis = page.split('<section id="analysis">')[1].split("</section>")[0]
    assert page.count("Evaluation copy.") == 1 and "Evaluation copy." in analysis.split('class="an-grid"')[0]
    assert analysis.index("Evaluation copy.") > analysis.index('class="decision"')
    assert "prefers-color-scheme: dark" in page and "@media print" in page
    assert 'class="bar js-only"' in page  # filters only shown when the script runs


def test_nothing_of_the_markdown_report_is_lost():
    result = _convert()
    config = ConversionConfig()
    markdown = build_report(result, config, ["cell.mod"])
    page = build_html_report(result, config, ["cell.mod"], title="t", extra="## Syntax errors\n\n- `x`\n")
    headings = [line.lstrip("#").strip() for line in markdown.splitlines() if line.startswith("## ")]
    for heading in headings:
        assert f"{heading}</h2>" in page, heading
    for note in result.notes:  # every item to review, with its cause
        assert f'data-c="{note.category}"' in page
    assert "Syntax errors</h2>" in page


def test_the_pipeline_writes_the_page_and_the_markdown(tmp_path):
    source = tmp_path / "cell.mod"
    source.write_text(SOURCE, encoding="utf-8")
    output = pipeline.run([source], output=tmp_path / "out", log=lambda _: None)
    page = output.tasks[0].report_html.read_text(encoding="utf-8")
    assert output.tasks[0].report_html.name == "crossarm_report.html"
    assert '<details class="prog" id="p-MAIN"' in page and "PROC main()" in page
    assert "# CrossArm conversion report" in (tmp_path / "out" / "crossarm_report.md").read_text(encoding="utf-8")
    ls = (tmp_path / "out" / "MAIN.LS").read_text(encoding="ascii")
    number = next(int(line.split(":")[0]) for line in ls.splitlines() if "!RAPID Cell.main" in line)
    assert number > 1  # after the licence mark: numbered as in the .LS
    assert f'<tr id="L-MAIN-4"><td class="n">4</td><td class="c">PROC main()</td><td class="n">{number}' in page
    assert Path(output.tasks[0].report_html).stat().st_size < 200_000


CELL = r"""MODULE Cell
PERS tooldata tGrip:=[TRUE,[[0,0,185.5],[1,0,0,0]],[2.4,[0,0,90],[1,0,0,0],0,0,0]];
PERS wobjdata wTable:=[FALSE,TRUE,"",[[800,-200,300],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
CONST robtarget pPick:=[[100,0,50],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
VAR num nParts:=3;
PROC main()
  MoveJ Offs(pPick,0,0,100),v1000,z50,tGrip\WObj:=wTable;
  MoveL pPick,v200,fine,tGrip\WObj:=wTable;
  SetDO doGrip,1;
  WaitDI diPart,1;
  nParts:=nParts+1;
  TPReadFK nParts,"Go?","A","B","C","D","E";
ENDPROC
ENDMODULE
"""


def _checklist(page: str) -> dict[str, list[str]]:
    """The checklist's groups, each with the text of its items."""
    section = page.split('<section id="checklist">')[1].split("</section>")[0]
    groups = {}
    for title, body in re.findall(r'<h3>\d+\. ([^<]*) <span class="ckc">.*?</h3>(.*?)</ul>', section):
        items = re.findall(r"<li data-id=[^>]*>(.*?)</li>", body)
        groups[title] = [" ".join(re.sub(r"<[^>]+>", " ", item).split()) for item in items]
    return groups


def test_the_checklist_lists_what_to_set_on_the_robot_in_order_with_its_values():
    result = _convert(CELL)
    page = build_html_report(result, ConversionConfig(), ["cell.mod"], title="CrossArm - cell")
    groups = _checklist(page)
    assert list(groups) == [
        "Load the programs", "Frames and tools", "Payloads", "I/O to map", "Registers, flags and timers",
        "TODO lines to finish by hand", "Points to touch up", "Motion to check",
    ]  # fmt: skip
    assert any("ASCII Upload option (R507)" in item and "--tp" in item for item in groups["Load the programs"])
    frames = groups["Frames and tools"]
    assert any(i.startswith("UFRAME[1] wTable X 800.000 Y -200.000 Z 300.000") and "MAIN l.7" in i for i in frames)
    assert any(i.startswith("UTOOL[1] tGrip X 0.000 Y 0.000 Z 185.500") for i in frames)
    payload = "PAYLOAD[1] tGrip mass 2.4 kg centre 0, 0, 9 cm inertia 0, 0, 0 kgf.cm.s2 tool used in MAIN l.7"
    assert groups["Payloads"] == [payload]
    assert groups["I/O to map"] == ["DI[1] diPart used in MAIN l.10", "DO[1] doGrip used in MAIN l.9"]
    assert groups["Registers, flags and timers"] == [
        "R[1] nParts RAPID VAR initial value 3: set it on the controller used in MAIN l.11"]
    assert groups["TODO lines to finish by hand"][0].startswith("MAIN.LS: 1 TODO")
    assert groups["Points to touch up"][0].startswith("MAIN.LS: 2 points P[1] Offs(pPick, 0, 0, 100), P[2] pPick")
    motion = groups["Motion to check"]
    assert any(i.startswith("Zone z50 CNT") for i in motion) and "Joint move speeds v1000 22%" in " ".join(motion)
    parsed = _Page()
    parsed.feed(page)
    assert parsed.loads == [] and set(parsed.links) <= parsed.ids  # nothing loaded, every link leads somewhere
    assert '<a href="#L-MAIN-12">MAIN l.12</a>' in page and 'data-prog="MAIN"' in page  # the TODO, then the list
    assert '<label for="ck-' in page and 'class="bar js-only"><span class="meter ck-meter">' in page


def test_the_checklist_keeps_its_ticks_per_report_and_works_with_storage_blocked():
    result = _convert(CELL)
    one = build_html_report(result, ConversionConfig(), ["cell.mod"], title="CrossArm - cell")
    other = build_html_report(result, ConversionConfig(), ["cell.mod"], title="CrossArm - other cell")
    key = re.compile(r'<div id="ck" data-key="([0-9a-f]+)"')
    assert key.search(one)[1] != key.search(other)[1]  # ticks kept apart, per backup and task
    ids = re.findall(r'<li data-id="([0-9a-f]+)"', one)
    assert ids == re.findall(r'<li data-id="([0-9a-f]+)"', other) and len(set(ids)) == len(ids)  # stable, unique
    # Every use of the storage is inside a try: blocked storage (file:// in some browsers) must not stop the page.
    outside = re.sub(r"try \{.*?\} catch \(e\)", "", CHECKLIST_JS, flags=re.DOTALL)
    assert "localStorage" in CHECKLIST_JS and "localStorage" not in outside
    assert "@media print" in one and "print-ck" in one  # printed with its boxes, alone with the button


def test_the_checklist_escapes_what_it_shows_and_loads_from_the_tp_folder():
    result = _convert(CELL)
    export = TpExport(Path("TP"), made=["MAIN"], refused=[("MAIN", "<b>bad</b> line")], robot="R<1>")
    page = build_html_report(result, ConversionConfig(), ["cell.mod"], title="t", tp=export, tp_where="TP")
    load = _checklist(page)["Load the programs"]
    assert load[0].startswith("Copy the TP folder to a USB stick and load its 1 .TP programs")
    assert any(item.startswith("MAIN.LS: refused by MakeTP") for item in load)
    assert "<b>bad" not in page and "&lt;b&gt;bad&lt;/b&gt; line" in page and "R&lt;1&gt;" in page


# ---------------------------------------------------------------------------
# The cockpit: what the first screen shows, what waits until opened
# ---------------------------------------------------------------------------


class _Live(HTMLParser):
    """What the browser lays out on opening the page: the elements outside every <template>."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0  # templates open
        self.elements = 0
        self.ids: set[str] = set()
        self.inert: set[str] = set()  # ids only built when their fold is opened
        self.folds: list[dict[str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "template":
            self.depth += 1
            return
        if self.depth == 0:
            self.elements += 1
            if tag == "details":
                self.folds.append(a)
        if "id" in a:
            (self.inert if self.depth else self.ids).add(a["id"])

    def handle_endtag(self, tag):
        if tag == "template":
            self.depth -= 1


def _live(page: str) -> _Live:
    parsed = _Live()
    parsed.feed(page)
    return parsed


def _many(count: int, todo: int | None = None) -> str:
    """A module of `count` routines, each with two points and a warning, the first `todo` (all) with a TODO."""
    todo = count if todo is None else todo
    routines = "".join(
        f"PROC r{i}()\n  MoveJ pHome,v1000,z10,tool0;\n  MoveL Offs(pHome,{i},0,0),v200,fine,tool0;\n"
        + ('  TPReadFK nCount,"go","A","B","C","D","E";\n' if i < todo else "")
        + f"  nCount:=nCount+{i};\nENDPROC\n"
        for i in range(count)
    )
    return ("MODULE Big\nCONST robtarget pHome:=[[900,100,700],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];\n"
            f"VAR num nCount:=0;\n{routines}ENDMODULE\n")  # fmt: skip


STAMP = datetime(2026, 3, 4, 5, 6, 7)


def test_the_top_line_says_where_things_stand_and_leads_to_each_section():
    result = _convert(CELL)
    page = build_html_report(result, ConversionConfig(timestamp=STAMP), ["cell.mod"], LicenceStatus(None), title="t")
    top = page.split('<div class="cockpit" id="cockpit">')[1].split("</nav></div>")[0]
    text = " ".join(re.sub(r"<[^>]+>", " ", top).split())
    decision = verdict(result)
    assert text.startswith(f"{decision.level} · {fmt_percent(result.coverage.percent)} converted · 1 TODO ·"), text
    assert f"{len(decision.blocking)} blocking cause" in text and "2 points to touch up" in text
    assert f"CrossArm {__version__} · 2026-03-04 05:06" in text
    assert re.findall(r'<option value="(\w)">', top) == ["s", "i", "d"]  # one page, three views
    labels = re.findall(r">([^<]+)</a>", top.split('<nav class="menu"')[1])
    assert labels[:2] == ["Analysis", "Capacity"] and labels[-1] == "Details"
    assert {"Checklist", "TODO (1)", "Programs", "Points", "Summary"} <= set(labels)
    live = _live(page)
    for href in re.findall(r'href="#([^"&]+)', top):  # every place it names is there, built or to build
        assert href in live.ids | live.inert, href
    # The evaluation notice: under the verdict, in the page as it opens (neither folded nor left to the script).
    analysis = page.split('<section id="analysis">')[1].split("</section>")[0]
    assert analysis.index('class="decision"') < analysis.index("Evaluation copy.") < analysis.index("What to do first")
    assert "<template" not in analysis


def test_only_the_analysis_is_open_and_each_view_opens_its_own_folds():
    page = build_html_report(_convert(CELL), ConversionConfig(), ["cell.mod"], title="t")
    sections = re.findall(r'<section id="([^"]+)">\s*(?:<span id="todo"></span>)?(<details class="sec"[^>]*>)?', page)
    assert sections[0] == ("analysis", "")  # never folded
    depth = {sid: re.search(r'data-depth="(\w+)"', fold)[1] for sid, fold in sections[1:]}
    assert depth == {"checklist": "id", "review": "id", "code": "id", "points": "d", "summary": "d", "details": "d"}
    for _, fold in sections[1:]:
        assert not re.search(r"\sopen\b", fold)  # folded until a view or the reader opens it
    assert '<details class="sec" id="ck-fold" data-depth="id">' in page
    assert '<details class="why" data-depth="d">' in page  # how the decision is made: the detail view
    # The script applies the view: synthesis unless this browser kept another, its storage inside a try.
    script = page.split("<script>")[1]
    assert "crossarm-view" in script and "var v = 's';" in script
    assert "localStorage" not in re.sub(r"try \{.*?\} catch \(e\)", "", script, flags=re.DOTALL)


def test_long_lists_wait_inert_until_their_fold_is_opened():
    small = _live(build_html_report(_convert(_many(2)), ConversionConfig(), ["big.mod"], title="t"))
    big_page = build_html_report(_convert(_many(60)), ConversionConfig(), ["big.mod"], title="t")
    big = _live(big_page)
    # The lines, programs, points, checklist items and items to review are all there, but inert.
    assert {"L-R0-5", "L-R59-359", "p-R59", "ck-points", "f-body"} <= big.inert
    assert not {"L-R0-5", "p-R59", "ck-points"} & big.ids
    assert '<template id="f-rows" data-page="50">' in big_page and big_page.count('<tr data-k="TODO"') == 60
    assert big_page.count("<template data-lazy>") >= 60 + 60 + 5  # a view per program, its points, each section
    # What the browser lays out first does not grow with the backup.
    assert big.elements < 400 and big.elements - small.elements < 40
    assert {"analysis", "cockpit", "todo", "ck-fold", "ck-sum"} <= big.ids
    assert '<noscript><p class="nojs">' in big_page and big_page.count("<noscript>") >= 6  # said without the script


def _review_rows(page: str) -> list[dict[str, str]]:
    rows = page.split('<template id="f-rows" data-page="50">')[1].split("</template>")[0]
    return [dict(zip(("k", "c", "p"), m, strict=True))
            for m in re.findall(r'<tr data-k="([^"]*)" data-c="([^"]*)" data-p="([^"]*)">', rows)]  # fmt: skip


def _shown(rows: list[dict[str, str]], pages: int, kind: str = "", cause: str = "", prog: str = "") -> tuple[int, int]:
    """What the page's script lays out: (rows in the table, rows matching) after `pages` pages of REVIEW_PAGE."""
    match = [r for r in rows if (not kind or r["k"] == kind) and (not cause or r["c"] == cause)
             and (not prog or r["p"] == prog)]  # fmt: skip
    return min(len(match), pages * REVIEW_PAGE), len(match)


def test_the_items_to_review_come_a_page_at_a_time_with_their_filters_kept():
    result = _convert(_many(60))
    page = build_html_report(result, ConversionConfig(), ["big.mod"], title="t")
    rows = _review_rows(page)
    assert len(rows) == len(result.notes) and '<tbody id="f-body"></tbody>' in page  # nothing laid out before
    assert '<select id="f-kind" aria-label="Kind" data-default="TODO">' in page  # the TODO first
    assert _shown(rows, 1, "TODO") == (50, 60) and _shown(rows, 2, "TODO") == (60, 60)  # "show more": the rest
    assert _shown(rows, 1, "TODO", prog="R7") == (1, 1)
    cause = result.notes[0].category
    assert _shown(rows, 1, cause=cause)[1] == sum(1 for n in result.notes if n.category == cause)
    # The script: a page more keeps the filters; the count says how many match and how many there are.
    assert 'id="f-more" hidden>' in page and "limit = more ? limit + PAGE : PAGE;" in page
    assert "shown + ' of ' + match.length + what + ' shown'" in page and "' TODO + ' + TOTAL.warn" in page
    warned = build_html_report(_convert(_many(2, todo=0)), ConversionConfig(), ["m.mod"], title="t")
    assert '<select id="f-kind" aria-label="Kind" data-default="">' in warned  # no TODO: the warnings at once


def test_links_to_the_items_to_review_carry_their_filters_in_the_address():
    assert todo_href() == "#todo"
    assert todo_href(cause="value not known", prog="MAIN") == "#todo&cause=value%20not%20known&prog=MAIN"
    odd = todo_href(cause="a&b=c <d>", prog="P#1", kind="WARNING", q="x y")
    assert parse_todo_href(odd) == {"kind": "WARNING", "cause": "a&b=c <d>", "prog": "P#1", "q": "x y"}
    assert parse_todo_href("#L-MAIN-3") is None and parse_todo_href("#todo") == {}
    result = _convert(CELL)
    page = build_html_report(result, ConversionConfig(), ["cell.mod"], title="t")
    parsed = _Page()
    parsed.feed(page)
    causes = {note.category for note in result.notes}
    assert parsed.filters and all(set(f) <= {"cause", "prog"} for f in parsed.filters)
    assert all(f["cause"] in causes for f in parsed.filters if "cause" in f)
    assert {"prog": "MAIN"} in parsed.filters  # the checklist's TODO of a program
    assert "if (h.id === 'todo') { showReview(h.q); return; }" in page  # read by the page's script
    assert "L-MAIN-12" in parsed.links and "ck-points" in parsed.links  # the plain anchors still lead there


def test_programs_ready_as_is_are_one_line_and_points_one_line_per_program():
    page = build_html_report(_convert(_many(3, todo=1)), ConversionConfig(), ["big.mod"], title="t")
    assert "<b>2 programs ready as is</b>" in page and 'id="p-ready"' in page
    assert '<details class="prog" id="p-R1" data-p="R1" data-r="Big.r1" data-todo="0" data-ready>' in page
    assert '<details class="prog" id="p-R0" data-p="R0" data-r="Big.r0" data-todo="1">' in page
    section = page.split('<section id="points">')[1].split("</section>")[0]
    assert section.count('<details class="pts"') == 3 and 'data-s="r1 phome offs(phome, 1, 0, 0)"' in section
    assert "<b>2 points</b>" in section and "Value (theoretical)" in section
    assert "<h2>Points</h2>" not in page.split('<section id="details">')[1]  # not twice
