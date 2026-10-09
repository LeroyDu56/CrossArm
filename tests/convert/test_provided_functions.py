# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Functions the integrator provides (external_routines with "returns", crossarm.convert.external): `x := F(args)`
is `CALL PROG(args,k)`, the program writes its result in R[AR[last]] or PR[AR[last]], the caller reads it back;
points are passed by the number of their position register."""

import json
import re
from datetime import datetime

import pytest
from helpers import parse_module

from crossarm.convert import ConversionConfig, build_mapping, build_report, convert
from crossarm.convert.blockers import Blocker
from crossarm.convert.external import ProvidedRoutine
from crossarm.fanuc.tp import Instruction

EXTAX = "[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]"
SOURCE = f"""MODULE M
    PERS tooldata tProbe:=[TRUE,[[0,0,150],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];
    PERS wobjdata wRing:=[FALSE,TRUE,"",[[650,-200,400],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    PERS wobjdata wHub:=[FALSE,TRUE,"",[[700,0,450],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    VAR robtarget pA;
    VAR robtarget pB;
    VAR robtarget pMid;
    PERS num nGap:=0;
    CONST robtarget pRimA:=[[760,0,450],[0,1,0,0],[0,0,0,0],{EXTAX}];
    CONST robtarget pRimB:=[[700,60,450],[0,1,0,0],[0,0,0,0],{EXTAX}];
    CONST robtarget pHole:=[[0,0,20],[0,1,0,0],[0,0,0,0],{EXTAX}];
    PROC main()
        MoveL pRimA,v100,fine,tProbe;
        pA:=CRobT(\\Tool:=tProbe\\WObj:=wobj0);
        MoveL pRimB,v100,fine,tProbe;
        pB:=CRobT(\\Tool:=tProbe\\WObj:=wobj0);
        pMid:=MidPoint(pA,pB);
        nGap:=GapOf(pA,pB);
        wHub.uframe.trans:=pMid.trans;
        wRing.uframe:=FitRing(pRimA,pRimB,nGap);
        tProbe.tframe.trans:=ProbeOffset(2);
        MoveL Offs(pHole,nGap,0,0),v100,fine,tProbe\\WObj:=wHub;
        MoveL pHole,v100,fine,tProbe\\WObj:=wRing;
    ENDPROC
ENDMODULE
"""
RETURNS = {"MidPoint": "robtarget", "GapOf": "num", "FitRing": "pose", "ProbeOffset": "pos"}
STAMP = datetime(2026, 1, 1)


def provided(returns: dict[str, str] = RETURNS) -> dict[str, ProvidedRoutine]:
    return {name.upper(): ProvidedRoutine(name, f"X{name.upper()[:7]}", None, kind) for name, kind in returns.items()}


def run(source: str = SOURCE, returns: dict[str, str] = RETURNS, karel: bool = False):
    cfg = ConversionConfig(timestamp=STAMP, external_routines=provided(returns), karel=karel)
    return convert([parse_module(source)], cfg, sources={"M": source})


def lines(result, program: str = "MAIN") -> list[str]:
    info = next(i for i in result.programs if i.program.name == program)
    return [line.text for line in info.program.lines if isinstance(line, Instruction)]


def todos(result) -> list[str]:
    return [n.message for n in result.notes if n.kind == "TODO"]


def test_the_key_says_what_a_function_returns(tmp_path):
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"external_routines": {"FitRing": {"program": "FIT_RING", "returns": "pose",
                                                                   "arguments": ["robtarget", "pos", "num"]}}}))  # fmt: skip
    cfg = ConversionConfig.from_mapping_file(path, timestamp=STAMP)
    assert cfg.external_routines["FITRING"] == ProvidedRoutine("FitRing", "FIT_RING", ("robtarget", "pos", "num"), "pose")
    path.write_text(json.dumps({"external_routines": {"FitRing": {"program": "FIT_RING", "returns": "tooldata"}}}))
    with pytest.raises(ValueError, match="external_routines.FitRing.returns: expected one of"):
        ConversionConfig.from_mapping_file(path, timestamp=STAMP)


def test_each_result_is_called_for_then_read_back_from_its_register():
    result = run()
    assert todos(result) == []
    text = lines(result)
    calls = [t for t in text if t.startswith("CALL")]
    # points kept in registers passed by their number, the result register's number last
    mid = re.fullmatch(r"CALL XMIDPOIN\((\d+),(\d+),(\d+)\)", calls[0])
    assert mid is not None
    assert f"PR[{mid[1]}]=LPOS" in " ".join(text) and f"=PR[{mid[3]}]" in " ".join(text)
    gap = re.fullmatch(r"CALL XGAPOF\((\d+),(\d+),(\d+)\)", calls[1])
    assert gap is not None and (gap[1], gap[2]) == (mid[1], mid[2])
    assert any(re.fullmatch(rf"R\[\d+:nGap\]=R\[{gap[3]}:result\]", t) for t in text)
    # a pos into the trans of a frame, x, y, z; a pose loaded whole
    assert any(re.fullmatch(r"PR\[\d+,1\]=PR\[\d+,1\]", t) for t in text)
    fit = next(i for i, t in enumerate(text) if t.startswith("CALL XFITRING("))
    assert re.fullmatch(r"CALL XFITRING\(\d+,\d+,R\[\d+:nGap\],(\d+)\)", text[fit])
    number = re.fullmatch(r".*,(\d+)\)", text[fit])[1]  # type: ignore[index]
    assert any(re.fullmatch(rf"UFRAME\[\d+\]=PR\[{number}\]", t) for t in text[fit:])
    offset = next(i for i, t in enumerate(text) if t.startswith("CALL XPROBEOF("))
    pr = re.fullmatch(r"CALL XPROBEOF\(2,(\d+)\)", text[offset])[1]  # type: ignore[index]
    assert [t.split("=")[1] for t in text[offset:] if f"=PR[{pr}," in t] == [f"PR[{pr},{i}]" for i in (1, 2, 3)]
    assert any(re.fullmatch(r"UTOOL\[\d+\]=PR\[\d+\]", t) for t in text[offset:])


def test_the_report_tells_the_program_where_to_write_its_result():
    result = run()
    report = build_report(result, ConversionConfig(timestamp=STAMP, external_routines=provided()), ["M.mod"])
    assert "R[AR[3]]=..." in report  # GapOf(pA, pB): its result register is the third argument
    assert "PR[AR[4]] (x, y, z, w, p, r)" in report  # FitRing(p, p, n)
    assert "x, y, z in PR[AR[2],1..3]" in report  # ProbeOffset(n)
    assert "read PR[AR[1]]" in report
    use = next(u for u in result.provided if u.routine == "FitRing")
    assert use.function and use.returns == "pose" and len(use.calls) == 1


def test_a_provided_function_inside_an_expression_still_stays_todo():
    source = SOURCE.replace("nGap:=GapOf(pA,pB);", "nGap:=GapOf(pA,pB)+1;")
    result = run(source)
    found = [n for n in result.notes if n.category == Blocker.PROVIDED_FUNCTION]
    assert len(found) == 1 and "comes back to `x := GapOf(...)` only" in found[0].message


def test_an_undeclared_function_without_returns_says_how_to_call_it():
    result = run(returns={"GapOf": None})  # type: ignore[dict-item]
    assert any("say what it returns in external_routines.GapOf.returns" in t for t in todos(result))


def test_a_function_the_backup_declares_returns_its_declared_type():
    source = SOURCE.replace("ENDMODULE", """    FUNC num GapOf(robtarget p1,robtarget p2)
        RETURN Distance(p1.trans,p2.trans);
    ENDFUNC
ENDMODULE""")
    cfg = ConversionConfig(timestamp=STAMP, external_routines={"GAPOF": ProvidedRoutine("GapOf", "XGAPOF")})
    result = convert([parse_module(source)], cfg, sources={"M": source})
    assert any(re.fullmatch(r"CALL XGAPOF\(\d+,\d+,\d+\)", t) for t in lines(result))
    use = result.provided[0]
    assert use.returns == "num" and [a.register for a in use.arguments] == ["AR[1]", "AR[2]", "AR[3]"]


def test_a_pose_with_an_oframe_needs_karel_without():
    source = SOURCE.replace('[[650,-200,400],[1,0,0,0]],[[0,0,0],[1,0,0,0]]', '[[650,-200,400],[1,0,0,0]],[[0,0,9],[1,0,0,0]]')
    assert any("oframe is not the identity" in t and "--karel" in t for t in todos(run(source)))
    assert not any("FitRing" in t for t in todos(run(source, karel=True)))


def test_the_written_mapping_offers_missing_functions_with_what_they_return():
    cfg = ConversionConfig(timestamp=STAMP)
    result = convert([parse_module(SOURCE)], cfg, sources={"M": SOURCE})
    offered = json.loads(build_mapping(result, cfg))["external_routines"]
    assert {name: entry["returns"] for name, entry in offered.items()} == RETURNS
    assert offered["MidPoint"]["arguments"] == ["robtarget", "robtarget"] and offered["MidPoint"]["program"] is None
    assert offered["FitRing"]["arguments"] == ["robtarget", "robtarget", "num"]
