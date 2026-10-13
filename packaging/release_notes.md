## CrossArm 1.13.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review before commissioning.

**What 1.13 changes:** more of what large industrial cells write is converted.

- **Stationary tool, part held by the robot:** written for the FANUC Remote TCP (option J624): `L` and `C` with
  `RTCP`, the user frame the stationary tool, the tool frame the held part. The analysis and the checklist say the
  option is needed. Measured on ROBOGUIDE.
- **`FOR` loops:** a bound worked out at run time is computed before the loop (mapping keys
  `CROSSARM.FOR.<ROUTINE>.L<line>.FROM|TO`); one TP cannot compute is left to you, the loop skipped until you set
  it; a constant `STEP` is converted.
- **Optional arguments:** an optional `num`, `bool` or `string` is passed as two arguments, 1 / 0 then the value;
  `Present()` reads the first. A program of your own calling such a routine passes both.
- **Calibration:** tools built by a FUNC from a base tool and a record of offsets and angles; `GetSysData` of a
  frame the routine selected; a tool or work object set but never used is a remark with a warning.
- **Module loads** (`Load`, `StartLoad`, `WaitLoad`, `UnLoad`) of a module of the backup: a remark with a warning.
- **The number of TODO can go up:** routines and loops once left TODO whole are converted and show their own.

Full list: [CHANGELOG](https://github.com/LeroyDu56/CrossArm/blob/main/CHANGELOG.md).

**The first 10 users who send a diagnostic report (or an anonymized backup) made from a real backup get a free one-year commercial licence, at the author's discretion: one per company, sent by e-mail.**

Not 100 %, not plug-and-play: about 65 % of the instructions of public programs convert, 87 % to 93 % of our own
test corpus, written for testing; the rest is marked `!TODO` with its cause
([why not 100 %](https://github.com/LeroyDu56/CrossArm#why-not-100-)).

**Licence:** free for evaluation and other non-production use; production use needs a commercial licence:
**enzoleroy56@gmail.com** ([LICENSING.md](https://github.com/LeroyDu56/CrossArm/blob/main/LICENSING.md)).
Business Source License 1.1; this version becomes Apache 2.0 on 2030-10-13. `python_license.txt` covers the
Python runtime bundled in the executable.

**Download `CrossArm.exe`**: Windows 10/11, nothing to install, runs offline. Drop a backup on its icon,
double-click it, or run `CrossArm.exe convert <backup> -o <folder>`.

**First launch:** the executable is not code-signed, so Windows SmartScreen may show *"Windows protected your
PC"*: **More info → Run anyway**. Check it against `CrossArm.exe.sha256` (built by GitHub Actions from the
tagged commit): `(Get-FileHash CrossArm.exe -Algorithm SHA256).Hash`
