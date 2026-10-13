/PROG  STATION
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Station";
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
   1:  !RAPID OptArgProbe.Station ;
   2:  R[1:Count]=AR[9]    ;
   3:  IF (AR[2]=1) THEN ;
   4:  R[2:nSpeedSum]=R[2:nSpeedSum]+AR[3]    ;
   5:  ELSE ;
   6:  R[3:nAbsent]=R[3:nAbsent]+1    ;
   7:  ENDIF ;
   8:  IF (AR[4]=1 AND AR[5]=1) THEN ;
   9:  R[4:nFast]=R[4:nFast]+1    ;
  10:  ENDIF ;
  11:  IF (AR[6]=1) THEN ;
  12:  R[5:nLabel]=R[5:nLabel]+1    ;
  13:  ENDIF ;
  14:  IF (AR[10]=1) THEN ;
  15:  R[6:nSlow]=R[6:nSlow]+1    ;
  16:  ENDIF ;
  17:  IF (AR[8]=1) THEN ;
  18:  R[1:Count]=R[1:Count]+AR[1]    ;
  19:  ENDIF ;
/POS
/END
