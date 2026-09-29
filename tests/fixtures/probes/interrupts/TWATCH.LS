/PROG  TWATCH
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "tWatch";
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
DEFAULT_GROUP	= *,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
/MN
   1:  !RAPID IntProbe.tWatch ;
   2:  R[7:iWatchSeen]=R[6:nState]    ;
   3:  R[4:nWatch]=R[4:nWatch]+1    ;
   4:  R[5:nLast]=R[6:nState]    ;
   5:  MONITOR IWATCH ;
/POS
/END
