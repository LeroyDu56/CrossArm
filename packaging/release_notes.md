## CrossArm 1.5.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review. 1.5 is for a robot that cannot load `.LS` programs, and for the commissioning that
follows. It converts about 60 % of the instructions of public open-source programs, 87 % to 93 % of our own
test corpus, written for testing ([why not 100 %](https://github.com/LeroyDu56/CrossArm#why-not-100-)).

**Binary `.TP` programs, for a robot without ASCII Upload.** A FANUC controller without the ASCII Upload
option loads only `.TP`. `crossarm convert --tp-robot <ROBOGUIDE robot folder>` (or `--tp` with a Setrobot
`robot.ini`), or step 4 of the window, has FANUC MakeTP, installed with ROBOGUIDE, make a `.TP` of every
program into a `TP` folder to copy to a USB stick. Optional: without MakeTP, the report says so and nothing
else changes. Measured on ROBOGUIDE: the `.TP` load and run, and decode back to the lines of their `.LS`.

**An interactive report, with a commissioning checklist.** `crossarm_report.html` shows each RAPID routine
and its TP side by side, line by line, every TODO marked with its cause; the items to review are filtered by
kind, cause and program, or searched, each leading to its line. A checklist follows the order the cell is
brought up (loading, frames and tools with their values, payloads, I/O, registers, TODO lines, points to touch
up, motion to check), each item linked to the lines using it, its ticks kept in the browser, printable. One
self-contained page: it works offline.

**Jointtargets read on the robot.** `j:=CJointT()` is kept in a joint position register (`PR[k]=JPOS`), its
axes `j.robax.rax_i` read with the measured axis conventions (the ABB values), and `MoveAbsJ j` is `J PR[k]`.
Measured on both controllers.

**A fix: negative constants in conditions.** A condition with a bare negative constant (`IF R[1]>-30`, a
`WAIT`, a flag set to a condition, `F[n]=(...)`), as earlier versions wrote it, loads on the controller but
stops the program with INTP-202 (syntax error) when the line runs. 1.5 writes it `(-30)`, measured to run.
Convert again any program converted by an earlier version that has such a condition.

**Still what 1.x keeps:** a mapping file written for 1.0 to 1.4 gives the same numbers, and the command
line keeps its options (`--tp` and `--tp-robot` are new). Numbers CrossArm picks by itself can move from one
version to the next: without a mapping file given back, a jointtarget now kept in a position register can move
the other position register numbers by one, compared with 1.4. Give a conversion its mapping file back to keep
them. The whole list:
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
`crossarm_mapping.json` and `crossarm_log.txt` are written to a new `crossarm_<name>` folder next to
the input, with a `TP` folder of `.TP` programs when step 4 is used. Everything runs locally: no file
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
