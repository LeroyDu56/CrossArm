# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Run every controller probe again, on ROBOGUIDE and RobotStudio, and check what each one leaves.

The probes of tests/fixtures/probes were each run once by hand, their results stored as fixtures. This
runs them all from the files CrossArm writes today (tools/roboguide.py: FTP, the robot's web pages, the
FANUC COM interface; tools/robotstudio.py: the probe server on the ABB virtual controller), so that a
change to CrossArm is checked on a controller and not only on text (--summary: one short line per
probe, everything else in local/logs/probe_all.log):

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
    records      data of RECORD types kept field by field (a state machine, a routine's own record, a whole copy):
                 the totals RobotStudio computes, the speed and zone of a record field as constants and from registers
    arraywrite   arrays of numbers the programs write (R[R[n]], R[base+k]): the totals RobotStudio computes
    flags        bools set to a condition, kept in flags (F[n]=(R[1]<5 AND F[2]=OFF)): the totals RobotStudio
                 computes
    flagarrays   arrays of bools kept in blocks of flags (F[base+k], F[R[n]]): the totals RobotStudio computes
    pointref     points passed by reference (VAR, INOUT robtarget) changed by the routine, read back after the
                 CALL: the values RobotStudio computes, after the moves
    movedo       an output set on the line after a FINE move (MoveLDO to a fine point): it switches with the TCP
                 on the point
    timeflag     waits with \\MaxTime and \\TimeFlag: the flags RobotStudio sets
    speedargs    a routine given its speed and zone (speeddata, zonedata): the time of the same moves written
                 with constants
    search       SearchL as a skip, the input switched through COM as the TCP passes a point: the point found
                 where it switched, a move above it, \\Sup going on to the point, a pause when the input is on at
                 the start; moves with a skip latching the position not slowed down up to the speed converted
    strings      strings kept in string registers (texts compared, worked out, passed on): the totals RobotStudio
                 computes
    pallet       points worked out at run time (Offs of loop counters, RelTool, CRobT): the poses of the moves written out
    io           PulseDO, InvertDO, clocks, SetAO, GripLoad: registers as RAPID computes them, the clock within
                 50 ms, the payload schedule of the tool with the part active
    maketp       the .LS made binary .TP by FANUC MakeTP (SETUP_FRAMES too): loaded, run, registers as RAPID
                 computes them, decoded back by PrintTP to the lines of the .LS (skipped without MakeTP)

Every register a probe reads is set to 0 first, so that no result can be left over from an earlier run.
The programs loaded are deleted at the end. The probes overwrite tool and user frames 1 to 3 and 9, and
position registers: use a test cell. The virtual pendant must be OFF.

Usage:  python tools/probe_all.py [probe ...]      (default: all of them)
"""

import contextlib
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
import make_array_write_probe
import make_bank_probe
import make_compute_probe
import make_condition_probe
import make_flag_array_probe
import make_flag_probe
import make_interrupt_probe
import make_io_probe
import make_maketp_probe
import make_move_do_probe
import make_pallet_probe
import make_param_probe
import make_point_probe
import make_point_ref_probe
import make_record_probe
import make_search_probe
import make_select_probe
import make_setup_probe
import make_speed_arg_probe
import make_string_probe
import make_time_flag_probe
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
    (PROBES / "records" / "RecordProbe.mod", "Probe", "recordprobe.txt", make_record_probe.ABB_RESULT),
    (PROBES / "strings" / "StringProbe.mod", "Probe", "stringprobe.txt", make_string_probe.ABB_RESULT),
    (PROBES / "arraywrite" / "ArrayWriteProbe.mod", "Probe", "arraywriteprobe.txt", make_array_write_probe.ABB_RESULT),
    (PROBES / "flags" / "FlagProbe.mod", "Probe", "flagprobe.txt", make_flag_probe.ABB_RESULT),
    (PROBES / "flagarrays" / "FlagArrayProbe.mod", "Probe", "flagarrayprobe.txt", make_flag_array_probe.ABB_RESULT),
    (PROBES / "pointref" / "PointRefProbe.mod", "Probe", "pointrefprobe.txt", make_point_ref_probe.ABB_RESULT),
    (PROBES / "timeflag" / "TimeFlagProbe.mod", "Probe", "timeflagprobe.txt", make_time_flag_probe.ABB_RESULT),
    (PROBES / "speedargs" / "SpeedArgProbe.mod", "Probe", "speedargprobe.txt", make_speed_arg_probe.ABB_RESULT),
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


def probe_maketp() -> str:
    verdict = make_maketp_probe.run()
    return verdict or f"{len(make_maketp_probe.programs())} .TP made by MakeTP: loaded, run, decoded to their .LS lines"


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


def probe_records() -> str:
    numbers = make_record_probe.registers(make_record_probe.conversion())
    expected = make_record_probe.EXPECTED
    verdicts = []
    for program in (make_record_probe.PROGRAM, *make_record_probe.VARIANTS):  # constants, then from registers
        verdicts.append(_run("records", program, list(numbers.values()),
                             lambda: registers_check(expected, {k: numbers[k] for k in expected}),
                             load=program == make_record_probe.PROGRAM))  # fmt: skip
        if verdicts[-1].startswith("FAIL"):
            return f"{program}: {verdicts[-1]}"
    return f"{verdicts[0]}, in 3 programs (speed and zone as constants, from registers)"


def probe_strings() -> str:
    numbers = make_string_probe.registers(make_string_probe.conversion())
    return _run("strings", make_string_probe.PROGRAM, list(numbers.values()),
                lambda: registers_check(make_string_probe.EXPECTED, numbers))  # fmt: skip


def probe_arraywrite() -> str:
    numbers = make_array_write_probe.registers(make_array_write_probe.conversion())
    return _run("arraywrite", make_array_write_probe.PROGRAM, list(numbers.values()),
                lambda: registers_check(make_array_write_probe.EXPECTED, numbers))  # fmt: skip


def probe_flagarrays() -> str:
    numbers = make_flag_array_probe.registers(make_flag_array_probe.conversion())
    return _run("flagarrays", make_flag_array_probe.PROGRAM, list(numbers.values()),
                lambda: registers_check(make_flag_array_probe.EXPECTED, numbers))  # fmt: skip


def probe_flags() -> str:
    numbers = make_flag_probe.registers(make_flag_probe.conversion())
    return _run("flags", make_flag_probe.PROGRAM, list(numbers.values()),
                lambda: registers_check(make_flag_probe.EXPECTED, numbers))  # fmt: skip


def probe_pointref() -> str:
    numbers = make_point_ref_probe.registers(make_point_ref_probe.conversion())
    return _run("pointref", make_point_ref_probe.PROGRAM, list(numbers.values()),
                lambda: registers_check(make_point_ref_probe.EXPECTED, numbers))  # fmt: skip


def probe_movedo() -> str:
    try:
        distance, delay = make_move_do_probe.measure()
    except RuntimeError as exc:
        return f"FAIL {exc}"
    verdict = "" if distance <= 0.01 else "FAIL "
    return f"{verdict}DO set {distance:.3f} mm from the FINE point, {delay:.0f} ms after the TCP is within 0.5 mm"


def probe_search() -> str:
    try:
        found = make_search_probe.read_results("\n".join(make_search_probe.measure()))
    except RuntimeError as exc:
        return f"FAIL {exc}"
    ok, _ = make_search_probe.verdict(found)
    return (f"{'' if ok else 'FAIL '}point found at y={found.get('nFoundY')} for the input switched at"
            f" y={found.get('SPSTOP_switched_y')}, \\Sup ends at {found.get('nSupEndY')}, input on at the start:"
            f" {found.get('SPEARLY_status')}")


def probe_timeflag() -> str:
    numbers = make_time_flag_probe.registers(make_time_flag_probe.conversion())
    expected = make_time_flag_probe.EXPECTED
    return _run("timeflag", make_time_flag_probe.PROGRAM, list(numbers.values()),
                lambda: registers_check(expected, {k: numbers[k] for k in expected}))  # fmt: skip


def probe_pallet() -> str:
    def check() -> str:
        found = make_pallet_probe.read_poses(make_pallet_probe.poses(roboguide.page("md/POSREG.VA")))
        rows = make_pallet_probe.gaps(found)
        if len(rows) != make_pallet_probe.MOVES:
            return f"FAIL {len(rows)} of {make_pallet_probe.MOVES} moves measured"
        gap, turn = max(r[1] for r in rows), max(r[2] for r in rows)
        verdict = "" if gap <= 0.01 and turn <= 0.001 else "FAIL "
        return f"{verdict}{len(rows)} moves within {gap:.4f} mm, {turn:.4f} deg of the moves written out"

    return _run("pallet", make_pallet_probe.PROGRAM, [], check, timeout=300)


LOADED: list[str] = []


def probe_speedargs() -> str:
    probe = make_speed_arg_probe
    numbers = probe.registers(probe.conversion())

    def check() -> str:
        values = roboguide.numreg()
        found = registers_check(probe.EXPECTED, {k: numbers[k] for k in probe.EXPECTED})
        if found.startswith("FAIL"):
            return found
        for given, written in probe.PAIRS:
            a, b = values.get(numbers[given], float("nan")), values.get(numbers[written], float("nan"))
            if not abs(a - b) <= probe.TOLERANCE * b:
                return f"FAIL {given} {a:.3f} s with arguments, {written} {b:.3f} s with constants"
        return f"{found}, the times of the moves written with constants"

    return _run("speedargs", probe.PROGRAM, list(numbers.values()), check)


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
              "interrupts": probe_interrupts, "params": probe_params, "records": probe_records, "strings": probe_strings,
              "arraywrite": probe_arraywrite, "flags": probe_flags, "flagarrays": probe_flagarrays, "pointref": probe_pointref, "movedo": probe_movedo, "search": probe_search, "timeflag": probe_timeflag, "speedargs": probe_speedargs,
              "pallet": probe_pallet, "maketp": probe_maketp,
              "abb": probe_abb}  # fmt: skip
    # --summary: one short line per probe; what the probes print and the full verdicts go to local/logs/probe_all.log
    summary = "--summary" in sys.argv
    chosen = [name for name in sys.argv[1:] if name != "--summary"] or list(probes)
    failed = 0
    log = None
    if summary:
        (ROOT / "local" / "logs").mkdir(parents=True, exist_ok=True)
        log = (ROOT / "local" / "logs" / "probe_all.log").open("w", encoding="utf-8")
    try:
        for name in chosen:
            start = time.monotonic()
            with contextlib.redirect_stdout(log) if log else contextlib.nullcontext():
                verdict = probes[name]()
            failed += verdict.startswith("FAIL")
            line = f"{name:11s} {time.monotonic() - start:5.1f} s  {verdict}"
            if log:
                print(line, file=log, flush=True)
                first = verdict.splitlines()[0] if verdict else ""
                line = f"{name:11s} {time.monotonic() - start:5.1f} s  " + (first[:60] + "..." if len(first) > 60 else first)
            print(line, flush=True)
    finally:
        for program in dict.fromkeys(LOADED):
            try:
                roboguide.delete(program)
            except Exception:  # noqa: BLE001, S110 - already gone
                pass
        if log:
            log.close()
    print("all probes pass" if not failed else f"{failed} probe(s) FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
