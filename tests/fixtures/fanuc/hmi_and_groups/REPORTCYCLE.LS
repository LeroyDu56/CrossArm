/PROG  REPORTCYCLE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "ReportCycle";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 08:00:00;
MODIFIED	= DATE 26-01-01  TIME 08:00:00;
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
   1:  !RAPID HmiAndGroups.ReportCycle ;
   2:  MESSAGE[Cell ready] ;
   3:  MESSAGE[Waiting for (code)] ;
   4:  R[1:nCode]=GI[1]    ;
   5:  GO[1]=R[1:nCode] ;
   6:  GO[2]=3 ;
   7:  MESSAGE[Exactly 24 characters ok] ;
   8:  MESSAGE[Cycle started] ;
/POS
/END
