# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The path probe: does the converted FANUC program stay as close to the taught path as the ABB one?

A CNT that rounds more than the RAPID zone did takes the tool off the taught path where the programmer
did not expect it: into a fixture on the way down to a part, or across an edge. The motion probe
measured one right-angle corner with long legs; this runs the moves where that matters in real
programs, with the zones they use:

  approach   travel, then down onto a part: the last 100, 50 or 20 mm should be straight down
  japproach  the same, the travel a joint move
  retract    straight up off the part, then away: the first mm should be straight up
  reversal   down and back up: how far short of the bottom the tool turns
  turn45/135 obtuse and acute corners
  zigzag     50 mm legs, every corner zoned

The ABB robot runs PROC Path in RobotStudio; CrossArm converts it with the profile of the FANUC robot
loaded in ROBOGUIDE, which runs that. Both TCPs are read while they move (tools/probe_motion.py), and
for each run: how close the tool comes to each zoned point (cut), how much of the last and first
move is on the straight line (straight in, straight out), and how far from the taught lines it goes
(deviation, linear runs). The FANUC is flagged where it strays further than the ABB.

Usage:  python tools/make_path_probe.py prep            (RobotStudio: the confdata of each point)
        python tools/make_path_probe.py write
        python tools/make_path_probe.py run [abb|fanuc]
        python tools/make_path_probe.py measure         (again, from the TCP samples kept)
        python tools/make_path_probe.py check [robot folder]
"""

import json
import math
import sys
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import make_motion_probe as motion

OUT = ROOT / "tests" / "fixtures" / "probes" / "path"
RESULTS = OUT / "results"
PREP = RESULTS / "pathprep_robotstudio.txt"
SCRATCH = ROOT / "local" / "path"  # raw TCP samples, kept out of the repository
TOL = 0.3  # mm: on a line
AT = 2.0  # mm: at a point where a run starts or ends. A FINE stop can settle 0.5 mm off (both robots)

_R = math.sqrt(0.5) * 200
POINTS = {
    "pTravel": (1100.0, -250.0, 950.0),
    "pPick": (1300.0, 100.0, 700.0),
    "pAbove100": (1300.0, 100.0, 800.0),
    "pAbove50": (1300.0, 100.0, 750.0),
    "pAbove20": (1300.0, 100.0, 720.0),
    "pDownA": (1200.0, -150.0, 1000.0),
    "pDownB": (1200.0, -150.0, 800.0),
    "pDownC": (1200.0, -140.0, 1000.0),  # 10 mm aside, so that the run ends somewhere it did not start
    "pTurnIn": (1250.0, -350.0, 900.0),
    "pTurn": (1250.0, -50.0, 900.0),
    "pTurn45": (round(1250.0 + _R, 3), round(-50.0 + _R, 3), 900.0),  # 45 deg off the way in
    "pTurn135": (round(1250.0 + _R, 3), round(-50.0 - _R, 3), 900.0),  # 135 deg off: nearly back
    "pZig0": (1150.0, -100.0, 800.0),
    "pZig1": (1200.0, -100.0, 800.0),
    "pZig2": (1200.0, -50.0, 800.0),
    "pZig3": (1250.0, -50.0, 800.0),
    "pZig4": (1250.0, 0.0, 800.0),
    "pZig5": (1300.0, 0.0, 800.0),
}
Run = motion.Run
RUNS: list[Run] = [
    *[(f"approach {h} {z}", "pTravel", [("L", f"pAbove{h}", "v1000", z), ("L", "pPick", "v300", "fine")])
      for h in (100, 50, 20) for z in ("z10", "z50", "z100")],
    *[(f"japproach {z}", "pTravel", [("J", "pAbove100", "v1000", z), ("L", "pPick", "v300", "fine")])
      for z in ("z10", "z50", "z100")],
    *[(f"retract {h} {z}", "pPick", [("L", f"pAbove{h}", "v300", z), ("L", "pTravel", "v1000", "fine")])
      for h in (100, 20) for z in ("z10", "z50", "z100")],
    *[(f"jretract {z}", "pPick", [("L", "pAbove100", "v300", z), ("J", "pTravel", "v1000", "fine")])
      for z in ("z10", "z50", "z100")],
    *[(f"reversal {z}", "pDownA", [("L", "pDownB", "v600", z), ("L", "pDownC", "v600", "fine")])
      for z in ("z5", "z20", "z50")],
    *[(f"turn{a} {z}", "pTurnIn", [("L", "pTurn", "v600", z), ("L", f"pTurn{a}", "v600", "fine")])
      for a in (45, 135) for z in ("z10", "z50")],
    *[(f"zigzag v{v} {z}", "pZig0", [*[("L", f"pZig{i}", f"v{v}", z) for i in range(1, 5)], ("L", "pZig5", f"v{v}", "fine")])
      for v in (300, 600) for z in ("z10", "z20")],
]  # fmt: skip


def confdata() -> dict[str, str]:
    """The confdata the ABB robot reached each point with, cf1 from the point's azimuth: at y = 0 the
    reported J1 flickers either side of 0 (J1 is 0 there, quadrant 0)."""
    out = {}
    for name, conf in motion.confdata(PREP).items():
        x, y, _ = POINTS[name]
        _, cf4, cf6, cfx = conf.strip("[]").split(",")
        out[name] = f"[{math.floor(math.degrees(math.atan2(y, x)) / 90)},{cf4},{cf6},{cfx}]"
    return out


def abb_module() -> str:
    conf = confdata()
    lines = [
        "MODULE PathProbe",
        "    ! CrossArm - path probe. PROC Path runs every move CrossArm converts; the TCP is read while it moves.",
    ]
    for name, pos in POINTS.items():
        lines.append(f"    CONST robtarget {name}:=[[{','.join(motion._num(c) for c in pos)}],{motion._orient()},"
                     f"{conf[name]},[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];")  # fmt: skip
    lines += ["", "    PROC Path()"]
    for _, start, moves in RUNS:
        lines.append(f"        MoveJ {start},v1000,fine,tool0;")
        lines += [f"        Move{kind} {point},{speed},{zone},tool0;" for kind, point, speed, zone in moves]
    lines += ["    ENDPROC", "ENDMODULE", ""]
    return "\r\n".join(lines)


def fanuc_program(module_text: str, profile) -> tuple[str, dict[str, list[str]]]:
    """CrossArm's conversion of PROC Path with that motion profile; run name -> the terminations written."""
    from datetime import datetime

    from crossarm.convert import ConversionConfig, convert
    from crossarm.fanuc.ls_writer import write_ls
    from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, Motion, Position, Program
    from crossarm.rapid import parse_text

    parsed = parse_text(module_text, path="PathProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    config.motion_profile, config.joint_speed_ref_mm_s = profile, profile.joint_speed_ref_mm_s
    result = convert([parsed.module], config, routines=["Path"])
    assert not [n for n in result.notes if n.kind == "TODO"], result.notes
    (info,) = result.programs
    (tool,) = result.utools
    positions = list(info.program.positions)
    data = max(p.number for p in positions) + 1  # tool0, loaded into its UTOOL through PR[20]
    positions.append(Position(data, 0, 1, CartesianPosition(0, 0, 0, 0, 0, 0)))
    lines = [Instruction("!CrossArm path probe"), Instruction(f"PR[20]=P[{data}]"),
             Instruction(f"UTOOL[{tool.number}]=PR[20]"), *info.program.lines]  # fmt: skip
    motions = iter(line for line in info.program.lines if isinstance(line, Motion))
    terms = {}
    for name, _, moves in RUNS:
        next(motions)  # to the start
        terms[name] = [f"{m.speed} {m.termination}" for m in (next(motions) for _ in moves)]
    attributes = Attributes(comment="path probe", created=datetime(2026, 1, 1))
    return write_ls(Program("PATHPROBE", lines, positions, attributes)), terms


# -- what the TCP did --------------------------------------------------------------------------

Sample = tuple[float, float, float, float]


def _stop(samples: list[Sample], k: int, point) -> int:
    """From the first sample near a point, the one where the robot stopped there: the closest of those
    that follow on while it stays near."""
    end = k
    while end + 1 < len(samples) and math.dist(samples[end + 1][1:], point) <= AT:
        end += 1
    return min(range(k, end + 1), key=lambda j: math.dist(samples[j][1:], point))


def windows(samples: list[Sample], runs: list[Run] = RUNS) -> list[list[Sample]]:
    """Each run's samples, in order: from its stop on its start point to its stop on its end point."""
    out, i = [], 0
    for name, start, moves in runs:
        a, b = POINTS[start], POINTS[moves[-1][1]]
        first = next((k for k in range(i, len(samples)) if math.dist(samples[k][1:], a) <= AT), None)
        if first is not None:
            first = _stop(samples, first, a)
        last = None if first is None else next(
            (k for k in range(first + 1, len(samples)) if math.dist(samples[k][1:], b) <= AT), None)  # fmt: skip
        if first is None or last is None:
            raise RuntimeError(f"run '{name}' not found in the TCP samples")
        last = _stop(samples, last, b)
        out.append(samples[first : last + 1])
        i = last
    return out


def _to_segment(p, a, b) -> float:
    ab = [y - x for x, y in zip(a, b, strict=True)]
    t = sum((q - x) * d for q, x, d in zip(p, a, ab, strict=True)) / sum(d * d for d in ab)
    t = min(1.0, max(0.0, t))
    return math.dist(p, [x + t * d for x, d in zip(a, ab, strict=True)])


def measure(run: Run, window: list[Sample]) -> dict:
    """cut (mm from each zoned point), straight_in / straight_out (mm of the last / first move on its
    line), deviation (mm from the taught lines, linear runs)."""
    _, start, moves = run
    path = [POINTS[start], *(POINTS[target] for _, target, _, _ in moves)]
    xyz = [s[1:] for s in window]
    out: dict = {"cut": {target: round(min(math.dist(p, POINTS[target]) for p in xyz), 2)
                         for _, target, _, zone in moves[:-1] if zone != "fine"}}  # fmt: skip
    # The line is followed from AT mm off the stops: a FINE stop can settle a few tenths of a mm aside.
    if moves[-1][0] == "L":
        a, b = path[-2], path[-1]
        k = len(xyz) - 1
        while k > 0 and math.dist(xyz[k], b) <= AT:
            k -= 1
        while k > 0 and _to_segment(xyz[k - 1], a, b) <= TOL:
            k -= 1
        out["straight_in"] = round(math.dist(xyz[k], b), 1)
    if moves[0][0] == "L":
        a, b = path[0], path[1]
        k = 0
        while k < len(xyz) - 1 and math.dist(xyz[k], a) <= AT:
            k += 1
        while k < len(xyz) - 1 and _to_segment(xyz[k + 1], a, b) <= TOL:
            k += 1
        out["straight_out"] = round(math.dist(xyz[k], a), 1)
    if all(kind == "L" for kind, *_ in moves):
        out["deviation"] = round(max(min(_to_segment(p, a, b) for a, b in pairwise(path)) for p in xyz), 2)
    return out


def worse(abb: dict, fanuc: dict) -> list[str]:
    """Where the FANUC strays further from the taught path than the ABB: beyond 1 mm and 20 %."""
    def margin(v: float) -> float:
        return max(1.0, 0.2 * v)

    out = [f"cut at {t} {fanuc['cut'][t]} mm for {c}" for t, c in abb["cut"].items() if fanuc["cut"][t] > c + margin(c)]
    for key, what in (("straight_in", "straight in"), ("straight_out", "straight out")):
        if key in abb and fanuc[key] < abb[key] - margin(abb[key]):
            out.append(f"{what} {fanuc[key]} mm for {abb[key]}")
    if "deviation" in abb and fanuc["deviation"] > abb["deviation"] + margin(abb["deviation"]):
        out.append(f"deviation {fanuc['deviation']} mm for {abb['deviation']}")
    return out


# -- running it --------------------------------------------------------------------------------


def read_samples(path: Path) -> list[Sample]:
    rows = (line.split(",") for line in path.read_text(encoding="ascii", errors="replace").splitlines())
    return [tuple(float(v) for v in row) for row in rows if len(row) == 4]  # type: ignore[misc]


def run_abb() -> dict:
    import probe_motion
    import robotstudio

    sampler = probe_motion.Sampler(probe_motion._ABB_SAMPLER, SCRATCH / "abb_pathprobe.csv")
    try:
        status = robotstudio.run(OUT / "PathProbe.mod", "Path", 900)
    finally:
        samples = sampler.close()
    if status != "done":
        raise RuntimeError(f"RobotStudio: {status}")
    return {"system": robotstudio.system(), "runs": results(samples)}


def remeasure() -> None:
    """The measurements again from the TCP samples kept in local/path/, the robots left alone."""
    path = RESULTS / "abb.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["runs"] = results(read_samples(SCRATCH / "abb_pathprobe.csv"))
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    for path in RESULTS.glob("*/fanuc.json"):
        samples = SCRATCH / f"fanuc_pathprobe_{path.parent.name}.csv"
        if samples.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            runs = results(read_samples(samples))
            for name, run in runs.items():
                run["written"] = data["runs"][name]["written"]
            data["runs"] = runs
            path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def run_fanuc() -> tuple[str, dict]:
    import probe_motion
    import roboguide

    from crossarm.convert.motion import profile_for

    robot = roboguide.model()
    profile, _ = profile_for(robot)
    folder = RESULTS / robot.replace("/", "_")
    folder.mkdir(parents=True, exist_ok=True)
    text, terms = fanuc_program((OUT / "PathProbe.mod").read_text(encoding="ascii"), profile)
    (folder / "PATHPROBE.LS").write_bytes(text.encode("ascii"))
    try:
        roboguide.delete("PATHPROBE")
    except Exception:  # noqa: BLE001, S110 - not there
        pass
    reason = roboguide.load(folder / "PATHPROBE.LS")
    if reason:
        raise RuntimeError(f"ROBOGUIDE refused PATHPROBE.LS: {reason}")
    try:
        sampler = probe_motion.Sampler(probe_motion._FANUC_SAMPLER, SCRATCH / f"fanuc_pathprobe_{folder.name}.csv")
        try:
            status = roboguide.run("PATHPROBE", 900)
        finally:
            samples = sampler.close()
        if status != "done":
            raise RuntimeError(f"ROBOGUIDE: {status}")
    finally:
        roboguide.release("PATHPROBE")
        roboguide.delete("PATHPROBE")
    runs = results(samples)
    for name, written in terms.items():
        runs[name]["written"] = written
    return folder.name, {"robot": robot, "profile": profile.name, "runs": runs}


def results(samples: list[Sample]) -> dict:
    return {run[0]: measure(run, window) for run, window in zip(RUNS, windows(samples), strict=True)}


def check(folder: Path) -> list[tuple[str, list[str]]]:
    abb = json.loads((RESULTS / "abb.json").read_text(encoding="utf-8"))["runs"]
    fanuc = json.loads((folder / "fanuc.json").read_text(encoding="utf-8"))["runs"]
    return [(name, worse(abb[name], fanuc[name])) for name, _, _ in RUNS]


def table(folder: Path) -> str:
    abb = json.loads((RESULTS / "abb.json").read_text(encoding="utf-8"))["runs"]
    fanuc = json.loads((folder / "fanuc.json").read_text(encoding="utf-8"))["runs"]
    rows = []
    for (name, _, _), (_, bad) in zip(RUNS, check(folder), strict=True):
        a, f = abb[name], fanuc[name]
        cuts = "  ".join(f"{t} {a['cut'][t]:.1f}/{f['cut'][t]:.1f}" for t in a["cut"])
        extra = "  ".join(f"{k} {a[k]:.1f}/{f[k]:.1f}" for k in ("straight_in", "straight_out", "deviation") if k in a)
        rows.append(f"{'!!' if bad else 'ok'} {name:20s} {' '.join(f['written']):32s} {cuts}  {extra}"
                    + (f"   <- {'; '.join(bad)}" if bad else ""))  # fmt: skip
    return "\n".join(rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args == ["prep"]:
        import robotstudio

        (OUT / "PathPrep.mod").write_bytes(motion.prep_module(POINTS, "PathPrep", "path").encode("ascii"))
        home = robotstudio.home()
        status = robotstudio.run(OUT / "PathPrep.mod", "Prep", 300, home)
        print(status)
        if status == "done":
            PREP.parent.mkdir(parents=True, exist_ok=True)
            PREP.write_bytes((home / "pathprep.txt").read_bytes())
        return 0 if status == "done" else 1
    if args == ["write"]:
        (OUT / "PathProbe.mod").write_bytes(abb_module().encode("ascii"))
        print(f"{len(RUNS)} runs written to {OUT / 'PathProbe.mod'}")
        return 0
    if args[:1] == ["run"]:
        for side in args[1:] or ["abb", "fanuc"]:
            if side == "abb":
                data = run_abb()
                (RESULTS / "abb.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
            else:
                folder, data = run_fanuc()
                (RESULTS / folder / "fanuc.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
            print(f"{side}: {len(data['runs'])} runs measured")
        return 0
    if args == ["measure"]:
        remeasure()
        return 0
    if args[:1] == ["check"]:
        folders = [Path(p) for p in args[1:]] or sorted(p for p in RESULTS.iterdir() if (p / "fanuc.json").exists())
        for folder in folders:
            print(f"-- {folder.name}: ABB/FANUC, mm")
            print(table(folder))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
