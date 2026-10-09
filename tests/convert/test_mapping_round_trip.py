# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A mapping file given back gives the programs it was written with (the 1.x promise).

Frames past what the controller holds are kept in position registers ("banks") and loaded into one
reserved number before use; the mapping file names them by the numbers past the limit they were
counted as. Up to 1.7 those numbers, given back, were selected directly (`UTOOL_NUM=11`, refused by
the controller): they mean banks, as in the conversion that wrote them.
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


@pytest.mark.skipif(not BACKUPS, reason="no local test corpus")
@pytest.mark.parametrize("backup", BACKUPS, ids=lambda p: p.name)
def test_every_backup_given_its_mapping_back_gives_the_same_programs(backup, tmp_path):
    """Each task's file given back gives that task's programs. One file is given to every task of the backup, so a
    routine of another task with the same name takes the name the file pins: programs are matched by routine."""
    first = _run([backup], tmp_path / "a")
    for task in first.tasks:
        mapping = task.folder / "crossarm_mapping.json"
        again = _run([backup], tmp_path / f"b_{task.task}", mapping)
        other = next(t for t in again.tasks if t.task == task.task)
        names = {first_name: other.result.program_keys.get(key, first_name)
                 for key, first_name in task.result.program_keys.items()}  # fmt: skip
        before = _programs(task.folder)
        after = _programs(other.folder)
        renamed = {}
        for name, text in before.items():
            stem = name[:-3]
            for old_name, new_name in names.items():
                text = re.sub(rf"\b{re.escape(old_name)}\b", new_name, text)
            renamed[names.get(stem, stem) + ".LS"] = text
        assert renamed == after, task.task
