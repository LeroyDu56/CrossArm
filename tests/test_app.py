# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Desktop entry point without a window (the GUI itself needs a display)."""

from crossarm.app import main


def test_headless_conversion_of_dropped_files(tmp_path, fixtures_dir, monkeypatch, capsys):
    source = tmp_path / "pick_and_place.mod"
    source.write_bytes((fixtures_dir / "rapid" / "pick_and_place.mod").read_bytes())
    monkeypatch.setenv("CROSSARM_NO_GUI", "1")
    assert main([str(source)]) == 0
    assert (tmp_path / "crossarm_pick_and_place" / "MAIN.LS").exists()
    assert "3 programs" in capsys.readouterr().out


def test_target_fanuc_backup_dropped_on_the_icon_with_the_abb_one(tmp_path, fixtures_dir, monkeypatch, capsys):
    """What Windows passes when both backups are dropped on CrossArm.exe together."""
    source = tmp_path / "logic_and_io.mod"
    source.write_bytes((fixtures_dir / "rapid" / "logic_and_io.mod").read_bytes())
    target = tmp_path / "fanuc_target"
    target.mkdir()
    for ls in (fixtures_dir / "fanuc" / "roboguide_export").glob("*.LS"):
        (target / ls.name).write_bytes(ls.read_bytes())
    monkeypatch.setenv("CROSSARM_NO_GUI", "1")
    assert main([str(source), str(target)]) == 0
    out = capsys.readouterr().out
    assert "Existing FANUC programs: 6 read" in out
    assert "2 programs" in out  # the FANUC programs were read, not converted
    assert "| Taken |" in (tmp_path / "crossarm_logic_and_io" / "crossarm_report.md").read_text(encoding="utf-8")


def test_icon_data_is_valid_png_and_the_exe_icon_holds_every_size():
    """tools/make_icon.py writes both; a truncated file would only show as a blank icon."""
    import base64
    import struct

    from helpers import FIXTURES

    from crossarm._icon import PNG

    for size, data in PNG.items():
        raw = base64.b64decode(data)
        assert raw.startswith(b"\x89PNG\r\n\x1a\n")
        assert struct.unpack(">II", raw[16:24]) == (size, size)
    ico = (FIXTURES.parents[1] / "packaging" / "crossarm.ico").read_bytes()
    reserved, kind, count = struct.unpack("<HHH", ico[:6])
    assert (reserved, kind, count) == (0, 1, 7)
