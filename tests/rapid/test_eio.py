# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

from datetime import datetime

from helpers import parse_module

from crossarm.cli import main
from crossarm.convert import ConversionConfig, convert
from crossarm.rapid.eio import Signal, find_eio, parse_eio

# Synthetic EIO.cfg in the RobotWare 7 layout (CRLF, continuation lines, other sections around).
EIO_CFG = (
    "EIO:CFG_1.0:7:0::\r\n"
    "#\r\n"
    "EIO_CROSS:\r\n"
    "\r\n"
    '      -Name "LIFE" -Res "ECHO" -Act1 "BIT"\r\n'
    "\r\n"
    "EIO_SIGNAL:\r\n"
    "\r\n"
    '      -Name "gripClose" -SignalType "DO" -Device "d652"\\\r\n'
    '      -Label "Gripper close" -DeviceMap "3"\r\n'
    "\r\n"
    '      -Name "partReady" -SignalType "DI" -Device "d652" -DeviceMap "0"\r\n'
    "\r\n"
    '      -Name "cycleCode" -SignalType "GI" -Device "PLC" -DeviceMap "0-7"\r\n'
    "\r\n"
    '      -Name "safetyOk" -SignalType "DI" -Access All -Category "safety"\r\n'
    "\r\n"
    "EIO_ACCESS:\r\n"
    "\r\n"
    '      -Name "All" -Rapid\r\n'
)


def test_signals_are_read_from_the_signal_section_only():
    signals = parse_eio(EIO_CFG)
    assert sorted(signals) == ["CYCLECODE", "GRIPCLOSE", "PARTREADY", "SAFETYOK"]
    assert signals["GRIPCLOSE"] == Signal("gripClose", "DO", "d652", "3", "Gripper close")
    assert signals["CYCLECODE"].signal_type == "GI"
    assert signals["SAFETYOK"].device == ""  # unquoted values and missing keys are fine


def run(body: str, signals):
    source = f"MODULE M\nPROC main()\n{body}\nENDPROC\nENDMODULE\n"
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    return convert([parse_module(source)], config, routines=["main"], sources={"M": source}, signals=signals)


def lines(result) -> list[str]:
    return [line.text for line in result.programs[0].program.lines[1:]]


def test_eio_types_signals_without_name_guessing():
    # Names without di/do prefix: only EIO.cfg can tell their direction.
    result = run("IF partReady=1 Set gripClose;", parse_eio(EIO_CFG))
    assert lines(result) == ["IF (DI[1]=ON) THEN", "DO[1]=ON", "ENDIF"]
    assert not [n for n in result.notes if "assumed" in n.message]
    assert result.digital_outputs[0].detail == "EIO.cfg: DO, device d652, map 3"


def test_eio_overrides_the_name_heuristic():
    signals = {"DOREADY": Signal("doReady", "DI")}  # named like an output, declared as an input
    assert lines(run("WaitUntil doReady=1;", signals)) == ["WAIT (DI[1]=ON)"]


def test_group_signals_are_read_as_values_not_as_digital_signals():
    result = run("IF cycleCode=3 Stop;", parse_eio(EIO_CFG))
    assert lines(result)[0] == "IF (GI[1]=3) THEN"
    assert result.group_inputs[0].detail == "EIO.cfg: GI, device PLC, map 0-7"
    result = run("Set cycleCode;", parse_eio(EIO_CFG))  # not a digital output
    assert lines(result)[0].startswith("!TODO")


def test_undeclared_signal_is_flagged_when_eio_is_known():
    result = run("Set doLamp;", parse_eio(EIO_CFG))
    assert lines(result) == ["DO[1]=ON"]
    assert any("not declared in EIO.cfg" in n.message for n in result.notes)


def test_find_eio_in_a_backup_layout(tmp_path):
    (tmp_path / "RAPID").mkdir()
    (tmp_path / "SYSPAR").mkdir()
    (tmp_path / "SYSPAR" / "EIO.cfg").write_text(EIO_CFG, encoding="utf-8")
    assert find_eio([tmp_path / "RAPID"]) == tmp_path / "SYSPAR" / "EIO.cfg"
    assert find_eio([tmp_path / "SYSPAR"]) == tmp_path / "SYSPAR" / "EIO.cfg"


def test_cli_uses_the_backup_eio(tmp_path, capsys):
    (tmp_path / "RAPID").mkdir()
    (tmp_path / "SYSPAR").mkdir()
    (tmp_path / "SYSPAR" / "EIO.cfg").write_text(EIO_CFG, encoding="utf-8")
    (tmp_path / "RAPID" / "m.mod").write_text("MODULE M\nPROC main()\nSet gripClose;\nENDPROC\nENDMODULE\n")
    assert main(["convert", str(tmp_path / "RAPID"), "-o", str(tmp_path / "out")]) == 0
    assert "I/O signal types from" in capsys.readouterr().out
    assert "DO[1]=ON" in (tmp_path / "out" / "MAIN.LS").read_text(encoding="ascii")
