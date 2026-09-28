# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the arm-configuration probes used to calibrate confdata -> CONFIG.

The same joint sets are evaluated by both controllers, each computing its own
configuration from the joint angles (forward kinematics, no reachability check):

  FANUC (ROBOGUIDE): CFGPROBE.LS holds the joint sets as joint positions. On the
      pendant, each point is switched to cartesian representation (POSITION >
      REPRE > Cartesian); the controller then stores X Y Z W P R + CONFIG.
      Re-exporting the program as .LS yields joint set -> CONFIG.

  ABB (RobotStudio): CfgProbe.mod runs CalcRobT on each joint set and writes
      the resulting confdata, TCP position and orientation to HOME:/cfgprobe.txt.

Usage:  python tools/make_config_probes.py [output_dir]   (default tests/fixtures/probes)
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, JointPosition, Motion, Position, Program

# (label, J1..J6 in degrees). Chosen to flip one configuration element at a time:
# wrist (J5 sign), turn numbers (J4, J6 beyond +/-180), elbow and front/back (J2, J3).
JOINT_SETS: list[tuple[str, tuple[float, ...]]] = [
    ("reference", (0, 0, 0, 0, -90, 0)),
    ("J5 positive", (0, 0, 0, 0, 90, 0)),
    ("J5 small neg", (0, 0, 0, 0, -30, 0)),
    ("J5 small pos", (0, 0, 0, 0, 30, 0)),
    ("J4 +185", (0, 0, 0, 185, -90, 0)),
    ("J4 -185", (0, 0, 0, -185, -90, 0)),
    ("J6 +190", (0, 0, 0, 0, -90, 190)),
    ("J6 -190", (0, 0, 0, 0, -90, -190)),
    ("J6 +350", (0, 0, 0, 0, -90, 350)),
    ("J2 +40 J3 +60", (0, 40, 60, 0, -90, 0)),
    ("J2 +40 J3 -60", (0, 40, -60, 0, -90, 0)),
    ("J2 -60 J3 -80", (0, -60, -80, 0, -90, 0)),
    ("J2 -60 J3 +80", (0, -60, 80, 0, -90, 0)),
    ("J2 +60 J3 +80", (0, 60, 80, 0, -90, 0)),
    ("J1 +90", (90, 0, 0, 0, -90, 0)),
    ("J1 -150", (-150, 0, 0, 0, -90, 0)),
]


# ABB only: J3 sweep across the elbow singularity of the IRB 6700 (J3 = -81.83 deg with the
# geometry fitted on the first probe) to check that confdata bit 1 ("wrist centre behind the
# lower arm") flips exactly there, like the FANUC U/D letter does for the M-20iD.
ELBOW_SWEEP: list[tuple[str, tuple[float, ...]]] = [
    (f"J3 {j3:g}", (0, 0, j3, 0, 90, 0)) for j3 in (60, -60, -75, -80, -81.5, -82.2, -85, -90, -120, -150)
] + [("J2 +40 J3 -100", (0, 40, -100, 0, 90, 0)), ("J2 -60 J3 -100", (0, -60, -100, 0, 90, 0))]


def fanuc_probe() -> str:
    lines: list[Instruction | Motion] = [Instruction("!CrossArm CONFIG probe")]
    positions = []
    for number, (_label, joints) in enumerate(JOINT_SETS, start=1):
        lines.append(Motion("J", f"P[{number}]", "10%", "FINE"))
        positions.append(Position(number, 0, 1, JointPosition(joints)))
    attributes = Attributes(comment="CONFIG probe", created=datetime(2026, 1, 1))
    return write_ls(Program("CFGPROBE", lines, positions, attributes))


def _abb_probe(module: str, proc: str, filename: str, joint_sets: list[tuple[str, tuple[float, ...]]]) -> str:
    rows = ",\r\n".join(
        f"        [[{','.join(f'{j:g}' for j in joints)}],[9E9,9E9,9E9,9E9,9E9,9E9]]" for _, joints in joint_sets
    )
    labels = "\r\n".join(f"    ! {i:2d}: {label}" for i, (label, _) in enumerate(joint_sets, start=1))
    return (
        f"MODULE {module}\r\n"
        f"    ! CrossArm - arm configuration probe. Run PROC {proc} (no motion):\r\n"
        "    ! it writes the confdata, TCP position and orientation computed for each\r\n"
        f"    ! joint set to HOME:/{filename}\r\n"
        f"{labels}\r\n"
        f"    CONST jointtarget JT{{{len(joint_sets)}}}:=[\r\n{rows}];\r\n"
        "\r\n"
        f"    PROC {proc}()\r\n"
        "        ! The file is closed after every point: an error keeps what was already written.\r\n"
        "        VAR iodev f;\r\n"
        "        VAR robtarget p;\r\n"
        "        VAR num nPoint:=0;\r\n"
        f'        Open "HOME:" \\File:="{filename}", f \\Write;\r\n'
        "        Close f;\r\n"
        "        FOR i FROM 1 TO Dim(JT,1) DO\r\n"
        "            nPoint:=i;\r\n"
        '            TPWrite "Probe point "\\Num:=i;\r\n'
        "            p:=CalcRobT(JT{i},tool0\\WObj:=wobj0);\r\n"
        f'            Open "HOME:" \\File:="{filename}", f \\Append;\r\n'
        '            Write f, NumToStr(i,0)+" "+ValToStr(p.robconf)+" "+ValToStr(JT{i}.robax);\r\n'
        '            Write f, NumToStr(i,0)+" trans "+NumToStr(p.trans.x,3)+" "+NumToStr(p.trans.y,3)+" "+NumToStr(p.trans.z,3);\r\n'
        '            Write f, NumToStr(i,0)+" rot "+NumToStr(p.rot.q1,6)+" "+NumToStr(p.rot.q2,6)+" "+NumToStr(p.rot.q3,6)+" "+NumToStr(p.rot.q4,6);\r\n'
        "            Close f;\r\n"
        "        ENDFOR\r\n"
        f'        TPWrite "{filename} written in HOME:";\r\n'
        "        ! Stop here: in continuous run mode main would restart and rewrite the file.\r\n"
        "        Stop;\r\n"
        "    ERROR\r\n"
        '        TPWrite "Probe error at point "\\Num:=nPoint;\r\n'
        '        TPWrite "ERRNO = "\\Num:=ERRNO;\r\n'
        "        Stop;\r\n"
        "    ENDPROC\r\n"
        "ENDMODULE\r\n"
    )


def abb_probe() -> str:
    return _abb_probe("CfgProbe", "Probe", "cfgprobe.txt", JOINT_SETS)


def abb_elbow_probe() -> str:
    return _abb_probe("ElbowProbe", "ProbeElbow", "elbowprobe.txt", ELBOW_SWEEP)


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "tests/fixtures/probes"
    out.mkdir(parents=True, exist_ok=True)
    (out / "CFGPROBE.LS").write_bytes(fanuc_probe().encode("ascii"))
    (out / "CfgProbe.mod").write_bytes(abb_probe().encode("ascii"))
    (out / "ElbowProbe.mod").write_bytes(abb_elbow_probe().encode("ascii"))
    print(f"probes written to {out}")


if __name__ == "__main__":
    main()
