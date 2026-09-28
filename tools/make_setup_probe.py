# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the setup probe: does SETUP_FRAMES.LS leave the robot with the frames of the report?

SetupProbe.mod uses three tools and two work objects (rotated, an object frame on one), with
values unlike the pose probe's, so that the frames it leaves on the robot cannot be mistaken
for what is being checked. CrossArm converts it and writes its SETUP_FRAMES.LS; FRAMECHK.LS
then copies every frame back into a position register:

    PR[31..33]=UTOOL[1..3]      PR[41..42]=UFRAME[1..2]

On ROBOGUIDE: load both, run SETUP_FRAMES (resume after its pause), then FRAMECHK, and read
POSREG.VA (the robot's web page, /md/POSREG.VA). tests/convert/test_setup.py compares it
with the frames of the report once it is in tests/fixtures/probes/setup/results/.

Usage:  python tools/make_setup_probe.py [output_dir]   (default tests/fixtures/probes/setup)
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crossarm.convert import ConversionConfig, convert
from crossarm.convert.setup import SETUP_NAME, FrameSetup, build_setup
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, Instruction, Program
from crossarm.rapid import parse_text

TOOL_PR = 30  # PR[31..]: UTOOL[1..] read back
FRAME_PR = 40  # PR[41..]: UFRAME[1..] read back

MODULE = "\r\n".join([  # noqa: FLY002 - one RAPID line per item, CRLF like a controller
    "MODULE SetupProbe",
    "    ! CrossArm - setup probe. Only converted by CrossArm, never run: see tools/make_setup_probe.py.",
    "    PERS tooldata tSetA:=[TRUE,[[12.5,-7.25,241],[1,0,0,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];",
    "    PERS tooldata tSetB:=[TRUE,[[-55,33,160.4],[0.9238795,0,0.3826834,0]],[1,[0,0,50],[1,0,0,0],0,0,0]];",
    "    PERS tooldata tSetC:=[TRUE,[[80,90,95],[0.8660254,0.2588190,0,0.4267767]],[1,[0,0,50],[1,0,0,0],0,0,0]];",
    '    PERS wobjdata wSet1:=[FALSE,TRUE,"",[[640,-420,85],[0.9848078,0,0,-0.1736482]],[[0,0,0],[1,0,0,0]]];',
    '    PERS wobjdata wSet2:=[FALSE,TRUE,"",[[1020,310,-40],[0.9961947,0.0871557,0,0]],[[35,-15,20],[0.9659258,0,0,0.258819]]];',
    "    CONST robtarget pSet:=[[0,0,0],[0,0,1,0],[0,0,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];",
    "    PROC main()",
    "        MoveJ pSet,v100,fine,tSetA\\WObj:=wSet1;",
    "        MoveJ pSet,v100,fine,tSetB\\WObj:=wSet2;",
    "        MoveJ pSet,v100,fine,tSetC;",
    "    ENDPROC",
    "ENDMODULE",
    "",
])  # fmt: skip


def setup() -> FrameSetup:
    parsed = parse_text(MODULE, path="SetupProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    result = convert([parsed.module], config, routines=["main"])
    return build_setup(result, config, SETUP_NAME)


def check_program(frames: FrameSetup) -> Program:
    lines = [Instruction("!CrossArm setup probe: read back")]
    for kind, frame in frames.written:
        base = TOOL_PR if kind == "UTOOL" else FRAME_PR
        lines.append(Instruction(f"PR[{base + frame.number}]={kind}[{frame.number}]"))
    return Program("FRAMECHK", lines, [], Attributes(comment="setup probe", created=datetime(2026, 1, 1)))


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "tests/fixtures/probes/setup"
    out.mkdir(parents=True, exist_ok=True)
    frames = setup()
    assert frames.program is not None
    (out / "SetupProbe.mod").write_bytes(MODULE.encode("ascii"))
    (out / f"{SETUP_NAME}.LS").write_bytes(write_ls(frames.program).encode("ascii"))
    (out / "FRAMECHK.LS").write_bytes(write_ls(check_program(frames)).encode("ascii"))
    for kind, frame in frames.written:
        print(f"{kind}[{frame.number}] {frame.rapid_name}")
    print(f"probe written to {out}")


if __name__ == "__main__":
    main()
