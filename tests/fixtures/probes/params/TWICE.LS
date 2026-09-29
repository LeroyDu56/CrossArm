/PROG  TWICE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Twice";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 5;
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
   1:  !RAPID ParamProbe.Twice ;
   2:  R[5:n]=AR[1]    ;
   3:  CALL BUMP(R[5:n],1) ;
   4:  R[5:n]=R[4:n]    ;
   5:  R[5:n]=R[5:n]+1    ;
/POS
/END
