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
| `conversion` | programs, TODO, warnings; instructions and the share converted, overall and by area; the TODO on an instruction and the TODO not on one (`todo_on_instructions`, `todo_not_on_an_instruction`); the instructions in no program, by reason (`not_converted_by`); TODO and warnings by cause (the causes of the report; any other is `other (cause not listed)`); per task, named `task_1`, `task_2`... (never the task's name): modules, routines, programs, instructions, share converted, TODO, warnings, verdict |
| `instructions`, `functions` | RAPID's own instructions and functions by name (`MOVEL`, `OFFS`), plus `assignment` and the blocks (`IF`, `FOR`...): uses, and of those uses how many were converted, converted with a warning on their line (`partial`), left TODO, inside a statement left TODO (`inside_todo`), in no program (`not_converted`, and why: `not_converted_by`) |
| `user_calls` | calls of the backup's own routines, never by name: `user_proc(num,robtarget,\switch)`, `user_func(num)->bool`, the parameters reduced to their types; calls of routines the backup does not hold: `missing_proc/2` (argument count only) |
| `data_types`, `records`, `aliases` | declarations by type and storage (`robtarget`: CONST 4, VAR 1, arrays...): RAPID's types by name, the backup's records as `record_1`, `record_2`... with the types of their fields, any other type as `user_type`; the number of ALIAS types |
| `control` | IF (and one-line IF), FOR, WHILE, TEST, RETURN, EXIT, GOTO, labels, RAISE, RETRY, TRYNEXT, CONNECT, late binding, ERROR / UNDO / BACKWARD handlers, TRAP routines; the deepest nesting of blocks |
| `signals` | signals by type (DI, DO, GI, GO, AI, AO), and the sections of EIO.cfg with their record counts (`DEVICENET_DEVICE: 2`: the bus and device kinds as ABB names them); never a signal, device or network name, label or address |
| `internal_errors` | CrossArm bugs met: the exception's type, where in CrossArm (`convert/translate.py:2400:stmt`), the stage (`statement` left TODO, `module` left out, `file` not read, `run` conversion stopped), how many places, and the RAPID around a statement as token categories: `<IDENT>`, `<NUM>`, `<STR>`, with RAPID's reserved words, its own instruction, function and type names and punctuation as written. Never the exception's message, which may quote the RAPID |

`instructions`, `functions` and `user_calls` count every use in the task's modules, and every row adds up:

    occurrences = converted + partial + todo + inside_todo + not_converted

- `todo`: the statement carrying a TODO itself. A TODO is counted once, on the statement that carries it: in a
  `TEST` whose `CASE` value is left TODO, the TODO is the `TEST`'s, a `Stop` in its blocks is `inside_todo` (as
  everything in the blocks of a statement left TODO as a whole). An `IF`, `WHILE` or `TEST` whose condition alone is
  left TODO (its blocks written, the condition left to the integrator, since 1.12) is the TODO; its blocks are
  counted as they were converted. A function's use is counted with its statement, so a function's `todo` is
  always 0: in a statement left TODO, it is `inside_todo`. The `todo` of `instructions` and `user_calls` add up to
  `conversion.todo_on_instructions`; `conversion.todo_not_on_an_instruction` is the rest of the report's TODO (a TODO
  not tied to one RAPID statement, none in the inputs at hand).
- `not_converted`: uses in code no program is written from, by reason (`not_converted_by`, a fixed list): `system
  module` (a routine of a system module no program calls, converted only on request), `routine left out` (a TRAP no
  interrupt connects, parameters not converted, a second routine of the same name), `wraps one move` (its calls are
  written as its move); for a FUNC not written as a program, `FUNC computed at conversion` (every call of it in the
  code converted is converted: its value worked out when converting), `FUNC inlined` (its body copied into its
  calls, or a bool FUNC written as its test in the conditions calling it), `FUNC left TODO at its calls` (a call of
  it in the code converted is left TODO), `FUNC never called` (no call of it in the code converted); a call made by
  a FUNC with no program counts as that FUNC's own calls do; `provided by the integrator` (`external_routines`), `conversion
  did not complete`, `other` (none expected: the tests check every input at hand has none).

**Checked by a test.** `tests/test_diagnose_privacy.py` makes the report of every input at hand (the test fixtures,
and the author's local test corpus) and collects from each input every identifier, string, comment word, number of
two digits or more, file, folder, task, signal and device name: none may appear in the report, compared word by
word (RAPID's and CrossArm's own vocabulary excepted). The numbers of the report are counts: they can equal a number
of the backup by chance, so the test checks numbers in the report's text, not in its counts.

## Schema

`schema_version` is 3 (CrossArm 1.12.0). A later version adds keys, never removes one, as for `crossarm_summary.json`.

- 3 tells apart the FUNCs not written as a program: the reason `FUNC computed or inlined` of version 2 is now one of
  `FUNC computed at conversion`, `FUNC inlined`, `FUNC left TODO at its calls`, `FUNC never called`. Nothing else
  changes; a tool reading version 2 reads version 3 as is, the four reasons being values of `not_converted_by`.

- 2 adds `inside_todo`, `not_converted` and `not_converted_by` to each row of `instructions`, `functions` and
  `user_calls`, and `todo_on_instructions`, `todo_not_on_an_instruction`, `not_converted_by` to `conversion`.
  The rows now add up: in version 1, `todo` also counted the statements inside one left TODO, the functions it
  calls and the routines left out, and the code in no program was in `occurrences` only.

## Example

The report of the test fixture `tests/fixtures/rapid/pick_and_place.mod`, `crossarm_diag.md` (the JSON holds the
same, as keys and numbers):

```
# CrossArm diagnostic report

Counts only: no name, comment, text, number or path of the backup is in this report or in crossarm_diag.json.

- Schema version: 3
- CrossArm 1.12.0, Python 3.14.6, Windows 11, 2026-10-13
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
- TODO on an instruction: 3, not on an instruction: 0
- Instructions in no program: FUNC never called 1

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

| Name | Uses | Converted | Partial | TODO | Inside TODO | Not converted | Why not converted |
|---|---|---|---|---|---|---|---|
| assignment | 4 | 4 | 0 | 0 | 0 | 0 | - |
| MOVEJ | 3 | 2 | 1 | 0 | 0 | 0 | - |
| MOVEL | 3 | 3 | 0 | 0 | 0 | 0 | - |
| IF | 2 | 1 | 1 | 0 | 0 | 0 | - |
| WAITTIME | 2 | 1 | 1 | 0 | 0 | 0 | - |
| ERROR_HANDLER | 1 | 0 | 0 | 1 | 0 | 0 | - |
| FOR | 1 | 1 | 0 | 0 | 0 | 0 | - |
| GOTO | 1 | 0 | 0 | 1 | 0 | 0 | - |
| LABEL | 1 | 0 | 0 | 1 | 0 | 0 | - |
| MOVEABSJ | 1 | 0 | 1 | 0 | 0 | 0 | - |
| MOVEC | 1 | 1 | 0 | 0 | 0 | 0 | - |
| RESET | 1 | 1 | 0 | 0 | 0 | 0 | - |
| RETURN | 1 | 0 | 0 | 0 | 0 | 1 | FUNC never called 1 |
| SET | 1 | 1 | 0 | 0 | 0 | 0 | - |
| TPWRITE | 1 | 0 | 1 | 0 | 0 | 0 | - |
| WHILE | 1 | 1 | 0 | 0 | 0 | 0 | - |

## RAPID functions

| Name | Uses | Converted | Partial | TODO | Inside TODO | Not converted | Why not converted |
|---|---|---|---|---|---|---|---|
| OFFS | 3 | 3 | 0 | 0 | 0 | 0 | - |

## Calls of the backup's routines (by parameter types)

| Name | Uses | Converted | Partial | TODO | Inside TODO | Not converted | Why not converted |
|---|---|---|---|---|---|---|---|
| user_proc() | 2 | 1 | 1 | 0 | 0 | 0 | - |

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

`RETURN` counts 1 use, not converted: it is in a FUNC, whose body is not written as a program (the FUNC is
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
