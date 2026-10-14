/PROG  CA_TEXT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CrossArm text";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 9;
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
   1:  !CrossArm EVALUATION copy ;
   2:  !production use needs a licence ;
   3:  !Text AR[2] into SR[AR[1]] ;
   4:  !AR[3]=1: added at its end ;
   5:  IF AR[3]=1,JMP LBL[1] ;
   6:  SR[AR[1]]=AR[2] ;
   7:  END ;
   8:  LBL[1] ;
   9:  SR[AR[1]]=SR[AR[1]]+AR[2] ;
/POS
/END
