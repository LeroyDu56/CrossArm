# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Which numbers the programs already on a FANUC controller use.

A migration lands on a cell that is not empty: the robot already has tool frames,
registers and I/O in use. Numbering the converted programs from 1 up collides with
all of it. Given the controller's existing programs (a backup folder, a zip or .LS
files), this reads them with the lossless parser and lists every UFRAME, UTOOL, R,
PR, F, DO, DI, GO and GI number they touch, with the programs that touch it, so the
conversion can leave those numbers alone.

What counts as a use: the number appears in an instruction or a motion, or a
position is recorded in that frame. Remarks ('!...'), commented-out lines ('//...'),
MESSAGE texts and quoted strings are ignored: a number mentioned in a comment is
not a use. Indirect references (R[R[4]], UFRAME_NUM=R[2]) count the register only;
where they point cannot be known without running the program.
"""

import re
import shutil
import tempfile
import zipfile
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from crossarm.backup import _safe_extract
from crossarm.fanuc.ls_parser import LSFormatError, parse_ls
from crossarm.fanuc.tp import Instruction, Program
from crossarm.rapid import RAPID_SUFFIXES

RESOURCES = ("UFRAME", "UTOOL", "R", "PR", "F", "DO", "DI", "GO", "GI", "TIMER")

# Not preceded by a letter, digit, '_' or '$': 'PR[' is not 'R[', 'SDO[' is not 'DO[',
# '$MNUFRAME[' is a system variable.
_BEFORE = r"(?<![A-Za-z0-9_$])"
_REGISTER = re.compile(_BEFORE + r"(R|PR|F|DO|DI|GO|GI|TIMER)\[(\d+)")
_FRAME_REGISTER = re.compile(_BEFORE + r"(UFRAME|UTOOL)\[(\d+)")
_FRAME_SELECT = re.compile(_BEFORE + r"(UFRAME|UTOOL)_NUM\s*=\s*(\d+)")
# MESSAGE[...] is the whole instruction, so its text runs to the last ']' of the line:
# stopping at the first one would read 'DO[2]' in MESSAGE[check R[1] and DO[2]] as a use.
_NOT_CODE = re.compile(r"MESSAGE\[.*\]|'[^']*'")


@dataclass
class ControllerUsage:
    # resource -> number -> names of the programs using it
    numbers: dict[str, dict[int, set[str]]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(set)))
    programs: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # file name, reason
    robot: str | None = None  # the arm, as the backup names it ('R-2000iC/165F'), when it says

    def add(self, resource: str, number: int, program: str) -> None:
        self.numbers[resource][number].add(program)

    def reserved(self) -> dict[str, dict[int, tuple[str, ...]]]:
        """For ConversionConfig.reserved: resource -> number -> sorted program names."""
        return {res: {n: tuple(sorted(users)) for n, users in sorted(nums.items())}
                for res, nums in self.numbers.items() if nums}  # fmt: skip

    def summary(self) -> str:
        """'UTOOL 3, R 40, DO 32': how many numbers are taken. 0 is left out, as in the
        report: UFRAME 0 is the world frame, and no register or I/O is numbered 0."""
        counts = {res: sum(1 for n in self.numbers.get(res, {}) if n > 0) for res in RESOURCES}
        return ", ".join(f"{res} {count}" for res, count in counts.items() if count) or "none"


def scan(programs: Iterable[Program], usage: ControllerUsage | None = None) -> ControllerUsage:
    usage = usage or ControllerUsage()
    for program in programs:
        usage.programs.append(program.name)
        for line in program.lines:
            if isinstance(line, Instruction):
                code = line.text.strip()
                if code.startswith(("!", "//")):
                    continue
                texts = [code]
            else:
                texts = [line.target, line.speed, line.termination, line.options, line.via or ""]
            for text in texts:
                _scan_text(_NOT_CODE.sub("", text), program.name, usage)
        for position in program.positions:
            usage.add("UFRAME", position.uf, program.name)
            usage.add("UTOOL", position.ut, program.name)
    return usage


def _scan_text(text: str, program: str, usage: ControllerUsage) -> None:
    for pattern in (_REGISTER, _FRAME_REGISTER, _FRAME_SELECT):
        for m in pattern.finditer(text):
            usage.add(m[1], int(m[2]), program)


def is_fanuc_input(path: Path) -> bool:
    """A .LS file, or a folder or zip holding .LS files and no RAPID module.

    Lets the desktop app take an ABB backup and the FANUC controller's backup dropped
    together: the second one is recognised and read for its numbers, not converted.
    """
    path = Path(path)
    if path.is_file() and path.suffix.lower() == ".ls":
        return True
    if path.is_dir():
        names = [p.name for p in path.rglob("*") if p.is_file()]
    elif path.is_file() and path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
        except zipfile.BadZipFile:
            return False
    else:
        return False
    suffixes = {Path(n).suffix.lower() for n in names}
    return ".ls" in suffixes and not suffixes & RAPID_SUFFIXES


# Where a backup names its arm: the order file lists the mechanical unit's order number with the model
# as a remark, the DCS verification report prints it.
_ROBOT_FILES = {
    "orderfil.dat": re.compile(r"^\s*\d*A05B-\d{4}-H\w+\s*!\s*(\S.*?)\s*$", re.MULTILINE),
    "dcsvrfy.dg": re.compile(r"^\s*Robot:\s*(\S.*?)(?:\s{2,}|\s*$)", re.MULTILINE),
}


# An arm's name: R-2000iC/190S, M-20iD/25, LR Mate 200iD, ARC Mate 120iD, CRX-10iA/L... The order file also lists
# the software (HandlingTool, English UIF...) with the same kind of order number, sometimes first (ROBOGUIDE V10).
_ARM = re.compile(r"\d+i[A-D]\b|\bMate\b|\bCRX\b")


def robot_model(files: Iterable[Path]) -> str | None:
    """The arm the backup is from, as its order file or DCS report names it."""
    for file in sorted(files, key=lambda f: list(_ROBOT_FILES).index(f.name.lower()) if f.name.lower() in _ROBOT_FILES else 9):
        pattern = _ROBOT_FILES.get(file.name.lower())
        if pattern is None:
            continue
        names = pattern.findall(file.read_bytes().decode("cp1252", errors="replace"))
        if names:
            return next((name for name in names if _ARM.search(name)), names[0])
    return None


def read_controller(paths: Iterable[Path]) -> ControllerUsage:
    """Scan every .LS file under the given folders, zips or files, and find the arm the backup is from."""
    usage = ControllerUsage()
    for path in map(Path, paths):
        if path.is_file() and path.suffix.lower() == ".zip":
            temp = Path(tempfile.mkdtemp(prefix="crossarm_fanuc_"))
            try:
                with zipfile.ZipFile(path) as archive:
                    _safe_extract(archive, temp)
                files = sorted(temp.rglob("*"))
                _scan_files([p for p in files if p.suffix.lower() == ".ls"], usage)
                usage.robot = usage.robot or robot_model(files)
            finally:
                shutil.rmtree(temp, ignore_errors=True)
        elif path.is_dir():
            files = sorted(path.rglob("*"))
            _scan_files([p for p in files if p.suffix.lower() == ".ls"], usage)
            usage.robot = usage.robot or robot_model(files)
        else:
            _scan_files([path], usage)
    return usage


def _scan_files(files: list[Path], usage: ControllerUsage) -> None:
    for file in files:
        data = file.read_bytes()
        try:
            # cp1252 as read_ls does: hand-edited programs carry accents in their comments
            program = parse_ls(data.decode("cp1252", errors="replace"))
        except LSFormatError as exc:
            reason = "not a TP program" if not data.startswith(b"/PROG") else str(exc)
            usage.skipped.append((file.name, reason))
            continue
        scan([program], usage)


__all__ = ["RESOURCES", "ControllerUsage", "is_fanuc_input", "read_controller", "robot_model", "scan"]
