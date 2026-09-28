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
from collections.abc import Iterable
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


__all__ = ["environment", "error_folder", "log_text", "write_error_report"]
