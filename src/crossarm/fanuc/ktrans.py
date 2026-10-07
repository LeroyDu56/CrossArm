# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The KAREL folder of a conversion (--karel): the library programs it calls, as .kl, compiled to .pc by FANUC
ktrans when it is installed.

ktrans (ktrans.exe, FANUC WinOLPC, installed with ROBOGUIDE next to maketp.exe) compiles a KAREL source for one
controller software version (`/ver V10.10-1`); CrossArm only calls it, it stays pure Python. Measured with
ROBOGUIDE V10.10 (tools/make_karel_probe.py):

- it needs no robot configuration ("Unable to find robot.ini, using basic KAREL support files");
- it prints "Translation successful" and writes the .pc, then reports "Copy to/from source directory failed"
  and exits with an error code: the .pc is good (loaded and run), so success is the message and the file;
- a .pc made for V9.40 (ktrans' own default) or V9.30 is refused by the V10.10 controller ("Program version
  is too old"); one made for V10.13 is loaded and runs.

The version: the robot's, when the robot MakeTP uses is given (a ROBOGUIDE robot folder, or a robot.ini),
else the newest WinOLPC core installed; the report names it, with the command to compile for another one.
"""

import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from crossarm.fanuc.maketp import core_version, find_maketp, roboguide_robot
from crossarm.karel import LIBRARY, PROGRAMS, R632, source

FOLDER = "KAREL"  # next to the task folders: the library programs the conversion calls
TIMEOUT_S = 60
ENV = "CROSSARM_KTRANS"  # ktrans.exe somewhere else

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class KarelRequest:
    """How the KAREL programs are compiled: for this robot's software, or this version."""

    robot: Path | None = None  # a ROBOGUIDE robot folder or a robot.ini (the --tp-robot one)
    version: str | None = None  # 'V10.10-1'; None: the robot's, else the newest installed
    ktrans: Path | None = None  # None: found (CROSSARM_KTRANS, the WinOLPC install, PATH)


@dataclass
class KarelExport:
    """What the KAREL folder holds."""

    folder: Path
    written: list[str] = field(default_factory=list)  # program names written as .kl
    compiled: list[str] = field(default_factory=list)  # of which compiled to .pc
    refused: list[tuple[str, str]] = field(default_factory=list)  # (program, ktrans' reason)
    problem: str = ""  # why nothing was compiled: ktrans or a version not found
    version: str = ""  # the software version compiled for

    def summary(self) -> str:
        names = ", ".join(self.written)
        if self.problem:
            return f"KAREL programs {names} written as .kl, not compiled: {self.problem}"
        text = f"KAREL programs {names} compiled for {self.version} in {self.folder}"
        return text + (f", {len(self.refused)} refused by ktrans" if self.refused else "")


def find_ktrans(env: dict[str, str] | None = None) -> Path | None:
    env = os.environ if env is None else env
    if env.get(ENV) and Path(env[ENV]).is_file():
        return Path(env[ENV])
    maketp = find_maketp(env)
    if maketp is not None and (beside := maketp.with_name("ktrans.exe")).is_file():
        return beside
    on_path = shutil.which("ktrans")
    return Path(on_path) if on_path else None


def installed_versions(ktrans: Path) -> list[str]:
    """The WinOLPC cores installed next to ktrans, oldest first: ['V9.40-1', 'V10.10-1', ...]."""
    versions = ktrans.parent.parent / "Versions"
    found = []
    for core in versions.glob("V*-*") if versions.is_dir() else ():
        match = re.fullmatch(r"V(\d+)(\d\d)-(\d+)", core.name)
        if match:
            found.append(((int(match[1]), int(match[2]), int(match[3])), f"V{match[1]}.{match[2]}-{match[3]}"))
    return [name for _, name in sorted(found)]


def robot_version(robot: Path, ktrans: Path) -> str | None:
    """The WinOLPC version of a robot: Version= of a robot.ini, or the core matching a ROBOGUIDE robot's software."""
    ini = robot if robot.is_file() else robot / "robot.ini"
    if ini.is_file():
        found = re.search(r"^\s*Version\s*=\s*(\S+)", ini.read_text(encoding="mbcs" if os.name == "nt" else "utf-8",
                                                                       errors="replace"), re.MULTILINE)  # fmt: skip
        return found[1] if found else None
    folder = roboguide_robot(robot) if robot.is_dir() else None
    if folder is None:
        return None
    version, _ = core_version(folder, ktrans)
    return version


def choose_version(request: KarelRequest, ktrans: Path) -> tuple[str | None, str]:
    """(version, '') or (None, why there is none)."""
    if request.version:
        return request.version, ""
    if request.robot is not None and (version := robot_version(request.robot, ktrans)):
        return version, ""
    versions = installed_versions(ktrans)
    if not versions:
        return None, f"no WinOLPC version installed next to {ktrans}"
    return versions[-1], ""


def write_library(names: list[str], folder: Path) -> None:
    """The .kl of these library programs, and the routines they include, into `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    for file in [LIBRARY, *(PROGRAMS[name].source for name in names)]:
        (folder / file).write_text(source(file), encoding="ascii", newline="\r\n")


def export(names: list[str], folder: Path, request: KarelRequest, log: Callable[[str], None] = print,
           runner: Runner | None = None) -> KarelExport:  # fmt: skip
    """Write the library programs `names` into `folder` and compile each with ktrans, when it is installed."""
    out = KarelExport(folder)
    write_library(names, folder)
    out.written = list(names)
    runner = runner or subprocess.run
    ktrans = request.ktrans or find_ktrans()
    if ktrans is None:
        out.problem = ("FANUC ktrans (ktrans.exe) not found: it is installed with ROBOGUIDE, in"
                       " C:\\Program Files (x86)\\FANUC\\WinOLPC\\bin")  # fmt: skip
        return out
    version, problem = choose_version(request, ktrans)
    if version is None:
        out.problem = problem
        return out
    out.version = version
    for name in names:
        kl = PROGRAMS[name].source
        pc = folder / Path(kl).with_suffix(".pc").name
        pc.unlink(missing_ok=True)
        try:
            done = runner([str(ktrans), kl, pc.name, "/ver", version], cwd=folder, capture_output=True, text=True,
                          errors="replace", timeout=TIMEOUT_S, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # fmt: skip
        except (OSError, subprocess.TimeoutExpired) as exc:
            out.refused.append((name, f"ktrans did not finish: {exc}"))
            continue
        if "Translation successful" in done.stdout and pc.is_file():
            out.compiled.append(name)
            continue
        why = reason(f"{done.stdout}\n{done.stderr}")
        if "version ID is invalid" in why:  # the version, not this program
            out.problem = f"ktrans cannot compile for {version}: {why}"
            out.version = ""
            return out
        out.refused.append((name, why))
        log(f"    ktrans refused {kl}: {why}")
    return out


def reason(output: str) -> str:
    """ktrans' message, without its banner and the paths it names: an unknown version, or each error and its line."""
    invalid = re.search(r"The requested version ID is invalid: \S+", output)
    if invalid:
        return invalid[0]
    errors = re.findall(r"\((\d+)\)\s*\n[^\n]*\n\s*\^ ERROR\s*\n\s*([^\n]+)", output)
    if errors:
        return "; ".join(f"line {line}: {message.strip()}" for line, message in errors[:3])
    lines = [line.strip() for line in output.splitlines()
             if "rror" in line and "Copy to/from source directory" not in line]  # fmt: skip
    return re.sub(r"\s+", " ", " ".join(lines)).strip() or "no message"


def compile_command(export: KarelExport) -> str:
    """The command compiling the folder's programs by hand, as the report gives it."""
    version = export.version or "<version>"
    return "; ".join(f"ktrans {PROGRAMS[n].source} {Path(PROGRAMS[n].source).stem}.pc /ver {version}"
                     for n in export.written)  # fmt: skip


def report_section(export: KarelExport, where: str) -> str:
    """The report's part about the KAREL programs; `where`: their folder, as the report names it."""
    text = "\n## KAREL programs (--karel)\n\n"
    text += (f"The programs call {len(export.written)} KAREL program{'s' if len(export.written) > 1 else ''} of"
             f" CrossArm's library, written in `{where}`. The robot needs the {R632}. Load each .pc before the .LS"
             " programs that call it: a CALL to a program the robot does not have stops when it runs"
             " (INTP-222).\n\n")  # fmt: skip
    text += "| Program | Does | Arguments | File |\n|---|---|---|---|\n"
    for name in export.written:
        program = PROGRAMS[name]
        stem = Path(program.source).stem
        file = f"{stem}.pc" if name in export.compiled else f"{program.source} (not compiled)"
        text += f"| `{name}` | {program.does} | {program.arguments} | `{file}` |\n"
    if export.problem:
        text += (f"\nNot compiled: {export.problem}. Compile them with FANUC ktrans for the robot's software version"
                 f" (`{LIBRARY}` in the same folder): `{compile_command(export)}`.\n")  # fmt: skip
    else:
        text += (f"\nCompiled by FANUC ktrans for software version {export.version}: a controller of another version"
                 " may refuse them (\"Program version is too old\"): compile the .kl again for it, in the same folder"
                 f" (`{compile_command(export).replace(export.version, '<version>')}`).\n")  # fmt: skip
    if export.refused:
        text += "\nRefused by ktrans:\n\n" + "".join(f"- `{name}`: {why}\n" for name, why in export.refused)
    return text
