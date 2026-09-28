/PROG  ARGPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "ArgProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 15;
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
   1:  !RAPID ArgProbe.ArgProbe ;
   2:  R[1:nSum]=0    ;
   3:  R[2:nCount]=0    ;
   4:  R[3:nFlags]=0    ;
   5:  R[4:nOn]=0    ;
   6:  R[5:nLast]=0    ;
   7:  R[6:nAngle]=0    ;
   8:  R[7:nWaits]=0    ;
   9:  CALL ARGRECORD(3,(-2.5),1,1) ;
  10:  CALL ARGRECORD(4,.5,0,0) ;
  11:  CALL ARGRECORD(2,10,1,1) ;
  12:  CALL ARGOUTER(1,1) ;
  13:  CALL ARGTURN(400) ;
  14:  CALL ARGTURN(90) ;
  15:  CALL ARGWAIT(.2) ;
/POS
/END
