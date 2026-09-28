# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""What a user can send when something goes wrong: the conversion log and the error report."""

from crossarm import __version__
from crossarm.pipeline import run
from crossarm.support import environment, write_error_report


def test_every_conversion_leaves_a_log_next_to_its_report(tmp_path, fixtures_dir):
    source = tmp_path / "pick_and_place.mod"
    source.write_bytes((fixtures_dir / "rapid" / "pick_and_place.mod").read_bytes())
    result = run([source], log=lambda _: None)
    log = (result.folder / "crossarm_log.txt").read_text(encoding="utf-8")
    assert f"CrossArm {__version__}" in log
    assert f"input: {source}" in log
    assert "target FANUC backup: none" in log
    assert "files: 3 programs, 7 TODO, 5 warnings" in log  # what the conversion said, as it said it


def test_a_backup_log_sits_above_the_task_folders(tmp_path):
    from test_backup import make_backup

    result = run([make_backup(tmp_path / "Cell")], log=lambda _: None)
    assert (result.folder / "crossarm_log.txt").exists()
    assert "T_ROB2: 1 programs" in (result.folder / "crossarm_log.txt").read_text(encoding="utf-8")


def test_an_error_report_keeps_the_whole_traceback(tmp_path):
    def inner():
        raise KeyError("missing piece")

    try:
        inner()
    except KeyError as exc:
        path = write_error_report(exc, {"stage": "convert", "input": "cell.mod"}, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert path.name == "crossarm_error.txt"
    assert environment() in text
    assert "stage: convert" in text and "input: cell.mod" in text
    assert "in inner" in text and "KeyError: 'missing piece'" in text


def test_environment_names_the_version_and_the_system():
    text = environment()
    assert text.startswith(f"CrossArm {__version__} · Python ")
