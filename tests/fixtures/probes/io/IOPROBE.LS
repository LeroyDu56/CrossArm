/PROG  IOPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "IoProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 29;
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
   1:  !RAPID IoProbe.IoProbe ;
   2:  R[1:nInvert]=0    ;
   3:  R[2:nPulse]=0    ;
   4:  R[3:nTime]=0    ;
   5:  DO[1]=OFF ;
   6:  DO[1]=(!DO[1]) ;
   7:  IF (DO[1]=ON) THEN ;
   8:  R[1:nInvert]=R[1:nInvert]+1    ;
   9:  ENDIF ;
  10:  DO[1]=(!DO[1]) ;
  11:  IF (DO[1]=OFF) THEN ;
  12:  R[1:nInvert]=R[1:nInvert]+10    ;
  13:  ENDIF ;
  14:  DO[2]=OFF ;
  15:  DO[2]=PULSE,0.5sec ;
  16:  WAIT    .10(sec) ;
  17:  IF (DO[2]=ON) THEN ;
  18:  R[2:nPulse]=R[2:nPulse]+1    ;
  19:  ENDIF ;
  20:  WAIT    .60(sec) ;
  21:  IF (DO[2]=OFF) THEN ;
  22:  R[2:nPulse]=R[2:nPulse]+10    ;
  23:  ENDIF ;
  24:  TIMER[1]=RESET ;
  25:  TIMER[1]=START ;
  26:  WAIT    .50(sec) ;
  27:  TIMER[1]=STOP ;
  28:  R[3:nTime]=TIMER[1]    ;
  29:  AO[1]=250 ;
/POS
/END
