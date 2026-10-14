# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the StopMove probe (--karel): the robot's motion paused and resumed, in TRAPs and in line.

StopProbe.mod, converted by CrossArm with --karel (each StopMove / StartMove `CALL CA_STOPMOVE(op,where)`, each
TRAP touching the motion ignoring pause requests, CA_STOPMOVE compiled by FANUC ktrans), moves the robot along three
lines; ROBOGUIDE's robot position is read through COM over and over while STOPPROBE runs, and inputs are switched
through COM as the TCP passes points:

- first line: diStopA on for 2 s once x passes 1200; its TRAP stops the motion, waits for the input to drop and
  starts it again (StartMove in a routine it calls);
- second line, in the program: a CNT move, StopMove, a 2 s wait, StartMove;
- third line: diHoldB pulsed once y passes -100, its TRAP stops the motion and clears the path; 1.5 s later
  diEnable goes on: its TRAP (armed on any change) starts the motion, or stops it when the input is off. Once y
  passes 100, diEnable goes off for 1.5 s. The TRAP of diHoldB, its program paused, waits for diEnable itself and
  runs that TRAP; diEnable's TRAP, stopping the robot, waits for its next change and runs again.

What RAPID does: the robot stops on its line while it is held and goes on along the same line to the same point;
nPaused 1, nHolds 1, nEnables 3 (on, off, on).

Measured before (raw programs, 2026-10-14): KAREL HOLD from a task without a group stops the robot but UNHOLD and
RESUME fail there (INTP-350 / INTP-353, PROG-040); KAREL STOP from it does not hold the robot; PAUSE_TASK pauses the
TRAP too unless its program ignores pause requests by command (2; 1 or 4 do not); no condition monitor fires while
its program is paused, nor afterwards for a change made meanwhile; in the moving program STOP / RESUME work, do
nothing with nothing stopped, and STOP does not hold the next move line.

  python tools/make_stopmove_probe.py write    the module and the programs, in tests/fixtures/probes/stopmove
  python tools/make_stopmove_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results stored
  python tools/make_stopmove_probe.py check    the stored results against what was measured
"""

import ftplib
import io
import math
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ktrans import KarelRequest, export
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, Position, Program
from crossarm.rapid import parse_text
from crossarm.rapid.eio import Signal

PROBE = ROOT / "tests" / "fixtures" / "probes" / "stopmove"
RESULT = PROBE / "results" / "stopmove_roboguide.txt"
PROGRAM = "STOPPROBE"
SETUP = "SMSETUP"
STAMP = datetime(2026, 1, 1)
START, CORNER, END = (1100.0, -200.0, 800.0), (1400.0, -200.0, 800.0), (1400.0, 200.0, 800.0)
STILL_MM = 0.1  # two samples this close: the robot stands still (it creeps the last hundredths)
TOLERANCE = 0.5  # mm off the lines, while it moves
EXPECTED = {"nPaused": "1", "nHolds": "1", "nEnables": "3", "nDone": "1"}
TRAPS = {"a": "TSTOPA", "b": "THOLDB", "e": "TENABLE"}  # the TRAP each input calls
_Q = "[0,0.3826834,0.9238795,0]"
MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE StopProbe",
    "    ! CrossArm - StopMove probe: see tools/make_stopmove_probe.py.",
    f"    CONST robtarget smStart:=[[1100,-200,800],{_Q},[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    f"    CONST robtarget smCorner:=[[1400,-200,800],{_Q},[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    f"    CONST robtarget smEnd:=[[1400,200,800],{_Q},[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    "    VAR intnum iStopA;",
    "    VAR intnum iHoldB;",
    "    VAR intnum iEnable;",
    "    VAR num nPaused:=0;",
    "    VAR num nHolds:=0;",
    "    VAR num nEnables:=0;",
    "    VAR num nDone:=0;",
    "",
    "    PROC StopProbe()",
    "        nPaused:=0;",
    "        nHolds:=0;",
    "        nEnables:=0;",
    "        nDone:=0;",
    "        IDelete iStopA;",
    "        IDelete iHoldB;",
    "        IDelete iEnable;",
    "        MoveJ smStart,v1000,fine,tool0;",
    "        CONNECT iStopA WITH tStopA;",
    "        ISignalDI diStopA,1,iStopA;",
    "        MoveL smCorner,v100,fine,tool0;",
    "        IDelete iStopA;",
    "        MoveL smStart,v1000,fine,tool0;",
    "        MoveL smCorner,v100,z100,tool0;",
    "        StopMove;",
    "        WaitTime 2;",
    "        StartMove;",
    "        CONNECT iHoldB WITH tHoldB;",
    "        ISignalDI diHoldB,1,iHoldB;",
    "        CONNECT iEnable WITH tEnable;",
    "        ISignalDI diEnable,edge,iEnable;",
    "        MoveL smEnd,v100,fine,tool0;",
    "        IDelete iHoldB;",
    "        IDelete iEnable;",
    "        nDone:=1;",
    "    ENDPROC",
    "",
    "    TRAP tStopA",
    "        StopMove;",
    "        nPaused:=nPaused+1;",
    "        StopWait;",
    "    ENDTRAP",
    "",
    "    PROC StopWait()",
    "        WaitDI diStopA,0;",
    "        StartMove;",
    "    ENDPROC",
    "",
    "    TRAP tHoldB",
    "        StopMove;",
    "        ClearPath;",
    "        nHolds:=nHolds+1;",
    "    ENDTRAP",
    "",
    "    TRAP tEnable",
    "        nEnables:=nEnables+1;",
    "        IF diEnable=1 THEN",
    "            StartMove;",
    "        ELSE",
    "            StopMove;",
    "        ENDIF",
    "    ENDTRAP",
    "ENDMODULE",
    "",
])  # fmt: skip
SIGNALS = {"DISTOPA": Signal("diStopA", "DI"), "DIHOLDB": Signal("diHoldB", "DI"),
           "DIENABLE": Signal("diEnable", "DI")}  # fmt: skip
ROUTINES = ["StopProbe", "tStopA", "StopWait", "tHoldB", "tEnable"]


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="StopProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=True), routines=ROUTINES,
                     sources={"StopProbe": MODULE}, signals=SIGNALS)  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def setup_program() -> Program:
    """UTOOL[1] = tool0 (zero), as the moves of the probe use it."""
    lines = [Instruction("PR[20]=P[1]"), Instruction("UTOOL[1]=PR[20]")]
    positions = [Position(1, 0, 1, CartesianPosition(0.0, 0.0, 0.0, 0.0, 0.0, 0.0))]
    return Program(SETUP, list(lines), positions, Attributes(comment="StopMove setup", created=STAMP))


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "StopProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    for info in result.programs:
        (PROBE / f"{info.program.name}.LS").write_bytes(write_ls(info.program).encode("ascii"))
    (PROBE / f"{SETUP}.LS").write_bytes(write_ls(setup_program()).encode("ascii"))


def inputs() -> dict[str, int]:
    """'a', 'b', 'e' -> the DI each condition program watches, as CrossArm numbered them."""
    found = {}
    for path in PROBE.glob("*.LS"):
        for number, trap in re.findall(r"WHEN DI\[(\d+)\]=ON\+,CALL (\w+)", path.read_text(encoding="ascii")):
            found.update({key: int(number) for key, name in TRAPS.items() if name == trap})
    if set(found) != set(TRAPS):
        raise RuntimeError(f"condition programs found for {sorted(found)} only")
    return found


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------

SAMPLER = r"""
param([string]$Out, [string]$Name, [int]$InA, [int]$InB, [int]$InE, [int]$Timeout)
$r = New-Object -ComObject FRRobot.FRCRobot
$r.ConnectEx("{host}", $false, 10, 1)
$g = $r.CurPosition.Group(1, 0)
$sa = $r.IOTypes.Item(1).Signals.Item($InA)
$sb = $r.IOTypes.Item(1).Signals.Item($InB)
$se = $r.IOTypes.Item(1).Signals.Item($InE)
foreach ($s in @($sa, $sb, $se)) {{ $s.Simulate = $true; $s.Value = $false }}
$r.KCL("RESET", $true)
$w = New-Object IO.StreamWriter($Out)
$sw = [Diagnostics.Stopwatch]::StartNew()
$r.Programs.Item($Name).Run()
$armed = $false; $phase = 0; $t = 0; $last = ""
while ($sw.Elapsed.TotalSeconds -lt $Timeout) {{
  $g.Refresh(); $f = $g.Formats(2); $ms = $sw.Elapsed.TotalMilliseconds
  if (-not $armed -and [math]::Abs($f.X - 1100) -lt 0.5 -and [math]::Abs($f.Y + 200) -lt 0.5) {{ $armed = $true }}
  if ($armed -and $phase -eq 0 -and $f.X -ge 1200 -and $f.Y -lt -150) {{ $sa.Value = $true; $phase = 1; $t = $ms }}
  elseif ($phase -eq 1 -and $ms -ge $t + 2000) {{ $sa.Value = $false; $phase = 2 }}
  elseif ($phase -eq 2 -and $f.Y -ge -100) {{ $sb.Value = $true; $phase = 3; $t = $ms }}
  elseif ($phase -eq 3 -and $ms -ge $t + 300) {{ $sb.Value = $false; $phase = 4 }}
  elseif ($phase -eq 4 -and $ms -ge $t + 1500) {{ $se.Value = $true; $phase = 5 }}
  elseif ($phase -eq 5 -and $f.Y -ge 100) {{ $se.Value = $false; $phase = 6; $t = $ms }}
  elseif ($phase -eq 6 -and $ms -ge $t + 1500) {{ $se.Value = $true; $phase = 7 }}
  $task = @($r.Tasks | Where-Object {{ $_.Name -eq $Name }})[0]
  $status = if ($task -eq $null) {{ -1 }} else {{ $task.Status }}
  $line = "{{0:F3}} {{1:F3}} {{2:F3}} {{3}} {{4}}" -f $f.X, $f.Y, $f.Z, $phase, $status
  if ($line -ne $last) {{ $w.WriteLine(("{{0:F0}} " -f $ms) + $line); $last = $line }}
  if ($status -eq 2 -and $sw.Elapsed.TotalSeconds -gt 1) {{ break }}
}}
foreach ($s in @($sa, $sb, $se)) {{ $s.Value = $false; $s.Simulate = $false }}
$w.Close()
"""


def _sampled(work: Path, numbers: dict[str, int], timeout: int = 90) -> list[str]:
    import roboguide

    script = work / "sampler.ps1"
    script.write_text(SAMPLER.format(host=roboguide.HOST), encoding="ascii")
    out = work / "samples.txt"
    done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Out",
                           str(out), "-Name", PROGRAM, "-InA", str(numbers["a"]), "-InB", str(numbers["b"]),
                           "-InE", str(numbers["e"]), "-Timeout", str(timeout)], capture_output=True, text=True,
                          timeout=timeout + 60, check=False)  # fmt: skip
    if done.stderr.strip():
        print("sampler:", done.stderr.strip()[:1500])
    return out.read_text(encoding="ascii").splitlines() if out.is_file() else []


def _ftp(command: str, path: Path | None = None) -> str:
    import roboguide

    ftp = ftplib.FTP()
    ftp.connect(roboguide.HOST, roboguide.FTP_PORT, timeout=30)
    ftp.login()
    try:
        if command == "STOR" and path is not None:
            ftp.storbinary(f"STOR {path.name}", io.BytesIO(path.read_bytes()))
        else:
            ftp.delete(command.split(" ", 1)[1])
        return ""
    except ftplib.error_perm as exc:
        return str(exc)
    finally:
        ftp.quit()


def measure() -> dict[str, str]:
    import make_maketp_probe
    import roboguide

    write()
    numbers = registers(conversion())
    signals = inputs()
    # the TRAPs before the condition programs calling them, the main program last
    programs = sorted((p.stem for p in PROBE.glob("*.LS")),
                      key=lambda s: (s in (PROGRAM, SETUP), not s.startswith(("T", "STOPW")), s))  # fmt: skip
    found: dict[str, str] = {"inputs": " ".join(f"{k}={v}" for k, v in sorted(signals.items()))}
    with tempfile.TemporaryDirectory(prefix="crossarm_stopmove_") as temp:
        work = Path(temp)
        out = export(["CA_STOPMOVE"], work, KarelRequest(make_maketp_probe.robot()), log=print)
        if not out.compiled:
            raise RuntimeError(f"CA_STOPMOVE not compiled: {out.problem or out.refused}")
        pc = next(work.rglob("ca_stopmove.pc"))
        for name in programs:
            roboguide.release(name)
        roboguide.select()
        try:
            found["pc_load"] = _ftp("STOR", pc) or "loaded"
            for name in programs:
                found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
            for trap in TRAPS.values():
                try:
                    stored = roboguide.page(f"md/{trap}.LS")
                except OSError:
                    stored = ""  # not loaded: said by its _load
                found[f"{trap}_pause_request"] = (re.search(r"PAUSE_REQUEST\s*=\s*(\d+)", stored) or ["", "?"])[1]
            if any(value != "loaded" for key, value in found.items() if key.endswith("_load")):
                return found
            found["setup_run"] = roboguide.run(SETUP, 60)
            roboguide.zero(list(numbers.values()))
            before = roboguide._alarms() or set()
            samples = _sampled(work, signals)
            after = roboguide._alarms() or set()
            found["alarms"] = " | ".join(sorted(re.sub(r"\s+", " ", a).split('"')[1].strip() for a in after - before
                                                if "INTP-" in a or "MOTN-" in a)) or "none"  # fmt: skip
            values = roboguide.numreg()
            for name, number in numbers.items():
                found[name] = f"{values.get(number, float('nan')):g}"
            found.update({f"s{i:04d}": s for i, s in enumerate(samples)})
        finally:
            for name in programs:
                roboguide.release(name)
            roboguide.select()
            for name in programs:
                _ftp(f"DELE {name.lower()}.tp")
            _ftp("DELE ca_stopmove.pc")
            _ftp("DELE ca_stopmove.vr")
    return found


# -- what the samples show ------------------------------------------------------------------------------------------


def _samples(found: dict[str, str]) -> list[tuple[float, float, float, float, int, int]]:
    """(s, x, y, z, phase of the inputs, task status) in the order read."""
    out = []
    for key in sorted(k for k in found if re.fullmatch(r"s\d{4}", k)):
        t, x, y, z, phase, status = found[key].split()
        out.append((float(t) / 1000, float(x), float(y), float(z), int(phase), int(status)))
    return out


def _stops(samples) -> list[tuple[float, float, tuple[float, float, float]]]:
    """(from, to, where) of each time the robot stood still for more than 0.5 s away from the three points, from
    its first arrival on smStart on (the MoveJ there and the fine points do not count)."""
    first = next((i for i, s in enumerate(samples) if math.dist(s[1:4], START) <= 0.05), len(samples))
    stops, begin = [], first
    for i in range(first + 1, len(samples) + 1):
        if i < len(samples) and math.dist(samples[i][1:4], samples[begin][1:4]) <= STILL_MM:
            continue
        t0, t1, where = samples[begin][0], samples[i - 1][0], samples[begin][1:4]
        if t1 - t0 > 0.5 and min(math.dist(where, p) for p in (START, CORNER, END)) > 0.05:
            stops.append((t0, t1, where))
        begin = i
    return stops


def _off_line(p, a, b) -> float:
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    s = max(0.0, min(1.0, sum(ab[i] * ap[i] for i in range(3)) / sum(v * v for v in ab)))
    return math.dist(p, [a[i] + s * ab[i] for i in range(3)])


def analysis(found: dict[str, str]) -> dict[str, float]:
    samples = _samples(found)
    first = next((i for i, s in enumerate(samples) if math.dist(s[1:4], START) <= 0.05), None)
    if first is None:
        return {}

    def when(phase: int) -> float:
        return next((s[0] for s in samples if s[4] >= phase), math.nan)

    out = {f"t{p}": when(p) for p in range(1, 8)}
    out["path_mm"] = max(min(_off_line(s[1:4], START, CORNER), _off_line(s[1:4], CORNER, END))
                         for s in samples[first:])  # fmt: skip
    out["end_mm"] = math.dist(samples[-1][1:4], END)
    for i, (t0, t1, where) in enumerate(_stops(samples)):
        out.update({f"stop{i}_from": t0, f"stop{i}_to": t1, f"stop{i}_x": where[0], f"stop{i}_y": where[1]})
    return out


def _stop(a: dict[str, float], i: int) -> tuple[float, float, float, float] | None:
    return (a[f"stop{i}_from"], a[f"stop{i}_to"], a[f"stop{i}_x"], a[f"stop{i}_y"]) if f"stop{i}_from" in a else None


def verdict(found: dict[str, str]) -> str:
    wrong = []
    for key, value in found.items():
        if key.endswith(("_load", "_run")) and value not in ("loaded", "done"):
            wrong.append(f"{key}: {value}")
        if key.endswith("_pause_request") and value != "2":
            wrong.append(f"{key} {value}, 2 written")
    if found.get("alarms") != "none":
        wrong.append(f"alarms: {found.get('alarms')}")
    counts = {name: found.get(name) for name in EXPECTED}
    if counts != EXPECTED:
        wrong.append(f"{counts}, RAPID {EXPECTED}")
    a = analysis(found)
    if not a:
        return "; ".join([*wrong, "no position read"])
    stops = [_stop(a, i) for i in range(4)]
    if None in stops or _stop(a, 4) is not None:
        return "; ".join([*wrong, f"{sum(s is not None for s in stops)} stops of the robot, 4 expected"])
    (a0, a1, ax, ay), (l0, l1, lx, ly), (b0, b1, bx, by), (e0, e1, ex, ey) = stops  # type: ignore[misc]
    if not (a0 - a["t1"] < 0.6 and abs(a1 - a["t2"]) < 0.6 and 1200 < ax < 1300 and abs(ay - START[1]) < 0.5):
        wrong.append(f"diStopA stop {a0:.2f}-{a1:.2f} s at x {ax:.1f}, input on {a['t1']:.2f}-{a['t2']:.2f} s")
    if not (1.5 < l1 - l0 < 2.6 and CORNER[0] - 30 < lx <= CORNER[0] + 0.05 and abs(ly - CORNER[1]) < 0.5):
        wrong.append(f"in-line stop {l1 - l0:.2f} s at x {lx:.1f}")
    if not (b0 - a["t3"] < 0.6 and abs(b1 - a["t5"]) < 0.6 and -100 < by < 0 and abs(bx - CORNER[0]) < 0.5):
        wrong.append(f"diHoldB stop {b0:.2f}-{b1:.2f} s at y {by:.1f}, diEnable on at {a['t5']:.2f} s")
    if not (e0 - a["t6"] < 0.6 and abs(e1 - a["t7"]) < 0.6 and 100 < ey < 200 and abs(ex - CORNER[0]) < 0.5):
        wrong.append(f"diEnable stop {e0:.2f}-{e1:.2f} s at y {ey:.1f}, input off {a['t6']:.2f}-{a['t7']:.2f} s")
    if a["path_mm"] > TOLERANCE:
        wrong.append(f"{a['path_mm']:.3f} mm off the lines")
    if a["end_mm"] > 0.05:
        wrong.append(f"ends {a['end_mm']:.3f} mm from the last point")
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    a = analysis(found)
    (a0, a1, ax, _), (l0, l1, lx, _), (b0, b1, _, by), (e0, e1, _, ey) = [_stop(a, i) for i in range(4)]  # type: ignore[misc]
    return (f"stopped {a1 - a0:.2f} s at x {ax:.1f} (TRAP), {l1 - l0:.2f} s at x {lx:.2f} (in line), {b1 - b0:.2f} s"
            f" at y {by:.1f} (TRAP waiting for another), {e1 - e0:.2f} s at y {ey:.1f} (TRAP on any change); counts as"
            f" RAPID; on the lines within {a['path_mm']:.3f} mm, last point {a['end_mm']:.3f} mm")


def run() -> str:
    found = measure()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text("".join(f"{k} {v}\n" for k, v in found.items()), encoding="ascii")
    return check()


def stored() -> dict[str, str]:
    return dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())


def check() -> str:
    found = stored()
    problem = verdict(found)
    print(f"FAIL {problem}" if problem else f"stopmove probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
