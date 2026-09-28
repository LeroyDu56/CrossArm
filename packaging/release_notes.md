## CrossArm 1.0.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`): motions,
positions, tool and user frames, arm configuration, speeds and zones, I/O, registers and program
logic, with a report of everything left to review. It was checked against an IRB 6700 in
RobotStudio on three FANUC robots in ROBOGUIDE (M-20iD/25, R-2000iC/190S, R-1000iA/80F).

**Loads, and does what the RAPID did.** Every program converted from the test corpus loads on a
FANUC controller, every form of instruction CrossArm writes is stored as written, and the flange
lands within 0.004 mm of where the ABB puts it.

**The points are theoretical, the path is close.** The positions CrossArm writes are the ABB's,
carried over exactly, to be touched up on the robot at commissioning as on any robot swap. The path
between them stays within 4 mm of the ABB's on every move measured, where CrossArm aims for 10.

**Speeds and zones measured, not guessed.** The same moves were timed and traced on both robots:
joint moves take about as long as on the ABB, and each zone is written as the CNT that rounds a
corner as much at the move's speed. CrossArm reads the arm in the FANUC backup and uses the profile
measured on its series (M-20iD and ARC Mate 120iD, R-2000iC, R-1000iA); for another arm it says so.

**Fits the robot in place.** Given the FANUC robot's backup, CrossArm leaves its frames, registers,
I/O and program names alone; `crossarm_mapping.json` pins any number, and `SETUP_FRAMES.LS` sets
every tool and user frame on the robot.

**Computes what TP cannot.** A tool or work object the RAPID builds from fixed values (`DefFrame`,
`PoseMult`, a FUNC of the backup) is worked out at conversion time and loaded from a position
register where the RAPID computes it. When something can change what it reads, or it is measured
on the robot, it stays a TODO that says why.

**What 1.x keeps:** mapping files keep working, a conversion given back its mapping file keeps its
numbers, and the command line keeps its options.

See the [README](https://github.com/LeroyDu56/CrossArm#readme), the
[user guide](https://github.com/LeroyDu56/CrossArm/blob/main/docs/guide.md) and
[how it was validated](https://github.com/LeroyDu56/CrossArm/blob/main/docs/validation.md).

## Licence

CrossArm is published under the **Business Source License 1.1**.

**Trying it is free**: evaluating it on your own backups, development, testing,
teaching, personal projects. **Production use needs a commercial licence** —
programs loaded on a real robot, conversions delivered to a customer, or billed
migration work. See [LICENSING.md](https://github.com/LeroyDu56/CrossArm/blob/main/LICENSING.md)
for where the line falls, and write to **enzoleroy56@gmail.com** for a licence.

This version becomes Apache 2.0 on 2030-09-26.

`python_license.txt` next to the executable covers the Python runtime bundled inside it; see
[THIRD_PARTY_LICENSES.md](https://github.com/LeroyDu56/CrossArm/blob/main/THIRD_PARTY_LICENSES.md).

## Download

**`CrossArm.exe`**: Windows 10/11, nothing to install.

- **Drop** an ABB backup folder, a zipped backup or RAPID files **on the icon** — with the target
  FANUC backup alongside if you have it — or
- **double-click** it and choose them in the window.

The `.LS` programs, `SETUP_FRAMES.LS`, the conversion report (`crossarm_report.html`), the editable
`crossarm_mapping.json` and `crossarm_log.txt` are written to a new `crossarm_<name>` folder next to
the input. Everything runs locally: no file leaves the computer.

## First launch: Windows SmartScreen

The executable is not code-signed, so Windows may show *"Windows protected your PC"*.
Click **More info → Run anyway**. To check that the file is the one built from this
repository, compare its SHA-256 with `CrossArm.exe.sha256` (built by GitHub Actions from the
tagged commit):

```powershell
(Get-FileHash CrossArm.exe -Algorithm SHA256).Hash
```

Python users can also install from source (`pip install .`) and run `crossarm` / `crossarm-gui`.
