# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The HTML report: RAPID and TP side by side, the TODO list, one page that loads nothing."""

import re
from html.parser import HTMLParser
from pathlib import Path

from crossarm import pipeline
from crossarm.convert import ConversionConfig, build_report, convert
from crossarm.convert.checklist import CHECKLIST_JS
from crossarm.convert.html_report import build_html_report, routine_end, tp_text
from crossarm.convert.source_map import Row, side_by_side
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
        self.loads: list[str] = []
        self.scripts = 0
        self.stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            assert a["id"] not in self.ids, f"id {a['id']} twice"
            self.ids.add(a["id"])
        if tag == "a" and (a.get("href") or "").startswith("#"):
            self.links.append(a["href"][1:])
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
    assert "Evaluation copy." in page.split('<nav class="menu"')[0]  # in the header, as in the Markdown report
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
