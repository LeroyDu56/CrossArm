## CrossArm 1.10.1

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review before commissioning. **1.10.1 changes the documentation only: the programs written
are the same as 1.10.0.** The README is a short entry page, the
[user guide](https://github.com/LeroyDu56/CrossArm/blob/main/docs/guide.md) opens on a quick start, and
[how it was validated](https://github.com/LeroyDu56/CrossArm/blob/main/docs/validation.md) on a one-page summary.

**What 1.10 brought** ([CHANGELOG](https://github.com/LeroyDu56/CrossArm/blob/main/CHANGELOG.md)):

- a FUNC of the backup known only at run time becomes a TP program of its own, called where its value is read;
- `RAISE` of the program's own errors is converted, the caller's ERROR handler runs after the `CALL`;
- `CrossArm.exe` runs the command line (`convert`, `parse`, `stats`, `--help`, `--version`);
- the report, a cockpit since 1.9, names what this adds and the registers it keeps.

**Upgrading from 1.9 or earlier:** two changes can make a program converted again differ.
Data of a routine with the name of module data now get their own register, `ROUTINE.name` in the mapping file
(a fix, present since 1.0); the end of an ERROR handler now stops the program (`ABORT`) as in RAPID.
What to do: [upgrading to 1.10](https://github.com/LeroyDu56/CrossArm/blob/main/docs/guide.md#upgrading-to-110).
Mapping files and the command line keep working as before.

Not 100 %, not plug-and-play: about 60 % of the instructions of public programs convert, 87 % to 93 % of our own
test corpus, written for testing; the rest is marked `!TODO` with its cause
([why not 100 %](https://github.com/LeroyDu56/CrossArm#why-not-100-)).

**Licence:** free for evaluation and other non-production use; production use needs a commercial licence:
**enzoleroy56@gmail.com** ([LICENSING.md](https://github.com/LeroyDu56/CrossArm/blob/main/LICENSING.md)).
Business Source License 1.1; this version becomes Apache 2.0 on 2030-10-12. `python_license.txt` covers the
Python runtime bundled in the executable.

**Download `CrossArm.exe`**: Windows 10/11, nothing to install, runs offline. Drop a backup on its icon,
double-click it, or run `CrossArm.exe convert <backup> -o <folder>`.

**First launch:** the executable is not code-signed, so Windows SmartScreen may show *"Windows protected your
PC"*: **More info → Run anyway**. Check it against `CrossArm.exe.sha256` (built by GitHub Actions from the
tagged commit): `(Get-FileHash CrossArm.exe -Algorithm SHA256).Hash`
