# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

import json

from crossarm.cli import main


def test_parse_pseudo(fixtures_dir, capsys):
    assert main(["parse", str(fixtures_dir / "rapid" / "pick_and_place.mod")]) == 0
    out = capsys.readouterr().out
    assert "MOVE C     via=pArcMid  to=pArcEnd" in out
    assert "?? [RECORD]" in out


def test_parse_json_to_file(fixtures_dir, tmp_path):
    out = tmp_path / "out.json"
    assert main(["parse", str(fixtures_dir / "rapid" / "legacy_header.mod"), "--format", "json", "-o", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["encoding"] == "cp1252"
    assert data["module"]["name"] == "Legacy_Palette"


def test_parse_reports_errors_with_exit_code(tmp_path, capsys):
    bad = tmp_path / "bad.mod"
    bad.write_text("MODULE B\nPROC p()\n  x := ;\nENDPROC\nENDMODULE\n", encoding="utf-8")
    assert main(["parse", str(bad)]) == 1
    assert "3:" in capsys.readouterr().err


def test_missing_file(tmp_path, capsys):
    assert main(["parse", str(tmp_path / "nope.mod")]) == 2


def test_stats(fixtures_dir, capsys):
    assert main(["stats", str(fixtures_dir / "rapid")]) == 0
    out = capsys.readouterr().out
    count = len(list((fixtures_dir / "rapid").glob("*.mod")))
    assert f"{count} files, 0 errors" in out
    assert "ERROR_HANDLER" in out


def test_convert_writes_ls_files_and_report(fixtures_dir, tmp_path, capsys):
    out = tmp_path / "out"
    assert main(["convert", str(fixtures_dir / "rapid" / "pick_and_place.mod"), "-o", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == [
        "MAIN.LS", "PICK.LS", "PLACE.LS", "SETUP_FRAMES.LS", "crossarm_log.txt", "crossarm_mapping.json", "crossarm_report.html",
        "crossarm_report.md",
    ]  # fmt: skip
    assert (out / "MAIN.LS").read_bytes().startswith(b"/PROG  MAIN\r\n")
    assert "3 programs, 7 TODO" in capsys.readouterr().out


def test_convert_single_routine_with_mapping(fixtures_dir, tmp_path):
    mapping = tmp_path / "map.json"
    mapping.write_text('{"digital_outputs": {"DO_GripperClose": 7}}', encoding="utf-8")
    out = tmp_path / "out"
    args = ["convert", str(fixtures_dir / "rapid"), "-o", str(out), "--routine", "Pick", "--map", str(mapping)]
    assert main(args) == 0
    assert "DO[7]=ON" in (out / "PICK.LS").read_text(encoding="ascii")
    assert not (out / "MAIN.LS").exists()
