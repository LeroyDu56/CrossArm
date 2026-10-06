# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""ConversionResult -> Markdown report (crossarm_report.md).

The report is what the integrator works from on site: which frames, registers
and I/O numbers the programs expect, which heuristics were applied, and every
RAPID line that still needs manual work.
"""

from crossarm import __version__
from crossarm.convert.config import ConversionConfig
from crossarm.convert.configuration import TOOL_PIN_DEFAULT
from crossarm.convert.coverage import fmt_percent
from crossarm.convert.translate import Allocation, ConversionResult, FrameInfo
from crossarm.fanuc.tp import CartesianPosition
from crossarm.licence import CONTACT, LicenceStatus

KGF_CM_S2 = 0.0980665  # kg.m2 in one kgf.cm.s2, the unit of the FANUC payload screen


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return ["_None._", ""]
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |" for row in rows]
    return out + [""]


def _frame_rows(frames: list[FrameInfo]) -> list[list[str]]:
    rows = []
    for f in frames:
        if f.frame is None or f.problem:
            rows.append([str(f.number), f.rapid_name, "—", "—", f.problem])
            continue
        (x, y, z), (w, p, r) = f.frame.pose.pos, f.frame.pose.wpr()
        note = "value saved in the backup, changed at run time: check it" if f.frame.saved else ""
        if f.bank is not None:  # above what the controller holds
            kind = "UTOOL" if f.frame.robhold else "UFRAME"
            kept = f"above the controller's limit: kept in PR[{f.bank}], loaded into {kind}[{f.slot}] before each use"
            note = f"{kept}; {note}" if note else kept
        rows.append([
            str(f.number), f.rapid_name,
            f"{x:.3f}, {y:.3f}, {z:.3f}", f"{w:.3f}, {p:.3f}, {r:.3f}", note,
        ])  # fmt: skip
    return rows


def _tool_pin_text(config: ConversionConfig) -> str:
    """Which way round the tool sits: the one thing about the tool frames the programs cannot tell."""
    if config.tool_pin == TOOL_PIN_DEFAULT:
        return (
            "The tool frames are the ABB ones as they are. That puts the tool's guide pin in the pin hole on -x"
            " of the FANUC faceplate frame: for the same TCP pose it is where the ABB flange had it (on the ABB,"
            " the guide pin hole is on -x of tool0). The two flanges differ, so the adapter plate decides: with"
            ' the pin in the +x hole, the ISO 9409-1 position, set `"tool_pin": "+x"` in the mapping file.'
        )
    return (
        "The tool's guide pin goes in the pin hole on +x of the FANUC faceplate frame (`tool_pin`, the ISO"
        " 9409-1 position). On the ABB it was on -x of tool0, so the tool frames are turned half a turn about z:"
        " x and y change sign, and J6 of joint targets is -J6 of the ABB instead of 180 - J6."
    )


def _motion_section(result: ConversionResult, config: ConversionConfig) -> list[str]:
    """How speeds and zones were written, and what they were matched on."""
    profile = config.motion_profile.name
    lines = ["## Speed and zone mapping", ""]
    if config.motion_profile_source == "mapping file":
        lines += [f"Speeds and zones: the profile of the mapping file, measured on the {profile}.", ""]
    elif config.motion_profile_source:
        lines += [f"Speeds and zones: {config.motion_profile_source}.", ""]
    elif config.target_robot:
        lines += [
            (
                f"**Target robot {config.target_robot}: no speeds and zones were measured on its"
                f" series: those of the {profile} are used.** Another arm can differ by twice as much or more (on"
                " an R-2000iC/190S joint moves are 2.25 times slower for the same %, and corners rounded up to"
                " 2.4 times more by the same CNT). Measure it with tools/probe_motion.py and pass the profile in"
                " the mapping file (`motion_profile`), or check joint speeds and corners on the robot."
            ),
            "",
        ]
    lines += [
        (
            f"- Linear and circular moves keep their speed in mm/s: measured on both robots, a move takes as"
            f" long up to 1000 mm/s. Joint moves: `%` = RAPID TCP speed / {config.joint_speed_ref_mm_s:g} mm/s"
            " (`joint_speed_ref_mm_s`), clamped to 1-100 %: the TCP speed a J 100 % move reaches, measured on"
            f" the {profile} (3,800 to 5,300 mm/s depending on the move, so a joint move can take 20 % more or"
            " less time than on the ABB)."
        ),
    ]
    if config.zone_mapping == "linear":
        lines.append(f"- Zones: `CNT` = zone radius (mm) x {config.cnt_per_mm:g} (`cnt_per_mm`), max 100.")
    else:
        lines.append(
            "- Zones: a RAPID zone rounds a corner by about the same distance at any speed, a CNT by more the"
            " faster the move. Each zone is written as the smallest CNT that rounds a right-angle corner as much"
            f" at the move's speed, from both robots measured ({profile}, `zone_mapping`). Into a faster move"
            " the FANUC rounds more, so the CNT is matched at the next move's speed there. Run on both robots"
            " (approaches, retracts, reversals, acute and obtuse corners, 50 mm zigzags), the FANUC path stays"
            " within about 1 mm of the ABB's or closer to the points; check it where it passes close to"
            " something."
        )
    lines.append("")
    lines += _table(["RAPID speed", "Motion", "TP"], [[s, m, t] for (s, m), t in sorted(result.speeds.items())])
    rows = []
    for (zone, speed, motion, then), use in sorted(result.zones.items()):
        cuts = note = ""
        if use.abb_cut is not None and use.fanuc_cut is not None:
            cuts = f"{use.abb_cut:.1f} / {use.fanuc_cut:.1f}"
            if use.capped:
                note = "CNT100 rounds less: the FANUC path stays closer to the point"
        rows.append([zone, f"{speed}, then {then}" if then else speed, motion, use.tp, cuts, note])
    lines += _table(["RAPID zone", "RAPID speed", "Motion", "TP", "Corner cut ABB / FANUC (mm)", "Note"], rows)
    return lines


def _fixed(value: float, digits: int) -> str:
    """12.5 -> '12.5', 0.0 -> '0', -0.0 -> '0': as few digits as the value needs."""
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _payload_section(result: ConversionResult, config: ConversionConfig) -> list[str]:
    """The load each tool carries: FANUC keeps it in PAYLOAD schedules, apart from the tool frame.

    Nothing converts it into the programs, and a robot running with the wrong payload has its
    collision detection and dynamics wrong, so it is listed here for every tool.
    """
    known, unknown = result.payloads(), result.unknown_payloads()
    listed = {f.rapid_name.upper() for f in known}
    gripped = [s for s in result.grip_payloads if s.load is not None or s.tool.upper() not in listed]
    if not known and not unknown and not gripped:
        return []
    limit = config.limits.get("UTOOL")
    lines = [
        "### Payloads to set up (PAYLOAD)",
        "",
        (
            "Set one payload schedule per tool before running the programs: MENU > SYSTEM > Motion, on the"
            " robot. Unlike the frames, a program cannot do it: the controller holds the payload schedules"
            " read-only for TP programs. Values are converted to the units of that screen: centre of"
            " gravity in cm in the flange frame (RAPID mm / 10), inertia in kgf.cm.s2 (RAPID kg.m2 /"
            f" {KGF_CM_S2:g}). The schedule number is the tool's UTOOL number; a tool holding a part"
            " (GripLoad) has a schedule of its own, which the programs select with PAYLOAD[n] where the"
            " RAPID grips or releases."
        ),
        "",
        (
            "The z coordinate and the mass carry over as they are; x and y depend on the pin hole the tool"
            " is fitted by, like the tool frames above."
        ),
        "",
    ]
    rows = []
    for f in known:
        load = f.frame.load if f.frame else None
        if load is None:  # payloads() only returns tools with a load
            continue
        (cx, cy, cz), (ix, iy, iz) = load.cog, load.inertia
        notes = []
        if tuple(load.aom) != (1, 0, 0, 0):
            notes.append("inertia given about the load's own axes (aom), not the flange's")
        schedule = str(f.number)
        if limit is not None and f.number > limit:
            schedule, notes = "—", [f"UTOOL {f.number}: above the {limit} schedules", *notes]
        rows.append([schedule, f.rapid_name, f"{load.mass:g}", ", ".join(_fixed(c / 10, 3) for c in (cx, cy, cz)),
                     ", ".join(_fixed(i / KGF_CM_S2, 4) for i in (ix, iy, iz)), "; ".join(notes)])  # fmt: skip
    for f in unknown:
        rows.append([str(f.number), f.rapid_name, "—", "—", "—", "tool built at run time: load unknown too"])
    for s in gripped:
        p = s.payload
        notes = [f"GripLoad in {', '.join(sorted({program for program, _ in s.uses}))}"]
        if s.load is not None:
            notes.insert(0, "tool and part together, about their common centre")
        if p.products / KGF_CM_S2 >= 0.00005:
            notes.append(f"products of inertia up to {_fixed(p.products / KGF_CM_S2, 4)} left out")
        name = s.tool if s.load is None else f"{s.tool} + {s.load} (GripLoad)"
        rows.append([str(s.number) if s.number is not None else "—", name, f"{p.mass:g}",
                     ", ".join(_fixed(c / 10, 3) for c in p.cog), ", ".join(_fixed(i / KGF_CM_S2, 4) for i in p.inertia),
                     "; ".join(notes)])  # fmt: skip
    headers = ["PAYLOAD", "RAPID tooldata", "Mass (kg)", "Centre X, Y, Z (cm)", "Inertia X, Y, Z (kgf.cm.s2)", "Note"]
    lines += _table(headers, rows)
    return lines


def _move_routine_section(result: ConversionResult) -> list[str]:
    """Routines of the backup that make one move: how their calls were converted, and what that leaves out."""
    if not result.move_routines:
        return []
    lines = [
        "### Moves made inside routines",
        "",
        (
            "These routines take a point, a speed, a zone and a tool and make one move with them. A routine"
            " that does nothing else is converted as its move. One that also does something else stays TODO"
            " by default, since converting it as the move leaves that out: set it to `true` under"
            " `move_routines` in `crossarm_mapping.json` and convert again to have its calls converted."
        ),
        "",
    ]
    rows = []
    for use in result.move_routines:
        status = "converted" if use.converted else "**TODO**, `move_routines` to convert"
        rows.append([use.name, use.instruction, str(use.calls), status,
                     "nothing" if use.pure else _short(use.also_does, 120)])  # fmt: skip
    lines += _table(["Routine", "Converted as", "Calls", "Calls are", "What else it does (not converted)"], rows)
    return lines


def _inlined_section(result: ConversionResult) -> list[str]:
    """The backup's bool functions that conditions were written from: TP has no function to call."""
    if not result.inlined:
        return []
    lines = [
        "### Functions written as their test",
        "",
        (
            "TP conditions cannot call a function. These bool functions only return a test on inputs or data,"
            " so each condition calling one was written with that test instead, and a remark above it keeps"
            " the RAPID text. A change to one of these functions on the robot has to be made where it is used."
        ),
        "",
    ]
    rows = [[name, str(count)] for name, count in result.inlined.most_common()]
    lines += _table(["RAPID function", "Conditions"], rows)
    return lines


def _setup_section(result: ConversionResult) -> list[str]:
    """The program that sets the frames above on the robot, and the frames it leaves alone."""
    setup = result.setup
    if setup is None or (setup.program is None and not setup.skipped):
        return []
    lines = ["### Setting them on the robot", ""]
    if setup.program is not None:
        tools = sum(1 for kind, _ in setup.written if kind == "UTOOL")
        frames = len(setup.written) - tools
        free = (
            "no program of the target robot uses it"
            if setup.scratch_checked
            else "check that no program of the robot uses it (give its backup to have it checked)"
        )
        computed = (f", and stores the {len(setup.registers)} computed frame(s) below in their position registers"
                    if setup.registers else "")  # fmt: skip
        kept = [f"`{a.name}` (PR[{a.base}] to PR[{a.base + len(a.values) - 1}])" for a in setup.arrays]
        kept += [f"`{a.name}` (R[{a.base}] to R[{a.base + len(a.values) - 1}])" for a in setup.numbers]
        if kept:
            computed += f"; it keeps the arrays the programs index at run time: {', '.join(kept)}"
        lines += [
            (
                f"`{setup.program.name}.LS` sets {tools} tool frame(s) and {frames} user frame(s) with the values"
                f" above{computed}: run it once on the robot, before the converted programs, instead of typing them in."
                " It overwrites those frame numbers, so it starts with a message and a pause: resume to go on."
                f" It uses `PR[{setup.scratch}]` on the way and leaves the last frame value in it: {free}."
            ),
            "",
        ]
    if setup.skipped:
        lines += ["Left out of the program, to set by hand if needed:", ""]
        lines += _table(["Frame", "RAPID data", "Why"],
                        [[f"{kind}[{f.number}]", f.rapid_name, why] for kind, f, why in setup.skipped])  # fmt: skip
    return lines


def _computed_section(result: ConversionResult) -> list[str]:
    """Frames the programs compute from fixed values: where each is kept, and where it is loaded."""
    if not result.computed_frames:
        return []
    lines = [
        "### Frames computed at conversion time",
        "",
        (
            "The programs compute these frames (a tool built from another, a work object copied from another...)"
            " from values that no program changes: CrossArm worked each one out, as TP cannot (no pose product,"
            " inverse or angle function). SETUP_FRAMES stores each distinct value in the position register"
            " below, and the programs load it into the frame where the RAPID computes it (`UTOOL[n]=PR[m]`)."
            " The registers are the free ones after the frame banks, from the top down: pin them with"
            " `frame_registers` in the mapping file. A frame computed from data the programs change, or measured"
            " on the robot, stays TODO."
        ),
        "",
    ]
    rows = []
    for f in result.computed_frames:
        x, y, z, w, p, r = f.values
        frames = sorted({f"{kind} {name}" for kind, name, _, _ in f.uses})
        where = [f"`{program}` l.{line}" for _, _, program, line in f.uses]
        rows.append([
            f"PR[{f.number}]" if f.number is not None else "**none left: TODO**",
            f"{x:.3f}, {y:.3f}, {z:.3f}", f"{w:.3f}, {p:.3f}, {r:.3f}", ", ".join(frames),
            _short(", ".join(where), 120), "mapping file" if f.fixed else "automatic",
        ])  # fmt: skip
    lines += _table(["Register", "X, Y, Z", "W, P, R", "Loaded into", "Where (RAPID line)", "Number"], rows)
    return lines


def _allocation_rows(allocations: list[Allocation], prefix: str) -> list[list[str]]:
    return [
        [f"{prefix}[{a.number}]", a.rapid_name, "mapping file" if a.fixed else "automatic", a.detail]
        for a in allocations
    ]


def _short(text: str, width: int = 90) -> str:
    """One example per row: enough to recognise the case, short enough to keep the table readable."""
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def _coverage_line(result: ConversionResult) -> list[str]:
    coverage = result.coverage
    if not coverage.total:
        return []
    return [f"- **{fmt_percent(coverage.percent)} of the {coverage.total:,} RAPID instructions converted.**"]


def _coverage_section(result: ConversionResult) -> list[str]:
    """Instructions converted, by area: where the conversion is complete, and where the work is."""
    coverage = result.coverage
    if not coverage.total:
        return []
    lines = [
        "### Instructions converted, by area",
        "",
        (
            "Counted per RAPID instruction, comments and declarations left out. Converted: written as TP,"
            " possibly on an assumption listed under the warnings. Not converted: a TODO, alone or inside a"
            " block that is one."
            + (
                f" Includes the {coverage.skipped:,} instructions of the routines not converted (listed under"
                " Programs)."
                if coverage.skipped else ""
            )
        ),
        "",
    ]
    rows = [[s.area, f"{s.total:,}", f"{s.converted:,}", fmt_percent(s.percent)] for s in coverage.shares]
    rows.append(["**All**", f"**{coverage.total:,}**", f"**{coverage.converted:,}**",
                 f"**{fmt_percent(coverage.percent)}**"])  # fmt: skip
    lines += _table(["Area", "Instructions", "Converted", "Share"], rows)
    return lines


def _summary(result: ConversionResult) -> list[str]:
    """What to work on next, before the line-by-line detail.

    A large backup yields hundreds of TODO entries that come down to a handful of
    causes; listing them one by one hides that. This section ranks the causes, so
    the reader sees which job unblocks the most code.
    """
    warnings = sum(1 for x in result.notes if x.kind == "WARNING")
    lines = [
        "## Summary",
        "",
        f"- **{result.clean_programs()} of {len(result.programs)} programs converted with no TODO.**",
        *_coverage_line(result),
        f"- {result.todo_count} TODO (not converted) and {warnings} warnings (converted on an assumption).",
        "",
    ]
    lines += _coverage_section(result)

    for kind, heading, first_column in (
        ("TODO", "### What is blocking, most frequent first", "Blocker"),
        ("WARNING", "### Assumptions to check", "Assumption"),
    ):
        groups = result.grouped(kind)
        if not groups:
            continue
        total = sum(count for _, count, _ in groups)
        lines += [heading, ""]
        lines += _table(
            [first_column, kind, "Share", "Most common case"],
            [
                [category, str(count), f"{count * 100 / total:.0f} %", _short(example)]
                for category, count, example in groups
            ],
        )

    lines += _move_routine_section(result)
    lines += _inlined_section(result)
    if result.capacity:
        lines += [
            "### Controller capacity",
            "",
            (
                "Numbers are allocated automatically from 1 up, with no upper bound. A resource marked"
                " **over** produces `.LS` files a controller with those limits cannot load: pin the numbers"
                " with a mapping file, reuse frames, or raise the limit (`limits`) if the controller has the"
                " option. The default limits are those of a standard controller — check yours."
            ),
            "",
        ]
        taken = any(c.taken for c in result.capacity)
        if taken:
            lines += [
                (
                    "Numbers already used by the programs on the controller (**Taken**) were skipped:"
                    " automatic numbering never lands on them."
                ),
                "",
            ]
        rows = [
            [c.resource, str(c.used), *([str(c.taken)] if taken else []), str(c.highest),
             "—" if c.limit is None else str(c.limit),
             "ok" if c.fits else f"**over by {len(c.over)}:** {_short(', '.join(c.over))}"]
            for c in result.capacity
        ]  # fmt: skip
        headers = ["Resource", "Used", *(["Taken"] if taken else []), "Highest", "Limit", "Status"]
        lines += _table(headers, rows)
    return lines


def build_report(result: ConversionResult, config: ConversionConfig, sources: list[str],
                 licence: "LicenceStatus | None" = None) -> str:  # fmt: skip
    lines = [line for _, part in report_parts(result, config, sources, licence) for line in part]
    return "\n".join(lines).rstrip() + "\n"


def report_parts(result: ConversionResult, config: ConversionConfig, sources: list[str],
                 licence: "LicenceStatus | None" = None) -> list[tuple[str, list[str]]]:  # fmt: skip
    """The report's sections, in order, as Markdown lines: (key, lines).

    Keys: head, summary, programs, frames, registers, motion, points, review. The Markdown report is
    them all; the HTML report (crossarm.convert.html_report) shows some of them its own way."""
    parts: list[tuple[str, list[str]]] = []
    lines = [
        "# CrossArm conversion report",
        "",
        f"- Generated: {config.timestamp:%Y-%m-%d %H:%M:%S} by CrossArm {__version__}",
        f"- Sources: {', '.join(f'`{s}`' for s in sources)}",
        (
            f"- Programs: {len(result.programs)}, items to review: "
            f"{result.todo_count} TODO, {sum(1 for x in result.notes if x.kind == 'WARNING')} warnings"
        ),
        *([f"- Licence: {licence.describe()}"] if licence is not None else []),
        "",
        *([(
            "> **Evaluation copy.** CrossArm is free to evaluate. Using these programs in production — on a robot"
            " doing real work, or delivered to a customer — needs a commercial licence"
            f" ({CONTACT}). Every program carries the same mark in its first lines."
        ), ""] if licence is not None and not licence.licensed else []),
        "> The `.LS` files are text listings to load and check in ROBOGUIDE (or convert on the controller).",
        "> They are **not** directly executable: frames, registers, I/O numbers and every TODO below",
        "> must be reviewed by the integrator before running on a robot.",
        "> The points are the ABB's, as theoretical points: touch them up on the robot. The path between them",
        "> is within 10 mm of the ABB's (measured: within 4 mm, corners included).",
        "",
    ]
    parts += [("head", lines), ("summary", _summary(result))]
    lines = ["## Programs", ""]
    rows = []
    for info in result.programs:
        todo = sum(1 for x in result.notes if x.program == info.program.name and x.kind == "TODO")
        rows.append([
            f"`{info.program.name}.LS`", f"{info.module}.{info.routine}",
            str(len(info.program.lines)), str(len(info.points)), str(todo),
        ])  # fmt: skip
    lines += _table(["TP program", "RAPID routine", "Lines", "Points", "TODO"], rows)
    if result.from_system:
        lines += [
            (
                f"{len(result.from_system)} of these come from system modules, which hold data and utilities rather"
                " than programs: they are written because the programs call them, and a CALL to a program the"
                f" robot does not have fails when it runs. {_short(', '.join(result.from_system), 300)}."
            ),
            "",
        ]

    if result.skipped_routines:
        lines += ["### Routines not converted", ""]
        lines += _table(["RAPID routine", "Reason"], [[f"{m}.{r}", why] for m, r, why in result.skipped_routines])
    parts.append(("programs", lines))

    lines = [
        "## Frames to set up on the controller",
        "",
        "Values are the RAPID frames converted to FANUC X, Y, Z (mm) and W, P, R (deg).",
        "User frames are `uframe x oframe` of the work object, relative to the robot world frame.",
        "",
        "### User frames (UFRAME)",
        "",
    ]
    lines += _table(["UF", "RAPID wobjdata", "X, Y, Z", "W, P, R", "Problem"], _frame_rows(result.uframes))
    lines += ["### Tool frames (UTOOL)", "", _tool_pin_text(config), ""]
    lines += _table(["UT", "RAPID tooldata", "X, Y, Z", "W, P, R", "Problem"], _frame_rows(result.utools))
    lines += _setup_section(result)
    lines += _computed_section(result)
    lines += _payload_section(result, config)
    parts.append(("frames", lines))

    lines = ["## Registers, flags and I/O", ""]
    lines += [
        (
            "Automatic numbers start at 1: pin them with a mapping file (`--map`) to avoid clashing with"
            " registers and I/O already used on the controller."
        ),
        "",
    ]
    if result.wait_clock:
        timer, clock = result.wait_clock
        lines += [
            (
                f"`{timer}` times the waits with a RAPID `MaxTime`, read into `{clock.split(':')[0]}]`: no other"
                " program may use that timer. TP cannot set the time limit of `WAIT ... TIMEOUT` per wait"
                " (`$WAITTMOUT` is write-protected for programs), so each such wait is a short loop on the timer."
            ),
            "",
        ]
    if result.shared_with:
        lines += [
            (
                f"Numbered together with {', '.join(result.shared_with)}: on a FANUC controller registers,"
                " flags and I/O are shared by every program, so the tasks of one backup never get the same"
                " number for different data, and a name used by several tasks keeps one number."
            ),
            "",
        ]
    lines += _table(["TP", "RAPID name", "Number from", "Note"],
                    _allocation_rows(result.registers, "R") + _allocation_rows(result.flags, "F")
                    + _allocation_rows(result.string_registers, "SR")
                    + _allocation_rows(result.digital_outputs, "DO")
                    + _allocation_rows(result.digital_inputs, "DI")
                    + _allocation_rows(result.group_outputs, "GO")
                    + _allocation_rows(result.group_inputs, "GI")
                    + _allocation_rows(result.analog_outputs, "AO")
                    + _allocation_rows(result.timers, "TIMER")
                    + _allocation_rows(result.point_registers, "PR"))  # fmt: skip
    if result.string_registers:
        lines += [
            "",
            "### Texts in string registers",
            "",
            ("Each string the programs change is a string register (SR). A TP line cannot write a text in one,"
             " nor compare one with a text: a text written in the program is loaded by "
             + (f"`CALL {result.text_program}(n,'text',0)`" if result.text_program else "the program loading texts")
             + " (38 characters at a time) into a scratch register taken from the top, just before it is"
             " compared or passed on, and never kept from one instruction to the next. An apostrophe ends a TP"
             " text: it is written as a backquote. TP compares texts regardless of case: a comparison is"
             " converted only when the texts compared cannot differ by case alone. A register only the"
             " statements converted with texts use is numbered from the top down (R[200], R[199]...), so that"
             " the other programs keep the numbers earlier versions gave them."),
        ]
    if result.records:
        lines += [
            "",
            "### Records kept field by field",
            "",
            ("TP has no records: each field the programs change is a register (a bool a flag) named by its"
             " path; a field no program changes is written as its value where it is read."),
            "",
        ]
        lines += _table(["Record", "Registers", "Flags"],
                        [[name, str(r), str(f)] for name, (r, f) in result.records.items()])  # fmt: skip
    parts += [("registers", lines), ("motion", _motion_section(result, config))]

    lines = ["## Points", ""]
    for info in result.programs:
        if not info.points:
            continue
        lines += [f"### {info.program.name}", ""]
        rows = []
        for p in info.points:
            if isinstance(p.value, CartesianPosition):
                v = p.value
                value = f"X {v.x:.3f} Y {v.y:.3f} Z {v.z:.3f} W {v.w:.3f} P {v.p:.3f} R {v.r:.3f}"
            else:
                value = "J " + " ".join(f"{j:.3f}" for j in p.value.joints)
            rows.append([f"P[{p.number}]", f"`{p.source}`", str(p.rapid_line), f"{p.uf}/{p.ut}", value])
        lines += _table(["P", "RAPID target", "RAPID line", "UF/UT", "Value"], rows)
    parts.append(("points", lines))

    lines = ["## Items to review", ""]
    rows = [
        [x.program or "—", str(x.rapid_line) if x.rapid_line else "—", x.kind, x.message]
        for x in sorted(result.notes, key=lambda x: (x.program, x.rapid_line or 0))
    ]
    lines += _table(["Program", "RAPID line", "Kind", "Detail"], rows)
    parts.append(("review", lines))
    return parts
