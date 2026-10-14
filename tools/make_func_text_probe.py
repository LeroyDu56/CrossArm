# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the text FUNC probe: FUNCs of the backup giving a text known at run time only, converted by
CrossArm into TP programs that write their result in SR[AR[n]] (convert.func_programs).

FuncTextProbe.mod puts texts together with three FUNCs of its own:

    ftCode := FtPad(NumToStr(ftPart,0), 5, \\Fill:="0")    a text padded on the left, an optional text argument,
                                                          a FOR loop on StrLen, two RETURNs (one early)
    ftTag := "#" + FtPad(..., 4) + "-" + FtJoin(ftCode, "9")  two FUNCs in one line, put together with texts
    ftLong := FtJoin(FtJoin(ftTag, ftTag), FtRepeat(...))     FUNCs as arguments of a FUNC, a 78-character text
    StrLen(FtPad("", 3)), IF FtPad("12", 2) = "12"            an empty text argument; a FUNC compared

and stores lengths and comparisons in registers, worked out here as RAPID does (EXPECTED). ROBOGUIDE runs the
converted FTPROBE: the registers are read from NUMREG.VA.

FTLIMIT (written by hand) measures how long a string register gets: a text of 38 characters doubled four times
(SR=SR+SR), its length read after each (R[150..153]), R[154]=1 at the end. The run says whether it stops.

  python tools/make_func_text_probe.py write      the .mod and the .LS in tests/fixtures/probes/functext
  python tools/make_func_text_probe.py run        ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); result stored
  python tools/make_func_text_probe.py check      the stored result against EXPECTED
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

PROBE = ROOT / "tests" / "fixtures" / "probes" / "functext"
RESULT = PROBE / "results" / "functext_roboguide.txt"
STAMP = datetime(2026, 1, 1)
PROGRAM = "FTPROBE"
LIMIT = "FTLIMIT"
LIMIT_REGISTERS = (150, 151, 152, 153, 154)

MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE FuncTextProbe",
    "    ! CrossArm - text FUNC probe: see tools/make_func_text_probe.py.",
    "    VAR string ftCode;",
    "    VAR string ftTag;",
    "    VAR string ftLong;",
    *(f"    VAR num {name}:=0;" for name in ("ftPart", "ftHits", "ftLen1", "ftLen2", "ftLen3", "ftLen4", "ftDone")),
    "",
    "    PROC FtProbe()",
    "        ftDone:=0;",
    "        ftHits:=0;",
    "        ftPart:=0;",
    "        FOR k FROM 1 TO 3 DO",
    "            ftPart:=ftPart+7;",
    "            ftCode:=FtPad(NumToStr(ftPart,0),5\\Fill:=\"0\");",
    "            IF ftCode=\"00007\" ftHits:=ftHits+1;",
    "            IF ftCode=\"00021\" ftHits:=ftHits+100;",
    "        ENDFOR",
    "        ftLen1:=StrLen(ftCode);",
    "        ftTag:=\"#\"+FtPad(NumToStr(ftPart,0),4)+\"-\"+FtJoin(ftCode,\"9\");",
    "        ftLen2:=StrLen(ftTag);",
    "        IF ftTag=\"#  21-00021/9\" ftHits:=ftHits+10;",
    "        ftLong:=FtJoin(FtJoin(ftTag,ftTag),FtRepeat(\"12345\",10));",
    "        ftLen3:=StrLen(ftLong);",
    "        ftLen4:=StrLen(FtPad(\"\",3));",
    "        IF FtPad(\"12\",2)=\"12\" ftHits:=ftHits+1000;",
    "        ftDone:=1;",
    "    ENDPROC",
    "",
    "    FUNC string FtPad(string text,num width,\\string Fill)",
    "        VAR string padded;",
    "        VAR string pad:=\" \";",
    "        IF StrLen(text)>=width THEN",
    "            RETURN text;",
    "        ENDIF",
    "        IF Present(Fill) pad:=Fill;",
    "        padded:=text;",
    "        FOR i FROM StrLen(text) TO width-1 DO",
    "            padded:=pad+padded;",
    "        ENDFOR",
    "        RETURN padded;",
    "    ENDFUNC",
    "",
    "    FUNC string FtJoin(string first,string second)",
    "        RETURN first+\"/\"+second;",
    "    ENDFUNC",
    "",
    "    FUNC string FtRepeat(string text,num times)",
    "        VAR string all;",
    "        FOR i FROM 1 TO times DO",
    "            all:=all+text;",
    "        ENDFOR",
    "        RETURN all;",
    "    ENDFUNC",
    "ENDMODULE",
    "",
])  # fmt: skip

# As RAPID works them out: ftPart 7, 14, 21 -> "00007" (+1), "00014", "00021" (+100); ftLen1 5; ftTag "#  21-00021/9"
# (13, +10); ftLong "#  21-00021/9/#  21-00021/9" + "/" + "12345" x 10: 27 + 1 + 50 = 78; FtPad("", 3) "   " (3);
# FtPad("12", 2) "12" by the early RETURN (+1000).
EXPECTED = {"ftHits": 1111.0, "ftLen1": 5.0, "ftLen2": 13.0, "ftLen3": 78.0, "ftLen4": 3.0, "ftDone": 1.0}
FUNCS = ("FTPAD", "FTJOIN", "FTREPEAT")
PIECE = "12345678901234567890123456789012345678"  # 38 characters: the most a TP text argument takes


def conversion(folder: Path):
    """FuncTextProbe.mod converted (no --karel): FTPROBE.LS and one program per FUNC, without a TODO."""
    from crossarm import pipeline
    from crossarm.convert import ConversionConfig

    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "FuncTextProbe.mod").write_bytes(MODULE.encode("ascii"))
    run = pipeline.run([PROBE / "FuncTextProbe.mod"], folder, ConversionConfig(timestamp=STAMP), log=lambda _: None)
    result = run.tasks[0].result
    assert result is not None and not [n for n in result.notes if n.kind == "TODO"], result and result.notes
    names = {info.program.name for info in result.programs}
    assert set(FUNCS) <= names, names
    return result


def registers(result) -> dict[str, int]:
    """ftHits... -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def limit_program() -> str:
    from crossarm.fanuc.ls_writer import write_ls
    from crossarm.fanuc.tp import Attributes, Instruction, Program

    lines = [f"CALL CA_TEXT(20,'{PIECE}',0)"]
    for number in LIMIT_REGISTERS[:-1]:
        lines += ["SR[20]=SR[20]+SR[20]", f"R[{number}]=STRLEN SR[20]"]
    lines.append(f"R[{LIMIT_REGISTERS[-1]}]=1")
    program = Program(LIMIT, Attributes(comment="CrossArm SR length", created=STAMP, modified=STAMP))
    program.lines = [Instruction(text) for text in lines]
    return write_ls(program)


def programs(folder: Path) -> list[str]:
    return sorted(p.stem for p in folder.glob("*.LS"))


def write() -> None:
    with tempfile.TemporaryDirectory(prefix="crossarm_functext_") as temp:
        result = conversion(Path(temp))
        for path in Path(temp).glob("*.LS"):
            (PROBE / path.name).write_bytes(path.read_bytes())
    (PROBE / f"{LIMIT}.LS").write_bytes(limit_program().encode("ascii"))
    for name, number in registers(result).items():
        print(f"  R[{number}] {name} expected {EXPECTED[name]:g}")
    print(f"probe written to {PROBE}")


def measure() -> dict[str, str]:
    import roboguide
    from make_karel_probe import _ftp

    write()
    with tempfile.TemporaryDirectory(prefix="crossarm_functext_") as temp:
        numbers = registers(conversion(Path(temp)))
    names = programs(PROBE)
    found: dict[str, str] = {}
    for name in names:
        roboguide.release(name)
    roboguide.select()
    for name in names:
        _ftp(f"DELE {name.lower()}.tp")
    try:
        for name in names:
            found[f"{name}_load"] = roboguide.load(PROBE / f"{name}.LS") or "loaded"
        roboguide.zero(list(numbers.values()) + list(LIMIT_REGISTERS))
        found["run"] = roboguide.run(PROGRAM, 240)
        found["limit_run"] = roboguide.run(LIMIT, 60)
        values = roboguide.numreg()
        for name, number in numbers.items():
            found[name] = f"{values.get(number, float('nan')):g}"
        for number in LIMIT_REGISTERS:
            found[f"R{number}"] = f"{values.get(number, float('nan')):g}"
        return found
    finally:
        roboguide.select()
        for name in names:
            roboguide.release(name)
        roboguide.select()
        for name in names:
            _ftp(f"DELE {name.lower()}.tp")


def verdict(found: dict[str, str]) -> str:
    wrong = [f"{key[:-5]}: {value}" for key, value in found.items() if key.endswith("_load") and value != "loaded"]
    if found.get("run") != "done":
        wrong.append(f"{PROGRAM}: {found.get('run')}")
    for name, value in EXPECTED.items():
        got = float(found.get(name, "nan"))
        if not abs(got - value) <= 0.01:
            wrong.append(f"{name} {found.get(name)} (RAPID {value:g})")
    return "; ".join(wrong)


def summary(found: dict[str, str]) -> str:
    lengths = ", ".join(found.get(f"R{k}", "?") for k in LIMIT_REGISTERS[:-1])
    return (f"{len(FUNCS)} text FUNCs written as TP programs (SR[AR[n]], optional text, FUNC in a FUNC's arguments,"
            f" early RETURN): {len(EXPECTED)} values as RAPID; SR doubled from 38: {lengths}, {LIMIT}"
            f" {found.get('limit_run')}")


def run() -> str:
    found = measure()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text("".join(f"{k} {v}\n" for k, v in found.items()), encoding="ascii")
    print(RESULT.read_text(encoding="ascii"))
    return check()


def stored() -> dict[str, str]:
    return dict(line.split(" ", 1) for line in RESULT.read_text(encoding="ascii").splitlines())


def check() -> str:
    found = stored()
    problem = verdict(found)
    print(f"FAIL {problem}" if problem else f"functext probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
