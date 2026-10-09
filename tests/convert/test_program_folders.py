# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The report's programs in folders, each with its counters, opened on its TODO with the rest one click away, a
TODO followed from the items list highlighting its RAPID line and the TP lines written from it; nothing of the
code laid out before it is asked for (crossarm.convert.program_folders, crossarm.convert.html_report)."""

import re
from datetime import datetime
from html.parser import HTMLParser

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.external import ProvidedRoutine
from crossarm.convert.html_report import build_html_report
from crossarm.convert.program_folders import MODULE, OTHER, PREFIX, Folder, Run, folders, name_start, todo_only
from crossarm.rapid import parse_text

STAMP = datetime(2026, 1, 1)


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------


def test_programs_go_in_folders_by_name_start_then_by_module_and_the_rest_last():
    assert [name_start(n) for n in ("PICK_A", "PICK2", "setDO16", "MAIN", "_X", "")] == [
        "PICK", "PICK", "SETDO", "MAIN", "", ""]  # fmt: skip
    programs = [("PICK_A", "Pick"), ("MAIN", "Main"), ("PICK_B", "Pick"), ("PICK3", "Cell"), ("CALIB_X", "Calib"),
                ("CALIB_Y", "Calib"), ("TOOLA", "Calib"), ("INIT", "Main"), ("LOG", "Util")]  # fmt: skip
    found = folders(programs)
    assert found == [Folder(PREFIX, "PICK", ("PICK_A", "PICK_B", "PICK3")),
                     Folder(MODULE, "Calib", ("CALIB_X", "CALIB_Y", "TOOLA")),
                     Folder(OTHER, "", ("MAIN", "INIT", "LOG"))]  # fmt: skip
    assert [f.label for f in found] == ["PICK*", "module Calib", "Other programs"]
    # Two programs never make a folder; a backup this makes no folder of is a plain list.
    assert folders([("PICK_A", "M"), ("PICK_B", "N"), ("MAIN", "O")]) == []
    assert folders([]) == []
    # Every program is in exactly one folder.
    many = [(f"P{k}_{i}", f"M{i % 4}") for k in range(9) for i in range(k)]
    names = [name for f in folders(many) for name in f.programs]
    assert sorted(names) == sorted(name for name, _ in many)


def test_the_todo_only_view_keeps_two_rows_around_each_mark_and_folds_the_rest_behind_separators():
    marks = [False] * 20
    marks[10] = True
    assert todo_only(marks) == [Run(0, 8, False), Run(8, 13, True), Run(13, 20, False)]
    # Context of two on each side, runs merged when they touch; fewer than 3 rows between two marks are shown.
    marks = [False] * 30
    marks[5] = marks[11] = marks[25] = True
    assert todo_only(marks) == [Run(0, 3, False), Run(3, 14, True), Run(14, 23, False), Run(23, 30, True)]
    assert todo_only([True, False, False, False]) == [Run(0, 4, True)]  # 1 row out: shown, no separator
    assert todo_only([False] * 5) == [Run(0, 5, False)]  # nothing to review: the full view is the one shown
    assert todo_only([]) == []
    for size in range(12):  # the runs cover every row once, in order, the marked one shown
        for k in range(size):
            runs = todo_only([i == k for i in range(size)])
            assert [i for r in runs for i in range(r.start, r.end)] == list(range(size))
            assert next(r for r in runs if r.start <= k < r.end).shown


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

DOWN = "[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]"
CELL = f"""MODULE FI
  PERS tooldata tBase:=[TRUE,[[0,0,150],[1,0,0,0]],[5,[0,0,60],[1,0,0,0],0,0,0]];
  CONST tooldata tOfsA:=[TRUE,[[0,20,40],[1,0,0,0]],[0.5,[0,0,20],[1,0,0,0],0,0,0]];
  CONST tooldata tOfsB:=[TRUE,[[10,0,30],[1,0,0,0]],[0.5,[0,0,20],[1,0,0,0],0,0,0]];
  PERS tooldata tA:=[TRUE,[[0,20,190],[1,0,0,0]],[5.5,[0,0,60],[1,0,0,0],0,0,0]];
  PERS tooldata tB:=[TRUE,[[10,0,180],[1,0,0,0]],[5.5,[0,0,60],[1,0,0,0],0,0,0]];
  CONST robtarget pA:=[[900,-100,500],{DOWN}];
  CONST robtarget pIn:=[[50,20,0],{DOWN}];
  VAR robtarget pM;
  VAR num nCount:=0;
  FUNC tooldata MakeTool(tooldata tB0,tooldata tOfs)
    VAR tooldata tRes;
    tRes:=tOfs;
    tRes.tframe:=PoseMult(tB0.tframe,tOfs.tframe);
    tRes.tload.mass:=tB0.tload.mass+tOfs.tload.mass;
    RETURN tRes;
  ENDFUNC
  PROC WriteLog(string text)
    TPWrite text;
  ENDPROC
  PROC Calib()
    MoveL pA,v200,fine,tool0;
    pM:=CRobT(\\Tool:=tool0\\WObj:=wobj0);
    tBase.tframe.trans.z:=pM.trans.z-350;
    tBase.tframe.rot:=pM.rot;
  ENDPROC
  PROC Main()
    MoveL pIn,v200,fine,tBase;
    tA:=MakeTool(tBase,tOfsA);
    tB:=MakeTool(tBase,tOfsB);
    WriteLog "tools";
    MoveL pIn,v200,fine,tA;
    MoveL pIn,v200,fine,tB;
    nCount:=nCount+1;
    nCount:=nCount+2;
    nCount:=nCount+3;
    nCount:=nCount+4;
    nCount:=nCount+5;
    nCount:=nCount+6;
    IF nCount>2 THEN
      TPReadFK nCount,"go","A","B","C","D","E";
    ENDIF
    nCount:=nCount+7;
  ENDPROC
ENDMODULE
"""


def _page(source: str = CELL, **config) -> tuple[object, str]:
    parsed = parse_text(source, path="cell.mod")
    assert parsed.module is not None, parsed.diagnostics
    cfg = ConversionConfig(timestamp=STAMP, **config)
    result = convert([parsed.module], cfg, sources={parsed.module.name: source})
    return result, build_html_report(result, cfg, ["cell.mod"], title="t")


def _program(page: str, name: str) -> str:
    return page.split(f'<details class="prog" id="p-{name}"')[1].split("</details>")[0]


def test_each_program_says_its_counts_before_opening_and_what_happened_in_it():
    provided = {"WRITELOG": ProvidedRoutine("WriteLog", "WRITE_LOG")}
    result, page = _page(karel=True, external_routines=provided)
    main = _program(page, "MAIN")
    summary = re.sub(r"<[^>]+>", "", main.split("</summary>")[0])
    assert "MAIN.LS FI.Main 1 TODO" in summary
    assert "2 KAREL calls" in summary and "2 inlined FUNC sites" in summary and "1 provided routine call" in summary
    assert result.karel_calls == {"CA_POSEMULT": {"MAIN": 2}}
    assert list(result.inlined_sites) == ["MakeTool"] and [p for p, _ in result.inlined_sites["MakeTool"]] == ["MAIN"] * 2
    body = main.split("</summary>")[1]
    facts = body.split('<ul class="pdid">')[1].split("</ul>")[0]
    assert "<code>CA_POSEMULT</code> (2)" in facts
    assert "copied here at 2 call sites (l. " in facts and "2 in all): change the FUNC" in facts
    assert "<code>WriteLog</code> called as <code>CALL WRITE_LOG</code>" in facts
    assert re.search(r'href="#L-MAIN-\d+"', facts)  # each site leads to its line
    # Without --karel, provided routines or FUNCs copied in, a program has nothing of it.
    _, plain = _page()
    assert "KAREL call" not in _program(plain, "MAIN").split("</summary>")[0]
    assert '<ul class="pdid">' not in _program(plain, "CALIB")


def test_a_program_opens_on_its_todo_with_the_rest_behind_separators_and_the_full_view_one_click_away():
    _, page = _page()
    main = _program(page, "MAIN")
    table = main.split('<table class="sbs only">')[1].split("</table>")[0]
    assert '<button type="button" data-v="todo" aria-pressed="true">' in main and 'data-v="all"' in main
    rows = re.findall(r"<tr([^>]*)>", table.split("<tbody>")[1])
    gaps = [r for r in rows if 'class="gap"' in r]
    assert gaps and all(re.search(r'data-g="\d+"', r) for r in gaps)
    folded = [r for r in rows if re.search(r'class="[^"]*\bf\b', r)]
    assert folded and all("todo" not in r and "warn" not in r for r in folded)  # never a line to review
    for g in re.findall(r'<tr class="gap" data-g="(\d+)"', table):  # each separator says how many lines it holds
        count = sum(1 for r in folded if f'data-g="{g}"' in r and "data-l=" in r and "again" not in r)
        assert re.search(rf'data-g="{g}"><td colspan="4"><button[^>]*>… {count} lines? converted …', table)
    # The TODO line, two lines before and after it: shown.
    todo_line = int(re.search(r'<tr id="L-MAIN-(\d+)" data-l="\d+" class="todo">', table)[1])
    for line in range(todo_line - 2, todo_line + 3):
        row = re.search(rf'<tr id="L-MAIN-{line}"[^>]*>', table)
        assert row and not re.search(r'class="[^"]*\bf\b', row[0]), line
    # A program with nothing to review opens on its full view: no separators, no view buttons.
    calib = _program(page, "CALIB")
    assert '<table class="sbs">' in calib and 'class="gap"' not in calib and "data-v=" not in calib


def test_a_todo_followed_from_the_list_highlights_its_rapid_line_and_every_tp_line_written_from_it():
    _, page = _page()
    main = _program(page, "MAIN")
    line = int(re.search(r'<tr id="L-MAIN-(\d+)" data-l="\d+" class="todo">', main)[1])
    assert f'href="#L-MAIN-{line}"' in page.split('<template id="f-rows"')[1].split("</template>")[0]
    tagged = re.findall(rf'<tr([^>]*data-l="{line}"[^>]*)>', main)
    kinds = [re.search(r'class="([^"]*)"', t)[1] for t in tagged]
    assert kinds[0] == "todo" and "note todo" in kinds  # the line and its note
    # The IF's ENDIF, written further down: a row of its own, highlighted with the line.
    if_line = int(re.search(r'<tr id="L-MAIN-(\d+)"[^>]*><td class="n">\d+</td><td class="c">\s*IF nCount', main)[1])
    assert re.search(rf'<tr data-l="{if_line}" class="again[^"]*">', main)
    script = page.split("<script>")[1]
    assert "function hit(el)" in script and "querySelectorAll('tr[data-l=\"' + l + '\"]')" in script
    assert "setView(el.closest('details.prog'), true)" in script  # opened on its TODO-only view


def _many(count: int) -> str:
    routines = "".join(f"PROC {'pick' if i % 2 else 'place'}_{i}()\n  nCount:=nCount+{i};\n"
                       + ('  TPReadFK nCount,"go","A","B","C","D","E";\n' if i % 3 == 0 else "")
                       + "ENDPROC\n" for i in range(count))  # fmt: skip
    return f"MODULE Big\nVAR num nCount:=0;\n{routines}ENDMODULE\n"


class _Live(HTMLParser):
    """Elements the browser lays out on opening the page (outside every <template>)."""

    def __init__(self) -> None:
        super().__init__()
        self.depth, self.tags = 0, []

    def handle_starttag(self, tag, attrs):
        if tag == "template":
            self.depth += 1
        elif self.depth == 0:
            self.tags.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag == "template":
            self.depth -= 1


class _Levels(HTMLParser):
    """How many details and tables of each class sit at each depth of lazy templates."""

    def __init__(self) -> None:
        super().__init__()
        self.depth, self.seen = 0, []

    def handle_starttag(self, tag, attrs):
        if tag == "template":
            self.depth += 1
        elif tag in ("details", "table") and (kind := dict(attrs).get("class", "").split(" ")[0]) in ("pf", "prog", "sbs"):
            self.seen.append((self.depth, kind))

    def handle_endtag(self, tag):
        if tag == "template":
            self.depth -= 1

    def at(self, depth: int) -> dict[str, int]:
        out: dict[str, int] = {}
        for d, kind in self.seen:
            if d == depth:
                out[kind] = out.get(kind, 0) + 1
        return out


def test_the_index_shows_folders_and_nothing_of_a_programs_code_is_laid_out_before_it_is_opened():
    _, page = _page(_many(240))
    section = page.split('<section id="code">')[1].split("</section>")[0]
    assert re.findall(r'<span class="fn">([^<]+)</span>', section) == ["PLACE*", "PICK*"]  # 40 TODO each: by first program
    assert re.search(r'<span class="fn">PICK\*</span> <span class="muted">120 programs</span> <span class="tag todo">'
                     r"40 TODO</span> <span class=\"tag ok\">80 ready</span>", section)  # fmt: skip
    live = _Live()
    live.feed(page)
    assert not [t for t, a in live.tags if t in ("table", "tr") and "sbs" in a.get("class", "")]
    assert not [a for t, a in live.tags if t == "details" and a.get("class") in ("pf", "prog")]
    # Opening the section lays out the folders alone; a folder its programs' lines alone; a program its code.
    levels = _Levels()
    levels.feed(section)
    assert levels.at(1) == {"pf": 2} and levels.at(2) == {"prog": 240} and levels.at(3) == {"sbs": 240}
    assert "<b>80 programs ready as is</b>" in section  # one line per folder, its programs on demand
