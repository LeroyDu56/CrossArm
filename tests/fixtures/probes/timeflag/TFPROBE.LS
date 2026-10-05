/PROG  TFPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "TfProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 39;
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
   1:  !RAPID TimeFlagProbe.TfProbe ;
   2:  R[1:tfLate1]=0    ;
   3:  R[2:tfLate2]=0    ;
   4:  R[3:tfTime1]=0    ;
   5:  R[4:tfTime2]=0    ;
   6:  F[1]=(OFF) ;
   7:  F[2]=(ON) ;
   8:  TIMER[1]=RESET ;
   9:  TIMER[1]=START ;
  10:  TIMER[10]=RESET ;
  11:  TIMER[10]=START ;
  12:  LBL[1] ;
  13:  R[5:WaitTimer]=TIMER[10]    ;
  14:  IF (F[1]=OFF AND R[5:WaitTimer]<1.5) THEN ;
  15:  JMP LBL[1] ;
  16:  ENDIF ;
  17:  TIMER[10]=STOP ;
  18:  F[3]=(R[5:WaitTimer]>=1.5) ;
  19:  TIMER[1]=STOP ;
  20:  R[3:tfTime1]=TIMER[1]    ;
  21:  IF (F[3]=ON) THEN ;
  22:  R[1:tfLate1]=1    ;
  23:  ENDIF ;
  24:  TIMER[1]=RESET ;
  25:  TIMER[1]=START ;
  26:  TIMER[10]=RESET ;
  27:  TIMER[10]=START ;
  28:  LBL[2] ;
  29:  R[5:WaitTimer]=TIMER[10]    ;
  30:  IF (F[2]=OFF AND R[5:WaitTimer]<1.5) THEN ;
  31:  JMP LBL[2] ;
  32:  ENDIF ;
  33:  TIMER[10]=STOP ;
  34:  F[3]=(R[5:WaitTimer]>=1.5) ;
  35:  TIMER[1]=STOP ;
  36:  R[4:tfTime2]=TIMER[1]    ;
  37:  IF (F[3]=ON) THEN ;
  38:  R[2:tfLate2]=1    ;
  39:  ENDIF ;
/POS
/END
