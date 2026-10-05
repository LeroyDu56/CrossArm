# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the probe of arrays of bools: kept in blocks of flags, set and read at a fixed index
(F[base+k]) and at an index only known at run time (F[R[n]]).

FlagArrayProbe.mod marks a VAR array of 6 slots in a FOR loop (faSlot{i}:=i>3) in a routine of its own,
counts the slots set in another (FaTally), sets elements at fixed indices, to a condition of other elements, sets a
PERS array of 2 x 3 at indices worked out, then counts what is set. Each result is a number: the converted
programs must give the totals RobotStudio gives.

  ABB (RobotStudio): PROC Probe runs FaProbe and writes the totals to HOME:/flagarrayprobe.txt.
  FANUC (ROBOGUIDE): the converted FAPROBE runs; totals from NUMREG.VA.

Usage:  python tools/make_flag_array_probe.py write    FlagArrayProbe.mod and the .LS in tests/fixtures/probes/flagarrays
        python tools/make_flag_array_probe.py run      RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_flag_array_probe.py check    compare the stored results
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

PROBE = ROOT / "tests" / "fixtures" / "probes" / "flagarrays"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "flagarrayprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "flagarrayprobe_roboguide.txt"
PROGRAM = "FAPROBE"
ROUTINES = ["FaProbe", "FaMark", "FaTally"]
TOTALS = ("faCount", "faPairs", "faFixed", "faFirst")

MODULE = "\r\n".join([
    "MODULE FlagArrayProbe",
    "    ! CrossArm - probe of arrays of bools: see tools/make_flag_array_probe.py.",
    "    VAR bool faSlot{6};",
    "    PERS bool faDone{2,3}:=[[FALSE,FALSE,FALSE],[FALSE,FALSE,FALSE]];",
    "    VAR num faK:=0;",
    *[f"    VAR num {total}:=0;" for total in TOTALS],
    "",
    "    PROC FaMark()",
    "        FOR i FROM 1 TO 6 DO",
    "            faSlot{i}:=i>3;",
    "        ENDFOR",
    "    ENDPROC",
    "",
    "    PROC FaTally()",
    "        FOR i FROM 1 TO 6 DO",
    "            IF faSlot{i} faCount:=faCount+1;",
    "        ENDFOR",
    "    ENDPROC",
    "",
    "    PROC FaProbe()",
    *[f"        {total}:=0;" for total in TOTALS],
    "        FOR i FROM 1 TO 2 DO",
    "            FOR j FROM 1 TO 3 DO",
    "                faDone{i,j}:=FALSE;",
    "            ENDFOR",
    "        ENDFOR",
    "        FaMark;",
    "        faSlot{1}:=TRUE;",
    "        faSlot{2}:=faSlot{5} AND (NOT faSlot{3});",
    "        FaTally;",
    "        faK:=2;",
    "        faDone{faK,faK+1}:=TRUE;",
    "        faDone{1,faK}:=faSlot{faK+1};",
    "        faDone{1,1}:=NOT faDone{2,3};",
    "        faDone{2,1}:=faSlot{faK*3};",
    "        FOR i FROM 1 TO 2 DO",
    "            FOR j FROM 1 TO 3 DO",
    "                IF faDone{i,j} faPairs:=faPairs+i*10+j;",
    "            ENDFOR",
    "        ENDFOR",
    "        IF faSlot{2} AND faDone{2,3} faFixed:=1;",
    "        IF NOT faSlot{3} faFirst:=1;",
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        VAR num v;",
    "        FaProbe;",
    '        Open "HOME:" \\File:="flagarrayprobe.txt", file \\Write;',
    # through a copy: CrossArm takes Write for an instruction that may change what it is given
    *[line for total in TOTALS for line in (f"        v:={total};", f'        Write file, "{total} " \\Num:=v;')],
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# Worked out by hand: slots 4, 5, 6 set by FaMark, 1 at a fixed index, 2 as 5 and not 3: five set. faDone{2,3}
# and faDone{2,1} (slot 6) set, {1,2} as slot 3 and {1,1} as not {2,3} cleared: 23+21. Slot 2 and {2,3}: 1.
# Slot 3 clear: 1.
EXPECTED = {"faCount": 5, "faPairs": 44, "faFixed": 1, "faFirst": 1}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="FlagArrayProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=ROUTINES,
                     sources={"FlagArrayProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """Probe total -> the R[n] CrossArm gave it."""
    numbers = {a.rapid_name.upper(): a.number for a in result.registers}
    return {total: numbers[total.upper()] for total in EXPECTED}


def programs() -> dict[str, str]:
    return {info.program.name: write_ls(info.program) for info in conversion().programs}


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    for stale in PROBE.glob("*.LS"):
        stale.unlink()
    (PROBE / "FlagArrayProbe.mod").write_bytes(MODULE.encode("ascii"))
    for name, text in programs().items():
        (PROBE / f"{name}.LS").write_bytes(text.encode("ascii"))
        print(f"{name}.LS")
    for total, number in registers(conversion()).items():
        print(f"  R[{number}] {total} expected {EXPECTED[total]}")


def read_totals(text: str) -> dict[str, str]:
    totals = {}
    for line in text.splitlines():
        if line.strip():
            name, _, value = line.partition(" ")
            totals[name] = value.strip()
    return totals


def run() -> None:
    import roboguide
    import robotstudio

    write()
    RESULTS.mkdir(parents=True, exist_ok=True)
    home = robotstudio.home()
    print(f"RobotStudio: {robotstudio.run(PROBE / 'FlagArrayProbe.mod', 'Probe', 180, home)}")
    ABB_RESULT.write_text((home / "flagarrayprobe.txt").read_text(encoding="utf-8", errors="replace"),
                          encoding="utf-8")  # fmt: skip
    names = list(programs())
    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)  # a copy from an earlier run: FTP does not replace it
        except Exception:  # noqa: BLE001, S110 - not there
            pass
    for name in names:
        print(f"ROBOGUIDE load {name}: {roboguide.load(PROBE / f'{name}.LS') or 'loaded'}")
    numbers = registers(conversion())
    print(f"ROBOGUIDE zero: {roboguide.zero(list(numbers.values()))}")
    print(f"ROBOGUIDE run {PROGRAM}: {roboguide.run(PROGRAM, 180)}")
    values = roboguide.numreg()
    FANUC_RESULT.write_text("".join(f"{total} {values.get(number, float('nan')):g}\n"
                                    for total, number in numbers.items()), encoding="utf-8")  # fmt: skip
    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)
        except Exception:  # noqa: BLE001, S110
            pass
    check()


def check() -> bool:
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    ok = True
    for total, expected in EXPECTED.items():
        same = float(abb.get(total, "nan")) == float(fanuc.get(total, "nan")) == expected
        ok &= same
        print(f"{total:10s} RobotStudio {abb.get(total)}  ROBOGUIDE {fanuc.get(total)}  expected {expected}  "
              f"{'ok' if same else 'DIFFERENT'}")  # fmt: skip
    return ok


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
