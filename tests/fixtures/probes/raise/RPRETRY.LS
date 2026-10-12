/PROG  RPRETRY
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RpRetry";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 17;
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
   3:  !RAPID RaiseProbe.RpRetry ;
   4:  R[9:RpRetryRetries]=0    ;
   5:  LBL[1] ;
   6:  CALL RPFLAKY    ;
   7:  IF R[8:Raised]=0,JMP LBL[2] ;
   8:  R[10:ErrNo]=R[8:Raised]    ;
   9:  R[8:Raised]=0    ;
  10:  IF (R[10:ErrNo]=10000) THEN ;
  11:  R[9:RpRetryRetries]=R[9:RpRetryRetries]+1    ;
  12:  IF R[9:RpRetryRetries]<=4,JMP LBL[1] ;
  13:  ABORT ;
  14:  ENDIF ;
  15:  ABORT ;
  16:  LBL[2] ;
  17:  R[2:rpTrace]=R[2:rpTrace]+1    ;
/POS
/END
