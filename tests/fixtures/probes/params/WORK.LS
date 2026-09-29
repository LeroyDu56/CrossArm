/PROG  WORK
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Work";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 9;
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
   1:  !RAPID ParamProbe.Work ;
   2:  FOR R[6:i]=1 TO AR[1] ;
   3:  R[1:nSum]=R[1:nSum]+AR[2]    ;
   4:  ENDFOR ;
   5:  IF (AR[3]=1) THEN ;
   6:  R[2:nCount]=R[2:nCount]+10    ;
   7:  ELSE ;
   8:  R[2:nCount]=R[2:nCount]+1    ;
   9:  ENDIF ;
/POS
/END
