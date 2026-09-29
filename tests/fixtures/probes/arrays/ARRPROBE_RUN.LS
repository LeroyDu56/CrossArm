/PROG  ARRPROBE_RUN
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "array probe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 20;
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
   1:  !CrossArm: tool and user frames ;
   2:  !of the ABB backup ;
   3:  !PR[100] is overwritten ;
   4:  !FEED: R[197] to R[200] ;
   5:  R[197]=1.5    ;
   6:  R[198]=(-2)    ;
   7:  R[199]=.25    ;
   8:  R[200]=10    ;
   9:  !GRID: R[191] to R[196] ;
  10:  R[191]=1    ;
  11:  R[192]=2    ;
  12:  R[193]=3    ;
  13:  R[194]=40    ;
  14:  R[195]=50    ;
  15:  R[196]=60    ;
  16:  !LIMIT: R[188] to R[190] ;
  17:  R[188]=5    ;
  18:  R[189]=(-5)    ;
  19:  R[190]=100    ;
  20:  CALL ARRPROBE    ;
/POS
/END
