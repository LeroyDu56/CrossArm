/PROG  WAITNEXT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "WaitNext";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 19;
MEMORY_SIZE	= 0;
PROTECT		= READ_WRITE;
TCD:  STACK_SIZE	= 0,
      TASK_PRIORITY	= 50,
      TIME_SLICE	= 0,
      BUSY_LAMP_OFF	= 0,
      ABORT_REQUEST	= 0,
      PAUSE_REQUEST	= 0;
DEFAULT_GROUP	= 1,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
/MN
   1:  !RAPID WaitProbe.WaitNext ;
   2:  TIMER[10]=RESET ;
   3:  TIMER[10]=START ;
   4:  LBL[1] ;
   5:  R[4:WaitTimer]=TIMER[10]    ;
   6:  IF (F[1]=OFF AND R[4:WaitTimer]<.5) THEN ;
   7:  JMP LBL[1] ;
   8:  ENDIF ;
   9:  TIMER[10]=STOP ;
  10:  R[2:nAfter]=R[2:nAfter]+1    ;
  11:  TIMER[10]=RESET ;
  12:  TIMER[10]=START ;
  13:  LBL[2] ;
  14:  R[4:WaitTimer]=TIMER[10]    ;
  15:  IF (DI[1]=OFF AND R[4:WaitTimer]<.3) THEN ;
  16:  JMP LBL[2] ;
  17:  ENDIF ;
  18:  TIMER[10]=STOP ;
  19:  R[2:nAfter]=R[2:nAfter]+1    ;
/POS
/END
