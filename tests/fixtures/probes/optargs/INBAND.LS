/PROG  INBAND
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "InBand";
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
   1:  !RAPID OptArgProbe.InBand ;
   2:  IF (AR[3]=1) THEN ;
   3:  R[13:Calc2]=AR[2]-AR[4]    ;
   4:  R[14:Calc4]=AR[2]+AR[4]    ;
   5:  IF (AR[1]>=R[13:Calc2] AND AR[1]<=R[14:Calc4]) THEN ;
   6:  R[AR[5]]=1 ;
   7:  END ;
   8:  ENDIF ;
   9:  R[AR[5]]=0 ;
  10:  END ;
  11:  ENDIF ;
  12:  IF (AR[1]=AR[2]) THEN ;
  13:  R[AR[5]]=1 ;
  14:  ELSE ;
  15:  R[AR[5]]=0 ;
  16:  ENDIF ;
/POS
/END
