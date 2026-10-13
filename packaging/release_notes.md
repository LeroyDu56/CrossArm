## CrossArm 1.11.1

CrossArm converts ABB robot programs written in RAPID into FANUC TP programs (`.LS`), with a report of
everything left to review before commissioning. **1.11.1 corrects the diagnostic report: the programs written are
the same as 1.11.0.**

**What 1.11.1 changes:** in `crossarm diagnose`, per-instruction counts now add up. Each row of the RAPID
instructions, functions and calls says how many uses were converted, converted with a warning, left TODO, inside a
statement left TODO, or in no program and why (system module, routine left out, FUNC computed or inlined...). A
TODO is counted once, on the statement carrying it: in `IF cond Stop;` whose condition is TODO, the TODO is the
IF's. `schema_version` 2, keys added only
([what the report contains](https://github.com/LeroyDu56/CrossArm/blob/main/docs/diagnostic.md)).

**What 1.11 brought** ([CHANGELOG](https://github.com/LeroyDu56/CrossArm/blob/main/CHANGELOG.md)):

- `crossarm diagnose BACKUP` (**Create diagnostic report** in the window): `crossarm_diag.md` and
  `crossarm_diag.json`, an anonymous report of what CrossArm understood and converted, counts only: no name,
  comment, text, number or path of the backup, checked by a test;
- `crossarm anonymize BACKUP`: a `.zip` of the backup that converts the same, every name renamed, texts
  replaced, comments removed, positions moved by a random offset per frame (joint positions are not moved: use
  `--keep-geometry` to check paths in ROBOGUIDE);
- CrossArm sends nothing: the window opens GitHub's issue form on your click, you attach the files yourself
  ([what the report contains](https://github.com/LeroyDu56/CrossArm/blob/main/docs/diagnostic.md));
- robustness: a damaged or unusual backup no longer stops the conversion; a CrossArm internal error gives exit
  code 3 and `crossarm_error.txt` to send.

**The first 10 users who send a diagnostic report (or an anonymized backup) made from a real backup get a free one-year commercial licence, at the author's discretion: one per company, sent by e-mail.**

Not 100 %, not plug-and-play: about 60 % of the instructions of public programs convert, 87 % to 93 % of our own
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
