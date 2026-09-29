/PROG  WEIGH
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Weigh";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 5;
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
   1:  !RAPID ArrayProbe.Weigh ;
   2:  R[2:nCalls]=R[2:nCalls]+AR[1]    ;
   3:  IF (AR[2]>1) THEN ;
   4:  R[3:nHits]=R[3:nHits]+100    ;
   5:  ENDIF ;
/POS
/END
