# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Command-line interface.

    crossarm parse FILE [--format pseudo|json] [-o OUT]
    crossarm stats PATH [PATH ...]
    crossarm convert BACKUP|FILES [-o OUTDIR] [--map mapping.json] [--routine NAME ...] [--fanuc TARGET]
                     [--tp] [--tp-robot ROBOT] [--keep-taught PATH] [--karel]

`stats` parses every RAPID file under the given paths and reports what the V1
parser recognises versus what it leaves as Unsupported — the tool used to decide
what to support next.
"""

import argparse
import sys
import zipfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

from crossarm import __version__, pipeline
from crossarm.convert import ConversionConfig
from crossarm.fanuc.maketp import TpRequest
from crossarm.rapid import RAPID_SUFFIXES, parse_file
from crossarm.rapid import nodes as n
from crossarm.rapid.to_json import dumps, result_to_data
from crossarm.rapid.to_pseudo import to_pseudo
from crossarm.rapid.walk import module_statements


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):  # Windows consoles default to cp1252
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = _build_parser().parse_args(argv)
    return args.handler(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crossarm", description="Industrial robot program converter (ABB RAPID -> FANUC TP).")
    parser.add_argument("--version", action="version", version=f"CrossArm {__version__}")
    sub = parser.add_subparsers(required=True, metavar="COMMAND")

    p_parse = sub.add_parser("parse", help="parse one RAPID module and print its AST")
    p_parse.add_argument("file", type=Path)
    p_parse.add_argument("--format", choices=("pseudo", "json"), default="pseudo")
    p_parse.add_argument("-o", "--output", type=Path, help="write to a file instead of stdout")
    p_parse.set_defaults(handler=_cmd_parse)

    p_stats = sub.add_parser("stats", help="coverage report over RAPID files or folders")
    p_stats.add_argument("paths", type=Path, nargs="+")
    p_stats.set_defaults(handler=_cmd_stats)

    p_conv = sub.add_parser("convert", help="convert RAPID routines to FANUC .LS programs")
    p_conv.add_argument(
        "paths", type=Path, nargs="+",
        help="ABB backup (folder or .zip), or RAPID files/folders (all modules share their data)",
    )  # fmt: skip
    p_conv.add_argument("-o", "--output", type=Path, help="output folder (default: crossarm_<name> next to the input)")
    p_conv.add_argument("--map", type=Path, help="JSON mapping file (registers, I/O, frames...)")
    p_conv.add_argument(
        "--eio", type=Path,
        help="ABB EIO.cfg giving the signal types; default: found in the given folders or a SYSPAR folder next to them",
    )  # fmt: skip
    p_conv.add_argument(
        "--routine", action="append",
        help="convert only this PROC (repeatable); default: every PROC of non-system modules",
    )  # fmt: skip
    p_conv.add_argument(
        "--fanuc", type=Path, action="append",
        help="the target controller's existing programs (backup folder, .zip or .LS files, repeatable): "
             "the frame, register and I/O numbers they use are left free. Also detected when simply "
             "given among the paths",
    )  # fmt: skip
    p_conv.add_argument(
        "--tp", action="store_true",
        help="also write the programs as binary .TP (folder TP), for a robot without the ASCII Upload option: "
             "made by FANUC MakeTP (maketp.exe, installed with ROBOGUIDE), when it is there",
    )  # fmt: skip
    p_conv.add_argument(
        "--tp-robot", type=Path, metavar="ROBOT",
        help="the robot MakeTP makes the .TP for (implies --tp): a ROBOGUIDE robot folder (...\\Robot_1) "
             "or a robot.ini made by FANUC Setrobot; default: robot.ini in the current folder",
    )  # fmt: skip
    p_conv.add_argument(
        "--keep-taught", type=Path, action="append", metavar="PATH",
        help="keep the positions touched up on the robot: its programs as they are now (folder, .zip, .LS, or .TP "
             "decoded by FANUC PrintTP, installed with ROBOGUIDE; robot as for --tp-robot) and the earlier CrossArm "
             "output folder (its crossarm_points.json, also found next to the --map file); repeatable. A point "
             "touched up there keeps its taught value unless it changed in the backup: then it is theoretical, "
             "listed to touch up again",
    )  # fmt: skip
    p_conv.add_argument(
        "--karel", action="store_true",
        help="write what TP cannot compute (PoseMult of poses computed at run time) as calls to CrossArm's KAREL "
             "programs, in a KAREL folder, compiled by FANUC ktrans (installed with ROBOGUIDE) when it is there, for "
             "the --tp-robot robot's software, else the newest version installed. The robot needs the KAREL option "
             "(R632)",
    )  # fmt: skip
    p_conv.set_defaults(handler=_cmd_convert)
    return parser


def _cmd_parse(args: argparse.Namespace) -> int:
    try:
        result = parse_file(args.file)
    except OSError as exc:
        print(f"CrossArm: cannot read {args.file}: {exc}", file=sys.stderr)
        return 2

    for diag in result.diagnostics:
        print(f"{args.file}:{diag}", file=sys.stderr)

    if args.format == "json":
        output = dumps(result_to_data(result)) + "\n"
    elif result.module is not None:
        output = to_pseudo(result.module)
    else:
        output = ""

    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if result.ok else 1


def iter_rapid_files(paths: list[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(p for p in path.rglob("*") if p.suffix.lower() in RAPID_SUFFIXES)
        else:
            yield path


def _cmd_stats(args: argparse.Namespace) -> int:
    nodes_count: Counter[str] = Counter()
    unsupported: Counter[str] = Counter()
    files = errors = 0
    for path in iter_rapid_files(args.paths):
        files += 1
        result = parse_file(path)
        file_errors = [d for d in result.diagnostics if d.severity.value == "error"]
        errors += len(file_errors)
        routines = len(result.module.routines) if result.module else 0
        print(f"{'OK ' if result.ok else 'ERR'}  {path}  ({routines} routines, {len(file_errors)} errors)")
        for diag in file_errors:
            print(f"       {diag}")
        for stmt in module_statements(result.module):
            nodes_count[type(stmt).__name__] += 1
            if isinstance(stmt, n.Unsupported):
                unsupported[stmt.kind] += 1

    print(f"\n{files} files, {errors} errors")
    print("\nStatements by node type:")
    for name, count in nodes_count.most_common():
        print(f"  {name:<14} {count:>6}")
    if unsupported:
        print("\nUnsupported by kind:")
        for kind, count in unsupported.most_common():
            print(f"  {kind:<18} {count:>6}")
    return 0 if errors == 0 else 1


def _cmd_convert(args: argparse.Namespace) -> int:
    try:
        config = ConversionConfig.from_mapping_file(args.map) if args.map else ConversionConfig()
    except (OSError, ValueError, TypeError) as exc:  # json.JSONDecodeError is a ValueError
        print(f"CrossArm: invalid mapping file {args.map}: {exc}", file=sys.stderr)
        return 2
    if args.karel:
        config = replace(config, karel=True)
    try:
        tp = TpRequest(args.tp_robot) if args.tp or args.tp_robot else None
        keep = pipeline.KeepTaught(args.keep_taught, args.map) if args.keep_taught else None
        output = pipeline.run(args.paths, args.output, config, args.routine, args.eio, fanuc=args.fanuc, tp=tp,
                              keep=keep)  # fmt: skip
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"CrossArm: {exc}", file=sys.stderr)
        return 2
    print(f"{output.programs} programs, {output.todo} TODO: see crossarm_report.html in each folder")
    return 1 if any(task.syntax_errors for task in output.tasks) else 0


if __name__ == "__main__":  # python -m crossarm.cli used to do nothing and exit 0
    raise SystemExit(main())
