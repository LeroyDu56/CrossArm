# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Drive a ROBOGUIDE virtual robot from this machine: load, run and read back, without the pendant.

Three channels the virtual controller offers, all local:
  FTP (port 21, anonymous)   STOR NAME.LS loads a program (550: refused, reason in ERRALL.LS), DELE removes it
  HTTP (the robot's page)    /md/NUMREG.VA, /md/POSREG.VA, /md/ERRALL.LS: registers and the error log
  COM (FRRobot.FRCRobot)     runs a program; driven through PowerShell, so nothing to install

Running needs the virtual pendant switched OFF ("TP is enabled" otherwise). Each run starts with a RESET
(KCL through COM): a motion alarm left by an earlier run holds the robot in error, and every later
program would pause on its first move. Use it on a simulator: the same channels on a real robot would
move it.

    python tools/roboguide.py load  tests/fixtures/probes/waits/*.LS
    python tools/roboguide.py run   WAITTIME [timeout_s]
    python tools/roboguide.py numreg 1 2 41
    python tools/roboguide.py zero   1 2 41
    python tools/roboguide.py delete WAITTIME
"""

import ftplib
import html
import io
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# The first virtual robot started takes the usual ports; another one gets its own (seen in netstat:
# web 9001, FTP 9125...). The COM interface reaches the first one only: keep one cell open.
HOST = os.environ.get("CROSSARM_RG_HOST", "127.0.0.1")
WEB = f"http://localhost:{os.environ.get('CROSSARM_RG_WEB', '9000')}"
FTP_PORT = int(os.environ.get("CROSSARM_RG_FTP", "21"))


def _ftp() -> ftplib.FTP:
    ftp = ftplib.FTP()
    ftp.connect(HOST, FTP_PORT, timeout=30)
    ftp.login()
    return ftp


def load(path: Path) -> str:
    """'' when the controller accepted the program, else its reason (from the error log)."""
    ftp = _ftp()
    try:
        ftp.storbinary(f"STOR {path.name}", io.BytesIO(path.read_bytes()))
        return ""
    except ftplib.error_perm as exc:
        if "in use" in str(exc):
            if same_as_loaded(path):
                return ""  # selected on the pendant, so it cannot be replaced: but it is this very program
            release(path.stem)  # selected on the pendant: select another one, then replace it
            ftp.delete(f"{path.stem.lower()}.tp")
            ftp.storbinary(f"STOR {path.name}", io.BytesIO(path.read_bytes()))
            return ""
        if "during load" not in str(exc):
            return str(exc)  # not a refusal of the program: the error log would name an older one
        log = page("md/ERRALL.LS")
        where = re.search(r"ASBN-009 on line (\d+), column (\d+)\s*\"\s*(ASBN-\d+ [^\"]*?)\s*\"", log)
        return f"{exc}: {where[3]} at line {where[1]}, column {where[2]}" if where else str(exc)
    finally:
        ftp.quit()


NEUTRAL = "GETDATA"  # a system program every controller has: selected instead of one to replace

_RELEASE = r"""
$r = New-Object -ComObject FRRobot.FRCRobot
$r.ConnectEx("{host}", $false, 10, 1)
$r.Tasks | Where-Object {{ $_.Name -eq "{name}" -and $_.Status -ne 2 }} | ForEach-Object {{ $_.Abort() }}
if ($r.Programs.Selected -eq "{name}") {{ $r.Programs.Selected = "{neutral}" }}
"released"
"""


def release(name: str) -> None:
    """A program selected on the pendant cannot be deleted or replaced: abort it if it is paused, and select
    another one instead."""
    script = _RELEASE.format(host=HOST, name=name.upper(), neutral=NEUTRAL)
    subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=60,
                   check=False)  # fmt: skip


def same_as_loaded(path: Path) -> bool:
    """Whether the robot holds this program already, instruction for instruction."""
    try:
        stored = page(f"md/{path.stem.upper()}.LS")
    except OSError:
        return False

    def body(text: str) -> list[str]:
        section = text.split("/MN", 1)[-1].split("/POS", 1)[0]
        return [line.strip() for line in section.splitlines() if line.strip()]

    # Compared as the controller stores it, but for the names it gives its own frames: UTOOL[1:Eoat1].
    unnamed = [re.sub(r"(UTOOL|UFRAME)\[(\d+):[^\]]*\]", r"\1[\2]", line) for line in body(stored)]
    return unnamed == body(path.read_bytes().decode("ascii", "replace"))


def delete(name: str) -> None:
    ftp = _ftp()
    try:
        ftp.delete(f"{name.lower()}.tp")
    finally:
        ftp.quit()


def page(path: str) -> str:
    """A file of the robot's web server, out of the HTML page it is served in."""
    with urllib.request.urlopen(f"{WEB}/{path}", timeout=30) as response:
        text = response.read().decode("utf-8", "replace")
    found = re.search(r"<XMP>(.*?)</XMP>", text, re.DOTALL | re.IGNORECASE) or re.search(r"<PRE>(.*?)</PRE>", text, re.DOTALL | re.IGNORECASE)
    return html.unescape(found.group(1)) if found else re.sub(r"<[^>]*>", "", text)


def numreg() -> dict[int, float]:
    values = {}
    for match in re.finditer(r"^\s*\[(\d+)\] = (-?[\d.eE+-]+)", page("md/NUMREG.VA"), re.MULTILINE):
        values[int(match[1])] = float(match[2])
    return values


_RUN = r"""
$r = New-Object -ComObject FRRobot.FRCRobot
$r.ConnectEx("{host}", $false, 10, 1)
$r.KCL("RESET", $true)
$r.Programs.Item("{name}").Run()
$resumes = {resumes}
$end = (Get-Date).AddSeconds({timeout})
Start-Sleep -Milliseconds 200
while ((Get-Date) -lt $end) {{
  $task = @($r.Tasks | Where-Object {{ $_.Name -eq "{name}" }})[0]
  if ($task -eq $null -or $task.Status -eq 0) {{ Start-Sleep -Milliseconds 200; continue }}
  if ($task.Status -eq 2) {{ "done"; exit 0 }}
  if ($resumes -gt 0) {{ $resumes -= 1; $task.Continue(); Start-Sleep -Milliseconds 300; continue }}
  "paused at line " + $task.CurLine; exit 0
}}
"timeout"
"""


_ZERO = r"""
$r = New-Object -ComObject FRRobot.FRCRobot
$r.ConnectEx("{host}", $false, 10, 1)
foreach ($n in @({numbers})) {{ $r.RegNumerics.Item($n).Value.RegLong = 0 }}
"zeroed"
"""
_SET = r"""
$r = New-Object -ComObject FRRobot.FRCRobot
$r.ConnectEx("{host}", $false, 10, 1)
{assignments}
"set"
"""


def set_registers(values: dict[int, int]) -> str:
    """Integer values into numeric registers, before a run that reads them."""
    assignments = "\n".join(f"$r.RegNumerics.Item({n}).Value.RegLong = {int(v)}" for n, v in values.items())
    script = _SET.format(host=HOST, assignments=assignments)
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                            timeout=60, check=False)  # fmt: skip
    return (result.stdout.strip().splitlines() or [result.stderr.strip()])[-1]


def model() -> str:
    """The robot of the virtual cell, as the controller names it ($SCR_GRP[1].$ROBOT_ID, e.g. 'M-20iD/25')."""
    found = re.search(r"\$SCR_GRP\[1\]\.\$ROBOT_ID\s+Access:\s*\w+:\s*STRING\[\d+\]\s*=\s*'([^']*)'",
                      page("md/SYSVARS.VA"))  # fmt: skip
    return found[1].strip() if found else "unknown FANUC robot"


def zero(numbers: list[int]) -> str:
    """Set registers to 0 before a run, so that what a run leaves cannot be an earlier run's."""
    script = _ZERO.format(host=HOST, numbers=",".join(str(n) for n in numbers))
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                            timeout=60, check=False)  # fmt: skip
    return (result.stdout.strip().splitlines() or [result.stderr.strip()])[-1]


def run(name: str, timeout: float = 120, resumes: int = 0) -> str:
    """Run a loaded program and wait for it to end: 'done', 'paused at line N', 'timeout', or the refusal.

    `resumes`: how many pauses to continue from, for a program that pauses on purpose (SETUP_FRAMES
    starts with one). A pause past those is reported: an alarm pauses a program too.
    """
    before = _alarms()
    started = time.time()
    script = _RUN.format(host=HOST, name=name.upper(), timeout=timeout, resumes=resumes)
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                            timeout=timeout + 60, check=False)  # fmt: skip
    status = (result.stdout.strip().splitlines() or [result.stderr.strip()])[-1]
    # A run the controller refuses (another task holds the robot: INTP-105, PROG-040) ends the task at once,
    # which reads as done: the error log says otherwise.
    after = _alarms()
    for line in after - before if before is not None and after is not None else ():
        if "Run request failed" in line and f"({name.upper()}," in line:
            return "refused: " + " ".join(line.split('"')[2:4]).strip()
    # An error stopping the program (INTP-323 Value overflow...) ends the task too: in it, or in a program it
    # calls. Dated from the run on: the log can show an earlier run's alarm late.
    for line in after - before if before is not None and after is not None and status == "done" else ():
        stamp = re.search(r"(\d\d-[A-Z]{3}-\d\d \d\d:\d\d:\d\d)", line)
        if "INTP-" in line and "ABORT" in line and stamp and _logged_at(stamp[1]) >= started - 2:
            return "aborted: " + " ".join(line.split('"')[1:3]).split("ABORT")[0].strip()
    return status


def _logged_at(stamp: str) -> float:
    """An error log time ('02-OCT-26 14:26:08', the PC's clock on a virtual robot) as time.time() gives it."""
    return time.mktime(time.strptime(stamp.title(), "%d-%b-%y %H:%M:%S"))


def _alarms() -> set[str] | None:
    """The entries of the controller's error log, each with its time; None when it cannot be read."""
    try:
        return {line.split('"', 1)[-1] for line in page("md/ERRALL.LS").splitlines()[2:] if line.strip()}
    except OSError:
        return None


def main() -> int:
    if len(sys.argv) < 3 and not (len(sys.argv) == 2 and sys.argv[1] == "numreg"):
        print(__doc__)
        return 2
    command, args = sys.argv[1], sys.argv[2:]
    if command == "load":
        for path in args:
            reason = load(Path(path))
            print(f"{Path(path).name}: {reason or 'loaded'}")
    elif command == "run":
        start = time.monotonic()
        print(f"{args[0]}: {run(args[0], float(args[1]) if len(args) > 1 else 120)} "
              f"after {time.monotonic() - start:.1f} s")  # fmt: skip
    elif command == "numreg":
        values = numreg()
        for number in [int(a) for a in args] or sorted(values):
            print(f"R[{number}] = {values.get(number)}")
    elif command == "zero":
        print(zero([int(a) for a in args]))
    elif command == "delete":
        for name in args:
            delete(name)
            print(f"{name}: deleted")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
