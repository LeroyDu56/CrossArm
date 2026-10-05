/PROG  FATALLY
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FaTally";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 8;
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
   1:  !RAPID FlagArrayProbe.FaTally ;
   2:  FOR R[3:i]=1 TO 6 ;
   3:  R[2:NumberIndex]=R[3:i]    ;
   4:  R[2:NumberIndex]=R[2:NumberIndex]+1018    ;
   5:  IF (F[R[2]]=ON) THEN ;
   6:  R[4:faCount]=R[4:faCount]+1    ;
   7:  ENDIF ;
   8:  ENDFOR ;
/POS
/END
