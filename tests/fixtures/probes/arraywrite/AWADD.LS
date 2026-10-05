/PROG  AWADD
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "AwAdd";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 10;
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
   1:  !RAPID ArrayWriteProbe.AwAdd ;
   2:  FOR R[5:i]=1 TO 3 ;
   3:  FOR R[6:j]=1 TO 4 ;
   4:  R[3:NumberIndex]=R[5:i]    ;
   5:  R[3:NumberIndex]=R[3:NumberIndex]*4    ;
   6:  R[3:NumberIndex]=R[3:NumberIndex]+R[6:j]    ;
   7:  R[3:NumberIndex]=R[3:NumberIndex]+184    ;
   8:  R[7:awSum]=R[7:awSum]+R[R[3]]    ;
   9:  ENDFOR ;
  10:  ENDFOR ;
/POS
/END
