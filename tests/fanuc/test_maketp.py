# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Binary .TP files through FANUC MakeTP: never run here, the subprocess is a stand-in.

What MakeTP does and prints was measured with ROBOGUIDE V10.10 (tools/make_maketp_probe.py)."""

import os
import subprocess
from pathlib import Path

import pytest

from crossarm import pipeline
from crossarm.cli import main
from crossarm.fanuc import maketp
from crossarm.fanuc.maketp import TpExport, TpRequest, check_robot, make_tp, neighborhood_name, reason, report_section
from crossarm.summary import GOOD, WARN, summarize

BANNER = "MakeTP V10.10-1, Copyright (C) 2004-2023, FANUC America Corporation.\n"
REFUSAL = (BANNER + "Error occurred during load\nC:\\Temp\\crossarm_maketp_x\\bad.ls(22)\non line 22, column 11\n"
           "Invalid encoding of line\nError executing MakeTP: Error translating program: Code: 0x160002:  \n")  # fmt: skip
UNKNOWN_ROBOT = (BANNER + "Error executing MakeTP: Internal error:\n\n-2147209132(0x80043054)\n\n"
                 "The requested item was not found\n")  # fmt: skip


@pytest.fixture
def winolpc(tmp_path):
    """A WinOLPC install (bin/maketp.exe, Versions/V1010-1) and a ROBOGUIDE cell with one V10.10 robot."""
    exe = tmp_path / "WinOLPC" / "bin" / "maketp.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    (tmp_path / "WinOLPC" / "Versions" / "V1010-1" / "bin").mkdir(parents=True)
    (tmp_path / "WinOLPC" / "Versions" / "V940-1" / "bin").mkdir(parents=True)
    robot = tmp_path / "Cell" / "Robot_1"
    robot.mkdir(parents=True)
    (robot / "frvirt.dat").write_text("V10.10270   V10.10270     9/11/2025\n/MC:\\x /N\n", encoding="ascii")
    return exe, robot


@pytest.fixture
def programs(tmp_path):
    folder = tmp_path / "ls"
    folder.mkdir()
    paths = []
    for name in ("MAIN", "BAD", "SETUP_FRAMES"):
        (folder / f"{name}.LS").write_text(f"/PROG  {name}\n/MN\n/POS\n/END\n", encoding="ascii")
        paths.append(folder / f"{name}.LS")
    return paths


class FakeMakeTP:
    """subprocess.run as MakeTP behaves: NAME.TP written in the current folder, or the refusal printed."""

    def __init__(self, refuse: dict[str, str] | None = None) -> None:
        self.refuse = refuse or {}
        self.calls: list[list[str]] = []
        self.ini = ""

    def __call__(self, args, cwd, **kwargs) -> subprocess.CompletedProcess:
        self.calls.append(args)
        self.ini = Path(args[4]).read_text(encoding="mbcs" if os.name == "nt" else "utf-8")
        name = args[1].removesuffix(".LS")
        if name in self.refuse:
            return subprocess.CompletedProcess(args, 2147745896, self.refuse[name], "")
        source = (Path(cwd) / args[1]).read_bytes()
        (Path(cwd) / args[2]).write_bytes(b"TP " + source[:10])
        return subprocess.CompletedProcess(args, 0, BANNER + "MakeTP completed.\n", "")


def test_robot_neighborhood_names_a_robot_by_its_path_with_the_drive_as_first_folder():
    assert neighborhood_name(Path("C:\\Users\\me\\Documents\\My Workcells\\Cell\\Robot_1")) == (
        "\\C\\Users\\me\\Documents\\My Workcells\\Cell\\Robot_1")  # fmt: skip


def test_a_roboguide_robot_gets_a_robot_ini_with_its_software_core(winolpc, programs, tmp_path):
    exe, robot = winolpc
    run = FakeMakeTP(refuse={"BAD": REFUSAL})
    export = make_tp(programs, tmp_path / "TP", TpRequest(robot.parent, maketp=exe), runner=run)  # the cell: its robot
    assert export.made == ["MAIN", "SETUP_FRAMES"] and not export.problem
    why = "Error occurred during load on line 22, column 11 Invalid encoding of line Error translating program: Code: 0x160002:"
    assert export.refused == [("BAD", why)]
    assert sorted(p.name for p in (tmp_path / "TP").iterdir()) == ["MAIN.TP", "SETUP_FRAMES.TP"]
    assert (tmp_path / "TP" / "MAIN.TP").read_bytes() == b"TP /PROG  MAI"
    lines = run.ini.splitlines()
    assert lines[0] == "[WinOLPC_Util]"
    assert lines[1] == "Robot=" + neighborhood_name(robot.resolve())
    assert lines[2] == "Version=V10.10-1"
    assert lines[3] == f"Path={exe.parent.parent / 'Versions' / 'V1010-1' / 'bin'}\\"
    assert lines[4:] == [f"Support={robot.resolve() / 'support'}\\", f"Output={robot.resolve() / 'output'}\\"]
    assert (robot / "support").is_dir() and (robot / "output").is_dir()  # MakeTP stops without them
    assert run.calls[0][:4] == [str(exe), "MAIN.LS", "MAIN.TP", "/config"]
    assert programs[0].read_text(encoding="ascii").startswith("/PROG  MAIN")  # the .LS stay as written


def test_a_robot_ini_given_is_used_as_it_is(winolpc, programs, tmp_path):
    exe, _ = winolpc
    ini = tmp_path / "robot.ini"
    ini.write_text("[WinOLPC_Util]\nRobot=\\C\\x\n", encoding="ascii")
    run = FakeMakeTP()
    export = make_tp(programs[:1], tmp_path / "TP", TpRequest(ini, maketp=exe), runner=run)
    assert export.made == ["MAIN"] and run.calls[0][4] == str(ini) and export.robot == str(ini)


def test_without_maketp_nothing_is_written_and_the_report_says_why(programs, tmp_path, monkeypatch):
    monkeypatch.setattr(maketp, "find_maketp", lambda: None)
    export = make_tp(programs, tmp_path / "TP", TpRequest(tmp_path), runner=FakeMakeTP())
    assert export.problem.startswith("FANUC MakeTP (maketp.exe) not found") and not export.made
    assert not (tmp_path / "TP").exists()
    section = report_section(export, "TP")
    assert "Not written: FANUC MakeTP (maketp.exe) not found" in section and "written as usual" in section


def test_without_a_robot_configuration_nothing_is_written(winolpc, programs, tmp_path, monkeypatch):
    exe, _ = winolpc
    monkeypatch.chdir(tmp_path)  # no robot.ini here
    export = make_tp(programs, tmp_path / "TP", TpRequest(None, maketp=exe), runner=FakeMakeTP())
    assert export.problem.startswith("no robot configuration")
    other = tmp_path / "not_a_robot"
    other.mkdir()
    export = make_tp(programs, tmp_path / "TP", TpRequest(other, maketp=exe), runner=FakeMakeTP())
    assert "not a ROBOGUIDE robot folder" in export.problem


def test_a_robot_of_a_software_winolpc_does_not_have_is_said(winolpc, programs, tmp_path):
    exe, robot = winolpc
    (robot / "frvirt.dat").write_text("V8.30187   x\n", encoding="ascii")
    export = make_tp(programs, tmp_path / "TP", TpRequest(robot, maketp=exe), runner=FakeMakeTP())
    assert export.problem.startswith("WinOLPC has no V8.30 core")


def test_a_configuration_maketp_cannot_use_is_said_once_not_for_every_program(winolpc, programs, tmp_path):
    exe, robot = winolpc
    run = FakeMakeTP(refuse={"MAIN": UNKNOWN_ROBOT})
    export = make_tp(programs, tmp_path / "TP", TpRequest(robot, maketp=exe), runner=run)
    assert len(run.calls) == 1 and not export.refused
    assert export.problem.startswith("the robot is unknown to FANUC Robot Neighborhood")
    assert "no .TP written" in export.summary()


def test_maketp_messages_lose_their_banner_and_temporary_path():
    assert reason(UNKNOWN_ROBOT) == "Internal error: -2147209132(0x80043054) The requested item was not found"
    assert reason("") == "no message"


def test_check_robot_says_at_once_what_is_not_a_robot(winolpc, tmp_path):
    _, robot = winolpc
    assert check_robot(robot) == "" and check_robot(robot.parent) == ""
    (robot.parent / "Robot_2").mkdir()
    (robot.parent / "Robot_2" / "frvirt.dat").write_text("V10.10270\n", encoding="ascii")
    assert "several robots" in check_robot(robot.parent)
    assert "nor a robot.ini" in check_robot(tmp_path / "missing")


def test_convert_with_tp_but_no_maketp_converts_as_usual(fixtures_dir, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(maketp, "find_maketp", lambda: None)
    module = fixtures_dir / "rapid" / "pick_and_place.mod"
    assert main(["convert", str(module), "-o", str(tmp_path / "with"), "--tp"]) == 0
    assert main(["convert", str(module), "-o", str(tmp_path / "without")]) == 0
    out = capsys.readouterr().out
    assert "no .TP written: FANUC MakeTP (maketp.exe) not found" in out
    programs = sorted(p.name for p in (tmp_path / "without").glob("*.LS"))
    assert programs == sorted(p.name for p in (tmp_path / "with").glob("*.LS")) and programs
    for name in programs:
        with_tp = (tmp_path / "with" / name).read_text(encoding="ascii").splitlines()
        without = (tmp_path / "without" / name).read_text(encoding="ascii").splitlines()
        assert [x for x in with_tp if "TIME" not in x] == [x for x in without if "TIME" not in x]
    report = (tmp_path / "with" / "crossarm_report.md").read_text(encoding="utf-8")
    assert "## Binary .TP programs (FANUC MakeTP)" in report and "Not written" in report
    assert "Binary .TP" not in (tmp_path / "without" / "crossarm_report.md").read_text(encoding="utf-8")
    assert not (tmp_path / "with" / "TP").exists()


def test_convert_writes_every_program_and_setup_frames_as_tp(fixtures_dir, tmp_path, winolpc, monkeypatch):
    exe, robot = winolpc
    fake = FakeMakeTP()
    monkeypatch.setattr(maketp.subprocess, "run", fake)
    monkeypatch.setattr(maketp, "find_maketp", lambda: exe)
    module = fixtures_dir / "rapid" / "pick_and_place.mod"
    run = pipeline.run([module], tmp_path / "out", tp=TpRequest(robot), log=lambda _: None)
    written = sorted(p.stem for p in (tmp_path / "out").glob("*.LS"))
    assert "SETUP_FRAMES" in written
    assert sorted(p.stem for p in (tmp_path / "out" / "TP").glob("*.TP")) == written
    report = (tmp_path / "out" / "crossarm_report.md").read_text(encoding="utf-8")
    assert f"{len(written)} programs written as .TP in `TP`" in report
    assert (GOOD, f"{len(written)} programs also written as .TP in the TP folder, ready to copy to a USB stick.") in (
        summarize(run).attention)  # fmt: skip


def test_the_summary_warns_when_no_tp_was_written(fixtures_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(maketp, "find_maketp", lambda: None)
    run = pipeline.run([fixtures_dir / "rapid" / "pick_and_place.mod"], tmp_path / "out", tp=TpRequest(tmp_path),
                       log=lambda _: None)  # fmt: skip
    assert any(level == WARN and text.startswith("No .TP written: FANUC MakeTP") for level, text in summarize(run).attention)
    run.tasks[0].tp = TpExport(tmp_path, made=["A"], refused=[("B", "why")])
    assert (WARN, "MakeTP refused 1 program: see the report; load their .LS instead.") in summarize(run).attention


class FakePrintTP:
    """subprocess.run as PrintTP behaves: NAME.LS written in the current folder, or the refusal printed."""

    def __init__(self, refuse: dict[str, str] | None = None) -> None:
        self.refuse = refuse or {}
        self.calls: list[list[str]] = []

    def __call__(self, args, cwd, **kwargs) -> subprocess.CompletedProcess:
        self.calls.append(args)
        name = args[1].removesuffix(".TP")
        if name in self.refuse:
            return subprocess.CompletedProcess(args, 1, "PrintTP V10.10-1, Copyright\n" + self.refuse[name], "")
        (Path(cwd) / args[2]).write_bytes(f"/PROG  {name}\r\n".encode("ascii"))
        return subprocess.CompletedProcess(args, 0, "PrintTP V10.10-1, Copyright\nPrintTP completed.\n", "")


def test_printtp_turns_the_robot_tp_back_into_ls_text(winolpc, tmp_path, monkeypatch):
    exe, robot = winolpc
    tps = []
    for name in ("MAIN", "BAD"):
        (tmp_path / f"{name}.TP").write_bytes(b"binary")
        tps.append(tmp_path / f"{name}.TP")
    run = FakePrintTP(refuse={"BAD": "Error executing PrintTP: cannot read file\n"})
    decoded = maketp.print_tp(tps, TpRequest(robot, maketp=exe), runner=run)
    assert decoded.texts == {"MAIN": "/PROG  MAIN\r\n"} and decoded.refused == [("BAD", "cannot read file")]
    assert run.calls[0][:4] == [str(exe.with_name("printtp.exe")), "MAIN.TP", "MAIN.LS", "/config"]
    monkeypatch.setattr(maketp, "find_maketp", lambda: None)
    assert maketp.print_tp(tps, TpRequest(robot), runner=run).problem.startswith("FANUC PrintTP (printtp.exe) not found")
