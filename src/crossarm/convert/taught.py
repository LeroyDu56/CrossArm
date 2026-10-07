# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Positions touched up on the robot, kept through a new conversion (crossarm convert --keep-taught).

CrossArm's points are theoretical: at commissioning the integrator touches them up on the FANUC robot. When the
ABB program changes later and the backup is converted again, the new programs would carry theoretical points
over every one of those touch-ups. So:

- every conversion writes crossarm_points.json next to its programs: each point it wrote, named by the RAPID it
  came from (routine, expression, and its rank when the routine writes that expression more than once: other
  frames, another value), with its P[n], frames and theoretical value, and the frames' values. A .LS alone does
  not say which P[n] is which RAPID point, and P numbers move when a routine gains a point;
- converting again with --keep-taught reads the programs as they are on the robot (.LS, or .TP decoded by FANUC
  PrintTP) and that file of the earlier conversion. A point the robot holds as it was written was not touched
  up: it is written theoretical again. A point touched up (another value on the robot) keeps its taught value
  (configuration and turns included) when its theoretical value and its frames did not change; when they did,
  the touch-up no longer fits: the new theoretical value is written, to touch up again.

Points kept in position registers (arrays of points SETUP_FRAMES fills) are not compared: the robot's registers
are not read. A point passed to a routine is a P[n] of the caller, compared like any other.
"""

import json
import math
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path

from crossarm.backup import _safe_extract
from crossarm.convert.translate import ConversionResult, FrameInfo, PointInfo
from crossarm.fanuc.ls_parser import LSFormatError, parse_ls
from crossarm.fanuc.maketp import TpRequest, print_tp
from crossarm.fanuc.tp import CartesianPosition, JointPosition, Program
from crossarm.geometry import wpr_to_matrix

POINTS_FILE = "crossarm_points.json"
OUTPUT_MARK = "crossarm_log.txt"  # the folder of a CrossArm output: what is under it is CrossArm's, not the robot's
FORMAT = 1
TOLERANCE_MM = 0.01  # values are written with 3 decimals: below this, the same point
TOLERANCE_DEG = 0.01

KEPT = "kept"  # touched up on the robot, kept
AGAIN = "touch up again"  # touched up on the robot, but its theoretical value or its frames changed
THEORETICAL = "theoretical"  # not touched up on the robot: theoretical again
NEW = "new"  # not in the earlier conversion
GONE = "gone"  # in the earlier conversion, no longer written
NOT_READ = "not read"  # its program (or P[n]) not found or not readable among the robot's programs
STATUSES = (KEPT, AGAIN, NEW, THEORETICAL, GONE, NOT_READ)

README = (
    "The points CrossArm wrote, for a later conversion with --keep-taught: each by the RAPID it came from (routine, "
    "expression, rank of that expression in the routine), with its P[n], frames and theoretical value as written. "
    "Converting again with --keep-taught reads it, with the programs as they are on the robot, to keep the "
    "positions touched up there. Not to edit."
)

Value = CartesianPosition | JointPosition


@dataclass(frozen=True, slots=True)
class PointRecord:
    """One point as a conversion wrote it."""

    routine: str  # Module.Routine
    source: str  # RAPID expression
    rank: int  # 1, or more when the routine writes the same expression in several points
    program: str  # TP program
    number: int  # P[n]
    uf: int
    ut: int
    wobj: str  # the frames the value is in, by their RAPID names ("" when not known)
    tool: str
    value: Value

    @property
    def key(self) -> tuple[str, str, int]:
        return self.routine.upper(), self.source.upper(), self.rank


@dataclass
class PointsFile:
    """crossarm_points.json: what a conversion wrote."""

    task: str
    points: list[PointRecord] = field(default_factory=list)
    # ("UF" | "UT", RAPID name) -> X, Y, Z, W, P, R as SETUP_FRAMES sets it; None: not known at conversion time
    frames: dict[tuple[str, str], tuple[float, ...] | None] = field(default_factory=dict)
    arrays: dict[str, int] = field(default_factory=dict)  # array of points -> elements kept in position registers
    path: Path | None = None  # where it was read from


@dataclass(frozen=True, slots=True)
class TaughtPoint:
    """What became of one point."""

    status: str  # one of STATUSES
    routine: str
    source: str
    rank: int
    program: str  # the TP program written now; a gone point: the earlier one
    number: int | None  # P[n] written now; None: gone
    previous: int | None  # P[n] in the earlier conversion, and on the robot; None: new
    why: str
    theoretical: Value | None = None  # the theoretical value of this conversion (None: gone)
    earlier: Value | None = None  # the theoretical value of the earlier one
    taught: Value | None = None  # the value read on the robot

    @property
    def written(self) -> Value | None:
        """What the .LS now holds."""
        return self.taught if self.status == KEPT else self.theoretical

    def deviation_mm(self) -> float | None:
        """How far the taught point is from the theoretical one of this conversion (both Cartesian)."""
        if isinstance(self.taught, CartesianPosition) and isinstance(self.theoretical, CartesianPosition):
            return _distance(self.taught, self.theoretical)
        return None


@dataclass
class RobotPrograms:
    """The programs as they are on the robot, and the earlier conversion's points, found in --keep-taught."""

    programs: dict[str, Program] = field(default_factory=dict)
    unread: dict[str, str] = field(default_factory=dict)  # program -> why it could not be read
    earlier: list[PointsFile] = field(default_factory=list)
    tp_problem: str = ""  # why no .TP was decoded at all
    tp_files: int = 0  # .TP given, decoded or not


@dataclass
class Taught:
    """The taught positions of one task, as this conversion kept them or not."""

    earlier: str  # the crossarm_points.json read
    points: list[TaughtPoint] = field(default_factory=list)
    unread: dict[str, str] = field(default_factory=dict)  # earlier program -> why its points were not compared
    foreign: list[tuple[str, int]] = field(default_factory=list)  # (program, P[n]) on the robot CrossArm did not write
    arrays: int = 0  # points of arrays kept in position registers: not compared

    def of(self, status: str) -> list[TaughtPoint]:
        return [p for p in self.points if p.status == status]

    def counts(self) -> dict[str, int]:
        return {status: len(self.of(status)) for status in STATUSES}

    def summary(self) -> str:
        counts = self.counts()
        return ", ".join(f"{n} {status}" for status, n in counts.items() if n) or "no point"


# ---------------------------------------------------------------------------
# What a conversion wrote: crossarm_points.json
# ---------------------------------------------------------------------------


def _frame(frames: list[FrameInfo], number: int, bank: int | None) -> FrameInfo | None:
    if bank is not None:
        return next((f for f in frames if f.bank == bank), None)
    return next((f for f in frames if f.bank is None and f.number == number), None)


def _frame_value(info: FrameInfo | None) -> tuple[float, ...] | None:
    if info is None or info.frame is None or info.problem:
        return None
    (x, y, z), (w, p, r) = info.frame.pose.pos, info.frame.pose.wpr()
    return tuple(round(v, 3) for v in (x, y, z, w, p, r))


def _rounded(value: Value) -> Value:
    if isinstance(value, JointPosition):
        return JointPosition(tuple(round(v, 3) for v in value.joints))
    return replace(value, x=round(value.x, 3), y=round(value.y, 3), z=round(value.z, 3), w=round(value.w, 3),
                   p=round(value.p, 3), r=round(value.r, 3))  # fmt: skip


def records(result: ConversionResult, task: str = "") -> PointsFile:
    """The points this conversion wrote, as crossarm_points.json keeps them."""
    out = PointsFile(task)
    for kind, frames in (("UF", result.uframes), ("UT", result.utools)):
        for info in frames:
            out.frames[(kind, info.rapid_name)] = _frame_value(info)
    for info in result.programs:
        ranks: dict[str, int] = {}
        for point in sorted(info.points, key=lambda p: p.number):
            ranks[point.source.upper()] = ranks.get(point.source.upper(), 0) + 1
            out.points.append(_record(result, info.module, info.routine, info.program.name, point,
                                      ranks[point.source.upper()]))  # fmt: skip
    out.arrays = {a.name: len(a.values) for a in result.point_arrays if a.base is not None}
    return out


def _record(result: ConversionResult, module: str, routine: str, program: str, point: PointInfo,
            rank: int) -> PointRecord:  # fmt: skip
    wobj = _frame(result.uframes, point.uf, point.uf_bank)
    tool = _frame(result.utools, point.ut, point.ut_bank)
    return PointRecord(f"{module}.{routine}", point.source, rank, program, point.number, point.uf, point.ut,
                       wobj.rapid_name if wobj else "", tool.rapid_name if tool else "", _rounded(point.value))  # fmt: skip


def _value_json(value: Value) -> dict[str, object]:
    if isinstance(value, JointPosition):
        return {"joints": list(value.joints)}
    return {"xyzwpr": [value.x, value.y, value.z, value.w, value.p, value.r], "config": value.config}


def _value_of(data: dict) -> Value:
    if "joints" in data:
        return JointPosition(tuple(float(v) for v in data["joints"]))
    x, y, z, w, p, r = (float(v) for v in data["xyzwpr"])
    return CartesianPosition(x, y, z, w, p, r, str(data["config"]))


def build_points(points: PointsFile) -> str:
    """The JSON text of crossarm_points.json."""
    programs: dict[str, dict[str, object]] = {}
    for record in points.points:
        entry = programs.setdefault(record.program, {"routine": record.routine, "points": []})
        entry["points"].append({  # type: ignore[union-attr]
            "P": record.number, "rapid": record.source, "rank": record.rank, "uf": record.uf, "ut": record.ut,
            "wobj": record.wobj, "tool": record.tool, **_value_json(record.value),
        })  # fmt: skip
    frames: dict[str, dict[str, object]] = {"uframes": {}, "utools": {}}
    for (kind, name), value in points.frames.items():
        frames["uframes" if kind == "UF" else "utools"][name] = list(value) if value is not None else None
    data = {"_README": README, "format": FORMAT, "task": points.task, "frames": frames, "programs": programs,
            "point_arrays": points.arrays}  # fmt: skip
    # One line per point and per frame: placeholders, laid out, then replaced by the compact JSON of each.
    lines: list[str] = []

    def one_line(value: object) -> str:
        lines.append(json.dumps(value, ensure_ascii=False))
        return f"\0{len(lines) - 1}\0"

    for entry in programs.values():
        entry["points"] = [one_line(p) for p in entry["points"]]  # type: ignore[union-attr]
    for table in frames.values():
        for name in table:
            table[name] = one_line(table[name])
    text = json.dumps(data, indent=1, ensure_ascii=False)
    for i, line in enumerate(lines):
        text = text.replace(f'"\\u0000{i}\\u0000"', line, 1)
    return text + "\n"


def read_points(path: Path) -> PointsFile:
    """crossarm_points.json as build_points wrote it; ValueError when it is not one."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != FORMAT:
            raise ValueError(f"format {data.get('format')!r}, this CrossArm reads {FORMAT}")
        out = PointsFile(str(data.get("task", "")), path=path)
        for kind, key in (("UF", "uframes"), ("UT", "utools")):
            for name, value in data["frames"][key].items():
                out.frames[(kind, name)] = tuple(float(v) for v in value) if value is not None else None
        for program, entry in data["programs"].items():
            for p in entry["points"]:
                out.points.append(PointRecord(entry["routine"], p["rapid"], int(p["rank"]), program, int(p["P"]),
                                              int(p["uf"]), int(p["ut"]), p["wobj"], p["tool"], _value_of(p)))  # fmt: skip
        out.arrays = {name: int(n) for name, n in data.get("point_arrays", {}).items()}
        return out
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"{path}: not a {POINTS_FILE} ({exc!r})") from exc
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc


# ---------------------------------------------------------------------------
# The robot's programs
# ---------------------------------------------------------------------------


def _output_roots(files: list[Path]) -> set[Path]:
    return {f.parent for f in files if f.name.lower() == OUTPUT_MARK}


def read_robot(paths: list[Path], tp: TpRequest | None = None, decode=print_tp) -> RobotPrograms:
    """The programs found in the paths (folders, .zip, .LS or .TP files): .LS read, .TP decoded by PrintTP; and the
    crossarm_points.json of earlier conversions. What lies in a CrossArm output folder (holding crossarm_log.txt:
    its .LS and its TP folder are theoretical) is not taken for the robot's programs."""
    robot = RobotPrograms()
    temps: list[Path] = []
    try:
        files: list[Path] = []
        for path in map(Path, paths):
            if path.is_file() and path.suffix.lower() == ".zip":
                temp = Path(tempfile.mkdtemp(prefix="crossarm_taught_"))
                temps.append(temp)
                with zipfile.ZipFile(path) as archive:
                    _safe_extract(archive, temp)
                files += sorted(p for p in temp.rglob("*") if p.is_file())
            elif path.is_dir():
                files += sorted(p for p in path.rglob("*") if p.is_file())
            elif path.is_file():
                files.append(path)
            else:
                raise ValueError(f"--keep-taught: {path} not found")
        roots = _output_roots(files)
        tps: list[Path] = []
        for file in files:
            if file.name.lower() == POINTS_FILE:
                robot.earlier.append(read_points(file))
                continue
            if any(root == file.parent or root in file.parents for root in roots):
                continue
            suffix = file.suffix.lower()
            if suffix == ".ls":
                _read_ls(file.read_bytes(), file.stem.upper(), robot)
            elif suffix == ".tp":
                tps.append(file)
        robot.tp_files = len(tps)
        if tps:
            decoded = decode(tps, tp or TpRequest())
            robot.tp_problem = decoded.problem
            for file in tps:
                name = file.stem.upper()
                if name in robot.programs:
                    continue  # its .LS was given too
                if name in decoded.texts:
                    _read_ls(decoded.texts[name].encode("cp1252", errors="replace"), name, robot)
                else:
                    why = dict(decoded.refused).get(name) or decoded.problem or "not decoded"
                    robot.unread.setdefault(name, f".TP not decoded by FANUC PrintTP: {why}")
        return robot
    finally:
        for temp in temps:
            shutil.rmtree(temp, ignore_errors=True)


def _read_ls(data: bytes, name: str, robot: RobotPrograms) -> None:
    data = data.strip()  # a program saved from the robot's web page starts and ends with empty lines
    try:
        program = parse_ls(data.decode("cp1252", errors="replace"))
    except LSFormatError as exc:
        if data.startswith(b"/PROG"):
            robot.unread.setdefault(name, f"not read: {exc}")
        return
    if program.name.upper() not in robot.programs:
        robot.programs[program.name.upper()] = program
        robot.unread.pop(program.name.upper(), None)


def earlier_for(task: str, files: list[PointsFile], tasks: int) -> PointsFile | None:
    """The earlier conversion's points of this task: the file of the same task, else the only one for the only task."""
    same = [f for f in files if f.task.upper() == task.upper()]
    if same:
        return same[0]
    return files[0] if len(files) == 1 and tasks == 1 else None


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _distance(a: CartesianPosition, b: CartesianPosition) -> float:
    return math.dist((a.x, a.y, a.z), (b.x, b.y, b.z))


def _turn(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """The angle between two orientations given as W, P, R, in degrees (a W, P, R and its equivalent are the same)."""
    ma, mb = wpr_to_matrix(*a), wpr_to_matrix(*b)
    trace = sum(ma[i][k] * mb[i][k] for i in range(3) for k in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1) / 2))))


def _config(text: str) -> str:
    return "".join(text.split()).upper()


def same(a: Value, b: Value) -> bool:
    """The same point, as written: within TOLERANCE_MM and TOLERANCE_DEG, same configuration and turns."""
    if isinstance(a, JointPosition) or isinstance(b, JointPosition):
        return (isinstance(a, JointPosition) and isinstance(b, JointPosition) and len(a.joints) == len(b.joints)
                and all(abs(x - y) <= TOLERANCE_DEG for x, y in zip(a.joints, b.joints, strict=True)))  # fmt: skip
    return (_distance(a, b) <= TOLERANCE_MM and _turn((a.w, a.p, a.r), (b.w, b.p, b.r)) <= TOLERANCE_DEG
            and _config(a.config) == _config(b.config))  # fmt: skip


def _same_frame(a: tuple[float, ...] | None, b: tuple[float, ...] | None) -> bool:
    if a is None or b is None:
        return a is None and b is None  # not known either time: nothing says it changed
    return math.dist(a[:3], b[:3]) <= TOLERANCE_MM and _turn(a[3:6], b[3:6]) <= TOLERANCE_DEG  # type: ignore[arg-type]


def _moved(old: Value, new: Value) -> str:
    if isinstance(old, CartesianPosition) and isinstance(new, CartesianPosition):
        what = []
        if _distance(old, new) > TOLERANCE_MM:
            what.append(f"moved {_distance(old, new):.1f} mm")
        if _turn((old.w, old.p, old.r), (new.w, new.p, new.r)) > TOLERANCE_DEG:
            what.append(f"turned {_turn((old.w, old.p, old.r), (new.w, new.p, new.r)):.1f} deg")
        if _config(old.config) != _config(new.config):
            what.append(f"configuration {old.config} -> {new.config}")
        return "changed in the backup: " + ", ".join(what)
    return "changed in the backup"


def compare(result: ConversionResult, earlier: PointsFile, robot: RobotPrograms, task: str = "") -> Taught:
    """What becomes of each point: kept as taught on the robot, theoretical, to touch up again, new, gone."""
    taught = Taught(str(earlier.path or POINTS_FILE))
    now = records(result, task)
    before = {record.key: record for record in earlier.points}
    for record in now.points:
        old = before.pop(record.key, None)
        taught.points.append(_compare(record, old, earlier, now, robot, taught))
    for old in before.values():
        taught.points.append(TaughtPoint(GONE, old.routine, old.source, old.rank, old.program, None, old.number,
                                         "no longer in the backup's programs", None, old.value))  # fmt: skip
    written = {(r.program.upper(), r.number) for r in earlier.points}
    for name in sorted({r.program.upper() for r in earlier.points}):
        program = robot.programs.get(name)
        if program is None:
            taught.unread[name] = robot.unread.get(name, "not among the robot's programs given")
            continue
        taught.foreign += [(name, p.number) for p in program.positions if (name, p.number) not in written]
    taught.arrays = sum(now.arrays.values())
    return taught


def _compare(record: PointRecord, old: PointRecord | None, earlier: PointsFile, now: PointsFile,
             robot: RobotPrograms, taught: Taught) -> TaughtPoint:  # fmt: skip
    def point(status: str, why: str, value: Value | None = None) -> TaughtPoint:
        return TaughtPoint(status, record.routine, record.source, record.rank, record.program, record.number,
                           old.number if old else None, why, record.value, old.value if old else None, value)  # fmt: skip

    if old is None:
        return point(NEW, "not in the earlier conversion")
    program = robot.programs.get(old.program.upper())
    if program is None:
        why = robot.unread.get(old.program.upper(), "not among the robot's programs given")
        return point(NOT_READ, f"{old.program}: {why}")
    on_robot = next((p for p in program.positions if p.number == old.number), None)
    if on_robot is None:
        return point(NOT_READ, f"P[{old.number}] not in {old.program} on the robot")
    value = on_robot.value
    if (on_robot.uf, on_robot.ut) == (old.uf, old.ut) and same(value, old.value):
        changed = not same(record.value, old.value)
        return point(THEORETICAL, "not touched up on the robot" + ("; " + _moved(old.value, record.value) if changed else ""),
                     value)  # fmt: skip
    if (on_robot.uf, on_robot.ut) != (old.uf, old.ut):
        return point(AGAIN, f"touched up in UF {on_robot.uf}, UT {on_robot.ut}, written in UF {old.uf}, UT {old.ut}",
                     value)  # fmt: skip
    if not same(record.value, old.value):
        return point(AGAIN, _moved(old.value, record.value), value)
    if isinstance(record.value, CartesianPosition):
        for kind, before, after, what in (("UF", old.wobj, record.wobj, "work object"),
                                          ("UT", old.tool, record.tool, "tool")):  # fmt: skip
            if before.upper() != after.upper():
                return point(AGAIN, f"{what} {before or '?'} -> {after or '?'}", value)
            if not _same_frame(earlier.frames.get((kind, before)), now.frames.get((kind, after))):
                return point(AGAIN, f"{what} {after} changed in the backup (U{'FRAME' if kind == 'UF' else 'TOOL'})",
                             value)  # fmt: skip
    return point(KEPT, "touched up on the robot, unchanged in the backup", value)


def apply(result: ConversionResult, taught: Taught) -> None:
    """The kept points' taught values into the programs to write, in the frames numbered by this conversion."""
    kept = {(p.program, p.number): p.taught for p in taught.of(KEPT)}
    for info in result.programs:
        positions = info.program.positions
        for i, position in enumerate(positions):
            value = kept.get((info.program.name, position.number))
            if value is not None:
                positions[i] = replace(position, value=value)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def report_section(taught: Taught, robot_from: str) -> str:
    """The report's part about the taught positions (Markdown, added to the .md and .html reports)."""
    counts = taught.counts()
    text = "\n## Taught positions (--keep-taught)\n\n"
    text += (f"Earlier conversion: `{taught.earlier}`; programs on the robot: {robot_from}. A point touched up on "
             "the robot keeps its taught value when its theoretical value and its frames did not change; when they "
             "did, the new theoretical value is written, to touch up again.\n\n")  # fmt: skip
    text += f"- {counts[KEPT]} kept as taught on the robot\n"
    text += f"- {counts[AGAIN]} to touch up again (theoretical value written)\n"
    text += f"- {counts[NEW]} new (theoretical)\n"
    text += f"- {counts[THEORETICAL]} theoretical: not touched up on the robot\n"
    text += f"- {counts[GONE]} gone from the backup\n"
    text += f"- {counts[NOT_READ]} not compared: their program not read on the robot (theoretical)\n"
    if taught.arrays:
        text += (f"- {taught.arrays} points of arrays kept in position registers: not compared (SETUP_FRAMES sets "
                 "their theoretical values again)\n")  # fmt: skip

    def where(p: TaughtPoint) -> str:
        was = f" (was P[{p.previous}])" if p.previous is not None and p.previous != p.number else ""
        rank = f" #{p.rank}" if p.rank > 1 else ""
        return f"`{p.program}` P[{p.number if p.number is not None else p.previous}] `{p.source}`{rank}{was}"

    if taught.of(AGAIN):
        text += "\n### To touch up again\n\n" + "".join(f"- {where(p)}: {p.why}\n" for p in taught.of(AGAIN))
    if taught.of(GONE):
        text += "\n### Gone from the backup\n\n" + "".join(f"- {where(p)}\n" for p in taught.of(GONE))
    if taught.unread:
        text += "\n### Programs not read on the robot\n\n"
        text += "".join(f"- `{name}`: {why}\n" for name, why in sorted(taught.unread.items()))
    if taught.foreign:
        text += "\n### Positions on the robot CrossArm did not write (not carried over)\n\n"
        text += "".join(f"- `{name}` P[{number}]\n" for name, number in taught.foreign)
    return text
