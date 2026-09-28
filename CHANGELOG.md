# Changelog

All notable changes to CrossArm, the ABB RAPID to FANUC TP converter. Dates are release dates;
downloads are on the [releases page](https://github.com/LeroyDu56/CrossArm/releases).

## Unreleased

### Converts
- `TEST` / `CASE` / `DEFAULT` to `SELECT`: one line per `CASE` value, a `CASE` that only calls a
  routine calls it on its `SELECT` line, the other branches behind labels. A `TEST` on a routine's
  argument or a group input selects a copy of it; a `TEST` on a constant keeps its branch only. A
  `TEST` on a string, or a `CASE` value only known at run time, stays TODO. A `FUNC` choosing its
  value with `TEST` is run at conversion time like one using `IF`.
- `PulseDO` to `DO[n]=PULSE,0.2sec`, its length rounded to the tenth of a second FANUC takes (a
  warning when that moves it); `InvertDO` to `DO[n]=(!DO[n])`; RAPID clocks (`ClkReset`, `ClkStart`,
  `ClkStop`, `ClkRead`) to `TIMER[n]`, apart from the timer the waits use.
- `SetAO` to `AO[n]=`, in the FANUC module's counts: the scale per signal comes from the mapping
  file (`analog_scales`, written with `null` for each analog output until it is filled in); without
  it the line stays TODO rather than write a value in the wrong unit.
- `GripLoad` to `PAYLOAD[n]`. A FANUC payload schedule is all the flange carries, so a tool holding a
  part has one of its own: CrossArm works out the two masses together, their common centre of
  gravity and the inertia about it, lists the schedule in the report, and numbers it from the top
  down past the tools' own; `GripLoad load0` goes back to the tool's schedule, its UTOOL number. The
  tool is the one the moves after it use, else the one selected, else the task's only tool.
- Motion settings: `ConfL`, `ConfJ`, `SingArea` and `CirPathMode` are left out, with a warning where
  FANUC does it its own way. `AccSet` and `VelSet` that slow the robot down stay TODO, as dropping
  them would run it faster than the ABB.

### Report
- Interrupts (`CONNECT`, `ISignalDI`, `IDelete`...) and motion settings are blockers of their own,
  no longer mixed with calls with arguments.

### Mapping file
- `analog_outputs`, `timers`, `analog_scales` and `payloads`, optional: a mapping file written for 1.0
  gives the same numbers.

### Validated
- A probe runs `TEST` in ten shapes (several values, negative and decimal values, empty and
  call-only `CASE`s, with and without `DEFAULT`, nested, on a constant, on an argument) on
  RobotStudio and, converted, on ROBOGUIDE: the same branches, register for register
  ([docs/validation.md](docs/validation.md#16-test-and-case-run)).
- The I/O probe, converted and run on ROBOGUIDE: the pulse is on during its length and off after,
  the output inverted and back, the clock reads the half second it timed, and the payload schedule of
  the tool with the part is the active one
  ([docs/validation.md](docs/validation.md#17-pulses-inverted-outputs-clocks-and-analog-outputs-run)).

## 1.0.0 — 2026-09-26

The first release. CrossArm converts ABB robot programs written in RAPID, from a RobotWare backup or
loose modules, into FANUC TP programs (`.LS`), with a report of everything left to review. Where the
two brands differ, both controllers were measured, with an ABB IRB 6700 in RobotStudio and three
FANUC robots in ROBOGUIDE (M-20iD/25, R-2000iC/190S, R-1000iA/80F). The points CrossArm writes are
the ABB's, as theoretical points to touch up at commissioning; the path between them stays within
4 mm of the ABB's on the moves measured, where CrossArm aims for 10.

### What 1.x keeps
- **A mapping file keeps working.** A `crossarm_mapping.json` written or edited for 1.0 is read the
  same way by every 1.x: no key is removed or changes meaning, new ones are optional.
- **Given back its mapping file, a conversion keeps its numbers.** Every register, flag, I/O, frame
  and program number a conversion wrote is in the mapping file it writes; converting again with it
  (`--map`) under a later 1.x gives the same numbers, so programs already on the robot still match.
- **The command line keeps its commands and options.**
- **What may change**: more RAPID converted where 1.0 writes a TODO, CNT and J % values where a
  robot is measured again or better, and the wording of the report and the window.

### Converts
- `MoveJ`, `MoveL`, `MoveC`, `MoveAbsJ` with their targets, `Offs()` and `RelTool()` resolved at
  conversion time; quaternions to W, P, R; `confdata` to `CONFIG` through axis conventions measured
  on both controllers, J6 at exactly 180 included. `MoveAbsJ` with a stationary tool or a robot-held
  work object is made with the tool already selected (else `tool0`), with a warning: a joint target
  does not depend on them.
- Tool and work objects to `UTOOL` / `UFRAME`, set on the robot by a generated `SETUP_FRAMES.LS`;
  frames past what the controller holds kept in position registers. Payloads listed in the report.
  `tool_pin` says which pin hole of the FANUC flange the tool sits by.
- **Frames and points the programs compute**, when every value they read is fixed: a tool built by a
  FUNC of the backup from another tool, a work object's `uframe` copied from another's, `DefFrame`,
  `PoseMult`, `PoseInv`, `PoseVect`, `OrientZYX`, `EulerZYX`, `Offs`, `RelTool`, a point put together
  component by component, the backup's own `RECORD`s. TP cannot do this arithmetic (measured: no pose
  product, inverse or angle function, `PR+PR` adds component by component), so CrossArm works the value
  out once; the program loads it where the RAPID computes it (`UTOOL[3]=PR[95]`), from a position
  register `SETUP_FRAMES.LS` sets. A value is computed only if nothing can change what it reads: a
  PERS another routine or task changes, a value set in one branch of an `IF`, in a loop or before a
  call that may change it leaves the TODO, and the TODO names that input and where it changes.
- Speeds and zones from motion profiles measured on both robots, per FANUC series: joint `%` from
  the TCP speed a J 100 % move reaches, each zone as the CNT that rounds a corner as much at the
  move's speed (the next move's, when it is faster).
- Digital and group I/O typed by `EIO.cfg`, waits, a wait with `\MaxTime` and its `ERROR` handler,
  `IF` / `ELSEIF`, `FOR`, `WHILE`, conditions calling the backup's own bool functions, calls with
  num, bool and switch arguments, the integrator's own move routines, `num` / `bool` data to
  registers and flags, operator messages, comments.
- Everything else is marked `!TODO` in the program and listed in the report, ranked by how much
  code each cause holds up, with the share of RAPID instructions converted by area. Each TODO says
  what it takes: among others a position built at run time, a frame or position **measured on the
  robot** (a calibration: `CRobT` and what derives from it, which only KAREL or the FANUC frame setup
  can redo), a payload changed at run time, a stationary tool.

### Fits the robot in place
- Given the FANUC robot's backup, its frames, registers, I/O and program names are left alone, and
  its model chooses the speed and zone profile.
- `crossarm_mapping.json` records the numbering of each conversion; edited and given back, it pins
  any number, the register of each computed frame included (`frame_registers`, by its value).
- The report compares what the conversion allocates with what the controller holds, position
  registers included (scratch, frame banks, computed frames), and gives each computed frame its
  register, value and where it is loaded.

### Validated
- Measured on a local test corpus written for testing, not distributed: three RobotWare backups and
  three FANUC backups in three integrators' styles, every RAPID task loaded by RobotStudio and every
  FANUC backup exported by ROBOGUIDE.
- Every program converted from the test corpus loads on ROBOGUIDE, and every form of instruction
  CrossArm writes is stored by the controller as written.
- On 16 test moves with rotated tools and work objects, the flange lands within 0.004 mm and 0.001°
  of where RobotStudio puts it; computed frames, 9 moves within 0.005 mm and 0.001°, `DefFrame` with
  each `\Origin` included.
- Converted joint moves take −16 % to +19 % of the ABB's time; corners, approaches, retracts,
  reversals and zigzags stay within 4 mm of the ABB's path.
- What TP can and cannot compute with frames, measured on ROBOGUIDE
  ([docs/validation.md](docs/validation.md#15-frames-and-points-the-programs-compute)).
- Every probe runs again unattended on both simulators. Details: [docs/validation.md](docs/validation.md).
