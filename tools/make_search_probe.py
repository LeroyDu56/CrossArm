# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the search probe: SearchL converted to a skip, run on ROBOGUIDE with the input switched
through COM when the TCP passes a point.

SearchProbe.mod searches along y from 50 to 250 mm, the input switching at y=150:
  SpStop   SearchL \\Stop: the point found (its y), where the robot stands after the search, then a move
           50 mm above the point found (Offs of a point known at run time);
  SpSup    SearchL \\Sup: the point found, and where the robot stands after the search (the point searched to);
  SpEarly  SearchL \\Stop with the input already on at the start: RAPID stops with an error, the converted
           program shows a MESSAGE and pauses.
The RobotStudio virtual controller has no signals to run SearchL on: what RAPID does is worked out by hand
(EXPECTED). Then moves at each of SPEEDS with and without a skip latching the position (written .LS):
the controller slows a move with `PR[k]=LPOS` down past a speed.

Usage:  python tools/make_search_probe.py write    SearchProbe.mod and the .LS in tests/fixtures/probes/search
        python tools/make_search_probe.py run      ROBOGUIDE: the three searches, then the speeds; results stored
        python tools/make_search_probe.py check    compare the stored results with EXPECTED
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.convert.translate import SKIP_SPEED_MAX
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, Motion, Position, Program
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "search"
RESULT = PROBE / "results" / "searchprobe_roboguide.txt"
WORK = ROOT / "local" / "search"
NINES = "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]"
SWITCH_Y = 150.0  # the input switches ON when the TCP's y reaches this
TOTALS = ("nFoundY", "nStopY", "nOffsY", "nOffsZ", "nSupFoundY", "nSupEndY")
ROUTINES = ["SpStop", "SpSup", "SpEarly"]
SPEEDS = (50, 100, 120, 250)

MODULE = "\r\n".join([
    "MODULE SearchProbe",
    "    ! CrossArm - search probe: see tools/make_search_probe.py.",
    f"    CONST robtarget pStart:=[[1100,50,1000],[0,1,0,0],[0,0,0,0],{NINES}];",
    f"    CONST robtarget pEnd:=[[1100,250,1000],[0,1,0,0],[0,0,0,0],{NINES}];",
    "    VAR robtarget pFound;",
    "    VAR robtarget pAt;",
    *[f"    VAR num {total}:=0;" for total in TOTALS],
    "",
    "    PROC SpStop()",
    "        MoveJ pStart,v1000,fine,tool0;",
    "        SearchL\\Stop,diProbe,pFound,pEnd,v50,tool0;",
    "        nFoundY:=pFound.trans.y;",
    "        pAt:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        nStopY:=pAt.trans.y;",
    "        MoveL Offs(pFound,0,0,50),v100,fine,tool0;",
    "        pAt:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        nOffsY:=pAt.trans.y;",
    "        nOffsZ:=pAt.trans.z;",
    "    ENDPROC",
    "",
    "    PROC SpSup()",
    "        MoveJ pStart,v1000,fine,tool0;",
    "        SearchL\\Sup,diProbe,pFound,pEnd,v50,tool0;",
    "        nSupFoundY:=pFound.trans.y;",
    "        pAt:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        nSupEndY:=pAt.trans.y;",
    "    ENDPROC",
    "",
    "    PROC SpEarly()",
    "        MoveJ pStart,v1000,fine,tool0;",
    "        SearchL\\Stop,diProbe,pFound,pEnd,v50,tool0;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# What RAPID does, worked out by hand: the point found where the input switched; \Stop stops past it and
# stays there (the FANUC comes back to it: nStopY within 1 mm of the switch); \Sup goes on to pEnd.
# Within 1 mm: the input is switched by a COM sampler reading the TCP about every 2.5 ms (0.125 mm at 50 mm/s).
EXPECTED = {"nFoundY": SWITCH_Y, "nStopY": SWITCH_Y, "nOffsY": SWITCH_Y, "nOffsZ": 1050.0, "nSupFoundY": SWITCH_Y,
            "nSupEndY": 250.0}  # fmt: skip
TOLERANCE = {"nFoundY": 1.0, "nStopY": 1.0, "nOffsY": 1.0, "nOffsZ": 0.05, "nSupFoundY": 1.0, "nSupEndY": 0.05}

SAMPLER = r"""
param([string]$Out, [string]$Stop, [double]$From, [double]$At)
$r = New-Object -ComObject FRRobot.FRCRobot
$r.ConnectEx("127.0.0.1", $false, 10, 1)
$g = $r.CurPosition.Group(1, 0)
$di = $r.IOTypes.Item(1).Signals.Item(1)
$w = New-Object IO.StreamWriter($Out)
$sw = [Diagnostics.Stopwatch]::StartNew()
$last = ""; $n = 0; $armed = $false; $done = $false
$di.Simulate = $true; $di.Value = $false
while ($true) {
  $g.Refresh()
  $f = $g.Formats(2)
  if (-not $armed -and $f.Y -le $From + 5) { $armed = $true }
  if ($armed -and -not $done -and $f.Y -ge $At) { $di.Value = $true; $done = $true }
  $line = "{0:F3},{1}" -f $f.Y, $di.Value
  if ($line -ne $last) { $w.WriteLine(("{0:F1}," -f $sw.Elapsed.TotalMilliseconds) + $line); $last = $line }
  $n++
  if ($n % 200 -eq 0 -and (Test-Path $Stop)) { break }
}
$di.Value = $false
$w.Close()
"""
EARLY = r"""
$r = New-Object -ComObject FRRobot.FRCRobot
$r.ConnectEx("127.0.0.1", $false, 10, 1)
$di = $r.IOTypes.Item(1).Signals.Item(1)
$di.Simulate = $true
$di.Value = $VALUE
"""


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="SearchProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1), digital_inputs={"DIPROBE": 1})
    result = convert([parsed.module], config, routines=ROUTINES, sources={"SearchProbe": MODULE})
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    numbers = {a.rapid_name.upper(): a.number for a in result.registers}
    return {total: numbers[total.upper()] for total in TOTALS}


def programs() -> dict[str, str]:
    return {info.program.name: write_ls(info.program) for info in conversion().programs}


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    for stale in PROBE.glob("*.LS"):
        stale.unlink()
    (PROBE / "SearchProbe.mod").write_bytes(MODULE.encode("ascii"))
    for name, text in programs().items():
        (PROBE / f"{name}.LS").write_bytes(text.encode("ascii"))
        print(f"{name}.LS")


def _replace(roboguide, name: str, path: Path) -> None:
    roboguide.release(name)
    try:
        roboguide.delete(name)  # a copy from an earlier run: FTP does not replace it
    except Exception:  # noqa: BLE001, S110 - not there
        pass
    reason = roboguide.load(path)
    if reason:
        raise RuntimeError(f"{name} not loaded: {reason}")


def _sampled(roboguide, name: str, start: float, switch: float, timeout: float = 120) -> tuple[str, list[tuple]]:
    """Run a program while the sampler switches DI[1] ON when the TCP's y reaches `switch` (once it has been
    near `start`): the run's status and the samples (ms, y, DI[1])."""
    WORK.mkdir(parents=True, exist_ok=True)
    out, stop, script = WORK / "samples.csv", WORK / "samples.stop", WORK / "sampler.ps1"
    stop.unlink(missing_ok=True)
    out.unlink(missing_ok=True)
    script.write_text(SAMPLER, encoding="utf-8")
    sampler = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                                "-Out", str(out), "-Stop", str(stop), "-From", str(start), "-At", str(switch)],
                               stdout=subprocess.DEVNULL)  # fmt: skip
    end = time.monotonic() + 60
    while not out.exists() and time.monotonic() < end:  # created when the sampler is connected
        time.sleep(0.2)
    time.sleep(1.0)  # it has set the input and read the TCP at least once
    status = roboguide.run(name, timeout)
    stop.write_text("stop", encoding="ascii")
    sampler.wait(timeout=60)
    rows = []
    for line in out.read_text(encoding="ascii").splitlines():
        ms, y, value = line.split(",")
        rows.append((float(ms), float(y), value.strip().lower() in ("true", "-1", "1")))
    return status, rows


def _switched_at(rows: list[tuple]) -> float | None:
    """The TCP's y in the sample where DI[1] went ON."""
    return next((r[1] for i, r in enumerate(rows) if r[2] and i and not rows[i - 1][2]), None)


def _set_input(value: bool) -> None:
    script = EARLY.replace("$VALUE", "$true" if value else "$false")
    subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, timeout=60, check=False)


def speed_program(speed: int, latched: bool) -> Program:
    """A move at `speed` along y from -150 to 450, with a skip latching the position (`latched`) or none; the
    input never switches."""
    points = [Position(i + 1, 0, 1, CartesianPosition(1100, y, 1000, 180, 0, 0, "N U T, 0, 0, 0"))
              for i, y in enumerate((-150.0, 450.0))]  # fmt: skip
    options = "Skip,LBL[1],PR[90]=LPOS" if latched else ""
    lines = [Instruction("UFRAME_NUM=0"), Instruction("UTOOL_NUM=1"), Motion("J", "P[1]", "20%", "FINE"),
             Instruction("WAIT    .50(sec)"), Instruction("SKIP CONDITION DI[1]=ON"),
             Motion("L", "P[2]", f"{speed}mm/sec", "FINE", options=options), Instruction("LBL[1]")]  # fmt: skip
    name = f"SKSPD{speed}{'L' if latched else 'P'}"
    return Program(name, lines, points, Attributes(comment="search probe", created=datetime(2026, 1, 1)))


def _speed(rows: list[tuple]) -> float:
    """The TCP's speed (mm/s, the PC's clock) between y=0 and y=140 on the way out."""
    last = len(rows) - 1
    while last > 0 and rows[last - 1][1] >= rows[last][1]:  # stopped at the end
        last -= 1
    first = last
    while first > 0 and rows[first - 1][1] < rows[first][1]:  # back to the start of the move out
        first -= 1
    out = [r for r in rows[first : last + 1] if 0 <= r[1] <= 140]
    return (out[-1][1] - out[0][1]) / (out[-1][0] - out[0][0]) * 1000 if len(out) > 2 else float("nan")


def _latched_y(roboguide) -> float | None:
    from make_pose_probe import read_posreg

    found = read_posreg(roboguide.page("md/POSREG.VA")).get(90)
    return found[1] if found else None


def measure() -> list[str]:
    """Run the converted searches, then moves at each of SPEEDS with and without a skip latching the position,
    on ROBOGUIDE: the results as 'name value' lines."""
    import roboguide

    WORK.mkdir(parents=True, exist_ok=True)
    result = conversion()
    names = [info.program.name for info in result.programs]
    for info in result.programs:
        path = WORK / f"{info.program.name}.LS"
        path.write_bytes(write_ls(info.program).encode("ascii"))
        _replace(roboguide, info.program.name, path)
    numbers = registers(result)
    roboguide.zero(list(numbers.values()))
    out: list[str] = []
    try:
        for name in ("SPSTOP", "SPSUP"):
            status, rows = _sampled(roboguide, name, 50.0, SWITCH_Y)
            out += [f"{name}_status {status.replace(' ', '_')}", f"{name}_switched_y {_switched_at(rows)}"]
        values = roboguide.numreg()
        out += [f"{total} {values.get(number, float('nan')):g}" for total, number in numbers.items()]
        _set_input(True)  # already on at the start: RAPID raises ERR_SIGSUPSEARCH
        out.append(f"SPEARLY_status {roboguide.run('SPEARLY', 60).replace(' ', '_')}")
        roboguide.release("SPEARLY")
    finally:
        _set_input(False)
        for name in names:
            roboguide.release(name)
            roboguide.delete(name)
    for speed in SPEEDS:
        for latched in (False, True):
            program = speed_program(speed, latched)
            path = WORK / f"{program.name}.LS"
            path.write_bytes(write_ls(program).encode("ascii"))
            _replace(roboguide, program.name, path)
            status, rows = _sampled(roboguide, program.name, -150.0, 9999.0)  # never switched
            out.append(f"speed{speed}_{'latched' if latched else 'plain'} {_speed(rows):.1f}")
            roboguide.release(program.name)
            roboguide.delete(program.name)
    return out


def run() -> None:
    write()
    out = measure()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(RESULT.read_text(encoding="utf-8"))
    check()


def read_results(text: str) -> dict[str, str]:
    return dict(line.split(" ", 1) for line in text.splitlines() if line.strip())


def verdict(found: dict[str, str]) -> tuple[bool, list[str]]:
    """Whether the results are those RAPID gives (EXPECTED), the search with the input on pauses, and the skip
    latching the position slows no move up to SKIP_SPEED_MAX; and what was compared."""
    ok, lines = True, []
    for total, expected in EXPECTED.items():
        value = float(found.get(total, "nan"))
        near = abs(value - expected) <= TOLERANCE[total]
        ok &= near
        lines.append(f"{total:11s} ROBOGUIDE {value:9.3f}  RAPID {expected:9.3f}  {'ok' if near else 'DIFFERENT'}")
    early = found.get("SPEARLY_status", "")
    ok &= early.startswith("paused")
    lines.append(f"SPEARLY     {early}  (RAPID: stops with an error)")
    for speed in SPEEDS:
        plain, latched = float(found.get(f"speed{speed}_plain", "nan")), float(found.get(f"speed{speed}_latched", "nan"))
        kept = latched >= 0.95 * plain
        if speed <= SKIP_SPEED_MAX:
            ok &= kept
        lines.append(f"{speed:4d} mm/s: {plain:6.1f} mm/s without a skip, {latched:6.1f} with PR[90]=LPOS"
                     f"{'' if kept else '  (slowed down)'}")
    return ok, lines


def check() -> bool:
    ok, lines = verdict(read_results(RESULT.read_text(encoding="utf-8")))
    print("\n".join(lines))
    return ok


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
