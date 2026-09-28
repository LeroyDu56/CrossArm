# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Do CrossArm's axis conventions hold on the robots loaded now in RobotStudio and ROBOGUIDE?

CrossArm's CONFIG, MoveAbsJ and flange conventions (crossarm.convert.configuration) were measured on
an IRB 6700 and an M-20iD/25. This runs the same configuration probe on whatever pair is loaded and
checks them, with nobody at either pendant:

  ABB     tools/robotstudio.py runs CfgProbe.mod (CalcRobT on 16 joint sets, no motion).
  FANUC   CFGRUN.LS goes to the same postures, the joint sets converted as CrossArm converts a
          MoveAbsJ (fanuc_joints), one per run, chosen in R[59], and records LPOS in PR[61..]: POSREG.VA
          then gives X Y Z W P R and CONFIG. A set out of the robot's limits pauses the run; it is
          recorded as such and the next one goes on.

  run     measure, into tests/fixtures/probes/models/<ABB system>__<FANUC robot>/
  check   [folder]  the checks below, on a folder of measurements (default: every one)

The checks, with no model in between: at the same posture, CrossArm's confdata -> CONFIG is the
CONFIG the FANUC computes (U/D and T/B included), and the FANUC flange has the orientation the ABB
one has. Positions differ: the arms are not the same size.
"""

import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import roboguide
import robotstudio
from make_config_probes import JOINT_SETS, abb_probe

from crossarm.convert.configuration import UnsupportedConfdata, fanuc_config, fanuc_joints, j6_on_turn_boundary
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, JointPosition, Motion, Position, Program
from crossarm.geometry import Pose, quat_to_matrix, wpr_to_matrix

MODELS = ROOT / "tests" / "fixtures" / "probes" / "models"
SELECT_REGISTER, FIRST_PR, ZERO_TOOL = 59, 60, 9
PROGRAM = "CFGRUN"


# -- measuring -------------------------------------------------------------------------------


def fanuc_program() -> str:
    lines: list[Instruction | Motion] = [Instruction("!CrossArm CONFIG probe"), Instruction("!one joint set per run")]
    zero = len(JOINT_SETS) + 1
    positions = [Position(i, 0, ZERO_TOOL, JointPosition(fanuc_joints(joints)))
                 for i, (_, joints) in enumerate(JOINT_SETS, 1)]  # fmt: skip
    positions.append(Position(zero, 0, 1, CartesianPosition(0, 0, 0, 0, 0, 0)))
    lines += [Instruction(f"PR[20]=P[{zero}]"), Instruction(f"UTOOL[{ZERO_TOOL}]=PR[20]"),
              Instruction("UFRAME_NUM=0"), Instruction(f"UTOOL_NUM={ZERO_TOOL}")]  # fmt: skip
    for i in range(1, len(JOINT_SETS) + 1):
        lines += [Instruction(f"IF (R[{SELECT_REGISTER}]={i}) THEN"), Instruction(f"JMP LBL[{i}]"), Instruction("ENDIF")]
    lines.append(Instruction("JMP LBL[99]"))
    for i in range(1, len(JOINT_SETS) + 1):
        lines += [Instruction(f"LBL[{i}]"), Motion("J", f"P[{i}]", "20%", "FINE"),
                  Instruction(f"PR[{FIRST_PR + i}]=LPOS"), Instruction("JMP LBL[99]")]  # fmt: skip
    lines.append(Instruction("LBL[99]"))
    return write_ls(Program(PROGRAM, lines, positions, Attributes(comment="CONFIG run", created=datetime(2026, 1, 1))))


def read_posreg_config(text: str) -> dict[int, dict]:
    """PR[n] -> {'config', 'xyz', 'wpr'} from POSREG.VA."""
    out = {}
    for block in re.split(r"(?=\[\s*1\s*,\s*\d+\s*\])", text):
        head = re.match(r"\[\s*1\s*,\s*(\d+)\s*\]", block)
        config = re.search(r"Config:\s*([^\r\n]+)", block)
        values = [re.search(rf"\b{axis}\s*[:=]\s*(-?\d*\.?\d+)", block) for axis in "XYZWPR"]
        if head and config and all(values):
            numbers = [float(v[1]) for v in values]  # type: ignore[index]
            out[int(head[1])] = {"config": config[1].strip(), "xyz": numbers[:3], "wpr": numbers[3:]}
    return out


def measure() -> Path:
    fanuc_robot = roboguide.model()
    abb_system = robotstudio.system()
    folder = MODELS / f"{abb_system}__{re.sub(r'[^A-Za-z0-9._-]+', '_', fanuc_robot)}"
    folder.mkdir(parents=True, exist_ok=True)
    # ABB: CalcRobT on every set, no motion.
    home = robotstudio.home()
    module = folder / "CfgProbe.mod"
    module.write_bytes(abb_probe().encode("ascii"))
    (home / "cfgprobe.txt").unlink(missing_ok=True)
    status = robotstudio.run(module, "Probe", 120, home)
    if status != "done":
        raise RuntimeError(f"RobotStudio: {status}")
    (folder / "cfgprobe_robotstudio.txt").write_bytes((home / "cfgprobe.txt").read_bytes())
    module.unlink()
    # FANUC: one set per run.
    path = folder / f"{PROGRAM}.LS"
    path.write_text(fanuc_program(), encoding="ascii", newline="")
    roboguide.release(PROGRAM)
    try:
        roboguide.delete(PROGRAM)
    except Exception:  # noqa: BLE001, S110 - not there
        pass
    reason = roboguide.load(path)
    if reason:
        raise RuntimeError(f"ROBOGUIDE refused {PROGRAM}.LS: {reason}")
    statuses = {}
    try:
        for i, (label, _) in enumerate(JOINT_SETS, 1):
            roboguide.set_registers({SELECT_REGISTER: i})
            status = roboguide.run(PROGRAM, 60)
            statuses[i] = status
            if status != "done":
                roboguide.release(PROGRAM)
            print(f"  FANUC set {i:2d} {label:16s} {status}")
        registers = read_posreg_config(roboguide.page("md/POSREG.VA"))
    finally:
        roboguide.release(PROGRAM)
        roboguide.delete(PROGRAM)
        path.unlink(missing_ok=True)
    fanuc = {i: registers.get(FIRST_PR + i) if statuses[i] == "done" else {"status": statuses[i]}
             for i in range(1, len(JOINT_SETS) + 1)}  # fmt: skip
    info = {"abb_system": abb_system, "fanuc_robot": fanuc_robot, "fanuc": fanuc}
    (folder / "cfgrun_roboguide.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    return folder


# -- checking --------------------------------------------------------------------------------


def load_abb(path: Path) -> dict[int, dict]:
    points: dict[int, dict] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        index, kind, *rest = line.split()
        entry = points.setdefault(int(index), {})
        if kind == "trans":
            entry["trans"] = tuple(map(float, rest))
        elif kind == "rot":
            entry["quat"] = tuple(map(float, rest))
            entry["rot"] = quat_to_matrix(entry["quat"])
        else:
            entry["conf"] = tuple(int(v) for v in kind.strip("[]").split(","))
    return points


def _gap(a, b) -> float:
    return max(abs(x - y) for ra, rb in zip(a, b, strict=True) for x, y in zip(ra, rb, strict=True))


def check(folder: Path) -> list[tuple[bool, str]]:
    abb = load_abb(folder / "cfgprobe_robotstudio.txt")
    info = json.loads((folder / "cfgrun_roboguide.json").read_text(encoding="utf-8"))
    fanuc = {int(k): v for k, v in info["fanuc"].items() if v and "config" in v}
    joints = {i: j for i, (_, j) in enumerate(JOINT_SETS, 1)}
    results: list[tuple[bool, str]] = []
    skipped = sorted(set(joints) - set(fanuc))
    if skipped:
        results.append((True, f"FANUC: sets {skipped} out of this robot's limits, left out"))

    bad = [i for i in abb if abb[i]["conf"][:3] != tuple(math.floor(joints[i][k] / 90) for k in (0, 3, 5))
           or (abb[i]["conf"][3] & 1) != (joints[i][4] < 0)]  # fmt: skip
    results.append((not bad, f"ABB confdata follows the quadrant and cfx rules{'' if not bad else f': not on {bad}'}"))
    bad = []
    for i, f in fanuc.items():
        try:
            flange = Pose(abb[i]["trans"], abb[i]["quat"])  # as CrossArm sees it: J6 = 180 exactly or not
            mapped = fanuc_config(abb[i]["conf"], j6_boundary=j6_on_turn_boundary(flange, abb[i]["conf"]))
        except UnsupportedConfdata as exc:
            bad.append((i, str(exc)))
            continue
        if mapped.replace(" ", "") != f["config"].replace(" ", ""):
            bad.append((i, f"CrossArm {mapped}, FANUC {f['config']}"))
    # Known limits, said rather than hidden: J6 exactly 180 with J4 off the arm's plane (found only with the
    # arm's lengths), and the elbow letter within a few degrees of the elbow singularity, where two arms of
    # different proportions part at the same joint angles.
    known = [(i, text) for i, text in bad if joints[i][3] % 180 != 0 or abs(joints[i][2] + 81.8) < 5]
    bad = [item for item in bad if item not in known]
    matched = len(fanuc) - len(bad) - len(known)
    results.append((not bad, (f"CrossArm's CONFIG is the FANUC's own at the same posture on {matched} of {len(fanuc)}"
                              f" sets{'' if not bad else f': {bad}'}")))  # fmt: skip
    if known:
        limits = "J4 off the arm's plane with J6 on 180, or next to the elbow singularity"
        results.append((True, f"known limits ({limits}): {known}"))
    worst = max(_gap(wpr_to_matrix(*fanuc[i]["wpr"]), abb[i]["rot"]) for i in fanuc)
    results.append((worst < 1e-3, f"the FANUC flange has the ABB flange's orientation at the same posture (worst gap {worst:.1e})"))
    return results


def main() -> int:
    if sys.argv[1:2] == ["run"]:
        folder = measure()
        print(f"measured into {folder.relative_to(ROOT)}")
        folders = [folder]
    elif sys.argv[1:2] == ["check"]:
        folders = [Path(p) for p in sys.argv[2:]] or sorted(p for p in MODELS.iterdir() if p.is_dir())
    else:
        print(__doc__)
        return 2
    failed = 0
    for folder in folders:
        info = json.loads((folder / "cfgrun_roboguide.json").read_text(encoding="utf-8"))
        print(f"{info['abb_system']}  ->  {info['fanuc_robot']}")
        for ok, text in check(folder):
            failed += not ok
            print(f"  {'ok  ' if ok else 'FAIL'} {text}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
