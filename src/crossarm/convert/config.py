# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Conversion settings and the optional user mapping file.

Everything that cannot be derived from the RAPID source (register numbers,
I/O numbers, frame numbers, speed heuristics) has an automatic default and can
be pinned in a JSON file passed with --map:

{
  "registers":       {"nCycles": 10},          RAPID num      -> R[n]
  "flags":           {"bPartPresent": 5},      RAPID bool     -> F[n]
  "string_registers": {"sState": 3},          RAPID string the programs change -> SR[n]
  "digital_outputs": {"doGrip": 3},            RAPID signal   -> DO[n]
  "digital_inputs":  {"diPartReady": 7},       RAPID signal   -> DI[n]
  "group_outputs":   {"goStatus": 1},          RAPID signal   -> GO[n]
  "group_inputs":    {"giCode": 2},            RAPID signal   -> GI[n]
  "analog_outputs":  {"aoFlow": 1},            RAPID signal   -> AO[n]
  "timers":          {"ckCycle": 1},           RAPID clock    -> TIMER[n]
  "uframes":         {"wobjFixture": 2},       wobjdata       -> UFRAME n
  "utools":          {"tGripper": 1},          tooldata       -> UTOOL n
  "joint_speed_ref_mm_s": 4500,               RAPID TCP speed that is J 100 % (default: the profile's)
  "zone_mapping": "measured",                  "measured": CNT from the motion profile; "linear": below
  "cnt_per_mm": 1.0,                           zone_mapping "linear": zone radius (mm) * cnt_per_mm
  "motion_profile": {...},                     measured on another robot (tools/probe_motion.py fit)
  "config_mapping": true,
  "tool_pin": "-x",                            FANUC faceplate pin hole the tool's guide pin goes in
  "tpwrite_values": "text",
  "program_name_max_length": 36,
  "limits":          {"UTOOL": 29},            what the controller holds (see ConversionConfig.limits)
  "reserved":        {"DO": [1, 2, 3]},        numbers already in use on the controller
  "move_routines":   {"MoveLSide": true}          convert calls to a routine wrapping a move as that
                                               move (see crossarm.convert.wrappers)
  "frame_registers": {"10,0,185.5,0,0,90": 95}  a frame the programs compute, by its value X,Y,Z,W,P,R
                                               -> the PR SETUP_FRAMES keeps it in (crossarm.convert.compute)
  "analog_scales":   {"aoFlow": 409.5}         FANUC analog output counts per RAPID unit: SetAO aoFlow,4.5
                                               -> AO[1]=1843 (null: not known yet, SetAO stays TODO)
  "payloads":        {"tGrip+lBox": 9}         the payload schedule of a tool holding a part (GripLoad)
  "point_registers": {"PickAt.pPick": 90}      the position register a robtarget parameter is passed in
  "point_arrays":    {"pSlot": 80}             the first of the position registers an array of points is kept in
  "number_arrays":   {"nTorque": 190}          the first of the registers an array of numbers is kept in
  "flag_arrays":     {"bSlotFull": 1001}       the first of the flags an array of bools is kept in
  "programs":        {"PickPart": "PICKPART"}  the TP name of a program CrossArm writes: a routine, an
                                               interrupt's condition program, CROSSARM.TEXT (texts)
  "external_routines": {"WriteLog": {"program": "WRITE_LOG"}}  a routine the integrator provides as a TP or
                                               KAREL program: its calls are CALL WRITE_LOG(...), it is not
                                               written ("program": null: not provided, as CrossArm writes the
                                               candidates); "arguments": ["num", "string", "INOUT num"] types the
                                               arguments of one the backup does not declare
                                               (crossarm.convert.external)
}

Names are matched case-insensitively, like RAPID.
"""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from crossarm.convert.arguments import MAX_ARGS
from crossarm.convert.configuration import TOOL_PIN_DEFAULT, TOOL_PINS
from crossarm.convert.external import ARGUMENT_TYPES, ProvidedRoutine
from crossarm.convert.motion import M20ID_25, MotionProfile

_MAPPING_KEYS = (
    "registers", "flags", "digital_outputs", "digital_inputs", "group_outputs", "group_inputs", "uframes", "utools",
    "analog_outputs", "timers", "string_registers",
)  # fmt: skip


def frame_key(values: Iterable[float]) -> str:
    """A frame value as the mapping file pins it: 'x,y,z,w,p,r', 3 decimals, no '-0.000'."""
    numbers = [round(v, 3) + 0.0 for v in values]
    if len(numbers) != 6:
        raise ValueError("expected 6 numbers")
    return ",".join(f"{v:.3f}" for v in numbers)


@dataclass
class ConversionConfig:
    # Fixed numbers, upper-cased RAPID name -> number.
    registers: dict[str, int] = field(default_factory=dict)
    flags: dict[str, int] = field(default_factory=dict)
    string_registers: dict[str, int] = field(default_factory=dict)
    digital_outputs: dict[str, int] = field(default_factory=dict)
    digital_inputs: dict[str, int] = field(default_factory=dict)
    group_outputs: dict[str, int] = field(default_factory=dict)
    group_inputs: dict[str, int] = field(default_factory=dict)
    analog_outputs: dict[str, int] = field(default_factory=dict)
    timers: dict[str, int] = field(default_factory=dict)  # RAPID clock -> TIMER[n]
    uframes: dict[str, int] = field(default_factory=lambda: {"WOBJ0": 0})
    utools: dict[str, int] = field(default_factory=dict)

    # First number used by automatic allocation.
    first_register: int = 1
    first_flag: int = 1
    first_string_register: int = 1
    first_digital_output: int = 1
    first_digital_input: int = 1
    first_group_output: int = 1
    first_group_input: int = 1
    first_analog_output: int = 1
    first_timer: int = 1
    first_uframe: int = 1
    first_utool: int = 1

    # Heuristics (documented in the conversion report).
    # Speeds and zones, measured on both robots (crossarm.convert.motion, tools/probe_motion.py).
    motion_profile: MotionProfile = M20ID_25
    # How the profile was chosen, for the report: "" the default, "mapping file", or the target robot it
    # was picked for (pipeline, from the FANUC backup). target_robot: that robot, when the backup names it.
    motion_profile_source: str = ""
    target_robot: str | None = None
    joint_speed_ref_mm_s: float = M20ID_25.joint_speed_ref_mm_s  # RAPID TCP speed that is J 100 %
    zone_mapping: str = "measured"  # "measured": the CNT rounding the corner as much; "linear": cnt_per_mm
    cnt_per_mm: float = 1.0  # zone_mapping "linear": zone radius (mm) * cnt_per_mm -> CNT, capped to 100
    config_mapping: bool = True  # CONFIG from ABB confdata; False: default_config everywhere
    joint_mapping: bool = True  # MoveAbsJ joints with measured axis conventions; False: copied as is
    # The FANUC faceplate pin hole the tool's guide pin goes in (crossarm.convert.configuration):
    # "-x" where the ABB pin was, tool frames as they are; "+x" the ISO 9409-1 hole, tools turned.
    tool_pin: str = TOOL_PIN_DEFAULT
    tpwrite_values: str = "text"  # TPWrite showing a value: "text" = MESSAGE[text] + warning, "todo" = TODO
    default_config: str = "N U T, 0, 0, 0"
    program_name_max_length: int = 36  # R-30iB; older controllers: 8

    # How many of each number the controller actually holds. A conversion that allocates
    # past these produces .LS files the controller cannot load, so the report says so
    # instead of letting it be found on site. Options raise several of them, and the
    # I/O counts depend on the cell, so they are all overridable ("limits" in the mapping file).
    limits: dict[str, int] = field(default_factory=lambda: {
        "UFRAME": 9,    # UFRAME_NUM 0-9 on a standard controller
        "UTOOL": 10,    # UTOOL_NUM 1-10
        "TIMER": 10,    # TIMER[1-10]: one times the waits with a MaxTime
        "R": 200,       # numeric registers
        "PR": 100,      # position registers
        "F": 1024,      # flags
        "SR": 25,       # string registers
    })  # fmt: skip

    # Numbers already used on the target controller, which automatic allocation leaves
    # alone: resource ("UTOOL", "R", "DO"...) -> number -> programs using it. Filled from
    # the controller's existing programs (--fanuc), or by hand ("reserved" in the mapping
    # file, as lists of numbers).
    reserved: dict[str, dict[int, tuple[str, ...]]] = field(default_factory=dict)

    # Routines of the backup that wrap one move (crossarm.convert.wrappers), upper-cased name ->
    # convert their calls as that move. Unlisted: only when the routine does nothing else.
    move_routines: dict[str, bool] = field(default_factory=dict)

    # Frames the programs compute, worked out at conversion time: their value as "x,y,z,w,p,r" (3 decimals,
    # as the report and the mapping file write it) -> the position register that keeps it.
    frame_registers: dict[str, int] = field(default_factory=dict)
    # FANUC analog output counts per RAPID unit, upper-cased signal name -> scale: a FANUC AO takes the
    # module's counts (0-4095 for 0-10 V on many), RAPID its logical value. Unknown: SetAO stays TODO.
    analog_scales: dict[str, float] = field(default_factory=dict)
    # Payload schedules of a tool holding a part (GripLoad), upper-cased "TOOL+LOAD" -> PAYLOAD number.
    payloads: dict[str, int] = field(default_factory=dict)
    # The position register a robtarget parameter is passed in, upper-cased "ROUTINE.PARAMETER" -> PR number.
    point_registers: dict[str, int] = field(default_factory=dict)
    # The first position register of an array of points indexed at run time, upper-cased name -> PR number.
    point_arrays: dict[str, int] = field(default_factory=dict)
    # The first numeric register of an array of numbers indexed at run time, upper-cased name -> R number.
    number_arrays: dict[str, int] = field(default_factory=dict)
    # The first flag of an array of bools the programs change or index at run time, upper-cased name -> F number.
    flag_arrays: dict[str, int] = field(default_factory=dict)
    # The TP name of a program CrossArm writes, upper-cased key -> name: a routine by its name, an interrupt's
    # condition program by the interrupt's (its relay "INTERRUPT.RELAY"), "CROSSARM.TEXT" the program loading
    # texts. Programs already on the robot call these names: a later conversion keeps them.
    programs: dict[str, str] = field(default_factory=dict)
    # Routines the integrator provides as TP or KAREL programs (crossarm.convert.external), upper-cased RAPID name
    # -> the program and, for one the backup does not declare, the types of its arguments.
    external_routines: dict[str, ProvidedRoutine] = field(default_factory=dict)

    timestamp: datetime = field(default_factory=lambda: datetime.now().replace(microsecond=0))

    def free_position_registers(self) -> tuple[list[int], bool]:
        """Position registers no program of the target robot uses, highest first, and whether that was checked
        (the robot's programs were read). Unchecked: every register, from the last one down."""
        last = self.limits.get("PR", 100)
        used = self.reserved.get("PR")
        if used is None:
            return list(range(last, 0, -1)), False
        return [number for number in range(last, 0, -1) if number not in used], True

    @classmethod
    def from_mapping_file(cls, path: str | Path, **overrides) -> "ConversionConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        config = cls(**overrides)
        # JSON has no comments: a generated file explains itself in "_README".
        data = {k: v for k, v in data.items() if not k.startswith("_")}
        unknown = set(data) - set(_MAPPING_KEYS) - {
            "joint_speed_ref_mm_s", "cnt_per_mm", "config_mapping", "joint_mapping", "default_config",
            "program_name_max_length", "tpwrite_values", "tool_pin", "limits", "reserved", "move_routines",
            "zone_mapping", "motion_profile", "frame_registers", "analog_scales", "payloads", "point_registers",
            "point_arrays", "number_arrays", "flag_arrays", "programs", "external_routines",
        }  # fmt: skip
        if unknown:
            raise ValueError(f"unknown keys in mapping file: {', '.join(sorted(unknown))}")
        for name, number in data.get("limits", {}).items():
            if not isinstance(number, int):
                raise TypeError(f"limits.{name}: expected an integer, got {number!r}")
            config.limits[name.upper()] = number
        for name, numbers in data.get("reserved", {}).items():
            if not (isinstance(numbers, list) and all(isinstance(n, int) for n in numbers)):
                raise TypeError(f"reserved.{name}: expected a list of integers, got {numbers!r}")
            config.reserved.setdefault(name.upper(), {}).update(dict.fromkeys(numbers, ()))
        for name, convert in data.get("move_routines", {}).items():
            if not isinstance(convert, bool):
                raise TypeError(f"move_routines.{name}: expected true or false, got {convert!r}")
            config.move_routines[name.upper()] = convert
        for value, number in data.get("frame_registers", {}).items():
            if not isinstance(number, int):
                raise TypeError(f"frame_registers.{value}: expected an integer, got {number!r}")
            try:
                config.frame_registers[frame_key(float(v) for v in value.split(","))] = number
            except ValueError as exc:
                raise ValueError(f"frame_registers: {value!r} is not X,Y,Z,W,P,R") from exc
        for name, scale in data.get("analog_scales", {}).items():
            if scale is None:
                continue  # written by CrossArm for the user to fill in
            if not isinstance(scale, int | float) or isinstance(scale, bool):
                raise TypeError(f"analog_scales.{name}: expected a number or null, got {scale!r}")
            config.analog_scales[name.upper()] = float(scale)
        for key, number in data.get("flag_arrays", {}).items():
            if not isinstance(number, int) or isinstance(number, bool):
                raise TypeError(f"flag_arrays.{key}: expected an integer, got {number!r}")
            config.flag_arrays[key.upper()] = number
        for key, number in data.get("number_arrays", {}).items():
            if not isinstance(number, int) or isinstance(number, bool):
                raise TypeError(f"number_arrays.{key}: expected an integer, got {number!r}")
            config.number_arrays[key.upper()] = number
        for key, number in data.get("point_arrays", {}).items():
            if not isinstance(number, int) or isinstance(number, bool):
                raise TypeError(f"point_arrays.{key}: expected an integer, got {number!r}")
            config.point_arrays[key.upper()] = number
        for key, number in data.get("point_registers", {}).items():
            if not isinstance(number, int) or isinstance(number, bool):
                raise TypeError(f"point_registers.{key}: expected an integer, got {number!r}")
            config.point_registers[key.upper()] = number
        for key, number in data.get("payloads", {}).items():
            if not isinstance(number, int) or isinstance(number, bool):
                raise TypeError(f"payloads.{key}: expected an integer, got {number!r}")
            config.payloads[key.upper()] = number
        for key in _MAPPING_KEYS:
            table = getattr(config, key)
            for name, number in data.get(key, {}).items():
                if not isinstance(number, int):
                    raise TypeError(f"{key}.{name}: expected an integer, got {number!r}")
                table[name.upper()] = number
        if "motion_profile" in data:  # measured on the target robot: its joint reference comes with it
            config.motion_profile = MotionProfile.from_dict(data["motion_profile"])
            config.motion_profile_source = "mapping file"
            config.joint_speed_ref_mm_s = config.motion_profile.joint_speed_ref_mm_s
        for key in ("joint_speed_ref_mm_s", "cnt_per_mm", "config_mapping", "joint_mapping", "default_config",
                    "program_name_max_length", "tpwrite_values", "tool_pin", "zone_mapping"):
            if key in data:
                setattr(config, key, data[key])
        if config.tpwrite_values not in ("text", "todo"):
            raise ValueError(f"tpwrite_values: expected 'text' or 'todo', got {config.tpwrite_values!r}")
        if config.zone_mapping not in ("measured", "linear"):
            raise ValueError(f"zone_mapping: expected 'measured' or 'linear', got {config.zone_mapping!r}")
        if config.tool_pin not in TOOL_PINS:
            raise ValueError(f"tool_pin: expected '-x' or '+x', got {config.tool_pin!r}")
        for key, name in data.get("programs", {}).items():
            config.programs[key.upper()] = _program_name(f"programs.{key}", name, config.program_name_max_length)
        external = data.get("external_routines", {})
        if not isinstance(external, dict):
            raise TypeError(f'external_routines: expected {{"Routine": {{"program": "NAME"}}}}, got {external!r}')
        for key, entry in external.items():
            if key.startswith("_") or entry is None:
                continue
            provided = _provided(f"external_routines.{key}", key, entry, config.program_name_max_length)
            if provided is None:
                continue  # "program": null, as CrossArm writes a candidate: not provided
            other = next((k for k, name in config.programs.items() if name == provided.program and k != key.upper()),
                         None)  # fmt: skip
            if other is not None:
                raise ValueError(f"external_routines.{key}: {provided.program} is the name programs gives {other}, a"
                                 " program CrossArm writes")  # fmt: skip
            config.external_routines[key.upper()] = provided
        return config


def _program_name(where: str, name: object, max_length: int) -> str:
    """A TP program name from the mapping file, upper case; ValueError saying why when it is not one."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", name.upper()):
        raise ValueError(f"{where}: expected a TP program name (a letter, then letters, digits and _), got {name!r}")
    if len(name) > max_length:
        raise ValueError(f"{where}: {name} is longer than program_name_max_length ({max_length})")
    return name.upper()


def _provided(where: str, key: str, entry: object, max_length: int) -> ProvidedRoutine | None:
    """An entry of external_routines; None when its program is null (a candidate not provided)."""
    if not isinstance(entry, dict):
        raise TypeError(f'{where}: expected {{"program": "NAME"}}, got {entry!r}')
    fields = {k: v for k, v in entry.items() if not k.startswith("_")}
    unknown = set(fields) - {"program", "arguments"}
    if unknown:
        raise ValueError(f"{where}: unknown keys {', '.join(sorted(unknown))} (expected program, arguments)")
    arguments = fields.get("arguments")
    if arguments is not None:
        if not isinstance(arguments, list) or any(a is not None and a not in ARGUMENT_TYPES for a in arguments):
            raise ValueError(f"{where}.arguments: expected a list of {', '.join(repr(t) for t in ARGUMENT_TYPES)}"
                             f" or null, got {arguments!r}")  # fmt: skip
        if len(arguments) > MAX_ARGS:
            raise ValueError(f"{where}.arguments: {len(arguments)} arguments, a TP CALL takes at most {MAX_ARGS}")
    if fields.get("program") is None:
        return None
    program = _program_name(f"{where}.program", fields["program"], max_length)
    return ProvidedRoutine(key, program, tuple(arguments) if arguments is not None else None)
