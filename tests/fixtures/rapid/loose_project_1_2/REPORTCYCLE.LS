/PROG  REPORTCYCLE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "ReportCycle";
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
   1:  !CrossArm EVALUATION copy ;
   2:  !production use needs a licence ;
   3:  !RAPID HmiAndGroups.ReportCycle ;
   4:  MESSAGE[Cell ready] ;
   5:  MESSAGE[Waiting for (code)] ;
   6:  R[11:nCode]=GI[1]    ;
   7:  GO[1]=R[11:nCode] ;
   8:  GO[2]=3 ;
   9:  MESSAGE[Exactly 24 characters ok] ;
  10:  MESSAGE[Cycle started] ;
/POS
/END
