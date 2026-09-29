/PROG  INTPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "IntProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 48;
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
   1:  !RAPID IntProbe.IntProbe ;
   2:  R[1:nHits]=0    ;
   3:  R[2:nOnce]=0    ;
   4:  R[3:nFall]=0    ;
   5:  R[4:nWatch]=0    ;
   6:  R[5:nLast]=0    ;
   7:  R[6:nState]=0    ;
   8:  DO[1]=OFF ;
   9:  DO[2]=OFF ;
  10:  MONITOR END IEDGE ;
  11:  MONITOR END IONCE ;
  12:  MONITOR END IFALL ;
  13:  MONITOR END IWATCH ;
  14:  MONITOR IEDGE ;
  15:  MONITOR IONCE ;
  16:  MONITOR IFALL ;
  17:  R[7:iWatchSeen]=R[6:nState]    ;
  18:  MONITOR IWATCH ;
  19:  WAIT    .10(sec) ;
  20:  FOR R[8:i]=1 TO 3 ;
  21:  DO[1]=ON ;
  22:  WAIT    .10(sec) ;
  23:  DO[1]=OFF ;
  24:  WAIT    .10(sec) ;
  25:  ENDFOR ;
  26:  DO[2]=ON ;
  27:  WAIT    .10(sec) ;
  28:  DO[2]=OFF ;
  29:  WAIT    .10(sec) ;
  30:  DO[2]=ON ;
  31:  WAIT    .10(sec) ;
  32:  DO[2]=OFF ;
  33:  WAIT    .10(sec) ;
  34:  R[6:nState]=5    ;
  35:  WAIT    .10(sec) ;
  36:  R[6:nState]=7    ;
  37:  WAIT    .10(sec) ;
  38:  MONITOR END IEDGE ;
  39:  CALL INTPULSE    ;
  40:  MONITOR IEDGE ;
  41:  WAIT    .10(sec) ;
  42:  CALL INTPULSE    ;
  43:  MONITOR END IEDGE ;
  44:  MONITOR END IFALL ;
  45:  MONITOR END IWATCH ;
  46:  CALL INTPULSE    ;
  47:  R[6:nState]=9    ;
  48:  WAIT    .10(sec) ;
/POS
/END
