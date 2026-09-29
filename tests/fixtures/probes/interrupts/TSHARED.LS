/PROG  TSHARED
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "tShared";
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
DEFAULT_GROUP	= *,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
/MN
   1:  !RAPID IntProbe.tShared ;
   2:  SELECT R[10:IntNo]=5,JMP LBL[2] ;
   3:         =6,JMP LBL[3] ;
   4:  JMP LBL[1] ;
   5:  LBL[2] ;
   6:  R[6:nShared]=R[6:nShared]+1    ;
   7:  JMP LBL[1] ;
   8:  LBL[3] ;
   9:  R[6:nShared]=R[6:nShared]+10    ;
  10:  LBL[1] ;
/POS
/END
