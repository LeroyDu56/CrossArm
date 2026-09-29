# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Run every controller probe again, on ROBOGUIDE and RobotStudio, and check what each one leaves.

The probes of tests/fixtures/probes were each run once by hand, their results stored as fixtures. This
runs them all from the files CrossArm writes today (tools/roboguide.py: FTP, the robot's web pages, the
FANUC COM interface; tools/robotstudio.py: the probe server on the ABB virtual controller), so that a
change to CrossArm is checked on a controller and not only on text:

    negative     load only: the forms the controller refuses are still the ones it refuses
    args         calls with arguments: registers as RAPID computes them
    conditions   conditions from the backup's bool functions: registers as RAPID computes them
    waits        waits with MaxTime and their ERROR handler: registers, and how long the waits took
    setup        SETUP_FRAMES.LS, then the frames read back: those of the report
    pose         16 moves: the flange where RobotStudio puts it
    pin          the same moves, tool's pin in the +x hole: the flange half a turn about z, the TCP in place
    abb          RobotStudio: the ABB probe modules write what RobotStudio measured before (needs
                 tools/CrossArmServer.mod running; skipped when RobotStudio is not)
    banks        the same moves with frames past the limit loaded from registers: the same flanges
    compute      frames and points the programs compute, worked out by CrossArm: the flanges RobotStudio computes
    select       TEST/CASE converted to SELECT: the totals RobotStudio computes
    points       routines given their points (Offs, RelTool), arrays of points: the poses of the moves written out
    arrays       arrays of numbers indexed at run time: the totals RobotStudio computes
    interrupts   ISignalDO, IPers, ISleep/IWatch/IDelete as condition monitors: the TRAP calls RAPID makes
    params       records passed as their components, nums passed by reference, Incr/Add: the totals RobotStudio computes
    io           PulseDO, InvertDO, clocks, SetAO, GripLoad: registers as RAPID computes them, the clock within
                 50 ms, the payload schedule of the tool with the part active

Every register a probe reads is set to 0 first, so that no result can be left over from an earlier run.
The programs loaded are deleted at the end. The probes overwrite tool and user frames 1 to 3 and 9, and
position registers: use a test cell. The virtual pendant must be OFF.

Usage:  python tools/probe_all.py [probe ...]      (default: all of them)
"""

import math
import sys
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import make_arg_probe
import make_array_probe
import make_bank_probe
import make_compute_probe
import make_condition_probe
import make_interrupt_probe
import make_io_probe
import make_param_probe
import make_point_probe
import make_select_probe
import make_setup_probe
import make_wait_probe
import roboguide
import robotstudio
from make_pose_probe import FLANGE_PR, compare, read_posreg, read_robotstudio

from crossarm.geometry import quat_to_matrix, wpr_to_matrix

PROBES = ROOT / "tests" / "fixtures" / "probes"
ROBOTSTUDIO = PROBES / "pose" / "results" / "poseprobe_robotstudio.txt"
PIN_ROBOTSTUDIO = PROBES / "pin" / "results" / "pinprobe_robotstudio.txt"
# ABB modules the RobotStudio server runs: (module, routine, file it writes in HOME:, stored measurement).
ABB_PROBES = [
    (PROBES / "CfgProbe.mod", "Probe", "cfgprobe.txt", PROBES / "results" / "cfgprobe_robotstudio.txt"),
    (PROBES / "ElbowProbe.mod", "ProbeElbow", "elbowprobe.txt", PROBES / "results" / "elbowprobe_robotstudio.txt"),
    (PROBES / "pose" / "PoseProbe.mod", "Probe", "poseprobe.txt", ROBOTSTUDIO),
    (PROBES / "pin" / "PinProbe.mod", "Probe", "pinprobe.txt", PIN_ROBOTSTUDIO),
    (PROBES / "compute" / "ComputeProbe.mod", "Probe", "computeprobe.txt", make_compute_probe.ABB_RESULT),
    (PROBES / "select" / "SelectProbe.mod", "Probe", "selectprobe.txt", make_select_probe.ABB_RESULT),
    (PROBES / "arrays" / "ArrayProbe.mod", "Probe", "arrayprobe.txt", make_array_probe.ABB_RESULT),
    (PROBES / "params" / "ParamProbe.mod", "Probe", "paramprobe.txt", make_param_probe.ABB_RESULT),
]
REFUSED = {"NEG_FOR_B"}  # the negative-constant probe: the one form the controller does not load


def flange_check(max_mm: float = 0.05, max_deg: float = 0.01) -> str:
    abb = read_robotstudio(ROBOTSTUDIO.read_text(encoding="utf-8", errors="replace"))
    rows = compare(abb, read_posreg(roboguide.page("md/POSREG.VA")))
    if len(rows) != len(abb):
        return f"{len(rows)} of {len(abb)} moves measured"
    gap, turn = max(r[1] for r in rows), max(r[2] for r in rows)
    verdict = "" if gap <= max_mm and turn <= max_deg else "FAIL "
    return f"{verdict}flanges within {gap:.4f} mm, {turn:.4f} deg of RobotStudio over {len(rows)} moves"


def registers_check(expected: dict[str, float], numbers: dict[str, int]) -> str:
    values = roboguide.numreg()
    found = {name: values.get(number) for name, number in numbers.items()}
    wrong = {name: (found[name], value) for name, value in expected.items() if found[name] != value}
    return f"FAIL {wrong} (found, expected)" if wrong else f"{len(expected)} registers as RAPID computes"


def probe_negative() -> str:
    refused = []
    for path in sorted((PROBES / "negative").glob("*.LS")):
        if roboguide.load(path):
            refused.append(path.stem)
        else:
            LOADED.append(path.stem)
    unexpected = set(refused) ^ REFUSED
    return f"FAIL refused {sorted(refused)}" if unexpected else f"refused only {sorted(refused)}, as measured"


def probe_args() -> str:
    numbers = make_arg_probe.registers(make_arg_probe.conversion())
    return _run("args", "ARGPROBE", list(numbers.values()),
                lambda: registers_check(make_arg_probe.EXPECTED, numbers))  # fmt: skip


def probe_conditions() -> str:
    numbers = make_condition_probe.registers(make_condition_probe.conversion())
    return _run("conditions", "CONDPROBE", list(numbers.values()),
                lambda: registers_check(make_condition_probe.EXPECTED, numbers))  # fmt: skip


def probe_waits() -> str:
    numbers = make_wait_probe.registers(make_wait_probe.conversion())

    def check() -> str:
        text = registers_check(make_wait_probe.EXPECTED, numbers)
        waited = roboguide.numreg().get(42, 0.0)
        ok = abs(waited - make_wait_probe.WAITED_S) <= 0.2
        return f"{text}; waits took {waited:.3f} s for {make_wait_probe.WAITED_S:g}" if ok else f"FAIL waits took {waited}"

    return _run("waits", "WAITTIME", [*numbers.values(), 41, 42], check)


def probe_setup() -> str:
    frames = make_setup_probe.setup()

    def check() -> str:
        registers = read_posreg(roboguide.page("md/POSREG.VA"))
        worst_mm = worst_deg = 0.0
        for kind, frame in frames.written:
            base = make_setup_probe.TOOL_PR if kind == "UTOOL" else make_setup_probe.FRAME_PR
            if base + frame.number not in registers:
                return f"FAIL {kind}[{frame.number}] not read back"
            x, y, z, w, p, r = registers[base + frame.number]
            worst_mm = max(worst_mm, math.dist((x, y, z), frame.frame.pose.pos))
            from make_pose_probe import angle_between

            worst_deg = max(worst_deg, angle_between(quat_to_matrix(frame.frame.pose.rot), wpr_to_matrix(w, p, r)))
        verdict = "" if worst_mm < 0.01 and worst_deg < 0.01 else "FAIL "
        return f"{verdict}{len(frames.written)} frames set within {worst_mm:.4f} mm, {worst_deg:.4f} deg"

    status = _run("setup", "SETUP_FRAMES", [], None, resumes=1)  # it starts with a PAUSE, on purpose
    if status:
        return status
    return _run("setup", "FRAMECHK", [], check, load=False)


def probe_pose() -> str:
    return _run("pose", "POSEPROBE", [], flange_check, timeout=300)


def probe_pin() -> str:
    def check() -> str:
        abb = read_robotstudio(PIN_ROBOTSTUDIO.read_text(encoding="utf-8", errors="replace"))
        rows = compare(abb, read_posreg(roboguide.page("md/POSREG.VA")), tool_pin="+x")
        if len(rows) != len(abb):
            return f"FAIL {len(rows)} of {len(abb)} moves measured"
        gap, turn = max(r[1] for r in rows), max(r[2] for r in rows)
        verdict = "" if gap <= 0.05 and turn <= 0.01 else "FAIL "
        return f"{verdict}flanges within {gap:.4f} mm, {turn:.4f} deg of RobotStudio's turned, over {len(rows)} moves"

    return _run("pin", "POSEPIN", [], check, timeout=300)


def probe_abb() -> str:
    try:
        folder = robotstudio.home()
    except RuntimeError as exc:
        return f"skipped: {exc}"
    for module, routine, output, stored in ABB_PROBES:
        (folder / output).unlink(missing_ok=True)  # what the check reads must be this run's
        status = robotstudio.run(module, routine, 120, folder)
        if status.startswith("server not running"):
            return f"skipped: {status}"
        if status != "done":
            return f"FAIL {module.name}: {status}"
        written = (folder / output).read_text(encoding="utf-8", errors="replace").split()
        if written != stored.read_text(encoding="utf-8", errors="replace").split():
            return f"FAIL {output} is not {stored.name}"
    return f"{len(ABB_PROBES)} modules write what RobotStudio measured, number for number"


def probe_banks() -> str:
    def check() -> str:
        if roboguide.numreg().get(make_bank_probe.MARKER) != make_bank_probe.DONE:
            return "FAIL the probe did not reach its end"
        return flange_check()

    return _run("banks", "BANKPROBE", [make_bank_probe.MARKER], check, timeout=300)


def probe_compute() -> str:
    def check() -> str:
        abb = read_robotstudio(make_compute_probe.ABB_RESULT.read_text(encoding="utf-8"))
        registers = read_posreg(roboguide.page("md/POSREG.VA"))
        rows = compare(abb, registers)
        if len(rows) != len(abb) or FLANGE_PR + make_compute_probe.MOVES not in registers:
            return f"FAIL {len(rows)} of {len(abb)} moves measured"
        gap, turn = max(r[1] for r in rows), max(r[2] for r in rows)
        verdict = "" if gap <= 0.05 and turn <= 0.01 else "FAIL "
        return f"{verdict}flanges within {gap:.4f} mm, {turn:.4f} deg of RobotStudio over {len(rows)} moves"

    return _run("compute", make_compute_probe.PROGRAM, [], check, timeout=300)


def probe_select() -> str:
    numbers = make_select_probe.registers(make_select_probe.conversion())
    return _run("select", make_select_probe.PROGRAM, list(numbers.values()),
                lambda: registers_check(make_select_probe.EXPECTED, numbers))  # fmt: skip


def probe_io() -> str:
    numbers = make_io_probe.registers(make_io_probe.conversion())

    def check() -> str:
        values = roboguide.numreg()
        found = {name: values.get(number) for name, number in numbers.items()}
        if not make_io_probe.matches(found):
            return f"FAIL {found}"
        payload = make_io_probe.active_payload(roboguide.page("md/SYSVARS.VA"))
        expected = make_io_probe.payload_schedule(make_io_probe.conversion())
        if payload != expected:
            return f"FAIL payload schedule {payload}, expected {expected}"
        return f"{len(found)} registers as RAPID computes, PAYLOAD[{payload}] active"

    return _run("io", "IOPROBE", list(numbers.values()), check)


def probe_points() -> str:
    def check() -> str:
        rows = make_point_probe.gaps(make_point_probe.read_poses(make_point_probe.poses(roboguide.page("md/POSREG.VA"))))
        if len(rows) != make_point_probe.MOVES:
            return f"FAIL {len(rows)} of {make_point_probe.MOVES} moves measured"
        gap, turn = max(r[1] for r in rows), max(r[2] for r in rows)
        verdict = "" if gap <= 0.01 and turn <= 0.001 else "FAIL "
        return f"{verdict}{len(rows)} moves within {gap:.4f} mm, {turn:.4f} deg of the moves written out"

    return _run("points", make_point_probe.PROGRAM, [make_point_probe.COUNTER], check, timeout=300)


def probe_arrays() -> str:
    numbers = make_array_probe.registers(make_array_probe.conversion()[0])
    return _run("arrays", make_array_probe.RUNNER, list(numbers.values()),
                lambda: registers_check(make_array_probe.EXPECTED, numbers))  # fmt: skip


def probe_interrupts() -> str:
    numbers = make_interrupt_probe.registers(make_interrupt_probe.conversion())
    return _run("interrupts", make_interrupt_probe.PROGRAM, list(numbers.values()),
                lambda: registers_check(make_interrupt_probe.EXPECTED, numbers))  # fmt: skip


def probe_params() -> str:
    numbers = make_param_probe.registers(make_param_probe.conversion())
    return _run("params", make_param_probe.PROGRAM, list(numbers.values()),
                lambda: registers_check(make_param_probe.EXPECTED, numbers))  # fmt: skip


LOADED: list[str] = []


def _run(folder: str, program: str, zero: list[int], check: Callable[[], str] | None, *, resumes: int = 0,
         timeout: float = 180, load: bool = True) -> str:  # fmt: skip
    """Load the probe's programs, zero its registers, run it, check it. '' when `check` is None and all went well."""
    if load:
        for path in sorted((PROBES / folder).glob("*.LS")):
            try:
                roboguide.delete(path.stem)  # a copy from an earlier run
            except Exception:  # noqa: BLE001, S110 - not there: nothing to delete
                pass
            reason = roboguide.load(path)
            if reason:
                return f"FAIL {path.name} not loaded: {reason}"
            LOADED.append(path.stem)
    if zero:
        roboguide.zero(zero)
    status = roboguide.run(program, timeout, resumes)
    if status != "done":
        return f"FAIL {program}: {status}"
    return check() if check else ""


def main() -> int:
    probes = {"negative": probe_negative, "args": probe_args, "conditions": probe_conditions, "waits": probe_waits,
              "setup": probe_setup, "pose": probe_pose, "pin": probe_pin, "banks": probe_banks,
              "compute": probe_compute, "select": probe_select, "io": probe_io, "points": probe_points, "arrays": probe_arrays,
              "interrupts": probe_interrupts, "params": probe_params,
              "abb": probe_abb}  # fmt: skip
    chosen = sys.argv[1:] or list(probes)
    failed = 0
    try:
        for name in chosen:
            start = time.monotonic()
            verdict = probes[name]()
            failed += verdict.startswith("FAIL")
            print(f"{name:11s} {time.monotonic() - start:5.1f} s  {verdict}", flush=True)
    finally:
        for program in dict.fromkeys(LOADED):
            try:
                roboguide.delete(program)
            except Exception:  # noqa: BLE001, S110 - already gone
                pass
    print("all probes pass" if not failed else f"{failed} probe(s) FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
