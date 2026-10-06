## CrossArm 1.4.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review. 1.4 converts routines given their speed and zone, and tells what is left apart by
cause. It converts about 60 % of the instructions of public open-source programs, 86 % to 93 % of our own
test corpus, written for testing ([why not 100 %](https://github.com/LeroyDu56/CrossArm#why-not-100-)).

**Speeds and zones as parameters.** A routine given its speed and zone (`PROC Approach(robtarget p,speeddata
v,zonedata z)`) makes its moves with what each call gives it: the call passes the speed and the CNT of each
corner (`CALL APPROACH(400,9,100)`), the routine moves with them from registers (`L P[1] R[1]mm/sec CNT R[3]`),
and `fine` given for a zone is a FINE move. Measured on both controllers: the moves take the time they take
written with constants.

**More converted.** A `byte` kept in a register; a `WaitTime` of a calculation (`WAIT R[n]`); `CRobT()` without
`\Tool` and `\WObj` read in the frames selected (`PR[k]=LPOS`); a number worked out with RAPID's math
functions (`Pow`, `Sqrt`, `Sin`...) from data no program changes; a routine with a parameter that is an array
of two or more dimensions.

**Causes told apart.** A routine or data no module of the backup declares is "routine or data not in the
backup", saying what to add. Files, sockets, byte buffers, operator dialogs and positions read on the robot
are "RAPID instruction without a TP equivalent", with why, also for a call to a routine of the backup that
uses them, and for its `ERROR` handler: work to redo another way on the FANUC, not a conversion still to
come.

**Still what 1.x keeps:** a mapping file written for 1.0 to 1.3 gives the same numbers, and the command
line keeps its options. Numbers CrossArm picks by itself can move from one version to the next: give a
conversion its mapping file back to keep them. The whole list:
[CHANGELOG](https://github.com/LeroyDu56/CrossArm/blob/main/CHANGELOG.md).

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

This version becomes Apache 2.0 on 2030-10-06.

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
