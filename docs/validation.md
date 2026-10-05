# How CrossArm was validated

A converter that produces plausible-looking but wrong robot programs is dangerous, so every claim
here is backed by a test. The tests on the local test corpus run locally only. Everything else, including
the controller measurements stored as fixtures, runs in CI on Windows and Linux.

The reference robots are an ABB IRB 6700 in RobotStudio and FANUC robots in ROBOGUIDE, which runs
the controller's own software: an M-20iD/25 first, then an R-2000iC/190S and an R-1000iA/80F.

**In short**

| What | Result |
|---|---|
| RAPID instructions converted, public open-source programs (indicative, [why not all](#public-programs)) | about 60 %, from about 15 % to all of it per project |
| RAPID instructions converted, our test corpus, written for testing | 86 % to 93 % |
| Every program converted from the test corpus, loaded on a FANUC controller | 130 of 130 |
| Every form of instruction CrossArm writes, read back from the controller | stored as written (234 forms) |
| The controller probes, run again on both simulators for this version | 26 of 26 give what was measured |
| Flange pose, RobotStudio against ROBOGUIDE running the converted program | within 0.004 mm and 0.001° |
| Arm configuration (`confdata` → `CONFIG`) | the controller's own, on three FANUC robots (two edge cases, listed) |
| Joint moves, converted, against the ABB | −16 % to +19 % in time |
| Corners, approaches, retracts, reversals, zigzags, converted, against the ABB | the path within 4 mm |
| Frames and points the programs compute, worked out by CrossArm, run on ROBOGUIDE | within 0.005 mm and 0.001° of RobotStudio |
| `TEST` / `CASE` converted to `SELECT`, run on both controllers | the branches RAPID takes |
| Pulses, inverted outputs, clocks, payloads, converted and run on ROBOGUIDE | what RAPID does, the clock within 50 ms |
| Points passed to routines or read from arrays indexed at run time, `Offs()` and `RelTool()` of them, run on ROBOGUIDE | the poses of the moves written out, to 0.001 mm |
| Records and nums passed by reference, run on both controllers | the values RAPID computes |
| Routines given their tool and work object, run on ROBOGUIDE | the faceplate where the moves written out put it |
| Points worked out at run time (palletizing), run on ROBOGUIDE | the faceplate where the moves written out put it |
| Arrays of numbers indexed at run time, run on both controllers | the values RAPID reads |
| Interrupts converted to condition monitors, run on ROBOGUIDE | the TRAP calls RAPID makes |
| Data of RECORD types kept field by field (a state machine), run on both controllers | the values RAPID computes, the moves at the record's speed |
| Strings kept in string registers (texts compared, worked out, passed on), run on both controllers | the values RAPID computes |
| Arrays of numbers the programs write, run on both controllers | the values RAPID computes |
| Bools set to a condition, kept in flags, run on both controllers | the values RAPID computes |
| Points a routine changes (VAR, INOUT robtarget), read back by the caller, run on both controllers | the values RAPID computes, after the moves |
| `MoveLDO` to a fine point: the move, then the output, run on ROBOGUIDE | the output switches with the TCP on the point |
| Waits with `\MaxTime` and `\TimeFlag`, run on both controllers | the flags RAPID sets |
| `SearchL` converted to a skip, run on ROBOGUIDE with the input switched as the TCP passes a point | the point found within 0.1 mm of where the input switched |
| Arrays of bools kept in flags, run on both controllers | the values RAPID computes |

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
19. [Arrays of numbers, run](#19-arrays-of-numbers-run)
20. [Interrupts, run](#20-interrupts-run)
21. [Records and nums passed by reference, run](#21-records-and-nums-passed-by-reference-run)
22. [Points worked out at run time, run](#22-points-worked-out-at-run-time-run)
23. [Records kept field by field, run](#23-records-kept-field-by-field-run)
24. [Strings in string registers, run](#24-strings-in-string-registers-run)
25. [Arrays the programs write, run](#25-arrays-the-programs-write-run)
26. [Bools set to a condition, run](#26-bools-set-to-a-condition-run)
27. [Points passed by reference, run](#27-points-passed-by-reference-run)
28. [An output set at a fine point, run](#28-an-output-set-at-a-fine-point-run)
29. [Waits with a time flag, run](#29-waits-with-a-time-flag-run)
30. [A search, run](#30-a-search-run)
31. [Arrays of bools, run](#31-arrays-of-bools-run)

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

### Public programs

Because we wrote the test corpus, it says little about programs we did not write. So CrossArm is also
run on a second local corpus: RAPID programs published on the Internet under permissive open-source
licences, read and converted as they are, every program written loaded on ROBOGUIDE. CrossArm converts
**about 60 %** of their instructions, from about 15 % to all of them depending on the project, where it
converts 86 % to 93 % of the test corpus. The projects that convert least are built around files,
sockets, operator dialogs and error handlers, or are libraries using data declared in other projects.

What the figure does not say:

- **Converted means written in TP and loaded by the controller without an error**, not validated on
  a robot. Only the probes below compare what the programs compute and where they move; the points
  stay theoretical, within 10 mm of the ABB's path, to be touched up at commissioning.
- It is indicative, neither stable nor reproducible: the corpus is not distributed (its licences do
  not allow it here), it changes as programs are added, and the figure is rounded.
- The projects are mostly students' work and libraries, not an industrial integrator's code; copies of
  one project in several folders are counted as many times as they appear.

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

The 130 programs converted from the three RobotWare backups of the test corpus were loaded on
ROBOGUIDE by FTP, and the controller's error log read for any it refused: all 130 load. Earlier
conversions of larger backups found two causes of refusal, both fixed: a group output set from a
group input (`GO[4]=GI[3]`), and selecting more tool or user frames than the controller holds. The
frames past the limit are loaded from position registers before use;
[tools/make_bank_probe.py](../tools/make_bank_probe.py) runs the pose probe's moves that way on a
controller of 2 tool frames and 1 user frame, and the flanges land within 0.004 mm of RobotStudio's.

## 11. Stored as written, and every probe run again unattended

Every program converted from the test corpus, 234 forms of instruction between them, was loaded on
ROBOGUIDE and read back from it: the controller stores every one as CrossArm wrote it, register and
frame names aside. Forms that first differed by a space before the `;` are now written the
controller's way.

[tools/probe_all.py](../tools/probe_all.py) then runs the probes again on both simulators with
nobody at either pendant, in about eighteen minutes. On ROBOGUIDE: FTP to load, the FANUC COM
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
| `TEST` / `CASE` as `SELECT` | 3 registers as RAPID computes them ([section 16](#16-test-and-case-run)) |
| pulses, clocks, analog outputs, payloads | 3 registers as RAPID computes them, the payload of the tool with the part active ([section 17](#17-pulses-inverted-outputs-clocks-and-analog-outputs-run)) |
| routines given their points, arrays of points | 43 moves where the moves written out go ([section 18](#18-routines-given-their-points-and-arrays-of-points-run)) |
| arrays of numbers indexed at run time | 3 registers as RAPID computes them ([section 19](#19-arrays-of-numbers-run)) |
| interrupts | 6 registers as RAPID computes them ([section 20](#20-interrupts-run)) |
| records and nums passed by reference | 3 registers as RAPID computes them ([section 21](#21-records-and-nums-passed-by-reference-run)) |
| points worked out at run time | 13 moves where the moves written out go ([section 22](#22-points-worked-out-at-run-time-run)) |
| records kept field by field | 7 registers as RAPID computes them, in three programs (speed and zone as constants, from registers) ([section 23](#23-records-kept-field-by-field-run)) |
| strings in string registers | 20 registers as RAPID computes them ([section 24](#24-strings-in-string-registers-run)) |
| arrays the programs write | 5 registers as RAPID computes them ([section 25](#25-arrays-the-programs-write-run)) |
| bools set to a condition | 6 registers as RAPID computes them ([section 26](#26-bools-set-to-a-condition-run)) |
| points passed by reference | 5 registers as RAPID computes them, after 4 moves ([section 27](#27-points-passed-by-reference-run)) |
| an output set at a fine point | set 0.000 mm from the point ([section 28](#28-an-output-set-at-a-fine-point-run)) |
| waits with a time flag | 2 registers as RAPID computes them ([section 29](#29-waits-with-a-time-flag-run)) |
| a search | the point found within 0.1 mm of the switch, `\Sup` on to the point, a pause with the input on at the start ([section 30](#30-a-search-run)) |
| arrays of bools | 4 registers as RAPID computes them ([section 31](#31-arrays-of-bools-run)) |
| ABB probe modules (RobotStudio) | the 15 modules write what RobotStudio measured before, number for number |

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

**End to end.** [tools/make_point_probe.py](../tools/make_point_probe.py) converts forty-three moves
twice: through routines that take a robtarget (one approaches its point with `Offs()`, moves to it,
leaves with another `Offs()`; another passes its own point on, as it is and with `Offs()`) and through a
CONST 2 x 2 array walked in two FOR loops (each element moved to, and handed with `Offs()` to the first
routine), and written out with their points. ROBOGUIDE runs both, with the frames `SETUP_FRAMES` sets, and records the pose after
every move:

| Comparison | Worst gap |
|---|---|
| Moves through routines and arrays vs the moves written out, over 43 moves | **0.000 mm, 0.000°** |

The poses are the RAPID values themselves (the point 40 mm above, the retract offset by 10, -20 and
40 mm), the array's elements row after row, as the loops walk them. The results are in [tests/fixtures/probes/points/results](../tests/fixtures/probes/points/results).

## 19. Arrays of numbers, run

A numeric register named by another, `R[R[5]]`, reads in an assignment, a calculation, an `IF`
condition, a `FOR` bound and a `CALL` argument on ROBOGUIDE, and the values `SETUP_FRAMES` writes are
stored as the controller writes them (`R[81]=0.5` becomes `.5`, `(-2.5)` keeps its parentheses).

[tools/make_array_probe.py](../tools/make_array_probe.py) converts a module that reads a CONST table
of decimals and negatives, a CONST 2 x 3 table and a PERS table no program changes, in FOR loops,
sums, `IF` conditions, a `WHILE` whose index the loop moves, and a call given two elements at once.
Each read adds its own weight to three totals. RobotStudio runs the RAPID; ROBOGUIDE sets the tables
in their registers as `SETUP_FRAMES` does, then runs the converted programs:

| Total | RobotStudio | ROBOGUIDE |
|---|---|---|
| `nSum` | 160.75 | 160.75 |
| `nCalls` | 156 | 156 |
| `nHits` | 211 | 211 |

Writing the probe found a fault before it ran: a call given two elements, the first one's index
already worked out by the statement before, had both read through the same index register. A
statement now keeps every index register it reads. The results are in
[tests/fixtures/probes/arrays/results](../tests/fixtures/probes/arrays/results).

## 20. Interrupts, run

TP has no interrupt, but FANUC's Condition Monitor function comes close: a condition program holds
`WHEN DI[1]=ON+,CALL TRAP`, and `MONITOR NAME` arms it. Short probes on ROBOGUIDE (R-1000iA/80F)
measured how it behaves before CrossArm wrote any:

- it fires once and is then disarmed: a TRAP arms it again as it ends, and one armed again while a
  level condition holds fires again at once, where an edge (`ON+`, `OFF-`) fires once per edge, and
  not for a signal already set when armed, as `ISignalDI` does;
- the program stops while the TRAP runs, but the move under way goes on: a joint move took 3.762 s
  with a TRAP of 1 s during it, 3.761 s without, as a RAPID interrupt leaves the path alone;
- it stays active in the programs called, and after they return;
- the TRAP runs as a task of its own: calling a program with a motion group fails while the
  interrupted program holds the robot (INTP-222, PROG-040 Already locked by other task), so the TRAP
  and every routine it calls are written without one;
- the condition is checked periodically: an edge made at once after `MONITOR` is missed, one 0.05 s
  later is seen; a pulse of no width is missed, one of 0.02 s is seen. The report says so;
- a digital input simulated on the controller fires like the output the probes drive;
- a condition program refuses a remark, a flag, a timer and a condition with `AND`.

[tools/make_interrupt_probe.py](../tools/make_interrupt_probe.py) then converts a module that arms
`ISignalDO` on a rising edge, on a falling edge and with `\Single`, and `IPers` on a PERS; drives
the outputs and the PERS, puts one interrupt to sleep (`ISleep`) and wakes it (`IWatch`), pulses the
output from a called routine, and deletes them all (`IDelete`) before pulsing once more. Each TRAP
counts its calls, one of them through a routine it calls; one TRAP serves two interrupts, through a
relay each that notes which one called it. ROBOGUIDE runs the converted programs;
the counts RAPID gives are worked out by hand, the virtual ABB controller having no signal for
`ISignalDO` to watch:

| Count | RAPID | ROBOGUIDE |
|---|---|---|
| `nHits`: rising edges, one while asleep and one after `IDelete` not counted | 4 | 4 |
| `nOnce`: `\Single`, two rising edges | 1 | 1 |
| `nFall`: falling edges, the output already down when armed | 2 | 2 |
| `nWatch`: changes of the PERS, the last after `IDelete` not counted | 2 | 2 |
| `nLast`: the value the last one saw | 7 | 7 |
| `nShared`: a TRAP two interrupts share (rising and falling edges of one output), telling them apart by `INTNO`: up twice, down once | 12 | 12 |

On the test corpus, the palletizing cell's two interrupts on inputs convert; the one on a timer
(`ITimer`) and the assembly cell's, whose TRAP stops the motion (`StopMove`), stay TODO. The results
are in [tests/fixtures/probes/interrupts/results](../tests/fixtures/probes/interrupts/results).

## 21. Records and nums passed by reference, run

TP passes values only: a CALL argument is read as `AR[n]` and cannot be written. A record is passed
as the components the routine reads, each an argument of its own; a num passed by reference goes in a
register of the routine's own, which the caller reads back after the CALL.
[tools/make_param_probe.py](../tools/make_param_probe.py) converts a module that gives a routine two
records of the backup's own type (a loop count, a decimal, a bool), passes a num by reference to a
routine that adds to it and to one that passes it on and increments it, and changes the totals with
`Incr`, `Decr`, `Add` and `Clear`. RobotStudio runs the RAPID, ROBOGUIDE the converted programs:

| Total | RobotStudio | ROBOGUIDE |
|---|---|---|
| `nSum` | 10.5 | 10.5 |
| `nCount` | 11 | 11 |
| `nBack` | 4.5 | 4.5 |

Writing it found a routine passing on a parameter it had copied: it passed the value it was given,
not its copy. It now passes the copy. The point probe ([section 18](#18-routines-given-their-points-and-arrays-of-points-run))
gained `RelTool()` of a point given to a routine and of an array element, displaced and turned about
one axis and about all three, a displacement given negated, and a routine given its tool and work
object, called with two of each: forty-three moves. It now records the faceplate in the world frame
after each move, not the TCP in the frames the move ran in, which a routine selecting the wrong tool
would not show; the two tools put it 57 mm apart, and every move where the move written out puts it,
to the thousandth of a millimetre. Reading the programs back showed the
controller stores a register's component, `PR[95,3]=(-30)`, with four spaces before `;`, as it does
a whole register; CrossArm now writes it so.

## 22. Points worked out at run time, run

Palletizing programs work the place out as they go: `Offs()` of the pallet's corner by the loop counters
times the part's size, a turn on every other layer, the robot's own position read with `CRobT()`. TP
has none of that arithmetic in one line, but a position register can be copied from a P (whatever
frames are selected: measured), offset component by component, set from `LPOS`, and moved to in the
frames selected. A calculation of several operations is made one per line in scratch registers.

[tools/make_pallet_probe.py](../tools/make_pallet_probe.py) converts a module that places parts in two
FOR loops (`pPlace:=Offs(pOrigin,(c-1)*LENGTH+nShift{k},(k-1)*WIDTH,(k-1)*HEIGHT)`), turns them on the
second layer with `RelTool(pPlace,0,0,0\Rz:=90)`, moves above and onto each and to `Offs()` of the
corner by the counters written in the move, then reads `CRobT()`, moves its x and goes above it.
ROBOGUIDE runs it and the same moves with the points written out: thirteen moves, the faceplate at the
same pose to the thousandth of a millimetre. Reading the first conversion showed the three offsets
of one `Offs()` worked out in the same scratch register before any was added: each is now worked out
just before its line. On the test corpus, the palletizing cell's place is worked out so, and its
TODO go from 39 to 25.

## 23. Records kept field by field, run

A state machine often keeps its state in data of a RECORD type: its state, its counters, the speed and
zone of its moves. TP has no records. CrossArm keeps each field a program changes in a register (a bool
in a flag), named by its path, and writes a field no program changes as its value; a speed or zone
field is the value every write gives it, when they all give the same.

[tools/make_record_probe.py](../tools/make_record_probe.py) converts a module whose state machine
(`VAR probectrl recCtrl`) is set up by one routine, moved on by two others in a `WHILE` on a `TEST` of
its state, and read in a fourth; its moves run at the speed and zone the set-up routine gives a record
inside it. A PERS record no program changes is read, a bool field in an `IF`; a routine keeps a record
of its own, which RAPID sets to zeros at each call; a record is copied whole into another. RobotStudio
runs the RAPID, ROBOGUIDE the converted programs, then two variants giving the speed, then the zone
too, from registers (`L P[3] R[8]mm/sec`, `CNT R[9]`):

| Total | RobotStudio | ROBOGUIDE (3 programs) |
|---|---|---|
| state, written by three routines | 3 | 3 |
| counter | 11 | 11 |
| passes, the bool read in another routine | 3, 1 | 3, 1 |
| fields of a PERS no program changes, a bool among them | 1307 | 1307 |
| calls where the routine's own record was not zeros | 0 | 0 |
| the copy of a record (its counter, its bool) | 103 | 103 |
| 200 mm at the record's speed, then two moves through its zone | 0.620 s, 1.300 s | 0.745 s, 1.392 s |

The times differ as joint and linear moves of the same speed do between the two robots
([section 12](#12-speeds-and-zones-measured-on-both-robots)); from registers, the moves take the same time
as with constants, to 3 ms. The same probe loads the forms a bool or a string field would need: a
flag set from a condition or from another flag loads, a string register set from an argument or from
another loads, but not from text written in the program (`SR[20]='IDLE'`), and a comparison of two
string registers in parentheses is refused too (the form without them loads:
[section 24](#24-strings-in-string-registers-run)). Writing it found a field read inside a speed
(`recSaved.p.speed.v_tcp`) and a bool field copied from another: both converted now. It also found
that `CONST zonedata zPick:=z50` was not read: a predefined speed or zone given as the value of a data
is read now.

## 24. Strings in string registers, run

A state machine can keep its state in a string, a program read a text one character at a time. TP
has 25 string registers, but a TP line can neither write a text in one nor compare one with a text:
CrossArm loads a text written in the program through a program given it as an argument
(`CALL CA_TEXT(3,'IDLE',0)`) into a scratch register, just before it is compared or passed on, and
compares two string registers in the one form TP has, `IF SR[a]=SR[b],JMP LBL[n]`.

[tools/make_string_probe.py](../tools/make_string_probe.py) converts a module that counts the letters
of `"LOAD. ROBOT!!"` read one character at a time (`StrLen`, `StrPart`, an `IF` / `ELSEIF` on each),
runs a state machine whose state is a string (`WHILE strState<>"DONE"`), looks for texts (`StrMatch`,
found and not), writes numbers as texts (`NumToStr`, `ValToStr`), loads a text of 80 characters, an
empty one and one with an apostrophe, puts a text before itself, sets a string of a routine at each
call and passes texts to a routine taking one. RobotStudio runs the RAPID, ROBOGUIDE the converted
programs:

| Total | RobotStudio | ROBOGUIDE |
|---|---|---|
| A, O, spaces, !, other characters of "LOAD. ROBOT!!" | 1, 3, 1, 2, 6 | 1, 3, 1, 2, 6 |
| turns of the state machine | 3 | 3 |
| `StrMatch` found, not found | 7, 14 | 7, 14 |
| `NumToStr(3,0)+"-"+ValToStr(1)`: its length, compared with "3-1" | 3, 1 | 3, 1 |
| a text of 80 characters (3 pieces): its length, compared | 80, 1 | 80, 1 |
| `"<"+strState` compared with "<DONE"; an empty text's length + 10 | 1, 10 | 1, 10 |
| "it's" (a backquote on the FANUC): its length, compared with itself | 4, 1 | 4, 1 |
| a routine's own string, set at each of two calls | 2 | 2 |
| texts passed to a routine: their lengths, those equal to "42" | 10, 1 | 10, 1 |

A program written by hand measures what TP does otherwise than RAPID: TP finds 'A' and 'a' equal
(RAPID does not) but not 'A' and 'A '; `FINDSTR` finds 'ROBOT' in 'load robot' (RAPID's `StrMatch`
does not) and gives 0 for an empty pattern (RAPID length+1, as for any text not found); a whole number
held as a real is written '3.000000' (RAPID's `NumToStr(3,0)` '3'); '12AB' reads as 12 where RAPID's
`StrToVal` fails. Hence what CrossArm converts: comparisons where the texts cannot differ by case
alone, `NumToStr` of numbers only ever whole, no `StrToVal`. `SUBSTR` past the end of a text stops the
program (INTP-323), as `StrPart` stops RAPID's. Loaded only: a text written in a string register, a
comparison with a text, a block `IF` or a `SELECT` on string registers, an argument of 39 characters
and an apostrophe are refused; an empty argument is stored `'...'`, so CrossArm writes an empty text
as one character and `SUBSTR` of none past it; no string register comment is kept.

Writing the probe found that a string never written and without initial value was not read as RAPID's
empty text, and that `roboguide.py` reported a program stopped by an error as done: both fixed. The
same measures settled the largest whole number a register line keeps, 2147483646 (2147483647 is
stored `********`): past it CrossArm writes a TODO.

## 25. Arrays the programs write, run

An array of numbers the programs change (a grid filled in loops, a command table written field by
field) is a block of registers, as an array only read is: an element at a fixed index is its own
register, one at an index known at run time `R[R[n]]`, the index worked out in a register first. A raw
probe first measured that the controller takes and runs `R[R[50]]=R[R[50]]+1`, `R[R[50]]=(-2.5)`,
`R[R[50]]=R[R[52]]` and `F[R[50]]=(ON)` read back in an `IF`.

[tools/make_array_write_probe.py](../tools/make_array_write_probe.py) converts a module that fills a
VAR array of 3 x 4 in two `FOR` loops (`awGrid{i,j}:=i*10+j`) in one routine and sums it in another,
then changes a PERS array at a fixed index from another element, with `Incr`, and at an index worked
out (`awTable{awK+1}:=awTable{awK}*2`), and reads elements back at fixed indices and at indices known
at run time. RobotStudio runs the RAPID, ROBOGUIDE the converted programs:

| Total | RobotStudio | ROBOGUIDE |
|---|---|---|
| sum of the grid | 270 | 270 |
| sum of the table after its changes | 231 | 231 |
| `awGrid{2,3}`; `awGrid{3,4}+awGrid{1,1}` | 23, 45 | 23, 45 |
| `awGrid{awK,awK+2}+awTable{awK}` | 94 | 94 |

Writing the probe found that the controller stores `R[R[3]]=...` with 4 spaces before `;`, as a register
assignment: CrossArm writes it so. Two tasks declaring the same PERS array each took a block of their
own: they share one now, as they share the PERS.

## 26. Bools set to a condition, run

A bool set to a condition is a flag set to TP's mixed logic, `F[n]=(R[1]<5 AND F[2]=OFF)`. A raw probe
loaded thirteen forms (NOT, AND, OR, nested parentheses, outputs, registers, flags, a negative constant):
each is stored as written and each gives the condition's value.

[tools/make_flag_probe.py](../tools/make_flag_probe.py) converts a module setting bools to a comparison,
to two joined by AND, to NOT another bool, to another bool, and to a comparison of texts joined with one
of numbers (written with jumps: TP compares texts in a jump only), then looping on a bool set at each turn:

| Total | RobotStudio | ROBOGUIDE |
|---|---|---|
| `3<5`, `3<5 AND 7>8`, `NOT TRUE`, a copy of TRUE, `"RUN"="RUN" AND 3=3` (1 when TRUE) | 1, 0, 0, 1, 1 | 1, 0, 0, 1, 1 |
| turns of `WHILE fpGo` with `fpGo:=fpTurns<4` | 4 | 4 |

## 27. Points passed by reference, run

A routine taking a point as `VAR` or `INOUT robtarget` can change it; the caller sees the change. On the
FANUC the point travels in a position register: the caller sets it before the CALL, the routine changes it
there and moves to it, and the caller reads it back after the CALL into the register its own point is
kept in.

[tools/make_point_ref_probe.py](../tools/make_point_ref_probe.py) converts a module that moves to a
point, shifts it twice by a routine taking it as `VAR robtarget` (which offsets it by 50 mm and moves
there), lowers it by 100 mm in a routine taking it as `INOUT robtarget` which passes it on to the first,
and reads its x, y and z back:

| Total | RobotStudio | ROBOGUIDE |
|---|---|---|
| y after two shifts; y, z, x after the lowering and a third shift | 150; 200, 900, 1100 | 150; 200, 900, 1100 |
| shifts made | 3 | 3 |

## 28. An output set at a fine point, run

`MoveLDO p,v500,fine,tool,doGrip,1` moves to `p` and sets `doGrip` when the robot reaches the fine point.
CrossArm writes the move, then `DO[1]=ON`: the line after a FINE move runs once the robot stands on the
point. [tools/make_move_do_probe.py](../tools/make_move_do_probe.py) runs that on ROBOGUIDE, reading the
TCP and `DO[1]` through COM while it runs: the output switches with the TCP 0.000 mm from the point, 50 ms
after the TCP is within 0.5 mm of it. The RobotStudio virtual controller has no signals to run `MoveLDO`
on: RAPID's timing is the manual's. Through a zone, RAPID sets the output in the middle of the corner
path, which no TP line does (TP sets one at a time or distance before the point): such a `MoveLDO` stays
TODO. For the same reason `WaitRob \InPos` after a FINE move needs nothing on the FANUC.

## 29. Waits with a time flag, run

With `\TimeFlag`, a wait with `\MaxTime` raises no error when the time runs out: it sets the bool and
the program goes on. CrossArm writes the timed wait as for the other waits with `\MaxTime` (a loop
polling a TIMER: `$WAITTMOUT` is write-protected for programs), then sets the flag to whether the time
ran out, `F[3]=(R[5:WaitTimer]>=1.5)`.

[tools/make_time_flag_probe.py](../tools/make_time_flag_probe.py) converts a module waiting 1.5 s at most
on a bool no one sets, then on one already TRUE, timing each wait with a clock:

| Total | RobotStudio | ROBOGUIDE |
|---|---|---|
| the flag after the wait that runs out; after the one that does not | TRUE, FALSE | TRUE, FALSE |
| the time each wait took | 1.600 s, 0.000 s | 1.504 s, 0.000 s |

RAPID's `WaitUntil` checks its condition every 0.1 s (`\PollRate`): it notices the time ran out at the
next check, 1.6 s.

## 30. A search, run

`SearchL \Stop,diProbe,pFound,pEnd,v50,tool` moves towards `pEnd` until `diProbe` switches on, and
`pFound` is where the TCP was then. CrossArm writes `SKIP CONDITION DI[1]=ON`, then the move with
`Skip,LBL[2],PR[99]=LPOS`: `PR[99]` keeps `pFound`, read afterwards as any point known at run time. RAPID
searches for the input switching on: before the move, the program checks it is not on already.

The RobotStudio virtual controller has no signals to run `SearchL` on: what RAPID does is the manual's.
[tools/make_search_probe.py](../tools/make_search_probe.py) converts a module searching along y from 50
to 250 mm and runs it on ROBOGUIDE, a sampler reading the TCP through COM and switching the input on as
the TCP passes y = 150:

| Search | ROBOGUIDE | RAPID |
|---|---|---|
| `\Stop`: y of the point found, for the input switched at 150.025 | 150.025 | where the input switched |
| `\Stop`: y where the robot stands after the search | 150.125 (it went 6.4 mm past, then came back) | past the switch, by the stopping distance |
| a move 50 mm above the point found (`Offs`) | y 150.025, z 1050 | the same |
| `\Sup`: the point found; where the robot stands after the search | 150.075; 250 | the same: it goes on to the point |
| the input already on at the start | the program pauses on the `MESSAGE` | an error stops the program |

The difference that stays is where the robot stops: past the switch on both, but the FANUC comes back to
it. The report says it, as a search by contact pushes the tool into the part by the stopping distance at
the search speed.

The same probe moves along y at several speeds with and without a skip recording the position, never
switched. A skip recording it (`PR[k]=LPOS`) slows the move down: at 50 and 100 mm/s the TCP moves as
fast as without a skip, at 120 and 250 mm/s at the speed of 100 mm/s (the FANUC course says 250 for the
high-speed skip). CrossArm leaves a search faster than 100 mm/s TODO rather than slow it down, which
would change what it measures and the cycle time.

## 31. Arrays of bools, run

An array of bools the programs change, or read at an index known at run time, is a block of flags, as
an array of numbers is a block of registers: an element at a fixed index is its own flag, one at an
index known at run time `F[R[n]]`, the index worked out in a register first, set to a condition as
any flag (`F[R[12]]=(F[R[2]])`, `F[1020]=(F[1023]=ON AND F[1021]=OFF)`).

[tools/make_flag_array_probe.py](../tools/make_flag_array_probe.py) converts a module that marks a VAR
array of six slots in a `FOR` loop in one routine (`faSlot{i}:=i>3`) and counts the slots set in
another, sets elements at fixed indices and to a condition of other elements, then sets a PERS array of
2 x 3 at indices worked out and counts what is set. RobotStudio runs the RAPID, ROBOGUIDE the converted
programs:

| Total | RobotStudio | ROBOGUIDE |
|---|---|---|
| slots set | 5 | 5 |
| sum of i*10+j over the elements of the 2 x 3 array set | 44 | 44 |
| an element and another set at fixed indices both set; an element clear | 1, 1 | 1, 1 |
