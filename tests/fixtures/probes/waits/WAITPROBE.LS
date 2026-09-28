/PROG  WAITPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "WaitProbe";
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
   1:  !RAPID WaitProbe.WaitProbe ;
   2:  R[1:nTimeouts]=0    ;
   3:  R[2:nAfter]=0    ;
   4:  R[3:nRetries]=0    ;
   5:  F[1]=(OFF) ;
   6:  CALL WAITNEXT    ;
   7:  CALL WAITRETRY    ;
   8:  R[2:nAfter]=R[2:nAfter]+100    ;
/POS
/END
