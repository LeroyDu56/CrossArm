## CrossArm 1.7.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review. 1.7 adds KAREL, as an option, for what TP cannot compute. Without it, CrossArm
converts about 60 % of the instructions of public open-source programs, 87 % to 93 % of our own test corpus,
written for testing ([why not 100 %](https://github.com/LeroyDu56/CrossArm#why-not-100-)).

**`--karel` and CrossArm's KAREL programs.** With the new option `--karel` (or step 6 of the window, off by
default), what TP has no arithmetic or instruction for is written as calls to a fixed library of KAREL
programs CrossArm ships: poses computed while the robot runs (`PoseMult`, `PoseInv`, `RelTool`, `DefFrame`
become `CALL CA_POSEMULT(...)` and the like, the poses kept in position registers), the tool and user frames
calibrated from them (loaded where the RAPID sets them, `UFRAME[n]=PR[k]`), and RAPID's text files (`Open`,
`Write`, `Close` become `CALL CA_FILE(...)`; the files of `HOME:` are written on the controller's `UD1:`, byte
for byte as RAPID writes them). Each program was measured on ROBOGUIDE.

**What the robot needs.** The programs land in a `KAREL` folder of the output, compiled to `.pc` by FANUC
ktrans when it is installed (with ROBOGUIDE), for the software version of the `--tp-robot` robot; without
ktrans, as `.kl` with the command to compile them. A real controller needs the KAREL option (R632). Load the
`.pc` before the `.LS`: a program calling one the robot does not have stops on that `CALL`. The report gets a
"KAREL programs" section, an action of the analysis and a checklist group; without `--karel`, it says how many
TODO the option would convert.

**What stays TODO.** Sockets, with `--karel` too: KAREL socket messaging needs client tags configured on the
robot, which CrossArm does not set up. A socket routine can still be a program the integrator provides
(`external_routines`). Also left: `PoseVect`, reading files, and the error handlers of file routines.

**Still what 1.x keeps:** without `--karel`, the programs are the ones 1.6 writes (the report adds what
`--karel` would convert). A mapping file written for 1.0
to 1.6 gives the same numbers, and the command line keeps its options (`--karel` is new). Numbers CrossArm
picks by itself can move from one version to the next: give a conversion its mapping file back to keep them.
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

This version becomes Apache 2.0 on 2030-10-08.

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
