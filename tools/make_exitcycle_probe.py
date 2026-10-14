# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the ExitCycle probe (--karel): the cycle ended from a TRAP and in line, the program run again.

ExitProbe.mod, converted by CrossArm with --karel (each ExitCycle `CALL CA_EXITCYCLE(1)`, the TRAP's StopMove
`CALL CA_STOPMOVE(1,1)`, the KAREL programs compiled by FANUC ktrans), counts its cycles:

- first cycle: diAbort switched on through COM once the TCP passes x 1250 on its way to the corner; its TRAP stops
  the motion, clears the path and ends the cycle;
- second cycle: a routine ends it in line, after a move through a zone to the corner;
- third cycle: the program runs to its end.

What RAPID does: nCycles 3 (data keep their values through ExitCycle), nTraps 1, nAfter 0 (the line after an
ExitCycle never runs), nDone 3; the robot stops on its line in the first cycle and goes back to the start.

Measured before (raw programs, 2026-10-14): ABORT_TASK of the task holding the robot from a TRAP ends the TRAP too,
nothing runs again; started as a task of its own by RUN_TASK, the KAREL program aborts it and runs it again, from
the program and from a TRAP; a task aborted while paused (StopMove) stays aborted when RUN_TASK follows at once,
RUN_TASK accepting: 0.1 s first.

  python tools/make_exitcycle_probe.py write    the module and the programs, in tests/fixtures/probes/exitcycle
  python tools/make_exitcycle_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results stored
  python tools/make_exitcycle_probe.py check    the stored results against what was measured
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

PROBE = ROOT / "tests" / "fixtures" / "probes" / "exitcycle"
RESULT = PROBE / "results" / "exitcycle_roboguide.txt"
PROGRAM = "EXITPROBE"
SETUP = "XPSETUP"
LIBRARY = ["CA_EXITCYCLE", "CA_STOPMOVE"]
STAMP = datetime(2026, 1, 1)
START, CORNER = (1100.0, -200.0, 800.0), (1400.0, -200.0, 800.0)
EXPECTED = {"nCycles": "3", "nTraps": "1", "nAfter": "0", "nDone": "3"}
_Q = "[0,0.3826834,0.9238795,0]"
MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE ExitProbe",
    "    ! CrossArm - ExitCycle probe: see tools/make_exitcycle_probe.py.",
    f"    CONST robtarget xpStart:=[[1100,-200,800],{_Q},[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    f"    CONST robtarget xpCorner:=[[1400,-200,800],{_Q},[-1,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    "    VAR intnum iAbort;",
    "    VAR num nCycles;",
    "    VAR num nTraps;",
    "    VAR num nAfter;",
    "    VAR num nDone;",
    "",
    "    PROC ExitProbe()",
    "        Incr nCycles;",
    "        IDelete iAbort;",
    "        MoveJ xpStart,v1000,fine,tool0;",
    "        IF nCycles=1 THEN",
    "            CONNECT iAbort WITH tAbort;",
    "            ISignalDI diAbort,1,iAbort;",
    "            MoveL xpCorner,v60,fine,tool0;",
    "        ENDIF",
    "        IDelete iAbort;",
    "        MoveL xpCorner,v200,z100,tool0;",
    "        Leave;",
    "        nDone:=nCycles;",
    "    ENDPROC",
    "",
    "    PROC Leave()",
    "        IF nCycles=2 THEN",
    "            ExitCycle;",
    "            nAfter:=1;",
    "        ENDIF",
    "    ENDPROC",
    "",
    "    TRAP tAbort",
    "        Incr nTraps;",
    "        StopMove;",
    "        ClearPath;",
    "        ExitCycle;",
    "    ENDTRAP",
    "ENDMODULE",
    "",
])  # fmt: skip
SIGNALS = {"DIABORT": Signal("diAbort", "DI")}
ROUTINES = ["ExitProbe", "Leave", "tAbort"]


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="ExitProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=True), routines=ROUTINES,
                     sources={"ExitProbe": MODULE}, signals=SIGNALS)  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def setup_program() -> Program:
    """UTOOL[1] = tool0 (zero), as the moves of the probe use it."""
    lines = [Instruction("PR[20]=P[1]"), Instruction("UTOOL[1]=PR[20]")]
    positions = [Position(1, 0, 1, CartesianPosition(0.0, 0.0, 0.0, 0.0, 0.0, 0.0))]
    return Program(SETUP, list(lines), positions, Attributes(comment="ExitCycle setup", created=STAMP))


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "ExitProbe.mod").write_bytes(MODULE.encode("ascii"))
    for info in conversion().programs:
        (PROBE / f"{info.program.name}.LS").write_bytes(write_ls(info.program).encode("ascii"))
    (PROBE / f"{SETUP}.LS").write_bytes(write_ls(setup_program()).encode("ascii"))


def abort_input() -> int:
    """The DI the condition program watches, as CrossArm numbered it."""
    for path in PROBE.glob("*.LS"):
        if found := re.search(r"WHEN DI\[(\d+)\]=ON\+,CALL TABORT", path.read_text(encoding="ascii")):
            return int(found[1])
    raise RuntimeError("no condition program calling TABORT")


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------

SAMPLER = r"""
param([string]$Out, [string]$Name, [int]$In, [int]$Timeout)
$r = New-Object -ComObject FRRobot.FRCRobot
$r.ConnectEx("{host}", $false, 10, 1)
$g = $r.CurPosition.Group(1, 0)
$s = $r.IOTypes.Item(1).Signals.Item($In)
$s.Simulate = $true; $s.Value = $false
$r.KCL("RESET", $true)
$w = New-Object IO.StreamWriter($Out)
$sw = [Diagnostics.Stopwatch]::StartNew()
$r.Programs.Item($Name).Run()
$armed = $false; $phase = 0; $t = 0; $last = ""; $ended = 0
while ($sw.Elapsed.TotalSeconds -lt $Timeout) {{
  $g.Refresh(); $f = $g.Formats(2); $ms = $sw.Elapsed.TotalMilliseconds
  if (-not $armed -and [math]::Abs($f.X - 1100) -lt 0.5 -and [math]::Abs($f.Y + 200) -lt 0.5) {{ $armed = $true }}
  if ($armed -and $phase -eq 0 -and $f.X -ge 1250) {{ $s.Value = $true; $phase = 1; $t = $ms }}
  elseif ($phase -eq 1 -and $ms -ge $t + 300) {{ $s.Value = $false; $phase = 2 }}
  $task = @($r.Tasks | Where-Object {{ $_.Name -eq $Name }})[0]
  $status = if ($task -eq $null) {{ -1 }} else {{ $task.Status }}
  $line = "{{0:F3}} {{1:F3}} {{2:F3}} {{3}} {{4}}" -f $f.X, $f.Y, $f.Z, $phase, $status
  if ($line -ne $last) {{ $w.WriteLine(("{{0:F0}} " -f $ms) + $line); $last = $line }}
  if ($status -eq 2) {{ if ($ended -eq 0) {{ $ended = $ms }} elseif ($ms -gt $ended + 3000) {{ break }} }} else {{ $ended = 0 }}
}}
$s.Value = $false; $s.Simulate = $false
$w.Close()
"""


def _sampled(work: Path, number: int, timeout: int = 60) -> list[str]:
    import roboguide

    script = work / "sampler.ps1"
    script.write_text(SAMPLER.format(host=roboguide.HOST), encoding="ascii")
    out = work / "samples.txt"
    done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Out",
                           str(out), "-Name", PROGRAM, "-In", str(number), "-Timeout", str(timeout)],
                          capture_output=True, text=True, timeout=timeout + 60, check=False)  # fmt: skip
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
    number = abort_input()
    # the TRAP before the condition program calling it, the main program last
    programs = sorted((p.stem for p in PROBE.glob("*.LS")), key=lambda s: (s in (PROGRAM, SETUP), s != "TABORT", s))
    found: dict[str, str] = {"input": str(number)}
    with tempfile.TemporaryDirectory(prefix="crossarm_exitcycle_") as temp:
        work = Path(temp)
        out = export(LIBRARY, work, KarelRequest(make_maketp_probe.robot()), log=print)
        if len(out.compiled) != len(LIBRARY):
            raise RuntimeError(f"library not compiled: {out.problem or out.refused}")
        for name in programs:
            roboguide.release(name)
        roboguide.select()
        try:
            for name in LIBRARY:
                found[f"{name.lower()}_load"] = _ftp("STOR", next(work.rglob(f"{name.lower()}.pc"))) or "loaded"
            for name in programs:
                found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
            if any(value != "loaded" for key, value in found.items() if key.endswith("_load")):
                return found
            found["setup_run"] = roboguide.run(SETUP, 60)
            roboguide.zero(list(numbers.values()))
            before = roboguide._alarms() or set()
            samples = _sampled(work, number)
            after = roboguide._alarms() or set()
            found["alarms"] = " | ".join(sorted(re.sub(r"\s+", " ", a).split('"')[1].strip() for a in after - before
                                                if "INTP-" in a or "MOTN-" in a)) or "none"  # fmt: skip
            values = roboguide.numreg()
            for name, register in numbers.items():
                found[name] = f"{values.get(register, float('nan')):g}"
            found.update({f"s{i:04d}": s for i, s in enumerate(samples)})
        finally:
            for name in programs:
                roboguide.release(name)
            roboguide.select()
            for name in programs:
                _ftp(f"DELE {name.lower()}.tp")
            for name in LIBRARY:
                _ftp(f"DELE {name.lower()}.pc")
                _ftp(f"DELE {name.lower()}.vr")
    return found


# -- what the samples show ------------------------------------------------------------------------------------------


def _samples(found: dict[str, str]) -> list[tuple[float, float, float, float, int, int]]:
    out = []
    for key in sorted(k for k in found if re.fullmatch(r"s\d{4}", k)):
        t, x, y, z, phase, status = found[key].split()
        out.append((float(t) / 1000, float(x), float(y), float(z), int(phase), int(status)))
    return out


def analysis(found: dict[str, str]) -> dict[str, float]:
    """Where the robot stood when the TRAP stopped it (the first stop off the points after the input), how many
    times it came back to the start after that, and how close to the corner it came before the in-line ExitCycle."""
    samples = _samples(found)
    on = next((i for i, s in enumerate(samples) if s[4] >= 1), None)
    if on is None:
        return {}
    still = next((i for i in range(on + 1, len(samples)) if math.dist(samples[i][1:4], samples[i - 1][1:4]) < 0.05
                  and samples[i][1] < CORNER[0] - 1), None)  # fmt: skip
    out: dict[str, float] = {}
    if still is not None:
        out["stop_x"] = samples[still][1]
        out["off_line_mm"] = max(abs(s[2] - START[1]) + abs(s[3] - START[2]) for s in samples[on:still + 1])
    backs, away = 0, False
    for s in samples[on:]:
        if math.dist(s[1:4], START) > 1:
            away = True
        elif away:
            backs, away = backs + 1, False
    out["back_to_start"] = backs
    out["closest_corner_mm"] = min(math.dist(s[1:4], CORNER) for s in samples[on:])
    return out


def verdict(found: dict[str, str]) -> str:
    wrong = [f"{k}: {v}" for k, v in found.items() if k.endswith(("_load", "_run")) and v not in ("loaded", "done")]
    if found.get("alarms", "none") != "none":
        wrong.append(f"alarms: {found.get('alarms')}")
    counts = {name: found.get(name) for name in EXPECTED}
    if counts != EXPECTED:
        wrong.append(f"{counts}, RAPID {EXPECTED}")
    a = analysis(found)
    if not a:
        return "; ".join([*wrong, "the input was never switched"])
    if not 1250 <= a.get("stop_x", 0) < 1300 or a.get("off_line_mm", 99) > 0.5:
        wrong.append(f"TRAP stop at x {a.get('stop_x')}, {a.get('off_line_mm')} mm off the line, RAPID on it past 1250")
    if a["back_to_start"] != 2:
        wrong.append(f"back to the start {a['back_to_start']:g} times after the input, 2 cycles run again")
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    a = analysis(found)
    return (f"TRAP: stopped at x {a['stop_x']:.1f}, cycle run again; in line after the zone move: run again; three"
            f" cycles, counts as RAPID ({', '.join(f'{k} {v}' for k, v in EXPECTED.items())})")


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
    print(f"FAIL {problem}" if problem else f"exitcycle probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
