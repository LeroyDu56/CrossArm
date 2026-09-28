/PROG  ARGRECORD
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "ArgRecord";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 12;
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
   1:  !RAPID ArgProbe.ArgRecord ;
   2:  R[5:nLast]=AR[1]    ;
   3:  R[1:nSum]=R[1:nSum]+AR[2]    ;
   4:  IF (AR[3]=1) THEN ;
   5:  R[4:nOn]=R[4:nOn]+1    ;
   6:  ENDIF ;
   7:  IF (AR[4]=1) THEN ;
   8:  R[3:nFlags]=R[3:nFlags]+1    ;
   9:  ENDIF ;
  10:  FOR R[8:i]=1 TO AR[1] ;
  11:  R[2:nCount]=R[2:nCount]+1    ;
  12:  ENDFOR ;
/POS
/END
