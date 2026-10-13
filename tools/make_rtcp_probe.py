# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the remote TCP probe: a stationary tool (robhold FALSE) and a work object the robot holds
(robhold TRUE), converted to the FANUC Remote TCP option (J624) by crossarm.convert.remote_tcp.

RtcpProbe.mod is converted by CrossArm: the stationary tool becomes UFRAME[n] (its tframe, in the world), the work
object the robot holds UTOOL[m] (uframe x oframe, on the faceplate), each point the inverse pose; MoveL / MoveC are
written `L P[k] ... RTCP` / `C P[i] P[k] ... RTCP`, MoveJ `J P[k]` (J refuses RTCP: ASBN-092). On ROBOGUIDE:

- after each fine move, the robot's flange is read in the world frame (CRobT(\\Tool:=tool0 \\WObj:=wobj0):
  PR[k]=LPOS) and compared with where RAPID puts it, tframe x inverse(p) x inverse(uframe x oframe), worked out here
  with quaternions (RobotStudio puts the flange there too: RobotStudio check of 2026-10-13, 0.3 mm);
- while RTCONV runs, md/CURPOS.DG is read over and over: the user frame position (the work object in the stationary
  tool's frame) gives where the stationary tool's TCP is in the part, which RAPID keeps on the line and the circle
  through the points (a corner CNT5 rounds near its point); the speed along the line is that of the TCP in the part;
- the raw program RTPLAIN makes the same L move without RTCP: the part's origin goes straight instead, and the
  tool's TCP leaves the line in the part by millimetres (what RTCP is for); RTJRTCP (J with RTCP) is refused at load.

  python tools/make_rtcp_probe.py write    the module and the programs, in tests/fixtures/probes/rtcp
  python tools/make_rtcp_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results stored
  python tools/make_rtcp_probe.py check    the stored results against what was measured
"""

import math
import re
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_karel_pose_probe import _about, _pose, _robtarget, gap, pose, pose_inv, pose_mult
from make_karel_probe import _ftp, q_mul, q_unit, read_pr

from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Motion, Program

PROBE = ROOT / "tests" / "fixtures" / "probes" / "rtcp"
RESULT = PROBE / "results" / "rtcp_roboguide.txt"
STAMP = datetime(2026, 1, 1)
DOWN = (0.0, 0.0, 1.0, 0.0)  # a half turn about y
GUN = ((1300.0, 50.0, 700.0), q_unit(_about(2, 30.0)))  # rtGun: the stationary tool, in the world (its z up)
PART = ((10.0, -20.0, 200.0), q_unit(_about(2, 10.0)))  # rtPart.uframe, on the faceplate
PART_O = ((5.0, 0.0, 0.0), q_unit(_about(0, 4.0)))  # rtPart.oframe
POINTS = {  # the stationary tool's TCP in the part
    "rtP1": ((40.0, 30.0, 0.0), q_unit(q_mul(DOWN, _about(2, 15.0)))),
    "rtP2": ((-60.0, -20.0, 5.0), q_unit(q_mul(q_mul(DOWN, _about(2, -25.0)), _about(0, 12.0)))),
    # the circle: centre (-20, -20, 5), radius 40, from rtP2 (180 deg) through 240 deg to 300 deg
    "rtP3": ((-40.0, -54.641, 5.0), q_unit(q_mul(DOWN, _about(1, -10.0)))),  # its via point
    "rtP4": ((0.0, -54.641, 5.0), q_unit(q_mul(DOWN, _about(2, 20.0)))),  # its end
}
LIFT = 8.0  # MoveL Offs(rtP1,0,0,8) z5: the corner
SPEED = 20.0  # v20: mm/s
SEEN = ("rtF1", "rtF2", "rtF4", "rtF5")  # the flange read after the moves to rtP1 (RtPrep), rtP2, rtP4, rtP1
TOLERANCE = 0.05  # mm, on the path samples; the flange after a fine move: 0.01 mm, 0.01 deg


def _held() -> tuple:
    return pose_mult((PART[0], PART[1]), (PART_O[0], PART_O[1]))


MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE RtcpProbe",
    "    ! CrossArm - remote TCP probe: see tools/make_rtcp_probe.py.",
    f"    PERS tooldata rtGun:=[FALSE,{_pose(GUN)},[1,[0,0,1],[1,0,0,0],0,0,0]];",
    f"    PERS wobjdata rtPart:=[TRUE,TRUE,\"\",{_pose(PART)},{_pose(PART_O)}];",
    *(f"    CONST robtarget {name}:={_robtarget(p[0], p[1])};" for name, p in POINTS.items()),
    *(f"    VAR robtarget {name};" for name in SEEN),
    "    VAR num rtDone:=0;",
    "",
    "    PROC RtPrep()",
    "        MoveJ rtP1,v500,fine,rtGun\\WObj:=rtPart;",
    "        rtF1:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "    ENDPROC",
    "",
    "    PROC RtConv()",
    "        rtDone:=0;",
    "        MoveL rtP2,v20,fine,rtGun\\WObj:=rtPart;",
    "        rtF2:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        MoveC rtP3,rtP4,v20,fine,rtGun\\WObj:=rtPart;",
    "        rtF4:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    f"        MoveL Offs(rtP1,0,0,{LIFT:g}),v20,z5,rtGun\\WObj:=rtPart;",
    "        MoveL rtP1,v20,fine,rtGun\\WObj:=rtPart;",
    "        rtF5:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        rtDone:=1;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip


def conversion(folder: Path):
    """RtcpProbe.mod converted as `crossarm convert` does: RTPREP.LS, RTCONV.LS, SETUP_FRAMES.LS."""
    from crossarm import pipeline
    from crossarm.convert import ConversionConfig

    (PROBE / "RtcpProbe.mod").write_bytes(MODULE.encode("ascii"))
    run = pipeline.run([PROBE / "RtcpProbe.mod"], folder, ConversionConfig(timestamp=STAMP), log=lambda _: None)
    result = run.tasks[0].result
    assert result is not None and not [n for n in result.notes if n.kind == "TODO"], result and result.notes
    assert len(result.remote_tcp) == 1, result.remote_tcp
    return result


def kept(result) -> dict[str, int]:
    """rtF1... -> the PR CrossArm keeps it in; RTDONE -> its R; UF / UT -> the remote TCP frames' numbers."""
    found = {a.rapid_name.upper(): a.number for a in result.point_registers}
    found["RTDONE"] = next(a.number for a in result.registers if a.rapid_name == "rtDone")
    _tool, _wobj, found["UF"], found["UT"] = result.remote_tcp[0]
    return found


def _program(name: str, lines: list, comment: str, positions=(), group: str = "1,*,*,*,*") -> Program:
    body = [line if isinstance(line, Motion) else Instruction(line) for line in lines]
    return Program(name, body, list(positions), attributes=Attributes(comment=comment, created=STAMP,
                                                                         default_group=group))  # fmt: skip


def raw_programs(result) -> list[Program]:
    """RTPLAIN: the move to rtP2 back to rtP1 without RTCP; RTJRTCP: J with RTCP (refused at load)."""
    conv = next(info.program for info in result.programs if info.program.name == "RTCONV")
    numbers = kept(result)
    first = next(p for p in conv.positions)  # rtP2, as converted
    prep = next(info.program for info in result.programs if info.program.name == "RTPREP")
    back = next(p for p in prep.positions)  # rtP1, as converted
    frames = [f"UFRAME_NUM={numbers['UF']}", f"UTOOL_NUM={numbers['UT']}"]
    plain = _program("RTPLAIN", [*frames, Motion("L", "P[1]", "20mm/sec", "FINE"), Motion("L", "P[2]", "20mm/sec", "FINE")],
                     "remote TCP probe: no RTCP", [first.__class__(1, first.uf, first.ut, first.value),
                                                  back.__class__(2, back.uf, back.ut, back.value)])  # fmt: skip
    refused = _program("RTJRTCP", [*frames, Motion("J", "P[1]", "20%", "FINE", options="RTCP")],
                       "remote TCP probe: J RTCP", [back.__class__(1, back.uf, back.ut, back.value)])  # fmt: skip
    prep_pr = _program("RTPRPR", ["UFRAME_NUM=0", "UTOOL_NUM=1"]
                       + [f"PR[{k}]=LPOS" for name, k in sorted(numbers.items()) if name.startswith("RTF")],
                       "remote TCP probe prep")  # fmt: skip
    return [plain, refused, prep_pr]


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="crossarm_rtcp_") as temp:
        result = conversion(Path(temp))
        for name in ("RTPREP", "RTCONV", "SETUP_FRAMES"):
            (PROBE / f"{name}.LS").write_bytes((Path(temp) / f"{name}.LS").read_bytes())
    for program in raw_programs(result):
        (PROBE / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
    for name, number in kept(result).items():
        print(f"  {name} {number}")
    print(f"probe written to {PROBE}")


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------


def _sampler(stop: threading.Event, frames: tuple[str, str], out: list[str]) -> None:
    """md/CURPOS.DG read over and over: 't x y z w p r' of the user frame position while those frames are selected."""
    import roboguide

    start = time.monotonic()
    while not stop.is_set():
        try:
            text = roboguide.page("md/CURPOS.DG")
        except OSError:
            continue
        at = time.monotonic() - start
        selected = re.search(r"Frame #:\s*(\d+)\s+Tool #:\s*(\d+)", text)
        block = text.split("CURRENT USER FRAME POSITION:")[1].split("Tool #")[0] if "USER FRAME" in text else ""
        values = [re.search(rf"\b{axis}:\s*(-?\d*\.?\d+)", block) for axis in "XYZWPR"]
        if selected and (selected[1], selected[2]) == frames and all(values):
            out.append(f"{at:.3f} " + " ".join(v[1] for v in values))  # type: ignore[index]


def _sampled(name: str, frames: tuple[str, str], timeout: float) -> tuple[str, list[str]]:
    import roboguide

    stop, samples = threading.Event(), []
    reader = threading.Thread(target=_sampler, args=(stop, frames, samples))
    reader.start()
    try:
        status = roboguide.run(name, timeout)
    finally:
        stop.set()
        reader.join()
    return status, samples


def measure() -> dict[str, str]:
    import roboguide

    write()
    with tempfile.TemporaryDirectory(prefix="crossarm_rtcp_") as temp:
        numbers = kept(conversion(Path(temp)))
    names = ["RTPRPR", "SETUP_FRAMES", "RTPREP", "RTCONV", "RTPLAIN"]
    frames = (str(numbers["UF"]), str(numbers["UT"]))
    found: dict[str, str] = {"frames": " ".join(frames)}
    for name in [*names, "RTJRTCP"]:
        roboguide.release(name)
    roboguide.select()
    try:
        for name in names:
            found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
        refused = roboguide.load(PROBE / "RTJRTCP.LS")
        found["RTJRTCP_load"] = re.sub(r"^.*?(ASBN-\d+)", r"\1", refused).split(" at line")[0] if refused else "loaded"
        found["RTPRPR_run"] = roboguide.run("RTPRPR", 60)
        found["SETUP_FRAMES_run"] = roboguide.run("SETUP_FRAMES", 60, resumes=1)
        roboguide.zero([numbers["RTDONE"]])
        found["RTPREP_run"] = roboguide.run("RTPREP", 120)
        found["RTCONV_run"], conv = _sampled("RTCONV", frames, 300)
        roboguide.release("RTCONV")  # paused by an alarm, it would hold the robot
        found["conv_done"] = f"{roboguide.numreg().get(numbers['RTDONE'], float('nan')):g}"
        posreg = roboguide.page("md/POSREG.VA")
        for name in SEEN:
            found[name.upper()] = read_pr(posreg, numbers[name.upper()])
        found["RTPLAIN_run"], plain = _sampled("RTPLAIN", frames, 120)
        found.update({f"conv_{i:03d}": s for i, s in enumerate(conv)})
        found.update({f"plain_{i:03d}": s for i, s in enumerate(plain)})
        return found
    finally:
        roboguide.select()
        for name in [*names, "RTJRTCP"]:
            roboguide.release(name)
        roboguide.select()
        for name in [*names, "RTJRTCP"]:
            _ftp(f"DELE {name.lower()}.tp")


# -- RAPID's semantics, with quaternions, independently of CrossArm -------------------------------------------------


def flange(p: tuple) -> tuple:
    """Where RAPID puts the flange: flange x (uframe x oframe) x p = tframe."""
    return pose_mult(pose_mult(GUN, pose_inv(p)), pose_inv(_held()))


def _target(name: str) -> tuple:
    return POINTS[name][0], q_unit(POINTS[name][1])


def _samples(found: dict[str, str], run: str) -> list[str]:
    """The samples taken while RTCONV ("conv") or RTPLAIN ("plain") ran, in order."""
    return [v for k, v in sorted(found.items()) if re.fullmatch(rf"{run}_\d+", k)]


def _tcp_in_part(sample: str) -> tuple[float, tuple[float, ...]]:
    """(time, where the stationary tool's TCP is in the part) from a sample: the user frame position is the part
    in the tool's frame, its inverse the tool in the part."""
    values = [float(v) for v in sample.split()]
    return values[0], pose_inv(pose(tuple(values[1:])))[0]


def _off_line(point, a, b) -> tuple[float, float]:
    d = [y - x for x, y in zip(a, b, strict=True)]
    t = sum((p - x) * dd for p, x, dd in zip(point, a, d, strict=True)) / sum(dd * dd for dd in d)
    t = min(1.0, max(0.0, t))
    return math.dist(point, [x + t * dd for x, dd in zip(a, d, strict=True)]), t


def _circle(a, b, c):
    def cross(u, v):
        return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])

    ab, ac = [y - x for x, y in zip(a, b, strict=True)], [y - x for x, y in zip(a, c, strict=True)]
    m = cross(ab, ac)
    m2 = sum(x * x for x in m)
    s1, s2 = cross(m, ab), cross(ac, m)
    lab, lac = sum(x * x for x in ab), sum(x * x for x in ac)
    centre = [x + (lac * u + lab * v) / (2 * m2) for x, u, v in zip(a, s1, s2, strict=True)]
    return centre, [x / math.sqrt(m2) for x in m], math.dist(centre, a)


def _off_circle(point, circle) -> float:
    centre, normal, radius = circle
    height = sum((p - c) * n for p, c, n in zip(point, centre, normal, strict=True))
    flat = math.sqrt(max(0.0, math.dist(point, centre) ** 2 - height**2))
    return math.hypot(height, flat - radius)


def path_gaps(found: dict[str, str]) -> tuple[float, float, int]:
    """(worst gap of the conversion's samples to the path RAPID makes, worst of those near the corner, samples)."""
    p1, p2, p3, p4 = (_target(n)[0] for n in POINTS)
    lift = (p1[0], p1[1], p1[2] + LIFT)
    circle = _circle(p2, p3, p4)
    worst = corner = 0.0
    samples = _samples(found, "conv")
    for sample in samples:
        _, at = _tcp_in_part(sample)
        off = min(_off_line(at, p1, p2)[0], _off_circle(at, circle), _off_line(at, p4, lift)[0],
                  _off_line(at, lift, p1)[0])  # fmt: skip
        if math.dist(at, lift) < 6.0:  # z5 rounds the corner, inside its 5 mm
            corner = max(corner, off)
        else:
            worst = max(worst, off)
    return worst, corner, len(samples)


def line_speed(found: dict[str, str]) -> float:
    """mm/s of the stationary tool's TCP along the part, on the line rtP1 -> rtP2 away from its ends."""
    p1, p2 = _target("rtP1")[0], _target("rtP2")[0]
    on = []
    for value in _samples(found, "conv"):
        at, point = _tcp_in_part(value)
        off, t = _off_line(point, p1, p2)
        if off < TOLERANCE and 0.15 < t < 0.85:
            on.append((at, t))
    if len(on) < 2:
        return float("nan")
    (t0, s0), (t1, s1) = on[0], on[-1]
    return (s1 - s0) * math.dist(p1, p2) / (t1 - t0)


def plain_gap(found: dict[str, str]) -> float:
    """How far the TCP leaves the line rtP2 -> rtP1 in the part without RTCP."""
    p1, p2 = _target("rtP1")[0], _target("rtP2")[0]
    return max((_off_line(_tcp_in_part(v)[1], p2, p1)[0] for v in _samples(found, "plain")), default=0.0)


def verdict(found: dict[str, str]) -> str:
    wrong = [f"{n}: {found.get(f'{n}_load')}" for n in ("RTPRPR", "SETUP_FRAMES", "RTPREP", "RTCONV", "RTPLAIN")
             if found.get(f"{n}_load") != "loaded"]  # fmt: skip
    wrong += [f"{n}: {found.get(f'{n}_run')}" for n in ("RTPRPR", "SETUP_FRAMES", "RTPREP", "RTCONV", "RTPLAIN")
              if found.get(f"{n}_run") != "done"]  # fmt: skip
    if not found.get("RTJRTCP_load", "").startswith("ASBN-092"):
        wrong.append(f"J with RTCP: {found.get('RTJRTCP_load')}, ASBN-092 expected")
    if found.get("conv_done") != "1":
        wrong.append(f"RTCONV done {found.get('conv_done')}")
    if wrong:
        return "; ".join(wrong)
    for name, target in zip(SEEN, ("rtP1", "rtP2", "rtP4", "rtP1"), strict=True):
        mm, deg = gap(found[name.upper()], flange(_target(target)))
        if mm > 0.01 or deg > 0.01:
            wrong.append(f"{name} {found[name.upper()]}: {mm:.3f} mm, {deg:.3f} deg from RAPID")
    worst, corner, count = path_gaps(found)
    if count < 6 or worst > TOLERANCE or corner > 5.0:
        wrong.append(f"path: {count} samples, {worst:.3f} mm off RAPID's path, {corner:.3f} mm at the corner")
    speed = line_speed(found)
    if not abs(speed - SPEED) <= 0.25 * SPEED:
        wrong.append(f"speed along the part {speed:.1f} mm/s, {SPEED:g} expected")
    if plain_gap(found) < 5.0:
        wrong.append(f"without RTCP the TCP stays {plain_gap(found):.3f} mm from the line: RTCP shows nothing")
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    worst = max(gap(found[n.upper()], flange(_target(t))) for n, t in zip(SEEN, ("rtP1", "rtP2", "rtP4", "rtP1"),
                                                                            strict=True))  # fmt: skip
    path, corner, count = path_gaps(found)
    return (f"flange after 4 moves within {worst[0]:.3f} mm / {worst[1]:.3f} deg; the stationary TCP on RAPID's line"
            f" and circle in the part within {path:.3f} mm over {count} samples (corner z5 {corner:.2f} mm), at"
            f" {line_speed(found):.1f} mm/s for v{SPEED:g}; without RTCP {plain_gap(found):.1f} mm off; J RTCP refused")


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
    print(f"FAIL {problem}" if problem else f"rtcp probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
