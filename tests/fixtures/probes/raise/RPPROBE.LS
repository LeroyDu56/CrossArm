/PROG  RPPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RpProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 19;
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
   3:  !RAPID RaiseProbe.RpProbe ;
   4:  !ERR_RP_A is error 10000 ;
   5:  !ERR_RP_B is error 10001 ;
   6:  R[1:rpTries]=0    ;
   7:  R[2:rpTrace]=0    ;
   8:  R[3:rpSkip]=0    ;
   9:  R[4:rpRet]=0    ;
  10:  R[5:rpPass]=0    ;
  11:  R[6:rpCode]=0    ;
  12:  R[7:rpDone]=0    ;
  13:  CALL RPRETRY    ;
  14:  CALL RPNEXT    ;
  15:  CALL RPRETURN    ;
  16:  R[4:rpRet]=R[4:rpRet]+10    ;
  17:  CALL RPOUTER    ;
  18:  CALL RPBODY    ;
  19:  R[7:rpDone]=1    ;
/POS
/END
