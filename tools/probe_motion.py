# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Run the motion probe on both simulators and fit CrossArm's speed and zone settings to it.

tools/make_motion_probe.py writes the runs; this runs them. On each simulator a second process reads
the TCP (tool0, the flange) while the runs move it: the ABB PC SDK on RobotStudio, the FANUC COM
interface on ROBOGUIDE. Times come from the controllers' own clocks (ClkRead, TIMER).

  run  [abb|fanuc]   run the probe, write tests/fixtures/probes/motion/results/
  fit                read the results: which J % takes as long as each RAPID speed, which CNT cuts a
                     corner as much as each RAPID zone, and the settings that come closest

A corner run goes from pCornerA to pCornerC past pCornerB: its window in the TCP samples is from
the last sample at pCornerA to the first at pCornerC, and its corner cut is how close the samples
come to pCornerB in that window.
"""

import json
import math
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import make_motion_probe as probe
import roboguide
import robotstudio

RESULTS = probe.OUT / "results"


def fanuc_results() -> Path:
    """Where the FANUC side goes: results/ for the M-20iD/25 CrossArm ships with, results/<robot>/ for
    another one (CROSSARM_MOTION_ROBOT names it, e.g. R-2000iC_190S). The ABB side stays in results/."""
    robot = os.environ.get("CROSSARM_MOTION_ROBOT")
    return RESULTS / robot if robot else RESULTS
SCRATCH = ROOT / "local" / "motion"  # raw TCP samples: large, kept out of the repository

_ABB_SAMPLER = r"""
param([string]$Out, [string]$Stop)
$bin = @("C:\Program Files (x86)\ABB\RobotStudio *\Bin-net48", "C:\Program Files (x86)\ABB\RobotStudio *\Bin") |
  ForEach-Object { Resolve-Path $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
Add-Type -Path (Join-Path $bin "ABB.Robotics.Controllers.PC.dll")
$s = New-Object ABB.Robotics.Controllers.Discovery.NetworkScanner
$s.Scan()
$c = [ABB.Robotics.Controllers.ControllerFactory]::CreateFrom(@($s.Controllers | Where-Object { $_.IsVirtual })[0])
$c.Logon([ABB.Robotics.Controllers.UserInfo]::DefaultUser)
$mu = $c.MotionSystem.ActiveMechanicalUnit
$world = [ABB.Robotics.Controllers.MotionDomain.CoordinateSystemType]::World
$w = New-Object IO.StreamWriter($Out)
$sw = [Diagnostics.Stopwatch]::StartNew()
$last = ""; $n = 0
while ($true) {
  $p = $mu.GetPosition($world)
  $line = "{0:F3},{1:F3},{2:F3}" -f $p.Trans.X, $p.Trans.Y, $p.Trans.Z
  if ($line -ne $last) { $w.WriteLine(("{0:F1}," -f $sw.Elapsed.TotalMilliseconds) + $line); $last = $line }
  $n++
  if ($n % 500 -eq 0 -and (Test-Path $Stop)) { break }
}
$w.Close(); $c.Logoff(); $c.Dispose()
"""
_FANUC_SAMPLER = r"""
param([string]$Out, [string]$Stop)
$r = New-Object -ComObject FRRobot.FRCRobot
$r.ConnectEx("127.0.0.1", $false, 10, 1)
$g = $r.CurPosition.Group(1, 0)
$w = New-Object IO.StreamWriter($Out)
$sw = [Diagnostics.Stopwatch]::StartNew()
$last = ""; $n = 0
while ($true) {
  $g.Refresh()
  $f = $g.Formats(2)
  $line = "{0:F3},{1:F3},{2:F3}" -f $f.X, $f.Y, $f.Z
  if ($line -ne $last) { $w.WriteLine(("{0:F1}," -f $sw.Elapsed.TotalMilliseconds) + $line); $last = $line }
  $n++
  if ($n % 500 -eq 0 -and (Test-Path $Stop)) { break }
}
$w.Close()
"""


class Sampler:
    """The TCP read in a second process while a probe runs, one line per change: 'ms,x,y,z'."""

    def __init__(self, script: str, out: Path) -> None:
        self.out, self.stop = out, out.with_suffix(".stop")
        out.parent.mkdir(parents=True, exist_ok=True)
        self.stop.unlink(missing_ok=True)
        path = out.with_suffix(".ps1")
        path.write_text(script, encoding="utf-8")
        command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path), "-Out", str(out),
                   "-Stop", str(self.stop)]  # fmt: skip
        self.process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        end = time.monotonic() + 60
        while not (out.exists() and out.stat().st_size) and time.monotonic() < end:  # connected and reading
            time.sleep(0.2)

    def close(self) -> list[tuple[float, float, float, float]]:
        self.stop.write_text("stop", encoding="ascii")
        self.process.wait(timeout=60)
        self.stop.unlink(missing_ok=True)
        samples = []
        for line in self.out.read_text(encoding="ascii", errors="replace").splitlines():
            parts = line.split(",")
            if len(parts) == 4:
                samples.append(tuple(float(v) for v in parts))
        return samples  # type: ignore[return-value]


def corner_cuts(samples: list[tuple[float, float, float, float]], tolerance: float = 0.5) -> list[float]:
    """How close the TCP came to pCornerB in each run from pCornerA to pCornerC, in order."""
    a, b, c = (probe.POINTS[name] for name in ("pCornerA", "pCornerB", "pCornerC"))
    cuts, start = [], None
    for i, (_, *xyz) in enumerate(samples):
        if math.dist(xyz, a) < tolerance:
            start = i
        elif start is not None and math.dist(xyz, c) < tolerance:
            window = samples[start : i + 1]
            cuts.append(min(math.dist(s[1:], b) for s in window))
            start = None
    return cuts


def run_abb(module: str = "MotionProbe", routine: str = "Probe", runs: list | None = None) -> dict:
    output = f"{module.lower()}.txt"
    folder = robotstudio.home()
    (folder / output).unlink(missing_ok=True)
    sampler = Sampler(_ABB_SAMPLER, SCRATCH / f"abb_{module.lower()}.csv")
    try:
        status = robotstudio.run(probe.OUT / f"{module}.mod", routine, 900, folder)
    finally:
        samples = sampler.close()
    if status != "done":
        raise RuntimeError(f"RobotStudio: {status}")
    times = {}
    for line in (folder / output).read_text(encoding="utf-8", errors="replace").splitlines():
        name, _, value = line.rpartition(" ")
        times[name] = float(value)
    return _results(probe.abb_runs() if runs is None else runs, times, samples)


def _results(runs: list, times: dict, samples: list) -> dict:
    """{'runs': {name: {'time': s, 'cut': mm}}}: the cut for the runs past the corner, in their order."""
    corners, cuts = probe.corner_runs(runs), corner_cuts(samples)
    if len(cuts) != len(corners):
        raise RuntimeError(f"{len(cuts)} corner passes in the TCP samples for {len(corners)} corner runs")
    out = {name: {"time": times.get(name)} for name, _, _ in runs}
    for name, cut in zip(corners, cuts, strict=True):
        out[name]["cut"] = round(cut, 3)
    return {"runs": out, "samples": len(samples)}


def run_fanuc(program: str = "MOTIONPROBE", runs: list | None = None, path: Path | None = None) -> dict:
    path = path or probe.OUT / f"{program}.LS"
    runs = probe.fanuc_runs() if runs is None else runs
    registers = [probe.FIRST_REGISTER + i for i in range(len(runs))]
    try:
        roboguide.delete(program)
    except Exception:  # noqa: BLE001, S110 - not there
        pass
    reason = roboguide.load(path)
    if reason:
        raise RuntimeError(f"ROBOGUIDE refused {program}.LS: {reason}")
    try:
        roboguide.zero(registers)
        sampler = Sampler(_FANUC_SAMPLER, SCRATCH / f"fanuc_{program.lower()}.csv")
        try:
            status = roboguide.run(program, 900)
        finally:
            samples = sampler.close()
        if status != "done":
            raise RuntimeError(f"ROBOGUIDE: {status}")
        values = roboguide.numreg()
    finally:
        roboguide.release(program)  # left paused by a failed run: aborted, then deleted
        roboguide.delete(program)
    times = {name: values.get(register) for (name, _, _), register in zip(runs, registers, strict=True)}
    return {"robot": roboguide.model(), **_results(runs, times, samples)}


# -- fit ---------------------------------------------------------------------------------------

MOTION_PY = ROOT / "src" / "CrossArm" / "convert" / "motion.py"
PROFILE_CONSTANTS = {"M-20iD/25": "M20ID_25", "R-2000iC/190S": "R2000IC_190S", "R-1000iA/80F": "R1000IA_80F"}  # robot -> constant in motion.py


def joint_reference(abb: dict, fanuc: dict) -> dict[str, float]:
    """Per joint move, the TCP speed a J 100 % move would reach: RAPID speed * 100 / the J % that takes
    as long. The FANUC time is fitted as t = a + b / % where the axes never reach their top speed
    (J 20 % and less); RAPID speeds the ABB axes cap (within 5 % of the FANUC's fastest) are left out."""
    out = {}
    for move in probe.JOINT_MOVES:
        measured = [(pct, fanuc[f"{move} {pct}%"]["time"]) for pct in probe.FANUC_JOINT_PERCENTS]
        fastest = min(t for _, t in measured)
        slow = [(1 / pct, t) for pct, t in measured if pct <= 20]
        mx, my = statistics.fmean(x for x, _ in slow), statistics.fmean(t for _, t in slow)
        b = sum((x - mx) * (t - my) for x, t in slow) / sum((x - mx) ** 2 for x, _ in slow)
        a = my - b * mx
        refs = []
        for speed in probe.ABB_JOINT_SPEEDS:
            t = abb[f"{move} {speed}"]["time"]
            if speed == "vmax" or t <= 1.05 * fastest:
                continue
            percent = b / (t - a)
            if percent <= 30:
                refs.append(float(speed[1:]) * 100 / percent)
        out[move] = statistics.median(refs)
    return out


def fit(abb: dict, fanuc: dict, name: str = "M-20iD/25") -> dict:
    """The motion profile (crossarm.convert.motion) these runs give, as JSON data."""
    from crossarm.convert.values import PREDEFINED_ZONES

    refs = joint_reference(abb, fanuc)
    reference = round(statistics.geometric_mean(refs.values()), -2)

    def rapid_side(prefix: str, speeds: list[str]) -> dict:
        return {speed[1:]: [[PREDEFINED_ZONES[z.upper()], round(abb[f"{prefix} {speed} {z}"]["cut"], 2)]
                            for z in probe.ABB_ZONES if z != "fine"] for speed in speeds}  # fmt: skip

    def fanuc_side(prefix: str, speeds: list[str], unit: str) -> dict:
        return {speed: [[0 if cnt == "CNT0" else int(cnt[3:]), round(fanuc[f"{prefix} {speed}{unit} {cnt}"]["cut"], 2)]
                        for cnt in probe.FANUC_CNTS if cnt != "FINE"] for speed in speeds}  # fmt: skip

    return {
        "name": name,
        "joint_speed_ref_mm_s": reference,
        "abb": {"L": rapid_side("corner", [f"v{v}" for v in probe.CORNER_SPEEDS]),
                "J": rapid_side("jcorner", list(probe.JOINT_CORNERS))},
        "fanuc": {"L": fanuc_side("corner", [str(v) for v in probe.CORNER_SPEEDS], "mm/sec"),
                  "J": {pct[:-1]: points for pct, points in
                        fanuc_side("jcorner", list(probe.JOINT_CORNERS.values()), "").items()}},
    }  # fmt: skip


def write_profile(profile: dict) -> None:
    """Replace that robot's profile constant in crossarm.convert.motion with the fitted profile."""
    mark = f"{PROFILE_CONSTANTS[profile['name']]} = MotionProfile.from_dict("
    text = MOTION_PY.read_text(encoding="utf-8")
    start = text.index(mark)
    end = text.index("})  # fmt: skip", start) + len("})  # fmt: skip")  # the end of this constant, not of a later one
    rows = []
    for key in ("name", "joint_speed_ref_mm_s"):
        rows.append(f"    {json.dumps(key)}: {json.dumps(profile[key])},")
    for side in ("abb", "fanuc"):
        rows.append(f'    "{side}": {{')
        for kind, by_speed in profile[side].items():
            rows.append(f'        "{kind}": {{')
            for speed, points in by_speed.items():
                rows.append(f'            "{speed}": {json.dumps(points)},')
            rows.append("        },")
        rows.append("    },")
    literal = mark + "{\n" + "\n".join(rows) + "\n})  # fmt: skip"
    MOTION_PY.write_text(text[:start] + literal + text[end:], encoding="utf-8")


def compare_check(abb: dict, fanuc: dict) -> list[str]:
    """The check, run by run: time on each robot, and corner cut on each for the corners."""
    rows = []
    for name, _, _ in probe.CHECK_RUNS:
        a, f = abb[name], fanuc[name]
        text = f"{name:26s} time ABB {a['time']:6.3f} s  FANUC {f['time']:6.3f} s  ({(f['time'] / a['time'] - 1) * 100:+4.0f} %)"
        if "cut" in a:
            text += f"   cut ABB {a['cut']:5.2f} mm  FANUC {f['cut']:5.2f} mm"
        rows.append(text)
    return rows


def main() -> int:
    target = fanuc_results()
    if sys.argv[1:2] == ["check"]:
        # Another robot: its own profile converts the check, and only the FANUC side runs again.
        other = target != RESULTS
        if other:
            from crossarm.convert.motion import MotionProfile

            profile = MotionProfile.from_dict(json.loads((target / "profile.json").read_text(encoding="utf-8")))
            module = (probe.OUT / "MotionCheck.mod").read_text(encoding="ascii")
            (target / "MOTIONCHECK.LS").write_bytes(probe.check_program(module, profile).encode("ascii"))
            abb = json.loads((RESULTS / "check_abb.json").read_text(encoding="utf-8"))
            fanuc = run_fanuc("MOTIONCHECK", probe.CHECK_RUNS, target / "MOTIONCHECK.LS")
        else:
            abb = run_abb("MotionCheck", "Check", probe.CHECK_RUNS)
            fanuc = run_fanuc("MOTIONCHECK", probe.CHECK_RUNS)
            (RESULTS / "check_abb.json").write_text(json.dumps(abb, indent=1) + "\n", encoding="utf-8")
        (target / "check_fanuc.json").write_text(json.dumps(fanuc, indent=1) + "\n", encoding="utf-8")
        print("\n".join(compare_check(abb["runs"], fanuc["runs"])))
        return 0
    if sys.argv[1:2] == ["fit"]:
        abb = json.loads((RESULTS / "motion_abb.json").read_text(encoding="utf-8"))["runs"]
        measured = json.loads((target / "motion_fanuc.json").read_text(encoding="utf-8"))
        fanuc = measured["runs"]
        for move, ref in joint_reference(abb, fanuc).items():
            print(f"{move:6s} J 100 % ~ {ref:5.0f} mm/s of TCP")
        profile = fit(abb, fanuc, measured.get("robot", "M-20iD/25"))
        print(f"joint_speed_ref_mm_s = {profile['joint_speed_ref_mm_s']:g} (geometric mean)")
        (target / "profile.json").write_text(json.dumps(profile, indent=1) + "\n", encoding="utf-8")
        if sys.argv[2:] == ["--write"]:
            write_profile(profile)
            print(f"written to {MOTION_PY.relative_to(ROOT)}")
        return 0
    if sys.argv[1:2] == ["run"]:
        target.mkdir(parents=True, exist_ok=True)
        sides = sys.argv[2:] or ["abb", "fanuc"]
        for side in sides:
            start = time.monotonic()
            data = run_abb() if side == "abb" else run_fanuc()
            folder = RESULTS if side == "abb" else target
            (folder / f"motion_{side}.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
            cuts = sum("cut" in run for run in data["runs"].values())
            print(f"{side}: {len(data['runs'])} runs timed, {cuts} corners, {data['samples']} TCP samples, "
                  f"{time.monotonic() - start:.0f} s")  # fmt: skip
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
