/PROG  STRSTEP
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "StrStep";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 13;
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
   1:  !RAPID StringProbe.StrStep ;
   2:  CALL CA_TEXT(25,'IDLE',0) ;
   3:  IF SR[3]<>SR[25],JMP LBL[2] ;
   4:  CALL CA_TEXT(3,'RUN',0) ;
   5:  JMP LBL[1] ;
   6:  LBL[2] ;
   7:  CALL CA_TEXT(25,'RUN',0) ;
   8:  IF SR[3]<>SR[25],JMP LBL[1] ;
   9:  R[7:spRuns]=R[7:spRuns]+1    ;
  10:  IF (R[7:spRuns]>=3) THEN ;
  11:  CALL CA_TEXT(3,'DONE',0) ;
  12:  ENDIF ;
  13:  LBL[1] ;
/POS
/END
