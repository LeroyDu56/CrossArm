## CrossArm 1.1.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review. 1.1 converts more of what real programs are made of, and each new construct
was measured on the controllers before CrossArm writes it: RobotStudio for the RAPID, ROBOGUIDE for the TP.

**`TEST` / `CASE` becomes `SELECT`.** One line per value, a case that only calls a routine calls it on
its own line, the rest behind labels; run on both controllers, the same branches are taken.

**The everyday instructions.** `PulseDO` (in the tenths of a second FANUC takes), `InvertDO`, the
RAPID clocks as `TIMER`, `SetAO` in the FANUC module's counts, and `GripLoad` as a `PAYLOAD` schedule
of the tool and the part together, worked out by CrossArm. Motion settings FANUC does its own way are
left out with a warning; those that slow the robot down stay TODO, rather than run it faster.

**Routines given text and points.** A string is passed in the call; a point (robtarget) in a position
register the caller sets and the routine moves to, `Offs()` included. Twenty-eight moves through
routines and arrays land at the poses of the moves written out, to the thousandth of a millimetre.

**Arrays indexed at run time.** A table of points (`pSlot{nTool}`, `pGrid{r,c}`) or of numbers
(`nTorque{i}`) is kept in registers `SETUP_FRAMES` fills, and read as `PR[R[n]]` or `R[R[n]]`.

**Still what 1.x keeps:** a mapping file written for 1.0 gives the same numbers, and the command line
keeps its options. The whole list: [CHANGELOG](https://github.com/LeroyDu56/CrossArm/blob/main/CHANGELOG.md).

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

This version becomes Apache 2.0 on 2030-09-29.

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
