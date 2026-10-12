/PROG  RPBODY
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RpBody";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 16;
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
   3:  !RAPID RaiseProbe.RpBody ;
   4:  R[6:rpCode]=1    ;
   5:  R[8:Raised]=7    ;
   6:  R[10:ErrNo]=R[8:Raised]    ;
   7:  R[8:Raised]=0    ;
   8:  SELECT R[10:ErrNo]=7,JMP LBL[4] ;
   9:  JMP LBL[3] ;
  10:  LBL[4] ;
  11:  R[6:rpCode]=R[6:rpCode]+R[10:ErrNo]    ;
  12:  JMP LBL[2] ;
  13:  LBL[3] ;
  14:  ABORT ;
  15:  LBL[2] ;
  16:  R[6:rpCode]=R[6:rpCode]+20    ;
/POS
/END
