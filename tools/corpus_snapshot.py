# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Non-regression over a local test corpus: what each conversion gives, saved, then compared.

The corpus is not in the repository, and neither is what it converts to. This keeps a snapshot of
each conversion outside it (in /local/, which git ignores): TODO, warnings and coverage by area for every task, and a fingerprint of every program
written. After a change, `check` converts again and says what moved: a coverage going down, a TODO
count going up (in all, and for each cause), a syntax error more, a program whose text changed. A change can be intended;
the point is to see it.

Each backup is converted twice: as is, and with every move routine accepted (the choice the window
offers after a conversion), as both are what a user gets.

Usage:
    python tools/corpus_snapshot.py save   [corpus] [snapshot]
    python tools/corpus_snapshot.py check  [corpus] [snapshot]

corpus: a backup folder, or a folder of them (default $CROSSARM_RAPID_CORPUS, else ./abb). A folder
of RAPID modules that is not a backup (no RAPID/ folder: the modules of a project, loose) counts as
one source too; folders whose name starts with '_' or '.' are left out (scripts, notes).
snapshot: default local/corpus_snapshot.json (keep one snapshot per corpus).
"""

import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from dataclasses import replace
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm import pipeline
from crossarm.convert import ConversionConfig
from crossarm.rapid import RAPID_SUFFIXES

ROOT = Path(__file__).resolve().parents[1]
MODES = ("as is", "moves accepted")
STAMP = datetime(2026, 1, 1)  # the date written in each program: fixed, or every program would differ


def _source(folder: Path) -> bool:
    """A backup, or a folder holding RAPID modules anywhere below it."""
    if folder.name.startswith(("_", ".")):
        return False
    return (folder / "RAPID").is_dir() or any(p.suffix.lower() in RAPID_SUFFIXES for p in folder.rglob("*"))


def backups(corpus: Path) -> list[Path]:
    """The corpus itself if it is a backup, else every backup or folder of modules directly under it."""
    if (corpus / "RAPID").is_dir():
        return [corpus]
    return sorted(p for p in corpus.iterdir() if p.is_dir() and _source(p))


def convert(backup: Path, mode: str, out: Path) -> dict:
    config = ConversionConfig(timestamp=STAMP)
    if mode == "moves accepted":
        first = pipeline.run([backup], output=out / "first", config=config, log=lambda _: None)
        names = {u.name.upper(): True for t in first.tasks if t.result for u in t.result.move_routines}
        config = replace(config, move_routines=names)
    run = pipeline.run([backup], output=out / "run", config=config, log=lambda _: None)
    tasks = {}
    for task in run.tasks:
        result = task.result
        if result is None:
            continue
        programs = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()[:16] for path in sorted(task.folder.glob("*.LS"))
        }  # fmt: skip
        tasks[task.task] = {
            "programs": len(result.programs),
            "syntax_errors": len(task.syntax_errors),
            "todo": result.todo_count,
            "warnings": sum(1 for n in result.notes if n.kind == "WARNING"),
            "causes": dict(sorted(Counter(n.category for n in result.notes if n.kind == "TODO").items())),
            "coverage": result.coverage.percent,
            "instructions": result.coverage.total,
            "areas": {s.area: [s.converted, s.total] for s in result.coverage.shares},
            "files": programs,
        }
    return tasks


def snapshot(corpus: Path) -> dict:
    out: dict = {}
    for backup in backups(corpus):
        key = backup.relative_to(corpus).as_posix() if backup != corpus else "."
        for mode in MODES:
            with tempfile.TemporaryDirectory() as tmp:
                out.setdefault(key, {})[mode] = convert(backup, mode, Path(tmp))
            tasks = out[key][mode].values()
            total = sum(t["instructions"] for t in tasks)
            converted = sum(v[0] for t in tasks for v in t["areas"].values())
            print(f"{key} [{mode}]: {sum(t['todo'] for t in tasks)} TODO, "
                  f"{converted * 100 / total if total else 100:.1f} % of {total} instructions")  # fmt: skip
    return out


def compare(old: dict, new: dict) -> list[str]:
    changes = []
    for key in sorted(set(old) | set(new)):
        for mode in MODES:
            before, after = old.get(key, {}).get(mode, {}), new.get(key, {}).get(mode, {})
            for task in sorted(set(before) | set(after)):
                where = f"{key} [{mode}] {task}"
                a, b = before.get(task), after.get(task)
                if a is None or b is None:
                    changes.append(f"{where}: task {'added' if a is None else 'gone'}")
                    continue
                for field in ("coverage", "todo", "warnings", "programs"):
                    if a[field] != b[field]:
                        changes.append(f"{where}: {field} {a[field]} -> {b[field]}")
                for field in ("syntax_errors",):  # snapshots saved before it was kept have none
                    if field in a and a[field] != b[field]:
                        changes.append(f"{where}: {field} {a[field]} -> {b[field]}")
                if "causes" in a:  # snapshots saved before causes were kept have none
                    for cause in sorted(set(a["causes"]) | set(b["causes"])):
                        x, y = a["causes"].get(cause, 0), b["causes"].get(cause, 0)
                        if x != y:
                            changes.append(f"{where}: TODO '{cause}' {x} -> {y}")
                for area in sorted(set(a["areas"]) | set(b["areas"])):
                    x, y = a["areas"].get(area, [0, 0]), b["areas"].get(area, [0, 0])
                    if x != y:
                        changes.append(f"{where}: {area} {x[0]}/{x[1]} -> {y[0]}/{y[1]}")
                files_a, files_b = a["files"], b["files"]
                changed = sorted(f for f in set(files_a) & set(files_b) if files_a[f] != files_b[f])
                for label, names in (("new", sorted(set(files_b) - set(files_a))),
                                     ("gone", sorted(set(files_a) - set(files_b))), ("changed", changed)):  # fmt: skip
                    if names:
                        shown = ", ".join(names[:8]) + (f" (+{len(names) - 8})" if len(names) > 8 else "")
                        changes.append(f"{where}: {len(names)} program(s) {label}: {shown}")
    return changes


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("save", "check"):
        print(__doc__)
        return 2
    corpus = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(os.environ.get("CROSSARM_RAPID_CORPUS", ROOT / "abb"))
    path = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "local" / "corpus_snapshot.json"
    if not corpus.is_dir() or not backups(corpus):
        print(f"no backup found in {corpus}")
        return 2
    current = snapshot(corpus)
    if sys.argv[1] == "save":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=1, sort_keys=True), encoding="utf-8")
        print(f"snapshot saved: {path}")
        return 0
    if not path.exists():
        print(f"no snapshot at {path}: run 'save' first")
        return 2
    changes = compare(json.loads(path.read_text(encoding="utf-8")), current)
    print("\n".join(changes) if changes else "no change")
    return 1 if changes else 0


if __name__ == "__main__":
    sys.exit(main())
