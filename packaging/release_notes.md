## CrossArm 1.12.0

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review before commissioning.

**What 1.12 changes:** an `IF`, `ELSEIF`, `WHILE` or `TEST` whose condition TP cannot write (`OpMode()`, an
operator dialog, a FUNC that does not convert...) is no longer one `!TODO` remark swallowing its blocks: the
blocks are converted, and only the condition is left to you, in a flag CrossArm reserves (a register for a
`TEST`).

- **The condition to replace:** above the instruction, `!TODO l.N <the RAPID line>`, `!Replace JMP by
  F[k]=(...)`, then `JMP LBL[n]`. Replace the `JMP` with the test your cell makes (`F[k]=(DI[3]=ON)`); the
  report lists each one under "Conditions to set".
- **Nothing runs until the `JMP` is replaced:** the jump skips the whole instruction, no branch, not the `ELSE`,
  and a `WHILE` does not turn, as when it was a remark. Measured on ROBOGUIDE.
- **New mapping keys:** `CROSSARM.CONDITION.<ROUTINE>.L<line>` (in `flags`, in `registers` for a `TEST`); keys
  are only added.
- **The number of TODO can go up:** the blocks once lost in one TODO are converted and show their own.
- `crossarm diagnose`: a FUNC with no program says why (computed at conversion, inlined, left TODO at its calls,
  never called); `schema_version` 3.

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
