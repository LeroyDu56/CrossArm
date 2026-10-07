/PROG  EXTPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "ExtProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 12;
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
   1:  !RAPID ExtProbe.ExtProbe ;
   2:  R[1:nSum]=0    ;
   3:  R[2:nFlag]=0    ;
   4:  R[3:nLen]=0    ;
   5:  R[4:nLogged]=0    ;
   6:  R[5:nBack]=7    ;
   7:  R[6:nAfter]=0    ;
   8:  CALL EXTADD(3,(-2.5),1) ;
   9:  CALL EXTLOG('HELLO',R[5:nBack]) ;
  10:  CALL EXTTWICE(R[5:nBack]) ;
  11:  R[5:nBack]=R[7:value]    ;
  12:  R[6:nAfter]=R[6:nAfter]+1    ;
/POS
/END
