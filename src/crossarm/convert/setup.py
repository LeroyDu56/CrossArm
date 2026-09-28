# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""The tool and user frames of a conversion -> a TP program that sets them on the robot.

The report lists every frame CrossArm derived, as X Y Z W P R. On a large backup that is
dozens of frames, hundreds of numbers typed on the pendant: the slowest step of a
commissioning and the easiest place for a typing error. This program does it instead.

A TP program cannot write a frame from constants, so each value is stored as a P[n] of
the program (the /POS format, validated byte for byte), copied to a position register,
then from it to the frame:

    PR[100]=P[1]
    UTOOL[1]=PR[100]

Both instructions were run on ROBOGUIDE by the pose probe (tools/make_pose_probe.py),
which then reached every converted point within 0.004 mm of RobotStudio's.

The program never writes a frame it should not: a frame whose value is unknown or
unusable, above what the controller holds, or already used by the robot's own programs
is left out, with the reason in a remark and in the report. It starts with a message and a
PAUSE, so that nobody overwrites frames by running it without knowing.
"""

from dataclasses import dataclass, field

from crossarm.convert.config import ConversionConfig
from crossarm.convert.translate import (
    MESSAGE_MAX,
    ComputedFrame,
    ConversionResult,
    FrameInfo,
    ascii_text,
    remark_lines,
)
from crossarm.fanuc.tp import Attributes, CartesianPosition, Instruction, Position, Program

SETUP_NAME = "SETUP_FRAMES"
SETUP_NAME_SHORT = "SETFRAME"  # controllers limited to 8-character program names
START_MESSAGE = "Overwrites UTOOL/UFRAME"
assert len(START_MESSAGE) <= MESSAGE_MAX


@dataclass
class FrameSetup:
    """What the setup program does, for the report."""

    program: Program | None  # None when there is no frame to set
    scratch: int  # the position register it overwrites on the way
    written: list[tuple[str, FrameInfo]] = field(default_factory=list)  # ("UTOOL" | "UFRAME", frame)
    skipped: list[tuple[str, FrameInfo, str]] = field(default_factory=list)  # (kind, frame, why)
    scratch_checked: bool = False  # the target robot's programs were read: the register is free there
    registers: list[ComputedFrame] = field(default_factory=list)  # computed frames it stores in their PR


def scratch_register(config: ConversionConfig) -> tuple[int, bool]:
    """The highest position register no program of the target robot uses (checked), else the last one.

    The frame banks (frames above what the controller holds) take the next free ones down."""
    free, checked = config.free_position_registers()
    return (free[0], checked) if free else (config.limits.get("PR", 100), False)


def build_setup(result: ConversionResult, config: ConversionConfig, name: str) -> FrameSetup:
    scratch, checked = scratch_register(config)
    setup = FrameSetup(None, scratch, scratch_checked=checked)
    lines: list[Instruction] = []
    positions: list[Position] = []
    for kind, frames, resource in (("UTOOL", result.utools, "UTOOL"), ("UFRAME", result.uframes, "UFRAME")):
        limit = config.limits.get(resource)
        taken = config.reserved.get(resource, {})
        for frame in frames:
            why = ""
            if kind == "UFRAME" and frame.number == 0:
                continue  # UFRAME 0 is the world frame: nothing to set
            if frame.frame is None or frame.problem:
                why = frame.problem or "value unknown"
            elif frame.bank is None and limit is not None and frame.number > limit:
                why = f"number above the {limit} the controller holds"
            elif frame.bank is None and frame.number in taken:
                users = ", ".join(taken[frame.number][:3])
                why = f"already used on the robot{' by ' + users if users else ''}: not overwritten"
            if why:
                setup.skipped.append((kind, frame, why))
                for text in remark_lines(f"{kind}[{frame.number}] {frame.rapid_name}: not set"):
                    lines.append(Instruction(text))
                continue
            assert frame.frame is not None
            (x, y, z), (w, p, r) = frame.frame.pose.pos, frame.frame.pose.wpr()
            point = len(positions) + 1
            positions.append(Position(point, 0, 1, CartesianPosition(x, y, z, w, p, r)))
            if frame.bank is not None:  # above what the controller holds: kept in its PR, loaded when used
                for text in remark_lines(f"{frame.rapid_name}: PR[{frame.bank}], {kind}[{frame.slot}] when used"):
                    lines.append(Instruction(text))
                lines.append(Instruction(f"PR[{frame.bank}]=P[{point}]"))
                setup.written.append((kind, frame))
                continue
            for text in remark_lines(f"{kind}[{frame.number}] {frame.rapid_name}"):
                lines.append(Instruction(text))
            lines += [Instruction(f"PR[{scratch}]=P[{point}]"), Instruction(f"{kind}[{frame.number}]=PR[{scratch}]")]
            setup.written.append((kind, frame))
    for computed in result.computed_frames:  # loaded by the programs where the RAPID computes the frame
        if computed.number is None:
            continue
        point = len(positions) + 1
        positions.append(Position(point, 0, 1, CartesianPosition(*computed.values)))
        names = sorted({use[1] for use in computed.uses})
        for text in remark_lines(f"PR[{computed.number}] computed: {', '.join(names)}"):
            lines.append(Instruction(text))
        lines.append(Instruction(f"PR[{computed.number}]=P[{point}]"))
        setup.registers.append(computed)
    if not setup.written and not setup.registers:
        return setup
    head = [Instruction(text) for text in remark_lines("CrossArm: tool and user frames of the ABB backup")]
    head += [Instruction(text) for text in remark_lines(f"PR[{scratch}] is overwritten")]
    head += [Instruction(f"MESSAGE[{START_MESSAGE}]"), Instruction("PAUSE")]
    attributes = Attributes(comment=ascii_text("CrossArm frames")[:16], created=config.timestamp)
    setup.program = Program(name, head + lines, positions, attributes)
    return setup


__all__ = ["SETUP_NAME", "SETUP_NAME_SHORT", "FrameSetup", "build_setup", "scratch_register"]
