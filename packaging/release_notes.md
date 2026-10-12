## CrossArm 1.10.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review. 1.10 converts more of the RAPID that runs a cell through functions and errors, fixes
a numbering bug present since 1.0, and lets `CrossArm.exe` run the command line. Without `--karel` and without
provided routines, CrossArm converts about 60 % of the instructions of public open-source programs, 87 % to 93 %
of our own test corpus, written for testing
([why not 100 %](https://github.com/LeroyDu56/CrossArm#why-not-100-)).

**FUNCs of the backup as TP programs.** A FUNC returning a num, a bool or a robtarget whose value is only known
at run time is written as a TP program of its own: the caller runs `CALL F(args,k)` just before the line that
reads it (an assignment, an IF, each test of a WHILE, a move, an argument), and the program leaves its result in
`R[AR[n]]` or `PR[AR[n]]`. Only when its whole body converts; otherwise its calls stay TODO and name the line of
the FUNC that stops it. The report names these programs, in the analysis and in each calling program.

**Errors the program raises itself.** `RAISE` of the program's own errors (its errnum data, `RAISE n`) is
converted: the routine sets a register and ends, its caller tests it after the `CALL` and runs its ERROR handler
there (RETRY at most 4 times then ABORT, TRYNEXT, RETURN, RAISE to its own caller, ERRNO in a register).
**Changed:** as in RAPID, the end of an ERROR handler, including the one of a wait's timeout, now stops the
program (`ABORT`) instead of ending the routine (`END`). Errors of the system stay TODO.

**Fixed (since 1.0):** a num or bool of a routine with the name of module data, or of data of a routine it calls
or that calls it, shared that data's `R[]` / `F[]`, so one changed the other without warning. It now has its own
register, named `ROUTINE.name` in the mapping file. A 1.x mapping file that named it by its RAPID name keeps
that number for the module data. Also converted: `Abs()` compared with a constant, the x, y, z of a robtarget
parameter, and a PERS one task declares without value while another gives it one.

**`CrossArm.exe` on the command line.** `CrossArm.exe convert <backup> [options]`, `parse`, `stats`, `--help`
and `--version` do what the `crossarm` command does, with its output and exit codes (0, 1 for syntax errors,
2 for a usage error). A `.bat` waits for it; at a cmd prompt use `start /wait`, in PowerShell
`Start-Process -Wait`. Without arguments it opens the window, as before.

**Still what 1.x keeps:** a mapping file is read the same way and gives the same numbers (keys are only added),
and the command line keeps its commands and options. Numbers CrossArm picks by itself can move from one version
to the next: give a conversion its mapping file back to keep them.
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

This version becomes Apache 2.0 on 2030-10-12.

`python_license.txt` next to the executable covers the Python runtime bundled inside it; see
[THIRD_PARTY_LICENSES.md](https://github.com/LeroyDu56/CrossArm/blob/main/THIRD_PARTY_LICENSES.md).

## Download

**`CrossArm.exe`**: Windows 10/11, nothing to install.

- **Drop** an ABB backup folder, a zipped backup or RAPID files **on the icon** — with the target
  FANUC backup alongside if you have it — or
- **double-click** it and choose them in the window.
- or run it **on the command line**: `CrossArm.exe convert <backup> -o <folder>` (`--help` for the
  options).

The `.LS` programs, `SETUP_FRAMES.LS`, the conversion report (`crossarm_report.html`), the editable
`crossarm_mapping.json`, `crossarm_points.json`, `crossarm_log.txt`, the one-page
`crossarm_report_summary.md` and `crossarm_summary.json` are written to a new
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
