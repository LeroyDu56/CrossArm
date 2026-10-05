# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the record probe: data of RECORD types declared in a module, their fields changed by some
routines and read by others, as a state machine keeps its state (crossarm.convert.records).

RecordProbe.mod holds three RECORD types: probectrl (a state, a counter, a bool, a string and a probeparams),
probeparams (a speeddata and a zonedata) and probetally (a num and a bool). VAR probectrl recCtrl is the state
machine: RecInit sets its fields, RecStepA and RecStepB change the state and the counter, RecCount reads the
bool in a routine of its own; the speed and the zone RecInit sets once are those of three moves, timed. PERS
probectrl recSaved is never written: its saved fields are read, a bool among them in an IF. RecCount keeps a
probetally of its own, which RAPID sets to zeros at each call (nBad counts a call where it is not), and
tallyLast at module level; RecProbe copies that one whole into tallyCopy. (Names of their own: a PERS is
global to the task, and the probe server's task has other modules loaded; a RECORD type and a data whose
names differ in case only are the same name in RAPID.)

CrossArm keeps each field the programs change in a register (a bool in a flag) and writes the others as
their value: the converted programs must give the totals RobotStudio gives, and the moves take the time the
speed and zone give. Two variants of the converted RECPROBE give its speed, then its zone too, from registers
(`L P[2] R[n]mm/sec`, `CNT R[m]`), the way a field set to several values could be written; forms for bool and
string fields are loaded only, to see which ones the controller refuses.

  ABB (RobotStudio): PROC Probe runs RecProbe and writes the totals to HOME:/recordprobe.txt.
  FANUC (ROBOGUIDE): the converted RECPROBE runs, then its variants; totals from NUMREG.VA.

Usage:  python tools/make_record_probe.py write    RecordProbe.mod and the .LS in tests/fixtures/probes/records
        python tools/make_record_probe.py run      RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_record_probe.py check    compare the stored results
"""

import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program
from crossarm.rapid import parse_text

PROBE = ROOT / "tests" / "fixtures" / "probes" / "records"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "recordprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "recordprobe_roboguide.txt"
FORMS_RESULT = RESULTS / "recordforms_roboguide.txt"
FORMS_DIR = PROBE / "forms"  # apart: two of them are refused, and probe_all loads every .LS of PROBE
PROGRAM = "RECPROBE"
VARIANTS = ("RECPROBR", "RECPROBZ")
ROUTINES = ["RecProbe", "RecInit", "RecStepA", "RecStepB", "RecCount"]
NINES = "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]"

MODULE = "\r\n".join([
    "MODULE RecordProbe",
    "    ! CrossArm - record probe: see tools/make_record_probe.py.",
    "    RECORD probeparams",
    "        speeddata speed;",
    "        zonedata zone;",
    "    ENDRECORD",
    "    RECORD probectrl",
    "        num state;",
    "        num counter;",
    "        probeparams p;",
    "        bool busy;",
    "        string label;",
    "    ENDRECORD",
    "    RECORD probetally",
    "        num n;",
    "        bool seen;",
    "    ENDRECORD",
    "    VAR probectrl recCtrl;",
    '    PERS probectrl recSaved:=[0,7,[[300,500,5000,1000],[FALSE,20,30,30,3,30,4.5]],FALSE,"SAVED"];',
    "    VAR probetally tallyLast;",
    "    VAR probetally tallyCopy;",
    # flange down in front of either robot, tool0 in the world: reached by the IRB 6700 and the R-1000iA
    f"    CONST robtarget pA:=[[1100,50,1000],[0,1,0,0],[0,0,0,0],{NINES}];",
    f"    CONST robtarget pB:=[[1100,250,1000],[0,1,0,0],[0,0,0,0],{NINES}];",
    f"    CONST robtarget pC:=[[1100,250,800],[0,1,0,0],[0,0,0,0],{NINES}];",
    f"    CONST jointtarget jStart:=[[0,0,0,0,-90,0],{NINES}];",
    "    VAR num nSteps:=0;",
    "    VAR num nBusy:=0;",
    "    VAR num nSaved:=0;",
    "    VAR num nBad:=0;",
    "    VAR num nCopy:=0;",
    "    VAR num nTime:=0;",
    "    VAR num nTime2:=0;",
    "    VAR clock ckProbe;",
    "",
    "    PROC RecInit()",
    "        recCtrl.counter:=0;",
    "        recCtrl.p.speed:=[400,500,5000,1000];",
    "        recCtrl.p.zone:=z50;",
    "        recCtrl.busy:=FALSE;",
    "    ENDPROC",
    "",
    "    PROC RecStepA()",
    "        recCtrl.state:=1;",
    "        recCtrl.counter:=recCtrl.counter+1;",
    "        recCtrl.busy:=TRUE;",
    "    ENDPROC",
    "",
    "    PROC RecStepB()",
    "        IF recCtrl.state=1 THEN",
    "            recCtrl.state:=2;",
    "            recCtrl.counter:=recCtrl.counter+10;",
    "        ENDIF",
    "        recCtrl.busy:=FALSE;",
    "    ENDPROC",
    "",
    "    PROC RecCount()",
    "        VAR probetally tallyNow;",
    "        IF tallyNow.n<>0 nBad:=nBad+1;",
    "        IF recCtrl.busy nBusy:=nBusy+1;",
    "        IF recCtrl.busy tallyLast.seen:=TRUE;",
    "        tallyNow.n:=nSteps+1;",
    "        nSteps:=tallyNow.n;",
    "        tallyLast.n:=nSteps;",
    "    ENDPROC",
    "",
    "    PROC RecProbe()",
    "        nSteps:=0;",
    "        nBusy:=0;",
    "        nSaved:=0;",
    "        nBad:=0;",
    "        nCopy:=0;",
    "        tallyLast.n:=0;",
    "        tallyLast.seen:=FALSE;",
    "        recCtrl.state:=0;",
    "        RecInit;",
    "        WHILE recCtrl.state<>3 DO",
    "            TEST recCtrl.state",
    "            CASE 0:",
    "                RecStepA;",
    "            CASE 1:",
    "                RecStepB;",
    "            DEFAULT:",
    "                recCtrl.state:=3;",
    "            ENDTEST",
    "            RecCount;",
    "        ENDWHILE",
    "        nSaved:=recSaved.counter+recSaved.p.speed.v_tcp;",
    "        IF NOT recSaved.busy nSaved:=nSaved+1000;",
    "        tallyCopy:=tallyLast;",
    "        IF tallyCopy.seen THEN",
    "            nCopy:=tallyCopy.n+100;",
    "        ELSE",
    "            nCopy:=tallyCopy.n;",
    "        ENDIF",
    "        MoveAbsJ jStart,v1000,fine,tool0;",
    "        MoveJ pA,v1000,fine,tool0;",
    "        ClkReset ckProbe;",
    "        ClkStart ckProbe;",
    "        MoveL pB,recCtrl.p.speed,fine,tool0;",
    "        ClkStop ckProbe;",
    "        nTime:=ClkRead(ckProbe);",
    "        ClkReset ckProbe;",
    "        ClkStart ckProbe;",
    "        MoveL pC,recCtrl.p.speed,recCtrl.p.zone,tool0;",
    "        MoveL pA,recCtrl.p.speed,fine,tool0;",
    "        ClkStop ckProbe;",
    "        nTime2:=ClkRead(ckProbe);",
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        ConfJ\\Off;",
    "        ConfL\\Off;",
    '        recCtrl.label:="IDLE";',
    "        RecProbe;",
    '        Open "HOME:" \\File:="recordprobe.txt", file \\Write;',
    '        Write file, "state " \\Num:=recCtrl.state;',
    '        Write file, "counter " \\Num:=recCtrl.counter;',
    '        Write file, "nSteps " \\Num:=nSteps;',
    '        Write file, "nBusy " \\Num:=nBusy;',
    '        Write file, "nSaved " \\Num:=nSaved;',
    '        Write file, "nBad " \\Num:=nBad;',
    '        Write file, "nCopy " \\Num:=nCopy;',
    '        Write file, "nTime " \\Num:=nTime;',
    '        Write file, "nTime2 " \\Num:=nTime2;',
    '        Write file, "label " + recCtrl.label;',
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# Worked out by hand: StepA (state 1, counter 1, busy: counted, tallyLast seen), StepB (state 2, counter 11),
# DEFAULT (state 3): three passes, one busy, tallyNow zero at each call; nSaved 7 + 300 + 1000 (busy FALSE);
# the copy of tallyLast: 3 passes, seen: 103.
EXPECTED = {"state": 3.0, "counter": 11.0, "nSteps": 3.0, "nBusy": 1.0, "nSaved": 1307.0, "nBad": 0.0,
            "nCopy": 103.0}  # fmt: skip
TIMES = ("nTime", "nTime2")
DATA = {"state": "recCtrl.state", "counter": "recCtrl.counter"}  # totals kept in a record, by register name

# Loaded only: what the controller refuses for a bool or a string field.
FORMS = {
    "RECF_BOOL_SET": ["F[20]=(ON)", "F[20]=(OFF)"],
    "RECF_BOOL_COND": ["F[20]=(R[20]>0)"],
    "RECF_BOOL_AND": ["F[20]=(DI[1] AND R[20]>0)"],
    "RECF_BOOL_IF": ["IF (F[20]),JMP LBL[1]", "LBL[1]"],
    "RECF_BOOL_COPY": ["F[20]=(F[21])"],
    "RECF_STR_LIT": ["SR[20]='IDLE'"],
    "RECF_STR_ARG": ["SR[20]=AR[1]"],
    "RECF_STR_CALL": ["CALL RECF_STR_ARG('IDLE')"],
    "RECF_STR_COPY": ["SR[21]=SR[20]"],
    "RECF_STR_IF": ["IF (SR[20]=SR[21]),JMP LBL[1]", "LBL[1]"],
    "RECF_STR_IND": ["SR[R[20]]=AR[1]"],
}


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="RecordProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=ROUTINES,
                     sources={"RecordProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """Probe total -> the R[n] CrossArm gave it."""
    numbers = {a.rapid_name.upper(): a.number for a in result.registers}
    return {total: numbers[DATA.get(total, total).upper()] for total in (*EXPECTED, *TIMES)}


def variants(main: str, result: ConversionResult) -> dict[str, str]:
    """RECPROBE with its speed, then its zone too, from registers: two programs of other names."""
    free = max(a.number for a in result.registers) + 1
    speed_line = re.compile(r"^( +\d+:)(L P\[\d+\]) 400mm/sec", re.MULTILINE)
    by_speed = speed_line.sub(rf"\1\2 R[{free}]mm/sec", main)
    cnt = re.search(r" CNT(\d+)", by_speed)
    assert cnt is not None, "the move with the zone is not a CNT"
    by_zone = by_speed.replace(cnt[0], f" CNT R[{free + 1}]")
    out = {}
    for name, text, sets in (("RECPROBR", by_speed, [f"R[{free}]=400"]),
                             ("RECPROBZ", by_zone, [f"R[{free}]=400", f"R[{free + 1}]={cnt[1]}"])):  # fmt: skip
        out[name] = _prepend(text.replace(f"/PROG  {PROGRAM}", f"/PROG  {name}", 1), sets)
    return out


def _prepend(text: str, lines: list[str]) -> str:
    """The program with `lines` first in /MN, numbered again."""
    head, rest = text.split("/MN\r\n", 1)
    body, tail = rest.split("/POS", 1)
    old = [re.sub(r"^ *\d+:", "", line) for line in body.split("\r\n") if line.strip()]
    new = [f"  {line} ;" for line in lines] + old
    numbered = "".join(f"{i:4d}:{line}\r\n" for i, line in enumerate(new, 1))
    head = re.sub(r"LINE_COUNT\t= \d+;", f"LINE_COUNT\t= {len(new)};", head)
    return f"{head}/MN\r\n{numbered}/POS{tail}"


def forms() -> dict[str, str]:
    return {name: write_ls(Program(name, [Instruction(t) for t in lines], [],
                                   Attributes(comment="record probe", created=datetime(2026, 1, 1))))
            for name, lines in FORMS.items()}  # fmt: skip


def programs() -> dict[str, str]:
    result = conversion()
    out = {info.program.name: write_ls(info.program) for info in result.programs}
    out.update(variants(out[PROGRAM], result))
    return out


def write() -> None:
    PROBE.mkdir(parents=True, exist_ok=True)
    FORMS_DIR.mkdir(exist_ok=True)
    for stale in [*PROBE.glob("*.LS"), *FORMS_DIR.glob("*.LS"), PROBE / "RecordFlat.mod"]:
        stale.unlink(missing_ok=True)
    (PROBE / "RecordProbe.mod").write_bytes(MODULE.encode("ascii"))
    for name, text in {**programs(), **forms()}.items():
        (FORMS_DIR if name in FORMS else PROBE).joinpath(f"{name}.LS").write_bytes(text.encode("ascii"))
        print(f"{name}.LS")
    for total, number in registers(conversion()).items():
        print(f"  R[{number}] {total} expected {EXPECTED.get(total, 'a time')}")


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
    print(f"RobotStudio: {robotstudio.run(PROBE / 'RecordProbe.mod', 'Probe', 180, home)}")
    ABB_RESULT.write_text((home / "recordprobe.txt").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    numbers = registers(conversion())
    names = [*programs(), *FORMS]
    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)  # a copy from an earlier run: FTP does not replace it
        except Exception:  # noqa: BLE001, S110 - not there
            pass
    refused = {}
    for name in names:
        refused[name] = roboguide.load((FORMS_DIR if name in FORMS else PROBE) / f"{name}.LS")
        print(f"ROBOGUIDE load {name}: {refused[name] or 'loaded'}")
    FORMS_RESULT.write_text("".join(f"{name} {refused[name] or 'loaded'}\n" for name in FORMS), encoding="utf-8")
    lines = []
    for program in (PROGRAM, *VARIANTS):
        if refused.get(program):
            lines.append(f"{program}.refused {refused[program]}\n")
            continue
        print(f"ROBOGUIDE zero: {roboguide.zero(list(numbers.values()))}")
        print(f"ROBOGUIDE run {program}: {roboguide.run(program, 180)}")
        values = roboguide.numreg()
        lines += [f"{program}.{total} {values.get(number, float('nan')):g}\n" for total, number in numbers.items()]
    FANUC_RESULT.write_text("".join(lines), encoding="utf-8")
    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)
        except Exception:  # noqa: BLE001, S110 - refused: never loaded
            pass
    check()


def check() -> bool:
    abb = read_totals(ABB_RESULT.read_text(encoding="utf-8"))
    fanuc = read_totals(FANUC_RESULT.read_text(encoding="utf-8"))
    ok = True
    for program in (PROGRAM, *VARIANTS):
        for total, expected in EXPECTED.items():
            got = fanuc.get(f"{program}.{total}")
            same = float(abb.get(total, "nan")) == float(got or "nan") == expected
            ok &= same
            print(f"{program}.{total:8s} RobotStudio {abb.get(total)}  ROBOGUIDE {got}  expected {expected:g}  "
                  f"{'ok' if same else 'DIFFERENT'}")  # fmt: skip
        for total in TIMES:
            a, b = float(abb.get(total, "nan")), float(fanuc.get(f"{program}.{total}") or "nan")
            print(f"{program}.{total:8s} RobotStudio {a:.3f} s  ROBOGUIDE {b:.3f} s  ({100 * (b - a) / a:+.0f} %)")
    print(f"label: RobotStudio {abb.get('label')!r}")
    for name, outcome in read_totals(FORMS_RESULT.read_text(encoding="utf-8")).items():
        print(f"{name:15s} {outcome}")
    return ok


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
