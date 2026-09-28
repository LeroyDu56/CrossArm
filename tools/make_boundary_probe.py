# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The J6 turn boundary probe: points where the FANUC J6 is exactly 180 must still be reached.

FANUC counts J6 = 180 exactly in turn 1: turn 0 is (-180, 180), open at both ends. An ABB target with
J6 = 0 exactly - flange straight down in front of the robot, [0,0,1,0] - is J6 = 180 exactly on the
FANUC, and a CONFIG with turn 0 is refused there (MOTN-018). CrossArm sees it from the pose
(crossarm.convert.configuration.j6_on_turn_boundary). This module holds such targets and their
neighbours, CrossArm converts it, and the FANUC must reach every point.

Usage:  python tools/make_boundary_probe.py prep      (RobotStudio: the confdata each target is reached with)
        python tools/make_boundary_probe.py [run]     (write, then run on the ROBOGUIDE robot)
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, JointPosition, Motion, Position, Program
from crossarm.rapid import parse_text

OUT = ROOT / "tests" / "fixtures" / "probes" / "boundary"
PREP = OUT / "results" / "boundaryprep_robotstudio.txt"
HOME = (0.0, 0.0, 0.0, 0.0, -90.0, 0.0)  # FANUC joints: flange down in front, J6 at 0
TOOL = "    PERS tooldata tProbe:=[TRUE,[[0,0,200],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];"
NO_EXT = "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]"


def _q(deg: float) -> str:
    """Flange down ([0,0,1,0]) turned deg about the world z axis."""
    h = math.radians(deg) / 2
    parts = (f"{v:.7f}".rstrip("0").rstrip(".") for v in (-math.sin(h), math.cos(h)))
    return "[0," + ",".join("0" if v == "-0" else v for v in parts) + ",0]"


# name -> (position, flange turned deg about z from [0,0,1,0], tool, at FANUC J6 = 180 exactly)
TARGETS = {
    "pAhead": ((1300, 0, 900), 0.0, "tool0", True),  # the common case
    "pAheadTool": ((1300, 0, 700), 0.0, "tProbe", True),  # the same, through a tool along z
    "pAheadHigh": ((1100, 0, 1000), 0.0, "tool0", True),
    "pTurned": ((1300, 0, 900), 0.1, "tool0", False),  # a tenth of a degree off, either way
    "pTurnedBack": ((1300, 0, 900), -0.1, "tool0", False),
    "pAside": ((1126.333, 650, 900), 30.0, "tool0", False),  # radial at 30 deg: 180 up to rounding
    "pSide45": ((1300, -300, 900), 45.0, "tool0", False),
}


def _targets(conf: dict[str, str]) -> list[str]:
    return [f"    CONST robtarget {name}:=[[{x},{y},{z}],{q},{conf.get(name, '[0,0,0,0]')},{NO_EXT}];"
            for name, ((x, y, z), turn, _, _) in TARGETS.items() for q in [_q(turn)]]  # fmt: skip


def prep_module() -> str:
    """RobotStudio moves to each target once (ConfJ Off) and writes the confdata it reached it with."""
    lines = ["MODULE BoundaryPrep", TOOL, *_targets({}), "", "    PROC Prep()", "        VAR iodev f;",
             r'        Open "HOME:" \File:="boundaryprep.txt", f \Write;', "        Close f;", r"        ConfJ\Off;"]  # fmt: skip
    for name, (_, _, tool, _) in TARGETS.items():
        lines += [f"        MoveJ {name},v1000,fine,{tool};", f'        Reached "{name}",{tool};']
    lines += [
        r"        ConfJ\On;",
        "    ENDPROC",
        "",
        "    PROC Reached(string name,PERS tooldata tool)",
        "        VAR iodev f;",
        "        VAR robtarget p;",
        "        VAR jointtarget j;",
        r"        p:=CRobT(\Tool:=tool\WObj:=wobj0);",
        "        j:=CJointT();",
        r'        Open "HOME:" \File:="boundaryprep.txt", f \Append;',
        '        Write f, name+" "+ValToStr(p.robconf)+" "+NumToStr(j.robax.rax_6,4);',
        "        Close f;",
        "    ENDPROC",
        "ENDMODULE",
        "",
    ]
    return "\r\n".join(lines)


def confdata() -> dict[str, str]:
    """The confdata of each target, from its pose: flange down, J4 at 0, so J1 is the azimuth of the
    point and J6 = azimuth - the turn about z (what the ABB robot reported where it is not within its
    0.02 deg of 0). cfx is the one the ABB robot reached it with."""
    out = {}
    for line in PREP.read_text(encoding="utf-8", errors="replace").splitlines():
        name, conf, _j6 = line.split()
        (x, y, _), turn, _, _ = TARGETS[name]
        azimuth = math.degrees(math.atan2(y, x))
        cfx = conf.strip("[]").split(",")[3]
        out[name] = f"[{math.floor(azimuth / 90)},0,{math.floor((azimuth - turn) / 90)},{cfx}]"
    return out


def abb_module() -> str:
    lines = [
        "MODULE BoundaryProbe",
        "    ! CrossArm - J6 turn boundary probe: CrossArm converts PROC Path; the FANUC must reach every point.",
        TOOL,
        *_targets(confdata()),
        "",
        "    PROC Path()",
    ]
    lines += [f"        MoveJ {name},v500,fine,{tool};" for name, (_, _, tool, _) in TARGETS.items()]
    lines += ["    ENDPROC", "ENDMODULE", ""]
    return "\r\n".join(lines)


def fanuc_program(module_text: str) -> tuple[str, dict[str, str]]:
    """CrossArm's conversion of PROC Path, each point reached from the same joint home; name -> CONFIG."""
    parsed = parse_text(module_text, path="BoundaryProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=["Path"])
    (info,) = result.programs
    positions = list(info.program.positions)
    home = max(p.number for p in positions) + 1
    positions.append(Position(home, 0, 1, JointPosition(HOME)))
    lines: list[Instruction | Motion] = []
    data = home + 1
    for frame in result.utools:  # the tool frames CrossArm derived, loaded as SETUP_FRAMES would
        assert frame.frame is not None
        (x, y, z), (w, p, r) = frame.frame.pose.pos, frame.frame.pose.wpr()
        positions.append(Position(data, 0, 1, CartesianPosition(x, y, z, w, p, r)))
        lines += [Instruction(f"PR[20]=P[{data}]"), Instruction(f"UTOOL[{frame.number}]=PR[20]")]
        data += 1
    configs = {}
    names = iter(TARGETS)
    tool = "UTOOL_NUM=1"
    for line in info.program.lines:
        if isinstance(line, Motion):
            name = next(names)
            point = next(p for p in positions if f"P[{p.number}]" == line.target)
            configs[name] = point.value.config  # type: ignore[union-attr]
            # The way back home is taught with UTOOL 1: selected for it, then the point's tool again.
            lines += [Instruction(f"!{name}"), Instruction("UTOOL_NUM=1"), Motion("J", f"P[{home}]", "30%", "FINE"),
                      Instruction(tool), line]  # fmt: skip
        elif not line.text.startswith("!"):
            if line.text.startswith("UTOOL_NUM="):
                tool = line.text
            lines.append(line)
    attributes = Attributes(comment="J6 boundary", created=datetime(2026, 1, 1))
    return write_ls(Program("BOUNDARY", lines, positions, attributes)), configs


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ["prep"]:
        import robotstudio

        (OUT / "BoundaryPrep.mod").write_bytes(prep_module().encode("ascii"))
        home = robotstudio.home()
        status = robotstudio.run(OUT / "BoundaryPrep.mod", "Prep", 120, home)
        print(status)
        if status == "done":
            PREP.parent.mkdir(exist_ok=True)
            PREP.write_bytes((home / "boundaryprep.txt").read_bytes())
            print(PREP.read_text())
        return 0 if status == "done" else 1
    module = abb_module()
    (OUT / "BoundaryProbe.mod").write_bytes(module.encode("ascii"))
    text, configs = fanuc_program(module)
    (OUT / "BOUNDARY.LS").write_bytes(text.encode("ascii"))
    for name, config in configs.items():
        print(f"{name:12s} CONFIG '{config}'  (J6 = 180 exactly: {TARGETS[name][3]})")
    if sys.argv[1:] == ["run"]:
        import roboguide

        roboguide.release("BOUNDARY")
        try:
            roboguide.delete("BOUNDARY")
        except Exception:  # noqa: BLE001, S110 - not there
            pass
        reason = roboguide.load(OUT / "BOUNDARY.LS")
        status = reason or roboguide.run("BOUNDARY", 300)
        roboguide.release("BOUNDARY")
        roboguide.delete("BOUNDARY")
        robot = roboguide.model()
        print(f"{robot}: {status}")
        results = OUT / "results" / "roboguide.json"
        runs = json.loads(results.read_text(encoding="utf-8")) if results.exists() else {}
        runs[robot] = {"status": status, "configs": configs}
        results.write_text(json.dumps(runs, indent=1) + "\n", encoding="utf-8")
        return 0 if status == "done" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
