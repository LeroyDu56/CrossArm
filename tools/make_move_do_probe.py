# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Measure where an output set on the line after a FINE move switches: CrossArm's MoveLDO to a fine point.

RAPID's MoveLDO sets its output when the robot reaches a fine point (the RobotStudio virtual controller
has no signals to run it on). CrossArm writes the move, then `DO[n]=ON`. This probe runs that on ROBOGUIDE,
reading the TCP and DO[1] through COM while it runs, and records how far from the point the TCP is when the
output switches, and how long after the TCP is within 0.5 mm of it.

  python tools/make_move_do_probe.py run      ROBOGUIDE; result in tests/fixtures/probes/movedo/results
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, Motion, Position, Program

PROBE = ROOT / "tests" / "fixtures" / "probes" / "movedo"
RESULT = PROBE / "results" / "movedo_roboguide.txt"
PROGRAM = "MOVEDO"
TARGET_Y = 250.0  # P[2]: the TCP moves along y from 50 to 250, tool0 pointing down in front of the robot

SAMPLER = r"""
param([string]$Out, [string]$Stop)
$r = New-Object -ComObject FRRobot.FRCRobot
$r.ConnectEx("127.0.0.1", $false, 10, 1)
$g = $r.CurPosition.Group(1, 0)
$do = $r.IOTypes.Item(2).Signals.Item(1)
$w = New-Object IO.StreamWriter($Out)
$sw = [Diagnostics.Stopwatch]::StartNew()
$last = ""; $n = 0
while ($true) {
  $g.Refresh()
  $f = $g.Formats(2)
  $line = "{0:F3},{1:F3},{2:F3},{3}" -f $f.X, $f.Y, $f.Z, $do.Value
  if ($line -ne $last) { $w.WriteLine(("{0:F1}," -f $sw.Elapsed.TotalMilliseconds) + $line); $last = $line }
  $n++
  if ($n % 200 -eq 0 -and (Test-Path $Stop)) { break }
}
$w.Close()
"""


def program() -> Program:
    points = [Position(i + 1, 0, 1, CartesianPosition(1100, y, 1000, 180, 0, 0, "N U T, 0, 0, 0"))
              for i, y in enumerate((50.0, TARGET_Y))]  # fmt: skip
    lines = [Instruction("UFRAME_NUM=0"), Instruction("UTOOL_NUM=1"), Instruction("DO[1]=OFF"),
             Motion("J", "P[1]", "20%", "FINE"), Instruction("WAIT    .50(sec)"),
             Motion("L", "P[2]", "500mm/sec", "FINE"), Instruction("DO[1]=ON"), Instruction("WAIT    .50(sec)"),
             Instruction("DO[1]=OFF")]  # fmt: skip
    return Program(PROGRAM, lines, points, Attributes(comment="movedo probe", created=datetime(2026, 1, 1)))


def measure() -> tuple[float, float]:
    """(mm from the point, ms after the TCP came within 0.5 mm of it) when DO[1] switches ON on ROBOGUIDE."""
    import roboguide

    PROBE.mkdir(parents=True, exist_ok=True)
    path = PROBE / f"{PROGRAM}.LS"
    path.write_bytes(write_ls(program()).encode("ascii"))
    roboguide.release(PROGRAM)
    try:
        roboguide.delete(PROGRAM)
    except Exception:  # noqa: BLE001, S110 - not there
        pass
    reason = roboguide.load(path)
    if reason:
        raise RuntimeError(f"{PROGRAM} not loaded: {reason}")
    work = ROOT / "local" / "movedo"
    work.mkdir(parents=True, exist_ok=True)
    out, stop, script = work / "samples.csv", work / "samples.stop", work / "sampler.ps1"
    stop.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    script.write_text(SAMPLER, encoding="utf-8")
    sampler = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                                "-Out", str(out), "-Stop", str(stop)], stdout=subprocess.DEVNULL)  # fmt: skip
    end = time.monotonic() + 60
    while not (out.exists() and out.stat().st_size) and time.monotonic() < end:
        time.sleep(0.2)
    status = roboguide.run(PROGRAM, 60)
    stop.write_text("stop", encoding="ascii")
    sampler.wait(timeout=60)
    roboguide.delete(PROGRAM)
    if status != "done":
        raise RuntimeError(f"{PROGRAM}: {status}")
    rows = []
    for line in out.read_text(encoding="ascii").splitlines():
        ms, _x, y, _z, value = line.split(",")
        rows.append((float(ms), float(y), value.strip().lower() in ("true", "-1", "1")))
    index = next(i for i, r in enumerate(rows) if r[2] and i and not rows[i - 1][2])
    on, arrive = rows[index], index
    while arrive > 0 and abs(rows[arrive - 1][1] - TARGET_Y) < 0.5:  # back to where the TCP came within 0.5 mm
        arrive -= 1
    return abs(TARGET_Y - on[1]), on[0] - rows[arrive][0]


def run() -> None:
    distance, delay = measure()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(f"distance_mm {distance:.3f}\nafter_within_0.5mm_ms {delay:.0f}\n", encoding="ascii")
    print(RESULT.read_text(encoding="ascii"))


if __name__ == "__main__":
    {"run": run}[sys.argv[1] if len(sys.argv) > 1 else "run"]()
