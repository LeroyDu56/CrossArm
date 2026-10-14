## CrossArm 1.14.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review before commissioning.

**What 1.14 changes:** more of what large industrial cells write is converted, and the report says what stands
between a "not ready" conversion and a workable one.

- **Motion paused on an input, cycles ended** (`--karel`, KAREL option R632): `StopMove` / `StartMove` and
  `ExitCycle`, in the program and in TRAPs, by CrossArm's new KAREL programs `CA_STOPMOVE` and `CA_EXITCYCLE`.
  Without `--karel` they stay TODO, under "motion without a TP equivalent". Measured on ROBOGUIDE.
- **`WaitRob \InPos`** after a move through a zone: a zero incremental FINE move, the robot on its point before the
  next line runs.
- **Calibration:** a routine given a tool by reference that sets its tframe is passed the tool's number; with
  `--karel`, a frame computed from a pose chosen in the branches of an `IF`.
- **FUNCs giving a text** are TP programs writing their result in a string register.
- **Path to workable**, under the decision: the blocking causes to solve, the instructions to convert besides,
  the verdict `--karel` would give. Diagnostic schema 4.
- **World zones** are TODO under a cause of their own and listed in the checklist, to set up in DCS: CrossArm
  converts no safety function. **Modules loaded** that the input does not hold: the files to add.
- **New mapping keys** (`CROSSARM.STOPPED`, `CROSSARM.STOPMOVE.<INTERRUPT>`, `CROSSARM.STANDSTILL`,
  `<PROGRAM>.<FUNC>.result`); keys are only added. The number of TODO can go up: routines once left out show
  their own.

Full list: [CHANGELOG](https://github.com/LeroyDu56/CrossArm/blob/main/CHANGELOG.md).

**The first 10 users who send a diagnostic report (or an anonymized backup) made from a real backup get a free one-year commercial licence, at the author's discretion: one per company, sent by e-mail.**

Not 100 %, not plug-and-play: about 65 % of the instructions of public programs convert, 87 % to 93 % of our own
test corpus, written for testing; the rest is marked `!TODO` with its cause
([why not 100 %](https://github.com/LeroyDu56/CrossArm#why-not-100-)).

**Licence:** free for evaluation and other non-production use; production use needs a commercial licence:
**enzoleroy56@gmail.com** ([LICENSING.md](https://github.com/LeroyDu56/CrossArm/blob/main/LICENSING.md)).
Business Source License 1.1; this version becomes Apache 2.0 on 2030-10-14. `python_license.txt` covers the
Python runtime bundled in the executable.

**Download `CrossArm.exe`**: Windows 10/11, nothing to install, runs offline. Drop a backup on its icon,
double-click it, or run `CrossArm.exe convert <backup> -o <folder>`.

**First launch:** the executable is not code-signed, so Windows SmartScreen may show *"Windows protected your
PC"*: **More info → Run anyway**. Check it against `CrossArm.exe.sha256` (built by GitHub Actions from the
tagged commit): `(Get-FileHash CrossArm.exe -Algorithm SHA256).Hash`
