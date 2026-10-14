# Changelog

All notable changes to CrossArm, the ABB RAPID to FANUC TP converter. Dates are release dates;
downloads are on the [releases page](https://github.com/LeroyDu56/CrossArm/releases).

## 1.14.0 — 2026-10-14

Patterns typical of large industrial cells: the motion paused and resumed on an input, cycles ended from a TRAP,
waits for the robot to stand still, calibration routines given the tool to set, FUNCs giving a text, and what
stands between a "not ready" conversion and a workable one. Share of instructions converted: the test corpus at
87 %, 93 % and 91 % (78 % for the calibration modules, which gained modules of world zones, motion paused on
inputs and other instructions TP has no form for); public open-source programs, about 65 %.

**Upgrading:** StopMove / StartMove and ExitCycle convert with `--karel` only (the KAREL option R632 on a real
robot); without it they stay TODO, now under "motion without a TP equivalent". World zones are TODO under a cause
of their own, "world zone or safety function: set up in DCS on the FANUC" (before: "RAPID instruction without a TP
equivalent"); a module Load names that the input does not hold, under "module loaded at run time, not in the
input" (before: "routine or data not in the backup" or "value not known at conversion time"); SyncMoveOn & co
under "motion without a TP equivalent", WaitSyncTask / WaitTestAndSet under "RAPID instruction without a TP
equivalent" (before: "routine call with arguments"). A routine given a tool by reference that sets its tframe is
passed the tool's number: a program of your own calling it passes the number. The mapping file gains the keys
`CROSSARM.STOPPED`, `CROSSARM.STOPMOVE.<INTERRUPT>` (in `flags`), `CROSSARM.STANDSTILL` (in `point_registers`) and
`<PROGRAM>.<FUNC>.result` (in `string_registers`); no key is removed or redefined. Diagnostic schema 4 (keys
added). **The number of TODO of a program can go up**: routines once left out are converted and show their own.

- StopMove / StartMove convert with `--karel`, through CrossArm's new KAREL program `CA_STOPMOVE`. In the program
  moving the robot: KAREL STOP / RESUME, when the same routine starts the motion again before its next move. In a
  TRAP (an input pausing the robot): the program holding the robot is paused and continued, the TRAP's program
  ignoring pause requests (`PAUSE_REQUEST = 2`); a TRAP leaving the robot paused waits itself for the input of the
  TRAP that starts it again (its own, or the one other such TRAP), then runs it, since no condition monitor fires
  while its program is paused. ClearPath after a StopMove in a TRAP is a remark. Measured on ROBOGUIDE (probe
  `stopmove`). The mapping file gains the flag keys `CROSSARM.STOPPED` and `CROSSARM.STOPMOVE.<INTERRUPT>`; no key
  is removed or redefined. Without `--karel` they stay TODO, now under "motion without a TP equivalent".
- A TRAP connected by a routine of a system module that the programs call is written with that routine.
- WaitRob \InPos / \ZeroSpeed after a move through a zone, or after a call or a branch, is a zero incremental FINE
  move (`L PR[k] 100mm/sec FINE INC`, `PR[k]` set to zero just before): the robot ends the move before on its point
  and stops there, as in RAPID, before the next line runs (measured on ROBOGUIDE, probe `waitrob`; without it, the
  line after a CNT100 move runs about 9 mm before the point). The mapping file gains the position register key
  `CROSSARM.STANDSTILL`. In a TRAP it stays TODO.
- ExitCycle converts with `--karel`, in the program and in a TRAP, through CrossArm's new KAREL program
  `CA_EXITCYCLE`: it starts itself as a task of its own, which aborts the program holding the robot (its motion
  cancelled) and runs it again from its first line; the line after the CALL never runs, data keep their values, as
  in RAPID. A TRAP that stops the robot then ends the cycle no longer needs a TRAP starting it again. Measured on
  ROBOGUIDE (probe `exitcycle`). Without `--karel` it stays TODO, now under "motion without a TP equivalent".
- With `--karel`, a work object's frame computed from a pose chosen in the branches of an IF or a TEST converts: the
  pose is kept in one position register every branch writes; `p.rot := OrientZYX(z, y, x)` of such a pose writes its
  W, P, R (`PR[k,4..6]`); the frame is worked out by `CA_POSEMULT` and its copies to other work objects follow.
  Measured on ROBOGUIDE (probe `branchframe`, within 0.001 mm). After an IF, a branch that never goes past it (EXIT,
  RETURN...) no longer makes data unknown; a tool or work object the branches leave different in one field only
  (a ufmec named per branch) keeps its other fields known; a field copied whole from another tool or work object
  that keeps it (`w2 := w1`) still counts as unchanged. No ufmec warning for a fixed work object (ufprog TRUE).
- A routine given a tool by reference (`INOUT tooldata`) that sets its tframe, a calibration routine, converts: the
  tool is passed by its number and the routine writes the robot's tool frame (`PR[k]=UTOOL[AR[1]]`, the parts it
  sets, `UTOOL[AR[1]]=PR[k]`); a tool kept in a bank register is read back into it after the CALL. The tool's other
  fields stay known to the programs, so a pose computed from its tframe afterwards reads the tool frame the robot
  holds. A statement left TODO that may change the tool (MToolTCPCalib...) stops it being read back in the routine.
  A tool changed other than in its tframe, or a stationary one, stays TODO. Measured on ROBOGUIDE (probe `toolarg`).
- A bool passed by reference that the routine sets is copied to a register (1 / 0) and read back into the caller's
  flag; an optional robtarget parameter is passed as whether the call gives it, the point in its position register
  (measured, probe `toolarg`). `p.trans := q.trans` (or a sum of positions) and `p.rot := q.rot` of points kept in
  position registers convert, component by component.
- MToolTCPCalib, MToolRotCalib, SToolTCPCalib and SToolRotCalib are said to be taught on the FANUC (tool frame
  setup) rather than "call with arguments"; CalcJointT / CalcRobT are said to need the robot's kinematics rather than
  to read the robot's position. A tool or work object set at run time that no converted program uses (only routines
  left out of the conversion read it) is a remark and a warning, as one no program reads.
- The analysis says what stands between a "not ready" conversion and a workable one, right under the decision:
  the blocking causes to solve (the fewest that bring them down to the 3 allowed, those with the fewest TODO first,
  each a link to its TODO), the RAPID instructions to convert besides when less than 85 % are, and, converted
  without `--karel`, the verdict `--karel` gives when it differs ("With --karel and the KAREL option R632, the
  conversion is workable"). In the HTML and Markdown reports, the one-page summary and the window. The rule is
  unchanged. `crossarm_summary.json` gains `causes_to_workable`, `instructions_to_workable` and
  `verdict_with_karel`.
- Diagnostic schema 4 (additive): `conversion` and each task gain `blocking_causes`, `causes_to_workable`,
  `instructions_to_workable` and `verdict_with_karel`; `conversion` gains `verdict` (every task counted together).
  Causes by their fixed names, as `todo_by_cause`.
- Fixed: the same backup could give a program with a different remark from one run to the next (since 1.13.0): the
  RAPID text of a statement made while copying a FUNC into its call was found by the statement's address in memory,
  which a statement made later could be given (a GetSysData copy then showed the text of another line). The
  statement is now held with its text, and so is the stand-in of a condition left to the integrator. The data
  known after an IF / TEST, and those a call may change, are now gone through in a fixed order rather than a
  set's. A new test converts under three PYTHONHASHSEED values and compares every file written.
- World zones (WZBoxDef, WZCylDef, WZSphDef, WZHomeJointDef, WZLimJointDef, WZLimSup, WZDOSet, WZEnable,
  WZDisable, WZFree) stay TODO under a cause of their own, "world zone or safety function: set up in DCS on the
  FANUC", saying so. The commissioning checklist gains a group "Safety and world zones (DCS)": one item per zone
  with its shape, its values when known at conversion (corners, centre, radius, joint values), what it does (the
  robot stops, or an output is set) and where the RAPID switches it. When the backup's system description lists
  SafeMove or World Zones, the analysis and the checklist remind that the safety is set up again in DCS. CrossArm
  converts no safety function: each zone is redone and validated on the FANUC.
- A module that Load / StartLoad / UnLoad name and the input does not hold, or whose file is named at run time,
  stays TODO under a cause of its own, "module loaded at run time, not in the input" (before: "routine or data not
  in the backup", or "value not known at conversion time"). The analysis lists the files to add to the input, as
  the RAPID names them, then convert again. Diagnostic schema 4 gains `loaded_modules_missing` and
  `loaded_modules_named_at_run_time` (counts only, in `conversion` and each task).
- A FUNC of the backup giving a text known at run time only (a label padded with zeros, a code put together from
  counters...) is written as a TP program, as the FUNCs giving a num, a bool or a robtarget: `CALL F(args,k)` just
  before the line, the FUNC's program writing its text in `SR[AR[n]]` (`SR[AR[n]]=SR[m]`). Its text can be put
  together with others, compared, passed on, given to another FUNC. Measured on ROBOGUIDE (probe `functext`); a string
  register took a text of 152 characters, and doubling it to 304 stopped the program (INTP-323). A text comparison reading one is converted
  when what the FUNC can give back (its RETURNs, its parameters as the call gives them) cannot differ from the other
  side by case alone. A FUNC called after a text was worked out in a scratch string register of the same line stays
  TODO, saying so. TPWrite of its text still shows the fixed part only. The mapping file names its result registers
  `<PROGRAM>.<FUNC>.result` among the string registers; no key is removed or redefined.
- A point given the x, y, z of a tool or work object frame computed at run time (`p.trans := tHead.tframe.trans`)
  converts when the robot holds that frame (every change of it converted, a move selecting it): the frame is read back
  from UTOOL / UFRAME into a position register and its x, y, z copied (`PR[k,i]=PR[s,i]`), forms already measured. A
  work object with an oframe, or a frame a statement left TODO may have changed, stays TODO as before.
- RAPID's instructions for tasks or robots working together stay TODO, each saying what it is for and how the FANUC
  cell does it, rather than "call ... with arguments has no mapping": WaitSyncTask (a meeting point of tasks: flags or
  outputs each program sets and waits for, set up by hand) and WaitTestAndSet (a semaphore: TP has no test-and-set in
  one step) under "RAPID instruction without a TP equivalent"; SyncMoveOn, SyncMoveOff, SyncMoveResume,
  SyncMoveSuspend, SyncMoveUndo (coordinated motion of several robots, the FANUC's own options) under "motion without
  a TP equivalent". Nothing new is converted.

## 1.13.0 — 2026-10-13

Patterns typical of large industrial cells: loops whose bounds are worked out at run time, optional arguments,
module loads, tools built by FUNCs from records, a stationary tool with the part held by the robot. Share of
instructions converted: the test corpus at 87 %, 93 % and 91 % (88 % for the calibration modules, which gained
new modules); public open-source programs, about 65 %.

**Upgrading:** an optional `num`, `bool` or `string` parameter is passed as two arguments (1 / 0 whether given,
then the value): a program of your own calling such a routine passes both. A stationary tool with a work object
the robot holds needs the Remote TCP option (J624): the mapping file lists the stationary tool under `uframes`
and the work object under `utools`; a file written by 1.12 that numbered them the other way keeps those numbers
reserved, unused. The mapping file gains the keys `CROSSARM.FOR.<ROUTINE>.L<line>.FROM|TO` (in `registers`); no
key is removed or redefined. A module loaded, and a tool or work object set at run time that no move selects and
no program reads, are remarks with a warning, no longer TODO. **The number of TODO of a program can go up**:
routines and loops once left TODO as a whole are converted and show their own TODO.

- A FOR whose bound is a calculation (`nRows*2-1`, `StrLen(s)`, a group input) is converted: the bound is worked
  out before the loop in a register of its own (mapping key `CROSSARM.FOR.<ROUTINE>.L<line>.FROM|TO`, added). A bound
  TP cannot work out is left to the integrator in a reserved register (`CROSSARM.CONDITION.<ROUTINE>.L<line>`), the
  loop written with its body behind a `JMP LBL[n]` that skips it until the line setting the register replaces the
  jump: the loop does not turn before. Listed in the checklist "Conditions to set".
- A FOR with a constant STEP other than 1 or -1 (`STEP 2`, `STEP -0.5`) is converted to a loop of labels, the
  counter tested before each turn and stepped after it (it was a TODO).
- Fixed: TP reads the end register of a FOR again at each turn, RAPID works it out once: a loop whose body (or a
  routine it calls) changes the data of its end turned a different number of times. The end is now copied into its
  own register before the loop. Measured on ROBOGUIDE (`forbound` probe).
- `Load`, `StartLoad`, `WaitLoad`, `UnLoad` and `EraseModule` of a module the backup holds are converted to a remark
  with a warning: a FANUC controller has no modules, the module's programs are converted with the others and are on
  the controller before the line runs (they stay there after an UnLoad). A module the backup does not hold, or a file
  named at run time, stays TODO and says so: load its programs on the controller (it was a TODO saying TP has no
  such instruction). `Save` stays TODO.
- `GetSysData` of a tool or work object selected earlier in the same routine (by a move or SetSysData) is converted
  as the copy of that frame (`tSaved := tGrip`, written as such an assignment is). Where only the caller knows the
  active frame (at the start of a routine, after a call), it stays TODO as before (a TP program reads no system
  variable). `GetSysData` of a load is a remark with a warning: the payload carried is the PAYLOAD schedule
  selected.
- `crossarm anonymize`: a text naming the file of a module of the backup (`"HOME:/dir/Name.mod"`) becomes the
  module's new name with its extension, so that the anonymized backup loads the same modules.
- A routine (or a FUNC written as a program) with optional `num`, `bool` or `string` parameters is converted: each
  is passed as two arguments, 1 / 0 whether the call gives it, then its value (0, or '' for a text, when it does
  not): `Station 3\Speed:=200;` -> `CALL STATION(3,1,200)`, `Station 4;` -> `CALL STATION(4,0,0)`; `Present(Speed)`
  reads the first (`IF AR[2]=1`). An optional `\INOUT num` the routine changes is read back after the CALL only
  when the call gives it; `\Speed?Speed` passes on what the caller was given. The arguments saying whether a value
  is given count in the ten a TP CALL takes. Measured on ROBOGUIDE (`optargs` probe). An optional point, pose, tool,
  speed or zone stays TODO and says why.
- A tooldata or wobjdata passed by reference (INOUT, VAR) that the routine only moves with or passes on is passed by
  its number, as one passed by value; one the routine changes stays TODO and names the line changing it. A `bool` or
  `string` passed by reference that the routine does not change is passed as one passed by value.
- Fixed: a condition with a calculation on each side of an AND or OR (`v>=r-t AND v<=r+t`) worked both out in the
  same scratch register, the second overwriting the first before the test read them. Each side now has registers of
  its own.
- A tool or work object built by a FUNC of the backup that builds poses part by part (`pe.trans := g.offset`,
  `pe.rot := OrientZYX(g.angles.z, g.angles.y, g.angles.x)`, the angles in a RECORD of pos fields) and returns
  `PoseMult(PoseMult(base.tframe, pe1), pe2)` is converted: worked out at conversion time when its base is fixed;
  when the base changes at run time, the FUNC is copied into the call (it was a TODO: only its result could be set
  part by part), the frame read back and moved in TP when only its position changes, by KAREL (`--karel`) when its
  orientation does. Checked against an independent computation (<= 0.001 mm, 0.001 deg).
- A tool or work object no move selects is kept on the robot when another one a move selects is computed from it at
  run time (`PR[k]=UTOOL[n]` then reads it back): it was a TODO ("no move selects it").
- A tool or work object set at run time that no move selects and no program reads is a remark with a warning
  (nothing to write on the FANUC): it was a TODO. Read anywhere (an expression, an argument, `GetDataVal` of its type
  by a computed name), it is as before.
- A tool copied from one whose payload changes at run time: a warning (select the same PAYLOAD schedule with it),
  not a TODO; its frame is converted.
- A stationary tool (tooldata robhold FALSE) with a work object the robot holds (wobjdata robhold TRUE, a fixed user
  frame) is converted to the FANUC Remote TCP option (J624): the stationary tool is a UFRAME (its tframe, in the
  world), the work object a UTOOL (uframe x oframe, on the faceplate), each point the part seen from the tool (the
  inverse pose), MoveL and MoveC written with `RTCP` (`L P[2] 100mm/sec CNT20 RTCP`), MoveJ and MoveAbsJ without it
  (J refuses RTCP). A point passed to a routine is passed that way by the callers. It was a TODO. The mapping file
  lists the stationary tool under `uframes` and the work object under `utools`; no key is added or redefined. A
  point only known at run time (CRobT, Offs() or RelTool() of a parameter, an array indexed at run time) and a work
  object moved by a mechanical unit stay TODO and say why. The analysis and the checklist say the option is needed.
  Measured on ROBOGUIDE (`rtcp` probe: the flange where RAPID puts it within 0.01 mm, the stationary TCP on RAPID's
  line and circle in the part; RobotStudio puts the flange there too).

## 1.12.0 — 2026-10-13

An instruction whose condition TP cannot write keeps its blocks. Share of instructions converted: the test corpus
stays at 87 %, 93 % and 90 % (89 % for the calibration modules); public open-source programs, about 65 % (about
60 % before).

**Upgrading:** an IF, ELSEIF, WHILE or TEST whose condition was left TODO was one remark, all its blocks with it;
it is now written, blocks included, behind a `JMP LBL[n]` that skips it until the integrator replaces the jump
with the line setting the condition's flag (`!Replace JMP by F[k]=(...)`; a register for a TEST): nothing of it
runs before, as before. The mapping file gains the keys `CROSSARM.CONDITION.<ROUTINE>.L<line>` (in `flags`, in
`registers` for a TEST); no key is removed or redefined. **The number of TODO of a program can go up**: the blocks
once inside one TODO are converted now and show their own TODO.

- An IF, ELSEIF, WHILE or TEST whose condition (a TEST's value) cannot be written in TP no longer becomes one TODO
  remark with all its blocks: the blocks are converted, and the condition alone is left to the integrator in a flag
  CrossArm reserves (a register for a TEST; mapping key `CROSSARM.CONDITION.<ROUTINE>.L<line>`, added). Until the
  integrator replaces the `JMP LBL[n]` before the instruction with the line setting it, the jump skips the whole
  instruction: no branch runs, the ELSE neither, and a WHILE does not turn, as before. Measured on ROBOGUIDE
  (`condgate` probe). The report lists each condition to set (analysis, checklist "Conditions to set").
- `crossarm diagnose`: such an instruction is the TODO; its blocks count as converted, no longer inside a TODO.
- `crossarm diagnose`: the code of a FUNC not written as a program says why, in four reasons instead of
  `FUNC computed or inlined`: `FUNC computed at conversion`, `FUNC inlined`, `FUNC left TODO at its calls`,
  `FUNC never called`. `schema_version` 3 (no key removed).

## 1.11.1 — 2026-10-13

The diagnostic report corrected. The programs written are the same as 1.11.0.

- `crossarm diagnose`: per-instruction counts now add up. Each row of the RAPID instructions, functions and calls
  gains `inside_todo` (in a statement left TODO as a whole) and `not_converted` with its reason (`system module`,
  `routine left out`, `wraps one move`, `FUNC computed or inlined`, `provided by the integrator`), so that uses =
  converted + partial + TODO + inside TODO + not converted on every row. A TODO is counted once, on the statement
  carrying it: in `IF cond Stop;` whose condition is TODO, the TODO is the IF's, no longer the Stop's; routines left
  out are no longer counted TODO. `schema_version` 2 (keys added only). Conversions are unchanged.

## 1.11.0 — 2026-10-12

Field feedback without sharing the backup: an anonymous diagnostic report and an anonymized copy of a backup, both made on the user's machine and sent by the user. The programs written are the same as 1.10.1.

- Robustness: a damaged or unusual backup no longer stops the conversion. A statement nested more than 40 levels
  deep (or an expression more than 60) is a syntax error of its own; a module CrossArm fails on outside a statement
  is left out, with a TODO "module X not converted: CrossArm internal error, please report it", and the others
  converted; a file the parser fails on is listed with the syntax errors; a damaged zip says so. Fixed: a routine
  raising an error, called in the ERROR handler of that error, made the conversion recurse without end;
  `Abs(Abs(x))` in a condition took twice as long per level; a confdata of 3 values was an internal error.
  UTF-16 modules (saved as "Unicode" by a text editor) are read. New exit code 3: a CrossArm internal error, its
  details saved in crossarm_error.txt. Programs converted from the local test corpus are the same.
- New command `crossarm diagnose BACKUP`: writes crossarm_diag.json and crossarm_diag.md, an anonymous report of
  what CrossArm understood and converted (counts only: RAPID instructions and functions used and converted, causes
  of TODO, share converted per task, RobotWare version and options, signal types, CrossArm internal errors), to
  send to the author. No name, comment, text, number or path of the backup is written, checked by a test; nothing
  is sent anywhere. See [docs/diagnostic.md](docs/diagnostic.md). Conversions are unchanged.
- New command `crossarm anonymize BACKUP`: writes a .zip holding only what CrossArm reads of the backup, every name
  renamed (`PROC_12`, `PT_17`...), texts replaced, comments removed, positions moved by a random offset per frame
  (`--keep-geometry` to keep them, `--scramble-tools` to move the tools, `--seed N` for the same bytes again), with
  `anonymize_report.md` (counts only); `--write-mapping FILE` writes the table of correspondence outside the zip.
  The copy converts the same, checked by a test. Joint positions are not moved, so it cannot be used to check paths
  in ROBOGUIDE unless made with `--keep-geometry`. See [docs/diagnostic.md](docs/diagnostic.md).
- Window: **Create diagnostic report** writes the diagnostic report of the chosen input, shows it as written, and
  opens GitHub's issue form in the browser on a click (CrossArm sends nothing itself); **Anonymized copy...**
  writes the anonymized .zip. Issue forms for a diagnostic report and a conversion bug. The first 10 users who
  send a diagnostic report (or an anonymized backup) made from a real backup get a free one-year commercial
  licence, at the author's discretion: one per company, sent by e-mail. Exit code 3 documented in the guide.

## 1.10.1 — 2026-10-12

Documentation only: the programs written are the same as 1.10.0.

- Docs: the README is a short entry page (what CrossArm does, for whom, download, what to expect, licence);
  the full conversion summary, the longer FAQ, what to expect in detail and the roadmap moved to the
  [user guide](docs/guide.md).
- Docs: the user guide opens on a quick start, what to expect and [upgrading to 1.10](docs/guide.md#upgrading-to-110)
  (the two changes a program converted again can show), with the reference after it; the validation page opens on
  a one-page [summary](docs/validation.md#summary) (what is measured, on what, the figures published).
- Docs: the licence is stated in the same line everywhere (README, guide, LICENSING.md, LICENSE-COMMERCIAL.md,
  release notes): free for evaluation and other non-production use, production use needs a commercial licence;
  the licence terms are unchanged. Shorter release notes. The programs written are the same as 1.10.0.

## 1.10.0 — 2026-10-12

For the RAPID that reaches the cell through functions and errors: a FUNC of the backup known only at run time
becomes a TP program of its own, and the errors the program raises itself are converted with a register its
callers test. It also fixes a numbering bug present since 1.0 (data of a routine sharing the register of
module data of the same name) and changes the end of an ERROR handler to ABORT, as in RAPID. `CrossArm.exe`
now runs the command line too. The mapping file only gains keys (`ROUTINE.name`), and the command line keeps
its options. **Upgrading:** two changes can make a program converted again differ from 1.9 (the register of
such routine data, `ABORT` at the end of an ERROR handler): what to do in
[upgrading to 1.10](docs/guide.md#upgrading-to-110).

- A FUNC of the backup returning a num, a bool or a robtarget whose value is only known at run time is written as a
  TP program: the caller makes `CALL F(args,k)` just before the line that reads it (assignment, IF / ELSEIF, each
  WHILE test, a move, an argument), the program writes its result in `R[AR[n]]` (bool as 1 / 0) or `PR[AR[n]]`.
  Only when its whole body converts; otherwise its calls stay TODO and name the statement of the FUNC that stops it.
  Measured on ROBOGUIDE (probe `funcbody`).
- Errors the program raises itself (`RAISE ERR_X;` of its own errnum, `RAISE n;`) are converted: the routine sets a
  register (`CROSSARM.RAISED`) and ends, its caller tests it after the `CALL` and runs its ERROR handler there
  (RETRY at most 4 times then ABORT, TRYNEXT, RETURN, `RAISE` to its own caller, ERRNO in `CROSSARM.ERRNO`);
  `BookErrNo` becomes a remark. As RAPID does, a RAISE in a routine without a handler, and the end of a handler,
  stop the program (ABORT; previously the end of a wait's timeout handler ended the routine). Errors of the system
  stay TODO. Measured on ROBOGUIDE (probe `raise`).
- Fixed (since 1.0): a num or bool of a routine with the name of module data, or of data of a routine it calls (or
  that calls it), shared that data's `R[]` / `F[]`, so either changed the other without warning. It now has its own,
  named `ROUTINE.name` in the mapping file (added keys only); a mapping file naming it by its RAPID name pins the
  module data.
- `Abs(x)` compared with a constant in a condition is converted as two comparisons of x (`x>c OR x<-c`); the x, y,
  z of a robtarget parameter are read in its position register (`PR[k,1]`), except in an exact comparison (`=`,
  `<>`), left TODO as the point is touched up on the robot; a PERS a task declares without value takes the value
  another task of the backup gives it (the usual way of sharing one), read as saved with a warning.
- `CrossArm.exe` runs the command line without opening its window: `CrossArm.exe convert <backup> [options]`,
  `parse`, `stats`, `--help`, `--version` do what the `crossarm` command does, with its output and exit codes
  (0, 1 when a file has syntax errors, 2 for a usage error). Without arguments, or given files dropped on its icon,
  it opens the window as before. In a script (.bat) cmd waits for it; at the prompt, use `start /wait`.
- Fixed: the newest WinOLPC core build (`V1010-10` after `V1010-9`) is chosen by number, not as text. Tests run on
  Ubuntu 24.04 and 26.04 as well as Windows, with the Node 24 versions of the GitHub actions.
- The report says what this adds: the FUNCs written as TP programs in the analysis and in each calling program's
  header, an action for those left TODO (the line of their body that stops them, who acts); in the checklist, the
  registers kept for the program's own errors (`CROSSARM.RAISED`, `CROSSARM.ERRNO`, `CROSSARM.RETRY.<routine>`),
  one item for the ERROR handlers converted in part and one for the PERS read at their saved value (check the value
  on the robot).

## 1.9.0 — 2026-10-09

For the report, which becomes a cockpit: in a minute, the reader knows where the conversion stands and what to
do first, and the detail opens only when asked for. A line kept at the top gives the decision and the figures;
each action says how many TODO it concerns, leads to them and says who acts; the programs are in folders, each
opened on its TODO; a one-page summary and a machine-readable summary are written next to the report, and
converting again compares with the previous conversion of the same input. The items to review and the
checklist export as CSV, and the report prints as a 2-page summary or as the site checklist. Nothing changes
in the `.LS` programs, the mapping file or the command line: two output files are added
(`crossarm_report_summary.md`, `crossarm_summary.json`), none removed.

- HTML report as a cockpit: a line kept at the top (decision, % converted, TODO, blocking causes, points) and a menu;
  all but the analysis folded, long lists laid out only when opened; three views; items to review 50 at a time,
  `#todo&cause=...&prog=...` links; programs with no TODO in one line; points in one line per program.
- Actions you can act on: each gives the exact number of TODO it concerns, leading to them, and who acts; cosmetic
  TODO apart; a family on each cause; an `external_routines` example to copy; over the controller's capacity, the
  mapping keys to edit; one sentence under the share converted by area; what TP has no equivalent for, apart.
- RAPID and TP, program by program, no longer a long list: programs in folders by name (or RAPID module), each with
  its counts; a program opens on its TODO and warnings, two lines around, the rest one click away; a TODO followed
  from the list highlights its RAPID line and the TP lines written from it; what `--karel`, FUNCs copied into
  their calls and provided routines did in each program.
- The integrator view no longer opens on a wall of checklist: its groups are one line each with their counts, the
  next items to do shown, every item one click away (and printed). A program mostly in warnings folds the lines
  repeating the same warning behind one line ("5 more lines with the same warning: ...").
- Two files more next to each report: `crossarm_report_summary.md`, one page (decision, figures, causes, what to do
  first and who acts, capacity, `--karel`, licence), and `crossarm_summary.json`, the figures in machine form.
- Converting again compares with the previous conversion of the same input, from its `crossarm_summary.json`:
  TODO, warnings and % then and now, causes gone and new, options that differ; if the RAPID files changed, it says
  how many differ; another backup is never compared. In the report, the summary, the log and the window.
- The report exports its items to review and its checklist as CSV (offline, UTF-8 for spreadsheets), and prints
  two ways: the summary on 2 pages, or the site checklist.

## 1.8.0 — 2026-10-09

For calibration routines, which compute tools and work objects while the robot runs. Tools and work objects
are followed field by field; a frame written part by part or copied is read back from the controller, written
by TP and loaded where the RAPID sets it; a FUNC of the backup that builds a tool or a work object from such a
frame is copied into each call; a function the backup does not have can be a program the integrator provides,
its result read back from a register. Each form was measured on ROBOGUIDE (four new probes). Converted without
`--karel` and without provided routines, the share of RAPID instructions converted stays at 87 %, 93 % and
87 % on the three RobotWare backups of the test corpus, and is 87 % on its new set of calibration modules
(most of whose TODO 1.8 converts); on public open-source programs it is still about 60 %. A mapping file
written for 1.0 to 1.7 keeps its meaning: the keys added (`"task"`, `"returns"`, point argument types) are
optional. Two fixes change what a mapping file given back writes, to what it always meant (frames past the
controller's limit, a backup of several tasks): see Fixes.

- Tools and work objects are followed field by field: a frame computed from `tframe` (or `uframe`, `oframe`) no
  longer waits for `robhold` or `tload` to be known, a field every program sets to its declared value
  (`w.oframe := [[0,0,0],[1,0,0,0]]`) does not count as changed, `ufprog` / `ufmec` write nothing (a warning
  when they name a moving work object), and a field left TODO only makes what reads that field TODO.
- Frames written part by part at run time (`w.uframe.trans := p.trans`, `w.uframe.rot := p.rot`,
  `t.tframe.trans.z := ...`) and frames copied (`wB.uframe := wA.uframe`, banks past the UFRAME limit) are converted:
  the frame read back (`PR[k]=UFRAME[n]`), its parts written by TP, then loaded; an oframe other than the identity
  by KAREL (`--karel`). Measured on ROBOGUIDE (probe `framefield`).
- A FUNC of the backup that builds a tool, a work object or a pose (`tNew := MakeTool(tBase, tOffset)`, its body
  only assignments and pose functions) from a frame calibrated at run time is copied into each call: TP when the
  base frame's orientation is known (`PR[k,i]=PR[k,i]+d`), else KAREL (`--karel`); other bodies stay TODO naming the
  FUNC and the statement, and the report says at how many calls each FUNC was copied. Measured (probe `funcinline`).
- `external_routines` provides functions too: `x := F(args)` with F returning a num, pos, pose or robtarget
  (`"returns": "pose"` for one the backup does not declare) is `CALL PROG(args,k)`, the program writing its result in
  R[AR[n]] / PR[AR[n]] for the caller to read; points are passed by their position register's number. The mapping
  file offers the functions missing from the backup this way. Measured on ROBOGUIDE (probe `funcresult`).
- `WaitDI` / `WaitDO` / `WaitUntil` with `\Visualize` (and `\Header`, `\Message`, `\MsgArray`, `\Icon`, `\Image`,
  `\VisualizeTime`) are converted as the same wait, the FlexPendant message dropped with a warning.
- A record passed by reference (`INOUT`, `VAR`) to a routine that changes its num components is converted as a num
  passed by reference is: each component an argument, copied to a register, read back after the CALL.
- A routine called by its name worked out at run time (`%"Bay_" + NumToStr(n,0)%`, `CallByVar "Bay_", n`,
  `%sStep%`) calls each routine of the backup it can name: a SELECT on the number, or a test of the text per name; a
  name outside those ends the program (ABORT, RAPID raises ERR_REFUNKPRC), with a warning.
- `SetSysData` of a tool or work object selects it (`UTOOL_NUM=n`, `UFRAME_NUM=n`), of a loaddata as `GripLoad`.
  `GetSysData` and `OpMode()` stay TODO, now saying why: a TP program reads no system variable on the measured
  controller (VARS-034, probe `sysvars`).
- The report says what `--karel` did on the run: each KAREL program called, from which programs and how often (or
  that none was used), in the analysis and the KAREL section. The HTML report shows the evaluation-copy notice under
  the verdict. The analysis points at the FUNCs copied into their calls (convert again after a change), the result
  register of provided functions, and the frames kept in position registers past the controller's limit.
- The window: step 5 is titled "Positions touched up", no longer cut on a window 820 px wide; step 3 names the task
  a mapping file was written for.

### Fixes
- A mapping file given back with frames past the controller's limit (kept in position registers) selected them by
  their number (`UTOOL_NUM=11`, refused by the controller) instead of loading them (`UTOOL[10]=PR[90]`,
  `UTOOL_NUM=10`). Versions 1.0.0 to 1.7.0 are affected: convert again with the same mapping file, which keeps its
  meaning (a number past the limit is a frame kept in a register).
- A robtarget whose confdata does not have 4 values is a TODO saying so, no longer an internal error.
- A backup of several tasks: one task's mapping file given back renamed the main program of the other tasks
  (`MAIN_2_2`). The file now says which task it was written for (`"task"`, a new key); its program names apply to
  that task only, the other tasks keep theirs. An older file is recognised by the task folder it is in, or by the
  routines it names; otherwise the report warns and asks for `"task"`.

## 1.7.0 — 2026-10-08

For what TP cannot compute. The new option `--karel` (off by default; step 6 of the window) writes some of it
as calls to CrossArm's own KAREL programs, in a `KAREL` folder of the output, compiled by FANUC ktrans when it
is installed (with ROBOGUIDE): poses computed at run time (`PoseMult`, `PoseInv`, `RelTool`, `DefFrame`), the
frames calibrated from them, and RAPID's text files. Every program of the library was measured on ROBOGUIDE
(three new probes). A real robot needs the KAREL option (R632), and the `.pc` loaded before the `.LS`. Without
`--karel` nothing changes, and the report says how many TODO it would convert. Sockets are not converted: KAREL
socket messaging needs client tags configured on the robot, which CrossArm does not set up. On the three
RobotWare backups of the test corpus, converted without `--karel`, the share of RAPID instructions converted
stays at 87 %, 93 % and 87 %; on public open-source programs it is about 60 %. A mapping file written for 1.0
to 1.6 gives the same numbers: `--karel` is a new option, and the registers its programs work with are
numbered in the existing tables.

- New option `--karel` (off by default; step 6 of the window): a pose computed at run time is kept in a
  position register and `PoseMult` of such poses becomes `CALL CA_POSEMULT(a,b,c)`, a program of CrossArm's
  own KAREL library, written in a `KAREL` folder and compiled by FANUC ktrans when it is installed. The robot
  needs the KAREL option (R632). Without the option nothing changes; the report says how many TODO it would
  convert.
- `--karel` also converts `PoseInv`, `DefFrame` and `RelTool` of a point whose orientation is only known at run
  time (`CA_POSEINV`, `CA_DEFFRAME`, `CA_RELTOOL`), and a work object's uframe or a tool's tframe calibrated
  from them, loaded where the RAPID sets it (`UFRAME[n]=PR[k]`, `UTOOL[n]=PR[k]`).
- `--karel` writes RAPID's text files: `Open` (`\Write`, `\Append`), `Write` (texts, `\Num`, `\NoNewLine`) and
  `Close` become `CALL CA_FILE(...)`, the iodev a register; the files of `HOME:` are written on `UD1:`, byte for
  byte as RAPID writes them (measured on ROBOGUIDE).
- With `--karel`, sockets stay TODO and say why (KAREL socket messaging needs client tags configured on the
  robot, which CrossArm does not set up); the analysis says what `--karel` would convert, files included, and
  the routines offered for `external_routines` leave out those it converts. The window's result panel scrolls
  on a small screen.

## 1.6.0 — 2026-10-07

For converting again a program already commissioned, and for the routines CrossArm cannot write. A routine
missing from the backup, or using files, sockets or byte buffers, can be a TP or KAREL program the integrator
provides, named under a new mapping key, `external_routines`: its calls become `CALL NAME(args)`. Converting
again keeps the positions touched up on the robot (`--keep-taught`), from `crossarm_points.json`, which every
conversion now writes. And the reports open on an analysis: a decision by a fixed rule printed with it, and
the things to do first. Both new forms were measured on ROBOGUIDE, and every controller probe was run again
for this version. On the three RobotWare backups of the test corpus, the share of RAPID instructions
converted stays at 87 %, 93 % and 87 %; on public open-source programs it is about 60 % (what that means:
[docs/validation.md](docs/validation.md#public-programs)). A mapping file written for 1.0 to 1.5 gives the
same numbers: `external_routines` is a new key, and without it nothing changes. A conversion made before 1.6
wrote no `crossarm_points.json`: to keep the touch-ups of its programs, convert that old backup again once
with 1.6, giving it its mapping file, then convert the new backup with `--keep-taught`.

### Mapping file
- New key `external_routines`: a routine CrossArm cannot write (not in the backup, or using files, sockets
  or byte buffers, itself or through the routines it calls) can be a TP or KAREL program the integrator
  provides, `{"WriteLog": {"program": "WRITE_LOG"}}`. Its calls become `CALL WRITE_LOG(args)`, the arguments
  passed as to the routines CrossArm converts, the num RAPID reads back read from a register after the call;
  the routine is not written. The report ("Programs to provide") and the checklist list each program with its
  arguments in order (`AR[1]`, `AR[2]`...) and their RAPID types. `"arguments": ["num", "string", "INOUT num"]`
  types those of a routine the backup does not declare. The mapping file CrossArm writes lists the candidates
  with `"program": null` and why: they activate nothing until a program name is filled in. A function used in
  an expression stays TODO (TP gives no value back to an expression), as do arguments TP cannot pass (a point,
  a speed, a zone, a record, an array). Measured on ROBOGUIDE (new `external` probe): a `.LS` calling a program
  the robot does not have loads, and stops on that `CALL` when run (INTP-222); with the programs, each gets
  what the call passes.

### Converting again
- `crossarm convert --keep-taught PATH` (repeatable) keeps the positions touched up on the robot: it reads the
  robot's programs as they are now (folder, `.zip`, `.LS`, or `.TP` decoded by FANUC PrintTP, installed with
  ROBOGUIDE, with the robot of `--tp-robot`) and the `crossarm_points.json` of the earlier conversion (in the
  paths given, or next to the `--map` file). A point touched up keeps its taught value unless its ABB position or
  one of its frames changed: then it is theoretical again and listed to touch up again. Each point is kept,
  touch up again, theoretical, new, gone or not read; same point within 0.01 mm and 0.01°. Points of arrays kept
  in position registers and frames touched up on the robot are not read. Measured on ROBOGUIDE (new `taught`
  probe): a point touched up, the backup changed and converted again, the robot goes to the touch-up kept and
  to the new point, from the `.LS` and from the `.TP`.
- Every conversion writes `crossarm_points.json` next to its programs: each point written, named by the RAPID
  it came from, with its `P[n]`, its frames and its theoretical value. A conversion made before 1.6 has none:
  convert that old backup again once to get one.
- Step 5 of the window, "Positions touched up on the robot" (Robot programs... / Files or .zip... / Earlier
  output... / Clear), does the same and says at once what it found. The window's steps scroll on a small
  screen, Convert staying at the bottom.

### Report
- The reports open on an analysis: a decision (ready / workable / not ready) by a fixed rule, printed under it
  with the figures it was applied to: ready when everything is converted, workable from 85 % of the RAPID
  instructions converted and at most 3 blocking causes (what the robot measures or computes while it runs,
  interrupts, searches...: work needing a solution designed on the FANUC side), not ready otherwise. Then the
  3 to 7 things to do first, the main TODO causes with an example each, the share converted by area, and only
  the controller resources over or near their limit. The checklist is folded until opened; the window shows
  the decision under its tiles.
- The touch-ups kept by `--keep-taught` are shown point by point: a "Taught positions" section in the HTML
  report (status, distance of the taught point from the theoretical one, why, link to the RAPID line; filters,
  programs folded), tables in the .md report, the checklist telling points kept (check only) from points to
  touch up again, and the window's result saying how many were kept and how many to touch up again.

### Fixes
- The window's result tiles are laid out two per row: the converted share ("77.6 % converted") was cut off.

## 1.5.0 — 2026-10-07

For a robot that cannot load `.LS` programs, and for the commissioning that follows. CrossArm also writes the
programs as binary `.TP`, made by FANUC MakeTP (installed with ROBOGUIDE), for a controller without the ASCII
Upload option; its HTML report shows each RAPID routine and its TP side by side, with a commissioning checklist
to tick. A jointtarget read on the robot (`CJointT()`) is kept in a joint position register, measured on both
controllers before CrossArm writes it. And a fix: a condition with a negative constant (`IF R[1]>-30`, a `WAIT`,
a flag set to a condition) was written bare by earlier versions, which the controller loads but stops on when
the line runs (INTP-202); it is now written `(-30)`, measured to run. On the three RobotWare backups of the test
corpus, the share of RAPID instructions converted is 87 %, 93 % and 87 %; on public open-source programs it is
about 60 % (what that means: [docs/validation.md](docs/validation.md#public-programs)). A mapping file written
for 1.0 to 1.4 gives the same numbers. Without one, a jointtarget now kept in a position register can move the
other position register numbers CrossArm picks by one, compared with 1.4: give the mapping file back to keep them.

### Writes
- Binary `.TP` programs too, for a robot without the ASCII Upload option (`crossarm convert --tp`, `--tp-robot`;
  step 4 of the window): FANUC MakeTP, installed with ROBOGUIDE, makes them for a ROBOGUIDE robot (or a Setrobot
  `robot.ini`) into a `TP` folder to copy to a USB stick. Without MakeTP, the report says so and nothing else changes.
  Measured on ROBOGUIDE: the .TP load and run, and decode back to the lines of their .LS (MakeTP probe).
- An interactive `crossarm_report.html`: each program's RAPID routine and TP side by side, line by line, TODO
  lines marked with their cause; the items to review filtered by kind, cause and program, or searched, each
  leading to its line. One self-contained page (nothing loaded, works offline), light and dark, printable.
- A commissioning checklist in that page, in the order the cell is brought up: loading (.LS or .TP), frames and
  tools with their values, payloads, I/O, registers, TODO lines, points to touch up, motion and assumptions to
  check, each item linked to the lines using it. Ticks are kept in the browser, per report; it prints with its boxes.

### Converts
- A jointtarget read on the robot (`j:=CJointT()`) is kept in a joint position register (`PR[k]=JPOS`): its axes
  `j.robax.rax_i` are read with the measured axis conventions (the ABB values), `MoveAbsJ j` is `J PR[k]`.
  External axes and writing an axis stay TODO. Measured on both controllers (joints probe). Without a mapping
  file given back, that register is numbered with the others, so the other position registers CrossArm picks
  can move by one compared with 1.4; a mapping file given back keeps its numbers.

### Fixes
- A position register numbered for a point is never one of the block of an array of points the mapping file
  pins (a point new to a mapping file given back could be given one).
- A negative constant in a condition is written in parentheses (`IF (R[1]<(-2.5))`, `WAIT (R[1]>(-30))`, a flag
  set to a condition, `F[1]=(R[1]<(-40))`). Earlier versions wrote it bare (`IF R[1]>-30`): ROBOGUIDE loads that
  form, but the program stops on the line when it runs (INTP-202 syntax error). The form in parentheses was
  measured to run (joints probe).

## 1.4.0 — 2026-10-06

Routines given their speed and zone, converted, and what is left told apart by cause. A routine taking
`speeddata` and `zonedata` parameters makes its moves with what each call gives it, measured on both
controllers before CrossArm writes it; bytes, waits of a calculated time, `CRobT()` in the frames selected
and RAPID's math functions of fixed data are converted too. The report now says when a routine or data is
not in the backup, and when the RAPID left is what TP has nothing for (files, sockets, operator dialogs,
positions read on the robot), rather than a conversion still to come. On the three RobotWare backups of the
test corpus, the share of RAPID instructions converted stays at 86 %, 93 % and 87 %; on public open-source
programs it is about 60 % (what that means: [docs/validation.md](docs/validation.md#public-programs)).
A mapping file written for 1.0 to 1.3 gives the same numbers.

### Converts
- A routine given its speed and zone (`PROC Approach(robtarget p,speeddata v,zonedata z)`) that makes its MoveJ,
  MoveL and MoveAbsJ with them: the call passes the speed (mm/s, and % for joint moves) and the CNT of each corner,
  worked out as the move would be written with them (`CALL APPROACH(400,9,100)`); the routine copies them to
  registers, `L P[1] R[1]mm/sec CNT R[3]`, as a move takes no `AR[n]` there. MoveC and other uses of the speed or
  zone stay TODO, with why. Measured on both controllers (speed argument probe): the time of the same moves
  written with constants.
- `fine` given for such a zone: when every call gives it, the routine's moves through the zone are FINE; when only
  some do, each is written both ways (`IF R[3]>100,JMP LBL[1]`, CNT, else FINE) and the call passes 101 for fine,
  as a CALL takes no negative number. Measured: the corner is rounded across those lines, same time as constants.
- A `byte` is kept in a register as a `num` is (`IF nType=3`, `nType:=nType+1`), and a `WaitTime` of a calculation
  (`WaitTime PERIOD-tSpent`) works it out in a register first, then `WAIT R[n]`.
- `CRobT()` without `\Tool` and `\WObj` in a routine whose moves have not selected frames yet: `PR[k]=LPOS` in the
  frames selected when it runs, as RAPID reads in the active tool and work object, those of the last move.
- A number calculated with RAPID's math functions (`Pow`, `Sqrt`, `Sin`...) from data no program changes
  (`FOR i FROM 1 TO Pow(2, nRings) - 1`) is worked out once, as TP has no such function: a PERS read at its saved
  value, with a warning. One that reads data the programs change stays TODO, saying where.
- A routine with a parameter that is an array of two or more dimensions (`INOUT num table{*,*}`) is read: its
  parameter list was taken as unreadable, so every argument of a call to it counted as changed, and the data
  given to its other parameters were no longer known values.

### Report
- A call to a routine, or a use of data, that no module of the backup declares (a system module, an option, another
  task) is a cause of its own, "routine or data not in the backup", saying what to add, instead of a routine call
  or a value CrossArm could not convert. RAPID's own instructions and data, and a routine's parameters, are not.
  A condition on such data (`IF bReady Grip;`) is too, instead of a condition not convertible.
- A statement reading what an operator dialog or a socket gave (`IF answer=resCancel`, `IF status=SOCKET_CONNECTED`)
  is "RAPID instruction without a TP equivalent", with why, instead of a value CrossArm could not work out; a
  position or a record compared as a whole (`IF pPick=pEmpty`) is a condition TP cannot test.
- A call that does not convert to a routine of the backup that writes files, uses sockets or byte buffers, itself
  or through the routines it calls, is "RAPID instruction without a TP equivalent", saying which
  (`LogLine calls Open`, `Ask, through SendLine, calls SocketSend`). A text a function of the backup gives, or an
  element of an array of texts, says so instead of "only known at run time".
- The same holds for a call to such a routine whose parameters TP cannot take (`ToFile \Text:=...`): files or
  sockets are why it stays TODO. An array parameter passed by reference (`INOUT num regs{*}`) is said to be an
  array, and an optional one (`\INOUT num count`) optional, instead of "only a num or a point is read back".
- The ERROR handler of such a routine is "RAPID instruction without a TP equivalent" too, saying which
  (`ERROR handler of a routine using SocketSend`), when it tests no error but those of files and sockets
  (`ERR_SOCK_TIMEOUT`, `ERR_FILEOPEN`) and the backup's own errors raised only where files or sockets are used.
- A position read on the robot that is not kept in a position register (`jNow:=CJointT()`, a `pos` from `CPos()`)
  says what TP reads and why it stays TODO, instead of a frame TP cannot compute; a position a function of the
  backup gets over a socket (`pPart:=Detect()`, a camera) is "RAPID instruction without a TP equivalent"; a frame
  computed from a point read with `CRobT()` is a calibration.
- A byte array passed to a routine (`Combine bHead,7,bAll`) that the caller also hands to a socket or
  a file, directly or through a routine of the backup, is a frame: "RAPID instruction without a TP equivalent",
  saying where it goes (`bHead, given to Combine, is a byte buffer also passed to ReadFrame, which calls
  SocketReceive`), instead of an array parameter TP arguments cannot take.

## 1.3.0 — 2026-10-05

More of the RAPID that cells keep their state in, converted: records, strings, arrays the programs
write, bools set to conditions, points routines change, and searches on an input. Each construct was
measured on the controllers before CrossArm writes it. On the three RobotWare backups of the test
corpus, the share of RAPID instructions converted goes from 84 %, 93 % and 85 % to 86 %, 93 % and
87 %; on public open-source programs it is about 60 % (what that means: [docs/validation.md](docs/validation.md#public-programs)).
A mapping file written for 1.0 to 1.2 gives the same numbers.

### Converts
- Data of a `RECORD` type the backup declares, as a state machine keeps its state in it. Each field a
  program changes is a register named by its path (`R[12:rCell.state]`), a bool field a flag; a
  record set whole is set field by field. A field no program changes is written as its value where it
  is read (a PERS at its saved value, with a warning). A speed or zone field is the speed or zone of
  the moves when every write gives it the same value, with a warning, and where it is read before
  that. A record of a routine whose fields are all num and bool is set to its initial value where the
  routine starts, as RAPID does at each call. String, point and other fields, arrays of records, a
  speed set to several values and a record of a routine calling itself back stay TODO, with why.
  Measured on both controllers (record probe): the same totals, the moves at the speed of the record.
- A speed or zone declared as a predefined one (`CONST zonedata zPick:=z50`), and the components of a
  speed or zone (`vFast.v_tcp`).
- Strings the programs change, as a state machine keeps its state in one or a program reads a text one
  character at a time. Each is a string register (`SR[3]`). A TP line can neither write a text in one
  nor compare one with a text: a text written in the program is loaded by a program CrossArm writes
  with the others, `CALL CA_TEXT(3,'IDLE',0)` (38 characters at a time, a longer one in pieces), into
  a scratch register just before it is compared or passed on. `IF s="RUN"` / `ELSEIF` / `WHILE` on
  texts are jumps, `IF SR[3]<>SR[25],JMP LBL[2]`, as TP compares texts in that form only; `StrLen`,
  `StrPart`, `StrMatch` from the first character, `+`, `NumToStr(n,0)` and `ValToStr(n)` of a number
  only ever given whole numbers are TP's `STRLEN`, `SUBSTR`, `FINDSTR`, `+` and `SR=R`. A string of a
  routine is set where the routine starts; a text worked out for a call is passed in a scratch register.
  TP compares texts regardless of case: a comparison where the texts could differ by case alone stays
  TODO, as do `StrToVal`, `StrFind`, `StrMemb`, `StrOrder`, a number with decimals written as a text and
  strings of records. Measured on both controllers (string probe): the same totals.
- Arrays of numbers the programs change (`nCmd{4}:=nDetail-1`, `nGrid{i,j}:=i*10+j`, `Incr nCount{k}`):
  a block of registers, as for an array only read, written at a fixed index in the element's own
  register (`R[186]=R[186]+1`) and at an index worked out in `R[R[n]]`; an index of several operations
  is worked out first. `SETUP_FRAMES` sets the values the array is declared with (zeros without) or,
  for a PERS, saved with, with a warning: a register keeps its value where RAPID sets a VAR again when
  the program starts. The tasks of a backup share the block of a PERS array, as they share the PERS.
  `Dim()` of a declared array is its size. An array of a routine stays TODO (RAPID sets it again at
  each call), and so do arrays of strings: TP has 25 string registers. Measured on both controllers
  (array write probe): the same totals.
- Arrays of bools the programs change or index at run time (`bSlot{i}:=i>3`, `IF bSlot{k} ...`): a block
  of consecutive flags, from the top down, `F[1022]` at a fixed index and `F[R[n]]` at an index known at
  run time, set to a condition as the other flags (`F[R[4]]=(F[R[3]]=OFF)`). `SETUP_FRAMES` sets the
  values the array is declared with, or saved with for a PERS. The mapping file has a `flag_arrays`
  key, optional: the first flag of each array. Measured on both controllers (flag array probe): the
  same totals.
- A bool set to a condition (`bOk:=nCount>2 AND NOT bBusy`, `bOk:=bBusy`) is its flag set to TP's
  mixed logic, `F[2]=(R[1]>2 AND F[1]=OFF)`, `F[2]=(F[1])`; to a comparison of texts, with jumps. Also a
  bool of a routine declared with a condition and a bool field of a record. Measured on both
  controllers (flag probe): the same totals.
- A point passed by reference (`VAR` or `INOUT robtarget`) that the routine changes (`pAt:=Offs(pAt,0,50,0)`,
  `pAt.trans.z:=...`, passed on): the routine works on the position register it is given, the caller
  reads it back after the CALL (`PR[99]=PR[98]`), and its point is kept in a position register. Measured
  on both controllers (point reference probe): the same values, after the moves.
- `MoveLDO` / `MoveJDO` / `MoveCDO` to a fine point: the move, then the output; measured, the output
  switches with the TCP on the point, as RAPID sets it there. Through a zone, where RAPID sets it in the
  middle of the corner path, it stays TODO. `TestDI(di)` is the input at 1 (`DI[n]=ON`). `WaitRob \InPos`
  or `\ZeroSpeed` after a FINE move is a remark: the line after a FINE move runs once the robot stands
  on the point; after a move through a zone it stays TODO.
- A wait with `\MaxTime` and `\TimeFlag` (`WaitDI diReady,1\MaxTime:=2.5\TimeFlag:=bLate`): RAPID raises no
  error when the time runs out, it sets the bool; the wait polls a TIMER as other timed waits do, then
  sets the flag, `F[3]=(R[5:WaitTimer]>=2.5)`, without an ERROR handler. Measured on both controllers
  (time flag probe): the same flags.
- `SearchL` on a digital input, as a skip: `SKIP CONDITION DI[1]=ON`, then the move to the point with
  `Skip,LBL[2],PR[99]=LPOS`, the point found kept in a position register and read as the other points
  known at run time (`Offs()`, its x, y, z, a move to it). A search for a change (`\PosFlank`, the
  default, `\NegFlank`) first checks the input is not already at that level, as RAPID does; `\HighLevel`
  and `\LowLevel` do not. `\Stop`, `\PStop`, `\SStop`: the move stops there. `\Sup` and no stop option:
  RAPID goes on to the point without stopping, the FANUC stops, then goes on to it (warning; a second
  switch, an error for `\Sup`, is not checked). Where RAPID stops with an error (nothing found, the
  input already on), a `MESSAGE` and `PAUSE`, then the search again when resumed. Measured on ROBOGUIDE
  (search probe): the point found where the input switched; the FANUC stops past it and comes back, where
  RAPID stays past it, which the report says. A move with a skip recording the position keeps its speed
  up to 100 mm/s, the controller slows a faster one down (measured, where the manual says 250): a faster
  search stays TODO, never slowed down. `\Flanks`, an array element as the search point and a routine
  with an `ERROR` handler stay TODO too.
- The mapping file has a `string_registers` key: the string register of each string
  (`"sState": 3`, `Routine.name` for a routine's own) and the scratch ones (`CROSSARM.TEXT`, taken
  from the top); and `limits.SR`, 25 on a standard controller, when strings are used. The string
  registers the FANUC robot's programs use are left free.
- The mapping file has a `programs` key: the TP name of each program written that other programs call
  or arm (`"pickPart": "PICKPART"`, an interrupt's condition program by the interrupt's name, its relay
  `iStop.relay`, `CROSSARM.TEXT` the program loading texts). Given back, a conversion keeps these names
  even when the FANUC robot has a program of that name by then, with a warning: the programs already
  loaded call them. A conversion without it names the programs as before.

### Changes
- The automatic numbers of registers, flags and I/O can shift between versions (more RAPID
  converted); give a conversion its mapping file back to keep them.
- A routine calling itself back and given points passed them in position registers every call under
  way shares, so a call overwrote the points of the calls waiting for it to end: such a call is a TODO
  that says so.
- A statement reading an array of numbers no run of free registers can hold was counted as converted
  while its line became a TODO: it counts as not converted.
- A register only the statements converted with texts use is numbered from the top down (`R[200]`,
  `R[199]`...): the programs without texts keep the numbers they had.
- The report gives RAPID instructions TP has nothing for a cause of their own, "RAPID instruction
  without a TP equivalent", with why: files and serial channels, sockets, raw byte buffers, operator
  dialogs waiting for an answer, screens of the ABB pendant, the ABB event log (`ErrWrite`, `ErrLog`),
  system instructions, world zones. They were counted as calls with arguments or values not known at conversion time.
- Loose modules holding several robot tasks or versions of a program (modules of the same name in
  several folders) are converted as a task per folder, each written in a folder of its own. They were
  converted as one task, and programs of the same name were written over one another: fewer files
  than the programs announced. Loose modules of distinct names are one task, written as before.
- Modules given as several files are read in path order, whatever the order they were picked in.
- The mapping file names a field of a record by its path (`rCell.state`, `Routine.data.field` for
  a routine's own); one it does not name is numbered after every number it pins. The report lists
  the registers and flags each record takes.
- The mapping file names the FOR counters of a routine and the copies of its parameters after the
  routine (`MAIN.i`), and the registers CrossArm uses itself `CROSSARM.` and their use
  (`CROSSARM.NUMBERINDEX`), instead of the RAPID name alone (`i`), which two routines can share.

### Validated
- The record probe keeps a state machine in records, on RobotStudio and, converted, on ROBOGUIDE: the
  same totals, the moves at the speed of the record
  ([docs/validation.md](docs/validation.md#23-records-kept-field-by-field-run)).
- The string probe compares, works out and passes texts on both controllers: the same totals
  ([docs/validation.md](docs/validation.md#24-strings-in-string-registers-run)).
- The probes of arrays the programs write, bools set to conditions, points passed by reference, waits
  with a time flag and arrays of bools, on both controllers: the values RAPID computes
  ([docs/validation.md](docs/validation.md#25-arrays-the-programs-write-run), sections 25 to 31).
- On ROBOGUIDE, with signals switched through COM as the TCP passes a point: the output after a fine
  move switches with the TCP on the point, and a search finds the point within 0.1 mm of the switch
  ([docs/validation.md](docs/validation.md#30-a-search-run)).

### Fixes
- A constant below 1 in an assignment is written without its zero (`R[4]=.25`), as the controller
  stores it. A small constant keeps its significant digits (`.0000015`, was `0.000002`).
- A whole number past what a TP register line keeps (2147483647 and more, `0xFFFFFFFF`, `1E10`) was
  written as it is, and the controller stored it as `********` or as another number (`-2147483648`
  as `-129`). It is a TODO that says so. Whole numbers up to 2147483646 are written digit for digit,
  as measured.
- A mapping file given back did not pin the FOR counters, the copies of parameters and CrossArm's own
  registers: they were numbered again, past every number of the file. They keep their numbers, also
  from a file written by 1.0 to 1.2, whose RAPID names pin the first register of each name.
- Two modules of one task declaring a routine of the same name (`LOCAL PROC main`) both wrote it to
  one file. The routine of the file that comes first by path is converted; the report lists the other
  as not converted.
- A name with a letter outside ASCII (`PROC Ñ`) stopped the reading of its module with an internal
  error. Names take the letters of any script, as RAPID does.
- Integers written in hexadecimal, octal or binary (`0xFF00`, `0o17`, `0b101`) were syntax errors.
  They are read, and written in TP in decimal.
- A move to a point whose orientation is no rotation, `[0,0,0,0]` (a `PERS` the program sets before
  moving there), was an internal error. It is a TODO that says so, as is a point of an array of
  points with such an orientation; a tool or work object with one is left unset in
  `SETUP_FRAMES.LS`, with why, as a frame set at run time.
- A tool whose load has no inertia and its axes of moment left at `[0,0,0,0]` stopped the whole
  conversion at the first `GripLoad` on it. The axes of a load without inertia do not matter: the
  payload is worked out from its mass and centre of gravity.

## 1.2.0 — 2026-09-29

More of what real cells do, converted: interrupts and their TRAP routines as FANUC condition
monitors, routines given records, tools, work objects and numbers to change, and the points and
calculations palletizing programs work out as they run. Each construct was measured on ROBOGUIDE
before CrossArm writes it. On the three RobotWare backups of the test corpus, the share of RAPID
instructions converted goes from 84 %, 88 % and 81 % to 84 %, 93 % and 85 %. A mapping file written
for 1.0 or 1.1 gives the same numbers.

### Converts
- RAPID interrupts to FANUC condition monitors. `CONNECT` and `ISignalDI` / `ISignalDO` become a
  condition program named after the interrupt, `WHEN DI[n]=ON+,CALL TRAP` (`OFF-` for 0, both for
  `edge`), armed with `MONITOR`; `ISleep` and `IDelete` end it (`MONITOR END`), `IWatch` arms it
  again; `IPers` on a `num` compares its register with a copy of the value last seen. The `TRAP` is a
  program without a motion group, as is every routine it calls, and arms its condition program
  again as it ends (the controller disarms one when it fires), unless `\Single`. Measured on
  ROBOGUIDE: one call per edge and none for a signal already set when armed, the program stopped
  while the TRAP runs but the move under way not slowed, the monitor active in the programs called.
  A warning says what a condition checked periodically can miss: a change within 0.05 s of
  `MONITOR`, or held less than 0.02 s. Still TODO, with why: `ITimer` (a condition monitor cannot
  watch a timer), `IError`, group and analog interrupts, `IDisable` / `IEnable`, a TRAP that moves
  the robot or controls its motion (`StopMove`, `ClearPath`...).
- A TRAP several interrupts share, or one reading `INTNO`: each condition program calls a relay of its
  own, which notes its interrupt in `R[n:IntNo]`, calls the TRAP and arms its condition program again.
  An `intnum` reads as its interrupt's number: `TEST INTNO CASE iUp:` is a `SELECT` on the register.
- Data a TRAP changes is never taken as known where the programs read it: a point offset by a count
  the TRAP keeps is not worked out with its value at the start.
- Routines with a parameter of a RECORD type the backup declares: the record is passed as the
  components the routine reads, each an argument of its own (`DeburrPart pdHousing;` ->
  `CALL DEBURRPART('HOUSING-120',2,35,.8,1)`), read as `AR[n]` where the routine reads `part.passes`.
  A record used whole (assigned, passed on to another routine) stays TODO.
- `num` parameters passed by reference (`INOUT`, `VAR`, `PERS`): the routine works on a register of
  its own, which the caller reads back into its data after the CALL when the routine changes it,
  directly, with `Incr` or the like, or through a routine it passes it on to.
- Routines given their tool or work object (`PERS tooldata t`, `\PERS wobjdata WObj`): each is passed as
  its frame number (`CALL PICK(2,1)`, 0 for a work object not given: wobj0) and the routine selects it
  (`UTOOL_NUM=AR[1]`, `UFRAME_NUM=AR[2]`), passing it on as it is. The points it moves to with them are
  in position registers `SETUP_FRAMES` sets: ROBOGUIDE refuses a P recorded in another tool than the
  one selected (INTP-253), where a move to a register takes the frames selected. A point passed to such
  a routine is recorded in the frames the call gives it. A frame the routine uses otherwise (a
  component read, a MoveAbsJ with it) stays TODO.
- `Incr`, `Decr`, `Add` and `Clear`, as the assignments they make (`R[2]=R[2]+1`).
- Calculations of several operations, `(nCol-1)*LENGTH+nShift{k}`: one operation per line in scratch
  registers (`R[n:Calc1]`...), as TP refuses `+` and `*` in one calculation (ASBN-040), in assignments,
  conditions, arguments and the offsets of `Offs()` / `RelTool()`. A wait on one stays TODO: worked out
  once before the `WAIT`, it would not follow the data.
- Points the programs work out at run time, the palletizing way: a robtarget set from data that changes
  then (loop counters, counts, inputs) is kept in a position register every assignment sets and every
  move reads. `Offs()` of a fixed point by run-time offsets is the point copied and offset component
  by component (`PR[98]=P[1]`, `PR[98,1]=PR[98,1]+R[4:Calc1]`), in an assignment or in a move
  (`MoveL Offs(pCorner,nCol*L,0,0)`); `RelTool()` of such a point whose orientation is known at
  conversion time turns the displacement by it and writes the new W, P, R; `CRobT()` is
  `PR[k]=LPOS`, in the frames its `\Tool` and `\WObj` name, selected first; `p.trans.x:=...` is
  `PR[k,1]=...`. `PR[k]=P[j]` copies the values whatever frames are selected (ROBOGUIDE). A point whose
  assignment stays TODO is never moved to: the moves to it stay TODO too, with why.
- A VAR array no program changes holds the values it is declared with, like a CONST one.
- `RelTool()` of a point given at run time, a routine's point parameter or an array element indexed at
  run time: the move goes to the point with `Tool_Offset,PR[m]`, PR[m] a copy of the point with the
  displacement and the turns in its six components (RAPID's turns about x, then y, then z, worked out
  as W, P, R). A displacement given negated (`-h`) is multiplied by -1; in `Offs()` it is subtracted,
  as `+` and `*` in one calculation are refused.

### Changes
- Every position register assignment is written with four spaces before `;`, a component
  (`PR[95,3]=(-30)    ;`) and a register named by another (`PR[R[90]]=LPOS    ;`) included, as the
  controller stores them; from a frame still with one.
- The TRAP routines converted take output, input and flag numbers too: without a mapping file, the
  numbers CrossArm gives a backup with interrupts can move. A mapping file written earlier gives
  the same numbers.
- The point probe records the faceplate in the world frame after each move, which a routine selecting
  the wrong tool would change, rather than the TCP in the frames the move ran in.

### Validated
- The interrupt probe arms edges, `\Single`, `IPers`, `ISleep` / `IWatch`, a call and `IDelete`, and a
  TRAP two interrupts share through `INTNO`, on ROBOGUIDE: the calls RAPID makes
  ([docs/validation.md](docs/validation.md#20-interrupts-run)).
- The parameter probe passes records, nums by reference and uses `Incr` / `Add` / `Clear`, on
  RobotStudio and, converted, on ROBOGUIDE: the same totals
  ([docs/validation.md](docs/validation.md#21-records-and-nums-passed-by-reference-run)).
- The point probe gains `RelTool()` of passed points and array elements and a routine given its tool
  and work object: forty-three moves, the faceplate where the moves written out put it.
- The pallet probe works places out in FOR loops, turns them and reads `CRobT()`: thirteen moves, the
  faceplate where the moves written out put it
  ([docs/validation.md](docs/validation.md#22-points-worked-out-at-run-time-run)).

## 1.1.0 — 2026-09-29

More of RAPID converted, each construct measured on the controllers first: `TEST`, the everyday
instructions (pulses, clocks, analog outputs, payloads), routines given text and points, and arrays
indexed at run time. On the three RobotWare backups of the test corpus, the share of RAPID
instructions converted goes from 78 %, 81 % and 78 % to 84 %, 88 % and 81 %. A mapping file written
for 1.0 gives the same numbers.

### Converts
- `TEST` / `CASE` / `DEFAULT` to `SELECT`: one line per `CASE` value, a `CASE` that only calls a
  routine calls it on its `SELECT` line, the other branches behind labels. A `TEST` on a routine's
  argument or a group input selects a copy of it; a `TEST` on a constant keeps its branch only. A
  `TEST` on a string, or a `CASE` value only known at run time, stays TODO. A `FUNC` choosing its
  value with `TEST` is run at conversion time like one using `IF`.
- `PulseDO` to `DO[n]=PULSE,0.2sec`, its length rounded to the tenth of a second FANUC takes (a
  warning when that moves it); `InvertDO` to `DO[n]=(!DO[n])`; RAPID clocks (`ClkReset`, `ClkStart`,
  `ClkStop`, `ClkRead`) to `TIMER[n]`, apart from the timer the waits use.
- `SetAO` to `AO[n]=`, in the FANUC module's counts: the scale per signal comes from the mapping
  file (`analog_scales`, written with `null` for each analog output until it is filled in); without
  it the line stays TODO rather than write a value in the wrong unit.
- `GripLoad` to `PAYLOAD[n]`. A FANUC payload schedule is all the flange carries, so a tool holding a
  part has one of its own: CrossArm works out the two masses together, their common centre of
  gravity and the inertia about it, lists the schedule in the report, and numbers it from the top
  down past the tools' own; `GripLoad load0` goes back to the tool's schedule, its UTOOL number. The
  tool is the one the moves after it use, else the one selected, else the task's only tool.
- Routines with `string` parameters: the text is passed in the call (`CALL FAULT('Gripper not
  open',3)`), 38 characters at most, an apostrophe written as a backquote. A TP program cannot show
  a string it is given (MESSAGE takes fixed text), so a `TPWrite` of it stays TODO in the routine;
  the routine and its calls are converted. A string only known at run time stays TODO at the call.
- Routines with `robtarget` parameters: the point goes in a position register of its own, which the
  caller sets before the CALL (`PR[99]=P[1]`) and the routine moves to (`L PR[99]`), in the frames it
  selects, as a RAPID move takes its own tool and work object. `Offs()` of the point is a copy offset
  component by component (`PR[98,3]=PR[98,3]+40`); a routine passes its point on, as it is or with
  `Offs()`. A point turned with `RelTool()` stays TODO.
- Arrays indexed at run time, of points (`pSlot{nTool}`, `pGrid{r,c}` in FOR loops) and of numbers
  (`nTorque{nScrew}`): `SETUP_FRAMES` keeps each in consecutive registers, row after row, position
  registers for points and numeric registers for numbers, and the programs work the index out in a
  register (`R[3]=R[1]*3`, `+R[2]`, `+88`) and read `PR[R[3]]` or `R[R[3]]`: a point moved to,
  offset with `Offs()` or passed to a routine, a number in a calculation, a condition or an argument.
  The index is worked out once while nothing it reads changes; two elements in one statement take
  two index registers. A CONST array, or a PERS one no program changes (kept at the values saved in
  the backup, with a warning); a VAR array or one the programs change stays TODO.
- An element of an array at a fixed index (`pSlot{2}`, `nTorque{3}`) is read like any other value.
- Motion settings: `ConfL`, `ConfJ`, `SingArea` and `CirPathMode` are left out, with a warning where
  FANUC does it its own way. `AccSet` and `VelSet` that slow the robot down stay TODO, as dropping
  them would run it faster than the ABB.

### Report
- Interrupts (`CONNECT`, `ISignalDI`, `IDelete`...) and motion settings are blockers of their own,
  no longer mixed with calls with arguments.

### Mapping file
- `analog_outputs`, `timers`, `analog_scales`, `payloads`, `point_registers`, `point_arrays` and
  `number_arrays`, optional: a mapping
  file written for 1.0 gives the same numbers; the new position registers are taken after the frame
  banks and the computed frames.

### Validated
- A probe runs `TEST` in ten shapes (several values, negative and decimal values, empty and
  call-only `CASE`s, with and without `DEFAULT`, nested, on a constant, on an argument) on
  RobotStudio and, converted, on ROBOGUIDE: the same branches, register for register
  ([docs/validation.md](docs/validation.md#16-test-and-case-run)).
- The I/O probe, converted and run on ROBOGUIDE: the pulse is on during its length and off after,
  the output inverted and back, the clock reads the half second it timed, and the payload schedule of
  the tool with the part is the active one
  ([docs/validation.md](docs/validation.md#17-pulses-inverted-outputs-clocks-and-analog-outputs-run)).
- The point probe makes twenty-eight moves on ROBOGUIDE through routines given their points and
  through a 2 x 2 array walked in two FOR loops, and the same moves written out: the same poses, to
  the thousandth of a millimetre
  ([docs/validation.md](docs/validation.md#18-routines-given-their-points-and-arrays-of-points-run)).
- The array probe reads tables of numbers indexed at run time in loops, sums, conditions, a WHILE
  and a call given two elements, on RobotStudio and, converted, on ROBOGUIDE: the same totals
  ([docs/validation.md](docs/validation.md#19-arrays-of-numbers-run)).

## 1.0.0 — 2026-09-26

The first release. CrossArm converts ABB robot programs written in RAPID, from a RobotWare backup or
loose modules, into FANUC TP programs (`.LS`), with a report of everything left to review. Where the
two brands differ, both controllers were measured, with an ABB IRB 6700 in RobotStudio and three
FANUC robots in ROBOGUIDE (M-20iD/25, R-2000iC/190S, R-1000iA/80F). The points CrossArm writes are
the ABB's, as theoretical points to touch up at commissioning; the path between them stays within
4 mm of the ABB's on the moves measured, where CrossArm aims for 10.

### What 1.x keeps
- **A mapping file keeps working.** A `crossarm_mapping.json` written or edited for 1.0 is read the
  same way by every 1.x: no key is removed or changes meaning, new ones are optional.
- **Given back its mapping file, a conversion keeps its numbers.** Every register, flag, I/O, frame
  and program number a conversion wrote is in the mapping file it writes; converting again with it
  (`--map`) under a later 1.x gives the same numbers, so programs already on the robot still match.
- **The command line keeps its commands and options.**
- **What may change**: more RAPID converted where 1.0 writes a TODO, CNT and J % values where a
  robot is measured again or better, and the wording of the report and the window.

### Converts
- `MoveJ`, `MoveL`, `MoveC`, `MoveAbsJ` with their targets, `Offs()` and `RelTool()` resolved at
  conversion time; quaternions to W, P, R; `confdata` to `CONFIG` through axis conventions measured
  on both controllers, J6 at exactly 180 included. `MoveAbsJ` with a stationary tool or a robot-held
  work object is made with the tool already selected (else `tool0`), with a warning: a joint target
  does not depend on them.
- Tool and work objects to `UTOOL` / `UFRAME`, set on the robot by a generated `SETUP_FRAMES.LS`;
  frames past what the controller holds kept in position registers. Payloads listed in the report.
  `tool_pin` says which pin hole of the FANUC flange the tool sits by.
- **Frames and points the programs compute**, when every value they read is fixed: a tool built by a
  FUNC of the backup from another tool, a work object's `uframe` copied from another's, `DefFrame`,
  `PoseMult`, `PoseInv`, `PoseVect`, `OrientZYX`, `EulerZYX`, `Offs`, `RelTool`, a point put together
  component by component, the backup's own `RECORD`s. TP cannot do this arithmetic (measured: no pose
  product, inverse or angle function, `PR+PR` adds component by component), so CrossArm works the value
  out once; the program loads it where the RAPID computes it (`UTOOL[3]=PR[95]`), from a position
  register `SETUP_FRAMES.LS` sets. A value is computed only if nothing can change what it reads: a
  PERS another routine or task changes, a value set in one branch of an `IF`, in a loop or before a
  call that may change it leaves the TODO, and the TODO names that input and where it changes.
- Speeds and zones from motion profiles measured on both robots, per FANUC series: joint `%` from
  the TCP speed a J 100 % move reaches, each zone as the CNT that rounds a corner as much at the
  move's speed (the next move's, when it is faster).
- Digital and group I/O typed by `EIO.cfg`, waits, a wait with `\MaxTime` and its `ERROR` handler,
  `IF` / `ELSEIF`, `FOR`, `WHILE`, conditions calling the backup's own bool functions, calls with
  num, bool and switch arguments, the integrator's own move routines, `num` / `bool` data to
  registers and flags, operator messages, comments.
- Everything else is marked `!TODO` in the program and listed in the report, ranked by how much
  code each cause holds up, with the share of RAPID instructions converted by area. Each TODO says
  what it takes: among others a position built at run time, a frame or position **measured on the
  robot** (a calibration: `CRobT` and what derives from it, which only KAREL or the FANUC frame setup
  can redo), a payload changed at run time, a stationary tool.

### Fits the robot in place
- Given the FANUC robot's backup, its frames, registers, I/O and program names are left alone, and
  its model chooses the speed and zone profile.
- `crossarm_mapping.json` records the numbering of each conversion; edited and given back, it pins
  any number, the register of each computed frame included (`frame_registers`, by its value).
- The report compares what the conversion allocates with what the controller holds, position
  registers included (scratch, frame banks, computed frames), and gives each computed frame its
  register, value and where it is loaded.

### Validated
- Measured on a local test corpus written for testing, not distributed: three RobotWare backups and
  three FANUC backups in three integrators' styles, every RAPID task loaded by RobotStudio and every
  FANUC backup exported by ROBOGUIDE.
- Every program converted from the test corpus loads on ROBOGUIDE, and every form of instruction
  CrossArm writes is stored by the controller as written.
- On 16 test moves with rotated tools and work objects, the flange lands within 0.004 mm and 0.001°
  of where RobotStudio puts it; computed frames, 9 moves within 0.005 mm and 0.001°, `DefFrame` with
  each `\Origin` included.
- Converted joint moves take −16 % to +19 % of the ABB's time; corners, approaches, retracts,
  reversals and zigzags stay within 4 mm of the ABB's path.
- What TP can and cannot compute with frames, measured on ROBOGUIDE
  ([docs/validation.md](docs/validation.md#15-frames-and-points-the-programs-compute)).
- Every probe runs again unattended on both simulators. Details: [docs/validation.md](docs/validation.md).
