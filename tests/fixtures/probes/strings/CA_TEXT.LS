/PROG  CA_TEXT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CrossArm text";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 7;
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
   1:  !Text AR[2] into SR[AR[1]] ;
   2:  !AR[3]=1: added at its end ;
   3:  IF AR[3]=1,JMP LBL[1] ;
   4:  SR[AR[1]]=AR[2] ;
   5:  END ;
   6:  LBL[1] ;
   7:  SR[AR[1]]=SR[AR[1]]+AR[2] ;
/POS
/END
