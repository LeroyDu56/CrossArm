# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the system-variable probe: can a TP program read what RAPID's GetSysData and OpMode() read?

RAPID's GetSysData gives the active tool, work object or load, OpMode() the operating mode (AUTO, T1, T2). On a
FANUC they are in system variables: the selected UTOOL and UFRAME ($MNUTOOLNUM[1], $MNUFRAMENUM[1]), the selected
payload schedule ($PLST_PARNUM[1]), the mode select key ($MSKKEY, $MSKKEY_PANL: 3 in AUTO in SYSVARS.VA). Each
program here reads one into a register; the controller loads them all, and stops each on that line (INTP-103
Program error, VARS-034 Variable cannot be accessed: measured on ROBOGUIDE V10.10, R-1000iA/80F), so CrossArm
leaves GetSysData and OpMode() TODO, saying so. The selections a value read would be given back to load too
(`UTOOL_NUM=R[n]`, `UFRAME_NUM=R[n]`, `PAYLOAD[R[n]]`): load only.

  python tools/make_sysvar_probe.py write    the programs, in tests/fixtures/probes/sysvars
  python tools/make_sysvar_probe.py run      ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py): prints the verdict
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program

PROBE = ROOT / "tests" / "fixtures" / "probes" / "sysvars"
FIRST = 150  # the registers the reads go to
READS = {  # program -> the system variable it reads
    "SYSV_UT": "$MNUTOOLNUM[1]",
    "SYSV_UF": "$MNUFRAMENUM[1]",
    "SYSV_PL": "$PLST_PARNUM[1]",
    "SYSV_KEY": "$MSKKEY",
    "SYSV_KEYP": "$MSKKEY_PANL",
}
SELECTS = {"SYSV_SELT": "UTOOL_NUM=R[150]", "SYSV_SELF": "UFRAME_NUM=R[151]", "SYSV_SELL": "PAYLOAD[R[152]]"}
REFUSAL = "VARS-034"


def programs() -> list[Program]:
    stamp = datetime(2026, 1, 1)
    found = []
    for i, (name, variable) in enumerate(READS.items()):
        lines = ["!sysvar probe", f"R[{FIRST + 5}]=0", f"R[{FIRST + i}]={variable}", f"R[{FIRST + 5}]=1"]
        found.append(Program(name, list(map(Instruction, lines)), [], Attributes(comment="sysvar probe", created=stamp)))
    for name, line in SELECTS.items():
        found.append(Program(name, [Instruction("!sysvar probe, load only"), Instruction(line)], [],
                             Attributes(comment="sysvar probe", created=stamp)))  # fmt: skip
    return found


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    for program in programs():
        (PROBE / f"{program.name}.LS").write_bytes(write_ls(program).encode("ascii"))
    print(f"probe written to {PROBE}")


def run() -> str:
    """'' when every program loads and every read stops on VARS-034; else what differs."""
    sys.path.insert(0, str(ROOT / "tools"))
    import roboguide

    write()
    problems = []
    for program in programs():
        try:
            roboguide.delete(program.name)
        except Exception:  # noqa: BLE001, S110 - not there: nothing to delete
            pass
        reason = roboguide.load(PROBE / f"{program.name}.LS")
        if reason:
            problems.append(f"{program.name} not loaded: {reason}")
            continue
        if program.name in READS:
            roboguide.zero(list(range(FIRST, FIRST + 6)))
            status = roboguide.run(program.name, 60)
            values = roboguide.numreg()
            if REFUSAL not in status or values.get(FIRST + 5):
                problems.append(f"{program.name}: {status}, R[{FIRST + 5}]={values.get(FIRST + 5)}")
    for program in programs():
        try:
            roboguide.delete(program.name)
        except Exception:  # noqa: BLE001, S110 - already gone
            pass
    return "; ".join(problems)


def main() -> None:
    if sys.argv[1:] == ["write"]:
        write()
    elif sys.argv[1:] == ["run"]:
        problem = run()
        print(f"FAIL {problem}" if problem else f"{len(READS)} reads stop on {REFUSAL}, {len(SELECTS)} selections load")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
