/PROG  FTREPEAT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FtRepeat";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 9;
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
   3:  !RAPID FuncTextProbe.FtRepeat ;
   4:  CALL CA_TEXT(9,'x',0) ;
   5:  SR[9]=SUBSTR SR[9],2,0 ;
   6:  FOR R[5:i]=1 TO AR[2] ;
   7:  SR[9]=SR[9]+AR[1] ;
   8:  ENDFOR ;
   9:  SR[AR[3]]=SR[9] ;
/POS
/END
