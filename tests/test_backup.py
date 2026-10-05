# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Backup detection, zip handling and the full pipeline, on a synthetic two-robot backup."""

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from crossarm.backup import find_backup_root, open_source
from crossarm.convert import ConversionConfig
from crossarm.convert.html import markdown_to_html
from crossarm.pipeline import run, unique_folder

DATA_MODULE = (
    "MODULE Cell_Data(SYSMODULE)\n"
    "  CONST robtarget pHome:=[[600,0,900],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];\n"
    "  PROC Util()\n  ENDPROC\n"
    "ENDMODULE\n"
)


def program(name: str, output: str) -> str:
    return f"MODULE {name}\n  PROC main()\n    MoveJ pHome,v1000,fine,tool0;\n    Set {output};\n  ENDPROC\nENDMODULE\n"


def make_backup(root: Path) -> Path:
    """Two tasks, folders numbered like a real controller (TASK1 = T_ROB1, TASK2 = T_ROB2)."""
    (root / "BACKINFO").mkdir(parents=True)
    (root / "BACKINFO" / "backinfo.txt").write_text(
        ">>SYSTEM_ID:\nCell\n\n>>TASK1: (T_ROB1,,)\nSYSMOD/Cell_Data.sys @\n\n>>TASK2: (T_ROB2,,)\n\n>>EOF:\n"
    )
    for task, robot in (("TASK1", "Robot1"), ("TASK2", "Robot2")):
        (root / "RAPID" / task / "PROGMOD").mkdir(parents=True)
        (root / "RAPID" / task / "SYSMOD").mkdir(parents=True)
        (root / "RAPID" / task / "PROGMOD" / f"{robot}.mod").write_text(program(robot, "gripClose"))
        (root / "RAPID" / task / "SYSMOD" / "Cell_Data.sys").write_text(DATA_MODULE)
    (root / "SYSPAR").mkdir()
    (root / "SYSPAR" / "EIO.cfg").write_text('EIO_SIGNAL:\n\n  -Name "gripClose" -SignalType "DO" -DeviceMap "4"\n')
    (root / "HOME").mkdir()
    (root / "HOME" / "notes.txt").write_text("not RAPID")
    (root / "users.bin").write_bytes(b"\x00\x01")
    return root


def zip_folder(folder: Path, archive: Path) -> Path:
    with zipfile.ZipFile(archive, "w") as z:
        for path in folder.rglob("*"):
            z.write(path, path.relative_to(folder.parent))  # keeps the top folder, like Windows "Send to zip"
    return archive


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_backup_is_split_by_task_with_controller_names(tmp_path):
    backup = make_backup(tmp_path / "Cell_2026")
    with open_source([backup]) as source:
        assert (source.kind, source.name) == ("backup", "Cell_2026")
        assert [t.name for t in source.tasks] == ["T_ROB1", "T_ROB2"]
        task = source.tasks[0]
        assert [p.name for p in task.program_files] == ["Robot1.mod"]
        assert [p.name for p in task.data_files] == ["Cell_Data.sys"]
        assert source.eio == backup / "SYSPAR" / "EIO.cfg"


def test_picking_the_rapid_folder_finds_the_backup(tmp_path):
    backup = make_backup(tmp_path / "Cell")
    with open_source([backup / "RAPID"]) as source:
        assert source.kind == "backup" and len(source.tasks) == 2


def test_task_folder_name_is_kept_without_backinfo(tmp_path):
    backup = make_backup(tmp_path / "Cell")
    (backup / "BACKINFO" / "backinfo.txt").unlink()
    with open_source([backup]) as source:
        assert [t.name for t in source.tasks] == ["TASK1", "TASK2"]


def test_zipped_backup_is_extracted_then_cleaned_up(tmp_path):
    archive = zip_folder(make_backup(tmp_path / "Cell"), tmp_path / "Cell_backup.zip")
    with open_source([archive]) as source:
        assert (source.kind, source.name, source.location) == ("backup", "Cell_backup", tmp_path)
        extracted = source.tasks[0].program_files[0]
        assert extracted.exists()
    assert not extracted.exists()


def test_zip_slip_is_refused(tmp_path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../outside.mod", "MODULE X\nENDMODULE\n")
    with pytest.raises(ValueError, match="unsafe path"), open_source([archive]):
        pass
    assert not (tmp_path / "outside.mod").exists()


def test_loose_files_make_one_task(tmp_path):
    a = tmp_path / "a.mod"
    a.write_text(program("A", "doA"))
    with open_source([a]) as source:
        assert (source.kind, source.name, [t.name for t in source.tasks]) == ("files", "a", ["files"])


def test_not_a_backup_folder(tmp_path):
    assert find_backup_root(tmp_path) is None


def test_missing_input(tmp_path):
    with pytest.raises(FileNotFoundError), open_source([tmp_path / "nope"]):
        pass


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def test_full_backup_conversion(tmp_path):
    backup = make_backup(tmp_path / "Cell")
    logs: list[str] = []
    result = run([backup], log=logs.append)

    assert result.folder == tmp_path / "crossarm_Cell"  # next to the backup
    assert [t.task for t in result.tasks] == ["T_ROB1", "T_ROB2"]
    # System module routines are not converted; data (pHome) is still resolved. Both tasks have a
    # main: one controller, one name space, so the second is written MAIN_2 rather than replace MAIN.
    # Each robot gets the program that sets its frames, named apart the same way.
    for task, program, setup in (("T_ROB1", "MAIN.LS", "SETUP_FRAMES.LS"), ("T_ROB2", "MAIN_2.LS", "SETUP_FRAMES_2.LS")):
        files = sorted(p.name for p in (result.folder / task).iterdir())
        assert files == [program, setup, "crossarm_mapping.json", "crossarm_report.html", "crossarm_report.md"]
    ls = (result.folder / "T_ROB1" / "MAIN.LS").read_text(encoding="ascii")
    assert "DO[1]=ON" in ls and "J P[1]" in ls
    assert result.todo == 0
    assert any("EIO.cfg" in line for line in logs)
    detail = (result.folder / "T_ROB1" / "crossarm_report.md").read_text(encoding="utf-8")
    assert "EIO.cfg: DO" in detail


def test_second_run_never_overwrites(tmp_path):
    backup = make_backup(tmp_path / "Cell")
    first, second = run([backup], log=lambda _: None), run([backup], log=lambda _: None)
    assert (first.folder.name, second.folder.name) == ("crossarm_Cell", "crossarm_Cell_2")
    assert unique_folder(tmp_path / "fresh") == tmp_path / "fresh"


def test_syntax_errors_are_reported_not_fatal(tmp_path):
    bad = tmp_path / "bad.mod"
    bad.write_text("MODULE Bad\n  PROC main()\n    x := ;\n    Stop;\n  ENDPROC\nENDMODULE\n")
    result = run([bad], log=lambda _: None)
    assert result.programs == 1
    assert result.tasks[0].syntax_errors
    assert "Syntax errors" in (result.folder / "crossarm_report.md").read_text(encoding="utf-8")


def test_no_rapid_file(tmp_path):
    (tmp_path / "readme.txt").write_text("hello")
    with pytest.raises(ValueError, match="no RAPID module"):
        run([tmp_path], log=lambda _: None)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------


def test_html_report_renders_the_markdown_subset():
    md = (
        "# Title <x>\n\n> **Warning** text\n\n- item `a|b`\n\n"
        "| Program | Kind | Detail |\n|---|---|---|\n| MAIN | TODO | pipe \\| inside |\n\n_None._\n"
    )
    page = markdown_to_html(md, "t")
    assert "<h1>Title &lt;x&gt;</h1>" in page
    assert "<blockquote><p><strong>Warning</strong> text</p></blockquote>" in page
    assert "<li>item <code>a|b</code></li>" in page
    assert '<td class="kind-TODO">TODO</td>' in page
    assert "<td>pipe | inside</td>" in page
    assert '<p class="muted">None.</p>' in page


# ---------------------------------------------------------------------------
# One controller: registers, flags and I/O are numbered across its tasks
# ---------------------------------------------------------------------------


def two_task_backup(root: Path, rob1: str, rob2: str, data: str = "") -> Path:
    backup = make_backup(root)
    for task, body in (("TASK1", rob1), ("TASK2", rob2)):
        (backup / "RAPID" / task / "PROGMOD" / f"Robot{task[-1]}.mod").write_text(
            f"MODULE Robot{task[-1]}\n{data}\n  PROC main()\n{body}\n  ENDPROC\nENDMODULE\n"
        )
    return backup


def mapping(result, task: str) -> dict:
    import json

    return json.loads((result.folder / task / "crossarm_mapping.json").read_text(encoding="utf-8"))


def test_tasks_of_one_backup_never_share_a_number_for_different_data(tmp_path):
    """A background task and the motion task must not both get DO[1]."""
    backup = two_task_backup(
        tmp_path / "Cell",
        "    Set doClamp;\n    nParts:=nParts+1;",
        "    Set doLamp;\n    nCycles:=nCycles+1;",
        "  PERS num nParts:=0;\n  PERS num nCycles:=0;",
    )
    result = run([backup], log=lambda _: None)
    rob1, rob2 = mapping(result, "T_ROB1"), mapping(result, "T_ROB2")
    assert rob1["digital_outputs"] == {"doClamp": 1}
    assert rob2["digital_outputs"] == {"doLamp": 2}
    assert set(rob1["registers"].values()).isdisjoint(rob2["registers"].values())


def test_a_name_used_by_several_tasks_keeps_one_number(tmp_path):
    """A PERS shared between tasks is one variable in RAPID; one signal is one output."""
    backup = two_task_backup(
        tmp_path / "Cell",
        "    Set gripClose;\n    nShared:=nShared+1;",
        "    Set gripClose;\n    nShared:=nShared+2;",
        "  PERS num nShared:=0;",
    )
    result = run([backup], log=lambda _: None)
    rob1, rob2 = mapping(result, "T_ROB1"), mapping(result, "T_ROB2")
    assert rob1["digital_outputs"] == rob2["digital_outputs"] == {"gripClose": 1}
    assert rob1["registers"] == rob2["registers"] == {"nShared": 1}


def test_frames_stay_per_robot(tmp_path):
    """Each robot of a multi-robot cell has its own tool frames: both start at 1."""
    tool = "  PERS tooldata tGun:=[TRUE,[[0,0,200],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];"
    backup = two_task_backup(tmp_path / "Cell", "    MoveJ pHome,v100,fine,tGun;", "    MoveJ pHome,v100,fine,tGun;", tool)
    result = run([backup], log=lambda _: None)
    assert mapping(result, "T_ROB1")["utools"] == mapping(result, "T_ROB2")["utools"] == {"tGun": 1}


def test_each_report_lists_only_its_task_and_says_numbering_is_shared(tmp_path):
    backup = two_task_backup(tmp_path / "Cell", "    Set doClamp;", "    Set doLamp;")
    result = run([backup], log=lambda _: None)
    report = (result.folder / "T_ROB2" / "crossarm_report.md").read_text(encoding="utf-8")
    assert "doLamp" in report and "doClamp" not in report
    assert "Numbered together with T_ROB1" in report


# ---------------------------------------------------------------------------
# One controller, one name space: a program never replaces another
# ---------------------------------------------------------------------------


def target_robot(root: Path, *names: str) -> Path:
    """A FANUC backup holding empty programs with these names."""
    from crossarm.fanuc.ls_writer import write_ls
    from crossarm.fanuc.tp import Attributes, Program

    root.mkdir()
    for name in names:
        program = Program(name, attributes=Attributes(created=__import__("datetime").datetime(2026, 1, 1)))
        (root / f"{name}.LS").write_text(write_ls(program), encoding="ascii", newline="")
    return root


def test_a_program_already_on_the_robot_is_not_replaced(tmp_path):
    """Measured: a routine main gave MAIN.LS for a robot that already had MAIN, with no warning."""
    source = tmp_path / "cell.mod"
    source.write_text("MODULE Cell\n  PROC main()\n    Stop;\n  ENDPROC\n  PROC pick()\n    Stop;\n  ENDPROC\nENDMODULE\n")
    result = run([source, target_robot(tmp_path / "robot", "MAIN", "HOME")], log=lambda _: None)
    written = sorted(p.name for p in result.folder.glob("*.LS"))
    assert written == ["MAIN_2.LS", "PICK.LS"]
    [note] = [n for n in result.tasks[0].result.notes if n.category.startswith("program renamed")]
    assert note.message == ("routine main written as MAIN_2.LS: the FANUC robot already has a program MAIN,"
                            " which loading it would replace")  # fmt: skip


def test_calls_follow_the_new_name(tmp_path):
    source = tmp_path / "cell.mod"
    source.write_text("MODULE Cell\n  PROC run()\n    main;\n  ENDPROC\n  PROC main()\n    Stop;\n  ENDPROC\nENDMODULE\n")
    result = run([source, target_robot(tmp_path / "robot", "MAIN")], log=lambda _: None)
    assert "CALL MAIN_2" in (result.folder / "RUN.LS").read_text(encoding="ascii")


def test_routines_that_are_not_written_claim_no_name(tmp_path):
    """System-module utilities are data only: they must not push a program aside."""
    backup = make_backup(tmp_path / "Cell")  # Cell_Data.sys holds PROC Util, not converted
    (backup / "RAPID" / "TASK2" / "PROGMOD" / "Robot2.mod").write_text(
        "MODULE Robot2\n  PROC util()\n    Stop;\n  ENDPROC\nENDMODULE\n"
    )
    result = run([backup], log=lambda _: None)
    assert (result.folder / "T_ROB2" / "UTIL.LS").exists()


# ---------------------------------------------------------------------------
# Loose files holding several tasks or versions
# ---------------------------------------------------------------------------


def variants(root: Path) -> Path:
    """A project with a folder per robot task, in two versions, and a module they all use."""
    for version in ("Version_1", "Version_2"):
        for task in ("T_ROB_L", "T_ROB_R"):
            folder = root / "RAPID" / version / task
            folder.mkdir(parents=True)
            (folder / "Module1.mod").write_text(program("Module1", "gripClose"))
    (root / "RAPID" / "Common.sys").write_text(DATA_MODULE)  # in each task: data only
    return root


def test_modules_of_one_name_in_several_folders_make_a_task_per_folder(tmp_path):
    with open_source([variants(tmp_path / "project")]) as source:
        tasks = {t.name: sorted(p.name for p in t.program_files) for t in source.tasks}
    assert tasks == {f"{v}/{t}": ["Common.sys", "Module1.mod"] for v in ("Version_1", "Version_2")
                     for t in ("T_ROB_L", "T_ROB_R")}  # fmt: skip


def test_the_split_looks_through_a_folder_all_the_modules_are_in(tmp_path):
    """Cell_A/Programs/ holds both controllers: a task per controller folder, each named as far down as it takes."""
    for folder in ("Cell_A/Programs/Robot1/T_ROB1", "Cell_A/Programs/Robot2/T_ROB1", "Cell_B/Programs/T_ROB1"):
        (tmp_path / folder).mkdir(parents=True)
        (tmp_path / folder / "Module1.mod").write_text(program("Module1", "doA"))
    with open_source([tmp_path]) as source:
        assert [t.name for t in source.tasks] == ["Cell_A/Programs/Robot1", "Cell_A/Programs/Robot2",
                                                  "Cell_B"]  # fmt: skip


def test_modules_spread_over_folders_with_distinct_names_stay_one_task(tmp_path):
    for folder, module in (("server", "Server"), ("client", "Client")):
        (tmp_path / "lib" / folder).mkdir(parents=True)
        (tmp_path / "lib" / folder / f"{module}.mod").write_text(program(module, "doA"))
    with open_source([tmp_path / "lib"]) as source:
        assert [(t.name, len(t.files)) for t in source.tasks] == [("files", 2)]


def test_every_program_of_every_folder_is_written(tmp_path):
    """Before, the four MAIN programs were written over one another: four announced, one file."""
    result = run([variants(tmp_path / "project")], log=lambda _: None)
    written = sorted(p.relative_to(result.folder).as_posix() for p in result.folder.rglob("*.LS"))
    assert result.programs == 4
    assert [w for w in written if "SETUP" not in w] == [
        "Version_1/T_ROB_L/MAIN.LS", "Version_1/T_ROB_R/MAIN_2.LS", "Version_2/T_ROB_L/MAIN_3.LS",
        "Version_2/T_ROB_R/MAIN_4.LS"]  # fmt: skip


def test_a_routine_name_two_modules_declare_is_written_once(tmp_path):
    """The one converted is the first by path, whatever the order the files are given in."""
    for module in ("First", "Second"):
        (tmp_path / f"{module}.mod").write_text(
            f"MODULE {module}\n  LOCAL PROC main()\n    Stop;\n  ENDPROC\nENDMODULE\n")
    result = run([tmp_path / "Second.mod", tmp_path / "First.mod"], log=lambda _: None)
    assert [p.name for p in result.folder.glob("*.LS")] == ["MAIN.LS"]
    assert result.tasks[0].result.skipped_routines == [
        ("Second", "main", ("First has a routine of the same name, converted: routines of one name in several "
                            "modules are not"))]  # fmt: skip


# ---------------------------------------------------------------------------
# What 1.x keeps: a loose folder of distinct modules converts as 1.2 did
# ---------------------------------------------------------------------------

LOOSE_1_2 = Path(__file__).parent / "fixtures" / "rapid" / "loose_project_1_2"  # written by CrossArm 1.2.0


def loose_project(root: Path, fixtures_dir: Path) -> Path:
    """Three modules of distinct names in subfolders: the case most loose folders are."""
    for name, folder in (("pick_and_place.mod", "cell"), ("logic_and_io.mod", "cell/logic"),
                         ("hmi_and_groups.mod", "hmi")):  # fmt: skip
        (root / folder).mkdir(parents=True, exist_ok=True)
        shutil.copy(fixtures_dir / "rapid" / name, root / folder / name)
    return root


@pytest.fixture
def evaluation(tmp_path, monkeypatch):
    """No licence: 1.2.0 wrote these programs as an evaluation copy."""
    monkeypatch.setenv("CROSSARM_LICENCE", str(tmp_path / "no.licence"))


def programs(folder: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in folder.glob("*.LS")}


def numbers(folder: Path) -> dict[str, dict[str, int]]:
    """Each table of the mapping file, by RAPID name: 1.3 names a routine's counter Routine.k, 1.2 named it k.
    Not the names of the programs (programs), which 1.3 adds: those of the files written."""
    data = json.loads((folder / "crossarm_mapping.json").read_text(encoding="utf-8"))
    if "programs" in data:
        assert {f"{name}.LS" for name in data.pop("programs").values()} <= set(programs(folder))
    return {table: {key.split(".")[-1].upper(): n for key, n in values.items()}
            for table, values in data.items() if isinstance(values, dict)}  # fmt: skip


def test_a_loose_folder_of_distinct_modules_converts_as_1_2_did(tmp_path, fixtures_dir, evaluation):
    """One task, programs in the output folder itself, the same programs and numbers as 1.2.0 wrote."""
    project = loose_project(tmp_path / "project", fixtures_dir)
    result = run([project], config=ConversionConfig(timestamp=datetime(2026, 1, 1)), log=lambda _: None)
    assert ([t.task for t in result.tasks], result.folder) == (["files"], tmp_path / "crossarm_project")
    assert programs(result.folder) == programs(LOOSE_1_2)
    assert numbers(result.folder) == numbers(LOOSE_1_2)


def test_the_mapping_1_2_wrote_given_back_gives_the_same_numbers(tmp_path, fixtures_dir, evaluation):
    project = loose_project(tmp_path / "project", fixtures_dir)
    config = ConversionConfig.from_mapping_file(LOOSE_1_2 / "crossarm_mapping.json", timestamp=datetime(2026, 1, 1))
    result = run([project], config=config, log=lambda _: None)
    # 1.2.0 itself did not: the FOR counters and CrossArm's own registers it named by their RAPID name
    # only were numbered again, past every number of the file.
    assert programs(result.folder) == programs(LOOSE_1_2)
    assert numbers(result.folder) == numbers(LOOSE_1_2)


def test_the_mapping_written_now_given_back_gives_the_same_files(tmp_path, fixtures_dir, evaluation):
    project = loose_project(tmp_path / "project", fixtures_dir)
    first = run([project], config=ConversionConfig(timestamp=datetime(2026, 1, 1)), log=lambda _: None)
    mapping = json.loads((first.folder / "crossarm_mapping.json").read_text(encoding="utf-8"))
    assert (mapping["registers"]["COUNTDOWN.k"], mapping["registers"]["CROSSARM.NUMBERINDEX"]) == (5, 10)
    config = ConversionConfig.from_mapping_file(first.folder / "crossarm_mapping.json",
                                                timestamp=datetime(2026, 1, 1))  # fmt: skip
    second = run([project], config=config, log=lambda _: None)
    assert programs(second.folder) == programs(first.folder)
    assert (second.folder / "crossarm_mapping.json").read_bytes() == (first.folder / "crossarm_mapping.json").read_bytes()
