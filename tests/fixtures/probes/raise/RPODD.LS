/PROG  RPODD
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RpOdd";
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
   3:  !RAPID RaiseProbe.RpOdd ;
   4:  R[8:Raised]=0    ;
   5:  R[11:Calc1]=AR[1] MOD 2    ;
   6:  IF (R[11:Calc1]=1) THEN ;
   7:  R[8:Raised]=10001    ;
   8:  END ;
   9:  ENDIF ;
/POS
/END
