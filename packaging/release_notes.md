## CrossArm 1.8.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review. 1.8 is for calibration routines, which compute tools and work objects while the
robot runs. Without `--karel` and without provided routines, CrossArm converts about 60 % of the
instructions of public open-source programs, 87 % to 93 % of our own test corpus, written for testing
([why not 100 %](https://github.com/LeroyDu56/CrossArm#why-not-100-)).

**Tools and work objects, field by field.** A frame computed from a tool's `tframe` no longer waits for its
`tload` to be known, and a field left TODO only makes TODO what reads it. A frame written part by part at run
time (`w.uframe.trans := p.trans`, `t.tframe.trans.z := ...`) is read back from the controller, its parts
written by TP and loaded where the RAPID sets it (`PR[91]=UFRAME[3]`, `PR[91,1]=PR[97,1]`, `UFRAME[3]=PR[91]`);
a frame copied (`wB.uframe := wA.uframe`) is loaded into the other one, past the controller's limit through its
bank register. A FUNC of the backup that builds a tool, a work object or a pose from such a frame (its body only
assignments and pose functions) is copied into each call, in TP, or with `--karel` when the orientation is only
known at run time; the report says at how many calls each was copied, to convert again after it changes.

**Functions you provide.** `external_routines` takes functions too: `x := F(args)`, F returning a num, pos,
pose or robtarget, becomes `CALL PROG(args,k)`, the program writing its result in `R[AR[n]]` or `PR[AR[n]]`
for the caller to read; points are passed by their position register's number, and `"returns"` types a
function the backup does not declare. Also new: `SetSysData`, routines called by a name worked out at run time
(a `SELECT` over the routines the name can be), waits with `\Visualize`, records passed by reference.
`GetSysData` and `OpMode()` stay TODO, saying why: a TP program reads no system variable on the controller
measured. Every form was measured on ROBOGUIDE (four new probes).

**Fixes to convert again for.** A mapping file given back with tool or user frames past the controller's
limit selected them by their number (`UTOOL_NUM=11`, refused by the controller) instead of loading them from
their position register. **Versions 1.0.0 to 1.7.0 are affected: convert again with the same mapping file**,
which keeps its meaning. A mapping file given back to a backup of several tasks renamed the other tasks' main
programs; each task's file now says which task it was written for (`"task"`). The report says what `--karel`
did on the run (each KAREL program, from which programs, how often).

**Still what 1.x keeps:** a mapping file written for 1.0 to 1.7 gives the same numbers (the keys added are
optional; a frame number past the limit means a bank register, as CrossArm always wrote it), and the command
line keeps its options. Numbers CrossArm picks by itself can move from one version to the next: give a
conversion its mapping file back to keep them.
The whole list: [CHANGELOG](https://github.com/LeroyDu56/CrossArm/blob/main/CHANGELOG.md).

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

This version becomes Apache 2.0 on 2030-10-09.

`python_license.txt` next to the executable covers the Python runtime bundled inside it; see
[THIRD_PARTY_LICENSES.md](https://github.com/LeroyDu56/CrossArm/blob/main/THIRD_PARTY_LICENSES.md).

## Download

**`CrossArm.exe`**: Windows 10/11, nothing to install.

- **Drop** an ABB backup folder, a zipped backup or RAPID files **on the icon** — with the target
  FANUC backup alongside if you have it — or
- **double-click** it and choose them in the window.

The `.LS` programs, `SETUP_FRAMES.LS`, the conversion report (`crossarm_report.html`), the editable
`crossarm_mapping.json`, `crossarm_points.json` and `crossarm_log.txt` are written to a new
`crossarm_<name>` folder next to the input, with a `TP` folder of `.TP` programs when step 4 is used and a
`KAREL` folder when step 6 is. Everything runs locally: no file
leaves the computer.

## First launch: Windows SmartScreen

The executable is not code-signed, so Windows may show *"Windows protected your PC"*.
Click **More info → Run anyway**. To check that the file is the one built from this
repository, compare its SHA-256 with `CrossArm.exe.sha256` (built by GitHub Actions from the
tagged commit):

```powershell
(Get-FileHash CrossArm.exe -Algorithm SHA256).Hash
```

Python users can also install from source (`pip install .`) and run `crossarm` / `crossarm-gui`.
