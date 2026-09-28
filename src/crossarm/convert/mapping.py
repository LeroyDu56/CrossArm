# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""ConversionResult -> a mapping file the integrator can edit (crossarm_mapping.json).

Without a mapping file CrossArm numbers everything automatically from 1 up, which
almost never matches the target cell. Writing one by hand means transcribing every
signal, frame and register the programs use, often dozens of numbers, which nobody
does.

So every conversion writes the mapping it just used. Open it, change the numbers to
the ones the controller already has, and convert again with `--map`. The file is
plain JSON, accepted as is by ConversionConfig.from_mapping_file.
"""

import json

from crossarm.convert.config import ConversionConfig
from crossarm.convert.translate import ConversionResult

README = (
    "Numbers CrossArm allocated automatically, in order of first use. "
    "Change them to the ones the controller already uses, then convert again with "
    "--map on this file. Names match the RAPID data, case-insensitively. "
    "Keys starting with _ are ignored."
)
MOVE_ROUTINES_README = (
    "Routines of the backup that make one move and also do something else (see the report, "
    "'Moves made inside routines'). false: their calls stay TODO. true: each call is converted as "
    "that move, and what the routine does besides is left out."
)
FRAME_REGISTERS_README = (
    "Frames the programs compute (a tool built from another, a work object copied...), worked out from the "
    "backup's fixed values: each value X,Y,Z,W,P,R is kept in the position register given here, which "
    "SETUP_FRAMES sets and the programs load into UTOOL/UFRAME where the RAPID computes the frame. "
    "Change a number to a register the robot does not use (see the report, 'Frames computed at conversion time')."
)
ANALOG_SCALES_README = (
    "FANUC analog output counts per unit of the RAPID value, per signal: SetAO aoFlow,4.5 with 409.5 is "
    "AO[n]=1843 (4.5 of 10 V on a 0-4095 module). null: not known, and SetAO on that signal stays TODO. "
    "The counts depend on the FANUC analog module: see its manual."
)
POINT_REGISTERS_README = (
    "Position registers a point is passed to a routine in (a robtarget parameter): the caller sets it "
    "before the CALL, the routine moves to it. CROSSARM.POINT is where a routine offsets one (Offs). Change "
    "a number to a register the robot does not use."
)
PAYLOADS_README = (
    "Payload schedules of a tool holding a part (GripLoad), numbered from the top down past the tools' "
    "own (a tool alone is its UTOOL number). Change a number to a schedule the robot does not use (see the "
    "report, 'Payloads to set up')."
)
TOOL_PIN_README = (
    "The pin hole of the FANUC flange the tool's guide pin goes in, which the adapter plate decides. "
    "-x: where the ABB pin was, tool frames as they are. +x: the ISO 9409-1 hole, tool frames turned "
    "half a turn about z (see the report, 'Tool frames')."
)


def build_mapping(result: ConversionResult, config: ConversionConfig) -> str:
    """The JSON text of a mapping file reproducing this conversion's numbering."""
    tables = [
        ("registers", result.registers),
        ("flags", result.flags),
        ("digital_outputs", result.digital_outputs),
        ("digital_inputs", result.digital_inputs),
        ("group_outputs", result.group_outputs),
        ("group_inputs", result.group_inputs),
        ("analog_outputs", result.analog_outputs),
        ("timers", result.timers),
        ("uframes", result.uframes),
        ("utools", result.utools),
    ]
    data: dict[str, object] = {"_README": README}
    for key, allocations in tables:
        if allocations:  # an empty table would only be noise
            data[key] = {a.rapid_name: a.number for a in allocations}
    if any(f.frame is not None and f.frame.robhold and f.number for f in result.utools):
        data["_tool_pin"] = TOOL_PIN_README
        data["tool_pin"] = config.tool_pin
    if result.analog_outputs:
        data["_analog_scales"] = ANALOG_SCALES_README
        data["analog_scales"] = {a.rapid_name: config.analog_scales.get(a.rapid_name.upper())
                                 for a in result.analog_outputs}  # fmt: skip
    data["limits"] = dict(config.limits)
    wrappers = [use for use in result.move_routines if not use.pure]
    if wrappers:
        data["_move_routines"] = MOVE_ROUTINES_README
        data["move_routines"] = {use.name: use.converted for use in wrappers}
    if result.point_registers:
        data["_point_registers"] = POINT_REGISTERS_README
        data["point_registers"] = {a.rapid_name: a.number for a in result.point_registers}
    gripped = [s for s in result.grip_payloads if s.load is not None and s.number is not None]
    if gripped:
        data["_payloads"] = PAYLOADS_README
        data["payloads"] = {s.key: s.number for s in gripped}
    computed = [f for f in result.computed_frames if f.number is not None]
    if computed:
        data["_frame_registers"] = FRAME_REGISTERS_README
        data["frame_registers"] = {f.key: f.number for f in computed}
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
