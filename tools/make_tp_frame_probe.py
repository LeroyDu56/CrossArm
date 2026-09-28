# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""What TP can do with frames: which instructions the controller loads, and what they compute.

RAPID composes frames freely (PoseMult, PoseInv, DefFrame...). Before deciding what CrossArm writes for
a frame the programs compute, this asks ROBOGUIDE:

  syntax   one program per candidate line, loaded or refused (ASBN-xxx): pose product, trigonometry,
           several operators in one calculation, OFFSET CONDITION, Offset / Tool_Offset on a move...
  compute  TPFRAMES.LS sets known values in PR[21..26], combines them and moves with offsets, recording
           each result (LPOS with a zero tool): PR[31..40]. Each is compared with a composition of
           frames and with a component-by-component sum.

Measured on an R-2000iC/190S (HandlingTool, V10): PR[a]=PR[b]+PR[c] adds component by component (W, P, R
included); PR[a]=PR[b]*PR[c] loads but stops the program (INTP-202); no angle function exists; Offset,PR
adds component by component in the active user frame; Tool_Offset,PR composes in the tool frame;
UFRAME[n]=PR[m] and back are exact; LPOS reads the pose in the active user frame. So TP cannot compute a
frame: crossarm.convert.compute does it at conversion time, and a calibration measured on the robot stays
TODO (KAREL has the pose operators).

Usage:  python tools/make_tp_frame_probe.py run     (ROBOGUIDE running, virtual pendant OFF)
        python tools/make_tp_frame_probe.py check   what the stored results say
"""

import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from make_pose_probe import angle_between, read_posreg

from crossarm.geometry import Pose, matrix_to_quat, quat_to_matrix, wpr_to_matrix

PROBE = ROOT / "tests" / "fixtures" / "probes" / "tp_frames"
RESULT = PROBE / "results" / "tp_frames_roboguide.txt"
PROGRAM = "TPFRAMES"

SYNTAX = {  # candidate line -> what it would give
    "pr_product": "PR[35]=PR[21]*PR[22]",
    "pr_quotient": "PR[35]=PR[21]/PR[22]",
    "pr_colon": "PR[35]=PR[21]:PR[22]",
    "pr_sum": "PR[35]=PR[21]+PR[22]",
    "pr_copy": "PR[35]=PR[21]",
    "pr_frame_sum": "PR[35]=UFRAME[5]+PR[21]",
    "pr_times_number": "PR[35]=PR[21]*R[42]",
    "component_copy": "PR[35,4]=PR[21,6]",
    "component_sum": "PR[35,1]=PR[21,1]+R[42]",
    "sin_brackets": "R[41]=SIN[R[42]]",
    "sin_parentheses": "R[41]=SIN(R[42])",
    "atan2": "R[41]=ATAN2[R[42],R[43]]",
    "sqrt": "R[41]=SQRT[R[42]]",
    "several_operators": "R[41]=(R[42]*R[43]+R[44])",
    "nested_parentheses": "R[41]=((R[42]+R[43])*(R[44]-R[45]))",
    "sin_in_expression": "R[41]=(SIN[R[42]]*PR[21,1]+R[44])",
    "offset_condition": "OFFSET CONDITION PR[24]",
    "offset_condition_frame": "OFFSET CONDITION PR[24],UFRAME[5]",
    "tool_offset_condition": "TOOL_OFFSET CONDITION PR[25],UTOOL[9]",
    "move_offset": "L PR[30] 100mm/sec FINE Offset,PR[23]",
    "move_tool_offset": "L PR[30] 100mm/sec FINE Tool_Offset,PR[25]",
    "uframe_from_pr": "UFRAME[5]=PR[21]",
    "pr_from_uframe": "PR[35]=UFRAME[5]",
    "payload": "PAYLOAD[1]",
}

VALUES = {  # PR -> X, Y, Z, W, P, R
    21: (100, -50, 30, 10, 0, 90),  # A: a user frame
    22: (50, 20, 0, 0, 20, 30),  # B
    23: (10, 20, 30, 5, 0, 10),  # T: Offset,PR
    24: (10, 0, 0, 0, 0, 0),  # C: OFFSET CONDITION ...,UFRAME[5]
    25: (20, 0, 50, 5, 0, 10),  # U: Tool_Offset,PR
}
MOVE = "100mm/sec FINE"


def program(name: str, lines: list[str], positions: str = "") -> str:
    head = [
        f"/PROG  {name}", "/ATTR", "OWNER\t\t= MNEDITOR;", 'COMMENT\t\t= "";', "PROG_SIZE\t= 0;",
        "CREATE\t\t= DATE 26-01-01  TIME 00:00:00;", "MODIFIED\t= DATE 26-01-01  TIME 00:00:00;", "FILE_NAME\t= ;",
        "VERSION\t\t= 0;", f"LINE_COUNT\t= {len(lines)};", "MEMORY_SIZE\t= 0;", "PROTECT\t\t= READ_WRITE;",
        "TCD:  STACK_SIZE\t= 0,", "      TASK_PRIORITY\t= 50,", "      TIME_SLICE\t= 0,", "      BUSY_LAMP_OFF\t= 0,",
        "      ABORT_REQUEST\t= 0,", "      PAUSE_REQUEST\t= 0;", "DEFAULT_GROUP\t= 1,*,*,*,*;",
        "CONTROL_CODE\t= 00000000 00000000;", "/MN",
    ]  # fmt: skip
    body = [f"{i:4d}:{line} ;" if line[:2] in ("J ", "L ") else f"{i:4d}:  {line} ;" for i, line in enumerate(lines, 1)]
    return "\r\n".join([*head, *body, "/POS", *([positions] if positions else []), "/END", ""])


HOME = (
    "P[1]{\r\n   GP1:\r\n\tUF : 0, UT : 9,\t\r\n"
    "\tJ1=     0.000 deg,\tJ2=     0.000 deg,\tJ3=     0.000 deg,\r\n"
    "\tJ4=     0.000 deg,\tJ5=   -90.000 deg,\tJ6=     0.000 deg\r\n};"
)


def compute_lines() -> list[str]:
    """R[41] tells how far it went: each step sets it before trying."""
    out = ["R[41]=0", "UFRAME_NUM=0", "PR[29]=LPOS", "PR[29]=PR[29]-PR[29]", "UTOOL[9]=PR[29]", "UTOOL_NUM=9",
           "J P[1] 10% FINE", "PR[30]=LPOS"]  # fmt: skip
    for pr, values in VALUES.items():
        out.append(f"PR[{pr}]=PR[29]")
        out += [f"PR[{pr},{j}]={v if v > 0 else f'({v})'}" for j, v in enumerate(values, 1) if v]
    return out + [
        "R[41]=1", "PR[31]=PR[21]+PR[22]", "UFRAME[5]=PR[21]", "PR[32]=UFRAME[5]",
        "UFRAME_NUM=5", "PR[34]=LPOS", "UFRAME_NUM=0",
        "R[41]=2", f"L PR[30] {MOVE} Offset,PR[23]", "PR[33]=LPOS", "J P[1] 10% FINE",
        "R[41]=3", "OFFSET CONDITION PR[24],UFRAME[5]", f"L PR[30] {MOVE} Offset", "PR[38]=LPOS", "J P[1] 10% FINE",
        "R[41]=4", f"L PR[30] {MOVE} Tool_Offset,PR[25]", "PR[39]=LPOS", "J P[1] 10% FINE",
        "R[41]=5", "UFRAME_NUM=5", f"L PR[34] {MOVE} Offset,PR[23]", "UFRAME_NUM=0", "PR[40]=LPOS",
        "J P[1] 10% FINE",
        "R[41]=6", "PR[36]=PR[21]*PR[22]",  # loads, then INTP-202 here
        "R[41]=7",
    ]  # fmt: skip


def run() -> None:
    import roboguide

    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "results").mkdir(exist_ok=True)
    rows = []
    for i, (case, line) in enumerate(SYNTAX.items()):
        path = PROBE / f"TPSYN{i:02d}.LS"
        path.write_bytes(program(path.stem, [line]).encode("ascii"))
        reason = roboguide.load(path)
        rows.append(f"syntax {case} {'loaded' if not reason else 'refused ' + reason.split('load: ')[-1].split(' ')[0]}")
        if not reason:
            roboguide.delete(path.stem)
        path.unlink()
    path = PROBE / f"{PROGRAM}.LS"
    path.write_bytes(program(PROGRAM, compute_lines(), HOME).encode("ascii"))
    print(f"load: {roboguide.load(path) or 'loaded'}")
    outcome = f"{roboguide.run(PROGRAM, 240)} step {roboguide.numreg().get(41, 0):g}"
    alarm = next((line for line in roboguide.page("md/ERRALL.LS").splitlines() if f"({PROGRAM}," in line), "")
    code = re.search(r"\b([A-Z]{3,4}-\d{3})\b", alarm)
    rows.append(f"run {outcome}" + (f" {code[1]}" if code else ""))
    registers = read_posreg(roboguide.page("md/POSREG.VA"))
    rows += [f"pr {k} " + " ".join(f"{v:.3f}" for v in registers[k]) for k in (30, 31, 32, 33, 34, 38, 39, 40)]
    roboguide.release(PROGRAM)
    roboguide.delete(PROGRAM)
    RESULT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    check()


def pose(values) -> Pose:
    return Pose(tuple(float(v) for v in values[:3]), matrix_to_quat(wpr_to_matrix(*values[3:6])))  # type: ignore[arg-type]


def added(a, b) -> tuple[float, ...]:
    return tuple(x + y for x, y in zip(a, b, strict=True))


def gap(expected: Pose, measured) -> tuple[float, float]:
    other = pose(measured)
    return math.dist(expected.pos, other.pos), angle_between(quat_to_matrix(expected.rot), quat_to_matrix(other.rot))


def results() -> tuple[dict[str, str], str, dict[int, tuple[float, ...]]]:
    syntax, outcome, registers = {}, "", {}
    for line in RESULT.read_text(encoding="utf-8").splitlines():
        kind, rest = line.split(" ", 1)
        if kind == "syntax":
            case, verdict = rest.split(" ", 1)
            syntax[case] = verdict
        elif kind == "run":
            outcome = rest
        elif kind == "pr":
            number, *values = rest.split()
            registers[int(number)] = tuple(float(v) for v in values)
    return syntax, outcome, registers


def findings() -> dict[str, tuple[float, float]]:
    """(mm, deg) between each measurement and what it is taken for; near 0: that is what TP does."""
    _, _, pr = results()
    a, t, c, u = (VALUES[k] for k in (21, 23, 24, 25))
    home = pr[30]
    frame = pose(a)
    return {
        "PR+PR adds component by component": gap(pose(added(a, VALUES[22])), pr[31]),
        "PR+PR is not a composition": gap(frame.compose(pose(VALUES[22])), pr[31]),
        "UFRAME[n]=PR[m] and back are exact": gap(frame, pr[32]),
        "LPOS reads in the active user frame": gap(frame.inverse().compose(pose(home)), pr[34]),
        "Offset,PR adds component by component": gap(pose(added(home, t)), pr[33]),
        "OFFSET CONDITION ...,UFRAME[n]: offset in that frame": gap(
            frame.compose(pose(c)).compose(frame.inverse()).compose(pose(home)), pr[38]),
        "Tool_Offset,PR composes in the tool frame": gap(pose(home).compose(pose(u)), pr[39]),
        "Offset in a user frame: added in it": gap(frame.compose(pose(added(pr[34], t))), pr[40]),
    }  # fmt: skip


def check() -> None:
    syntax, outcome, _ = results()
    for case, verdict in syntax.items():
        print(f"{case:24s} {SYNTAX[case]:45s} {verdict}")
    print(f"TPFRAMES: {outcome}")
    for claim, (mm, deg) in findings().items():
        print(f"{mm:9.3f} mm {deg:7.3f} deg  {claim}")


if __name__ == "__main__":
    {"run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "check"]()
