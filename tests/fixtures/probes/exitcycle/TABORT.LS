/PROG  TABORT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "tAbort";
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
      PAUSE_REQUEST	= 2;
DEFAULT_GROUP	= *,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
/MN
   1:  !RAPID ExitProbe.tAbort ;
   2:  R[4:nTraps]=R[4:nTraps]+1    ;
   3:  CALL CA_STOPMOVE(1,1) ;
   4:  F[1]=(ON) ;
   5:  !l.36 ClearPath ;
   6:  F[1]=(OFF) ;
   7:  CALL CA_EXITCYCLE(1) ;
   8:  MONITOR IABORT ;
/POS
/END
