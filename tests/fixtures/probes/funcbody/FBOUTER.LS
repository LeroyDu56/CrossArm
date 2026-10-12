/PROG  FBOUTER
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FbOuter";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 8;
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
   3:  !RAPID FuncBodyProbe.FbOuter ;
   4:  CALL FBSCALE(AR[1],23) ;
   5:  R[22:a]=R[23:result]    ;
   6:  R[21:Calc1]=AR[1]+1    ;
   7:  CALL FBSCALE(R[21:Calc1],23) ;
   8:  R[AR[2]]=R[22:a]+R[23:result] ;
/POS
/END
