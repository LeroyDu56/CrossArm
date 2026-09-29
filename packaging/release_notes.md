## CrossArm 1.2.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review. 1.2 converts more of what real cells do, and each new construct was measured
on ROBOGUIDE before CrossArm writes it.

**Interrupts.** `ISignalDI`, `ISignalDO` and `IPers` become FANUC condition monitors: a condition
program `WHEN DI[n]=ON+,CALL TRAP` armed with `MONITOR`, the TRAP arming it again as it ends. Measured:
one call per edge, the program held while the TRAP runs and the move under way not slowed, as in
RAPID. A TRAP several interrupts share reads `INTNO` through a relay per interrupt.

**Routines given more.** A record is passed as the components the routine reads; a number passed by
reference comes back to the caller; a tool or a work object is passed as its frame number and selected
by the routine. `Incr`, `Decr`, `Add`, `Clear` and `RelTool()` of a point given at run time convert too.

**Palletizing.** Calculations of any length, one operation per line, and points the programs work out
as they run (`Offs()` of the loop counters, a turn with `RelTool()`, `CRobT()`) kept in position
registers. A place worked out in two loops lands where the moves written out land, to the thousandth
of a millimetre. On the test corpus, the palletizing cell goes from 88 % to 93 % of its RAPID converted.

**Still what 1.x keeps:** a mapping file written for 1.0 or 1.1 gives the same numbers, and the command
line keeps its options. The whole list: [CHANGELOG](https://github.com/LeroyDu56/CrossArm/blob/main/CHANGELOG.md).

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
