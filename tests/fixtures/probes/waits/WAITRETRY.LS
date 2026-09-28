/PROG  WAITRETRY
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "WaitRetry";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 22;
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
   1:  !RAPID WaitProbe.WaitRetry ;
   2:  LBL[1] ;
   3:  TIMER[10]=RESET ;
   4:  TIMER[10]=START ;
   5:  LBL[2] ;
   6:  R[4:WaitTimer]=TIMER[10]    ;
   7:  IF (F[1]=OFF AND R[4:WaitTimer]<.2) THEN ;
   8:  JMP LBL[2] ;
   9:  ENDIF ;
  10:  TIMER[10]=STOP ;
  11:  IF (F[1]=ON) THEN ;
  12:  JMP LBL[3] ;
  13:  ENDIF ;
  14:  IF (R[3:nRetries]<2) THEN ;
  15:  R[3:nRetries]=R[3:nRetries]+1    ;
  16:  JMP LBL[1] ;
  17:  ELSE ;
  18:  R[1:nTimeouts]=R[1:nTimeouts]+1    ;
  19:  END ;
  20:  ENDIF ;
  21:  LBL[3] ;
  22:  R[2:nAfter]=R[2:nAfter]+10    ;
/POS
/END
