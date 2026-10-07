# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The KAREL folder (--karel) and FANUC ktrans: never run here, the subprocess is a stand-in.

What ktrans prints and does was measured with ROBOGUIDE V10.10 (tools/make_karel_probe.py)."""

import subprocess
from pathlib import Path

import pytest

from crossarm import pipeline
from crossarm.cli import main
from crossarm.convert import ConversionConfig
from crossarm.fanuc import ktrans
from crossarm.fanuc.ktrans import KarelRequest, choose_version, export, find_ktrans, installed_versions, reason
from crossarm.karel import LIBRARY, PROGRAMS, source
from crossarm.summary import INFO, WARN, summarize

BANNER = ("KTRANS Version V10.10 (Build 270   9/11/2025)\nCopyright (C) FANUC America Corporation, 1985 through 2023.\n"
          "All Rights Reserved.\n\n\n\n")  # fmt: skip
SUCCESS = (BANNER + "*** Translation successful, 749 bytes of p-code generated, checksum 16257. ***\n"
           "Error executing KTrans: Copy to/from source directory failed: \n32 - File C:\\x\\ca_posemult.pc\n")  # fmt: skip
SYNTAX = (BANNER + "C:\\x\\ca_posemult.kl(3)\n   3   x = 1\n       ^ ERROR\nId must be defined before this use.  Id: X\n"
          "\n\n===============Translation not successful===============\n"
          "Error executing KTrans: Error translating program: Code: 0xFFFFFFFF:  \n")  # fmt: skip
INVALID = "The requested version ID is invalid: V99.99-1\n\n       Installed versions of WinOLPC:\n   V10.10-1\n"
MODULE = """MODULE KP
  VAR pose pA;
  VAR pose pC;
  VAR num n:=5;
  PROC Main()
    n:=n+1;
    pA:=[[n,0,100],[1,0,0,0]];
    pC:=PoseMult(pA,[[10,20,30],[1,0,0,0]]);
  ENDPROC
ENDMODULE
"""


@pytest.fixture
def winolpc(tmp_path):
    """A WinOLPC install (bin/ktrans.exe, three cores) and a ROBOGUIDE robot of V10.10."""
    exe = tmp_path / "WinOLPC" / "bin" / "ktrans.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    for core in ("V940-1", "V1010-1", "V1013-1", "V640-1"):
        (tmp_path / "WinOLPC" / "Versions" / core / "bin").mkdir(parents=True)
    robot = tmp_path / "Cell" / "Robot_1"
    robot.mkdir(parents=True)
    (robot / "frvirt.dat").write_text("V10.10270   V10.10270     9/11/2025\n", encoding="ascii")
    return exe, robot


class FakeKtrans:
    """subprocess.run as ktrans behaves: the .pc written next to the .kl and an error code even then."""

    def __init__(self, output: str = SUCCESS, write: bool = True) -> None:
        self.output, self.write = output, write
        self.calls: list[tuple[list[str], Path]] = []

    def __call__(self, args, cwd, **kwargs) -> subprocess.CompletedProcess:
        self.calls.append((args, Path(cwd)))
        assert (Path(cwd) / args[1]).is_file() and (Path(cwd) / LIBRARY).is_file()  # %INCLUDE ca_lib beside it
        if self.write:
            (Path(cwd) / args[2]).write_bytes(b"pc")
        return subprocess.CompletedProcess(args, 2147745898, self.output, "")


def test_ktrans_is_found_next_to_maketp_or_where_the_variable_says(winolpc, tmp_path):
    exe, _ = winolpc
    assert find_ktrans({"CROSSARM_KTRANS": str(exe)}) == exe
    (exe.parent / "maketp.exe").write_bytes(b"")
    assert find_ktrans({"CROSSARM_MAKETP": str(exe.parent / "maketp.exe")}) == exe
    assert installed_versions(exe) == ["V6.40-1", "V9.40-1", "V10.10-1", "V10.13-1"]


def test_the_version_is_the_robots_else_the_newest_installed(winolpc, tmp_path):
    exe, robot = winolpc
    assert choose_version(KarelRequest(robot), exe) == ("V10.10-1", "")
    assert choose_version(KarelRequest(robot.parent), exe) == ("V10.10-1", "")  # a cell of one robot
    ini = tmp_path / "robot.ini"
    ini.write_text("[WinOLPC_Util]\nRobot=\\C\\x\nVersion=V9.30-1\n", encoding="ascii")
    assert choose_version(KarelRequest(ini), exe) == ("V9.30-1", "")
    assert choose_version(KarelRequest(), exe) == ("V10.13-1", "")
    assert choose_version(KarelRequest(version="V8.30-1"), exe) == ("V8.30-1", "")


def test_the_library_is_written_and_compiled(winolpc, tmp_path):
    exe, robot = winolpc
    run = FakeKtrans()
    out = export(["CA_POSEMULT"], tmp_path / "KAREL", KarelRequest(robot, ktrans=exe), runner=run)
    assert (out.written, out.compiled, out.refused, out.problem, out.version) == (
        ["CA_POSEMULT"], ["CA_POSEMULT"], [], "", "V10.10-1")  # fmt: skip
    assert sorted(p.name for p in (tmp_path / "KAREL").iterdir()) == ["ca_lib.kl", "ca_posemult.kl", "ca_posemult.pc"]
    assert (tmp_path / "KAREL" / "ca_posemult.kl").read_bytes() == source("ca_posemult.kl").encode().replace(b"\n", b"\r\n")
    assert run.calls[0][0][1:] == ["ca_posemult.kl", "ca_posemult.pc", "/ver", "V10.10-1"]
    section = ktrans.report_section(out, "../KAREL")
    assert "| `CA_POSEMULT` |" in section and "`ca_posemult.pc`" in section and "V10.10-1" in section
    assert "KAREL option (R632)" in section and "INTP-222" in section


def test_without_ktrans_the_kl_are_delivered_with_how_to_compile_them(tmp_path, monkeypatch):
    monkeypatch.setattr(ktrans, "find_ktrans", lambda: None)
    out = export(["CA_POSEMULT"], tmp_path / "KAREL", KarelRequest(), runner=FakeKtrans())
    assert out.problem.startswith("FANUC ktrans (ktrans.exe) not found") and out.compiled == []
    assert sorted(p.name for p in (tmp_path / "KAREL").iterdir()) == ["ca_lib.kl", "ca_posemult.kl"]
    section = ktrans.report_section(out, "KAREL")
    assert "Not compiled: FANUC ktrans (ktrans.exe) not found" in section
    assert "`ktrans ca_posemult.kl ca_posemult.pc /ver <version>`" in section
    assert "(not compiled)" in section and "not compiled" in out.summary()


def test_what_ktrans_refuses_is_said(winolpc, tmp_path):
    exe, _ = winolpc
    out = export(["CA_POSEMULT"], tmp_path / "KAREL", KarelRequest(ktrans=exe), runner=FakeKtrans(SYNTAX, write=False))
    assert out.refused == [("CA_POSEMULT", "line 3: Id must be defined before this use.  Id: X")]
    out = export(["CA_POSEMULT"], tmp_path / "KAREL", KarelRequest(version="V99.99-1", ktrans=exe),
                 runner=FakeKtrans(INVALID, write=False))  # fmt: skip
    assert out.problem == "ktrans cannot compile for V99.99-1: The requested version ID is invalid: V99.99-1"
    assert reason("nothing useful") == "no message"


def test_every_library_program_has_its_source():
    for program in PROGRAMS.values():
        assert source(program.source).startswith("-- SPDX-FileCopyrightText")


def test_convert_with_karel_writes_the_karel_folder_and_says_it(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ktrans, "find_ktrans", lambda: None)
    (tmp_path / "KP.mod").write_text(MODULE, encoding="ascii")
    assert main(["convert", str(tmp_path / "KP.mod"), "--karel", "-o", str(tmp_path / "on")]) == 0
    assert sorted(p.name for p in (tmp_path / "on" / "KAREL").iterdir()) == ["ca_lib.kl", "ca_posemult.kl"]
    report = (tmp_path / "on" / "crossarm_report.md").read_text(encoding="utf-8")
    assert "## KAREL programs (--karel)" in report and "Not compiled: FANUC ktrans" in report
    assert "Load the 1 KAREL program before the programs that call it" in report
    assert "CALL CA_POSEMULT(" in (tmp_path / "on" / "MAIN.LS").read_text(encoding="ascii")
    assert "KAREL programs CA_POSEMULT written as .kl, not compiled" in capsys.readouterr().out
    assert main(["convert", str(tmp_path / "KP.mod"), "-o", str(tmp_path / "off")]) == 0
    assert not (tmp_path / "off" / "KAREL").exists()
    assert "CALL CA_" not in (tmp_path / "off" / "MAIN.LS").read_text(encoding="ascii")
    assert "2 TODO would be converted with --karel" in capsys.readouterr().out


def test_the_window_summary_says_what_karel_did_or_would_do(tmp_path, monkeypatch):
    monkeypatch.setattr(ktrans, "find_ktrans", lambda: None)
    (tmp_path / "KP.mod").write_text(MODULE, encoding="ascii")
    on = pipeline.run([tmp_path / "KP.mod"], tmp_path / "on", ConversionConfig(karel=True), log=lambda _: None)
    lines = summarize(on).attention
    assert any(kind == WARN and text.startswith("KAREL programs CA_POSEMULT in the KAREL folder") for kind, text in lines)
    off = pipeline.run([tmp_path / "KP.mod"], tmp_path / "off", ConversionConfig(), log=lambda _: None)
    text = "2 TODO would be converted with KAREL programs (step 6, or --karel): the robot needs the KAREL option (R632)."
    assert (INFO, text) in summarize(off).attention
