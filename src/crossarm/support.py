# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""What a user can send when something goes wrong.

Every conversion writes crossarm_log.txt next to its report: the CrossArm version, the
system, what was given and everything the conversion said. An unexpected error in the
desktop window writes crossarm_error.txt with the full traceback, which the window would
otherwise lose after showing a one-line message. Both stay on the user's computer
until they decide to send them.
"""

import os
import platform
import sys
import traceback
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from crossarm import __version__


def environment() -> str:
    """'CrossArm 1.0.0 · Python 3.12.7 · Windows-11-10.0.26200-SP0 · frozen exe'"""
    frozen = " · CrossArm.exe" if getattr(sys, "frozen", False) else ""
    return f"CrossArm {__version__} · Python {platform.python_version()} · {platform.platform()}{frozen}"


def log_text(inputs: Iterable[Path], target: Iterable[Path], lines: Iterable[str]) -> str:
    header = [
        f"CrossArm conversion log — {datetime.now():%Y-%m-%d %H:%M:%S}",
        environment(),
        "input: " + ", ".join(str(p) for p in inputs),
        "target FANUC backup: " + (", ".join(str(p) for p in target) or "none"),
        "",
    ]
    return "\n".join([*header, *lines]) + "\n"


def internal_error(exc: BaseException) -> str:
    """One line naming a CrossArm bug and where in CrossArm it happened, for a report or a log."""
    frames = traceback.extract_tb(exc.__traceback__)
    where = f" (at {Path(frames[-1].filename).name}:{frames[-1].lineno})" if frames else ""
    return f"CrossArm internal error, please report it: {type(exc).__name__}: {exc}{where}"


@dataclass(frozen=True, slots=True)
class InternalError:
    """A CrossArm bug met during a conversion, as `crossarm diagnose` reports it: never the exception's message (it
    may quote the RAPID), only its type and where in CrossArm it happened. `module` and `line` say where in the RAPID,
    for the diagnostic to look at the code around it; they are never written."""

    kind: str  # the exception's type: 'KeyError'
    where: str  # the last frame inside CrossArm: 'convert/translate.py:2400:stmt'
    stage: str  # 'statement' (left TODO), 'module' (module left out), 'file' (file not read)
    module: str = ""
    line: int | None = None


_RECORDED: ContextVar[list[InternalError] | None] = ContextVar("crossarm_internal_errors", default=None)


def crossarm_frame(exc: BaseException) -> str:
    """'convert/translate.py:2400:stmt': the last frame of the traceback inside CrossArm's package, '' if none."""
    package = Path(__file__).resolve().parent
    where = ""
    for frame in traceback.extract_tb(exc.__traceback__):
        path = Path(frame.filename).resolve()
        if path.is_relative_to(package):
            where = f"{path.relative_to(package).as_posix()}:{frame.lineno}:{frame.name}"
    return where


def record_internal(exc: BaseException, stage: str, module: str = "", line: int | None = None) -> None:
    """Note a CrossArm bug the conversion went on after, when a diagnostic is recording (recording_internal)."""
    recorded = _RECORDED.get()
    if recorded is not None:
        recorded.append(InternalError(type(exc).__name__, crossarm_frame(exc), stage, module, line))


@contextmanager
def recording_internal() -> Iterator[list[InternalError]]:
    """The CrossArm bugs met while inside, in the order they were met (in this thread)."""
    recorded: list[InternalError] = []
    token = _RECORDED.set(recorded)
    try:
        yield recorded
    finally:
        _RECORDED.reset(token)


def error_folder() -> Path:
    """Where the window leaves an error report: the user's local application data."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME") or str(Path.home())
    return Path(base) / "CrossArm"


def write_error_report(exc: BaseException, context: dict[str, object], folder: Path | None = None) -> Path:
    """Full traceback and context in crossarm_error.txt; returns its path."""
    folder = folder or error_folder()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "crossarm_error.txt"
    lines = [
        f"CrossArm error report — {datetime.now():%Y-%m-%d %H:%M:%S}",
        environment(),
        *(f"{key}: {value}" for key, value in context.items()),
        "",
        *traceback.format_exception(exc),
    ]
    path.write_text("\n".join(line.rstrip("\n") for line in lines) + "\n", encoding="utf-8")
    return path


__all__ = [
    "InternalError", "crossarm_frame", "environment", "error_folder", "internal_error", "log_text", "record_internal",
    "recording_internal", "write_error_report",
]  # fmt: skip
