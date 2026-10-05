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
    "--map on this file. Names match the RAPID data, case-insensitively; a routine's FOR counters and "
    "the copies of its parameters are named Routine.name, the registers CrossArm uses itself CROSSARM.name. "
    "Keys starting with _ are ignored."
)
STRING_REGISTERS_README = (
    "String registers SR[n] keeping the strings the programs change (a routine's own named Routine.name). "
    "CROSSARM.TEXT and CROSSARM.TEXT2, taken from the top, are scratch registers: a text written in the "
    "program is loaded into one just before it is compared or passed on, never kept from one instruction to "
    "the next; CROSSARM.TRAPTEXT and CROSSARM.TRAPTEXT2 are those of what a TRAP runs. The controller has 25 "
    "(limits.SR). Change a number to a register the robot does not use."
)
PROGRAMS_README = (
    "TP program names of the programs written that other programs call or arm: a routine by its name, an "
    "interrupt's condition program by the interrupt's (its relay INTERRUPT.relay), CROSSARM.TEXT the program "
    "loading texts. Given back, a conversion keeps them, even when the FANUC robot has a program of that name "
    "by then (said in the report): the programs already loaded call these names."
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
NUMBER_ARRAYS_README = (
    "Arrays of numbers the programs index at run time (nTorque{i}): SETUP_FRAMES keeps each in consecutive "
    "registers from the one given here, read as R[R[n]]. Change it to the first of a free run."
)
FLAG_ARRAYS_README = (
    "Arrays of bools the programs change or index at run time (bSlotFull{i}): SETUP_FRAMES sets each in "
    "consecutive flags from the one given here, read and set as F[R[n]]. Change it to the first of a free run."
)
POINT_ARRAYS_README = (
    "Arrays of points the programs index at run time (pSlot{i}): SETUP_FRAMES keeps each in consecutive "
    "position registers from the one given here, read as PR[R[n]]. Change it to the first of a free run."
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
        ("string_registers", result.string_registers),
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
            if key == "string_registers":
                data["_string_registers"] = STRING_REGISTERS_README
            data[key] = {getattr(a, "key", "") or a.rapid_name: a.number for a in allocations}  # frames: no key
    if result.program_keys:
        data["_programs"] = PROGRAMS_README
        data["programs"] = dict(result.program_keys)
    if any(f.frame is not None and f.frame.robhold and f.number for f in result.utools):
        data["_tool_pin"] = TOOL_PIN_README
        data["tool_pin"] = config.tool_pin
    if result.analog_outputs:
        data["_analog_scales"] = ANALOG_SCALES_README
        data["analog_scales"] = {a.rapid_name: config.analog_scales.get(a.rapid_name.upper())
                                 for a in result.analog_outputs}  # fmt: skip
    data["limits"] = dict(config.limits)
    if not result.string_registers and config.limits.get("SR") == ConversionConfig().limits["SR"]:
        del data["limits"]["SR"]  # no string register used: the file stays as before strings were converted
    wrappers = [use for use in result.move_routines if not use.pure]
    if wrappers:
        data["_move_routines"] = MOVE_ROUTINES_README
        data["move_routines"] = {use.name: use.converted for use in wrappers}
    numbers = [a for a in result.number_arrays if a.base is not None]
    if numbers:
        data["_number_arrays"] = NUMBER_ARRAYS_README
        data["number_arrays"] = {a.name: a.base for a in numbers}
    flags = [a for a in result.flag_arrays if a.base is not None]
    if flags:
        data["_flag_arrays"] = FLAG_ARRAYS_README
        data["flag_arrays"] = {a.name: a.base for a in flags}
    arrays = [a for a in result.point_arrays if a.base is not None]
    if arrays:
        data["_point_arrays"] = POINT_ARRAYS_README
        data["point_arrays"] = {a.name: a.base for a in arrays}
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
