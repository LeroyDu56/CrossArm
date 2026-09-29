/PROG  PARPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "ParProbe";
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
   1:  !RAPID ParamProbe.ParProbe ;
   2:  R[1:nSum]=0    ;
   3:  R[2:nCount]=0    ;
   4:  R[3:nBack]=0    ;
   5:  CALL WORK(3,.5,1) ;
   6:  CALL WORK(2,(-1.25),0) ;
   7:  CALL BUMP(R[3:nBack],4) ;
   8:  R[3:nBack]=R[4:n]    ;
   9:  CALL BUMP(R[3:nBack],(-1.5)) ;
  10:  R[3:nBack]=R[4:n]    ;
  11:  CALL TWICE(R[3:nBack]) ;
  12:  R[3:nBack]=R[5:n]    ;
  13:  R[2:nCount]=R[2:nCount]-1    ;
  14:  R[1:nSum]=R[1:nSum]+10    ;
  15:  R[2:nCount]=0    ;
  16:  R[2:nCount]=R[2:nCount]+1    ;
  17:  CALL WORK(3,.5,1) ;
/POS
/END
