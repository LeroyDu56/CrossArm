## CrossArm 1.6.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review. 1.6 is for converting again a program already commissioned, and for the routines
CrossArm cannot write. It converts about 60 % of the instructions of public open-source programs, 87 % to 93 %
of our own test corpus, written for testing ([why not 100 %](https://github.com/LeroyDu56/CrossArm#why-not-100-)).

**Programs the integrator provides.** A routine CrossArm cannot write (missing from the backup, or using
files, sockets or byte buffers) can be a TP or KAREL program written on the FANUC side, named under the new
mapping key `external_routines`: `{"WriteLog": {"program": "WRITE_LOG"}}`. Its calls become
`CALL WRITE_LOG(args)`, the routine is not written, and the report and checklist list each program to
provide with its arguments (`AR[1]`, `AR[2]`...) and the num read back. The mapping file CrossArm writes lists
the candidates with `"program": null`: they activate nothing until a name is filled in. Measured on ROBOGUIDE.

**Converting again, keeping the touch-ups.** Every conversion now writes `crossarm_points.json`, each point
written and the RAPID it came from. When the ABB program changes after commissioning,
`crossarm convert new_backup/ --keep-taught robot_programs/ --keep-taught crossarm_old/`, or step 5 of the
window, reads the robot's programs as they are now (`.LS`, or `.TP` decoded by FANUC PrintTP) and keeps
each point touched up there unless its ABB position or its frames changed; those are listed to touch up
again, with how far the touch-up was. A conversion made before 1.6 has no `crossarm_points.json`: convert
that old backup again once with 1.6 to get one. Measured on ROBOGUIDE: the robot goes to the touch-up kept
and to the new point.

**Reports that open on a decision.** The report opens on an analysis: ready, workable or not ready, by a
fixed rule printed under it (workable from 85 % of the RAPID instructions converted and at most 3 blocking
causes), the 3 to 7 things to do first, the main TODO causes, the share converted by area, and only the
controller resources near their limit. The detail follows; the checklist is folded until opened. The window
shows the decision too; its steps scroll on a small screen.

**A fix:** the window's result tiles are laid out two per row: the converted share was cut off.

**Still what 1.x keeps:** a mapping file written for 1.0 to 1.5 gives the same numbers, and the command
line keeps its options (`--keep-taught` is new). `external_routines` is a new key: without it, nothing
changes. Numbers CrossArm picks by itself can move from one version to the next: give a conversion its
mapping file back to keep them. The whole list:
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

This version becomes Apache 2.0 on 2030-10-07.

`python_license.txt` next to the executable covers the Python runtime bundled inside it; see
[THIRD_PARTY_LICENSES.md](https://github.com/LeroyDu56/CrossArm/blob/main/THIRD_PARTY_LICENSES.md).

## Download

**`CrossArm.exe`**: Windows 10/11, nothing to install.

- **Drop** an ABB backup folder, a zipped backup or RAPID files **on the icon** — with the target
  FANUC backup alongside if you have it — or
- **double-click** it and choose them in the window.

The `.LS` programs, `SETUP_FRAMES.LS`, the conversion report (`crossarm_report.html`), the editable
`crossarm_mapping.json`, `crossarm_points.json` and `crossarm_log.txt` are written to a new
`crossarm_<name>` folder next to the input, with a `TP` folder of `.TP` programs when step 4 is used. Everything runs locally: no file
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
