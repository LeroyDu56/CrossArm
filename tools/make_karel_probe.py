# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the KAREL probe (--karel): CrossArm's KAREL library compiled, loaded and called from TP.

KarelProbe.mod builds two poses at run time and multiplies them (PoseMult), then multiplies the product by a
pose known at conversion time. CrossArm converts it with --karel: the poses are kept in position registers,
each PoseMult is `CALL CA_POSEMULT(a,b,c)` with the registers' numbers, and the library program is written and
compiled by FANUC ktrans (crossarm.fanuc.ktrans). On ROBOGUIDE:

- KRPROBE.LS is loaded before CA_POSEMULT: it loads, and stops on the CALL when it runs (INTP-222);
- a .pc compiled for ktrans' own default version (V9.40) is refused by a V10.10 controller, one compiled for
  V10.13 is loaded;
- with ca_posemult.pc loaded, KRPROBE runs to the end: the registers of krC and krD hold PoseMult as RAPID
  computes it (worked out here from the quaternions of the module, without CrossArm's geometry);
- error cases, each a TP program calling CA_POSEMULT wrongly, then setting a register that must stay 0: a
  register out of range (VARS-024), a real instead of an integer (ROUT-043), an argument missing (ROUT-042), a
  register holding joints (ROUT-032), a register never set (ROUT-038, cleared first by the probe's own KAREL
  program KRCLEAR). Each aborts the program on the CALL, with the controller's message.

  python tools/make_karel_probe.py write    the module and the programs, in tests/fixtures/probes/karel
  python tools/make_karel_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); results in results/
  python tools/make_karel_probe.py check    the stored results against what was measured
"""

import ftplib
import io
import math
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ktrans import KarelRequest, export, find_ktrans
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "karel"
RESULT = PROBE / "results" / "karel_roboguide.txt"
PROGRAM = "KRPROBE"
STAMP = datetime(2026, 1, 1)
WPR_A, WPR_B = (30.0, -20.0, 45.0), (10.0, 40.0, -60.0)  # the orientations of krA and krB, as W, P, R
TURN_Z = (0.7071068, 0.0, 0.0, 0.7071068)  # krD: krC turned 90 deg about its z and moved 10 mm along it
FLAGS = {"KRERRRNG": 81, "KRERRTYP": 82, "KRERRARG": 83, "KRERRJNT": 84, "KRERRUNI": 85}  # R[n] set after the CALL
JOINTS, CLEARED, SPARE = 81, 82, 83  # PR: a joint position, a register cleared, a result nobody reads
ALARMS = {"KRERRRNG": "VARS-024", "KRERRTYP": "ROUT-043", "KRERRARG": "ROUT-042", "KRERRJNT": "ROUT-032",
          "KRERRUNI": "ROUT-038"}  # fmt: skip
CLEAR_KL = """PROGRAM krclear
%NOLOCKGROUP
%ENVIRONMENT REGOPE
-- CrossArm KAREL probe only: CALL KRCLEAR(n) clears PR[n], as on a controller where it was never set.
VAR
  kind, n, status : INTEGER
  r : REAL
  s : STRING[8]
BEGIN
  GET_TPE_PRM(1, kind, n, r, s, status)
  CLR_POS_REG(n, 0, status)
END krclear
"""
VERSION_KL = "PROGRAM {name}\n%NOLOCKGROUP\nBEGIN\nEND {name}\n"


# -- the expected values: RAPID's PoseMult, with quaternions (w, x, y, z), independently of CrossArm ---------------


def q_mul(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    a0, a1, a2, a3 = a
    b0, b1, b2, b3 = b
    return (a0 * b0 - a1 * b1 - a2 * b2 - a3 * b3, a0 * b1 + a1 * b0 + a2 * b3 - a3 * b2,
            a0 * b2 - a1 * b3 + a2 * b0 + a3 * b1, a0 * b3 + a1 * b2 - a2 * b1 + a3 * b0)  # fmt: skip


def q_unit(q: tuple[float, ...]) -> tuple[float, ...]:
    norm = math.sqrt(sum(c * c for c in q))
    return tuple(c / norm for c in q)


def q_turn(q: tuple[float, ...], v: tuple[float, ...]) -> tuple[float, ...]:
    return q_mul(q_mul(q, (0.0, *v)), (q[0], -q[1], -q[2], -q[3]))[1:]


def q_from_wpr(w: float, p: float, r: float) -> tuple[float, ...]:
    """FANUC's W, P, R: turned about the fixed x by W, then y by P, then z by R (Rz . Ry . Rx)."""

    def about(axis: int, degrees: float) -> tuple[float, ...]:
        half = math.radians(degrees) / 2
        return (math.cos(half), *(math.sin(half) if i == axis else 0.0 for i in range(3)))

    return q_mul(q_mul(about(2, r), about(1, p)), about(0, w))


def pose_mult(a: tuple, b: tuple) -> tuple:
    """RAPID PoseMult(a, b): ((x, y, z), q) of b expressed in the frame a."""
    (ta, qa), (tb, qb) = a, b
    turned = q_turn(qa, tb)
    return tuple(x + y for x, y in zip(ta, turned, strict=True)), q_unit(q_mul(qa, qb))


def quaternion_text(q: tuple[float, ...]) -> str:
    return ",".join(f"{c:.7f}" for c in q)


QA, QB = (tuple(round(c, 7) for c in q_from_wpr(*wpr)) for wpr in (WPR_A, WPR_B))
POSE_A = ((100.0, -50.0, 300.0), q_unit(QA))
POSE_B = ((10.0, 20.0, 30.0), q_unit(QB))
POSE_C = pose_mult(POSE_A, POSE_B)
POSE_D = pose_mult(POSE_C, ((0.0, 0.0, 10.0), q_unit(TURN_Z)))

MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE KarelProbe",
    "    ! CrossArm - KAREL probe: see tools/make_karel_probe.py.",
    "    VAR num krDone:=0;",
    "    VAR num krX:=0;",
    "    VAR num krY:=0;",
    "    VAR pose krA;",
    "    VAR pose krB;",
    "    VAR pose krC;",
    "    VAR pose krD;",
    "",
    "    PROC KrProbe()",
    "        krDone:=0;",
    "        krX:=100;",
    "        krY:=10;",
    f"        krA:=[[krX,-50,300],[{quaternion_text(QA)}]];",
    f"        krB:=[[krY,20,30],[{quaternion_text(QB)}]];",
    "        krC:=PoseMult(krA,krB);",
    f"        krD:=PoseMult(krC,[[0,0,10],[{quaternion_text(TURN_Z)}]]);",
    "        krDone:=1;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="KarelProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=True), sources={"KarelProbe": MODULE})
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    assert [info.program.name for info in result.programs] == [PROGRAM] and result.karel_programs == ["CA_POSEMULT"]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """krA... -> the PR CrossArm keeps it in; krDone -> its R."""
    kept = {a.rapid_name.upper(): a.number for a in result.point_registers}
    found = {name: kept[name.upper()] for name in ("krA", "krB", "krC", "krD")}
    found["krDone"] = next(a.number for a in result.registers if a.rapid_name == "krDone")
    return found


def error_programs(numbers: dict[str, int]) -> list[Program]:
    a, b = numbers["krA"], numbers["krB"]
    calls = {
        "KRERRRNG": [f"CALL CA_POSEMULT({a},{b},9999)"],
        "KRERRTYP": [f"CALL CA_POSEMULT({a},{b},2.5)"],
        "KRERRARG": [f"CALL CA_POSEMULT({a},{b})"],
        "KRERRJNT": [f"PR[{JOINTS}]=JPOS", f"CALL CA_POSEMULT({JOINTS},{b},{SPARE})"],
        "KRERRUNI": [f"CALL KRCLEAR({CLEARED})", f"CALL CA_POSEMULT({CLEARED},{b},{SPARE})"],
    }
    return [Program(name, [Instruction(text) for text in [*lines, f"R[{FLAGS[name]}]=1"]],
                    attributes=Attributes(comment="KAREL error case", created=STAMP))
            for name, lines in calls.items()]  # fmt: skip


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "KarelProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    numbers = registers(result)
    for program in [info.program for info in result.programs] + error_programs(numbers):
        (PROBE / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
        print(f"{program.name}.LS")
    (PROBE / "krclear.kl").write_text(CLEAR_KL, encoding="ascii", newline="\r\n")
    for name, number in numbers.items():
        print(f"  {'R' if name == 'krDone' else 'PR'}[{number}] {name}")
    print(f"probe written to {PROBE}")


# -- on ROBOGUIDE ---------------------------------------------------------------------------------------------------


def _ftp(command: str, path: Path | None = None) -> str:
    """'' when the controller did it, else its answer: STOR of a file, DELE of a name."""
    import roboguide

    ftp = ftplib.FTP()
    ftp.connect(roboguide.HOST, roboguide.FTP_PORT, timeout=30)
    ftp.login()
    try:
        if command == "STOR" and path is not None:
            ftp.storbinary(f"STOR {path.name}", io.BytesIO(path.read_bytes()))
        else:
            ftp.delete(command.split(" ", 1)[1])
        return ""
    except ftplib.error_perm as exc:
        return str(exc)
    finally:
        ftp.quit()


def compile_all(work: Path) -> dict[str, str]:
    """The library compiled as a conversion compiles it, KRCLEAR for the same version, and the version probes."""
    import make_maketp_probe

    out = export(["CA_POSEMULT"], work, KarelRequest(make_maketp_probe.robot()), log=print)
    if not out.compiled:
        raise RuntimeError(f"CA_POSEMULT not compiled: {out.problem or out.refused}")
    ktrans = find_ktrans()
    shutil.copy(PROBE / "krclear.kl", work / "krclear.kl")
    found = {"version": out.version}
    jobs = [("krclear", out.version), ("krvdefault", None), ("krv1013", "V10.13-1")]
    for name, version in jobs:
        if name != "krclear":
            (work / f"{name}.kl").write_text(VERSION_KL.format(name=name), encoding="ascii")
        args = [str(ktrans), f"{name}.kl", f"{name}.pc", *(["/ver", version] if version else [])]
        done = subprocess.run(args, cwd=work, capture_output=True, text=True, errors="replace", timeout=60, check=False)
        found[f"{name}_compiled"] = "yes" if (work / f"{name}.pc").is_file() and "successful" in done.stdout else "no"
    return found


def alarm(log: str, code: str, after: set[str]) -> str:
    """The first new error log entry with this code, as 'CODE text SEVERITY', or 'none'."""
    for line in log.splitlines():
        entry = line.split('"', 1)[-1]
        if code in line and entry not in after:
            parts = [p.strip() for p in line.split('"') if p.strip()]
            return " ".join(parts[1:4])[:90]
    return "none"


def measure() -> dict[str, str]:
    import roboguide

    write()
    result = conversion()
    numbers = registers(result)
    names = [PROGRAM, *FLAGS]
    pcs = ["ca_posemult", "krclear", "krvdefault", "krv1013"]
    found: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="crossarm_karel_") as temp:
        work = Path(temp)
        found.update(compile_all(work))
        for name in names:
            roboguide.release(name)
        roboguide.select()
        for name in names:
            _ftp(f"DELE {name.lower()}.tp")
        for name in pcs:
            _ftp(f"DELE {name}.pc")
        try:
            # 1. The TP program before the KAREL one it calls.
            found["alone_load"] = roboguide.load(PROBE / f"{PROGRAM}.LS") or "loaded"
            before = roboguide._alarms() or set()
            roboguide.zero([numbers["krDone"], *FLAGS.values()])
            found["alone_run"] = roboguide.run(PROGRAM, 60)
            found["alone_alarm"] = alarm(roboguide.page("md/ERRALL.LS"), f"INTP-222 ({PROGRAM},", before)
            roboguide.release(PROGRAM)
            roboguide.select()
            # 2. Which compiled versions the controller takes.
            for name in ("krvdefault", "krv1013"):
                found[f"{name}_load"] = _ftp("STOR", work / f"{name}.pc") or "loaded"
            # 3. The library, then the program to the end.
            for name in ("ca_posemult", "krclear"):
                found[f"{name}_load"] = _ftp("STOR", work / f"{name}.pc") or "loaded"
            roboguide.zero([numbers["krDone"]])
            found["run"] = roboguide.run(PROGRAM, 60)
            found["krDone"] = f"{roboguide.numreg().get(numbers['krDone'], float('nan')):g}"
            posreg = roboguide.page("md/POSREG.VA")
            for name in ("krA", "krB", "krC", "krD"):
                found[name] = read_pr(posreg, numbers[name])
            # 4. The error cases.
            for program, flag in FLAGS.items():
                found[f"{program}_load"] = roboguide.load(PROBE / f"{program}.LS") or "loaded"
                before = roboguide._alarms() or set()
                found[f"{program}_run"] = roboguide.run(program, 60)
                found[f"{program}_alarm"] = alarm(roboguide.page("md/ERRALL.LS"), ALARMS[program], before)
                found[f"{program}_after"] = f"{roboguide.numreg().get(flag, float('nan')):g}"
                roboguide.release(program)
            return found
        finally:
            roboguide.select()
            for name in names:
                roboguide.release(name)
            roboguide.select()
            for name in names:
                _ftp(f"DELE {name.lower()}.tp")
            for name in pcs:
                _ftp(f"DELE {name}.pc")


def read_pr(posreg: str, number: int) -> str:
    """PR[n] of POSREG.VA as 'x y z w p r', or 'missing'."""
    block = re.search(rf"\[1,{number}\] =[^\n]*\n([^\[]*)", posreg)
    values = [re.search(rf"\b{axis}:\s*(-?\d*\.?\d+)", block[1]) for axis in "XYZWPR"] if block else []
    if not values or not all(values):
        return "missing"
    return " ".join(v[1] for v in values)  # type: ignore[index]


def gap(found: str, expected: tuple) -> tuple[float, float]:
    """(mm, deg) between a PR read and a pose."""
    numbers = [float(v) for v in found.split()]
    (t, q) = expected
    mm = math.dist(numbers[:3], t)
    dot = abs(sum(a * b for a, b in zip(q_unit(q_from_wpr(*numbers[3:])), q, strict=True)))
    return mm, math.degrees(2 * math.acos(min(1.0, dot)))


def verdict(found: dict[str, str]) -> str:
    """'' when the probe went as measured; else what differs."""
    wrong = []
    if found.get("alone_load") != "loaded" or not found.get("alone_run", "").startswith("paused at line") \
            or not found.get("alone_alarm", "").startswith("INTP-222"):  # fmt: skip
        wrong.append(f"before the .pc: {found.get('alone_load')}, {found.get('alone_run')}, {found.get('alone_alarm')}")
    if "too old" not in found.get("krvdefault_load", "") or found.get("krv1013_load") != "loaded":
        wrong.append(f"versions: default {found.get('krvdefault_load')}, V10.13 {found.get('krv1013_load')}")
    if found.get("ca_posemult_load") != "loaded" or found.get("run") != "done" or found.get("krDone") != "1":
        wrong.append(f"with the .pc: {found.get('ca_posemult_load')}, {found.get('run')}, krDone {found.get('krDone')}")
    for name, expected in (("krA", POSE_A), ("krB", POSE_B), ("krC", POSE_C), ("krD", POSE_D)):
        if found.get(name, "missing") == "missing":
            wrong.append(f"{name} not read")
            continue
        mm, deg = gap(found[name], expected)
        if mm > 0.01 or deg > 0.01:
            wrong.append(f"{name} {found[name]}: {mm:.3f} mm, {deg:.3f} deg from PoseMult")
    for program, code in ALARMS.items():
        if not found.get(f"{program}_alarm", "").startswith(code) or found.get(f"{program}_after") != "0":
            wrong.append(f"{program}: {found.get(f'{program}_run')}, {found.get(f'{program}_alarm')},"
                         f" line after {found.get(f'{program}_after')}")  # fmt: skip
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    worst = max(gap(found[n], e)[0] for n, e in (("krC", POSE_C), ("krD", POSE_D)))
    return (f"compiled for {found.get('version')}; CALL before the .pc stops (INTP-222); PoseMult in PR within"
            f" {worst:.3f} mm; {len(ALARMS)} error cases abort on the CALL")  # fmt: skip


def run() -> str:
    found = measure()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text("".join(f"{k} {v}\n" for k, v in found.items()), encoding="ascii")
    print(RESULT.read_text(encoding="ascii"))
    return check()


def check() -> str:
    found = dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())
    problem = verdict(found)
    print(f"FAIL {problem}" if problem else f"karel probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
