/PROG  SELARG
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "SelArg";
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
   1:  !RAPID SelectProbe.SelArg ;
   2:  R[6:TestValue]=AR[1]    ;
   3:  SELECT R[6:TestValue]=3,JMP LBL[2] ;
   4:         ELSE,JMP LBL[3] ;
   5:  LBL[2] ;
   6:  R[2:nCalls]=R[2:nCalls]+10    ;
   7:  JMP LBL[1] ;
   8:  LBL[3] ;
   9:  R[2:nCalls]=R[2:nCalls]+100    ;
  10:  LBL[1] ;
/POS
/END
