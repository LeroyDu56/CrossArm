/PROG  INTPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "IntProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 63;
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
   7:  R[6:nShared]=0    ;
   8:  R[7:nState]=0    ;
   9:  DO[1]=OFF ;
  10:  DO[2]=OFF ;
  11:  MONITOR END IEDGE ;
  12:  MONITOR END IONCE ;
  13:  MONITOR END IFALL ;
  14:  MONITOR END IWATCH ;
  15:  MONITOR END IUP ;
  16:  MONITOR END IDOWN ;
  17:  MONITOR IEDGE ;
  18:  MONITOR IONCE ;
  19:  MONITOR IFALL ;
  20:  R[8:iWatchSeen]=R[7:nState]    ;
  21:  MONITOR IWATCH ;
  22:  DO[3]=OFF ;
  23:  MONITOR IUP ;
  24:  MONITOR IDOWN ;
  25:  WAIT    .10(sec) ;
  26:  FOR R[9:i]=1 TO 3 ;
  27:  DO[1]=ON ;
  28:  WAIT    .10(sec) ;
  29:  DO[1]=OFF ;
  30:  WAIT    .10(sec) ;
  31:  ENDFOR ;
  32:  DO[2]=ON ;
  33:  WAIT    .10(sec) ;
  34:  DO[2]=OFF ;
  35:  WAIT    .10(sec) ;
  36:  DO[2]=ON ;
  37:  WAIT    .10(sec) ;
  38:  DO[2]=OFF ;
  39:  WAIT    .10(sec) ;
  40:  R[7:nState]=5    ;
  41:  WAIT    .10(sec) ;
  42:  R[7:nState]=7    ;
  43:  WAIT    .10(sec) ;
  44:  DO[3]=ON ;
  45:  WAIT    .10(sec) ;
  46:  DO[3]=OFF ;
  47:  WAIT    .10(sec) ;
  48:  DO[3]=ON ;
  49:  WAIT    .10(sec) ;
  50:  MONITOR END IEDGE ;
  51:  CALL INTPULSE    ;
  52:  MONITOR IEDGE ;
  53:  WAIT    .10(sec) ;
  54:  CALL INTPULSE    ;
  55:  MONITOR END IEDGE ;
  56:  MONITOR END IFALL ;
  57:  MONITOR END IWATCH ;
  58:  MONITOR END IUP ;
  59:  MONITOR END IDOWN ;
  60:  DO[3]=OFF ;
  61:  CALL INTPULSE    ;
  62:  R[7:nState]=9    ;
  63:  WAIT    .10(sec) ;
/POS
/END
