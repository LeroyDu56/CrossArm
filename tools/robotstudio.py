# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Run RAPID probe modules on a RobotStudio virtual controller, and read what they write.

RobotWare 7 and 8 (OmniCore) let a PC program read the controller through ABB's PC SDK, but loading
and starting programs needs write access, which the controller gives only to its control stations
(the pendant, RobotStudio). So the controller does it itself: tools/CrossArmServer.mod, loaded and
started once from RobotStudio, waits for requests in HOME:/crossarm/, loads the module named there
with Load \\Dynamic, calls its routine by name and unloads it.

HOME: of a virtual controller is a folder of this PC: requests and results go through the file
system. The folder is asked from the controller once through the PC SDK (read only), or given in
CROSSARM_RS_HOME.

A probe written to be run by hand ends with Stop, which would stop the server too: the copy sent
to the server has its Stop instructions turned into remarks.

    python tools/robotstudio.py home
    python tools/robotstudio.py run tests/fixtures/probes/pose/PoseProbe.mod Probe [timeout_s]
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

_HOME = r"""
$bin = @("C:\Program Files (x86)\ABB\RobotStudio *\Bin-net48", "C:\Program Files (x86)\ABB\RobotStudio *\Bin") |
  ForEach-Object { Resolve-Path $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
Add-Type -Path (Join-Path $bin "ABB.Robotics.Controllers.PC.dll")
$s = New-Object ABB.Robotics.Controllers.Discovery.NetworkScanner
$s.Scan()
$found = @($s.Controllers | Where-Object { $_.IsVirtual -and (-not $env:CROSSARM_RS_SYSTEM -or $_.SystemName -eq $env:CROSSARM_RS_SYSTEM) })
if ($found.Count -eq 0) { "no virtual controller running"; exit 1 }
if ($found.Count -gt 1) { "several virtual controllers running (" + (($found | ForEach-Object { $_.SystemName }) -join ", ") + "): set CROSSARM_RS_SYSTEM"; exit 1 }
$info = $found[0]
$info.SystemName
$c = [ABB.Robotics.Controllers.ControllerFactory]::CreateFrom($info)
$c.Logon([ABB.Robotics.Controllers.UserInfo]::DefaultUser)
$c.FileSystem.RemoteDirectory
$c.Logoff(); $c.Dispose()
"""
_STATUS = _HOME.replace(
    "$c.FileSystem.RemoteDirectory",
    '"execution " + $c.Rapid.ExecutionStatus + ", " + $c.State\n'
    "$c.EventLog.GetCategory(0).Messages | Select-Object -First 4 | ForEach-Object { $_.Number.ToString() + ' ' + $_.Title }",
)
_STOP = re.compile(r"^(\s*)Stop;", re.MULTILINE | re.IGNORECASE)


def _controller() -> tuple[str, Path]:
    result = subprocess.run(["powershell", "-NoProfile", "-Command", _HOME], capture_output=True, text=True,
                            encoding="oem", errors="replace", timeout=120, check=False)  # fmt: skip
    lines = result.stdout.strip().splitlines()
    if result.returncode or len(lines) < 2 or not Path(lines[-1]).is_dir():
        raise RuntimeError(f"virtual controller not found: {(lines or [result.stderr.strip()])[-1]}")
    return lines[-2], Path(lines[-1])


def home() -> Path:
    """HOME: of the running virtual controller, as a folder of this PC."""
    if given := os.environ.get("CROSSARM_RS_HOME"):
        return Path(given)
    return _controller()[1]


def system() -> str:
    """The name of the running virtual controller's system (RobotStudio names it after the robot)."""
    return _controller()[0]


def status() -> str:
    """The controller's execution state and its latest events: why a request got no answer."""
    result = subprocess.run(["powershell", "-NoProfile", "-Command", _STATUS], capture_output=True, text=True,
                            encoding="oem", errors="replace", timeout=120, check=False)  # fmt: skip
    return "; ".join(result.stdout.strip().splitlines()) or result.stderr.strip()


def served_copy(text: str) -> str:
    """The module as the server runs it: a Stop would stop the server, so it becomes a remark."""
    return _STOP.sub(r"\1! Stop; (taken out by CrossArm: run by the probe server)", text)


def run(module: Path, routine: str, timeout: float = 120, folder: Path | None = None) -> str:
    """Have the server run `routine` of `module`: 'done', 'error N in routine', or why nothing ran."""
    folder = folder or home()
    queue = folder / "crossarm"
    queue.mkdir(exist_ok=True)
    (queue / "done.txt").unlink(missing_ok=True)
    if (queue / "request.txt").exists():
        return "server not running: an earlier request is still waiting (start CrossArmServer, PP to Main)"
    text = module.read_text(encoding="utf-8", errors="replace")
    (queue / module.name).write_text(served_copy(text), encoding="utf-8", newline="")
    request = queue / "request.tmp"
    request.write_text(f"{module.name}\r\n{routine}\r\n", encoding="ascii", newline="")
    request.replace(queue / "request.txt")  # whole, or not at all: the server polls for it
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        done = queue / "done.txt"
        if done.exists():
            answer = done.read_text(encoding="utf-8", errors="replace").strip()
            if answer:
                done.unlink()
                return answer
        time.sleep(0.2)
    if (queue / "request.txt").exists():
        (queue / "request.txt").unlink()
        return "server not running (start CrossArmServer in RobotStudio, PP to Main)"
    return f"timeout: {status()}"


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "home":
        print(home())
        return 0
    if len(sys.argv) in (4, 5) and sys.argv[1] == "run":
        timeout = float(sys.argv[4]) if len(sys.argv) == 5 else 120
        status = run(Path(sys.argv[2]), sys.argv[3], timeout)
        print(status)
        return 0 if status == "done" else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
