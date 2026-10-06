# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The HTML report: RAPID and TP side by side, the TODO list, one page that loads nothing."""

from html.parser import HTMLParser
from pathlib import Path

from crossarm import pipeline
from crossarm.convert import ConversionConfig, build_report, convert
from crossarm.convert.html_report import build_html_report, routine_end, tp_text
from crossarm.convert.source_map import Row, side_by_side
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
