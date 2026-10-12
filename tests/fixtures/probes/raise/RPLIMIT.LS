/PROG  RPLIMIT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RpLimit";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 18;
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
   3:  !RAPID RaiseProbe.RpLimit ;
   4:  R[13:rpLimit]=0    ;
   5:  R[14:RpLimitRetries]=0    ;
   6:  LBL[1] ;
   7:  CALL RPALWAYS    ;
   8:  IF R[8:Raised]=0,JMP LBL[2] ;
   9:  R[10:ErrNo]=R[8:Raised]    ;
  10:  R[8:Raised]=0    ;
  11:  IF (R[10:ErrNo]=10000) THEN ;
  12:  R[14:RpLimitRetries]=R[14:RpLimitRetries]+1    ;
  13:  IF R[14:RpLimitRetries]<=4,JMP LBL[1] ;
  14:  ABORT ;
  15:  ENDIF ;
  16:  ABORT ;
  17:  LBL[2] ;
  18:  R[13:rpLimit]=R[13:rpLimit]+100    ;
/POS
/END
