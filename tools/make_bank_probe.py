# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Generate the frame bank probe: are frames past the controller's limit loaded where they should be?

A large backup can use more tool frames than a controller holds (10 on a standard one). CrossArm keeps
the frames past the limit in position registers, stores them there with SETUP_FRAMES.LS, and has the
programs load each one into a reserved number before using it: `UTOOL[2]=PR[98]` then `UTOOL_NUM=2`.

This probe runs the 16 moves of the pose probe (tools/make_pose_probe.py) converted for a controller
of 2 tool frames and 1 user frame, so that two of its three tools and both its work objects go through
a register, several times each and in turn. BANKPROBE.LS stores the frames as the setup program does,
then makes each move with the frame selection CrossArm wrote for it, and records the faceplate pose
after it in PR[51..], as the pose probe does. The flanges must be where RobotStudio puts them.

The flange registers are those of the pose probe, so values left by an earlier run would pass for a
result: BANKPROBE sets R[40] to 0 first and to DONE last, and stores the frames it banks in PR[96..99].
A run counts only if R[40] is DONE and those registers hold the frames.

On ROBOGUIDE: load BANKPROBE.LS, run it, then read POSREG.VA and NUMREG.VA (/md/POSREG.VA, /md/NUMREG.VA).

Usage:  python tools/make_bank_probe.py [output_dir]   (default tests/fixtures/probes/banks)
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_pose_probe import FLANGE_PR, HOME_JOINTS, JOINTS_PR, MOVES, ZERO_TOOL, abb_module

from crossarm.convert import ConversionConfig, ConversionResult, convert
from crossarm.convert.setup import build_setup
from crossarm.fanuc.ls_writer import write_ls
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, JointPosition, Motion, Position, Program
from crossarm.rapid import parse_text

LIMITS = {"UTOOL": 2, "UFRAME": 1, "PR": 100}  # a controller far too small for the probe's frames
MARKER = 40  # R[40]: 0 while the probe runs, DONE once every move was measured
DONE = 7


def conversion() -> ConversionResult:
    module_text = abb_module()
    parsed = parse_text(module_text, path="PoseProbe.mod")
    assert parsed.module is not None, parsed.diagnostics
    config = ConversionConfig(timestamp=datetime(2026, 1, 1))
    config.limits.update(LIMITS)
    result = convert([parsed.module], config, routines=["Path"])
    assert not [n for n in result.notes if n.kind == "TODO"], [n.message for n in result.notes if n.kind == "TODO"]
    result.setup = build_setup(result, config, "SETUP_FRAMES")
    return result


def program() -> Program:
    result = conversion()
    (info,) = result.programs
    assert result.setup is not None and result.setup.program is not None
    setup = result.setup.program
    # The setup program's frame lines, without its MESSAGE and PAUSE; its P[n] renumbered after ours.
    offset = max(p.number for p in info.program.positions)
    positions = list(info.program.positions)
    positions += [Position(p.number + offset, p.uf, p.ut, p.value) for p in setup.positions]
    lines: list[Instruction | Motion] = [Instruction("!CrossArm frame bank probe"), Instruction(f"R[{MARKER}]=0"),
                                         Instruction("!store the frames")]  # fmt: skip
    for line in setup.lines:
        text = line.text  # type: ignore[union-attr]
        if text.startswith(("MESSAGE", "PAUSE", "!")):
            continue
        lines.append(Instruction(_shift(text, offset)))
    home = max(p.number for p in positions) + 1
    zero = home + 1
    positions += [Position(home, 0, ZERO_TOOL, JointPosition(HOME_JOINTS)),
                  Position(zero, 0, 1, CartesianPosition(0, 0, 0, 0, 0, 0))]  # fmt: skip
    lines += [Instruction(f"PR[21]=P[{zero}]"), Instruction(f"UTOOL[{ZERO_TOOL}]=PR[21]"),
              Instruction("!known start"), Instruction("UFRAME_NUM=0"), Instruction(f"UTOOL_NUM={ZERO_TOOL}"),
              Motion("J", f"P[{home}]", "10%", "FINE"),
              Instruction(f"PR[{FLANGE_PR}]=LPOS"), Instruction(f"PR[{JOINTS_PR}]=JPOS")]  # fmt: skip
    # Each move with the selection CrossArm wrote before it: the load from a register, when there is one.
    selection: dict[str, list[str]] = {"UFRAME": [], "UTOOL": []}
    loads: dict[str, str] = {}  # UTOOL[2]=PR[98] seen, waiting for its UTOOL_NUM=2
    move = 0
    for line in info.program.lines:
        if isinstance(line, Motion):
            move += 1
            lines.append(Instruction(f"!move {move}"))
            lines += [Instruction(text) for text in selection["UFRAME"] + selection["UTOOL"]]
            lines += [line, Instruction("UFRAME_NUM=0"), Instruction(f"UTOOL_NUM={ZERO_TOOL}"),
                      Instruction(f"PR[{FLANGE_PR + move}]=LPOS"), Instruction(f"PR[{JOINTS_PR + move}]=JPOS")]  # fmt: skip
            continue
        text = line.text
        for kind in ("UFRAME", "UTOOL"):
            if text.startswith(f"{kind}["):
                loads[kind] = text
            elif text.startswith(f"{kind}_NUM="):
                selection[kind] = [loads.pop(kind), text] if kind in loads else [text]
    assert move == len(MOVES)
    lines.append(Instruction(f"R[{MARKER}]={DONE}"))
    return Program("BANKPROBE", lines, positions, Attributes(comment="bank probe", created=datetime(2026, 1, 1)))


def _shift(text: str, offset: int) -> str:
    """PR[99]=P[3] in the setup program is PR[99]=P[3 + offset] here."""
    if "=P[" not in text:
        return text
    head, number = text.split("=P[")
    return f"{head}=P[{int(number.rstrip(']')) + offset}]"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "tests/fixtures/probes/banks"
    out.mkdir(parents=True, exist_ok=True)
    probe = program()
    (out / "BANKPROBE.LS").write_bytes(write_ls(probe).encode("ascii"))
    result = conversion()
    for kind, frames in (("UTOOL", result.utools), ("UFRAME", result.uframes)):
        for f in frames:
            where = f"PR[{f.bank}] -> {kind}[{f.slot}]" if f.bank else f"{kind}[{f.number}]"
            print(f"  {f.rapid_name:10s} {where}")
    print(f"probe written to {out}")


if __name__ == "__main__":
    main()
