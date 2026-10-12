# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Entry point of the desktop application (CrossArm.exe).

    CrossArm.exe                      opens the window
    CrossArm.exe <backup or files>    what Windows passes when items are dropped on the icon:
                                     the window opens and converts them right away
    CrossArm.exe convert|parse|stats ...,  CrossArm.exe --help | --version
                                     the `crossarm` command line, without a window: same commands,
                                     options, output and exit codes (0 ok, 1 syntax errors, 2 usage)

The exe is built windowed (no console of its own): on the command line it attaches to the console
it was started from, so its output shows there. cmd.exe waits for it in a script (.bat); typed at
the prompt, `start /wait CrossArm.exe convert ...` waits for it and sets %ERRORLEVEL%.

CROSSARM_NO_GUI=1 runs the dropped-files conversion without a window (used to smoke-test the exe).
"""

import os
import sys
from pathlib import Path

# First arguments that select the command line rather than files dropped on the icon.
CLI_COMMANDS = frozenset({"convert", "parse", "stats"})


def is_command_line(args: list[str]) -> bool:
    return bool(args) and (args[0] in CLI_COMMANDS or args[0].startswith("-"))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if is_command_line(args):
        return _run_command_line(args)

    paths = [Path(p) for p in args]
    if os.environ.get("CROSSARM_NO_GUI") == "1":
        from crossarm import pipeline
        from crossarm.gui import close_splash

        close_splash()  # no window will replace it
        result = pipeline.run(paths)
        print(f"{result.programs} programs, {result.todo} TODO -> {result.folder}")
        return 0

    from crossarm.gui import launch

    launch(paths)
    return 0


def _run_command_line(args: list[str]) -> int:
    from crossarm.cli import main as cli_main

    _close_splash()  # no window will replace it (crossarm.gui is not imported: no Tk needed)
    _attach_console()
    try:
        return cli_main(args)
    except SystemExit as stop:  # --help, --version, usage errors: argparse exits
        code = stop.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return 1
    finally:
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.flush()
            except (AttributeError, OSError, ValueError):
                pass


def _attach_console() -> None:
    """Give a windowed exe the console it was started from (or a sink when there is none).

    A windowed (GUI subsystem) program starts with no standard streams unless they were redirected
    (`CrossArm.exe convert x > log.txt`): Python then sets sys.stdout/sys.stderr to None. Those
    left as None are reopened on the parent console, if any, else on os.devnull so that printing
    never fails.
    """
    missing = [name for name in ("stdout", "stderr") if getattr(sys, name) is None]
    if not missing:
        return
    attached = sys.platform == "win32" and _attach_parent_console()
    for name in missing:
        try:
            stream = open("CONOUT$" if attached else os.devnull, "w", encoding="utf-8", errors="replace")  # noqa: SIM115
        except OSError:
            stream = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
        setattr(sys, name, stream)
    if attached and "stdout" in missing:
        print()  # an interactive shell does not wait for a windowed program: its prompt is already there


def _attach_parent_console() -> bool:
    import ctypes

    attach_parent_process = -1
    return bool(ctypes.windll.kernel32.AttachConsole(attach_parent_process))


def _close_splash() -> None:
    try:
        import pyi_splash  # type: ignore[import-not-found]
    except ImportError:
        return
    pyi_splash.close()


if __name__ == "__main__":
    raise SystemExit(main())
