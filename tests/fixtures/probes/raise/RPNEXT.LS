/PROG  RPNEXT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RpNext";
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
   3:  !RAPID RaiseProbe.RpNext ;
   4:  FOR R[12:i]=1 TO 5 ;
   5:  CALL RPODD(R[12:i]) ;
   6:  IF R[8:Raised]=0,JMP LBL[2] ;
   7:  R[10:ErrNo]=R[8:Raised]    ;
   8:  R[8:Raised]=0    ;
   9:  IF (R[10:ErrNo]=10001) THEN ;
  10:  R[3:rpSkip]=R[3:rpSkip]+1    ;
  11:  JMP LBL[2] ;
  12:  ENDIF ;
  13:  ABORT ;
  14:  LBL[2] ;
  15:  R[3:rpSkip]=R[3:rpSkip]+10    ;
  16:  ENDFOR ;
/POS
/END
