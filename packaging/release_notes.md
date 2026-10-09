## CrossArm 1.9.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review. 1.9 makes the report a cockpit: in a minute, you know where the conversion stands
and what to do first; the detail opens only when you ask for it. Without `--karel` and without provided
routines, CrossArm converts about 60 % of the instructions of public open-source programs, 87 % to 93 % of
our own test corpus, written for testing
([why not 100 %](https://github.com/LeroyDu56/CrossArm#why-not-100-)).

**The decision first, the detail on demand.** A line stays at the top of the report: the decision (ready,
workable, not ready), the share converted, the TODO, the blocking causes, the points to touch up. Everything
but the analysis is folded, and long lists are laid out only when opened, so a large backup opens at once.
Three views choose how much opens (Synthesis, Integrator, Detail); the programs are in folders by name, each
with its counts, and a program opens on its TODO, two lines around each, a TODO followed from the list
highlighting its RAPID line and the TP lines written from it.

**Actions you can act on.** Each action of the analysis gives the exact number of TODO it concerns, leads to
them and says who acts: the FANUC integrator, the ABB backup, a robot option, or "a later CrossArm version may
help". Cosmetic TODO are apart; routines to provide come with an `external_routines` example to paste; over the
controller's capacity, the report proposes the mapping keys to edit. A sentence under the share converted by
area says what it means for the cell.

**A summary, a comparison, a spreadsheet.** Next to each report, `crossarm_report_summary.md` holds it on one
page and `crossarm_summary.json` its figures. Converting the same backup again compares with the previous
conversion: TODO, warnings and % then and now, causes gone and new; if RAPID files changed, it says how many,
and another backup is never compared. The items to review and the checklist export as CSV, and the report
prints as a 2-page summary or as the site checklist.

**Still what 1.x keeps:** the `.LS` programs and the mapping file are unchanged (no key added or removed), and
the command line keeps its options; two output files are added, none removed. Numbers CrossArm picks by
itself can move from one version to the next: give a conversion its mapping file back to keep them.
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
