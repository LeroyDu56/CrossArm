# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""crossarm_summary.json, crossarm_report_summary.md and the comparison with the previous conversion."""

import json
from pathlib import Path

from crossarm import __version__, pipeline
from crossarm.convert import ConversionConfig
from crossarm.convert.run_summary import (
    SUMMARY_JSON,
    SUMMARY_MD,
    compare,
    file_hashes,
    files_differ,
    fingerprint,
    newest,
    read_summary,
)
from crossarm.summary import describe_since

MAIN = """MODULE Main
CONST robtarget pHome:=[[900,100,700],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
PROC main()
  MoveJ pHome,v1000,z10,tool0;
  TPReadFK nCount,"go","A","B","C","D","E";
  Pick;
ENDPROC
ENDMODULE
"""
PICK = """MODULE Pick
VAR num nCount:=0;
PROC Pick()
  nCount:=nCount+1;
  ErrWrite "Pick", "done";
ENDPROC
ENDMODULE
"""


def _cell(folder: Path, pick: str = PICK) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Main.mod").write_text(MAIN, encoding="utf-8")
    (folder / "Pick.mod").write_text(pick, encoding="utf-8")
    return folder


def _run(cell: Path, output: Path | None = None, karel: bool = False):
    files = sorted(cell.glob("*.mod"))
    return pipeline.run(files, output=output, log=lambda line: None, config=ConversionConfig(karel=karel))


def _summary(**changes) -> dict:
    base = {
        "format": 1, "crossarm": "1.9.0", "date": "2026-10-09T10:00:00", "backup": "Cell", "task": "T_ROB1",
        "sources": {"fingerprint": "f1", "files": {"A.mod": "1", "B.mod": "2", "C.mod": "3"}},
        "options": {"karel": False, "map": False, "provided_routines": 0},
        "todo": 10, "warnings": 4, "converted_percent": 80.0,
        "todo_by_cause": {"value not known at conversion time": 6, "RAPID error handler": 4},
    }  # fmt: skip
    base.update(changes)
    return base


def test_the_fingerprint_is_the_sorted_hashes_of_the_rapid_files(tmp_path):
    cell = _cell(tmp_path / "cell")
    hashes = file_hashes([cell / "Pick.mod", cell / "Main.mod"])
    assert list(hashes) == ["Main.mod", "Pick.mod"] and all(len(h) == 64 for h in hashes.values())
    assert fingerprint(hashes) == fingerprint(dict(reversed(hashes.items())))
    other = _cell(tmp_path / "other")
    assert set(file_hashes([cell / "Main.mod", other / "Main.mod"])) == {"cell/Main.mod", "other/Main.mod"}
    assert files_differ({"A": "1", "B": "2"}, {"A": "1", "B": "3", "C": "4"}) == 2


def test_the_same_backup_compares_todo_share_and_causes():
    then = _summary()
    now = _summary(todo=7, warnings=4, converted_percent=85.5,
                   todo_by_cause={"value not known at conversion time": 5, "routine call with arguments": 2})
    since = compare(then, now)
    assert since is not None and since.same_backup and since.files_differ == 0
    assert since.todo == (10, 7) and since.percent == (80.0, 85.5)
    assert since.lost == (("RAPID error handler", 4),) and since.gained == (("routine call with arguments", 2),)
    text = since.text()
    assert text.startswith("Since the previous conversion (CrossArm 1.9.0, 2026-10-09 10:00), same RAPID files:")
    assert "TODO 10 -> 7" in text and "converted 80 % -> 85.5 %" in text
    assert "Causes gone: RAPID error handler (4); new causes: routine call with arguments (2)." in text
    assert "Options differ" not in text
    assert since.short().isascii()  # the log and the window: any console prints it


def test_a_changed_backup_says_how_many_files_differ_and_labels_the_figures():
    now = _summary(sources={"fingerprint": "f2", "files": {"A.mod": "1", "B.mod": "9", "D.mod": "4"}})
    since = compare(_summary(), now)
    assert since is not None and not since.same_backup and since.files_differ == 3  # B changed, C gone, D new
    assert since.text().startswith("The backup changed since the previous conversion (CrossArm 1.9.0, 2026-10-09"
                                   " 10:00): 3 RAPID files differ. Figures then (other files) and now: TODO 10 -> 10")
    assert since.short().startswith("Backup changed (3 files differ) since the previous conversion: TODO 10 -> 10")


def test_another_backup_or_task_is_never_compared_whatever_its_name():
    other = _summary(sources={"fingerprint": "f9", "files": {"X.mod": "1", "Y.mod": "2"}})
    assert compare(_summary(), other) is None  # same backup name, no RAPID file in common
    assert compare(_summary(task="T_ROB2"), _summary()) is None
    assert compare(None, _summary()) is None
    assert compare(_summary(sources={"files": {}}), _summary()) is None


def test_the_options_that_differ_are_named():
    now = _summary(options={"karel": True, "map": False, "provided_routines": 3})
    since = compare(_summary(), now)
    assert since.options == ("--karel: now only", "routines provided (external_routines): 0 -> 3")
    assert "Options differ: --karel: now only; routines provided (external_routines): 0 -> 3." in since.text()
    assert compare(now, _summary()).options[0] == "--karel: then only"


def test_an_unreadable_summary_is_none_and_the_newest_is_the_previous(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("<html>not a summary</html>", encoding="utf-8")
    assert read_summary(bad) is None and read_summary(tmp_path / "missing.json") is None
    bad.write_text(json.dumps({"todo": 3}), encoding="utf-8")
    assert read_summary(bad) is None
    assert newest([_summary(date="2026-10-01T10:00:00"), _summary(date="2026-10-09T09:00:00", todo=1)])["todo"] == 1


def test_every_conversion_writes_both_summaries(tmp_path):
    out = _run(_cell(tmp_path / "cell"), tmp_path / "out")
    folder = out.tasks[0].folder
    data = json.loads((folder / SUMMARY_JSON).read_text(encoding="utf-8"))
    assert data["crossarm"] == __version__ and data["format"] == 1 and data["task"] == out.tasks[0].task
    assert set(data["sources"]["files"]) == {"Main.mod", "Pick.mod"}
    assert data["todo"] == out.tasks[0].todo == sum(data["todo_by_cause"].values())
    assert data["options"]["karel"] is False and data["licence"] in {"evaluation", "licensed"}
    assert data["verdict"] in {"ready", "workable", "not ready", "empty"} and "Motion" in data["converted_by_area"]
    page = (folder / SUMMARY_MD).read_text(encoding="utf-8")
    assert page.startswith("# CrossArm summary: ") and "## What to do first" in page and "Since" not in page
    assert len(page.splitlines()) < 60  # one page
    assert out.tasks[0].result.since is None


def test_converting_again_into_the_same_folder_compares_with_the_previous_conversion(tmp_path):
    cell = _cell(tmp_path / "cell")
    _run(cell, tmp_path / "out")
    again = _run(cell, tmp_path / "out", karel=True)
    since = again.tasks[0].result.since
    assert since is not None and since.same_backup and since.options == ("--karel: now only",)
    folder = again.tasks[0].folder
    assert "Since the previous conversion" in (folder / SUMMARY_MD).read_text(encoding="utf-8")
    assert "Since the previous conversion" in (folder / "crossarm_report.md").read_text(encoding="utf-8")
    assert 'class="since same"' in (folder / "crossarm_report.html").read_text(encoding="utf-8")
    assert json.loads((folder / SUMMARY_JSON).read_text(encoding="utf-8"))["options"]["karel"] is True


def test_a_new_output_next_to_the_input_compares_with_the_newest_earlier_one(tmp_path):
    cell = _cell(tmp_path / "cell")
    first = _run(cell)
    assert first.folder.name == "crossarm_cell" and first.tasks[0].result.since is None
    (cell / "Pick.mod").write_text(PICK.replace("nCount+1", "nCount+2"), encoding="utf-8")
    second = _run(cell)
    assert second.folder.name == "crossarm_cell_2"
    since = second.tasks[0].result.since
    assert since is not None and not since.same_backup and since.files_differ == 1
    assert "The backup changed since the previous conversion" in since.text()


def test_the_html_says_nothing_when_there_is_no_previous_conversion(tmp_path):
    out = _run(_cell(tmp_path / "cell"), tmp_path / "out")
    assert 'class="since' not in (out.tasks[0].folder / "crossarm_report.html").read_text(encoding="utf-8")


def test_the_window_says_the_comparison_in_one_short_line(tmp_path):
    cell = _cell(tmp_path / "cell")
    assert describe_since(_run(cell, tmp_path / "out")) == []
    line = describe_since(_run(cell, tmp_path / "out", karel=True))
    assert len(line) == 1 and line[0].startswith("Since the previous conversion: TODO ") and line[0].isascii()
    assert line[0].endswith("(options differ: --karel: now only).")
