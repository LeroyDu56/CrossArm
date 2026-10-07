# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""ConversionResult -> the commissioning checklist of crossarm_report.html.

What the integrator does on the FANUC cell, in the order it is done, each item with the values to enter or
check and links to the lines that use it (their rows in the side-by-side view):

    Load the programs     .LS (ASCII Upload, R507) or the .TP of the TP folder; every program before any runs
    Programs to provide   the TP or KAREL programs the integrator writes (external_routines): arguments, results
    Frames and tools      SETUP_FRAMES, each UFRAME / UTOOL and its values, what to teach on the robot
    Payloads              each PAYLOAD schedule and its values
    I/O                   each DI / DO / GI / GO / AO and the RAPID signal it was
    Registers and flags   R, F, SR, TIMER: free on the controller, initial values to set
    TODO lines            the lines left to write by hand, per program
    Points                the theoretical points to touch up, the positions kept in registers
    Motion                zones and speeds as converted, the moves converted on an assumption
    Other assumptions     every other warning, to check on the cell

Everything comes from what the conversion already knows; every text from the backup is escaped. Each item has
an id hashed from its group and what it says: the page keeps the ticks in the browser (localStorage, under the
report's identity), so a backup converted again keeps the ticks of the items that did not change, and an item
whose values changed comes back unticked. Without the script the list is all there, printable, boxes empty.
"""

import hashlib
import html
import re
from collections import defaultdict
from dataclasses import dataclass

from crossarm.convert.blockers import Blocker
from crossarm.convert.config import ConversionConfig
from crossarm.convert.external import argument_texts, note_texts
from crossarm.convert.html import inline
from crossarm.convert.report import payload_rows
from crossarm.convert.source_map import line_anchor, tp_text
from crossarm.convert.translate import Allocation, ConversionResult, FrameInfo, Note, ZoneUse
from crossarm.fanuc.maketp import TpExport
from crossarm.fanuc.tp import CartesianPosition

# The TP data a line uses: UFRAME_NUM=2, DO[3:name], PR[98,1]... (remarks left out).
_USE = re.compile(r"\b(UFRAME_NUM|UTOOL_NUM|PAYLOAD|DO|DI|GO|GI|AO|AI|F|R|SR|PR|TIMER)(?:\[|=)(\d+)")
Place = tuple[str, int | None]  # (TP program, RAPID line)

# Notes that belong with a group of their own rather than with the motion checks.
_FRAME_CAUSES = (Blocker.CALIBRATION, Blocker.RUNTIME_FRAME, Blocker.SAVED_FRAME, Blocker.STATIONARY)
_PAYLOAD_CAUSES = (Blocker.PAYLOAD,)
_IO_CAUSES = (Blocker.SIGNAL, Blocker.IO_ROUNDED)
_POINT_CAUSES = (Blocker.RUNTIME_POSITION,)
_MOTION_CAUSES = (Blocker.MOTION, Blocker.MOTION_SETTING, Blocker.AXIS_CONVENTION, Blocker.SEARCH,
                  Blocker.MOVE_ROUTINE, Blocker.MOVE_ROUTINE_ASSUMED)  # fmt: skip


def _e(text: object) -> str:
    return html.escape(str(text), quote=True)


@dataclass
class _Item:
    key: str  # what makes it this item: hashed into its id
    title: str  # HTML
    values: str = ""  # HTML, the values to enter or check
    note: str = ""  # HTML
    links: str = ""  # HTML


class _Places:
    """Where the programs use each register, frame, I/O...: links from an item to the lines."""

    def __init__(self, result: ConversionResult, anchors: set[tuple[str, int]]) -> None:
        self.anchors = anchors
        self.programs = {info.program.name for info in result.programs}
        self.uses: dict[tuple[str, int], list[Place]] = defaultdict(list)
        for info in result.programs:
            for i, line in enumerate(info.program.lines):
                rapid = info.sources[i] if i < len(info.sources) else None
                for text in tp_text(line):
                    if text.lstrip().startswith("!"):
                        continue
                    for match in _USE.finditer(text):
                        places = self.uses[(match[1], int(match[2]))]
                        if (info.program.name, rapid) not in places:
                            places.append((info.program.name, rapid))

    def links(self, places: list[Place], lead: str = "used in", limit: int = 4) -> str:
        out, seen = [], set()
        for program, line in places:
            if line and (program, line) in self.anchors:
                link = f'<a href="#{_e(line_anchor(program, line))}">{_e(program)} l.{line}</a>'
            elif program in self.programs:
                link = f'<a href="#p-{_e(program)}">{_e(program)}</a>'
            else:
                continue
            if link not in seen:
                seen.add(link)
                out.append(link)
        if not out:
            return ""
        more = len(out) - limit
        return f"{lead} " + ", ".join(out[:limit]) + (f" and {more} more" if more > 0 else "")

    def of(self, kind: str, number: int, lead: str = "used in") -> str:
        return self.links(self.uses.get((kind, number), []), lead)


def _pose(frame: FrameInfo) -> str:
    assert frame.frame is not None
    (x, y, z), (w, p, r) = frame.frame.pose.pos, frame.frame.pose.wpr()
    return _values(("X", x), ("Y", y), ("Z", z), ("W", w), ("P", p), ("R", r))


def _values(*pairs: tuple[str, float]) -> str:
    return "  ".join(f"{name} {value:.3f}" for name, value in pairs)


def _code(text: str) -> str:
    return f"<code>{_e(text)}</code>"


def _note_items(result: ConversionResult, places: _Places, causes: tuple[str, ...] | None,
                kinds: tuple[str, ...] = ("TODO", "WARNING"), skip: tuple[str, ...] = ()) -> list[_Item]:  # fmt: skip
    """One item per cause and program: the notes of those causes (None: every cause not in `skip`)."""
    grouped: dict[tuple[str, str], list[Note]] = defaultdict(list)
    for note in sorted(result.notes, key=lambda x: (x.program, x.rapid_line or 0)):
        if note.kind in kinds and (note.category in causes if causes is not None else note.category not in skip):
            grouped[(note.category, note.program)].append(note)
    items = []
    for (cause, program), notes in sorted(grouped.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        count = len(notes)
        where = f"{_e(program)}.LS" if program else "Whole conversion"
        kind = "TODO" if notes[0].kind == "TODO" else "warning"
        lines = f"{count} line{'s' if count > 1 else ''}" if program else f"{count} item{'s' if count > 1 else ''}"
        items.append(_Item(
            f"{cause}|{program}|{count}", f"{where}: {_e(cause)}",
            note=f'<span class="tag {"todo" if kind == "TODO" else "warn"}">{_e(lines)}</span> {inline(notes[0].message)}',
            links=places.links([(n.program, n.rapid_line) for n in notes], "at"),
        ))  # fmt: skip
    return items


# ---------------------------------------------------------------------------
# The groups, in the order commissioning goes
# ---------------------------------------------------------------------------


def _loading(result: ConversionResult, tp: TpExport | None, tp_where: str) -> tuple[str, list[_Item]]:
    items = []
    if tp is not None and not tp.problem and tp.made:
        items.append(_Item(
            f"tp|{tp_where}|{len(tp.made)}",
            f"Copy the {_code(tp_where or 'TP')} folder to a USB stick and load its {len(tp.made)} .TP programs"
            " (FILE menu)",
            note=f"Made by FANUC MakeTP for the robot {_code(tp.robot)}: a controller with older software may"
                 " refuse them. The .LS files are the same programs, for a controller with ASCII Upload (R507).",
        ))  # fmt: skip
    else:
        problem = f"No .TP written: {_e(tp.problem)}. " if tp is not None and tp.problem else ""
        items.append(_Item(
            "ascii-upload",
            "The controller has the ASCII Upload option (R507): it loads the .LS programs",
            note=f"{problem}Without it, a controller loads only binary .TP programs: convert again with"
                 " <code>--tp</code> (step 4 of the window) to have FANUC MakeTP, installed with ROBOGUIDE, write"
                 " them in a TP folder to copy to a USB stick.",
        ))  # fmt: skip
    for name, why in tp.refused if tp is not None else ():
        items.append(_Item(f"refused|{name}", f"{_e(name)}.LS: refused by MakeTP, no .TP",
                           note=f"{_e(why)}. Load the .LS, or fix the line MakeTP names."))  # fmt: skip
    names = [info.program.name for info in result.programs]
    setup = result.setup.program.name if result.setup and result.setup.program else None
    every = names + ([setup] if setup else [])
    shown = ", ".join(f"{_e(n)}.LS" for n in every[:60]) + (f" and {len(every) - 60} more" if len(every) > 60 else "")
    items.append(_Item(
        "load|" + ",".join(every),
        f"Load all {len(every)} programs before running any" if len(every) > 1 else "Load the program",
        values=shown,
        note="A CALL to a program the robot does not have fails when it runs."
             + (f" {_e(setup)} runs first (frames and tools, below)." if setup else "")
             + (" The programs to provide (next group) are loaded too." if result.provided else ""),
    ))  # fmt: skip
    return "", items


def _provided(result: ConversionResult, places: _Places) -> tuple[str, list[_Item]]:
    items = []
    for use in result.provided:
        arguments = argument_texts(use)
        items.append(_Item(
            f"provided|{use.program}|{use.routine}|{'|'.join(arguments)}",
            f"Provide {_code(use.program)}, a TP or KAREL program doing what RAPID {_code(use.routine)} did",
            values="<br>".join(_e(a) for a in arguments) or ("no argument" if use.arguments is not None else ""),
            note=_e("; ".join(note_texts(use))),
            links=places.links(use.calls, "called in"),
        ))  # fmt: skip
    intro = ("CrossArm does not write these routines (external_routines in the mapping file): write each program, load"
             " it with the others. It reads its arguments as <code>AR[1]</code>, <code>AR[2]</code>... and cannot"
             " change them; a num RAPID reads back is given back in the register named.")  # fmt: skip
    return intro, items


def _frames(result: ConversionResult, config: ConversionConfig, places: _Places) -> tuple[str, list[_Item]]:
    setup = result.setup
    items = []
    written = {(kind, f.number) for kind, f in setup.written} if setup else set()
    skipped = {(kind, f.number): why for kind, f, why in setup.skipped} if setup else {}
    if setup is not None and setup.program is not None:
        tools = sum(1 for kind, _ in setup.written if kind == "UTOOL")
        stored = []
        if setup.registers:
            stored.append(f"{len(setup.registers)} computed frame(s) in their position registers")
        stored += [f"{_e(a.name)} in PR[{a.base}] to PR[{a.base + len(a.values) - 1}]" for a in setup.arrays]
        stored += [f"{_e(a.name)} in R[{a.base}] to R[{a.base + len(a.values) - 1}]" for a in setup.numbers]
        items.append(_Item(
            f"setup|{setup.program.name}|{sorted(written)}",
            f"Run {_e(setup.program.name)}.LS once, before the converted programs",
            values=f"{tools} tool frame(s), {len(setup.written) - tools} user frame(s)"
                   + (f"; stores {', '.join(stored)}" if stored else ""),
            note=f"It overwrites those frame numbers: it starts with a message and a pause, resume to go on. It uses"
                 f" PR[{setup.scratch}] on the way"
                 + ("." if setup.scratch_checked else ": check that no program of the robot uses it."),
        ))  # fmt: skip
    for kind, frames, selected in (("UFRAME", result.uframes, "UFRAME_NUM"), ("UTOOL", result.utools, "UTOOL_NUM")):
        for f in frames:
            if f.number == 0:  # wobj0 / tool0: the world frame, the faceplate
                continue
            title = f"{kind}[{f.number}] {_code(f.rapid_name)}"
            links = places.of("PR", f.bank) if f.bank is not None else places.of(selected, f.number)
            if f.frame is None or f.problem:
                why = _e((f.problem or "built at run time").rstrip("."))
                items.append(_Item(f"{kind}|{f.number}|{f.rapid_name}|?", title,
                                   note=f"<strong>Not known at conversion time</strong>: {why}. Teach or measure it on"
                                        " the robot.", links=links))  # fmt: skip
                continue
            notes = []
            if (kind, f.number) in written:
                notes.append(f"set by {_e(setup.program.name)}.LS" if setup and setup.program else "")
            elif (kind, f.number) in skipped:
                notes.append(f"left out of the setup program ({_e(skipped[(kind, f.number)])}): enter it by hand")
            else:
                notes.append("enter it on the robot")
            if f.bank is not None:
                notes.append(f"above the controller's limit: kept in PR[{f.bank}], loaded into {kind}[{f.slot}]"
                             " before each use")  # fmt: skip
            if f.frame.saved:
                notes.append("value saved in the backup, changed at run time: check it")
            note = "; ".join(n for n in notes if n)
            items.append(_Item(f"{kind}|{f.number}|{f.rapid_name}|{_pose(f)}", title, values=_pose(f),
                               note=note[:1].upper() + note[1:] + ".", links=links))  # fmt: skip
    for c in result.computed_frames:
        x, y, z, w, p, r = c.values
        into = ", ".join(sorted({f"{kind} {name}" for kind, name, _, _ in c.uses}))
        register = f"PR[{c.number}]" if c.number is not None else "No position register left"
        items.append(_Item(
            f"computed|{c.key}|{c.number}", f"{register}: frame computed at conversion time, loaded into {_e(into)}",
            values=_values(("X", x), ("Y", y), ("Z", z), ("W", w), ("P", p), ("R", r)),
            note="Stored by the setup program." if c.number is not None else "Its loads stay TODO.",
            links=places.links([(program, line) for _, _, program, line in c.uses], "loaded in"),
        ))  # fmt: skip
    if result.utools:
        items.append(_Item(
            f"tool_pin|{config.tool_pin}",
            f"The tool's guide pin is in the {_e(config.tool_pin)} pin hole of the FANUC faceplate",
            note="The tool frames are written for that hole (<code>tool_pin</code>): with the pin in the other one,"
                 " change <code>tool_pin</code> in crossarm_mapping.json and convert again.",
        ))  # fmt: skip
    items += _note_items(result, places, _FRAME_CAUSES)
    intro = ("Values converted from the ABB: X, Y, Z in mm, W, P, R in degrees. User frames are relative to the robot"
             " world frame and the points to their user frame: where the FANUC robot does not stand where the ABB"
             " stood, teach the user frames again on the cell, and the points follow.")  # fmt: skip
    return intro, items


def _payloads(result: ConversionResult, config: ConversionConfig, places: _Places) -> tuple[str, list[_Item]]:
    items = []
    for schedule, name, mass, cog, inertia, note in payload_rows(result, config):
        title = f"PAYLOAD[{_e(schedule)}] {_code(name)}" if schedule != "—" else f"No schedule: {_code(name)}"
        if mass == "—":
            values = ""
            note = f"<strong>{_e(note)}</strong>: find the load and set it." if note else ""
        else:
            values = f"mass {_e(mass)} kg  centre {_e(cog)} cm  inertia {_e(inertia)} kgf.cm.s2"
            note = _e(note[:1].upper() + note[1:] + ".") if note else ""
        links = ""
        if schedule.isdigit():
            number = int(schedule)
            links = places.of("PAYLOAD", number, "selected in") or places.of("UTOOL_NUM", number, "tool used in")
        items.append(_Item(f"payload|{schedule}|{name}|{mass}|{cog}|{inertia}", title, values=values, note=note,
                           links=links))  # fmt: skip
    if result.utools and not items:
        items.append(_Item("payload|none", "No load declared in the backup: set each tool's payload schedule",
                           note="From the tool's data sheet: mass, centre of gravity, inertia."))  # fmt: skip
    items += _note_items(result, places, _PAYLOAD_CAUSES)
    intro = ("MENU > SYSTEM > Motion, one schedule per tool (its UTOOL number), the units of that screen: a program"
             " cannot set them. A robot running with the wrong payload has its collision detection wrong.")
    return intro, items


def _allocations(allocations: list[Allocation], prefix: str, places: _Places, what: str) -> list[_Item]:
    items = []
    for a in allocations:
        notes = [a.detail] if a.detail else []
        if a.fixed:
            notes.append("number pinned in the mapping file")
        note = "; ".join(notes)
        items.append(_Item(f"{prefix}|{a.number}|{a.rapid_name}|{a.detail}", f"{prefix}[{a.number}] {_code(a.rapid_name)}",
                           note=_e(note[:1].upper() + note[1:]) if note else "",
                           links=places.of(prefix, a.number, what)))  # fmt: skip
    return items


def _io(result: ConversionResult, places: _Places) -> tuple[str, list[_Item]]:
    items = []
    for allocations, prefix in ((result.digital_inputs, "DI"), (result.digital_outputs, "DO"),
                                (result.group_inputs, "GI"), (result.group_outputs, "GO"),
                                (result.analog_outputs, "AO")):  # fmt: skip
        items += _allocations(allocations, prefix, places, "used in")
    items += _note_items(result, places, _IO_CAUSES)
    intro = ("Assign each signal to its physical I/O on the controller (I/O screens: rack, slot, start), from the"
             " RAPID signal it was; the note gives its EIO.cfg line when the backup has it.")
    return intro, items


def _registers(result: ConversionResult, places: _Places) -> tuple[str, list[_Item]]:
    items = []
    for allocations, prefix in ((result.registers, "R"), (result.flags, "F"), (result.string_registers, "SR"),
                                (result.timers, "TIMER")):  # fmt: skip
        items += _allocations(allocations, prefix, places, "used in")
    if result.wait_clock:
        timer, clock = result.wait_clock
        number = int(re.sub(r"\D", "", timer) or 0)
        items.append(_Item(f"wait_clock|{timer}|{clock}", f"{_e(timer)}: times the waits with a RAPID MaxTime",
                           note=f"Read into {_e(clock.split(':')[0])}]: no other program may use that timer.",
                           links=places.of("TIMER", number)))  # fmt: skip
    intro = ("Registers, flags and timers are shared by every program on a FANUC controller: check that no program"
             " already on the robot uses these numbers (pin others in crossarm_mapping.json), and set the initial"
             " value a note gives.")  # fmt: skip
    return intro, items


def _todo(result: ConversionResult, places: _Places) -> tuple[str, list[_Item]]:
    counts: dict[str, list[Note]] = defaultdict(list)
    for note in result.notes:
        if note.kind == "TODO":
            counts[note.program].append(note)
    items = []
    for program, notes in sorted(counts.items()):
        notes.sort(key=lambda n: n.rapid_line or 0)
        causes = sorted({n.category for n in notes})
        filter_link = (f'<a href="#review" data-prog="{_e(program)}">the list</a>' if program
                       else '<a href="#review">the list</a>')  # fmt: skip
        first = places.links([(n.program, n.rapid_line) for n in notes], "at")
        items.append(_Item(
            f"todo|{program}|{len(notes)}|{','.join(causes)}",
            f"{_e(program) + '.LS' if program else 'Whole conversion'}: {len(notes)} TODO",
            note=_e(", ".join(causes)),
            links=(first + "; " if first else "") + filter_link,
        ))  # fmt: skip
    intro = ("Lines left as <code>!TODO</code> remarks in the .LS: write them by hand (in ROBOGUIDE or on the"
             " pendant) before the program runs. The items to review give each one with why.")
    return intro, items


def _points(result: ConversionResult, places: _Places) -> tuple[str, list[_Item]]:
    items = []
    for info in result.programs:
        if not info.points:
            continue
        name = info.program.name
        frames = sorted({(p.uf, p.ut) for p in info.points})
        listed = ", ".join(f"P[{p.number}] {_e(p.source)}" for p in info.points[:40])
        more = len(info.points) - 40
        cartesian = sum(1 for p in info.points if isinstance(p.value, CartesianPosition))
        joints = len(info.points) - cartesian
        items.append(_Item(
            f"points|{name}|{len(info.points)}|" + ",".join(p.source for p in info.points),
            f"{_e(name)}.LS: {len(info.points)} point{'s' if len(info.points) > 1 else ''}",
            values=listed + (f" and {more} more" if more > 0 else ""),
            note="In " + ", ".join(f"UF {uf} / UT {ut}" for uf, ut in frames)
                 + (f"; {joints} in joints" if joints else "") + ".",
            links=f'<a href="#p-{_e(name)}">the program</a>' if name in places.programs else "",
        ))  # fmt: skip
    for a in result.point_registers:
        items.append(_Item(f"pr|{a.number}|{a.rapid_name}", f"PR[{a.number}] {_code(a.rapid_name)}",
                           note="A position the programs set at run time: check the moves to it.",
                           links=places.of("PR", a.number)))  # fmt: skip
    for array in result.point_arrays:
        if array.base is None:
            continue
        last = array.base + len(array.values) - 1
        items.append(_Item(f"array|{array.name}|{array.base}|{len(array.values)}",
                           f"PR[{array.base}] to PR[{last}] {_code(array.name)}",
                           note=f"{len(array.values)} points the setup program stores, read at run time: touch them"
                                " up in the registers.",
                           links=places.of("PR", array.base)))  # fmt: skip
    items += _note_items(result, places, _POINT_CAUSES)
    intro = ("The points are the ABB's, as theoretical points: touch them up on the robot, in their user frame and"
             " tool. The target: within 10 mm of the ABB path.")
    return intro, items


def _motion(result: ConversionResult, config: ConversionConfig, places: _Places) -> tuple[str, list[_Item]]:
    items = []
    if config.target_robot and not config.motion_profile_source:
        items.append(_Item(
            f"profile|{config.target_robot}",
            f"No speeds and zones measured on the {_e(config.target_robot)}: those of the"
            f" {_e(config.motion_profile.name)} are used",
            note="Check joint speeds and corners on the robot, or measure it with tools/probe_motion.py.",
        ))  # fmt: skip
    zones: dict[str, list[ZoneUse]] = defaultdict(list)
    for (zone, _speed, _motion, _then), use in sorted(result.zones.items()):
        if not (use.tp == "FINE" and zone.lower() == "fine"):
            zones[zone].append(use)
    for zone, uses in zones.items():
        items.append(_zone_item(zone, uses))
    speeds: dict[str, list[str]] = defaultdict(list)
    for (speed, motion), tp in sorted(result.speeds.items()):
        speeds[motion].append(f"{speed} {tp}")
    for motion, texts in sorted(speeds.items()):
        joint = motion == "J"
        items.append(_Item(
            f"speed|{motion}|{'|'.join(texts)}", f"{_e(_MOTIONS.get(motion, motion))} move speeds",
            values=_e(" · ".join(texts)),
            note=(f"% = RAPID TCP speed / {config.joint_speed_ref_mm_s:g} mm/s: a joint move can take 20 % more or"
                  " less time than on the ABB. Check the cycle time." if joint
                  else "Kept in mm/s: a move takes as long up to 1000 mm/s."),
        ))  # fmt: skip
    items += _note_items(result, places, _MOTION_CAUSES, kinds=("WARNING",))
    intro = ("How the moves were written, and the moves converted on an assumption: check them on the robot, at low"
             " speed first.")
    return intro, items


def _assumptions(result: ConversionResult, places: _Places) -> tuple[str, list[_Item]]:
    taken = _FRAME_CAUSES + _PAYLOAD_CAUSES + _IO_CAUSES + _POINT_CAUSES + _MOTION_CAUSES
    intro = "The other lines converted on an assumption (the warnings): check that it holds on this cell."
    return intro, _note_items(result, places, None, kinds=("WARNING",), skip=taken)


_MOTIONS = {"J": "Joint", "L": "Linear", "C": "Circular"}


def _span(values: list[float], unit: str = "") -> str:
    low, high = min(values), max(values)
    return f"{low:.1f}{unit}" if round(low, 1) == round(high, 1) else f"{low:.1f} to {high:.1f}{unit}"


def _zone_item(zone: str, uses: list[ZoneUse]) -> _Item:
    """A RAPID zone: the CNT it was written as (one per speed), and how close the corners come, both robots."""
    cnts = sorted({u.tp for u in uses}, key=lambda t: (t != "FINE", int(t[3:]) if t.startswith("CNT") else 0))
    values = cnts[0] if len(cnts) == 1 else f"{cnts[0]} to {cnts[-1]}"
    values += f" ({len(uses)} speed{'s' if len(uses) > 1 else ''})" if len(uses) > 1 else ""
    cut = [u for u in uses if u.abb_cut is not None and u.fanuc_cut is not None]
    if cut:
        values += (f"  corner cut ABB {_span([u.abb_cut for u in cut if u.abb_cut is not None], ' mm')},"
                   f" FANUC {_span([u.fanuc_cut for u in cut if u.fanuc_cut is not None], ' mm')}")  # fmt: skip
    capped = sum(1 for u in uses if u.capped)
    note = ("The path passes this close to the points: check it" if cut else "Corners rounded by the CNT: check the path") + " where it passes close to something."
    if capped:
        note += f" At {capped} speed{'s' if capped > 1 else ''} CNT100 rounds less: the FANUC path stays closer."
    return _Item(f"zone|{zone}|{values}", f"Zone {_code(zone)}", values=_e(values), note=note)


_GROUPS = (
    ("load", "Load the programs"),
    ("provided", "Programs to provide"),
    ("frames", "Frames and tools"),
    ("payloads", "Payloads"),
    ("io", "I/O to map"),
    ("registers", "Registers, flags and timers"),
    ("todo", "TODO lines to finish by hand"),
    ("points", "Points to touch up"),
    ("motion", "Motion to check"),
    ("assumptions", "Other assumptions to check"),
)


def checklist_section(result: ConversionResult, config: ConversionConfig, anchors: set[tuple[str, int]], *,
                      identity: str, tp: TpExport | None = None, tp_where: str = "") -> tuple[str, str, str]:  # fmt: skip
    """The section of the page: (id, menu label, HTML). `anchors`: the RAPID lines the page shows (links lead
    there); `identity`: what tells this report from another (the ticks are kept under it)."""
    places = _Places(result, anchors)
    built = {
        "load": _loading(result, tp, tp_where),
        "provided": _provided(result, places),
        "frames": _frames(result, config, places),
        "payloads": _payloads(result, config, places),
        "io": _io(result, places),
        "registers": _registers(result, places),
        "todo": _todo(result, places),
        "points": _points(result, places),
        "motion": _motion(result, config, places),
        "assumptions": _assumptions(result, places),
    }
    groups, total, ids = [], 0, set()
    number = 0
    for gid, title in _GROUPS:
        intro, items = built[gid]
        if not items:
            continue
        number += 1
        rows = []
        for item in items:
            digest = hashlib.sha1(f"{gid}|{item.key}".encode()).hexdigest()[:10]
            while digest in ids:  # two items saying the same thing: still two boxes
                digest = hashlib.sha1(digest.encode()).hexdigest()[:10]
            ids.add(digest)
            parts = [f'<label for="ck-{digest}" class="ckt">{item.title}</label>']
            if item.values:
                parts.append(f'<div class="ckv">{item.values}</div>')
            if item.note:
                parts.append(f'<div class="ckd">{item.note}</div>')
            if item.links:
                parts.append(f'<div class="ckl">{item.links}</div>')
            rows.append(f'<li data-id="{digest}"><input type="checkbox" id="ck-{digest}">'
                        f'<div class="ckb">{"".join(parts)}</div></li>')  # fmt: skip
        total += len(items)
        groups.append(
            f'<div class="ckg" id="ck-{gid}"><h3>{number}. {_e(title)} <span class="ckc">{len(items)}'
            f' item{"s" if len(items) > 1 else ""}</span></h3>'
            + (f'<p class="muted">{intro}</p>' if intro else "")
            + f'<ul class="ck">{"".join(rows)}</ul></div>'
        )
    key = hashlib.sha1(identity.encode()).hexdigest()[:16]
    body = [
        "<h2>Commissioning checklist</h2>",
        ("<p>What to do on the FANUC cell, in the order it is done, with the values to enter or check and links to"
         " the lines that use them. Tick each item when done: the ticks are kept in this browser, for this report."
         " Print it to tick it on paper.</p>"),
        ('<div class="bar js-only"><span class="meter ck-meter"><span id="ck-meter"></span></span>'
         f' <b id="ck-total">{total} items</b> <label><input id="ck-hide" type="checkbox"> hide the items done</label>'
         ' <button type="button" id="ck-print">Print the checklist</button>'
         ' <button type="button" id="ck-reset">Untick all</button> <span id="ck-store" class="muted"></span></div>'),
        f'<div id="ck" data-key="{key}">' + "".join(groups) + "</div>",
    ]  # fmt: skip
    return "checklist", "Checklist", "\n".join(body)


CHECKLIST_CSS = """
.ckg h3 { display: flex; gap: 12px; align-items: baseline; margin-bottom: .2em; }
.ckc { font-size: .8em; font-weight: 600; color: var(--muted); }
.ckg.complete .ckc { color: var(--ok); }
.ckg > p { margin: .2em 0 .5em; font-size: .92em; }
ul.ck { list-style: none; padding: 0; margin: 0 0 1em; border-top: 1px solid var(--line); }
ul.ck li { display: flex; gap: 10px; align-items: flex-start; padding: 6px 4px; border-bottom: 1px solid var(--line); }
ul.ck input[type=checkbox] { appearance: none; -webkit-appearance: none; flex: none; width: 18px; height: 18px;
  margin: 3px 0 0; border: 2px solid var(--muted); border-radius: 4px; background: var(--bg); cursor: pointer;
  display: grid; place-content: center; }
ul.ck input[type=checkbox]:checked { background: var(--ok); border-color: var(--ok); }
ul.ck input[type=checkbox]:checked::after { content: "\\2713"; color: #fff; font-weight: 700; font-size: 13px;
  line-height: 1; }
ul.ck input[type=checkbox]:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.ckb { min-width: 0; flex: 1; }
.ckt { font-weight: 600; cursor: pointer; }
li.done .ckt { color: var(--muted); }
.ckv { font: .88em ui-monospace, Consolas, "Courier New", monospace; overflow-wrap: anywhere; white-space: pre-wrap; }
.ckd, .ckl { font-size: .9em; }
.ckl { color: var(--muted); }
.ck-meter { display: inline-block; width: 160px; }
#ck-meter { width: 0; background: var(--ok); }
#ck.hide-done li.done { display: none; }
@media print {
  html.print-ck main > :not(#checklist):not(header) { display: none !important; }
  #ck.hide-done li.done { display: flex; }
  .ckg h3 { break-after: avoid; }
  ul.ck li { break-inside: avoid; }
  ul.ck input[type=checkbox] { border-color: #000; }
  ul.ck input[type=checkbox]:checked { background: #fff; border-color: #000; }
  ul.ck input[type=checkbox]:checked::after { color: #000; }
}
"""

CHECKLIST_JS = r"""
(function () {
  // Commissioning checklist: the ticks are kept in this browser, under the report's identity. Storage may be
  // blocked (a file:// page in some browsers, a strict profile): the list still works, ticks are just not kept.
  var d = document, box = d.getElementById('ck');
  if (!box) { return; }
  var key = 'crossarm-checklist:' + box.getAttribute('data-key'), ticks = {}, kept = true;
  try {
    ticks = JSON.parse(window.localStorage.getItem(key) || '{}');
    if (!ticks || typeof ticks !== 'object') { ticks = {}; }
  } catch (e) { ticks = {}; kept = false; }
  var items = [].slice.call(box.querySelectorAll('li[data-id]')), groups = [].slice.call(box.querySelectorAll('.ckg'));
  function told() {
    var el = d.getElementById('ck-store');
    if (el) { el.textContent = kept ? 'ticks kept in this browser' : 'ticks not kept: this browser blocks local storage'; }
  }
  function save() {
    if (!kept) { return; }
    try { window.localStorage.setItem(key, JSON.stringify(ticks)); } catch (e) { kept = false; told(); }
  }
  function count() {
    var all = 0, done = 0;
    groups.forEach(function (g) {
      var lis = g.querySelectorAll('li[data-id]'), n = lis.length, k = g.querySelectorAll('li.done').length;
      g.querySelector('.ckc').textContent = k + ' / ' + n;
      g.classList.toggle('complete', n > 0 && k === n);
      all += n; done += k;
    });
    d.getElementById('ck-total').textContent = done + ' of ' + all + ' done';
    d.getElementById('ck-meter').style.width = (all ? Math.round(done * 100 / all) : 0) + '%';
  }
  items.forEach(function (li) {
    var input = li.querySelector('input'), id = li.getAttribute('data-id');
    input.checked = ticks[id] === 1;
    li.classList.toggle('done', input.checked);
    input.addEventListener('change', function () {
      if (input.checked) { ticks[id] = 1; } else { delete ticks[id]; }
      li.classList.toggle('done', input.checked);
      save(); count();
    });
  });
  d.getElementById('ck-hide').addEventListener('change', function () { box.classList.toggle('hide-done', this.checked); });
  d.getElementById('ck-reset').addEventListener('click', function () {
    if (!window.confirm('Untick every item of the checklist?')) { return; }
    ticks = {};
    items.forEach(function (li) { li.querySelector('input').checked = false; li.classList.remove('done'); });
    try { window.localStorage.removeItem(key); } catch (e) { kept = false; told(); }
    count();
  });
  var root = d.documentElement;
  d.getElementById('ck-print').addEventListener('click', function () {
    root.classList.add('print-ck');
    window.print();
  });
  window.addEventListener('afterprint', function () { root.classList.remove('print-ck'); });
  told(); count();
})();
"""
