# Diagnostic report (`crossarm diagnose`)

`crossarm diagnose` describes what CrossArm understood and converted of a backup, **without any of the backup's
content**: no name, comment, text, number or path of it. It is made to be sent to the author, so that CrossArm can
improve on the backups people actually have, while the backup itself never leaves your computer.

```
crossarm diagnose BACKUP|FILES [-o OUTDIR] [--map mapping.json] [--eio EIO.cfg] [--fanuc TARGET] [--karel]
```

It converts the backup as `crossarm convert` does, in a temporary folder deleted afterwards (no program is written
next to your backup), and writes two files, by default in `crossarm_diag_<name>` next to the input (the name is only
in the folder's path on your computer, never in the files):

- `crossarm_diag.json`: the report, for the author's tools;
- `crossarm_diag.md`: the same report as a page to read. It is made from the JSON alone: read it to see exactly
  what you would send.

**Nothing is sent anywhere.** CrossArm has no network code (a test checks that no module it ships imports one); you
decide whether to send the two files, and how.

Exit codes: 0 the report is written (a backup with syntax errors or CrossArm errors gives a report that counts
them); 2 the input cannot be read (missing, empty, not RAPID, damaged zip) or the mapping file is invalid;
3 a CrossArm internal error outside the conversion (details in crossarm_error.txt).

## The rule: an allow-list

The report holds what the list below names, and nothing else. Everything is counted; the only words in clear are
RAPID's own vocabulary (public, from ABB's manuals), ABB option names and CrossArm's own.

| Section | What it holds |
|---|---|
| `crossarm`, `environment` | CrossArm version; operating system family and release; Python version; whether CrossArm.exe ran; the day (never the time) |
| `input` | input kind (backup / files); counts of tasks, program and system modules, PROC / FUNC / TRAP, lines, files not read, syntax errors; which options were given (mapping file, EIO.cfg, FANUC programs, --karel), as yes / no |
| `system` | RobotWare version, ABB options with their ABB code (`616-1 PC Interface`), robot models (`IRB 1600-10/1.45`), read from BACKINFO/backinfo.txt and system.xml; anything else in those files (system name, serial number, paths, an option without its ABB code) is only counted, in `other_product_lines` |
| `conversion` | programs, TODO, warnings; instructions and the share converted, overall and by area; TODO and warnings by cause (the causes of the report; any other is `other (cause not listed)`); per task, named `task_1`, `task_2`... (never the task's name): modules, routines, programs, instructions, share converted, TODO, warnings, verdict |
| `instructions`, `functions` | RAPID's own instructions and functions by name (`MOVEL`, `OFFS`), plus `assignment` and the blocks (`IF`, `FOR`...): uses, and of those uses how many were converted, converted with a warning on their line (`partial`), left TODO |
| `user_calls` | calls of the backup's own routines, never by name: `user_proc(num,robtarget,\switch)`, `user_func(num)->bool`, the parameters reduced to their types; calls of routines the backup does not hold: `missing_proc/2` (argument count only) |
| `data_types`, `records`, `aliases` | declarations by type and storage (`robtarget`: CONST 4, VAR 1, arrays...): RAPID's types by name, the backup's records as `record_1`, `record_2`... with the types of their fields, any other type as `user_type`; the number of ALIAS types |
| `control` | IF (and one-line IF), FOR, WHILE, TEST, RETURN, EXIT, GOTO, labels, RAISE, RETRY, TRYNEXT, CONNECT, late binding, ERROR / UNDO / BACKWARD handlers, TRAP routines; the deepest nesting of blocks |
| `signals` | signals by type (DI, DO, GI, GO, AI, AO), and the sections of EIO.cfg with their record counts (`DEVICENET_DEVICE: 2`: the bus and device kinds as ABB names them); never a signal, device or network name, label or address |
| `internal_errors` | CrossArm bugs met: the exception's type, where in CrossArm (`convert/translate.py:2400:stmt`), the stage (`statement` left TODO, `module` left out, `file` not read, `run` conversion stopped), how many places, and the RAPID around a statement as token categories: `<IDENT>`, `<NUM>`, `<STR>`, with RAPID's reserved words, its own instruction, function and type names and punctuation as written. Never the exception's message, which may quote the RAPID |

`instructions`, `functions` and `user_calls` count every use in the task's modules; converted / partial / TODO count
the uses the conversion counts in its coverage (routines converted or left out), so a FUNC's own body or the
routines of a system module not converted are counted as uses only.

**Checked by a test.** `tests/test_diagnose_privacy.py` makes the report of every input at hand (the test fixtures,
and the author's local test corpus) and collects from each input every identifier, string, comment word, number of
two digits or more, file, folder, task, signal and device name: none may appear in the report, compared word by
word (RAPID's and CrossArm's own vocabulary excepted). The numbers of the report are counts: they can equal a number
of the backup by chance, so the test checks numbers in the report's text, not in its counts.

## Schema

`schema_version` is 1. A later version adds keys, never removes or redefines one, as for `crossarm_summary.json`.

## Example

The report of the test fixture `tests/fixtures/rapid/pick_and_place.mod`, `crossarm_diag.md` (the JSON holds the
same, as keys and numbers):

```
# CrossArm diagnostic report

Counts only: no name, comment, text, number or path of the backup is in this report or in crossarm_diag.json.

- Schema version: 1
- CrossArm 1.11.0, Python 3.14.6, Windows 11, 2026-10-12
- Input: files, 1 task(s), 1 program module(s), 0 system module(s), 76 lines
- Routines: 3 PROC, 1 FUNC, 0 TRAP
- Files not read: 0, syntax errors: 0
- Options: map no, eio no, fanuc no, karel no

## System

- RobotWare: not found
- Options: none found
- Robots: none found
- Other product lines (not kept): 0

## Conversion

- Programs: 3, TODO: 3, warnings: 5
- Instructions: 27, converted: 85.1 %

| Area | Converted |
|---|---|
| Motion | 100 % |
| I/O and waits | 100 % |
| Program flow | 100 % |
| Data | 100 % |
| Routine calls | 100 % |
| Operator messages | 100 % |
| Error handling | 0 % |
| Other instructions | 0 % |

### TODO by cause

| Cause | TODO |
|---|---|
| RAPID error handler | 1 |
| RAPID goto | 1 |
| RAPID label | 1 |

### Warnings by cause

| Cause | Warnings |
|---|---|
| posture converted with the measured axis conventions | 2 |
| I/O signal without a mapping | 1 |
| TPWrite showing a value | 1 |
| instruction options dropped | 1 |

### Tasks

| Task | Modules | Routines | Programs | Instructions | Converted | TODO | Warnings | Verdict |
|---|---|---|---|---|---|---|---|---|
| task_1 | 1 | 4 | 3 | 27 | 85.1 % | 3 | 5 | workable |

## RAPID instructions

| Name | Uses | Converted | Partial | TODO |
|---|---|---|---|---|
| assignment | 4 | 4 | 0 | 0 |
| MOVEJ | 3 | 2 | 1 | 0 |
| MOVEL | 3 | 3 | 0 | 0 |
| IF | 2 | 1 | 1 | 0 |
| WAITTIME | 2 | 1 | 1 | 0 |
| ERROR_HANDLER | 1 | 0 | 0 | 1 |
| FOR | 1 | 1 | 0 | 0 |
| GOTO | 1 | 0 | 0 | 1 |
| LABEL | 1 | 0 | 0 | 1 |
| MOVEABSJ | 1 | 0 | 1 | 0 |
| MOVEC | 1 | 1 | 0 | 0 |
| RESET | 1 | 1 | 0 | 0 |
| RETURN | 1 | 0 | 0 | 0 |
| SET | 1 | 1 | 0 | 0 |
| TPWRITE | 1 | 0 | 1 | 0 |
| WHILE | 1 | 1 | 0 | 0 |

## RAPID functions

| Name | Uses | Converted | Partial | TODO |
|---|---|---|---|---|
| OFFS | 3 | 3 | 0 | 0 |

## Calls of the backup's routines (by parameter types)

| Name | Uses | Converted | Partial | TODO |
|---|---|---|---|---|
| user_proc() | 2 | 1 | 1 | 0 |

## Data types

| Type | Declarations |
|---|---|
| bool | VAR 1 |
| jointtarget | CONST 1 |
| num | CONST 1, PERS 1, VAR 2, arrays 1 |
| robtarget | CONST 4, VAR 1 |
| tooldata | PERS 1 |
| wobjdata | PERS 1 |

## Records

| Record | Field types |
|---|---|
| record_1 | num, string |

Aliases: 0

## Control constructs

| Construct | Count |
|---|---|
| IF | 1 |
| IF_compact | 1 |
| FOR | 1 |
| WHILE | 1 |
| RETURN | 1 |
| GOTO | 1 |
| LABEL | 1 |
| ERROR_HANDLER | 1 |
| max_nesting | 2 |

## Signals

No EIO.cfg read.

## Internal errors

(none)
```

`RETURN` counts 1 use and none converted or TODO: it is in a FUNC, whose body is not counted on its own (the FUNC is
converted where it is called).

# Anonymized backup (`crossarm anonymize`)

When a diagnostic report is not enough (a construction CrossArm converts wrongly, a TODO you want looked at), an
anonymized copy of the backup shows the author the program's structure without its content. It converts as the
backup does, but none of the backup's names, texts or comments is in it.

```
crossarm anonymize BACKUP|FILES [-o FILE.zip] [--seed N] [--keep-geometry] [--scramble-tools]
                   [--write-mapping FILE] [--eio EIO.cfg]
```

It writes a .zip, by default `crossarm_anonymized.zip` next to the input (`_2`, `_3`... when it exists: the input's
name is not in it). **Nothing is sent anywhere**: you read `anonymize_report.md` in the zip, and decide whether to send
the zip, and how.

What the zip holds:

- **Only what CrossArm reads.** The RAPID modules (a backup keeps its `RAPID/TASKn/PROGMOD|SYSMOD` layout), each file
  named after its module's new name; `SYSPAR/EIO.cfg` reduced to each signal's name, type and device and to each
  section's records (renamed: no label, address or device map); `BACKINFO/backinfo.txt` reduced to the task names
  (renamed), the RobotWare version, the ABB options with their code and the robot models. HOME, License, system.xml,
  the .bin files, dates, paths, the system's name and serial number are left out. The zip's entries have a fixed date.
- **Every name renamed, the same way everywhere** (RAPID ignores case): `MOD_1`, `PROC_12`, `FUNC_3`, `TRAP_2`,
  `REC_1`, `FIELD_4`, `PARAM_2`, `TOOL_3`, `WOBJ_1`, `PT_17`, `JT_2`, `NUM_5`, `DO_5`, `DI_2`, `TASK_1`, `EXT_3` (a
  name the backup uses without declaring it)... A name keeps what a rule of CrossArm reads in it: a signal name
  starting with di / do keeps that start, an `ERR_` name keeps `ERR_`, and routines whose FANUC program names clash
  once shortened still clash. Never renamed: RAPID's reserved words, its own instructions, functions, data types,
  predefined data (`tool0`, `wobj0`, `v1000`, `z50`, `fine`...), constants and error numbers, the components of its
  data types after a dot (`.trans`, `.uframe`) and the optional arguments of its own instructions (`\WObj`, `\Conc`).
- **Comments removed** (a comment holding semicolons keeps them alone, `!;;`: the coverage counts an error handler's
  instructions by its semicolons). **Each text replaced** by a code of the same length (`"SA_______"`), keeping its
  apostrophes and semicolons and whether it has a character TP texts do not have; a text equal to a name of the
  backup becomes that name's new name, and a text starting the names of routines called by a name built at run time
  (`CallByVar "Station_", n`, `%"Station_" + NumToStr(n, 0)%`) is renamed with those routines. A text with no letter
  and at most one digit (`","`, `" "`, `"1"`) is kept.
- **Positions moved**, unless `--keep-geometry`: each declared robtarget by a random offset of its frame (the work
  object its moves name, wobj0 otherwise: the same offset for every point of a frame, orientations kept), each work
  object's user frame by the offset of wobj0; tool frames are kept unless `--scramble-tools`. A pose at 0,0,0 is
  kept. Every other number is kept (speeds, zones, offsets, counters): the conversion depends on them.

**Limit.** Joint positions (jointtarget, MoveAbsJ) are not moved while the robtargets are, so the cell's geometry no
longer holds together: the conversion stays equivalent, but an anonymized backup cannot be used to check paths in
ROBOGUIDE unless it is made with `--keep-geometry`. Positions written in an instruction rather than declared are
kept as they are.

The offsets are random; `--seed N` makes them repeatable (the same input and seed give the same bytes). The seed is
never written in the zip. `--write-mapping FILE` also writes the table of correspondence (original names and texts ->
new ones, the offsets) to FILE, outside the zip: it reverses the anonymization, so keep it and never send it.

Not handled: a routine name built at run time from several texts joined (`"Sta" + "tion_"`), and a position written
in the code rather than declared (`p := [[...], ...]`, kept as written).

Exit codes: 0 the zip is written (a RAPID file CrossArm failed to anonymize is left out of it, and said so); 2 the
input cannot be read; 3 a CrossArm internal error (details in crossarm_error.txt).

**Checked by a test.** `tests/test_anonymize.py` anonymizes every input at hand (the test fixtures, a module of
tricky cases, and the author's local test corpus) and checks that the anonymized copy converts the same (the
diagnostic of the original and of the copy are equal: programs, TODO and warnings by cause, share converted by area
and per task, instructions, functions, calls, data types, records, control, signals; and as many points), and that
nothing of the input is in the zip (the privacy audit of the diagnostic report, on the zip: identifiers, strings,
comment words, numbers in texts and comments, file and folder names; every robtarget coordinate moved).

# Sending a report or an anonymized backup

In the window, **Create diagnostic report** (in the right-hand panel once the ABB program is chosen, and after a
conversion) writes the two files with the window's choices, shows `crossarm_diag.md` as it is written, and offers:

- **Open a GitHub issue**: opens the [diagnostic report form](https://github.com/LeroyDu56/CrossArm/issues/new?template=diagnostic_report.yml)
  in your browser. The address carries no data: you attach `crossarm_diag.md` and `crossarm_diag.json` there
  yourself. CrossArm makes no network request;
- **Open folder**: the folder holding the two files;
- **Anonymized copy...**: `crossarm anonymize` on the same input, next to it.

An anonymized backup you would rather not publish in an issue: e-mail it to **enzoleroy56@gmail.com**. Never
attach a backup that is not anonymized. A RAPID construction converted wrongly: the
[conversion bug form](https://github.com/LeroyDu56/CrossArm/issues/new?template=conversion_bug.yml), with a few
lines of RAPID rewritten so they hold nothing of your cell.

**The first 10 users who send a diagnostic report (or an anonymized backup) made from a real backup get a free one-year commercial licence, at the author's discretion: one per company, sent by e-mail.**
