# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A work object's uframe computed from a pose chosen in the branches of an IF, turned by OrientZYX of a parameter,
then copied (--karel; crossarm.convert.runtime_points, karel_poses, frame_writes; the merge of what the branches
leave known). Measured on ROBOGUIDE: tools/make_branch_frame_probe.py."""

import sys
from datetime import datetime
from pathlib import Path

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.blockers import Blocker
from crossarm.rapid import parse_text

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from make_branch_frame_probe import MODULE

STAMP = datetime(2026, 1, 1)


def run(text: str, karel: bool = True):
    parsed = parse_text(text, path="BF.mod")
    assert parsed.module is not None
    return convert([parsed.module], ConversionConfig(timestamp=STAMP, karel=karel), sources={"BF": text})


def lines(result, name: str) -> list[str]:
    program = next(info.program for info in result.programs if info.program.name == name)
    return [getattr(line, "text", "") for line in program.lines]


def todos(result) -> list[tuple[str, str]]:
    return [(note.message, note.category) for note in result.notes if note.kind == "TODO"]


def test_a_pose_set_in_each_branch_is_kept_in_one_register_and_karel_turns_it():
    result = run(MODULE)
    assert todos(result) == []
    turn = lines(result, "BFTURN")
    base = sorted({t.split(",")[0] for t in turn if t.endswith(("=1000", "=1100"))})
    assert len(base) == 1  # both branches write the same register
    assert [t.split("=")[1] for t in turn if t.startswith("PR[94,")] == ["0", "0", "0", "5", "10", "AR[2]"]
    assert "CALL CA_POSEMULT(95,94,93)" in turn
    assert not any("ufmec" in note.message for note in result.notes if note.kind == "WARNING")  # ufprog TRUE


def test_without_karel_the_frame_stays_todo():
    assert any(category == Blocker.RUNTIME_FRAME or "frame" in message for message, category in todos(run(MODULE, False)))


def test_a_branch_that_exits_does_not_make_the_data_unknown():
    text = """MODULE BF
  PERS wobjdata wA:=[FALSE,TRUE,"",[[500,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  PERS wobjdata wB:=[FALSE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  CONST robtarget pA:=[[100,0,50],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  PROC Main(num nSide)
    VAR pose pBase;
    IF nSide=1 THEN
      pBase:=[[10,0,0],[1,0,0,0]];
    ELSE
      EXIT;
    ENDIF
    wB.uframe:=PoseMult(wA.uframe,pBase);
    MoveL pA,v100,fine,tool0\\WObj:=wB;
  ENDPROC
ENDMODULE
"""
    result = run(text, karel=False)
    assert todos(result) == []  # wB worked out at conversion: the EXIT path does not count


def test_a_field_kept_through_whole_copies_is_still_known():
    """`wC := wB` copies robhold, ufprog, oframe as wB has them: unchanged when wB's are, the frame computed."""
    text = """MODULE BF
  PERS wobjdata wB:=[FALSE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  PERS wobjdata wC:=[FALSE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  CONST robtarget pA:=[[100,0,50],[0,1,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  PROC Init()
    wC:=wB;
  ENDPROC
  PROC Main(num nAngle)
    VAR pose pTurn;
    pTurn.rot:=OrientZYX(nAngle,0,0);
    wC.uframe:=PoseMult([[500,0,0],[1,0,0,0]],pTurn);
    MoveL pA,v100,fine,tool0\\WObj:=wC;
  ENDPROC
ENDMODULE
"""
    result = run(text)
    assert todos(result) == []
    assert any(t.startswith("CALL CA_POSEMULT(") for t in lines(result, "MAIN"))
