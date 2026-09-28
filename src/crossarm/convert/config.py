# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""Conversion settings and the optional user mapping file.

Everything that cannot be derived from the RAPID source (register numbers,
I/O numbers, frame numbers, speed heuristics) has an automatic default and can
be pinned in a JSON file passed with --map:

{
  "registers":       {"nCycles": 10},          RAPID num      -> R[n]
  "flags":           {"bPartPresent": 5},      RAPID bool     -> F[n]
  "digital_outputs": {"doGrip": 3},            RAPID signal   -> DO[n]
  "digital_inputs":  {"diPartReady": 7},       RAPID signal   -> DI[n]
  "group_outputs":   {"goStatus": 1},          RAPID signal   -> GO[n]
  "group_inputs":    {"giCode": 2},            RAPID signal   -> GI[n]
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
}

Names are matched case-insensitively, like RAPID.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from crossarm.convert.configuration import TOOL_PIN_DEFAULT, TOOL_PINS
from crossarm.convert.motion import M20ID_25, MotionProfile

_MAPPING_KEYS = (
    "registers", "flags", "digital_outputs", "digital_inputs", "group_outputs", "group_inputs", "uframes", "utools",
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
    digital_outputs: dict[str, int] = field(default_factory=dict)
    digital_inputs: dict[str, int] = field(default_factory=dict)
    group_outputs: dict[str, int] = field(default_factory=dict)
    group_inputs: dict[str, int] = field(default_factory=dict)
    uframes: dict[str, int] = field(default_factory=lambda: {"WOBJ0": 0})
    utools: dict[str, int] = field(default_factory=dict)

    # First number used by automatic allocation.
    first_register: int = 1
    first_flag: int = 1
    first_digital_output: int = 1
    first_digital_input: int = 1
    first_group_output: int = 1
    first_group_input: int = 1
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
            "zone_mapping", "motion_profile", "frame_registers",
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
        return config
