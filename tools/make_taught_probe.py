# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the taught-positions probe: converting again keeps the positions touched up on the robot.

KeepProbe v1 moves to three points in a work object with a tool: pKeep, pMove, pPlain. CrossArm converts it
(KEEPPROBE.LS, SETUP_FRAMES.LS, and crossarm_points.json: the points it wrote). On ROBOGUIDE the frames are
set, and two points are touched up as on the pendant: the robot is moved to another pose (a helper program),
then the FANUC COM interface records the current position into the program's P[n] (FRCTPPosition.Record, the
program opened for writing): pKeep 4 mm along x, 3 mm down and turned 2 deg about z, pMove 5 mm up. The
program is read back as the robot has it, as .LS (its web server) and as .TP (FTP), the .TP decoded by FANUC
PrintTP.

KeepProbe v2 is the next version of the ABB program: a new point pNew moved to first (every P number moves by
one), pMove moved 20 mm in the backup, pKeep and pPlain unchanged. CrossArm converts it keeping the taught
positions (crossarm.convert.taught, what --keep-taught does), once from the .LS read back, once from the .TP:
both must write the same points. Expected: pKeep its taught value (kept), pMove the new theoretical one (to
touch up again), pNew and pPlain theoretical. The program is loaded and run with the position recorded after
each move (PR[k]=LPOS, in the program's frames): the robot must reach each expected point.

  python tools/make_taught_probe.py write    the programs, in tests/fixtures/probes/taught
  python tools/make_taught_probe.py run      ROBOGUIDE; result in tests/fixtures/probes/taught/results
  python tools/make_taught_probe.py check    the result against the expected points
"""

import ftplib
import io
import math
import re
import subprocess
import sys
import tempfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.convert.setup import SETUP_NAME, build_setup
from crossarm.convert.taught import (
    AGAIN,
    KEPT,
    NEW,
    POINTS_FILE,
    THEORETICAL,
    Taught,
    apply,
    build_points,
    compare,
    read_robot,
    records,
)
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.maketp import TpRequest, find_maketp
from crossarm.fanuc.tp import CartesianPosition, Instruction, Motion, Program
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "taught"
RESULT = PROBE / "results" / "taught_roboguide.txt"
PROGRAM = "KEEPPROBE"
FIRST_PR = 50  # PR[50..53]: where the robot is after each move of v2
TOLERANCE_MM, TOLERANCE_DEG = 0.01, 0.01
# The touch-ups: (point, dx, dy, dz, dr in degrees about the tool's z, as R)
TOUCH = {"pKeep": (4.0, 0.0, -3.0, 2.0), "pMove": (0.0, 0.0, 5.0, 0.0)}
EXPECTED_STATUS = {"pNew": NEW, "pKeep": KEPT, "pMove": AGAIN, "pPlain": THEORETICAL}

TARGET = "[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]"


def module(version: int) -> str:
    move = "[150,120,200]" if version == 2 else "[150,100,200]"
    return "\r\n".join([  # one RAPID line per item, CRLF like a controller
        "MODULE KeepProbe",
        f"    ! CrossArm - taught positions probe, version {version}: see tools/make_taught_probe.py.",
        "    PERS tooldata tKeep:=[TRUE,[[0,0,150],[1,0,0,0]],[2,[0,0,60],[1,0,0,0],0,0,0]];",
        '    PERS wobjdata wKeep:=[FALSE,TRUE,"",[[900,0,400],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];',
        *([f"    CONST robtarget pNew:=[[0,-100,300],{TARGET}];"] if version == 2 else []),
        f"    CONST robtarget pKeep:=[[100,-150,200],{TARGET}];",
        f"    CONST robtarget pMove:=[{move},{TARGET}];",
        f"    CONST robtarget pPlain:=[[-50,0,250],{TARGET}];",
        "",
        "    PROC KeepProbe()",
        *(["        MoveL pNew,v200,fine,tKeep\\WObj:=wKeep;"] if version == 2 else []),
        "        MoveL pKeep,v200,fine,tKeep\\WObj:=wKeep;",
        "        MoveL pMove,v200,fine,tKeep\\WObj:=wKeep;",
        "        MoveL pPlain,v200,fine,tKeep\\WObj:=wKeep;",
        "    ENDPROC",
        "ENDMODULE",
        "",
    ])  # fmt: skip


def conversion(version: int) -> tuple[ConversionResult, ConversionConfig]:
    text = module(version)
    parsed = parse_text(text, path="KeepProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    result = convert([parsed.module], config, sources={"KeepProbe": text})
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    assert [info.program.name for info in result.programs] == [PROGRAM]
    return result, config


def program(result: ConversionResult) -> Program:
    return result.programs[0].program


def touch_helper(result: ConversionResult, source: str) -> Program:
    """A program moving the robot to the touched-up pose of one point: where the integrator jogs it."""
    info = result.programs[0]
    point = next(p for p in info.points if p.source == source)
    dx, dy, dz, dr = TOUCH[source]
    value = point.value
    assert isinstance(value, CartesianPosition)
    r = (value.r + dr + 180.0) % 360.0 - 180.0  # within -180..180, as the controller prints it
    moved = replace(value, x=value.x + dx, y=value.y + dy, z=value.z + dz, r=r)
    position = replace(next(p for p in info.program.positions if p.number == point.number), number=1, value=moved)
    lines = [Instruction(f"UFRAME_NUM={point.uf}"), Instruction(f"UTOOL_NUM={point.ut}"),
             Motion("L", "P[1]", "200mm/sec", "FINE")]  # fmt: skip
    name = f"KPTOUCH{list(TOUCH).index(source) + 1}"
    return Program(name, lines, [position], replace(info.program.attributes, comment="touch up"))


def measured(prog: Program) -> Program:
    """The program with the position recorded after each move, in the frames it selected."""
    lines: list[Instruction | Motion] = []
    count = 0
    for line in prog.lines:
        lines.append(line)
        if isinstance(line, Motion):
            lines.append(Instruction(f"PR[{FIRST_PR + count}]=LPOS"))
            count += 1
    return Program(prog.name, lines, prog.positions, prog.attributes)


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    for version in (1, 2):
        (PROBE / f"KeepProbe_v{version}.mod").write_bytes(module(version).encode("ascii"))
    result, config = conversion(1)
    setup = build_setup(result, config, SETUP_NAME)
    assert setup.program is not None
    files = {f"{PROGRAM}.LS": write_ls(program(result)), f"{SETUP_NAME}.LS": write_ls(setup.program)}
    for source in TOUCH:
        helper = touch_helper(result, source)
        files[f"{helper.name}.LS"] = write_ls(helper)
    (PROBE / "v1").mkdir(exist_ok=True)
    for name, text in files.items():
        (PROBE / "v1" / name).write_bytes(text.encode("ascii"))
    (PROBE / "v1" / POINTS_FILE).write_text(build_points(records(result, "files")), encoding="utf-8")
    (PROBE / "v1" / "crossarm_log.txt").write_text("CrossArm output of the probe (v1)\n", encoding="utf-8")
    print(f"probe written to {PROBE}")


def reconvert(robot_paths: list[Path], request: TpRequest | None = None) -> tuple[ConversionResult, Taught]:
    """v2 converted keeping the positions taught on the robot, as crossarm convert --keep-taught does."""
    robot = read_robot([*robot_paths, PROBE / "v1"], request)
    assert len(robot.earlier) == 1, robot.earlier
    result, _ = conversion(2)
    taught = compare(result, robot.earlier[0], robot, "files")
    apply(result, taught)
    return result, taught


_RECORD = r"""
$r = New-Object -ComObject FRRobot.FRCRobot
$r.ConnectEx("{host}", $false, 10, 1)
$p = $r.Programs.Item("{name}", $true, 3, 0)
$pos = $p.Positions.Item({number})
$pos.Record()
$pos.Update()
$p.Close()
"recorded"
"""


def touch_up(name: str, number: int) -> str:
    """The current position recorded into P[number] of the program, as SHIFT+TOUCHUP does on the pendant."""
    import roboguide

    script = _RECORD.format(host=roboguide.HOST, name=name, number=number)
    done = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                          timeout=60, check=False)  # fmt: skip
    return (done.stdout.strip().splitlines() or [done.stderr.strip()])[-1]


def fetch(name: str) -> bytes:
    import roboguide

    ftp = ftplib.FTP()
    ftp.connect(roboguide.HOST, roboguide.FTP_PORT, timeout=30)
    ftp.login()
    data = io.BytesIO()
    try:
        ftp.retrbinary(f"RETR {name}", data.write)
    finally:
        ftp.quit()
    return data.getvalue()


def _xyzwpr(value) -> str:
    return " ".join(f"{v:.3f}" for v in (value.x, value.y, value.z, value.w, value.p, value.r))


def measure() -> list[str]:
    import make_maketp_probe
    import roboguide
    from make_pose_probe import read_posreg

    write()
    names = [PROGRAM, SETUP_NAME, *(f"KPTOUCH{i + 1}" for i in range(len(TOUCH)))]
    roboguide.select()
    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)
        except Exception:  # noqa: BLE001, S110 - not there
            pass
    lines: list[str] = []
    result1, _ = conversion(1)
    try:
        for name in names:
            reason = roboguide.load(PROBE / "v1" / f"{name}.LS")
            if reason:
                return [*lines, f"load {name} {reason}"]
        lines.append(f"run {SETUP_NAME} {roboguide.run(SETUP_NAME, 120, resumes=1)}")
        numbers = {p.source: p.number for p in result1.programs[0].points}
        for i, source in enumerate(TOUCH):
            helper = f"KPTOUCH{i + 1}"
            lines.append(f"run {helper} {roboguide.run(helper, 60)}")
            lines.append(f"touched {source} {_xyzwpr(touch_helper(result1, source).positions[0].value)}")
            roboguide.select()
            lines.append(f"touchup {source} P[{numbers[source]}] {touch_up(PROGRAM, numbers[source])}")
        with tempfile.TemporaryDirectory(prefix="taught_probe_") as temp:
            folder = Path(temp)
            (folder / "ls").mkdir()
            (folder / "tp").mkdir()
            ls_text = roboguide.page(f"md/{PROGRAM}.LS").strip().replace("\r\n", "\n").replace("\n", "\r\n") + "\r\n"
            (folder / "ls" / f"{PROGRAM}.LS").write_bytes(ls_text.encode("ascii", "replace"))
            (PROBE / "results").mkdir(parents=True, exist_ok=True)
            (PROBE / "results" / f"{PROGRAM}.robot.LS").write_bytes(ls_text.encode("ascii", "replace"))
            (folder / "tp" / f"{PROGRAM}.TP").write_bytes(fetch(f"{PROGRAM.lower()}.tp"))
            result2, taught = reconvert([folder / "ls"])
            for point in taught.points:
                lines.append(f"status {point.source} {point.status} P[{point.number}] was P[{point.previous}]")
                if point.taught is not None:
                    lines.append(f"taught {point.source} {_xyzwpr(point.taught)}")
            text = write_ls(measured(program(result2)))
            (folder / f"{PROGRAM}.LS").write_bytes(text.encode("ascii"))
            (PROBE / "v2").mkdir(exist_ok=True)
            (PROBE / "v2" / f"{PROGRAM}.LS").write_bytes(write_ls(program(result2)).encode("ascii"))
            maketp, chosen = find_maketp(), make_maketp_probe.robot()
            if maketp is not None and chosen is not None:  # PrintTP deletes KEEPPROBE in the open cell: done last
                result_tp, _ = reconvert([folder / "tp"], TpRequest(chosen, maketp))
                same = program(result_tp).positions == program(result2).positions
                lines.append(f"tp_route {'same points' if same else 'other points'}")
                lines.append(f"printtp_left_program {'yes' if _on_robot(PROGRAM) else 'no'}")
            else:
                lines.append("tp_route skipped: no MakeTP/PrintTP or ROBOGUIDE robot")
            roboguide.select()
            try:
                roboguide.delete(PROGRAM)
            except Exception:  # noqa: BLE001, S110 - deleted by PrintTP
                pass
            reason = roboguide.load(folder / f"{PROGRAM}.LS")
            if reason:
                return [*lines, f"load v2 {reason}"]
        lines.append(f"run v2 {roboguide.run(PROGRAM, 120)}")
        found = read_posreg(roboguide.page("md/POSREG.VA"))
        for k, number in enumerate(sorted(p.number for p in result2.programs[0].points)):
            source = next(p.source for p in result2.programs[0].points if p.number == number)
            pr = found.get(FIRST_PR + k)
            lines.append(f"lpos {source} " + (" ".join(f"{v:.3f}" for v in pr) if pr else "none"))
        for position in program(result2).positions:
            source = next(p.source for p in result2.programs[0].points if p.number == position.number)
            lines.append(f"expected {source} {_xyzwpr(position.value)}")
        return lines
    finally:
        roboguide.select()
        for name in names:
            roboguide.release(name)
            try:
                roboguide.delete(name)
            except Exception:  # noqa: BLE001, S110 - already gone
                pass


def _on_robot(name: str) -> bool:
    import roboguide

    try:
        roboguide.page(f"md/{name}.LS")
        return True
    except OSError:
        return False


def _turn(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    from crossarm.geometry import wpr_to_matrix

    ma, mb = wpr_to_matrix(*a), wpr_to_matrix(*b)
    trace = sum(ma[i][k] * mb[i][k] for i in range(3) for k in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1) / 2))))


def verdict(lines: list[str]) -> str:
    """'' when the probe went as it should; else what did not."""
    wrong = [line for line in lines if line.startswith(("load ", "run ")) and not line.endswith("done")]
    wrong += [line for line in lines if line.startswith("touchup") and not line.endswith("recorded")]
    statuses = {m[1]: m[2] for line in lines if (m := re.match(r"status (\w+) (.+?) P\[", line))}
    wrong += [f"{source} {statuses.get(source)} (expected {status})" for source, status in EXPECTED_STATUS.items()
              if statuses.get(source) != status]  # fmt: skip
    expected = {p[1]: tuple(map(float, p[2:])) for p in (line.split() for line in lines) if p[0] == "expected"}
    taught = {p[1]: tuple(map(float, p[2:])) for p in (line.split() for line in lines) if p[0] == "taught"}
    touched = {p[1]: tuple(map(float, p[2:])) for p in (line.split() for line in lines) if p[0] == "touched"}
    for source in TOUCH:
        if source not in taught or source not in touched:
            wrong.append(f"{source}: no taught value read")
        elif math.dist(taught[source][:3], touched[source][:3]) > TOLERANCE_MM or _turn(taught[source][3:], touched[source][3:]) > TOLERANCE_DEG:
            wrong.append(f"{source}: read back {taught[source]}, touched up at {touched[source]}")
    for parts in (line.split() for line in lines):
        if parts[0] != "lpos":
            continue
        if parts[2] == "none" or parts[1] not in expected:
            wrong.append(f"{parts[1]}: not measured")
            continue
        at, want = tuple(map(float, parts[2:])), expected[parts[1]]
        gap, turn = math.dist(at[:3], want[:3]), _turn(at[3:], want[3:])
        if gap > TOLERANCE_MM or turn > TOLERANCE_DEG:
            wrong.append(f"{parts[1]} reached {gap:.3f} mm, {turn:.3f} deg from the point written")
    if len([line for line in lines if line.startswith("lpos")]) != len(EXPECTED_STATUS):
        wrong.append("not every move measured")
    if "tp_route same points" not in lines and not any(line.startswith("tp_route skipped") for line in lines):
        wrong.append("the .TP read back gives other points than the .LS")
    return "; ".join(wrong)


def run() -> str:
    lines = measure()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(RESULT.read_text(encoding="ascii"))
    return check()


def check() -> str:
    problem = verdict(RESULT.read_text(encoding="ascii").splitlines())
    print(f"FAIL {problem}" if problem else "taught probe: as measured")
    return f"FAIL {problem}" if problem else ""


def summary() -> str:
    lines = RESULT.read_text(encoding="ascii").splitlines()
    gaps = []
    expected = {p[1]: tuple(map(float, p[2:])) for p in (line.split() for line in lines) if p[0] == "expected"}
    for parts in (line.split() for line in lines):
        if parts[0] == "lpos" and parts[2] != "none" and parts[1] in expected:
            gaps.append(math.dist(tuple(map(float, parts[2:5])), expected[parts[1]][:3]))
    return (f"touched up on the robot (COM Record), reconverted: {len(gaps)} moves within {max(gaps, default=0):.4f} mm"
            " of the points written (taught kept, changed one theoretical), .LS and .TP read back alike")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    if command == "write":
        write()
    else:
        verdict_text = {"run": run, "check": check}[command]()
        sys.exit(1 if verdict_text.startswith("FAIL") else 0)
