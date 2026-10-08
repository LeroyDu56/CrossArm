# CrossArm conversion report

- Generated: 2026-01-01 08:00:00 by CrossArm 1.7.0
- Sources: `hmi_and_groups.mod`
- Programs: 1, items to review: 0 TODO, 0 warnings

> The `.LS` files are text listings to load and check in ROBOGUIDE (or convert on the controller).
> They are **not** directly executable: frames, registers, I/O numbers and every TODO below
> must be reviewed by the integrator before running on a robot.
> The points are the ABB's, as theoretical points: touch them up on the robot. The path between them
> is within 10 mm of the ABB's (measured: within 4 mm, corners included).

## Analysis

- **Ready for commissioning: load the programs, set the frames and touch up the points.**
- Rule: ready when every instruction is converted; workable when at least 85 % of the RAPID instructions are converted and at most 3 causes are blocking; not ready otherwise. Here: 100 % converted, 0 blocking causes.
- 100 % of the 8 RAPID instructions converted.
- 1 of 1 programs with no TODO, 0 with TODO (0 TODO).

### What to do first

1. **Load every program before running any**: a CALL to a program the robot does not have fails when it runs. (Checklist: Load the programs.)

## Summary

- **1 of 1 programs converted with no TODO.**
- **100 % of the 8 RAPID instructions converted.**
- 0 TODO (not converted) and 0 warnings (converted on an assumption).

### Instructions converted, by area

Counted per RAPID instruction, comments and declarations left out. Converted: written as TP, possibly on an assumption listed under the warnings. Not converted: a TODO, alone or inside a block that is one.

| Area | Instructions | Converted | Share |
|---|---|---|---|
| I/O and waits | 2 | 2 | 100 % |
| Data | 1 | 1 | 100 % |
| Operator messages | 5 | 5 | 100 % |
| **All** | **8** | **8** | **100 %** |

### Controller capacity

Numbers are allocated automatically from 1 up, with no upper bound. A resource marked **over** produces `.LS` files a controller with those limits cannot load: pin the numbers with a mapping file, reuse frames, or raise the limit (`limits`) if the controller has the option. The default limits are those of a standard controller — check yours.

| Resource | Used | Highest | Limit | Status |
|---|---|---|---|---|
| R | 1 | 1 | 200 | ok |

## Programs

| TP program | RAPID routine | Lines | Points | TODO |
|---|---|---|---|---|
| `REPORTCYCLE.LS` | HmiAndGroups.ReportCycle | 8 | 0 | 0 |

## Frames to set up on the controller

Values are the RAPID frames converted to FANUC X, Y, Z (mm) and W, P, R (deg).
User frames are `uframe x oframe` of the work object, relative to the robot world frame.

### User frames (UFRAME)

_None._

### Tool frames (UTOOL)

The tool frames are the ABB ones as they are. That puts the tool's guide pin in the pin hole on -x of the FANUC faceplate frame: for the same TCP pose it is where the ABB flange had it (on the ABB, the guide pin hole is on -x of tool0). The two flanges differ, so the adapter plate decides: with the pin in the +x hole, the ISO 9409-1 position, set `"tool_pin": "+x"` in the mapping file.

_None._

## Registers, flags and I/O

Automatic numbers start at 1: pin them with a mapping file (`--map`) to avoid clashing with registers and I/O already used on the controller.

| TP | RAPID name | Number from | Note |
|---|---|---|---|
| R[1] | nCode | automatic | RAPID VAR initial value 0: set it on the controller |
| GO[1] | goEchoCode | automatic |  |
| GO[2] | goStatus | automatic |  |
| GI[1] | giCycleCode | automatic |  |

## Speed and zone mapping

- Linear and circular moves keep their speed in mm/s: measured on both robots, a move takes as long up to 1000 mm/s. Joint moves: `%` = RAPID TCP speed / 4500 mm/s (`joint_speed_ref_mm_s`), clamped to 1-100 %: the TCP speed a J 100 % move reaches, measured on the M-20iD/25 (3,800 to 5,300 mm/s depending on the move, so a joint move can take 20 % more or less time than on the ABB).
- Zones: a RAPID zone rounds a corner by about the same distance at any speed, a CNT by more the faster the move. Each zone is written as the smallest CNT that rounds a right-angle corner as much at the move's speed, from both robots measured (M-20iD/25, `zone_mapping`). Into a faster move the FANUC rounds more, so the CNT is matched at the next move's speed there. Run on both robots (approaches, retracts, reversals, acute and obtuse corners, 50 mm zigzags), the FANUC path stays within about 1 mm of the ABB's or closer to the points; check it where it passes close to something.

_None._

_None._

## Points

## Items to review

_None._
