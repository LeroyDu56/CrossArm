# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the string probe: strings the programs change, kept in string registers
(crossarm.convert.strings).

StringProbe.mod counts the letters of a text read one character at a time (StrLen, StrPart, an IF/ELSEIF
on each), runs a state machine whose state is a string (WHILE strState<>"DONE"), looks for texts (StrMatch,
found and not), writes numbers as texts (NumToStr, ValToStr), loads a text of 77 characters, an empty one, one
with an apostrophe, puts a text before itself, sets a string of a routine at each call, and passes texts to a
routine taking one. Each result is a number: the converted programs must give the totals RobotStudio gives.

Forms are loaded only, and what the controller stores read back: the forms it refuses (a text written in a
string register, a block IF or a SELECT on one, an argument of 39 characters, an apostrophe), how it stores an
empty text argument and string register comments, the largest whole number a register line keeps.
STRFACTS (written by hand, ROBOGUIDE only) measures what TP does otherwise than RAPID: texts compared
regardless of case, not of spaces; FINDSTR regardless of case, 0 for an empty pattern; SR=R of a whole
number held as a real; R=SR of a text that is not a number; SUBSTR past the end. RobotStudio writes RAPID's.

  ABB (RobotStudio): PROC Probe runs StrProbe and writes the totals and RAPID's facts to HOME:/stringprobe.txt.
  FANUC (ROBOGUIDE): the converted STRPROBE runs, then STRFACTS; totals from NUMREG.VA.

Usage:  python tools/make_string_probe.py write    StringProbe.mod and the .LS in tests/fixtures/probes/strings
        python tools/make_string_probe.py run      RobotStudio (probe server), then ROBOGUIDE; results stored
        python tools/make_string_probe.py check    compare the stored results
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

PROBE = ROOT / "tests" / "fixtures" / "probes" / "strings"
RESULTS = PROBE / "results"
ABB_RESULT = RESULTS / "stringprobe_robotstudio.txt"
FANUC_RESULT = RESULTS / "stringprobe_roboguide.txt"
FORMS_RESULT = RESULTS / "stringforms_roboguide.txt"
FORMS_DIR = PROBE / "forms"  # apart: most are refused, and probe_all loads every .LS of PROBE
FACTS_DIR = PROBE / "facts"
PROGRAM = "STRPROBE"
FACTS = "STRFACTS"
ROUTINES = ["StrProbe", "StrCount", "StrStep", "StrTake", "StrLocal"]
LONG = "THE-QUICK-BROWN-FOX-JUMPS-OVER-THE-LAZY-DOG-0123456789-PACK-MY-BOX-WITH-FIVE-JUG"
assert len(LONG) == 80 and LONG.upper() == LONG  # RAPID strings hold 80; upper case: no case to tell apart
TOTALS = ("spA", "spO", "spSp", "spBang", "spOther", "spRuns", "spAt", "spMiss", "spNumLen", "spNumOk",
          "spLongLen", "spLongOk", "spSelf", "spEmpty", "spAposLen", "spApos", "spLocal", "spTakeLen", "spTake42",
          "spPart")  # fmt: skip

MODULE = "\r\n".join([
    "MODULE StringProbe",
    "    ! CrossArm - string probe: see tools/make_string_probe.py.",
    "    VAR string strState;",
    "    VAR string strWord;",
    "    VAR string strNum;",
    "    VAR string strLong;",
    "    VAR string strApos;",
    "    VAR string strEmpty;",
    *[f"    VAR num {total}:=0;" for total in TOTALS],
    "",
    "    PROC StrCount()",
    "        VAR num i:=1;",
    "        VAR string ch;",
    "        WHILE i<=StrLen(strWord) DO",
    "            ch:=StrPart(strWord,i,1);",
    '            IF ch="A" THEN',
    "                Incr spA;",
    '            ELSEIF ch="O" THEN',
    "                Incr spO;",
    '            ELSEIF ch=" " THEN',
    "                Incr spSp;",
    '            ELSEIF ch="!" THEN',
    "                Incr spBang;",
    "            ELSE",
    "                Incr spOther;",
    "            ENDIF",
    "            Incr i;",
    "        ENDWHILE",
    "    ENDPROC",
    "",
    "    PROC StrStep()",
    '        IF strState="IDLE" THEN',
    '            strState:="RUN";',
    '        ELSEIF strState="RUN" THEN',
    "            Incr spRuns;",
    '            IF spRuns>=3 strState:="DONE";',
    "        ENDIF",
    "    ENDPROC",
    "",
    "    PROC StrTake(string sIn)",
    "        spTakeLen:=spTakeLen+StrLen(sIn);",
    '        IF sIn="42" Incr spTake42;',
    "    ENDPROC",
    "",
    "    PROC StrLocal()",
    '        VAR string sLoc:="X";',
    '        sLoc:=sLoc+"Y";',
    '        IF sLoc="XY" Incr spLocal;',
    "    ENDPROC",
    "",
    "    PROC StrProbe()",
    *[f"        {total}:=0;" for total in TOTALS],
    '        strState:="IDLE";',
    '        strWord:="LOAD. ROBOT!!";',
    "        StrCount;",
    '        WHILE strState<>"DONE" DO',
    "            StrStep;",
    "        ENDWHILE",
    '        spAt:=StrMatch(strWord,1,"ROBOT");',
    '        spMiss:=StrMatch(strWord,1,"XYZ");',
    '        strNum:=NumToStr(spRuns,0)+"-"+ValToStr(spA);',
    "        spNumLen:=StrLen(strNum);",
    '        IF strNum="3-1" spNumOk:=1;',
    f'        strLong:="{LONG}";',
    "        spLongLen:=StrLen(strLong);",
    f'        IF strLong="{LONG}" spLongOk:=1;',
    '        strState:="<"+strState;',
    '        IF strState="<DONE" spSelf:=1;',
    '        strEmpty:="";',
    "        spEmpty:=StrLen(strEmpty)+10;",
    "        strApos:=\"it's\";",
    "        spAposLen:=StrLen(strApos);",
    "        IF strApos=\"it's\" spApos:=1;",
    "        StrLocal;",
    "        StrLocal;",
    "        StrTake strNum;",
    '        StrTake "42";',
    "        StrTake strState;",
    "        spPart:=StrLen(StrPart(strWord,7,5));",
    "    ENDPROC",
    "",
    "    PROC Probe()",
    "        VAR iodev file;",
    "        VAR num v;",
    "        VAR bool ok;",
    "        StrProbe;",
    '        Open "HOME:" \\File:="stringprobe.txt", file \\Write;',
    # through a copy: CrossArm takes Write for an instruction that may change what it is given, and the
    # totals NumToStr writes must be numbers no instruction but the probe's changes
    *[line for total in TOTALS for line in (f"        v:={total};", f'        Write file, "{total} " \\Num:=v;')],
    '        Write file, "fact.case_equal " \\Bool:="A"="a";',
    '        Write file, "fact.space_equal " \\Bool:="A"="A ";',
    '        Write file, "fact.match_case " \\Num:=StrMatch("load robot",1,"ROBOT");',
    '        Write file, "fact.match_empty " \\Num:=StrMatch("load robot",1,"");',
    '        Write file, "fact.numtostr_half [" + NumToStr(2.5,0) + "]";',
    "        v:=7;",
    '        ok:=StrToVal("12AB",v);',
    '        Write file, "fact.strtoval_12ab " \\Num:=v;',
    '        Write file, "fact.strtoval_12ab_ok " \\Bool:=ok;',
    "        Close file;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip

# Worked out by hand: "LOAD. ROBOT!!" has 1 A, 3 O, 1 space, 2 !, 6 others; the state machine runs 3 times;
# ROBOT at 7, XYZ not found (StrLen+1 = 14); "3-1"; 80 characters; "<DONE"; '' (+10); "it's"; the routine's
# string set at each call (2); texts of 3, 2 and 5 characters passed, one "42"; "ROBOT" (5).
EXPECTED = {"spA": 1, "spO": 3, "spSp": 1, "spBang": 2, "spOther": 6, "spRuns": 3, "spAt": 7, "spMiss": 14,
            "spNumLen": 3, "spNumOk": 1, "spLongLen": 80, "spLongOk": 1, "spSelf": 1, "spEmpty": 10,
            "spAposLen": 4, "spApos": 1, "spLocal": 2, "spTakeLen": 10, "spTake42": 1, "spPart": 5}  # fmt: skip

# Loaded only: what the controller refuses, and how it stores what it takes.
FORMS = {
    "STRF_LIT": ["SR[20]='IDLE'"],
    "STRF_IFBLOCK": ["IF (SR[20]=SR[21]) THEN", "ENDIF"],
    "STRF_IFLIT": ["IF SR[20]='A',JMP LBL[1]", "LBL[1]"],
    "STRF_SELECT": ["SELECT SR[20]='A',JMP LBL[1]", "       ELSE,JMP LBL[1]", "LBL[1]"],
    "STRF_ARG39": ["CALL CA_TEXT(20,'" + "A" * 39 + "',0)"],
    "STRF_APOS": ["CALL CA_TEXT(20,'it''s',0)"],
    "STRF_EMPTY": ["CALL CA_TEXT(20,'',0)"],
    "STRF_CHARS": ["CALL CA_TEXT(20,'say \"hi\", f(x); ok',0)"],
    "STRF_COMMENT": ["SR[20:sState]=SR[21:sOther]"],
    "STRF_INT_MAX": ["R[60]=2147483646"],
    "STRF_INT_OVER": ["R[60]=2147483647"],
    "STRF_INT_MIN": ["R[60]=(-2147483648)"],
}  # fmt: skip

# Written by hand, run on ROBOGUIDE after the probe (CA_TEXT loaded): what TP does otherwise than RAPID.
FACT_LINES = [
    "CALL CA_TEXT(20,'A',0)", "CALL CA_TEXT(21,'a',0)", "CALL CA_TEXT(22,'A ',0)",
    "R[70]=0", "IF SR[20]<>SR[21],JMP LBL[1]", "R[70]=1", "LBL[1]",
    "R[71]=0", "IF SR[20]<>SR[22],JMP LBL[2]", "R[71]=1", "LBL[2]",
    "CALL CA_TEXT(23,'load robot',0)", "CALL CA_TEXT(24,'ROBOT',0)", "R[72]=FINDSTR SR[23],SR[24]",
    "CALL CA_TEXT(24,'x',0)", "SR[24]=SUBSTR SR[24],2,0", "R[73]=FINDSTR SR[23],SR[24]",
    "R[74]=2.5", "R[74]=R[74]+.5", "SR[25]=R[74]", "R[75]=STRLEN SR[25]",
    "CALL CA_TEXT(25,'12AB',0)", "R[76]=7", "R[76]=SR[25]",
    "CALL CA_TEXT(25,'ABC',0)", "R[77]=7", "R[77]=SR[25]",
    "R[78]=STRLEN SR[23]",
]  # fmt: skip
# Each stops the program on ROBOGUIDE (INTP-323 Value overflow), as StrPart past the end stops RAPID's.
STOPPING = {
    "STRF_PAST": ["CALL CA_TEXT(23,'load robot',0)", "SR[25]=SUBSTR SR[23],8,5"],
    "STRF_NONE": ["CALL CA_TEXT(23,'load robot',0)", "SR[25]=SUBSTR SR[23],1,0"],
}
FACT_REGISTERS = {"case_equal": 70, "space_equal": 71, "findstr_case": 72, "findstr_empty": 73, "real_text_length": 75,
                  "number_12ab": 76, "number_abc": 77, "length": 78}  # fmt: skip
# Measured (ROBOGUIDE): 'A' = 'a', 'A' <> 'A '; FINDSTR finds ROBOT in 'load robot' at 6, 0 for an empty pattern;
# SR=R of 2.5+.5 is '3.000000' (8 characters); '12AB' reads as 12, 'ABC' as 0.
FACTS_EXPECTED = {"case_equal": 1, "space_equal": 0, "findstr_case": 6, "findstr_empty": 0, "real_text_length": 8,
                  "number_12ab": 12, "number_abc": 0, "length": 10}  # fmt: skip
# RAPID's, measured (RobotStudio): compared as they are; StrMatch StrLen+1 for an empty pattern too; NumToStr
# rounds (2.5 -> "2"); StrToVal of "12AB" fails and leaves the number.
ABB_FACTS = {"fact.case_equal": "FALSE", "fact.space_equal": "FALSE", "fact.match_case": "11", "fact.match_empty": "11",
             "fact.numtostr_half": "[2]", "fact.strtoval_12ab": "7", "fact.strtoval_12ab_ok": "FALSE"}  # fmt: skip


def conversion() -> ConversionResult:
    parsed = parse_text(MODULE, path="StringProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    result = convert([parsed.module], ConversionConfig(timestamp=datetime(2026, 1, 1)), routines=ROUTINES,
                     sources={"StringProbe": MODULE})  # fmt: skip
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    return result


def registers(result: ConversionResult) -> dict[str, int]:
    """Probe total -> the R[n] CrossArm gave it."""
    numbers = {a.rapid_name.upper(): a.number for a in result.registers}
    return {total: numbers[total.upper()] for total in EXPECTED}


def _program(name: str, lines: list[str], comment: str) -> str:
    return write_ls(Program(name, [Instruction(t) for t in lines], [],
                            Attributes(comment=comment, created=datetime(2026, 1, 1))))  # fmt: skip


def forms() -> dict[str, str]:
    return {name: _program(name, lines, "string probe") for name, lines in FORMS.items()}


def programs() -> dict[str, str]:
    return {info.program.name: write_ls(info.program) for info in conversion().programs}


def write() -> None:
    for folder in (PROBE, FORMS_DIR, FACTS_DIR):
        folder.mkdir(parents=True, exist_ok=True)
        for stale in folder.glob("*.LS"):
            stale.unlink()
    (PROBE / "StringProbe.mod").write_bytes(MODULE.encode("ascii"))
    for name, text in programs().items():
        (PROBE / f"{name}.LS").write_bytes(text.encode("ascii"))
        print(f"{name}.LS")
    for name, text in forms().items():
        (FORMS_DIR / f"{name}.LS").write_bytes(text.encode("ascii"))
    (FACTS_DIR / f"{FACTS}.LS").write_bytes(_program(FACTS, FACT_LINES, "string facts").encode("ascii"))
    for name, lines in STOPPING.items():
        (FACTS_DIR / f"{name}.LS").write_bytes(_program(name, lines, "string facts").encode("ascii"))
    for total, number in registers(conversion()).items():
        print(f"  R[{number}] {total} expected {EXPECTED[total]}")


def read_totals(text: str) -> dict[str, str]:
    totals = {}
    for line in text.splitlines():
        if line.strip():
            name, _, value = line.partition(" ")
            totals[name] = value.strip()
    return totals


def _stored(name: str) -> str:
    """The first line of /MN as the controller stores the program."""
    import roboguide

    ftp = roboguide._ftp()
    chunks: list[bytes] = []
    ftp.retrbinary(f"RETR {name.lower()}.ls", chunks.append)
    ftp.quit()
    body = b"".join(chunks).decode("ascii", errors="replace").split("/MN")[1].split("/POS")[0].strip()
    line = re.sub(r"^ *\d+:", "", body.splitlines()[0]).rstrip(" ;").strip()
    return re.sub(r"\b(R\[\d+):[^\]]*\]", r"\1]", line)  # the cell's register comments: not the probe's


def run() -> None:
    import roboguide
    import robotstudio

    write()
    RESULTS.mkdir(parents=True, exist_ok=True)
    home = robotstudio.home()
    print(f"RobotStudio: {robotstudio.run(PROBE / 'StringProbe.mod', 'Probe', 180, home)}")
    ABB_RESULT.write_text((home / "stringprobe.txt").read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    names = [*programs(), *FORMS, FACTS, *STOPPING]
    for name in names:
        roboguide.release(name)
        try:
            roboguide.delete(name)  # a copy from an earlier run: FTP does not replace it
        except Exception:  # noqa: BLE001, S110 - not there
            pass
    for name in programs():
        reason = roboguide.load(PROBE / f"{name}.LS")
        print(f"ROBOGUIDE load {name}: {reason or 'loaded'}")
    outcome = {}
    for name in FORMS:
        reason = roboguide.load(FORMS_DIR / f"{name}.LS")
        outcome[name] = reason.split(":", 1)[-1].strip() if reason else f"stored {_stored(name)}"
        print(f"ROBOGUIDE form {name}: {outcome[name]}")
    FORMS_RESULT.write_text("".join(f"{name} {outcome[name]}\n" for name in FORMS), encoding="utf-8")
    numbers = registers(conversion())
    print(f"ROBOGUIDE zero: {roboguide.zero(list(numbers.values()))}")
    print(f"ROBOGUIDE run {PROGRAM}: {roboguide.run(PROGRAM, 180)}")
    values = roboguide.numreg()
    lines = [f"{total} {values.get(number, float('nan')):g}\n" for total, number in numbers.items()]
    print(f"ROBOGUIDE load {FACTS}: {roboguide.load(FACTS_DIR / f'{FACTS}.LS') or 'loaded'}")
    print(f"ROBOGUIDE zero: {roboguide.zero(list(FACT_REGISTERS.values()))}")
    print(f"ROBOGUIDE run {FACTS}: {roboguide.run(FACTS, 60)}")
    values = roboguide.numreg()
    lines += [f"fact.{fact} {values.get(number, float('nan')):g}\n" for fact, number in FACT_REGISTERS.items()]
    for name in STOPPING:
        roboguide.load(FACTS_DIR / f"{name}.LS")
        status = roboguide.run(name, 30)
        print(f"ROBOGUIDE run {name}: {status}")
        lines.append(f"stop.{name} {'INTP-323' if 'INTP-323' in status else status.replace(' ', '_')}\n")
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
    for total, expected in EXPECTED.items():
        same = float(abb.get(total, "nan")) == float(fanuc.get(total, "nan")) == expected
        ok &= same
        print(f"{total:10s} RobotStudio {abb.get(total)}  ROBOGUIDE {fanuc.get(total)}  expected {expected}  "
              f"{'ok' if same else 'DIFFERENT'}")  # fmt: skip
    for fact, expected in FACTS_EXPECTED.items():
        same = float(fanuc.get(f"fact.{fact}", "nan")) == expected
        ok &= same
        print(f"TP {fact:16s} {fanuc.get(f'fact.{fact}')}  measured {expected}  {'ok' if same else 'DIFFERENT'}")
    for name in STOPPING:
        same = fanuc.get(f"stop.{name}") == "INTP-323"
        ok &= same
        print(f"TP {name:16s} {fanuc.get(f'stop.{name}')}  measured INTP-323  {'ok' if same else 'DIFFERENT'}")
    for fact, expected in ABB_FACTS.items():
        same = abb.get(fact) == expected
        ok &= same
        print(f"RAPID {fact:24s} {abb.get(fact)}  measured {expected}  {'ok' if same else 'DIFFERENT'}")
    for name, outcome in read_totals(FORMS_RESULT.read_text(encoding="utf-8")).items():
        print(f"{name:15s} {outcome}")
    return ok


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "write"
    {"write": write, "run": run, "check": check}[command]()
