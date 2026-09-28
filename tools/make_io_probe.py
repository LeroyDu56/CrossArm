# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the I/O probe: do PulseDO, InvertDO, SetAO, the clocks and GripLoad, converted, do what RAPID does?

IoProbe.mod inverts an output twice, pulses another and looks at it during and after the pulse, times
half a second with a clock, sets an analog output with the scale of the mapping file, and grips a part between two joint
moves (GripLoad: the payload schedule of the tool with the part). CrossArm
converts it (DO[n]=(!DO[n]), DO[n]=PULSE,0.5sec, TIMER[n]=RESET/START/STOP and R[m]=TIMER[n],
AO[n]=counts); every program is written to this folder. On ROBOGUIDE, load it, run IOPROBE, and read
NUMREG.VA: each RAPID num holds the value EXPECTED gives, which is what the module does on an ABB
controller (worked out by hand: the virtual ABB controller has no such signals), the clock within
TIME_TOLERANCE_S of half a second. The active payload schedule, $PLST_PARNUM[1] in SYSVARS.VA, is then the
one CrossArm numbered for the tool with the part.

Usage:  python tools/make_io_probe.py [output_dir]   (default tests/fixtures/probes/io)
"""

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import parse_text
from crossarm.rapid.eio import Signal

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE IoProbe",
    "    ! CrossArm - I/O probe: see tools/make_io_probe.py.",
    "    VAR num nInvert:=0;",
    "    VAR num nPulse:=0;",
    "    VAR num nTime:=0;",
    "    VAR clock ckProbe;",
    "    PERS tooldata tProbe:=[TRUE,[[0,0,100],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];",
    "    PERS loaddata lProbe:=[2,[0,0,20],[1,0,0,0],0,0,0];",
    "    CONST jointtarget jProbe:=[[0,0,0,0,-90,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    "",
    "    PROC IoProbe()",
    "        nInvert:=0;",
    "        nPulse:=0;",
    "        nTime:=0;",
    "        Reset doProbeA;",
    "        InvertDO doProbeA;",
    "        IF DOutput(doProbeA)=1 nInvert:=nInvert+1;",
    "        InvertDO doProbeA;",
    "        IF DOutput(doProbeA)=0 nInvert:=nInvert+10;",
    "        Reset doProbeB;",
    "        PulseDO\\PLength:=0.5,doProbeB;",
    "        WaitTime 0.1;",
    "        IF DOutput(doProbeB)=1 nPulse:=nPulse+1;",
    "        WaitTime 0.6;",
    "        IF DOutput(doProbeB)=0 nPulse:=nPulse+10;",
    "        ClkReset ckProbe;",
    "        ClkStart ckProbe;",
    "        WaitTime 0.5;",
    "        ClkStop ckProbe;",
    "        nTime:=ClkRead(ckProbe);",
    "        SetAO aoProbe,2.5;",
    "        MoveAbsJ jProbe,v1000,fine,tProbe;",
    "        GripLoad lProbe;",
    "        MoveAbsJ jProbe,v1000,fine,tProbe;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

SIGNALS = {"DOPROBEA": Signal("doProbeA", "DO"), "DOPROBEB": Signal("doProbeB", "DO"),
           "AOPROBE": Signal("aoProbe", "AO")}  # fmt: skip
ANALOG_SCALE = 100.0  # counts per RAPID unit, as a mapping file would give it: 2.5 -> AO[1]=250

# Inverted to 1 then back to 0; the pulse is on 0.1 s in and off 0.7 s in; the clock timed 0.5 s.
EXPECTED = {"nInvert": 11.0, "nPulse": 11.0, "nTime": 0.5}
TIME_TOLERANCE_S = 0.05


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="IoProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1), analog_scales={"AOPROBE": ANALOG_SCALE})
    result = convert([parsed.module], config, sources={"IoProbe": MODULE}, signals=SIGNALS)
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    return result


def payload_schedule(result: ConversionResult) -> int:
    """The schedule CrossArm gave the tool holding the part: the one active once the probe has run."""
    (schedule,) = [s for s in result.grip_payloads if s.load is not None]
    assert schedule.number is not None
    return schedule.number


def active_payload(sysvars: str) -> int | None:
    """$PLST_PARNUM[1] in SYSVARS.VA: the payload schedule group 1 runs with."""
    found = re.search(r"\$PLST_PARNUM\s[^\n]*\n\s*\[1\] = (\d+)", sysvars)
    return int(found[1]) if found else None


def registers(result: ConversionResult) -> dict[str, int]:
    """RAPID variable -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def matches(found: dict[str, float | None]) -> bool:
    time = found.get("nTime")
    return (all(found.get(name) == value for name, value in EXPECTED.items() if name != "nTime")
            and time is not None and abs(time - EXPECTED["nTime"]) <= TIME_TOLERANCE_S)  # fmt: skip


def main() -> None:
    default = Path(__file__).resolve().parents[1] / "tests/fixtures/probes/io"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    out.mkdir(parents=True, exist_ok=True)
    (out / "IoProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    for info in result.programs:
        (out / f"{info.program.name}.LS").write_bytes(write_ls(info.program).encode("ascii"))
        print(f"{info.program.name}.LS")
    for name, number in registers(result).items():
        print(f"  R[{number}] {name} expected {EXPECTED[name]:g}")
    print(f"probe written to {out}")


if __name__ == "__main__":
    main()
