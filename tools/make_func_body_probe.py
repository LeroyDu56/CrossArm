# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate and run the FUNC body probe: FUNCs of the backup whose value is only known at run time, converted by
CrossArm into TP programs that write their result in R[AR[n]] / PR[AR[n]] (convert.func_programs).

FuncBodyProbe.mod calls six FUNCs of its own, from a FOR loop (their arguments known at run time only):

    fbSum := fbSum + FbScale(i) * 10       num, two RETURNs (one in an IF: R[AR[2]]=..., END), a local
    IF FbEven(i) ... ELSEIF FbBig(i)       bool as R 1 / 0, called in an IF and again in the ELSEIF (inside ELSE)
    WHILE NOT FbDone() DO                  a FUNC changing data, called before each test of the loop
    fbNest := FbScale(..) + FbOuter(3)     a FUNC calling a FUNC (twice), its own result register kept
    fbP := FbCell(fbLoops, 3); MoveJ fbP     robtarget: PR[AR[3]] written whole, kept by the caller
    MoveL FbCell(1, 1), ...                a move straight to a FUNC's point
    fbB := FbBig(1); IF NOT FbEven(...)    a bool FUNC into a flag, negated in a condition

and stores what they give in registers, worked out here as RAPID does (EXPECTED). ROBOGUIDE runs the converted
FBPROBE: the registers are read from NUMREG.VA, fbX... from the point it moved to, read back with CRobT.

  python tools/make_func_body_probe.py write      the .mod and the .LS in tests/fixtures/probes/funcbody
  python tools/make_func_body_probe.py run        ROBOGUIDE (CROSSARM_RG_WEB as tools/roboguide.py); result stored
  python tools/make_func_body_probe.py check      the stored result against EXPECTED
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

PROBE = ROOT / "tests" / "fixtures" / "probes" / "funcbody"
RESULT = PROBE / "results" / "funcbody_roboguide.txt"
STAMP = datetime(2026, 1, 1)
PROGRAM = "FBPROBE"
EXTAX = "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]"

MODULE = "\r\n".join([  # one RAPID line per item, CRLF like a controller
    "MODULE FuncBodyProbe",
    "    ! CrossArm - FUNC body probe: see tools/make_func_body_probe.py.",
    f"    CONST robtarget fbOrigin:=[[1000,-100,800],[0,0,1,0],[0,0,0,0],{EXTAX}];",
    "    VAR robtarget fbP;",
    "    VAR robtarget fbW;",
    "    VAR bool fbB:=FALSE;",
    *(f"    VAR num {name}:=0;" for name in ("fbSum", "fbFlags", "fbLoops", "fbCount", "fbNest", "fbBias", "fbX", "fbY",
                                              "fbZ", "fbX1", "fbY1", "fbBack", "fbDone")),
    "",
    "    PROC FbProbe()",
    "        fbDone:=0;",
    "        fbSum:=0;",
    "        fbFlags:=0;",
    "        fbLoops:=0;",
    "        fbCount:=0;",
    "        fbBack:=0;",
    "        fbBias:=0.5;",
    "        FOR i FROM 1 TO 4 DO",
    "            fbSum:=fbSum+FbScale(i)*10;",
    "            IF FbEven(i) THEN",
    "                fbFlags:=fbFlags+1;",
    "            ELSEIF FbBig(i) THEN",
    "                fbFlags:=fbFlags+100;",
    "            ENDIF",
    "        ENDFOR",
    "        WHILE NOT FbDone() DO",
    "            fbLoops:=fbLoops+1;",
    "        ENDWHILE",
    "        fbNest:=FbScale(fbLoops)+FbOuter(3);",
    "        fbP:=FbCell(fbLoops,3);",
    "        MoveJ fbP,v500,fine,tool0;",
    "        fbX:=fbP.trans.x;",
    "        fbY:=fbP.trans.y;",
    "        fbZ:=fbP.trans.z;",
    "        MoveL FbCell(1,1),v500,fine,tool0;",
    "        fbW:=CRobT(\\Tool:=tool0\\WObj:=wobj0);",
    "        fbX1:=fbW.trans.x;",
    "        fbY1:=fbW.trans.y;",
    "        fbB:=FbBig(1);",
    "        IF fbB THEN",
    "            fbBack:=1;",
    "        ELSE",
    "            fbBack:=2;",
    "        ENDIF",
    "        IF NOT FbEven(2) THEN",
    "            fbBack:=fbBack+10;",
    "        ENDIF",
    "        IF NOT FbEven(fbBack+1) THEN",
    "            fbBack:=fbBack+100;",
    "        ENDIF",
    "        fbDone:=1;",
    "    ENDPROC",
    "",
    "    FUNC num FbScale(num k)",
    "        VAR num r;",
    "        r:=k*k;",
    "        IF r>5 THEN",
    "            RETURN r-1;",
    "        ENDIF",
    "        RETURN r+fbBias;",
    "    ENDFUNC",
    "",
    "    FUNC bool FbEven(num k)",
    "        IF k MOD 2=0 THEN",
    "            RETURN TRUE;",
    "        ENDIF",
    "        RETURN FALSE;",
    "    ENDFUNC",
    "",
    "    FUNC bool FbBig(num k)",
    "        IF k>2 THEN",
    "            RETURN TRUE;",
    "        ENDIF",
    "        RETURN FALSE;",
    "    ENDFUNC",
    "",
    "    FUNC bool FbDone()",
    "        fbCount:=fbCount+1;",
    "        RETURN fbCount>=3;",
    "    ENDFUNC",
    "",
    "    FUNC num FbOuter(num k)",
    "        VAR num a;",
    "        a:=FbScale(k);",
    "        RETURN a+FbScale(k+1);",
    "    ENDFUNC",
    "",
    "    FUNC robtarget FbCell(num row,num col)",
    "        VAR robtarget p;",
    "        p:=fbOrigin;",
    "        p.trans.x:=fbOrigin.trans.x+(col-1)*20;",
    "        p.trans.y:=fbOrigin.trans.y+(row-1)*30;",
    "        RETURN p;",
    "    ENDFUNC",
    "ENDMODULE",
    "",
])  # fmt: skip

# As RAPID works them out: FbScale(1..4) = 1.5, 4.5, 8, 15 -> fbSum 290; FbEven 2, 4 (+1 each), FbBig 3 (+100);
# FbDone true at its third call: two turns; FbScale(2) + FbOuter(3) = 4.5 + 8 + 15; FbCell(fbLoops = 2, 3) = (1040, -70, 800), FbCell(1,1) the
# origin; FbBig(1) FALSE -> 2, FbEven(2) TRUE -> no +10, FbEven(3) FALSE -> +100.
EXPECTED = {"fbSum": 290.0, "fbFlags": 102.0, "fbLoops": 2.0, "fbCount": 3.0, "fbNest": 27.5, "fbX": 1040.0,
            "fbY": -70.0, "fbZ": 800.0, "fbX1": 1000.0, "fbY1": -100.0, "fbBack": 102.0, "fbDone": 1.0}  # fmt: skip
FUNCS = ("FBSCALE", "FBEVEN", "FBBIG", "FBDONE", "FBOUTER", "FBCELL")


def conversion(folder: Path):
    """FuncBodyProbe.mod converted (no --karel): FBPROBE.LS and one program per FUNC, without a TODO."""
    from crossarm import pipeline
    from crossarm.convert import ConversionConfig

    PROBE.mkdir(parents=True, exist_ok=True)
    (PROBE / "FuncBodyProbe.mod").write_bytes(MODULE.encode("ascii"))
    run = pipeline.run([PROBE / "FuncBodyProbe.mod"], folder, ConversionConfig(timestamp=STAMP), log=lambda _: None)
    result = run.tasks[0].result
    assert result is not None and not [n for n in result.notes if n.kind == "TODO"], result and result.notes
    names = {info.program.name for info in result.programs}
    assert set(FUNCS) <= names, names
    return result


def registers(result) -> dict[str, int]:
    """fbSum... -> the R[n] CrossArm gave it."""
    return {a.rapid_name: a.number for a in result.registers if a.rapid_name in EXPECTED}


def programs(folder: Path) -> list[str]:
    return sorted(p.stem for p in folder.glob("*.LS"))


def write() -> None:
    with tempfile.TemporaryDirectory(prefix="crossarm_funcbody_") as temp:
        result = conversion(Path(temp))
        for path in Path(temp).glob("*.LS"):
            (PROBE / path.name).write_bytes(path.read_bytes())
    for name, number in registers(result).items():
        print(f"  R[{number}] {name} expected {EXPECTED[name]:g}")
    print(f"probe written to {PROBE}")


def measure() -> dict[str, str]:
    import roboguide
    from make_karel_probe import _ftp

    write()
    with tempfile.TemporaryDirectory(prefix="crossarm_funcbody_") as temp:
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
        if "SETUP_FRAMES" in names:
            found["SETUP_FRAMES_run"] = roboguide.run("SETUP_FRAMES", 60, resumes=1)
        roboguide.zero(list(numbers.values()))
        found["run"] = roboguide.run(PROGRAM, 240)
        values = roboguide.numreg()
        for name, number in numbers.items():
            found[name] = f"{values.get(number, float('nan')):g}"
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
    return (f"{len(FUNCS)} FUNCs written as TP programs (num, bool as 1/0, robtarget in PR[AR[n]], RETURN in an IF,"
            f" in a WHILE test, FUNC calling a FUNC): {len(EXPECTED)} values as RAPID")


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
    print(f"FAIL {problem}" if problem else f"funcbody probe: as measured ({summary(found)})")
    return problem


if __name__ == "__main__":
    {"write": write, "run": run, "check": check}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
