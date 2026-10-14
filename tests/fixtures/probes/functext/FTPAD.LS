/PROG  FTPAD
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FtPad";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 23;
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
   3:  !RAPID FuncTextProbe.FtPad ;
   4:  CALL CA_TEXT(7,'x',0) ;
   5:  SR[7]=SUBSTR SR[7],2,0 ;
   6:  CALL CA_TEXT(8,' ',0) ;
   7:  R[196:Calc1]=STRLEN AR[1]    ;
   8:  IF (R[196:Calc1]>=AR[2]) THEN ;
   9:  SR[AR[5]]=AR[1] ;
  10:  END ;
  11:  ENDIF ;
  12:  IF (AR[3]=1) THEN ;
  13:  SR[8]=AR[4] ;
  14:  ENDIF ;
  15:  SR[7]=AR[1] ;
  16:  R[194:FOR FROM l.43]=STRLEN AR[1]    ;
  17:  R[193:FOR TO l.43]=AR[2]-1    ;
  18:  FOR R[195:i]=R[194:FOR FROM l.43] TO R[193:FOR TO l.43] ;
  19:  SR[25]=SR[8] ;
  20:  SR[25]=SR[25]+SR[7] ;
  21:  SR[7]=SR[25] ;
  22:  ENDFOR ;
  23:  SR[AR[5]]=SR[7] ;
/POS
/END
