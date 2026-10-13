# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Tools built by a FUNC of the backup from a base tool and a RECORD of pos fields (offsets, ZYX angles), the FUNC
copying the base, building two poses part by part and returning PoseMult(PoseMult(base.tframe, peA), peB):
worked out now when the base is fixed, its body copied into the call when the base changes at run time (TP when
only its position does, KAREL when its orientation does), nothing written for a tool no move uses and no program
reads. The expected frames come from an independent computation (quaternions from scratch, ABB OrientZYX = about
Z, then the new Y, then the new X; FANUC W, P, R = Rz(R) Ry(P) Rx(W))."""

import math
import re
from datetime import datetime

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.compute import Layouts, Written
from crossarm.convert.func_inline import inline_body
from crossarm.fanuc.ls_writer import write_ls
from crossarm.rapid import nodes as n
from crossarm.rapid import parse_text
from crossarm.rapid.to_pseudo import format_expr

STAMP = datetime(2026, 1, 1)
DOWN = "[0,0,1,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]"
SYSTEM = """MODULE FT_SYS(SYSMODULE)
  RECORD CutGeom
    pos offNose;
    pos angNose;
    pos offTip;
    pos angTip;
  ENDRECORD
  PERS tooldata tNose:=[TRUE,[[3.2,181.5,307.25],[0.5,0.5,-0.5,0.5]],[14.2,[0,12,95],[1,0,0,0],0.31,0.28,0.12]];
  PERS tooldata tProbe:=[TRUE,[[-6.4,0,262.8],[0.965926,0,0.258819,0]],[3.1,[0,0,60],[1,0,0,0],0,0,0]];
  PERS tooldata tCut:=[TRUE,[[0,0,0],[1,0,0,0]],[14.2,[0,12,95],[1,0,0,0],0.31,0.28,0.12]];
  PERS tooldata tFeel:=[TRUE,[[0,0,0],[1,0,0,0]],[3.1,[0,0,60],[1,0,0,0],0,0,0]];
  PERS tooldata tSpare:=[TRUE,[[0,0,0],[1,0,0,0]],[3.1,[0,0,60],[1,0,0,0],0,0,0]];
  PERS CutGeom geoCut:=[[0,0,-47.5],[0,0,90],[11.5,0,26],[0,17.5,0]];
  PERS CutGeom geoFeel:=[[0,0,-18],[0,0,0],[0,6,0],[0,0,22]];
  PERS num nShim:=0.4;
  PROC InitTools()
    tCut:=Fit(tNose,geoCut);
    tFeel:=Fit(tProbe,geoFeel);
    tSpare:=Fit(tProbe,geoCut);
  ENDPROC
  FUNC tooldata Fit(tooldata tFrom,CutGeom gSheet)
    VAR tooldata tOut;
    VAR pose peNose;
    VAR pose peTip;
    tOut:=tFrom;
    peNose.trans:=gSheet.offNose;
    peNose.rot:=OrientZYX(gSheet.angNose.Z,gSheet.angNose.y,gSheet.angNose.x);
    peTip.trans:=gSheet.offTip;
    peTip.rot:=OrientZYX(gSheet.angTip.Z,gSheet.angTip.y,gSheet.angTip.x);
    tOut.tframe:=PoseMult(PoseMult(tOut.tframe,peNose),peTip);
    RETURN tOut;
  ENDFUNC
ENDMODULE
"""
JOBS = f"""MODULE FT
  CONST robtarget pA:=[[900,-100,500],{DOWN}];
  PROC Shim()
    tProbe.tframe.trans.z:=262.4+nShim;
    nShim:=nShim+0.1;
  ENDPROC
  PROC Cycle()
    Shim;
    InitTools;
    MoveL pA,v100,fine,tProbe;
    MoveL pA,v100,fine,tCut;
    MoveL pA,v100,fine,tFeel;
  ENDPROC
  BODY
ENDMODULE
"""


def conversion(extra: str = "", karel: bool = False, system: str = SYSTEM):
    modules = []
    sources = {}
    for name, text in (("FT_SYS", system), ("FT", JOBS.replace("BODY", extra))):
        parsed = parse_text(text, path=f"{name}.mod")
        assert parsed.module is not None, parsed.diagnostics
        modules.append(parsed.module)
        sources[name] = text
    return convert(modules, ConversionConfig(timestamp=STAMP, karel=karel), sources=sources)


def program(result, name: str) -> list[str]:
    info = next(p for p in result.programs if p.program.name == name)
    return [line.split(":", 1)[1].strip().rstrip(";").strip() for line in write_ls(info.program).splitlines()
            if re.match(r"^\s*\d+:", line)]  # fmt: skip


def todo(result) -> list:
    return [note for note in result.notes if note.kind == "TODO"]


def warnings(result) -> list[str]:
    return [note.message for note in result.notes if note.kind == "WARNING"]


# -- an independent reference ---------------------------------------------------------------------------------------


def _qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)  # fmt: skip


def _axis(index: int, degrees: float):
    half = math.radians(degrees) / 2
    v = [0.0, 0.0, 0.0]
    v[index] = math.sin(half)
    return (math.cos(half), *v)


def _rotate(q, v):
    return _qmul(_qmul(q, (0.0, *v)), (q[0], -q[1], -q[2], -q[3]))[1:]


def _compose(a, b):
    return tuple(p + d for p, d in zip(a[0], _rotate(a[1], b[0]), strict=True)), _qmul(a[1], b[1])


def _zyx(z, y, x):
    return _qmul(_qmul(_axis(2, z), _axis(1, y)), _axis(0, x))


def _expected(base, sheet):
    (off_a, ang_a, off_b, ang_b) = sheet
    t = _compose(_compose(base, (off_a, _zyx(ang_a[2], ang_a[1], ang_a[0]))), (off_b, _zyx(ang_b[2], ang_b[1], ang_b[0])))
    return t[0], t[1]


def _wpr_quat(w, p, r):
    return _qmul(_qmul(_axis(2, r), _axis(1, p)), _axis(0, w))


def _angle(q1, q2) -> float:
    return math.degrees(2 * math.acos(min(1.0, abs(sum(a * b for a, b in zip(q1, q2, strict=True))))))


NOSE = ((3.2, 181.5, 307.25), (0.5, 0.5, -0.5, 0.5))
PROBE_ROT = (0.965926, 0, 0.258819, 0)
GEO_CUT = ((0, 0, -47.5), (0, 0, 90), (11.5, 0, 26), (0, 17.5, 0))
GEO_FEEL = ((0, 0, -18), (0, 0, 0), (0, 6, 0), (0, 0, 22))


# -- tests ----------------------------------------------------------------------------------------------------------


def test_a_tool_built_from_a_fixed_base_and_a_record_is_worked_out_now():
    result = conversion()
    out = program(result, "INITTOOLS")
    loads = [line for line in out if line.startswith("UTOOL[")]
    assert any(re.fullmatch(r"UTOOL\[\d+\]=PR\[\d+\]", line) for line in loads), out
    cut = next(f for f in result.computed_frames if any(use[1] == "tCut" for use in f.uses))
    x, y, z, w, p, r = cut.values
    pos, rot = _expected(NOSE, GEO_CUT)
    assert math.dist((x, y, z), pos) < 0.001
    assert _angle(_wpr_quat(w, p, r), rot) < 0.001


def test_a_tool_built_from_a_base_whose_position_changes_at_run_time_is_moved_in_tp():
    result = conversion()
    out = program(result, "INITTOOLS")
    assert not [n.message for n in todo(result) if n.program == "INITTOOLS"]
    start = out.index(next(line for line in out if line.startswith("!l.18 tFeel.tframe:=PoseMult(")))
    block = out[start + 1 : out.index(next(line for line in out[start:] if line.startswith("!l.") and "tSpare" in line))]
    assert re.fullmatch(r"PR\[\d+\]=UTOOL\[\d+\]", block[0]), block
    shift = [0.0, 0.0, 0.0]
    wpr = {}
    for line in block:
        if (m := re.fullmatch(r"PR\[\d+,([1-3])\]=PR\[\d+,\1\]([+-])([\d.]+)", line)) is not None:
            shift[int(m[1]) - 1] = float(m[3]) * (1 if m[2] == "+" else -1)
        elif (m := re.fullmatch(r"PR\[\d+,([4-6])\]=\(?(-?[\d.]+)\)?", line)) is not None:
            wpr[int(m[1])] = float(m[2])
    assert re.fullmatch(r"UTOOL\[\d+\]=PR\[\d+\]", block[-1]), block
    for z in (262.8, 250.0, 271.3):  # whatever z the base has at run time, the same tool as RAPID's
        base = ((-6.4, 0.0, z), PROBE_ROT)
        pos, rot = _expected(base, GEO_FEEL)
        assert math.dist(pos, tuple(b + s for b, s in zip(base[0], shift, strict=True))) < 0.001
        assert _angle(_wpr_quat(wpr[4], wpr[5], wpr[6]), rot) < 0.001
    assert any("FUNC Fit() of the backup is inlined" in m for m in warnings(result))


def test_a_tool_no_move_selects_and_no_program_reads_is_written_nowhere():
    result = conversion()
    assert any(m.startswith("tool tSpare set at run time") and "nothing written on the FANUC" in m
               for m in warnings(result))  # fmt: skip
    assert "!l.19 tSpare:=Fit(tProbe,geoCut)" in program(result, "INITTOOLS")
    # read by a program: it stays what it was (a tool no move selects: TODO)
    result = conversion("PROC Show()\n    TPWrite \"z\"\\Num:=tSpare.tframe.trans.z;\n  ENDPROC")
    assert any("tSpare" in n.message for n in todo(result) if n.program == "INITTOOLS")


def test_getdataval_with_a_computed_name_reads_the_data_of_its_type():
    reader = "PROC Pick(string sName)\n    VAR {} vOut;\n    GetDataVal sName,vOut;\n  ENDPROC"
    result = conversion(reader.format("num"))
    assert not any("tSpare" in n.message for n in todo(result))
    result = conversion(reader.format("tooldata"))
    assert any("tSpare" in n.message for n in todo(result) if n.program == "INITTOOLS")


def test_reads_count_every_use_but_the_assignments_setting_the_data():
    text = """MODULE R
  PERS tooldata tA:=[TRUE,[[0,0,0],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];
  PERS tooldata tB:=[TRUE,[[0,0,0],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];
  PERS tooldata tC:=[TRUE,[[0,0,0],[1,0,0,0]],[1,[0,0,1],[1,0,0,0],0,0,0]];
  PERS num nZ:=0;
  PROC P()
    tA.tframe.trans.z:=10;
    tB.tframe.trans.z:=tB.tframe.trans.z+1;
    IF nZ>0 tC:=tA;
  ENDPROC
ENDMODULE
"""
    written = Written.of([parse_text(text, path="R.mod").module])
    assert written.read("TA") and written.read("TB") and written.read("NZ") and not written.read("TC")


def test_a_base_turned_at_run_time_that_no_move_selects_is_read_back_by_karel():
    turn = "PROC Turn()\n    tNose.tframe:=PoseMult(tNose.tframe,[[0,0,0],[0.9659258,0,0,0.2588190]]);\n  ENDPROC"
    without = conversion(turn)
    cut = [n for n in todo(without) if n.program == "INITTOOLS" and "tCut" in n.message]
    assert cut and "convert with --karel" in cut[0].message
    result = conversion(turn, karel=True)
    assert not [n.message for n in todo(result) if n.program in ("INITTOOLS", "TURN")]
    out = program(result, "INITTOOLS")
    assert not any("not used by a move" in line for line in out), out
    assert sum(line.startswith("CALL CA_POSEMULT(") for line in out) == 2
    number = next(re.fullmatch(r"PR\[\d+\]=UTOOL\[(\d+)\]", line)[1] for line in out
                  if re.fullmatch(r"PR\[\d+\]=UTOOL\[\d+\]", line))  # fmt: skip
    assert f"UTOOL[{number}]=PR[" in " ".join(program(result, "TURN"))
    assert any("tool tCut computed at run time by KAREL" in m for m in warnings(result))


def test_a_payload_the_base_takes_at_run_time_is_said_not_todo():
    load = "PROC Weigh()\n    tProbe.tload.mass:=nShim*10;\n  ENDPROC"
    result = conversion(load)
    assert not [n.message for n in todo(result) if n.program == "INITTOOLS"]
    assert any(m.startswith("payload of tFeel copied from tProbe") and m.endswith("select the PAYLOAD schedule of"
               " tProbe with this tool") for m in warnings(result)), warnings(result)  # fmt: skip


def test_a_local_pose_set_part_by_part_stands_for_its_parts():
    module = parse_text(SYSTEM, path="FT_SYS.mod").module
    assert module is not None
    routine = next(r for r in module.routines if r.name == "Fit")
    span = n.Span(1, 0)
    call = n.FuncCall(span, "Fit", (n.Arg(span, n.Name(span, "tProbe"), None, False),
                                    n.Arg(span, n.Name(span, "geoFeel"), None, False)))  # fmt: skip
    out = inline_body(routine, call, n.Name(span, "tFeel"), span, layouts=Layouts([module]))
    assert [format_expr(s.target) for s in out] == ["tFeel", "tFeel.tframe"]
    assert format_expr(out[1].value) == (
        "PoseMult(PoseMult(tFeel.tframe, [geoFeel.offNose, OrientZYX(geoFeel.angNose.Z, geoFeel.angNose.y,"
        " geoFeel.angNose.x)]), [geoFeel.offTip, OrientZYX(geoFeel.angTip.Z, geoFeel.angTip.y, geoFeel.angTip.x)])"
    )
