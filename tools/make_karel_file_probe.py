# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the KAREL file probe (--karel): RAPID's Open, Write and Close converted to CALL CA_FILE, the
files the robot writes read back by FTP and compared byte for byte with what RAPID writes.

KarelFileProbe.mod opens a file of HOME: with \\Write, writes texts (an apostrophe, commas, a semicolon,
parentheses, a text of 70 characters), numbers with \\Num (a list of values: thirds, six digits and more, very
small, whole ones, a sum of tenths), a line in two Writes (\\NoNewLine), a line written by a routine given a text
and a number, opens it again with \\Append, opens a second file through an element of an iodev array (the index
known at run time, the folder given as diskhome), and a third one twice with \\Write (emptied the second time).
CrossArm converts it with --karel; CA_FILE writes the files on UD1:. The bytes RAPID writes are worked out here
from RAPID's rules, without CrossArm: lines ended by CR LF (as RobotStudio's HOME: files are), a number as Write
\\Num writes it (six significant digits; a whole number when the decimals are within 0.000005 of one).

Error cases, each a TP program calling CA_FILE wrongly, then setting a register that must stay 0: a write to a
handle with no file open, a device the controller does not have, a folder of HOME:. And whether a file stays open
after the TP program that opened it ends (KFKEEP, then KFKEEP2 writing to it).

  python tools/make_karel_file_probe.py write    the module and the programs, in tests/fixtures/probes/karelfile
  python tools/make_karel_file_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results in results/
  python tools/make_karel_file_probe.py check    the stored results against what RAPID writes
"""

import ftplib
import io
import math
import struct
import sys
import tempfile
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_karel_probe import _ftp, alarm

from crossarm.fanuc.ktrans import KarelRequest, export
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program

PROBE = ROOT / "tests" / "fixtures" / "probes" / "karelfile"
RESULT = PROBE / "results" / "karelfile_roboguide.txt"
STAMP = datetime(2026, 1, 1)
MAIN, LINE = "KFPROBE", "KFLINE"
FILES = ("kfprobe.txt", "kfsecond.txt", "kfthird.txt", "kfkeep.txt")
# (RAPID literal, its value): what the probe writes with \Num
VALUES = [("1/3", 1 / 3), ("2.5", 2.5), ("123456.7", 123456.7), ("1234567", 1234567.0), ("-0.000012", -0.000012),
          ("-7", -7.0), ("0.1+0.2", 0.1 + 0.2), ("99.99999", 99.99999), ("0.0123456", 0.0123456),
          ("12.345678", 12.345678), ("3.14159265", 3.14159265), ("-0.3", -0.3), ("0.000004", 0.000004), ("0", 0.0),
          ("100", 100.0)]  # fmt: skip
LONG = "0123456789" * 7  # 70 characters: RAPID writes it (a string over 80 stopped RobotStudio's server)
HANDLE, SPARE, FLAGS = 95, 96, {"KFERRCLS": 97, "KFERRDEV": 98, "KFERRDIR": 99, "KFKEEP2": 94}
ERRORS = {  # program: its lines before the flag, the alarm code expected
    "KFERRCLS": ([f"R[{SPARE}]=0", f"CALL CA_FILE(2,{SPARE},1,'x')"], "INTP-328"),
    "KFERRDEV": ([f"CALL CA_FILE(1,{SPARE},1,'UD9:','kfx.txt')"], "FILE-008"),
    "KFERRDIR": ([f"CALL CA_FILE(1,{SPARE},1,'HOME:/sub','kfx.txt')"], "INTP-325"),
}  # fmt: skip
KEEP = {"KFKEEP": [f"CALL CA_FILE(1,{HANDLE},1,'UD1:','kfkeep.txt')", f"CALL CA_FILE(2,{HANDLE},1,'a')"],
        "KFKEEP2": [f"CALL CA_FILE(2,{HANDLE},1,'b')", f"CALL CA_FILE(3,{HANDLE})"]}  # fmt: skip


def module() -> str:
    lines = [
        "MODULE KarelFileProbe",
        "    ! CrossArm - KAREL file probe: see tools/make_karel_file_probe.py.",
        "    VAR iodev kfLog;",
        "    VAR iodev kfMany{2};",
        "    VAR num kfDone:=0;",
        "    VAR num kfI:=0;",
        "    VAR num kfV:=0;",
        "",
        "    PROC KfProbe()",
        "        kfDone:=0;",
        '        Open "HOME:" \\File:="kfprobe.txt", kfLog \\Write;',
        '        Write kfLog, "CrossArm file probe";',
        "        Write kfLog, \"it's a,b;c (x)\";",
        f'        Write kfLog, "{LONG}";',
    ]
    for i, (literal, _value) in enumerate(VALUES):
        lines += [f"        kfV:={literal};", f'        Write kfLog, "n{i} " \\Num:=kfV;']
    lines += [
        '        Write kfLog, "no line, " \\NoNewLine;',
        '        Write kfLog, "end";',
        "        Close kfLog;",
        '        Open "HOME:" \\File:="kfprobe.txt", kfLog \\Append;',
        '        KfLine "appended", 3;',
        "        Close kfLog;",
        "        kfI:=2;",
        '        Open diskhome \\File:="kfsecond.txt", kfMany{kfI} \\Write;',
        '        Write kfMany{kfI}, "second";',
        "        Close kfMany{kfI};",
        '        Open "HOME:/kfsecond.txt", kfMany{1} \\Append;',
        '        Write kfMany{1}, "added";',
        "        Close kfMany{1};",
        '        Open "HOME:" \\File:="kfthird.txt", kfLog \\Write;',
        '        Write kfLog, "first";',
        "        Close kfLog;",
        '        Open "HOME:" \\File:="kfthird.txt", kfLog;',
        '        Write kfLog, "rewritten";',
        "        Close kfLog;",
        "        kfDone:=1;",
        "    ENDPROC",
        "",
        "    PROC KfLine(string text, num n)",
        '        Write kfLog, "[" + text + "] " \\Num:=n;',
        "    ENDPROC",
        "ENDMODULE",
        "",
    ]
    return "\r\n".join(lines)


MODULE = module()


# -- what RAPID writes, from its rules, without CrossArm ------------------------------------------------------------


def rapid_num(value: float) -> str:
    """RAPID's Write \\Num of a num (a 32-bit float): a whole number when its decimals are within 0.000005 of one,
    else six significant digits, without the zeros at the end."""
    v = struct.unpack("f", struct.pack("f", value))[0]
    a = abs(v)
    fraction = a - math.trunc(a)
    if fraction < 0.000005 or fraction > 0.999995:
        return str(int(Decimal(v).quantize(Decimal(1), ROUND_HALF_UP)))
    digits = max(0, 5 - math.floor(math.log10(a)))  # CA_FILE writes a number from 1E6 up whole (not compared)
    text = str(Decimal(v).quantize(Decimal(1).scaleb(-digits), ROUND_HALF_UP))
    return text.rstrip("0").rstrip(".") if "." in text else text


def expected() -> dict[str, bytes]:
    probe = ["CrossArm file probe", "it's a,b;c (x)", LONG]
    probe += [f"n{i} {rapid_num(value)}" for i, (_literal, value) in enumerate(VALUES)]
    probe += ["no line, end", "[appended] 3"]
    files = {"kfprobe.txt": probe, "kfsecond.txt": ["second", "added"], "kfthird.txt": ["rewritten"]}
    return {name: "".join(f"{line}\r\n" for line in lines).encode("ascii") for name, lines in files.items()}


# -- the conversion ---------------------------------------------------------------------------------------------------


def conversion(folder: Path):
    """KarelFileProbe.mod converted with --karel as `crossarm convert` does."""
    from crossarm import pipeline
    from crossarm.convert import ConversionConfig

    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "KarelFileProbe.mod").write_bytes(MODULE.encode("ascii"))
    run = pipeline.run([PROBE / "KarelFileProbe.mod"], folder, ConversionConfig(timestamp=STAMP, karel=True),
                       log=lambda _: None)  # fmt: skip
    result = run.tasks[0].result
    assert result is not None and not [n for n in result.notes if n.kind == "TODO"], result and result.notes
    assert result.karel_programs == ["CA_FILE"], result.karel_programs
    return result


def _program(name: str, lines: list[str], comment: str) -> Program:
    return Program(name, [Instruction(text) for text in lines], attributes=Attributes(comment=comment, created=STAMP))


def hand_programs() -> list[Program]:
    found = [_program(name, [*lines, f"R[{FLAGS[name]}]=1"], "KAREL file error case")
             for name, (lines, _code) in ERRORS.items()]  # fmt: skip
    found.append(_program("KFKEEP", KEEP["KFKEEP"], "KAREL file left open"))
    found.append(_program("KFKEEP2", [*KEEP["KFKEEP2"], f"R[{FLAGS['KFKEEP2']}]=1"], "KAREL file written later"))
    return found


def write() -> list[str]:
    """The probe's .LS files: the conversion's programs, then the hand-written ones. Their names, in loading order."""
    names = []
    with tempfile.TemporaryDirectory(prefix="crossarm_karelfile_") as temp:
        result = conversion(Path(temp))
        for info in result.programs:
            (PROBE / f"{info.program.name}.LS").write_bytes(write_ls(info.program).encode("ascii"))
            names.append(info.program.name)
    for program in hand_programs():
        (PROBE / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
        names.append(program.name)
    print(f"probe written to {PROBE}: {', '.join(names)}")
    return names


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------


def _retr(name: str) -> bytes | None:
    import roboguide

    ftp = ftplib.FTP()
    ftp.connect(roboguide.HOST, roboguide.FTP_PORT, timeout=30)
    ftp.login()
    buffer = io.BytesIO()
    try:
        ftp.retrbinary(f"RETR ud1:{name}", buffer.write)
        return buffer.getvalue()
    except ftplib.error_perm:
        return None
    finally:
        ftp.quit()


def measure() -> dict[str, str]:
    import make_maketp_probe
    import roboguide

    names = write()
    found: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="crossarm_karelfile_") as temp:
        work = Path(temp)
        out = export(["CA_FILE"], work, KarelRequest(make_maketp_probe.robot()), log=print)
        if out.compiled != ["CA_FILE"]:
            raise RuntimeError(f"CA_FILE not compiled: {out.problem or out.refused}")
        found["version"] = out.version
        for name in names:
            roboguide.release(name)
        roboguide.select()
        for name in names:
            _ftp(f"DELE {name.lower()}.tp")
        for name in FILES:
            _ftp(f"DELE ud1:{name}")
        try:
            found["ca_file_load"] = _ftp("STOR", work / "ca_file.pc") or "loaded"
            for name in names:
                found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
            # 1. The converted program: the files it writes.
            found["run"] = roboguide.run(MAIN, 120)
            roboguide.release(MAIN)
            for name in FILES[:3]:
                data = _retr(name)
                found[name] = data.hex() if data is not None else "missing"
            # 2. The error cases.
            for program, (_lines, code) in ERRORS.items():
                roboguide.zero([FLAGS[program]])
                before = roboguide._alarms() or set()
                found[f"{program}_run"] = roboguide.run(program, 60)
                found[f"{program}_alarm"] = alarm(roboguide.page("md/ERRALL.LS"), code, before)
                found[f"{program}_after"] = f"{roboguide.numreg().get(FLAGS[program], float('nan')):g}"
                roboguide.release(program)
            # 3. A file left open by a program that ended, written by the next one.
            roboguide.zero([HANDLE, FLAGS["KFKEEP2"]])
            found["KFKEEP_run"] = roboguide.run("KFKEEP", 60)
            roboguide.release("KFKEEP")
            before = roboguide._alarms() or set()
            found["KFKEEP2_run"] = roboguide.run("KFKEEP2", 60)
            found["KFKEEP2_alarm"] = alarm(roboguide.page("md/ERRALL.LS"), "INTP-328", before)
            found["KFKEEP2_after"] = f"{roboguide.numreg().get(FLAGS['KFKEEP2'], float('nan')):g}"
            data = _retr("kfkeep.txt")
            found["kfkeep.txt"] = data.hex() if data is not None else "missing"
            return found
        finally:
            roboguide.select()
            for name in names:
                roboguide.release(name)
            roboguide.select()
            for name in names:
                _ftp(f"DELE {name.lower()}.tp")
            _ftp("DELE ca_file.pc")
            _ftp("DELE ca_file.vr")  # its variables, left after the program (the .va view goes with them)
            for name in (*FILES, "kfx.txt"):
                _ftp(f"DELE ud1:{name}")


def verdict(found: dict[str, str]) -> str:
    """'' when the probe went as measured; else what differs."""
    wrong = []
    if found.get("ca_file_load") != "loaded" or found.get("run") != "done":
        wrong.append(f"converted program: {found.get('ca_file_load')}, {found.get('run')}")
    for name, data in expected().items():
        got = found.get(name, "missing")
        if got != data.hex():
            shown = bytes.fromhex(got) if got != "missing" else b"missing"
            wrong.append(f"{name}: {shown!r} where RAPID writes {data!r}")
    for program, (_lines, code) in ERRORS.items():
        if not found.get(f"{program}_alarm", "").startswith(code) or found.get(f"{program}_after") != "0":
            wrong.append(f"{program}: {found.get(f'{program}_run')}, {found.get(f'{program}_alarm')},"
                         f" line after {found.get(f'{program}_after')}")  # fmt: skip
    keep = (found.get("KFKEEP2_alarm", "none"), found.get("KFKEEP2_after"), found.get("kfkeep.txt"))
    if keep != KEPT:
        wrong.append(f"file left open: {keep}")
    return "; ".join(wrong)


# A file left open when the TP program that opened it ends: closed with what was written (measured 2026-10-08).
KEPT = ("INTP-328 (%s^4, %d^5) File is not opened ABORT.G", "0", "610d0a")  # 'a' CR LF


def summary(found: dict[str, str]) -> str:
    return (f"compiled for {found.get('version')}; {len(expected())} files byte for byte as RAPID writes them"
            f" ({len(VALUES)} numbers); {len(ERRORS)} error cases abort on the CALL")  # fmt: skip


def run() -> str:
    """Measure, store the result (results/karelfile_roboguide.txt), check it: '' when as measured."""
    found = measure()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text("".join(f"{k} {v}\n" for k, v in found.items()), encoding="ascii")
    print(RESULT.read_text(encoding="ascii"))
    return check()


def stored() -> dict[str, str]:
    return dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())


def check() -> str:
    found = stored()
    problem = verdict(found)
    print(f"FAIL {problem}" if problem else f"karelfile probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
