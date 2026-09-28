/PROG  CONDPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CondProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 41;
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
   1:  !RAPID CondProbe.CondProbe ;
   2:  R[1:nHits]=0    ;
   3:  R[2:nMiss]=0    ;
   4:  R[3:nGroup]=0    ;
   5:  R[4:nLoops]=0    ;
   6:  R[5:nMode]=0    ;
   7:  F[1]=(ON) ;
   8:  !Ready() = TRUE ;
   9:  IF (R[5:nMode]=0) THEN ;
  10:  R[1:nHits]=R[1:nHits]+1    ;
  11:  ENDIF ;
  12:  !Blocked() = FALSE AND NOT Armed( ;
  13:  IF (R[5:nMode]<>2 AND (R[5:nMode]<>0 OR F[1]=OFF)) THEN ;
  14:  R[2:nMiss]=R[2:nMiss]+1    ;
  15:  ENDIF ;
  16:  R[5:nMode]=1    ;
  17:  !Blocked() = FALSE AND NOT Armed( ;
  18:  IF (R[5:nMode]<>2 AND (R[5:nMode]<>0 OR F[1]=OFF)) THEN ;
  19:  R[1:nHits]=R[1:nHits]+10    ;
  20:  ENDIF ;
  21:  IF (R[5:nMode]>0 AND (R[5:nMode]<=2 AND F[1]=OFF)) THEN ;
  22:  R[2:nMiss]=R[2:nMiss]+10    ;
  23:  ENDIF ;
  24:  F[1]=(OFF) ;
  25:  IF (R[5:nMode]>0 AND (R[5:nMode]<=2 AND F[1]=OFF)) THEN ;
  26:  R[3:nGroup]=R[3:nGroup]+1    ;
  27:  ENDIF ;
  28:  !l.35 IF never TRUE: left out ;
  29:  !l.38 IF always TRUE: no test ;
  30:  R[1:nHits]=R[1:nHits]+100    ;
  31:  !NOT Ready() ;
  32:  LBL[1] ;
  33:  IF (R[5:nMode]=0) THEN ;
  34:  JMP LBL[2] ;
  35:  ENDIF ;
  36:  R[4:nLoops]=R[4:nLoops]+1    ;
  37:  R[5:nMode]=R[5:nMode]-1    ;
  38:  JMP LBL[1] ;
  39:  LBL[2] ;
  40:  !Ready() ;
  41:  WAIT (R[5:nMode]=0)    ;
/POS
/END
