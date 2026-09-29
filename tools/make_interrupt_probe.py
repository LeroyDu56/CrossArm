# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the interrupt probe: do RAPID interrupts, converted to condition monitors, fire as RAPID's do?

PROC IntProbe of IntProbe.mod arms the interrupts RAPID programs use: ISignalDO on a rising edge, on a
falling edge, with \\Single, and IPers on a PERS; then drives the outputs and the PERS, puts one
interrupt to sleep (ISleep) and wakes it (IWatch), pulses the output from a called routine, and
deletes them all (IDelete) before pulsing once more. Each TRAP counts its calls: nHits, nOnce, nFall,
nWatch, and nLast the value IPers saw last; tEdge counts through a routine it calls. Each change is held 0.1 s, as a real signal is: a condition
monitor checks its condition periodically (a change within 0.05 s of MONITOR, or shorter than 0.02 s,
can be missed; measured on ROBOGUIDE).

  FANUC (ROBOGUIDE): the converted INTPROBE runs; the totals are read from NUMREG.VA.
  ABB: the totals RAPID gives are worked out by hand (EXPECTED): the virtual ABB controller has no
  signals for ISignalDO to watch.

Usage:  python tools/make_interrupt_probe.py write     IntProbe.mod and the .LS in tests/fixtures/probes/interrupts
        python tools/make_interrupt_probe.py run       ROBOGUIDE; results stored
        python tools/make_interrupt_probe.py check     compare the stored results
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import parse_text
from crossarm.rapid.eio import Signal

PROBE = ROOT / "tests" / "fixtures" / "probes" / "interrupts"
RESULTS = PROBE / "results"
FANUC_RESULT = RESULTS / "interruptprobe_roboguide.txt"
PROGRAM = "INTPROBE"
ROUTINES = ["IntProbe", "IntPulse", "IntAdd", "tEdge", "tOnce", "tFall", "tWatch", "tShared"]

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE IntProbe",
    "    ! CrossArm - interrupt probe: see tools/make_interrupt_probe.py.",
    "    VAR intnum iEdge;",
    "    VAR intnum iOnce;",
    "    VAR intnum iFall;",
    "    VAR intnum iWatch;",
    "    VAR intnum iUp;",
    "    VAR intnum iDown;",
    "    PERS num nState:=0;",
    "    VAR num nHits:=0;",
    "    VAR num nOnce:=0;",
    "    VAR num nFall:=0;",
    "    VAR num nWatch:=0;",
    "    VAR num nLast:=0;",
    "    VAR num nShared:=0;",
    "",
    "    PROC IntProbe()",
    "        nHits:=0;",
    "        nOnce:=0;",
    "        nFall:=0;",
    "        nWatch:=0;",
    "        nLast:=0;",
    "        nShared:=0;",
    "        nState:=0;",
    "        Reset doProbeA;",
    "        Reset doProbeB;",
    "        IDelete iEdge;",
    "        IDelete iOnce;",
    "        IDelete iFall;",
    "        IDelete iWatch;",
    "        IDelete iUp;",
    "        IDelete iDown;",
    "        CONNECT iEdge WITH tEdge;",
    "        ISignalDO doProbeA,1,iEdge;",
    "        CONNECT iOnce WITH tOnce;",
    "        ISignalDO\\Single,doProbeB,1,iOnce;",
    "        CONNECT iFall WITH tFall;",
    "        ISignalDO doProbeB,0,iFall;",
    "        CONNECT iWatch WITH tWatch;",
    "        IPers nState,iWatch;",
    "        Reset doProbeC;",
    "        CONNECT iUp WITH tShared;",
    "        ISignalDO doProbeC,1,iUp;",
    "        CONNECT iDown WITH tShared;",
    "        ISignalDO doProbeC,0,iDown;",
    "        WaitTime 0.1;",
    "        FOR i FROM 1 TO 3 DO",
    "            SetDO doProbeA,1;",
    "            WaitTime 0.1;",
    "            SetDO doProbeA,0;",
    "            WaitTime 0.1;",
    "        ENDFOR",
    "        SetDO doProbeB,1;",
    "        WaitTime 0.1;",
    "        SetDO doProbeB,0;",
    "        WaitTime 0.1;",
    "        SetDO doProbeB,1;",
    "        WaitTime 0.1;",
    "        SetDO doProbeB,0;",
    "        WaitTime 0.1;",
    "        nState:=5;",
    "        WaitTime 0.1;",
    "        nState:=7;",
    "        WaitTime 0.1;",
    "        SetDO doProbeC,1;",
    "        WaitTime 0.1;",
    "        SetDO doProbeC,0;",
    "        WaitTime 0.1;",
    "        SetDO doProbeC,1;",
    "        WaitTime 0.1;",
    "        ISleep iEdge;",
    "        IntPulse;",
    "        IWatch iEdge;",
    "        WaitTime 0.1;",
    "        IntPulse;",
    "        IDelete iEdge;",
    "        IDelete iFall;",
    "        IDelete iWatch;",
    "        IDelete iUp;",
    "        IDelete iDown;",
    "        SetDO doProbeC,0;",
    "        IntPulse;",
    "        nState:=9;",
    "        WaitTime 0.1;",
    "    ENDPROC",
    "",
    "    PROC IntPulse()",
    "        SetDO doProbeA,1;",
    "        WaitTime 0.1;",
    "        SetDO doProbeA,0;",
    "        WaitTime 0.1;",
    "    ENDPROC",
    "",
    "    PROC IntAdd()",
    "        nHits:=nHits+1;",
    "    ENDPROC",
    "",
    "    TRAP tEdge",
    "        IntAdd;",
    "    ENDTRAP",
    "",
    "    TRAP tOnce",
    "        nOnce:=nOnce+1;",
    "    ENDTRAP",
    "",
    "    TRAP tFall",
    "        nFall:=nFall+1;",
    "    ENDTRAP",
    "",
    "    TRAP tShared",
    "        TEST INTNO",
    "        CASE iUp:",
    "            nShared:=nShared+1;",
    "        CASE iDown:",
    "            nShared:=nShared+10;",
    "        ENDTEST",
    "    ENDTRAP",
    "",
    "    TRAP tWatch",
    "        nWatch:=nWatch+1;",
    "        nLast:=nState;",
    "    ENDTRAP",
    "ENDMODULE",
    "",
])  # fmt: skip

# What RAPID does (worked out by hand from the RAPID reference: ISignalDO fires on each change to the
# value given, \Single once only; IPers on each change of the PERS; ISleep holds an interrupt off,
# IWatch arms it again; IDelete removes it): three pulses on doProbeA, then one from IntPulse after
# IWatch -> 4 (the one while asleep and the one after IDelete do not count); doProbeB up twice -> nOnce 1
# (\Single), down twice -> nFall 2 (it starts down: arming it is no change); nState 5 then 7 -> 2, the
# last seen 7 (9 comes after IDelete).
# tShared, which iUp and iDown share, tells them apart by INTNO: doProbeC up twice (+1 each) and down once
# (+10), the last fall after IDelete not counted -> 12.
EXPECTED = {"nHits": 4.0, "nOnce": 1.0, "nFall": 2.0, "nWatch": 2.0, "nLast": 7.0, "nShared": 12.0}
SIGNALS = {"DOPROBEA": Signal("doProbeA", "DO"), "DOPROBEB": Signal("doProbeB", "DO"),
           "DOPROBEC": Signal("doProbeC", "DO")}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="IntProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=ROUTINES,
                     sources={"IntProbe": MODULE}, signals=SIGNALS)  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """RAPID variable -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "IntProbe.mod").write_bytes(MODULE.encode("ascii"))
    result = conversion()
    for info in result.programs:
        (PROBE / f"{info.program.name}.LS").write_bytes(write_ls(info.program).encode("ascii"))
        print(f"{info.program.name}.LS")
    for name, number in registers(result).items():
        print(f"  R[{number}] {name} expected {EXPECTED[name]:g}")


def read_totals(text: str) -> dict[str, float]:
    totals = {}
    for line in text.splitlines():
        if line.strip():
            name, value = line.split()
            totals[name] = float(value)
    return totals


def run() -> None:
    import roboguide

    write()
    RESULTS.mkdir(parents=True, exist_ok=True)
    numbers = registers(conversion())
    # The TRAPs first: a condition program is refused while the program it calls is not there.
    programs = sorted(PROBE.glob("*.LS"), key=lambda p: (p.stem.startswith("I") and p.stem != PROGRAM, p.stem))
    for path in programs:
        print(f"ROBOGUIDE load {path.stem}: {roboguide.load(path) or 'loaded'}")
    print(f"ROBOGUIDE zero: {roboguide.zero(list(numbers.values()))}")
    print(f"ROBOGUIDE run: {roboguide.run(PROGRAM, 120)}")
    values = roboguide.numreg()
    FANUC_RESULT.write_text("".join(f"{name} {values.get(number, float('nan')):g}\n" for name, number in numbers.items()),
                            encoding="utf-8")  # fmt: skip
    for path in programs:
        roboguide.release(path.stem)
        roboguide.delete(path.stem)
    check()


def check() -> bool:
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    ok = True
    for name, expected in EXPECTED.items():
        same = fanuc.get(name) == expected
        ok &= same
        print(f"{name:7s} ROBOGUIDE {fanuc.get(name)}  RAPID {expected:g}  {'ok' if same else 'DIFFERENT'}")
    return ok


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
