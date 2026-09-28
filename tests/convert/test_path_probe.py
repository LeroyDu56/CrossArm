# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Zones where they matter: does the converted program stay as close to the taught path as the ABB?

tools/make_path_probe.py ran approaches, retracts, reversals, acute and obtuse corners and zigzags on an
IRB 6700 (RobotStudio) and, converted by CrossArm, on an R-1000iA/80F and an R-2000iC/190S (ROBOGUIDE), the
TCP read on both.
tests/fixtures/probes/path/results/ holds what they measured; here:

  * the files are what the generator writes, the FANUC program what CrossArm writes;
  * the FANUC never strays more than 1.5 mm further from the taught path than the ABB, and on the way
    down onto a part it stays on the line at least as long; but for reversals (down and back up through
    a zone), where the R-2000iC turns up to 4 mm shorter of the bottom, still on the line;
  * into a faster move it rounded more than the ABB with the CNT of the zoned move's own speed, which is
    why CrossArm matches it at the next move's speed.
"""

import json
import math
import sys
from pathlib import Path

import pytest
from helpers import FIXTURES

from crossarm.convert.motion import R1000IA_80F, R2000IC_190S

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import make_motion_probe as motion
import make_path_probe as probe

OUT = FIXTURES / "probes" / "path"
R1000 = OUT / "results" / "R-1000iA_80F"
# robot -> the runs flagged: where it strays further than the ABB beyond 1 mm and 20 %
FLAGGED = {
    R1000IA_80F.name: {"reversal z5"},  # 3.9 mm short of the bottom, the ABB 2.6
    R2000IC_190S.name: {"reversal z5", "reversal z20"},  # 5.6 and 12.1 mm short, the ABB 2.6 and 9.5
}
ROBOTS = [R1000IA_80F, R2000IC_190S]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["runs"]


def folder(profile) -> Path:
    return OUT / "results" / profile.name.replace("/", "_")


def test_the_probe_files_are_what_the_generator_writes():
    assert (OUT / "PathPrep.mod").read_bytes() == motion.prep_module(probe.POINTS, "PathPrep", "path").encode("ascii")
    module = probe.abb_module()
    assert (OUT / "PathProbe.mod").read_bytes() == module.encode("ascii")
    for profile in ROBOTS:  # converted with the profile of that robot's series, as for its backup
        text, terms = probe.fanuc_program(module, profile)
        assert (folder(profile) / "PATHPROBE.LS").read_bytes() == text.encode("ascii")
        assert {name: run["written"] for name, run in load(folder(profile) / "fanuc.json").items()} == terms


@pytest.mark.parametrize("profile", ROBOTS, ids=lambda p: p.name)
def test_the_fanuc_strays_no_further_than_the_abb_beyond_a_millimetre_and_a_half(profile):
    abb, fanuc = load(OUT / "results" / "abb.json"), load(folder(profile) / "fanuc.json")
    assert set(abb) == set(fanuc) == {name for name, _, _ in probe.RUNS}
    for name in abb:
        a, f = abb[name], fanuc[name]
        reversal = name.startswith("reversal")
        for point, cut in a["cut"].items():
            assert f["cut"][point] <= cut + (4.0 if reversal else 1.5), (name, point)
        if "deviation" in a:
            assert f["deviation"] <= a["deviation"] + 1.5, name  # a reversal too: it stays on the line
    assert {name for name, bad in probe.check(folder(profile)) if bad} == FLAGGED[profile.name]


@pytest.mark.parametrize("profile", ROBOTS, ids=lambda p: p.name)
@pytest.mark.parametrize("name", [name for name, _, _ in probe.RUNS if "approach" in name])
def test_on_the_way_down_onto_the_part_the_fanuc_is_on_the_line_at_least_as_long(name, profile):
    a, f = load(OUT / "results" / "abb.json")[name], load(folder(profile) / "fanuc.json")[name]
    assert f["straight_in"] >= a["straight_in"]
    assert all(f["cut"][p] <= c for p, c in a["cut"].items())


def test_into_a_faster_move_the_zoned_moves_own_speed_rounded_more_than_the_abb():
    abb = load(OUT / "results" / "abb.json")["retract 100 z10"]
    own_speed = load(R1000 / "fanuc_own_speed.json")["retract 100 z10"]  # the first run: CNT69, for 300 mm/s
    now = load(R1000 / "fanuc.json")["retract 100 z10"]  # CNT22, for 1000 mm/s
    assert own_speed["written"] == ["300mm/sec CNT69", "1000mm/sec FINE"]
    assert own_speed["cut"]["pAbove100"] > abb["cut"]["pAbove100"] + 1.5 > now["cut"]["pAbove100"]
    assert now["written"] == ["300mm/sec CNT22", "1000mm/sec FINE"]


def test_the_runs_are_found_and_measured_in_the_tcp_samples():
    """A synthetic retract: settled 0.4 mm off the part, straight up 95 mm, then a short cut to the travel point."""
    pick, above, travel = (probe.POINTS[name] for name in ("pPick", "pAbove100", "pTravel"))
    run = next(r for r in probe.RUNS if r[0] == "retract 100 z10")
    top = (pick[0], pick[1], pick[2] + 95)
    samples = [(0.0, pick[0] + 0.4, pick[1], pick[2])]
    samples += [(float(i), pick[0], pick[1], pick[2] + i) for i in range(1, 96)]
    samples += [(100.0 + i, *(t + (e - t) * i / 100 for t, e in zip(top, travel, strict=True))) for i in range(1, 101)]
    (window,) = probe.windows([(-1.0, 0.0, 0.0, 0.0), *samples, (999.0, 0.0, 0.0, 0.0)], [run])
    assert window == samples
    measured = probe.measure(run, window)
    assert measured["cut"] == {"pAbove100": round(min(math.dist(s[1:], above) for s in samples), 2)}
    assert measured["straight_out"] == 95.0
    taught = [(pick, above), (above, travel)]
    farthest = max(min(probe._to_segment(s[1:], *line) for line in taught) for s in samples)
    assert measured["deviation"] == round(farthest, 2) and 4 < farthest < 5
