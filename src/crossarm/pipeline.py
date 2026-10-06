# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Complete conversion of what the user drops, shared by the CLI and the desktop app.

    input (backup folder / .zip / files) -> Source -> one conversion per task -> output folder

The target FANUC controller's own programs can be given too (--fanuc, or simply
dropped alongside the ABB backup): they are not converted, only read for the numbers
they already use, which the conversion then leaves free.

Output layout, created next to the input unless an output folder is given:

    crossarm_<name>/
      <task>/                   one folder per task of a backup (T_ROB1, T_ROB2...)
        *.LS
        crossarm_report.md / .html
      TP/                       when asked: the .TP of every task, made by FANUC MakeTP (fanuc/maketp.py)
"""

import os
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from crossarm.backup import Source, TaskSource, open_source
from crossarm.convert import ConversionConfig, ConversionResult, build_mapping, build_report, convert
from crossarm.convert.compute import Written
from crossarm.convert.coverage import Coverage, fmt_percent
from crossarm.convert.html_report import build_html_report
from crossarm.convert.motion import M20ID_25, profile_for
from crossarm.convert.setup import SETUP_NAME, SETUP_NAME_SHORT, build_setup
from crossarm.convert.translate import ControllerScope, remark_lines
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.maketp import FOLDER as TP_FOLDER
from crossarm.fanuc.maketp import TpExport, TpRequest, make_tp, report_section
from crossarm.fanuc.tp import Instruction, Program
from crossarm.fanuc.usage import RESOURCES, ControllerUsage, is_fanuc_input, read_controller
from crossarm.licence import LicenceStatus
from crossarm.licence import current as current_licence
from crossarm.rapid import ParseResult, parse_file
from crossarm.rapid.eio import find_eio, read_eio
from crossarm.support import log_text

Log = Callable[[str], None]


@dataclass
class TaskOutput:
    task: str
    folder: Path
    programs: int = 0
    todo: int = 0
    warnings: int = 0
    syntax_errors: list[str] = field(default_factory=list)
    report_html: Path | None = None
    result: ConversionResult | None = None  # the full detail, for a summary on screen
    tp: TpExport | None = None  # the .TP files, when asked for


@dataclass
class Inspection:
    """What CrossArm understood from the user's input, before converting anything."""

    name: str
    kind: str  # "backup" | "files"
    tasks: list[tuple[str, int]]  # robot task, number of RAPID modules
    eio_signals: int | None  # signals typed by EIO.cfg; None: no EIO.cfg found
    fanuc: list[Path]  # FANUC programs given among the paths (read, not converted)

    @property
    def modules(self) -> int:
        return sum(count for _, count in self.tasks)


def split_fanuc(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    """(RAPID inputs, FANUC inputs): FANUC programs dropped with the ABB backup are set aside,
    or the backup would be taken for a pile of loose files."""
    fanuc = [Path(p) for p in paths if is_fanuc_input(Path(p))]
    return [Path(p) for p in paths if Path(p) not in fanuc], fanuc


def inspect(paths: list[Path], eio: Path | None = None) -> Inspection:
    """Look at the input without converting it: the window shows this as soon as the user picks it."""
    rapid, fanuc = split_fanuc(paths)
    if not rapid:
        raise ValueError("only FANUC programs were given: add the ABB backup or RAPID files to convert")
    with open_source(rapid) as source:
        tasks = [(task.name, len(task.files)) for task in source.tasks if task.files]
        if not tasks:
            raise ValueError("no RAPID module found (.mod, .modx, .sys, .sysx, .prg)")
        eio_path = eio or source.eio or (find_eio(rapid) if source.kind == "files" else None)
        signals = len(read_eio(eio_path)) if eio_path else None
        return Inspection(source.name, source.kind, tasks, signals, fanuc)


@dataclass
class RunOutput:
    source_name: str
    kind: str
    folder: Path
    tasks: list[TaskOutput]
    eio: Path | None
    controller: ControllerUsage | None = None  # the target controller's programs, when given
    licence: LicenceStatus | None = None  # the licence the conversion ran under
    config: ConversionConfig | None = None  # as the conversion ran: speeds and zones chosen for the robot

    @property
    def programs(self) -> int:
        return sum(t.programs for t in self.tasks)

    @property
    def todo(self) -> int:
        return sum(t.todo for t in self.tasks)

    @property
    def coverage(self) -> Coverage:
        """Instructions converted, every task of the backup counted together."""
        return sum((t.result.coverage for t in self.tasks if t.result), Coverage(()))


def unique_folder(base: Path) -> Path:
    """base, or base_2, base_3... : never write into a previous run's output."""
    candidate, n = base, 1
    while candidate.exists():
        n += 1
        candidate = base.with_name(f"{base.name}_{n}")
    return candidate


def _setup_name(config: ConversionConfig, taken: set[str]) -> str:
    """SETUP_FRAMES, or SETFRAME on controllers with 8-character names; suffixed if the name is taken."""
    max_len = config.program_name_max_length
    base = SETUP_NAME if max_len >= len(SETUP_NAME) else SETUP_NAME_SHORT
    name, n = base, 1
    while name in taken:
        n += 1
        name = f"{base[: max_len - len(str(n)) - 1]}_{n}"
    return name


def _marked(program: Program, licence: LicenceStatus) -> Program:
    """The program with the licence mark as its first lines: an evaluation copy says so where it is used.

    Not a condition program: it holds WHEN lines only, a remark in one is refused (ROBOGUIDE, ASBN-092).
    The TRAP it calls carries the mark."""
    if program.condition:
        return program
    return replace(program, lines=[*map(Instruction, _mark(licence)), *program.lines])


def _mark(licence: LicenceStatus) -> list[str]:
    """The remark lines of the licence mark, as written first in each program."""
    return [text for line in licence.remarks() for text in remark_lines(line)]


def _parse_task(task: TaskSource) -> tuple[list[ParseResult], list[str]]:
    """The task's modules as parsed, and its syntax errors."""
    parsed: list[ParseResult] = []
    errors: list[str] = []
    for path in task.files:
        parsed_file = parse_file(path)
        if parsed_file.module is None:
            errors.append(f"{path.name}: not a RAPID module ({parsed_file.diagnostics[0].message})")
            continue
        errors += [f"{path.name}:{d}" for d in parsed_file.diagnostics if d.severity.value == "error"]
        parsed.append(parsed_file)
    return parsed, errors


def _convert_task(task: TaskSource, parsed_task: tuple[list[ParseResult], list[str]], folder: Path,
                  config: ConversionConfig, signals, routines, source: Source, log: Log, numbers: ControllerScope,
                  other_tasks: list[str], licence: LicenceStatus,
                  tp: tuple[TpRequest, Path] | None = None) -> TaskOutput:  # fmt: skip
    out = TaskOutput(task.name, folder)
    parsed, out.syntax_errors = parsed_task
    modules = [p.module for p in parsed if p.module is not None]
    program_names = {m.name.upper() for p, m in zip(parsed, modules, strict=True) if Path(p.path) in set(task.program_files)}

    result = convert(
        modules, config, routines,
        sources={m.name: p.text for p, m in zip(parsed, modules, strict=True)}, signals=signals,
        program_modules=program_names if source.kind == "backup" else None, shared=numbers,
    )  # fmt: skip
    result.shared_with = other_tasks
    folder.mkdir(parents=True, exist_ok=True)
    for info in result.programs:
        (folder / f"{info.program.name}.LS").write_text(write_ls(_marked(info.program, licence)), encoding="ascii",
                                                        newline="")  # fmt: skip
    # The frames, ready to set on the robot: one program instead of every value typed on the pendant.
    result.setup = build_setup(result, config, _setup_name(config, numbers.program_names))
    if result.setup.program is not None:
        numbers.program_names.add(result.setup.program.name)
        (folder / f"{result.setup.program.name}.LS").write_text(write_ls(_marked(result.setup.program, licence)),
                                                             encoding="ascii", newline="")  # fmt: skip
    if tp is not None:  # binary copies of the programs just written, for a robot that cannot load .LS
        written = [info.program.name for info in result.programs]
        if result.setup.program is not None:
            written.append(result.setup.program.name)
        out.tp = make_tp([folder / f"{name}.LS" for name in written], tp[1], tp[0], log)
    names = [Path(p.path).name for p in parsed]
    extra = ""  # what this run adds to the report
    if out.tp is not None:
        extra += report_section(out.tp, os.path.relpath(tp[1], folder) if tp else "")
    if out.syntax_errors:
        extra += "\n## Syntax errors (statements skipped by the parser)\n\n"
        extra += "\n".join(f"- `{e}`" for e in out.syntax_errors) + "\n"
    (folder / "crossarm_report.md").write_text(build_report(result, config, names, licence) + extra, encoding="utf-8")
    out.report_html = folder / "crossarm_report.html"
    page = build_html_report(result, config, names, licence, title=f"CrossArm - {source.name} - {task.name}",
                             extra=extra, lead=_mark(licence), tp=out.tp,
                             tp_where=os.path.relpath(tp[1], folder) if tp else "")  # fmt: skip
    out.report_html.write_text(page, encoding="utf-8")
    # The numbering this run used, ready to edit and feed back with --map.
    (folder / "crossarm_mapping.json").write_text(build_mapping(result, config), encoding="utf-8")

    out.result = result
    out.programs = len(result.programs)
    out.todo = result.todo_count
    out.warnings = sum(1 for n in result.notes if n.kind == "WARNING")
    log(f"  {task.name}: {out.programs} programs, {out.todo} TODO, {out.warnings} warnings"
        + (f", {len(out.syntax_errors)} syntax errors" if out.syntax_errors else "")
        + (f", {fmt_percent(result.coverage.percent)} of {result.coverage.total} instructions converted"
           if result.coverage.total else ""))  # fmt: skip
    if out.tp is not None:
        log(f"  {task.name}: {out.tp.summary()}")
    return out


def run(
    paths: list[Path],
    output: Path | None = None,
    config: ConversionConfig | None = None,
    routines: list[str] | None = None,
    eio: Path | None = None,
    log: Log = print,
    fanuc: list[Path] | None = None,
    tp: TpRequest | None = None,
) -> RunOutput:
    """Convert; with `tp`, also write the programs as .TP with FANUC MakeTP (fanuc/maketp.py), in TP/."""
    given, lines = list(paths), []
    user_log = log

    def log(line: str) -> None:  # also kept for crossarm_log.txt
        lines.append(line)
        user_log(line)

    config = config or ConversionConfig()
    licence = current_licence()
    log(licence.describe())
    paths, detected = split_fanuc(paths)
    fanuc = [*(fanuc or []), *detected]
    if not paths:
        raise ValueError("only FANUC programs were given: add the ABB backup or RAPID files to convert")
    controller = None
    if fanuc:
        controller = read_controller(fanuc)
        log(f"Existing FANUC programs: {len(controller.programs)} read"
            + (f", {len(controller.skipped)} other files ignored" if controller.skipped else ""))  # fmt: skip
        log(f"  numbers already in use, left free: {controller.summary()}")
        reserved = {resource: dict(numbers) for resource, numbers in config.reserved.items()}
        for resource, numbers in controller.reserved().items():
            reserved.setdefault(resource, {}).update(numbers)
        for resource in RESOURCES:  # read, even if unused: 'no PR in use' is known, not unknown
            reserved.setdefault(resource, {})
        config = replace(config, reserved=reserved)
        if controller.robot:
            log(f"  robot: {controller.robot}")
            config = replace(config, target_robot=controller.robot)
            untouched = config.motion_profile is M20ID_25 and config.joint_speed_ref_mm_s == M20ID_25.joint_speed_ref_mm_s
            if untouched and not config.motion_profile_source:  # nothing given in the mapping file
                profile, how = profile_for(controller.robot)
                if how:
                    config = replace(config, motion_profile=profile, joint_speed_ref_mm_s=profile.joint_speed_ref_mm_s,
                                     motion_profile_source=how)  # fmt: skip
                log(f"  speeds and zones: {how or 'no profile measured on its series, the M-20iD/25 one is used'}")

    with open_source(paths) as source:
        if not any(task.files for task in source.tasks):
            raise ValueError("no RAPID module found (.mod, .modx, .sys, .sysx, .prg)")
        location = source.location or Path.cwd()
        folder = output or unique_folder(location / f"crossarm_{source.name}")
        eio_path = eio or source.eio or (find_eio([Path(p) for p in paths]) if source.kind == "files" else None)
        signals = read_eio(eio_path) if eio_path else None

        what = "ABB backup" if source.kind == "backup" else "RAPID files"
        log(f"{what} '{source.name}': {len(source.tasks)} task(s)")
        if source.kind == "files" and len(source.tasks) > 1:
            log("  modules of the same name in several folders: each folder converted as a task of its own")
        if eio_path:
            log(f"I/O signal types from {eio_path.name} ({len(signals or {})} signals)")
        # One controller: its registers, flags and I/O are shared by every task converted here.
        shared = ControllerScope.from_config(config, controller.programs if controller else ())
        names = [task.name for task in source.tasks if task.files]
        parsed = [_parse_task(task) for task in source.tasks]
        # A PERS is shared by the tasks: what one task changes, a frame another computes from is not fixed.
        shared.written = Written.of(p.module for modules, _ in parsed for p in modules if p.module is not None)
        tasks = []
        if tp is not None:
            log("Binary .TP programs: made by FANUC MakeTP, which loads each program into the robot's virtual "
                "controller (a cell open in ROBOGUIDE loses its programs of the same names)")  # fmt: skip
        for task, parsed_task in zip(source.tasks, parsed, strict=True):
            task_folder = folder / task.name if source.kind == "backup" or len(source.tasks) > 1 else folder
            others = [name for name in names if name != task.name]
            tasks.append(_convert_task(task, parsed_task, task_folder, config, signals, routines, source, log, shared,
                                       others, licence, (tp, folder / TP_FOLDER) if tp else None))  # fmt: skip
        log(f"Output: {folder}")
        # What a user can send when a result looks wrong: stays next to the report.
        (folder / "crossarm_log.txt").write_text(log_text(given, fanuc, lines), encoding="utf-8")
        return RunOutput(source.name, source.kind, folder, tasks, eio_path, controller, licence, config)
