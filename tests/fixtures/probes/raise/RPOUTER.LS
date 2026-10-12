/PROG  RPOUTER
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RpOuter";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 14;
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
   3:  !RAPID RaiseProbe.RpOuter ;
   4:  CALL RPMIDDLE    ;
   5:  IF R[8:Raised]=0,JMP LBL[2] ;
   6:  R[10:ErrNo]=R[8:Raised]    ;
   7:  R[8:Raised]=0    ;
   8:  IF (R[10:ErrNo]=10001) THEN ;
   9:  R[5:rpPass]=R[5:rpPass]+10    ;
  10:  JMP LBL[2] ;
  11:  ENDIF ;
  12:  ABORT ;
  13:  LBL[2] ;
  14:  R[5:rpPass]=R[5:rpPass]+1000    ;
/POS
/END
