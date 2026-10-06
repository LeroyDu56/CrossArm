# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Binary .TP programs made from the .LS ones by FANUC's MakeTP, when it is installed.

A controller without the ASCII Upload option (R507) does not load .LS programs; a .TP it copies from a
USB stick. MakeTP (maketp.exe, FANUC WinOLPC, installed with ROBOGUIDE in
C:\\Program Files (x86)\\FANUC\\WinOLPC\\bin) makes them: CrossArm only calls it, it stays pure Python.

How MakeTP works, measured with ROBOGUIDE V10.10 (tools/make_maketp_probe.py): it does not translate by
itself, it loads the .LS into a virtual controller and saves the program back as .TP. The robot is named
in a robot configuration file (robot.ini, written by FANUC's Setrobot):

    [WinOLPC_Util]
    Robot=\\C\\Users\\me\\Documents\\My Workcells\\Cell\\Robot_1     the robot in FANUC Robot Neighborhood
    Version=V10.10-1                                            WinOLPC core of its software
    Path=C:\\Program Files (x86)\\FANUC\\WinOLPC\\Versions\\V1010-1\\bin\\
    Support=C:\\Users\\me\\Documents\\My Workcells\\Cell\\Robot_1\\support\\   (must exist)
    Output=C:\\Users\\me\\Documents\\My Workcells\\Cell\\Robot_1\\output\\     (must exist)

A ROBOGUIDE robot folder (...\\Cell\\Robot_1) does as well: CrossArm writes that file for it. Robot
Neighborhood knows the robots of every cell ROBOGUIDE has opened. MakeTP starts the robot's virtual
controller (about 20 s a program), or uses it at once when its cell is open in ROBOGUIDE: then a program
of the same name in that cell is replaced and deleted.
"""

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

FOLDER = "TP"  # next to the task folders: the .TP of every task, ready to copy to a USB stick
TIMEOUT_S = 180  # a program: the virtual controller starts in about 20 s
ENV = "CROSSARM_MAKETP"  # maketp.exe somewhere else

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class TpRequest:
    """What the user asked for: .TP files too, made for this robot."""

    robot: Path | None = None  # robot.ini, or a ROBOGUIDE robot folder; None: robot.ini of the current folder
    maketp: Path | None = None  # None: found (CROSSARM_MAKETP, the WinOLPC install, PATH)


@dataclass
class TpExport:
    """What MakeTP made of one task's programs."""

    folder: Path
    made: list[str] = field(default_factory=list)  # program names written as .TP
    refused: list[tuple[str, str]] = field(default_factory=list)  # (program, MakeTP's reason)
    problem: str = ""  # why no .TP was made at all: MakeTP or the robot configuration not found
    robot: str = ""  # the robot configuration used, as the report names it

    def summary(self) -> str:
        if self.problem:
            return f"no .TP written: {self.problem}"
        text = f"{len(self.made)} .TP written to {self.folder}"
        return text + (f", {len(self.refused)} refused by MakeTP" if self.refused else "")


def find_maketp(env: dict[str, str] | None = None) -> Path | None:
    env = os.environ if env is None else env
    candidates = [Path(env[ENV])] if env.get(ENV) else []
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        if env.get(variable):
            candidates.append(Path(env[variable]) / "FANUC" / "WinOLPC" / "bin" / "maketp.exe")
    found = next((path for path in candidates if path.is_file()), None)
    if found is None and (on_path := shutil.which("maketp")):
        found = Path(on_path)
    return found


def core_version(robot: Path, maketp: Path) -> tuple[str, str] | tuple[None, str]:
    """(Version, Path) for robot.ini: the WinOLPC core matching the software of a ROBOGUIDE robot.

    frvirt.dat of the robot folder starts with its software version ('V10.10270 ...')."""
    try:
        head = (robot / "frvirt.dat").read_text(encoding="ascii", errors="replace")
    except OSError:
        return None, f"{robot} is not a ROBOGUIDE robot folder (no frvirt.dat): give a robot.ini made by FANUC Setrobot"
    found = re.match(r"\s*V(\d+)\.(\d\d)", head)
    if not found:
        return None, f"no software version in {robot / 'frvirt.dat'}"
    versions = maketp.parent.parent / "Versions"
    cores = sorted(versions.glob(f"V{found[1]}{found[2]}-*")) if versions.is_dir() else []
    if not cores:
        return None, f"WinOLPC has no V{found[1]}.{found[2]} core for this robot (in {versions})"
    core = cores[-1].name  # V1010-1
    return f"V{found[1]}.{found[2]}-{core.split('-', 1)[1]}", str(cores[-1] / "bin") + "\\"


def neighborhood_name(robot: Path) -> str:
    """The robot as FANUC Robot Neighborhood names it: C:\\Users\\...\\Robot_1 -> \\C\\Users\\...\\Robot_1."""
    text = str(robot)
    return "\\" + text[0] + text[2:] if len(text) > 2 and text[1] == ":" else text


def roboguide_robot(folder: Path) -> Path | None:
    """The ROBOGUIDE robot folder (holding frvirt.dat) of a robot folder, or of a cell with one robot."""
    if (folder / "frvirt.dat").is_file():
        return folder
    robots = [robot for robot in sorted(folder.glob("Robot_*")) if (robot / "frvirt.dat").is_file()]
    return robots[0] if len(robots) == 1 else None


def check_robot(robot: Path) -> str:
    """'' when `robot` looks usable as a robot configuration, else why not (said as soon as it is chosen)."""
    if robot.is_file() or (robot / "robot.ini").is_file() or roboguide_robot(robot):
        return ""
    if robot.is_dir() and len(list(robot.glob("Robot_*"))) > 1:
        return "this ROBOGUIDE cell has several robots: choose one of its Robot_ folders"
    return "neither a ROBOGUIDE robot folder (...\\Robot_1) nor a robot.ini"


def robot_config(robot: Path | None, maketp: Path, workdir: Path) -> tuple[Path | None, str]:
    """(robot.ini to give MakeTP, '') or (None, why there is none)."""
    if robot is None:
        default = Path.cwd() / "robot.ini"
        if default.is_file():
            return default, ""
        return None, ("no robot configuration: choose the ROBOGUIDE robot folder (...\\Robot_1) of a robot "
                      "like the target one, or a robot.ini made by FANUC Setrobot")  # fmt: skip
    if robot.is_file():
        return robot, ""
    if not robot.is_dir():
        return None, f"robot configuration {robot} not found"
    if (robot / "robot.ini").is_file():
        return robot / "robot.ini", ""
    robot = (roboguide_robot(robot) or robot).resolve()  # a ROBOGUIDE cell of one robot: that robot
    version, path = core_version(robot, maketp)
    if version is None:
        return None, path
    for sub in ("support", "output"):  # MakeTP stops on 'Path not found' without them
        (robot / sub).mkdir(exist_ok=True)
    ini = workdir / "robot.ini"
    ini.write_text(
        "[WinOLPC_Util]\n"
        f"Robot={neighborhood_name(robot)}\n"
        f"Version={version}\n"
        f"Path={path}\n"
        f"Support={robot / 'support'}\\\n"
        f"Output={robot / 'output'}\\\n",
        encoding="mbcs" if os.name == "nt" else "utf-8",
    )  # fmt: skip
    return ini, ""


# MakeTP's own words for a configuration it cannot use, said once instead of for every program.
_SETUP_ERRORS = {
    "A robot has not been defined": "the robot configuration names no robot",
    "requested item was not found": "the robot is unknown to FANUC Robot Neighborhood: open its cell once in "
                                    "ROBOGUIDE, or make a robot.ini with FANUC Setrobot",
    "Path not found": "a folder of the robot configuration does not exist (Robot, Support, Output)",
    "version ID is invalid": "the WinOLPC version of the robot configuration is not installed",
    "Unable to load version library": "the WinOLPC version of the robot configuration is not installed",
}  # fmt: skip


def reason(output: str) -> str:
    """MakeTP's message, without its banner and the temporary path it names."""
    lines = [line.strip() for line in output.splitlines() if line.strip() and not line.startswith("MakeTP V")]
    lines = [line for line in lines if not re.search(r"\.ls\(\d+\)$", line, re.IGNORECASE)]
    text = " ".join(lines).replace("Error executing MakeTP: ", "")
    return re.sub(r"\s+", " ", text).strip() or "no message"


def make_tp(programs: list[Path], folder: Path, request: TpRequest, log: Callable[[str], None] = print,
            runner: Runner | None = None) -> TpExport:  # fmt: skip
    """Write NAME.TP into `folder` for each NAME.LS that MakeTP accepts."""
    export = TpExport(folder)
    runner = runner or subprocess.run
    maketp = request.maketp or find_maketp()
    if maketp is None:
        export.problem = ("FANUC MakeTP (maketp.exe) not found: it is installed with ROBOGUIDE, in "
                          "C:\\Program Files (x86)\\FANUC\\WinOLPC\\bin")  # fmt: skip
        return export
    with tempfile.TemporaryDirectory(prefix="crossarm_maketp_") as temp:
        work = Path(temp)
        ini, problem = robot_config(request.robot, maketp, work)
        if ini is None:
            export.problem = problem
            return export
        export.robot = str(request.robot or ini)
        folder.mkdir(parents=True, exist_ok=True)
        for source in programs:
            name = source.stem.upper()
            shutil.copyfile(source, work / f"{name}.LS")  # MakeTP works in the current folder
            try:
                done = runner([str(maketp), f"{name}.LS", f"{name}.TP", "/config", str(ini)], cwd=work,
                              capture_output=True, text=True, errors="replace", timeout=TIMEOUT_S,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # fmt: skip
            except (OSError, subprocess.TimeoutExpired) as exc:
                export.refused.append((name, f"MakeTP did not finish: {exc}"))
                continue
            made = work / f"{name}.TP"
            if done.returncode == 0 and made.is_file():
                shutil.move(made, folder / made.name)
                export.made.append(name)
                continue
            why = reason(f"{done.stdout}\n{done.stderr}")
            setup = next((text for key, text in _SETUP_ERRORS.items() if key in why), None)
            if setup and not export.made:  # the configuration, not this program: no use trying the others
                export.problem = f"{setup} (MakeTP: {why})"
                return export
            export.refused.append((name, why))
            log(f"    MakeTP refused {name}.LS: {why}")
    return export


def report_section(export: TpExport, where: str) -> str:
    """The report's part about the .TP files; `where`: their folder, as the report names it."""
    text = "\n## Binary .TP programs (FANUC MakeTP)\n\n"
    if export.problem:
        return text + f"Not written: {export.problem}. The .LS programs are written as usual.\n"
    text += (f"{len(export.made)} programs written as .TP in `{where}`, made by MakeTP with the robot "
             f"configuration `{export.robot}`: copy the folder to a USB stick and load them on the robot "
             "(FILE menu), for a controller without the ASCII Upload option. Made for that robot's software "
             "version: a controller with older software may refuse them.\n")  # fmt: skip
    if export.refused:
        text += "\nRefused by MakeTP (load the .LS instead, or fix the line it names):\n\n"
        text += "".join(f"- `{name}.LS`: {why}\n" for name, why in export.refused)
    return text
