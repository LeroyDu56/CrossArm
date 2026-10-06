# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the MakeTP probe: do the binary .TP programs FANUC MakeTP makes of CrossArm's .LS load and
run on the controller, and say the same as the .LS?

MakeTpProbe.mod adds in a loop, calls a routine each turn, and moves to a joint position (MtProbe); MtTeach,
converted but not run, moves with a tool and a work object, so that the conversion writes SETUP_FRAMES too.
CrossArm converts it; crossarm.fanuc.maketp makes a .TP of every .LS it wrote, SETUP_FRAMES included. On
ROBOGUIDE each .TP is loaded (FTP), MTPROBE runs and NUMREG.VA must hold what RAPID computes (EXPECTED), and
SETUP_FRAMES runs (it starts with a pause, resumed once). FANUC PrintTP then turns each .TP back into text:
its /MN and /POS must be the .LS ones, line for line (the header differs: sizes, dates, padded comment).

MakeTP needs a robot of FANUC Robot Neighborhood (fanuc/maketp.py). CROSSARM_MAKETP_ROBOT names it (a
ROBOGUIDE robot folder or a robot.ini); by default, the ROBOGUIDE robot of ~/Documents whose web port is
CROSSARM_RG_WEB (as tools/roboguide.py), the most recently used one: the cell open in ROBOGUIDE, where
MakeTP works at once instead of starting the robot for each program (about 20 s).

Usage:  python tools/make_maketp_probe.py write    MakeTpProbe.mod and the .LS in tests/fixtures/probes/maketp
        python tools/make_maketp_probe.py run      MakeTP, ROBOGUIDE, PrintTP; results stored in results/
        python tools/make_maketp_probe.py check    compare the stored results
"""

import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.convert.setup import SETUP_NAME, build_setup
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.maketp import TpRequest, find_maketp, make_tp, robot_config
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "maketp"
RESULTS = PROBE / "results"
FANUC_RESULT = RESULTS / "maketpprobe_roboguide.txt"
PROGRAM = "MTPROBE"
ROUTINES = ["MtProbe", "MtCount", "MtTeach"]
TOTALS = ("mtSum", "mtCalls", "mtFlag")
EXPECTED = {"mtSum": 30, "mtCalls": 5, "mtFlag": 100}  # 2+4+6+8+10; five calls; mtSum = 30

MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE MakeTpProbe",
    "    ! CrossArm - MakeTP probe: see tools/make_maketp_probe.py.",
    *[f"    VAR num {total}:=0;" for total in TOTALS],
    "    PERS tooldata tMkTp:=[TRUE,[[0,0,150],[1,0,0,0]],[2,[0,0,60],[1,0,0,0],0,0,0]];",
    '    PERS wobjdata wMkTp:=[FALSE,TRUE,"",[[900,0,400],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];',
    "    CONST jointtarget jMkTp:=[[0,0,0,0,-90,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    "    CONST robtarget pMkTp:=[[0,0,0],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    "",
    "    PROC MtProbe()",
    *[f"        {total}:=0;" for total in TOTALS],
    "        MoveAbsJ jMkTp,v1000,fine,tool0;",
    "        FOR i FROM 1 TO 5 DO",
    "            mtSum:=mtSum+i*2;",
    "            MtCount;",
    "        ENDFOR",
    "        IF mtSum=30 mtFlag:=100;",
    "    ENDPROC",
    "",
    "    PROC MtCount()",
    "        mtCalls:=mtCalls+1;",
    "    ENDPROC",
    "",
    "    PROC MtTeach()",
    "        MoveL pMkTp,v200,fine,tMkTp\\WObj:=wMkTp;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="MakeTpProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    result = convert([parsed.module], config, routines=ROUTINES, sources={"MakeTpProbe": MODULE})
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    result.setup = build_setup(result, config, SETUP_NAME)
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    numbers = {a.rapid_name.upper(): a.number for a in result.registers}
    return {total: numbers[total.upper()] for total in TOTALS}


def programs() -> dict[str, str]:
    result = conversion()
    texts = {info.program.name: write_ls(info.program) for info in result.programs}
    assert result.setup.program is not None
    texts[result.setup.program.name] = write_ls(result.setup.program)
    return texts


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    for stale in PROBE.glob("*.LS"):
        stale.unlink()
    (PROBE / "MakeTpProbe.mod").write_bytes(MODULE.encode("ascii"))
    for name, text in programs().items():
        (PROBE / f"{name}.LS").write_bytes(text.encode("ascii"))
        print(f"{name}.LS")
    for total, number in registers(conversion()).items():
        print(f"  R[{number}] {total}")


def default_robot() -> Path | None:
    """The ROBOGUIDE robot serving on CROSSARM_RG_WEB, the one used last (the cell open in ROBOGUIDE)."""
    port = os.environ.get("CROSSARM_RG_WEB", "9000")
    found = []
    for url in (Path.home() / "Documents").glob("*/*/Robot_*/thisrobot.url"):
        text = url.read_text(encoding="ascii", errors="replace")
        if re.search(rf"localhost:{port}/", text) and (url.parent / "frvirt.dat").is_file():
            log = url.parent / "logfile.txt"
            found.append((log.stat().st_mtime if log.is_file() else 0.0, url.parent))
    return max(found)[1] if found else None


def robot() -> Path | None:
    chosen = os.environ.get("CROSSARM_MAKETP_ROBOT")
    return Path(chosen) if chosen else default_robot()


def body(text: str) -> list[str]:
    """/MN and /POS of a program, the lines as written: what the .TP must keep. The controller names the
    frames it holds (UTOOL[1:Eoat1]) in what it stores from a .LS as well: those names are left out."""
    lines = text.replace("\r\n", "\n").split("\n")
    kept = lines[lines.index("/MN") : lines.index("/END")]
    return [re.sub(r"\b(UTOOL|UFRAME)\[(\d+):[^\]]*\]", r"\1[\2]", line.rstrip()) for line in kept]


def print_tp(maketp: Path, ini: Path, tp: Path, out: Path) -> str:
    """PrintTP (next to MakeTP): the .TP turned back into .LS text."""
    work = tp.parent
    done = subprocess.run([str(maketp.with_name("printtp.exe")), tp.name, out.name, "/config", str(ini)], cwd=work,
                          capture_output=True, text=True, errors="replace", timeout=180, check=False)  # fmt: skip
    if done.returncode != 0 or not (work / out.name).is_file():
        return f"refused: {done.stdout.strip()} {done.stderr.strip()}"
    # Kept without the names the cell gives its frames (UTOOL[1:Gripper]): the cell's own, not CrossArm's.
    text = (work / out.name).read_bytes().decode("ascii", "replace")
    out.write_bytes(re.sub(r"\b(UTOOL|UFRAME)\[(\d+):[^\]]*\]", r"\1[\2]", text).encode("ascii", "replace"))
    return ""


def run() -> str:
    """'' when everything went as it should, else what did not (probe_all prints it)."""
    import roboguide

    maketp, chosen = find_maketp(), robot()
    if maketp is None:
        return "skipped: FANUC MakeTP not installed"
    if chosen is None:
        return "skipped: no ROBOGUIDE robot found for MakeTP (set CROSSARM_MAKETP_ROBOT)"
    write()
    RESULTS.mkdir(parents=True, exist_ok=True)
    for stale in RESULTS.glob("*.printtp.LS"):
        stale.unlink()
    names = list(programs())
    lines = [f"robot {chosen.name}"]
    roboguide.select()
    for name in names:  # MakeTP replaces and deletes a program of the same name in the open cell: none left over
        roboguide.release(name)
        try:
            roboguide.delete(name)
        except Exception:  # noqa: BLE001, S110 - not there
            pass
    with tempfile.TemporaryDirectory(prefix="maketp_probe_") as temp:
        folder = Path(temp)
        export = make_tp([PROBE / f"{name}.LS" for name in names], folder / "TP", TpRequest(chosen, maketp))
        if export.problem:
            return f"FAIL MakeTP: {export.problem}"
        lines += [f"refused {name}: {why}" for name, why in export.refused]
        for name in names:
            tp = folder / "TP" / f"{name}.TP"
            if tp.is_file():
                status = roboguide.load(tp) or "loaded"
                lines.append(f"load {name}.TP {status}")
        lines.append(f"run {SETUP_NAME} {roboguide.run(SETUP_NAME, 120, resumes=1)}")  # starts with a PAUSE
        values = registers(conversion())
        print(f"ROBOGUIDE zero: {roboguide.zero(list(values.values()))}")
        lines.append(f"run {PROGRAM} {roboguide.run(PROGRAM, 120)}")
        found = roboguide.numreg()
        lines += [f"total {total} {found.get(number, float('nan')):g}" for total, number in values.items()]
        ini, problem = robot_config(chosen, maketp, folder)
        for name in names:
            tp = folder / "TP" / f"{name}.TP"
            if tp.is_file() and ini is not None:
                status = print_tp(maketp, ini, tp, RESULTS / f"{name}.printtp.LS")
                lines.append(f"printtp {name} {status or 'done'}")
        if problem:
            lines.append(f"printtp: {problem}")
    roboguide.select()  # the program run last stays selected, and could not be deleted
    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)
        except Exception:  # noqa: BLE001, S110
            pass
    FANUC_RESULT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return check()


def check() -> str:
    """'' when the stored results are right, else the first thing that is not."""
    results = FANUC_RESULT.read_text(encoding="utf-8").splitlines()
    names = list(programs())
    problems = [line for line in results if line.startswith("refused")]
    for name in names:
        if f"load {name}.TP loaded" not in results:
            problems.append(f"{name}.TP not loaded")
        decoded = RESULTS / f"{name}.printtp.LS"
        if not decoded.is_file():
            problems.append(f"{name}.TP not decoded by PrintTP")
        elif body(decoded.read_text(encoding="ascii", errors="replace")) != body((PROBE / f"{name}.LS").read_text(encoding="ascii")):
            problems.append(f"{name}.TP decodes to other lines than {name}.LS")
    for program in (PROGRAM, SETUP_NAME):
        if f"run {program} done" not in results:
            problems.append(f"{program} did not run to its end")
    totals = {parts[1]: float(parts[2]) for parts in (line.split() for line in results) if parts[0] == "total"}
    problems += [f"{total} {totals.get(total)} instead of {value}" for total, value in EXPECTED.items()
                 if totals.get(total) != value]  # fmt: skip
    for line in problems:
        print(line)
    return f"FAIL {problems[0]}" if problems else ""


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    if command == "write":
        write()
    else:
        verdict = {"run": run, "check": check}[command]()
        print(verdict or f"{len(programs())} .TP made by MakeTP: loaded, run, decoded to the lines of their .LS")
        sys.exit(1 if verdict.startswith("FAIL") else 0)
