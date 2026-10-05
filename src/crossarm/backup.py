# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Find what to convert in what the user drops: an ABB backup folder, a zipped backup,
or loose RAPID files.

ABB backup layout (RobotWare 6 and 7):

    <backup>/
      BACKINFO/backinfo.txt      '>>TASK2: (T_ROB1,,)' maps folders to task names
      RAPID/TASK<n>/PROGMOD/     program modules  -> converted
      RAPID/TASK<n>/SYSMOD/      system modules   -> data only (tools, frames, targets)
      SYSPAR/EIO.cfg             I/O signal types
      HOME/, License/, *.bin...  ignored

Each task is converted on its own: in a multi-robot cell every task has its own
program, data and name space.

Loose files are one task, unless modules of the same name come from several folders: a
project holding a folder per robot task, or several versions of its program side by side.
RAPID loads one module of a name per task, so each folder is then a task of its own
(modules directly in the folder above go into each of them), rather than programs of the
same name written over one another.
"""

import os
import re
import shutil
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from crossarm.rapid import RAPID_SUFFIXES

_BACKINFO_TASK = re.compile(r"^>>(TASK\d+):\s*\(([^,)]*)")
_MODULE = re.compile(r"^\s*MODULE\s+(\w+)", re.IGNORECASE | re.MULTILINE)


@dataclass
class TaskSource:
    name: str  # controller task name (T_ROB1) or folder name
    program_files: list[Path] = field(default_factory=list)  # routines converted
    data_files: list[Path] = field(default_factory=list)  # data only

    @property
    def files(self) -> list[Path]:
        return self.data_files + self.program_files


@dataclass
class Source:
    name: str  # used for the output folder: crossarm_<name>
    kind: str  # "backup" | "files"
    tasks: list[TaskSource]
    eio: Path | None = None
    location: Path | None = None  # where the user's input lives (output goes next to it)


def is_rapid_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in RAPID_SUFFIXES


def find_backup_root(folder: Path) -> Path | None:
    """The folder holding RAPID/TASK*: the given one, or one below it (zip with a top folder)."""
    for candidate in (folder, *sorted(p.parent for p in folder.rglob("RAPID") if p.is_dir())):
        rapid = candidate / "RAPID"
        if rapid.is_dir() and any(p.is_dir() and p.name.upper().startswith("TASK") for p in rapid.iterdir()):
            return candidate
    return None


def task_names(root: Path) -> dict[str, str]:
    """TASK folder -> controller task name, from BACKINFO/backinfo.txt."""
    info = root / "BACKINFO" / "backinfo.txt"
    names: dict[str, str] = {}
    if info.is_file():
        for line in info.read_text(encoding="utf-8", errors="replace").splitlines():
            match = _BACKINFO_TASK.match(line.strip())
            if match and match[2].strip():
                names[match[1].upper()] = match[2].strip()
    return names


def read_backup(root: Path) -> Source:
    names = task_names(root)
    tasks = []
    for folder in sorted(p for p in (root / "RAPID").iterdir() if p.is_dir() and p.name.upper().startswith("TASK")):
        task = TaskSource(names.get(folder.name.upper(), folder.name))
        for path in sorted(folder.rglob("*")):
            if not is_rapid_file(path):
                continue
            is_system = "SYSMOD" in (part.upper() for part in path.relative_to(folder).parts[:-1])
            (task.data_files if is_system else task.program_files).append(path)
        if task.files:
            tasks.append(task)
    eio = root / "SYSPAR" / "EIO.cfg"
    return Source(root.name, "backup", tasks, eio if eio.is_file() else None, root.parent)


def module_name(path: Path) -> str:
    """The name a module file declares (its file name when it declares none), upper case."""
    try:
        found = _MODULE.search(path.read_bytes()[:65536].decode("utf-8", errors="replace"))
    except OSError:
        found = None
    return (found[1] if found else path.stem).upper()


def _split(files: list[Path], folder: Path) -> list[tuple[Path, list[Path]]]:
    """(folder, its modules) for each task: the files under `folder` as one task, unless two subfolders hold a
    module of the same name: then one task (at least) per subfolder, the modules directly in `folder` in each."""
    names = [module_name(f) for f in files]
    if len(set(names)) == len(names):
        return [(folder, files)]
    below: dict[Path, list[Path]] = {}
    where: dict[str, set[Path]] = {}
    for f, name in zip(files, names, strict=True):
        if f.parent != folder:
            sub = folder / f.relative_to(folder).parts[0]
            below.setdefault(sub, []).append(f)
            where.setdefault(name, set()).add(sub)
    if len(below) == 1 and sum(map(len, below.values())) == len(files):  # all in one subfolder (Rapid/): look in it
        [(sub, own)] = below.items()
        return _split(own, sub)
    if all(len(subs) == 1 for subs in where.values()):  # a name twice in one folder: RAPID refuses it there
        return [(folder, files)]
    shared = [f for f in files if f.parent == folder]
    tasks = []
    for sub, own in sorted(below.items()):
        for task_folder, task_files in _split(own, sub):
            mine = {module_name(f) for f in task_files}
            tasks.append((task_folder, sorted([f for f in shared if module_name(f) not in mine] + task_files)))
    return tasks


def read_files(paths: list[Path]) -> Source:
    """Loose files and folders that are not a backup: every module is a program. One task, or one per folder
    when modules of the same name come from several folders, named after its path.

    The modules are read in path order, whatever order they were given in: where two declare a routine of
    the same name, the one converted (the first read) does not depend on how the files were picked."""
    files: list[Path] = []
    for path in paths:
        files += [p for p in path.rglob("*") if is_rapid_file(p)] if path.is_dir() else [path]
    files = sorted({f for f in files if is_rapid_file(f)})
    first = paths[0]
    name = first.stem if len(paths) == 1 else (first.parent.name or "rapid")
    eio = next((p for p in paths if p.name.lower() == "eio.cfg"), None)
    try:
        top = Path(os.path.commonpath([f.parent for f in files])) if files else first.parent
    except ValueError:  # on several drives: nothing in common to split by
        top = None
    groups = _split(files, top) if top is not None else [(first.parent, files)]
    if len(groups) == 1:
        tasks = [TaskSource("files", program_files=files)]
    else:
        parts = [folder.relative_to(top).parts for folder, _ in groups]
        common = 0
        while all(len(p) > common + 1 and p[common] == parts[0][common] for p in parts):
            common += 1  # what every task folder starts with names none of them
        tasks = [TaskSource("/".join(p[common:]) or "files", program_files=own)
                 for p, (_, own) in zip(parts, groups, strict=True)]  # fmt: skip
    return Source(name, "files", tasks, eio, first.parent)


def _safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    """Extract, refusing entries that would land outside the target (zip slip)."""
    root = target.resolve()
    for member in archive.infolist():
        destination = (target / member.filename).resolve()
        if not destination.is_relative_to(root):
            raise ValueError(f"unsafe path in archive: {member.filename}")
    archive.extractall(target)


@contextmanager
def open_source(paths: list[Path]) -> Iterator[Source]:
    """Resolve the user's input. Zip files are extracted to a temporary folder for the duration."""
    paths = [Path(p).resolve() for p in paths]  # absolute: shown to the user, opened in Explorer
    if not paths:
        raise ValueError("nothing to convert")
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"not found: {missing[0]}")

    if len(paths) == 1 and paths[0].suffix.lower() == ".zip":
        temp = Path(tempfile.mkdtemp(prefix="crossarm_"))
        try:
            with zipfile.ZipFile(paths[0]) as archive:
                _safe_extract(archive, temp)
            root = find_backup_root(temp)
            source = read_backup(root) if root else read_files([temp])
            source.name, source.location = paths[0].stem, paths[0].parent
            yield source
        finally:
            shutil.rmtree(temp, ignore_errors=True)
        return

    if len(paths) == 1 and paths[0].is_dir():
        root = find_backup_root(paths[0])
        if root is None and paths[0].name.upper() == "RAPID":  # user picked the RAPID folder itself
            root = find_backup_root(paths[0].parent)
        if root is not None:
            yield read_backup(root)
            return
    yield read_files(paths)
