# How CrossArm was validated

A converter that produces plausible-looking but wrong robot programs is dangerous, so every claim
here is backed by a test. The tests on the local test corpus run locally only. Everything else, including
the controller measurements stored as fixtures, runs in CI on Windows and Linux.

The reference robots are an ABB IRB 6700 in RobotStudio and FANUC robots in ROBOGUIDE, which runs
the controller's own software: an M-20iD/25 first, then an R-2000iC/190S and an R-1000iA/80F.

**In short**

| What | Result |
|---|---|
| Every program converted from the test corpus, loaded on a FANUC controller | 123 of 123 |
| Every form of instruction CrossArm writes, read back from the controller | stored as written (194 forms) |
| Flange pose, RobotStudio against ROBOGUIDE running the converted program | within 0.004 mm and 0.001° |
| Arm configuration (`confdata` → `CONFIG`) | the controller's own, on three FANUC robots (two edge cases, listed) |
| Joint moves, converted, against the ABB | −16 % to +19 % in time |
| Corners, approaches, retracts, reversals, zigzags, converted, against the ABB | the path within 4 mm |
| Frames and points the programs compute, worked out by CrossArm, run on ROBOGUIDE | within 0.005 mm and 0.001° of RobotStudio |
| `TEST` / `CASE` converted to `SELECT`, run on both controllers | the branches RAPID takes |
| Pulses, inverted outputs, clocks, payloads, converted and run on ROBOGUIDE | what RAPID does, the clock within 50 ms |
| Points passed to routines or read from arrays indexed at run time, run on ROBOGUIDE | the poses of the moves written out, to 0.001 mm |

1. [The test corpus](#1-the-test-corpus)
2. [Round trip through a FANUC controller](#2-round-trip-through-a-fanuc-controller)
3. [Arm configuration measured on both controllers](#3-arm-configuration-measured-on-both-controllers)
4. [Geometry](#4-geometry)
5. [Same flange pose on both controllers](#5-same-flange-pose-on-both-controllers)
6. [Frames set by program](#6-frames-set-by-program)
7. [Calls with arguments, run](#7-calls-with-arguments-run)
8. [Conditions from the backup's own functions, run](#8-conditions-from-the-backups-own-functions-run)
9. [Waits with a time limit, run](#9-waits-with-a-time-limit-run)
10. [Every program of the test corpus, loaded](#10-every-program-of-the-test-corpus-loaded)
11. [Stored as written, and every probe run again unattended](#11-stored-as-written-and-every-probe-run-again-unattended)
12. [Speeds and zones, measured on both robots](#12-speeds-and-zones-measured-on-both-robots)
13. [The path where zones matter](#13-the-path-where-zones-matter)
14. [Other robots](#14-other-robots)
15. [Frames and points the programs compute](#15-frames-and-points-the-programs-compute)
16. [TEST and CASE, run](#16-test-and-case-run)
17. [Pulses, inverted outputs, clocks and analog outputs, run](#17-pulses-inverted-outputs-clocks-and-analog-outputs-run)
18. [Routines given their points, and arrays of points, run](#18-routines-given-their-points-and-arrays-of-points-run)

## 1. The test corpus

Besides the demo programs committed here, CrossArm is tested on a local corpus it does not
distribute, written for testing: three RobotWare backups and three FANUC backups, each in the style
of a different integrator (a palletizing and machine-tending cell with a PLC task, a deburring cell
that builds its tools and fixtures in RAPID, an assembly cell run as a state machine over three
tasks), with as much of RAPID and of TP as the controllers offer. It is checked on the controllers
themselves: RobotStudio loads every RAPID task, every reference resolved (the World Zones
instructions aside, an option the virtual controller lacks); the three FANUC backups are what three
ROBOGUIDE controllers (R-2000iC/190S, ARC Mate 120iD, R-1000iA/80F) hold once their programs are
loaded, exported from them.

- **RAPID side:** every module parses with zero syntax errors.
- **FANUC side:** every TP program goes through the `.LS` parser and back through the writer
  **byte for byte**; a file that is not a program is refused rather than half-read.
- **Robustness:** deliberately corrupted RAPID — 400 cases from the demo programs in CI, 800 from
  the test corpus — goes through the parser and the converter without a single crash
  ([tests/rapid/test_fuzz.py](../tests/rapid/test_fuzz.py)).
- The tests for this corpus run locally and are skipped in CI.

**Reading `.LS` back, losslessly.** The parser's contract is `write_ls(parse_ls(text)) == text`. That
is what lets CrossArm check itself without a controller, and it holds on every `.LS` file in this
repository, including the programs ROBOGUIDE exported back. Holding it meant keeping what controllers
really write rather than what a generator would: the spaces before each `;` (anything from 0 to 18),
task-control values, a `LINE_COUNT` that does not match the body, an empty `/APPL` section. It also
exposed a writer bug: a converted axis of −0.0 was written `-0.000`, a form no controller writes.

## 2. Round trip through a FANUC controller

The generated programs were loaded into ROBOGUIDE, compiled by the virtual controller without
error, then exported back. CrossArm's output matches that export **byte for byte**. The only
exception is the header values the controller computes itself. Every TP construct CrossArm emits is
covered:
- motions: J / L / C, cartesian and joint `/POS`;
- logic: mixed-logic `IF`, `FOR`, `LBL`/`JMP`;
- instructions: `WAIT`, registers, flags, digital and group I/O, operator messages.

A probe also measured the `MESSAGE[...]` limit. Texts of 25, 32 and 40 characters are accepted but
silently cut to 24 by the controller. CrossArm cuts at the same length and says so in the report.

See [fanuc_ls_format.md](fanuc_ls_format.md).

## 3. Arm configuration measured on both controllers

ABB `confdata` and FANUC `CONFIG` encode the arm posture differently, and no reference maps one to
the other reliably. So CrossArm measures it:

- [tools/make_config_probes.py](../tools/make_config_probes.py) turns one list of joint sets into a
  FANUC program and a RAPID module.
- ROBOGUIDE (M-20iD/25) computes `CONFIG`, position and orientation for each set.
- RobotStudio (IRB 6700, `CalcRobT`) computes `confdata`, position and orientation for the same sets.
- Fitting kinematic models to both sets of measurements gives the conventions below. Both fits
  are exact to the printed precision. They also recover the arm dimensions: 75 / 840 / 215 / 890 mm
  for the M-20iD/25, its documented kinematics.

| Axis | ABB | FANUC | Consequence |
|---|---|---|---|
| J1, J2 | + | + | same |
| J3 | relative to the upper arm | absolute (J2/J3 coupling) | `J3_fanuc = -(J2 + J3)_abb` |
| J4, J5, J6 | + | **−** | all three wrist axes reversed |
| flange frame | — | reported 180° about z | `J6_fanuc = 180 - J6_abb` |

The mapping `confdata → 'F/N U/D T/B, t1, t4, t6'` is then checked in
[tests/convert/test_configuration.py](../tests/convert/test_configuration.py) against:
- the measurements of both controllers;
- a J3 sweep across the elbow singularity, where the ABB bit flips exactly at the predicted −81.83°;
- 5000 random postures.

## 4. Geometry

Quaternion → W, P, R is checked on known orientations and on 2000 random rotations, including gimbal
lock.

## 5. Same flange pose on both controllers

The final check measures the whole chain end to end.
[tools/make_pose_probe.py](../tools/make_pose_probe.py) writes 16 test moves that combine:
- three tools with asymmetric offsets, two of them rotated;
- work objects with a rotated user frame and an object frame on top;
- `Offs`, `RelTool` with rotations, and one inside the other.

CrossArm converts the moves. Then each controller works out where the robot flange ends up, in the
world frame:
- RobotStudio computes it with `PoseMult` / `PoseInv`;
- ROBOGUIDE (M-20iD/25) runs the converted program with the frames CrossArm derived, and records
  the faceplate pose after each move.

| Comparison | Worst gap over 16 moves |
|---|---|
| RobotStudio vs CrossArm's own computation | 0.0007 mm, 0.00001° |
| RobotStudio vs ROBOGUIDE running the converted program | **0.004 mm, 0.001°** |

Both gaps are at the print precision of the controllers. The two measurement files are in
[tests/fixtures/probes/pose/results/](../tests/fixtures/probes/pose/results/), and
[tests/convert/test_pose_probe.py](../tests/convert/test_pose_probe.py) fails if a change to CrossArm
moves a single flange by more than 0.05 mm or 0.01°.

The same moves converted with `"tool_pin": "+x"` (the ABB flanges half a turn about z, the usual
`[0,0,1,0]` orientation pointing down) put the ROBOGUIDE faceplate half a turn about z from the
flange RobotStudio computes, within 0.004 mm and 0.001°: the tool turned on its flange, the TCP
where RAPID puts it ([tests/fixtures/probes/pin/](../tests/fixtures/probes/pin/)).

## 6. Frames set by program

`SETUP_FRAMES.LS` was run on ROBOGUIDE with frames unlike those already on the robot, then read back
into position registers ([tools/make_setup_probe.py](../tools/make_setup_probe.py)). The robot is
left with the frames of the report within 0.0004 mm and 0.0005°. Payloads cannot be set the same
way: the controller holds the payload schedules read-only for TP programs, so the report gives them
in the units of the payload screen.

## 7. Calls with arguments, run

[tools/make_arg_probe.py](../tools/make_arg_probe.py) converts a module of calls with num, bool and
switch arguments (negative and decimal values, switches given or not, arguments passed on, a
parameter the routine changes, a FOR bounded by an argument, a WAIT on one). Run on ROBOGUIDE, it
leaves every register with the value RAPID computes, and the controller stores the five programs
line for line as CrossArm writes them. On the way, a probe of negative constants showed the
controller's own forms: `(-2.5)` in assignments, calculations, FOR bounds and CALL arguments — where
the bare form is refused — and `-2.5` in conditions. No `.LS` written by a controller had shown one
before.

**Text arguments.** A string passed in a call (`CALL FAULT('Pince non ouverte')`) reaches the routine
whole: `SR[5]=AR[1]` holds it, `STRLEN AR[1]` measures it. The controller takes 38 characters per
string, whatever the length of the line, refuses an apostrophe inside, and has no way to show the
text: `MESSAGE` takes fixed text, and writing it into a user alarm (`$UALRM_MSG[1]=AR[1]`) runs
without setting anything. So CrossArm passes the text, and leaves a `TPWrite` of it TODO.

## 8. Conditions from the backup's own functions, run

[tools/make_condition_probe.py](../tools/make_condition_probe.py) converts conditions calling bool
functions of the common shape (`IF x=0 OR RobOS()=FALSE THEN RETURN TRUE`), compared with
TRUE and FALSE, negated, nested in another function, in a `WHILE` and a `WaitUntil`, and a negated
group next to `AND` (`a AND NOT (b OR c)`), which needs its parentheses in TP. Run on ROBOGUIDE,
every register holds the value RAPID computes on a real controller, and the programs are stored as
CrossArm writes them. Writing its tests showed that CrossArm used to drop those parentheses:
`a AND NOT (b AND c)` came out as `a AND NOT b OR NOT c`.

## 9. Waits with a time limit, run

[tools/make_wait_probe.py](../tools/make_wait_probe.py) converts waits with `\MaxTime` whose `ERROR`
handler goes on (`TRYNEXT`) or tries again (`RETRY`) before leaving the routine. Its first version
used `WAIT ... TIMEOUT` with `$WAITTMOUT` set by the program: the controller refused (VARS-010, the
variable is write-protected for programs). Each wait is now a loop on a timer. Run on ROBOGUIDE,
every register holds the value RAPID computes, the waits take 1.47 s for the 1.4 s of their
`MaxTime`, and the controller stores the four programs as CrossArm writes them — down to `R[4]<.5`,
not `<0.5`, in conditions.

## 10. Every program of the test corpus, loaded

The 123 programs converted from the three RobotWare backups of the test corpus were loaded on
ROBOGUIDE by FTP, and the controller's error log read for any it refused: all 123 load. Earlier
conversions of larger backups found two causes of refusal, both fixed: a group output set from a
group input (`GO[4]=GI[3]`), and selecting more tool or user frames than the controller holds. The
frames past the limit are loaded from position registers before use;
[tools/make_bank_probe.py](../tools/make_bank_probe.py) runs the pose probe's moves that way on a
controller of 2 tool frames and 1 user frame, and the flanges land within 0.004 mm of RobotStudio's.

## 11. Stored as written, and every probe run again unattended

Every program converted from the test corpus, 194 forms of instruction between them, was loaded on
ROBOGUIDE and read back from it: the controller stores every one as CrossArm wrote it, register and
frame names aside. Forms that first differed by a space before the `;` are now written the
controller's way.

[tools/probe_all.py](../tools/probe_all.py) then runs the probes again on both simulators with
nobody at either pendant, in about two and a half minutes. On ROBOGUIDE: FTP to load, the FANUC COM
interface to run, the robot's web pages to read. On RobotStudio, where RobotWare 7 and 8 give a PC
program no right to load or start programs, a small RAPID module started once
([tools/CrossArmServer.mod](../tools/CrossArmServer.mod)) loads and runs each probe module itself, and
the results are read from the virtual controller's `HOME:` folder:

| Probe | Checked on the controller |
|---|---|
| negative constants | the one refused form is still the only one refused |
| calls with arguments | 7 registers as RAPID computes them |
| conditions | 4 registers as RAPID computes them |
| waits with MaxTime | 3 registers, and 1.47 s of waiting for 1.4 s of MaxTime |
| SETUP_FRAMES | 5 frames within 0.0004 mm, 0.0005° |
| flange poses | 16 moves within 0.004 mm, 0.001° of RobotStudio |
| tool pin on +x | the same moves, tools turned: faceplate half a turn about z, within 0.004 mm, 0.001° |
| frames from registers | the same 16 moves, frames loaded from registers: same flanges |
| computed frames | 9 moves within 0.005 mm, 0.001° of RobotStudio ([section 15](#15-frames-and-points-the-programs-compute)) |
| ABB probe modules (RobotStudio) | the 5 modules write what RobotStudio measured by hand, number for number |

## 12. Speeds and zones, measured on both robots

Neither has an exact equivalent, and both depend on the robots, so both were measured:
[tools/probe_motion.py](../tools/probe_motion.py) runs the same moves on the IRB 6700 of a
RobotStudio station and on the M-20iD/25 of a ROBOGUIDE cell, timed by each controller's clock, the
TCP read while it moves (every millisecond or so, through the ABB PC SDK and the FANUC COM
interface). 86 runs on the ABB and 96 on the FANUC:

- **Linear moves** take as long on both at the same mm/s, up to 1000 mm/s: the speed carries over.
- **Joint moves**: a MoveJ takes about as long as its TCP path at the RAPID speed; a J move, its
  joint path at a share of the axes' top speed. The J % that takes as long as each RAPID speed
  gives the TCP speed a J 100 % move reaches: 3,800 to 5,300 mm/s depending on the move, nearly the
  same at every speed. CrossArm divides by 4500. The former 2000 made the FANUC 2 to 2.5 times
  faster than the ABB.
- **Zones**: a RAPID zone rounds a corner by about the same distance at any speed (`z10`: 5 mm at
  200 to 1000 mm/s); a CNT, by more the faster the move (`CNT50`: 1.9 mm at 200 mm/s, 11 mm at
  1000). No single ratio fits, so CrossArm writes the smallest CNT that rounds a right-angle corner
  as much as the RAPID zone at the move's speed: `z10` is `CNT97` at 200 mm/s, `CNT54` at 500,
  `CNT31` at 1000. Where even `CNT100` rounds less (`z50` below about 700 mm/s), the report says so.
  The former rule, `CNT = radius in mm`, rounded `z10` by 0.5 mm instead of 5.

RAPID moves at speeds the fit never saw, converted by CrossArm and run on both robots:

| Check | FANUC against ABB |
|---|---|
| joint moves, 3 paths, v400 and v600 | −16 % to +19 % in time |
| right-angle corner, linear, z5 to z30, v300 and v600 | −1 % to +3 % in time, corner cut within 0.8 mm (z30 at v300: CNT100 rounds less, as reported) |
| the same corner in joint moves, z10 and z20, v600 | corner cut within 0.15 mm |

[tests/convert/test_motion.py](../tests/convert/test_motion.py) fails if the profile CrossArm
converts with is not what the stored runs fit to, or if the check drifts.

## 13. The path where zones matter

A CNT that rounds more than the RAPID zone did takes the tool off the taught path where the
programmer did not expect it. [tools/make_path_probe.py](../tools/make_path_probe.py) runs the moves
where that counts, with the zones programs commonly use, on the IRB 6700 and, converted by CrossArm, on
an R-1000iA/80F and an R-2000iC/190S, and reads the TCP on both: approaches onto a part 100, 50 and
20 mm below the travel point, in linear and joint moves; retracts off it; a reversal; corners of 45
and 135 degrees; zigzags with 50 mm legs. 32 runs:

- **On the way down onto a part the FANUC stays on the line longer than the ABB** in every case
  (`z100` 100 mm above the part: straight for the last 86 mm, where the ABB is for 12), and passes
  closer to the approach point: into a slower move, a CNT rounds less than at the move's own speed.
- **Into a faster move it rounds more.** Off the top of a retract (300 mm/s, then 1000), the CNT
  for 300 mm/s cut the corner by 6.8 mm, where the ABB cut it by 4.9. CrossArm now matches a
  corner at the next move's speed when that is faster, past outputs and remarks in between: 1.3 mm.
  On the test corpus the rule lowers 72 CNT of 654 moves and raises none.
- **A reversal turns short of the bottom by up to 4 mm more.** Down and back up through a zone, the
  R-2000iC turns 5.6 mm short of the bottom with `z5` (the ABB 2.6), 12.1 with `z20` (9.5), still
  on the line: the tool goes less deep, not aside. The R-1000iA: 3.9 mm for 2.6 with `z5`, as
  the ABB with `z20`. The CNT is matched on a right-angle corner, which heavier arms round
  differently when they turn back.
- Everywhere else the FANUC is within 1 mm of the ABB or closer to the points.

So a converted program keeps to the ABB's path within 4 mm on the moves measured, and within about
a millimetre but for zoned reversals: well inside the 10 mm CrossArm aims for, since the points are
touched up on the robot anyway. [tests/convert/test_path_probe.py](../tests/convert/test_path_probe.py)
fails if the FANUC strays more than 1.5 mm further from the taught path than the ABB (4 mm short of
the bottom of a reversal), or leaves the line sooner on the way down onto a part.

## 14. Other robots

The probes were run again on an R-2000iC/190S and an R-1000iA/80F in ROBOGUIDE. At the same posture,
their flange has the ABB flange's orientation to within 1e-6, as the M-20iD/25's does, and CrossArm's
CONFIG is the one the controller computes ([tools/check_conventions.py](../tools/check_conventions.py),
with nobody at the pendant). The pose probe and every other probe pass on both. Two limits, both said
by the tool: with J4 off the arm's plane and J6 exactly on 180 (the arm's lengths would be needed),
and the elbow letter within a few degrees of the elbow singularity, where two arms of different
proportions part at the same joint angles.

On the way, a real fault: FANUC counts J6 = 180 exactly in turn 1 (turn 0 is open at both ends,
with a tolerance of about 0.0005 deg, measured), and a point written with turn 0 there is refused
(MOTN-018). An ABB target with J6 = 0 exactly, a tool straight down in front of the robot, is exactly
that point, and the demo's `pHome` was one. CrossArm now finds it from the pose, whatever the arm
([tools/make_boundary_probe.py](../tools/make_boundary_probe.py): every target reached).

**Speeds and zones differ from one arm to another.** Run the same way on an R-2000iC/190S, the motion
probe finds axes 2.25 times slower for the same TCP path (J 100 % reaches 2,000 mm/s, not 4,500) and
corners rounded 2 to 2.4 times more by the same CNT; with its own profile the check matches as well
(time within 27 %, corners within 1.4 mm). An R-1000iA/80F sits between the two: J 100 % reaches
3,400 mm/s, corners as round as the M-20iD's up to 500 mm/s and about 1.3 times rounder at 1,000
(check: time within 24 %, corners within 1.5 mm where CNT100 is enough). This is why CrossArm takes
the profile of the target robot's series ([user guide](guide.md#speeds-and-zones)).

## 15. Frames and points the programs compute

**What TP can do with a frame** was asked of the controller before choosing what to write
([tools/make_tp_frame_probe.py](../tools/make_tp_frame_probe.py), R-2000iC/190S): each candidate
instruction loaded alone, then a program that combines known values and moves with offsets, each
result read back and compared with a product of frames and with a component-by-component sum.

| Instruction | On ROBOGUIDE |
|---|---|
| `PR[a]=PR[b]+PR[c]` | adds component by component, W, P and R included: 76 mm and 6° from the product of the two frames |
| `PR[a]=PR[b]*PR[c]`, `PR[a]=PR[b]/PR[c]` | loads, then stops the program where it runs (INTP-202) |
| `PR[a]=PR[b]:PR[c]`, `PR[a]=UFRAME[n]+PR[b]`, `PR[a]=PR[b]*R[n]` | refused (ASBN-092) |
| `SIN`, `ATAN2`, `SQRT`, with brackets, parentheses or inside a calculation | refused (ASBN-092); several operators in one calculation, `R[1]=(R[2]*R[3]+R[4])`, load |
| `UFRAME[n]=PR[m]`, `PR[m]=UFRAME[n]` | exact |
| `PR[n]=LPOS` with a user frame selected | the pose in that frame, exact |
| `Offset,PR[n]` on a move | the offset added component by component in the selected user frame, W, P, R included |
| `OFFSET CONDITION PR[n],UFRAME[m]` then `Offset` | the offset expressed in that user frame |
| `Tool_Offset,PR[n]` on a move | the offset composed in the tool frame, rotations included |
| a joint point whose tool number is not the one selected | refused when it runs (INTP-253) |

A TP program can load a frame and move relative to it, but it cannot compute one. So CrossArm works
a computed frame out at conversion time, when every value it reads is fixed
([user guide](guide.md#frames-and-points-the-programs-compute)); a frame measured on the robot
(`CRobT`) stays TODO, as it would need KAREL, which has pose operators (not measured here).

**End to end.** [tools/make_compute_probe.py](../tools/make_compute_probe.py) writes a module that
builds its frames the way programs do: a tool made by a FUNC from a base tool and a `RECORD`, a
`uframe` copied from another work object, one work object computed four times with `DefFrame`
(each `\Origin`, then the first again), a point put together from `PoseVect`, `PoseInv`, `EulerZYX`
and `OrientZYX`, `RelTool` on that point, a `MoveAbsJ` with a stationary tool. CrossArm converts it
with no TODO. RobotStudio runs the same statements with each move replaced by the flange pose it
would reach; ROBOGUIDE runs what `SETUP_FRAMES.LS` sets, then the converted program:

| Comparison | Worst gap over 9 moves |
|---|---|
| RobotStudio vs ROBOGUIDE running the converted program | **0.005 mm, 0.001°** |

The three `DefFrame` origins put the flange in three places, the same on both; the fourth
computation reuses the first one's register; the `MoveAbsJ` runs, with the tool selected before it
(not compared: a joint target puts the flange elsewhere on another arm). The results are in
[tests/fixtures/probes/compute/results/](../tests/fixtures/probes/compute/results/), checked by
[tests/convert/test_compute_probe.py](../tests/convert/test_compute_probe.py).

**Only when certain.** A frame frozen at a wrong value would be worse than a TODO, so each way a value
can change keeps it: [tests/convert/test_compute.py](../tests/convert/test_compute.py) covers a PERS
another routine changes, one changed through an `INOUT` parameter (and one only read through a
`PERS` parameter, which does not count), `SetDataVal` on the data's type, a value set in one branch
of an `IF` (and the same value on both), a loop, a frame read from the robot and what derives from
it, a function that does more than compute.

On the test corpus, the deburring cell's burr tools, built by a FUNC from the spindle frame, and two
of its fixtures (a `uframe` copied, one from `DefFrame` on measured reference points) are worked out
and loaded from five registers; the fixture it measures with a search and the TCP it checks with
`CRobT` stay TODO, as calibrations. Computing them takes 9 TODO off the three backups, and the automatic
numbers of their mapping files do not move.

## 16. TEST and CASE, run

**What `SELECT` does** was asked of ROBOGUIDE first, with hand-written programs: every form loads
(values negative, decimal, repeated; a `CALL` with or without arguments on a line; no `ELSE`), the
controller indents the lines after the first by 7 spaces whatever they had, and stores `-1` as
`(-1)`. Run with each value: the first equal line wins, as the first `CASE` does in RAPID; with no
`ELSE` and no equal value the program goes on after the `SELECT`; a `CALL` made on a `SELECT` line
comes back after the `SELECT`. So a `CASE` that only calls a routine is written on its line, and the
other branches behind labels, each jumping to a common exit.

**End to end.** [tools/make_select_probe.py](../tools/make_select_probe.py) writes a module that runs
`TEST` in the shapes programs use: several values on a `CASE`, a negative and a decimal value, a
`CASE` that only calls a routine, an empty one, with and without `DEFAULT`, a value no `CASE` has, a
`TEST` nested in a `CASE`, one on a constant and one on a routine's argument. Each branch adds its own
weight to three totals, so a wrong branch shows. RobotStudio runs the RAPID, ROBOGUIDE the converted
programs:

| Total | RobotStudio | ROBOGUIDE |
|---|---|---|
| `nSum` | 21120 | 21120 |
| `nCalls` | 112 | 112 |
| `nPath` | 114 | 114 |

The results are in [tests/fixtures/probes/select/results](../tests/fixtures/probes/select/results).

## 17. Pulses, inverted outputs, clocks and analog outputs, run

**The forms** were asked of ROBOGUIDE first. `DO[1]=PULSE,0.5sec` loads and is stored with its zero;
the length is in tenths of a second: 0.25 is stored `0.3sec`, 0.05 `0.1sec`, a length below that is
dropped (the controller's default then applies), and 25.5 s is the longest (25.6 is refused). So
CrossArm rounds the length of a `PulseDO` to the tenth, with a warning when that changes it, and
leaves a longer pulse TODO. `DO[1]=(!DO[1])` loads. `AO[1]=` takes a constant, decimal or negative,
or a register, but not a calculation. `PAYLOAD[3]` loads and selects schedule 3 (`$PLST_PARNUM[1]`
reads 3 after it, 7 after `PAYLOAD[7]`); `PAYLOAD[11]` loads but stops the program when it runs.

**Run.** [tools/make_io_probe.py](../tools/make_io_probe.py) converts a module that inverts an output
twice, pulses another for half a second and reads it 0.1 s and 0.7 s in, times half a second with a
clock, sets an analog output with a scale from the mapping file, and grips a part between two joint
moves. On ROBOGUIDE the output is inverted and back, the pulse is on during its length and off
after, and the clock reads 0.500 s: every register as RAPID computes it; after the run the active
payload schedule is the one CrossArm gave the tool with the part. The virtual ABB controller has none of these signals, so the
RAPID side is worked out by hand, as for the argument probe. An analog output is not read back: the
probe checks that the line loads and runs.

## 18. Routines given their points, and arrays of points, run

**What a position register does** was asked of ROBOGUIDE first. A point recorded in user frame 1 and
copied into a position register (`PR[60]=P[1]`) keeps its values and its configuration; moved to
with user frame 2 selected, the robot goes to those values in frame 2 (`LPOS` read in frame 2 gives
them back). A move to a position register takes the frames selected when it runs, as a RAPID move
takes the tool and work object written in it with the robtarget it is given. `PR[62,3]=PR[62,3]+40`
moves the point 40 mm along the frame's z, as `Offs()` does. A register can also be named by another:
`L PR[R[5]]`, `J PR[R[5]]` and `PR[63]=PR[R[5]]` go to, and copy, the register whose number `R[5]` holds, and
the index can be worked out beforehand (`R[5]=R[1]*2`, `R[5]=R[5]+R[2]`, `R[5]=R[5]+76`).

**End to end.** [tools/make_point_probe.py](../tools/make_point_probe.py) converts twenty-eight moves
twice: through routines that take a robtarget (one approaches its point with `Offs()`, moves to it,
leaves with another `Offs()`; another passes its own point on, as it is and with `Offs()`) and through a
CONST 2 x 2 array walked in two FOR loops (each element moved to, and handed with `Offs()` to the first
routine), and written out with their points. ROBOGUIDE runs both, with the frames `SETUP_FRAMES` sets, and records the pose after
every move:

| Comparison | Worst gap |
|---|---|
| Moves through routines and arrays vs the moves written out, over 28 moves | **0.000 mm, 0.000°** |

The poses are the RAPID values themselves (the point 40 mm above, the retract offset by 10, -20 and
40 mm), the array's elements row after row, as the loops walk them. The results are in [tests/fixtures/probes/points/results](../tests/fixtures/probes/points/results).
