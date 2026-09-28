/PROG  ARGTURN
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "ArgTurn";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 6;
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
   1:  !RAPID ArgProbe.ArgTurn ;
   2:  R[9:angle]=AR[1]    ;
   3:  IF (R[9:angle]>360) THEN ;
   4:  R[9:angle]=0    ;
   5:  ENDIF ;
   6:  R[6:nAngle]=R[6:nAngle]+R[9:angle]    ;
/POS
/END
