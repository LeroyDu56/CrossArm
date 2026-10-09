# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A mapping file given back gives the programs it was written with (the 1.x promise).

Frames past what the controller holds are kept in position registers ("banks") and loaded into one
reserved number before use; the mapping file names them by the numbers past the limit they were
counted as. Up to 1.7 those numbers, given back, were selected directly (`UTOOL_NUM=11`, refused by
the controller): they mean banks, as in the conversion that wrote them.

A backup of several tasks has a mapping file per task, and one file is given back to the whole backup. Up to 1.7
its program names applied to the routines of those names in every task: the MAIN of the other tasks was renamed
(MAIN_2_2). They now name the programs of the task the file was written for only ("task", or the task folder it
was read from, or the only task declaring every routine it names).
"""

import json
import re
from pathlib import Path

import pytest

from crossarm import pipeline
from crossarm.convert import ConversionConfig

REPO = Path(__file__).resolve().parents[2]
BACKUPS = sorted(p for p in (REPO / "abb").glob("*") if p.is_dir()) if (REPO / "abb").is_dir() else []
STAMP = re.compile(r"^(CREATE|MODIFIED)\s*=.*$", re.MULTILINE)


def _module() -> str:
    lines = ["MODULE Banks"]
    lines += [f"PERS tooldata tBankT{i}:=[TRUE,[[0,0,{100 + i}],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];"
              for i in range(1, 13)]  # fmt: skip
    lines += [f'PERS wobjdata wBankW{i}:=[FALSE,TRUE,"",[[{i * 10},0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];'
              for i in range(1, 12)]  # fmt: skip
    lines += ["CONST robtarget pBank:=[[500,0,500],[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];", "PROC main()"]
    lines += [f"  MoveL pBank,v100,fine,tBankT{i}\\WObj:=wBankW{(i - 1) % 11 + 1};" for i in range(1, 13)]
    return "\n".join([*lines, "ENDPROC", "ENDMODULE", ""])


# What CrossArm 1.0 to 1.7 wrote for that module: 12 tools and 11 work objects on a controller of 10 and 9.
WRITTEN_BY_1_0 = {
    "uframes": {**{f"wBankW{i}": i for i in range(1, 9)}, "wBankW9": 10, "wBankW10": 11, "wBankW11": 12},
    "utools": {**{f"tBankT{i}": i for i in range(1, 10)}, "tBankT10": 11, "tBankT11": 12, "tBankT12": 13},
    "limits": {"UFRAME": 9, "UTOOL": 10, "TIMER": 10, "R": 200, "PR": 100, "F": 1024},
}


def _programs(folder: Path) -> dict[str, str]:
    return {str(f.relative_to(folder)): STAMP.sub("", f.read_text(encoding="utf-8")) for f in folder.rglob("*.LS")}


def _run(paths: list[Path], out: Path, mapping: Path | None = None) -> pipeline.RunOutput:
    config = ConversionConfig.from_mapping_file(mapping) if mapping else None
    return pipeline.run(paths, output=out, config=config, log=lambda _: None)


def test_a_mapping_written_by_an_earlier_version_still_means_banks(tmp_path):
    source = tmp_path / "Banks.mod"
    source.write_text(_module(), encoding="utf-8")
    first = _run([source], tmp_path / "a")
    written = json.loads((tmp_path / "a" / "crossarm_mapping.json").read_text(encoding="utf-8"))
    assert {k: written[k] for k in WRITTEN_BY_1_0} == WRITTEN_BY_1_0  # the file says what it always said

    old = tmp_path / "old.json"
    old.write_text(json.dumps(WRITTEN_BY_1_0), encoding="utf-8")
    _run([source], tmp_path / "b", old)
    main = _programs(tmp_path / "b")["MAIN.LS"]
    assert "UTOOL_NUM=11" not in main and "UFRAME_NUM=10" not in main
    assert re.search(r"UTOOL\[10\]=PR\[\d+\]", main) and re.search(r"UFRAME\[9\]=PR\[\d+\]", main)
    assert _programs(tmp_path / "b") == _programs(tmp_path / "a")
    assert first.tasks[0].todo == 0


def _two_tasks(root: Path, own_routine: bool = False) -> Path:
    """Two task folders with modules of the same names: two tasks, each with its main."""
    for task in ("TaskA", "TaskB"):
        extra = "  PickB;\n" if own_routine and task == "TaskB" else ""
        body = ("MODULE MainMod\nVAR num nCount:=0;\nPROC main()\n  nCount:=nCount+1;\n" + extra + "ENDPROC\n")
        if own_routine and task == "TaskB":
            body += "PROC PickB()\n  nCount:=0;\nENDPROC\n"
        (root / "cell" / task).mkdir(parents=True, exist_ok=True)
        (root / "cell" / task / "MainMod.mod").write_text(body + "ENDMODULE\n", encoding="utf-8")
    return root / "cell"


def test_a_task_mapping_given_back_names_that_task_programs_only(tmp_path):
    cell = _two_tasks(tmp_path)
    first = _run([cell], tmp_path / "a")
    assert sorted(_programs(tmp_path / "a")) == [str(Path("TaskA", "MAIN.LS")), str(Path("TaskB", "MAIN_2.LS"))]
    for task in first.tasks:
        written = json.loads((task.folder / "crossarm_mapping.json").read_text(encoding="utf-8"))
        assert written["task"] == task.task
        _run([cell], tmp_path / f"b_{task.task}", task.folder / "crossarm_mapping.json")
        assert _programs(tmp_path / f"b_{task.task}") == _programs(tmp_path / "a"), task.task

    # Written before 1.8 (no "task") and moved out of its folder: the routines it names are in both tasks.
    old = json.loads((tmp_path / "a" / "TaskB" / "crossarm_mapping.json").read_text(encoding="utf-8"))
    del old["task"], old["_task"]
    (tmp_path / "old.json").write_text(json.dumps(old), encoding="utf-8")
    again = _run([cell], tmp_path / "c", tmp_path / "old.json")
    assert sorted(_programs(tmp_path / "c")) == [str(Path("TaskA", "MAIN_2.LS")), str(Path("TaskB", "MAIN_2_2.LS"))]
    assert all(any('add "task"' in n.message.lower() for n in t.result.notes) for t in again.tasks)
    # Given in its folder, it is that task's.
    _run([cell], tmp_path / "d", tmp_path / "a" / "TaskB" / "crossarm_mapping.json")
    assert _programs(tmp_path / "d") == _programs(tmp_path / "a")


def test_an_older_task_mapping_is_known_by_its_routines(tmp_path):
    cell = _two_tasks(tmp_path, own_routine=True)
    _run([cell], tmp_path / "a")
    old = json.loads((tmp_path / "a" / "TaskB" / "crossarm_mapping.json").read_text(encoding="utf-8"))
    del old["task"], old["_task"]
    (tmp_path / "old.json").write_text(json.dumps(old), encoding="utf-8")
    again = _run([cell], tmp_path / "b", tmp_path / "old.json")
    assert _programs(tmp_path / "b") == _programs(tmp_path / "a")
    assert not any("mapping file" in n.message for t in again.tasks for n in t.result.notes)


def test_a_single_task_mapping_has_no_task(tmp_path):
    source = tmp_path / "Banks.mod"
    source.write_text(_module(), encoding="utf-8")
    _run([source], tmp_path / "a")
    assert "task" not in json.loads((tmp_path / "a" / "crossarm_mapping.json").read_text(encoding="utf-8"))


@pytest.mark.skipif(not BACKUPS, reason="no local test corpus")
@pytest.mark.parametrize("backup", BACKUPS, ids=lambda p: p.name)
def test_every_backup_given_its_mapping_back_gives_the_same_programs(backup, tmp_path):
    """Each task's file given back to the whole backup gives every task's programs, names included."""
    first = _run([backup], tmp_path / "a")
    before = _programs(tmp_path / "a")
    for task in first.tasks:
        _run([backup], tmp_path / f"b_{task.task}", task.folder / "crossarm_mapping.json")
        assert _programs(tmp_path / f"b_{task.task}") == before, task.task
