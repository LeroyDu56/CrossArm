# CrossArm conversion report

- Generated: 2026-01-01 08:00:00 by CrossArm 1.1.0
- Sources: `logic_and_io.mod`
- Programs: 2, items to review: 0 TODO, 4 warnings

> The `.LS` files are text listings to load and check in ROBOGUIDE (or convert on the controller).
> They are **not** directly executable: frames, registers, I/O numbers and every TODO below
> must be reviewed by the integrator before running on a robot.
> The points are the ABB's, as theoretical points: touch them up on the robot. The path between them
> is within 10 mm of the ABB's (measured: within 4 mm, corners included).

## Summary

- **2 of 2 programs converted with no TODO.**
- **100 % of the 27 RAPID instructions converted.**
- 0 TODO (not converted) and 4 warnings (converted on an assumption).

### Instructions converted, by area

Counted per RAPID instruction, comments and declarations left out. Converted: written as TP, possibly on an assumption listed under the warnings. Not converted: a TODO, alone or inside a block that is one.

| Area | Instructions | Converted | Share |
|---|---|---|---|
| Motion | 4 | 4 | 100 % |
| I/O and waits | 9 | 9 | 100 % |
| Program flow | 9 | 9 | 100 % |
| Data | 5 | 5 | 100 % |
| **All** | **27** | **27** | **100 %** |

### Assumptions to check

| Assumption | WARNING | Share | Most common case |
|---|---|---|---|
| posture converted with the measured axis conventions | 2 | 50 % | joint targets (MoveAbsJ) converted with the measured axis conventions (J3 absolute, J4/J5… |
| I/O signal without a mapping | 2 | 50 % | 'diForceRow' assumed to be a digital input from its name |

### Controller capacity

Numbers are allocated automatically from 1 up, with no upper bound. A resource marked **over** produces `.LS` files a controller with those limits cannot load: pin the numbers with a mapping file, reuse frames, or raise the limit (`limits`) if the controller has the option. The default limits are those of a standard controller — check yours.

| Resource | Used | Highest | Limit | Status |
|---|---|---|---|---|
| UFRAME | 2 | 1 | 9 | ok |
| UTOOL | 2 | 2 | 10 | ok |
| R | 6 | 6 | 200 | ok |
| F | 1 | 1 | 1024 | ok |

## Programs

| TP program | RAPID routine | Lines | Points | TODO |
|---|---|---|---|---|
| `PALLETIZE.LS` | LogicAndIo.Palletize | 31 | 3 | 0 |
| `COUNTDOWN.LS` | LogicAndIo.CountDown | 13 | 0 | 0 |

## Frames to set up on the controller

Values are the RAPID frames converted to FANUC X, Y, Z (mm) and W, P, R (deg).
User frames are `uframe x oframe` of the work object, relative to the robot world frame.

### User frames (UFRAME)

| UF | RAPID wobjdata | X, Y, Z | W, P, R | Problem |
|---|---|---|---|---|
| 0 | wobj0 | 0.000, 0.000, 0.000 | 0.000, 0.000, 0.000 |  |
| 1 | wobjStack | 800.000, -200.000, 0.000 | 0.000, 0.000, 0.000 |  |

### Tool frames (UTOOL)

The tool frames are the ABB ones as they are. That puts the tool's guide pin in the pin hole on -x of the FANUC faceplate frame: for the same TCP pose it is where the ABB flange had it (on the ABB, the guide pin hole is on -x of tool0). The two flanges differ, so the adapter plate decides: with the pin in the +x hole, the ISO 9409-1 position, set `"tool_pin": "+x"` in the mapping file.

| UT | RAPID tooldata | X, Y, Z | W, P, R | Problem |
|---|---|---|---|---|
| 1 | tool0 | 0.000, 0.000, 0.000 | 0.000, 0.000, 0.000 |  |
| 2 | tSuction | 0.000, 0.000, 120.000 | 0.000, 0.000, 0.000 |  |

### Payloads to set up (PAYLOAD)

Set one payload schedule per tool before running the programs: MENU > SYSTEM > Motion, on the robot. Unlike the frames, a program cannot do it: the controller holds the payload schedules read-only for TP programs. Values are converted to the units of that screen: centre of gravity in cm in the flange frame (RAPID mm / 10), inertia in kgf.cm.s2 (RAPID kg.m2 / 0.0980665). The schedule number is the tool's UTOOL number; a tool holding a part (GripLoad) has a schedule of its own, which the programs select with PAYLOAD[n] where the RAPID grips or releases.

The z coordinate and the mass carry over as they are; x and y depend on the pin hole the tool is fitted by, like the tool frames above.

| PAYLOAD | RAPID tooldata | Mass (kg) | Centre X, Y, Z (cm) | Inertia X, Y, Z (kgf.cm.s2) | Note |
|---|---|---|---|---|---|
| 2 | tSuction | 1.5 | 0, 0, 6 | 0, 0, 0 |  |

## Registers, flags and I/O

Automatic numbers start at 1: pin them with a mapping file (`--map`) to avoid clashing with registers and I/O already used on the controller.

| TP | RAPID name | Number from | Note |
|---|---|---|---|
| R[1] | nParts | automatic | RAPID PERS initial value 0: set it on the controller |
| R[2] | nRow | automatic | RAPID VAR initial value 0: set it on the controller |
| R[3] | nCol | automatic | RAPID VAR initial value 0: set it on the controller |
| R[4] | tSettle | automatic | RAPID PERS initial value 0.4: set it on the controller |
| R[5] | k | automatic |  |
| R[6] | nLayer | automatic | RAPID PERS initial value 0: set it on the controller |
| F[1] | bStackFull | automatic |  |
| DO[1] | doRowStart | automatic |  |
| DO[2] | doVacuum | automatic |  |
| DI[1] | diStackReady | automatic |  |
| DI[2] | diForceRow | automatic |  |
| DI[3] | diAbort | automatic |  |

## Speed and zone mapping

- Linear and circular moves keep their speed in mm/s: measured on both robots, a move takes as long up to 1000 mm/s. Joint moves: `%` = RAPID TCP speed / 4500 mm/s (`joint_speed_ref_mm_s`), clamped to 1-100 %: the TCP speed a J 100 % move reaches, measured on the M-20iD/25 (3,800 to 5,300 mm/s depending on the move, so a joint move can take 20 % more or less time than on the ABB).
- Zones: a RAPID zone rounds a corner by about the same distance at any speed, a CNT by more the faster the move. Each zone is written as the smallest CNT that rounds a right-angle corner as much at the move's speed, from both robots measured (M-20iD/25, `zone_mapping`). Into a faster move the FANUC rounds more, so the CNT is matched at the next move's speed there. Run on both robots (approaches, retracts, reversals, acute and obtuse corners, 50 mm zigzags), the FANUC path stays within about 1 mm of the ABB's or closer to the points; check it where it passes close to something.

| RAPID speed | Motion | TP |
|---|---|---|
| v1000 | J | 22% |
| v200 | L | 200mm/sec |
| v500 | L | 500mm/sec |
| v800 | J | 18% |

| RAPID zone | RAPID speed | Motion | TP | Corner cut ABB / FANUC (mm) | Note |
|---|---|---|---|---|---|
| fine | v1000 | J | FINE |  |  |
| fine | v200 | L | FINE |  |  |
| z20 | v500 | L | CNT74 | 8.6 / 8.7 |  |
| z50 | v800 | J | CNT100 | 16.2 / 14.5 | CNT100 rounds less: the FANUC path stays closer to the point |

## Points

### PALLETIZE

| P | RAPID target | RAPID line | UF/UT | Value |
|---|---|---|---|---|
| P[1] | `jSafe` | 24 | 0/1 | J 0.000 -20.000 -0.000 -0.000 -70.000 180.000 |
| P[2] | `Offs(pStack, 0, 0, 150)` | 34 | 1/2 | X 500.000 Y -300.000 Z 550.000 W 180.000 P 0.000 R 90.000 |
| P[3] | `pStack` | 35 | 1/2 | X 500.000 Y -300.000 Z 400.000 W 180.000 P 0.000 R 90.000 |

## Items to review

| Program | RAPID line | Kind | Detail |
|---|---|---|---|
| COUNTDOWN | 52 | WARNING | 'diAbort' assumed to be a digital input from its name |
| PALLETIZE | 24 | WARNING | joint targets (MoveAbsJ) converted with the measured axis conventions (J3 absolute, J4/J5/J6 reversed, J6 +180): same posture, but the TCP lands elsewhere on another robot model, check joint limits and clearances |
| PALLETIZE | 29 | WARNING | 'diForceRow' assumed to be a digital input from its name |
| PALLETIZE | 34 | WARNING | CONFIG derived from ABB confdata (measured conventions, see docs). A different robot model can need a different posture to reach the same point, and the J6 turn number assumes the tool's pin is in the -x hole of the faceplate (tool_pin): check reachability in ROBOGUIDE |
