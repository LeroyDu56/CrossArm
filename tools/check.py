# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Run the tests, the linter and the corpus check together, and print at most ten lines.

    python tools/check.py           pytest -q, ruff check, corpus_snapshot check (local test corpus)
    python tools/check.py --real    the same, plus the snapshot of local/real_world when it is there
    python tools/check.py --fast    pytest and ruff only

The three run side by side. Each one's full output goes to local/logs/<name>.log (overwritten every
run): read it there when a line says FAIL, rather than running the command again.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "local" / "logs"
MAX_DETAIL = 6  # lines of detail shared by the failing steps


def _ruff() -> list[str]:
    exe = shutil.which("ruff")
    return [exe] if exe else [sys.executable, "-m", "ruff"]


def _steps(args: list[str]) -> dict[str, list[str]]:
    steps = {
        "pytest": [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        "ruff": [*_ruff(), "check", "."],
    }
    if "--fast" not in args:
        steps["snapshot"] = [sys.executable, "tools/corpus_snapshot.py", "check"]
        real = ROOT / "local" / "real_world"
        if "--real" in args and real.is_dir():
            steps["real"] = [sys.executable, "tools/corpus_snapshot.py", "check", str(real),
                             str(ROOT / "local" / "real_world_snapshot.json")]  # fmt: skip
    return steps


def _summary(name: str, code: int, text: str) -> tuple[str, list[str]]:
    """(one-line verdict, detail lines worth showing)."""
    lines = [line for line in text.splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    if name == "pytest":
        tail = next((line.strip("= ") for line in reversed(lines) if re.search(r"\d+ (passed|failed|error)", line)), last)
        return tail, [line for line in lines if line.startswith(("FAILED ", "ERROR "))]
    if name == "ruff":
        if code == 0:
            return "clean", []
        found = next((line for line in lines if line.startswith("Found ")), last)
        rules = [line for line in lines if re.match(r"[A-Z]+\d+ ", line)]
        where = [line.split("--> ", 1)[1] for line in lines if "--> " in line]
        return found, [f"{w}: {r}" for w, r in zip(where, rules, strict=False)] or rules
    # corpus snapshots: "no change", or one line per change after the per-backup coverage lines
    if code == 0 and last == "no change":
        return "no change", []
    if "no backup found" in text or "run 'save' first" in text:
        return "skipped: " + last, []
    changes = [line for line in lines if not re.search(r"TODO, [\d.]+ % of \d+ instructions$", line)]
    return f"{len(changes)} change(s)", changes


def main(args: list[str]) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    start = time.monotonic()
    running = {}
    for name, command in _steps(args).items():
        log = (LOGS / f"{name}.log").open("w", encoding="utf-8")
        running[name] = (subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env), log)
    failed, details = 0, []
    for name, (process, log) in running.items():
        code = process.wait()
        log.close()
        text = (LOGS / f"{name}.log").read_text(encoding="utf-8", errors="replace")
        verdict, detail = _summary(name, code, text)
        bad = code != 0 and not verdict.startswith("skipped")
        failed += bad
        print(f"{name:9s} {'FAIL' if bad else 'ok  '}  {verdict[:100]}")
        details += [f"  {name}: {line[:110]}" for line in detail] if bad else []
    for line in details[:MAX_DETAIL]:
        print(line)
    if len(details) > MAX_DETAIL:
        print(f"  (+{len(details) - MAX_DETAIL} more)")
    print(f"{time.monotonic() - start:.0f} s; full output in local/logs/" if failed else f"all ok in {time.monotonic() - start:.0f} s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
