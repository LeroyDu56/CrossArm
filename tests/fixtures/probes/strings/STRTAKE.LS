/PROG  STRTAKE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "StrTake";
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
DEFAULT_GROUP	= 1,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
/MN
   1:  !RAPID StringProbe.StrTake ;
   2:  R[200:Calc2]=STRLEN AR[1]    ;
   3:  R[19:spTakeLen]=R[19:spTakeLen]+R[200:Calc2]    ;
   4:  CALL CA_TEXT(25,'42',0) ;
   5:  IF SR[25]<>AR[1],JMP LBL[1] ;
   6:  R[20:spTake42]=R[20:spTake42]+1    ;
   7:  LBL[1] ;
/POS
/END
