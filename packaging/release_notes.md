## CrossArm 1.3.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review. 1.3 converts the data cells keep their state in, and each new construct was
measured on the controllers before CrossArm writes it. It converts about 60 % of the instructions of
public open-source programs, 86 % to 93 % of our own test corpus, written for testing
([why not 100 %](https://github.com/LeroyDu56/CrossArm#why-not-100-)).

**State machines.** Data of a `RECORD` type is kept field by field in registers and flags; strings the
programs change in string registers, compared and worked out with TP's own string instructions; arrays
of numbers and of bools the programs write in blocks of registers and flags; a bool set to a condition
in its flag, with TP's mixed logic. RobotStudio and ROBOGUIDE give the same totals.

**Moves.** A point a routine changes comes back to its caller; `MoveLDO` to a fine point sets its output
with the robot on the point; `SearchL` on an input becomes a skip, the point found kept in a position
register (measured: within 0.1 mm of where the input switched; a search faster than 100 mm/s stays TODO,
as the controller would slow it down).

**Still what 1.x keeps:** a mapping file written for 1.0 to 1.2 gives the same numbers, and the command
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

This version becomes Apache 2.0 on 2030-10-05.

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
