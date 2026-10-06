# Changelog

All notable changes to CrossArm, the ABB RAPID to FANUC TP converter. Dates are release dates;
downloads are on the [releases page](https://github.com/LeroyDu56/CrossArm/releases).

## Unreleased

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

### Report
- A call to a routine, or a use of data, that no module of the backup declares (a system module, an option, another
  task) is a cause of its own, "routine or data not in the backup", saying what to add, instead of a routine call
  or a value CrossArm could not convert. RAPID's own instructions and data, and a routine's parameters, are not.
- A statement reading what an operator dialog or a socket gave (`IF answer=resCancel`, `IF status=SOCKET_CONNECTED`)
  is "RAPID instruction without a TP equivalent", with why, instead of a value CrossArm could not work out; a
  position or a record compared as a whole (`IF pPick=pEmpty`) is a condition TP cannot test.

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
