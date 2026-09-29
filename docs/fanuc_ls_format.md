# FANUC `.LS` output: what is confirmed and what is not

CrossArm writes ASCII `.LS` listings. Every construct it emits is listed here with its
source of truth. Two sources confirm a construct:

* **Controller export**: observed on programs exported by FANUC controllers. The local test corpus
  holds the backups of three ROBOGUIDE virtual controllers (not distributed), and the parser and
  writer reproduce every program in them **byte for byte** (`tests/fanuc/test_corpus_ls.py`).
* **ROBOGUIDE round trip**: the generated programs
  [`tests/fixtures/fanuc/pick_and_place/`](../tests/fixtures/fanuc/pick_and_place/) were loaded into
  ROBOGUIDE, compiled to TP by the virtual controller without error, and exported back:
  [`tests/fixtures/fanuc/roboguide_export/`](../tests/fixtures/fanuc/roboguide_export/). CrossArm
  reproduces that export byte for byte. The only exception is the header values the controller
  computes itself (`tests/fanuc/test_roboguide_roundtrip.py`).

Every construct CrossArm emits has now been validated on a controller.

## File structure

| Element | Emitted as | Status |
|---|---|---|
| Sections | `/PROG`, `/ATTR` (tab-aligned keys), optional `/APPL`, `/MN`, `/POS`, `/END` | Controller export + ROBOGUIDE |
| Line endings | CRLF | Controller export + ROBOGUIDE |
| `PROG_SIZE`, `MEMORY_SIZE`, dates | `0` and conversion time. The controller recomputes them on load | ROBOGUIDE (accepted) |
| `COMMENT` | Routine name, not padded. Recent controllers pad it to 16 on export | ROBOGUIDE (accepted) |
| `LOCAL_REGISTERS` | Not emitted by default. Recent controllers add `0,0,0` on export | ROBOGUIDE (accepted without it) |
| Instruction line | `   1:  UFRAME_NUM=0 ;` | Controller export + ROBOGUIDE |
| Padded terminator | `CALL PLACE    ;`, `R[3:nCycles]=R[3:nCycles]+1    ;`, `WAIT DI[1]=ON    ;`, `WAIT (...)    ;` | Controller export + ROBOGUIDE |
| Numbers in `/POS` | 3 decimals, no leading zero below 1 (`.500`, `-.000`), exact zero `0.000`. A negative zero is an exact zero: never `-0.000` | ROBOGUIDE |
| Register / flag comments | `R[n:name]` kept only for registers the programs write; flags never commented (the controller keeps comments in its own tables) | ROBOGUIDE |
| Motion line | `   5:J P[1] 50% CNT20    ;` (motion letter right after `:`) | Controller export + ROBOGUIDE |
| Empty line | `   6:   ;` | Controller export |
| Empty program | `/MN` immediately followed by `/POS` | Controller export |

## What controller exports contain beyond what CrossArm emits

Found by reading controller exports back with the `.LS` parser (all reproduced byte for
byte). CrossArm does not emit these; the parser keeps them so files survive a round trip.

| Element | Observed | Kept as |
|---|---|---|
| Macro | `/PROG  NAME<tab><2 spaces>Macro` on macros (not two tabs) | `Program.macro` |
| Empty `/APPL` | `/APPL` directly followed by `/MN`, on macros | `Attributes.appl == ()` (`None`: no section) |
| Spaces before `;` | 0 to 18, depending on the instruction; no rule simple enough to recompute | `Instruction.pad`, `Motion.pad` |
| `LINE_COUNT` | 53 over a single `/MN` line: not always the number of lines | `Attributes.line_count` |
| Task control | `STACK_SIZE = 500` | `Attributes.stack_size` and siblings |
| Stray LFs | bare LF inside `/APPL` of a CRLF file | raw `/APPL` lines |
| Trailing blank lines | two lines of two spaces between the last instruction and `/POS` | `Program.mn_extra` |
| Not a program | a listing saved as `.LS` (an alarm history, for instance) | refused (`LSFormatError`) |

## Instructions

| TP | Example | Status |
|---|---|---|
| Joint / linear motion | `J P[1] 50% CNT50`, `L P[2] 500mm/sec FINE` | ROBOGUIDE |
| Circular motion | `C P[1]` + continuation line `    :  P[2] 300mm/sec CNT10    ;` | ROBOGUIDE |
| Frames | `UFRAME_NUM=1`, `UTOOL_NUM=2` | Controller export + ROBOGUIDE |
| Digital output | `DO[1]=ON` | Controller export + ROBOGUIDE |
| Group I/O | `GO[1]=R[1:nCode]`, `GO[2]=3`, `R[1:nCode]=GI[1]` | ROBOGUIDE |
| Operator message | `MESSAGE[Cell ready]`: 24 characters at most, longer texts are **silently cut by the controller** (probe: 24/25/32/40 characters all accepted, all exported cut to 24) | ROBOGUIDE |
| Register | `R[2:nSlot]=R[1:i]`, `R[3:nCycles]=R[3:nCycles]+1` | ROBOGUIDE |
| Register with `DIV` / `MOD` | `R[2:nRow]=R[1] DIV 4` | ROBOGUIDE |
| Flag | `F[1]=(ON)` | Controller export + ROBOGUIDE |
| Remark | `!text` (no parentheses in `.LS`) | Controller export + ROBOGUIDE |
| Label / jump | `LBL[1]`, `JMP LBL[1]` | Controller export + ROBOGUIDE |
| Call | `CALL PICK` | Controller export + ROBOGUIDE |
| Mixed-logic IF block, nested | `IF (R[2:nSlot]=1) THEN` / `ELSE` / `ENDIF` | ROBOGUIDE |
| Conditions with `AND` / `OR`, flags | `IF (R[1]>=12 OR F[1]=ON) THEN` | ROBOGUIDE |
| Grouped conditions, group input | `IF (R[5]<>2 AND (R[5]<>0 OR F[1]=OFF)) THEN`, `IF (GI[1]=0 AND DI[1]=OFF) THEN` | ROBOGUIDE (condition probe: the grouped conditions run, registers as RAPID computes; the group input loaded) |
| FOR loop | `FOR R[1:i]=1 TO 3` / `ENDFOR` | ROBOGUIDE |
| Select | `SELECT R[5:nMode]=1,JMP LBL[4] ;` then `       =(-1),CALL SELCOUNT ;`, `       ELSE,JMP LBL[6] ;`: the next lines indented 7 spaces (the controller indents them so), a negative value stored in parentheses, `.5` without its zero, one space before `;`. The first equal value wins; with no `ELSE` and no equal value the program goes on after the `SELECT`, and so does a `CALL` made on a `SELECT` line once it returns | ROBOGUIDE (select probe, run: registers as RobotStudio computes) |
| FOR loop, descending | `FOR R[5:k]=3 DOWNTO 1` | ROBOGUIDE |
| Timed wait | `WAIT    .30(sec)` (width 6, no leading zero) | ROBOGUIDE |
| Other waits | `WAIT R[4]`, `WAIT DI[1]=ON`, `WAIT DO[2]=ON`, `WAIT (DI[1]=OFF OR R[6]<>0)` | ROBOGUIDE |
| Timer | `TIMER[10]=RESET`, `TIMER[10]=START`, `TIMER[10]=STOP`, `R[4]=TIMER[10]`: the reading is in seconds (1.000000 after `WAIT 1.00(sec)`) | ROBOGUIDE (wait probe, run) |
| Wait with a time limit | a loop: `LBL[2]` / `R[4]=TIMER[10]` / `IF (F[1]=OFF AND R[4]<.2) THEN` / `JMP LBL[2]` / `ENDIF`. Decimals below 1 in a condition are stored `.2`, not `0.2`. `$WAITTMOUT=200` loads but stops the program when run: **VARS-010** Variable/field write-protected | ROBOGUIDE (wait probe, run) |
| Pause / abort | `PAUSE`, `ABORT` | Controller export + ROBOGUIDE |
| Call with arguments | `CALL ARGRECORD(3,(-2.5),1,1) ;`: one space before `;`, decimals without leading zero (`.5`), arguments read as `AR[n]` in values, `IF (AR[3]=1)`, `FOR R[8:i]=1 TO AR[1]`, `WAIT AR[1]`, and passed on (`CALL X(AR[1],1)`). Text: `CALL FAULT('Pince non ouverte',3) ;`, 38 characters per string at most (39 **refused**, ASBN-092, whatever the line's length), `"`, `,` and `(` inside, an apostrophe **refused**; the routine keeps it (`SR[5]=AR[1]`, `R[7]=STRLEN AR[1]`) but cannot show it (`MESSAGE` takes fixed text; `$UALRM_MSG[1]=AR[1]` runs and leaves it unset) | ROBOGUIDE (argument probe, run: registers as RAPID computes; strings: loaded, `SR` and `STRLEN` read back) |
| Negative constant | `R[20]=(-2.5)`, `R[20]=R[21]*(-2)`, `CALL P((-2.5))`, `FOR R[20]=(-2) TO 2`: parentheses; `IF (R[20]<-2.5)`, `WAIT (R[20]<-2.5)`: bare. `CALL P(-2.5)` and `FOR R[20]=-2 TO 2` are **refused** (ASBN-092); `R[20]=-2.5` loads but is stored with parentheses | ROBOGUIDE (negative-constant probe) |
| Frames by program | `PR[100]=P[1]`, `UTOOL[1]=PR[100]`, `UFRAME[1]=PR[100]`, `PR[31]=UTOOL[1]`, `PR[51]=LPOS`, `PR[71]=JPOS` | ROBOGUIDE (pose and setup probes, run) |
| Frames the programs compute | `UTOOL[1]=PR[99]` / `UFRAME[2]=PR[97]` where the RAPID computes the frame, the register set by `SETUP_FRAMES` (`PR[99]=P[11]`); `PR[98]=PR[97]` for a frame kept in a register (past the limit) | ROBOGUIDE (compute probe, run); `PR[n]=PR[m]` loaded and read back (TP frame probe) |
| Spaces before `;` | 4 after `CALL NAME`, `R[n]=...`, `PR[n]=P[m]`, `PR[n]=PR[m]`, `PR[n]=LPOS` / `JPOS`, `WAIT DI[n]=...`, `WAIT (...)`; 1 elsewhere, including `CALL NAME(args)`, `PR[n]=UTOOL[m]` and `UTOOL[n]=PR[m]`. A remark does not end with a space | ROBOGUIDE (probe programs and programs of the test corpus, read back from the robot) |
| Point in a position register | `PR[99]=P[1]` then `CALL PICKAT(2)`; in the routine `L PR[99] 200mm/sec FINE`, `PR[98]=PR[99]`, `PR[98,3]=PR[98,3]+40` (4 spaces before `;`). A move to a position register filled from a `P` takes the values and the configuration of the `P`, in the frames selected when it runs (LPOS read in UF 2 after `PR[60]=P[1]` recorded in UF 1: the same values) | ROBOGUIDE (point probe, run: the poses of the moves written out) |
| Array of points | `R[3:PointIndex]=R[1:r]`, `R[3:PointIndex]=R[3:PointIndex]*3`, `+R[2:c]`, `+88`, then `L PR[R[3]] 200mm/sec FINE`, `J PR[R[3]] 20% FINE`, `PR[99]=PR[R[3]]` (4 spaces before `;`); `SETUP_FRAMES` fills the block (`PR[92]=P[14]`) | ROBOGUIDE (point probe, run: the poses of the moves written out) |
| Frames past the limit | `UTOOL[2]=PR[99]` / `UTOOL_NUM=2` before a move, `UFRAME[1]=PR[98]` / `UFRAME_NUM=1`; a selection past the limit (`UTOOL_NUM=11` with 10 tool frames) is **refused** at load (ASBN-092) | ROBOGUIDE (bank probe, run; every program of the test corpus loaded) |
| Pulse | `DO[1]=PULSE,0.5sec ;`: tenths of a second, stored with the zero (`0.5sec`), 0.25 stored `0.3sec`, a length below 0.05 dropped for the controller's default, 25.5 s at most (25.6 **refused**, ASBN-092); on during its length, off after | ROBOGUIDE (I/O probe, run) |
| Inverted output | `DO[1]=(!DO[1]) ;` | ROBOGUIDE (I/O probe, run) |
| Payload schedule | `PAYLOAD[10] ;`: selects the schedule (`$PLST_PARNUM[1]` follows it); `PAYLOAD[11]` loads but stops the program when run, with 10 schedules | ROBOGUIDE (I/O probe, run) |
| Analog output | `AO[1]=250 ;`, `AO[1]=4.5`, `AO[1]=(-5)`, `AO[1]=R[1]` load; `AO[1]=R[1]/10` is **refused**: through a register | ROBOGUIDE |
| Group output from a group input | `GO[4]=GI[3]` is **refused** at load (ASBN-092): `R[5]=GI[3]` then `GO[4]=R[5]` | ROBOGUIDE |
| End | `END` | ROBOGUIDE |

## `/POS` section

Both layouts are confirmed byte for byte.

Joint position (controller export):

```
P[1]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=   -30.000 deg,	J3=    30.000 deg,
	J4=     0.000 deg,	J5=    90.000 deg,	J6=     0.000 deg
};
```

Cartesian position (ROBOGUIDE round trip):

```
P[1]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   900.000  mm,	Y =     0.000  mm,	Z =   500.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
```

## Known limits

* The arm configuration (`CONFIG`) is derived from ABB `confdata` with conventions **measured** on
  both controllers: the same 16 joint sets were evaluated by RobotStudio (IRB 6700-140/2.85) and ROBOGUIDE
  (M-20iD/25).
  See `src/crossarm/convert/configuration.py` and `tests/convert/test_configuration.py`. The
  measurements show that FANUC J4, J5, J6 turn opposite to ABB, that FANUC J3 is absolute
  (J2/J3 coupling), and that the flange frames differ by 180° about z. Two limits remain. A
  different robot model may need another posture to reach a point. The J6 turn number depends on
  the pin hole the tool is fitted by (`tool_pin`, `-x` by default: the ABB tool frame reused as
  UTOOL; `+x`: turned half a turn about z). The `U/D` and `T/B` letters are the same geometric criteria on
  both brands: wrist centre past the shoulder–elbow line, and wrist centre behind axis 1. This was
  checked on every probe point, including a J3 sweep showing that the ABB bit flips exactly at the
  IRB 6700 elbow singularity (J3 = −81.83°). `"config_mapping": false` in the mapping file
  falls back to `'N U T, 0, 0, 0'`.
* Joint targets (`MoveAbsJ`) are converted for the same posture:
  `(J1, J2, -(J2+J3), -J4, -J5, 180-J6)`, or `-J6` with `"tool_pin": "+x"`. J2's direction was confirmed by fitting the arm
  geometry on the measured positions: the fit is exact and recovers the M-20iD/25 link lengths.
  On another robot model the TCP lands elsewhere, so check joint limits and clearances.
  `"joint_mapping": false` copies the values as they are.
* No `P[n]` comment is emitted (`P[1:HOME]`). The report maps every `P[n]` back to its RAPID name.
