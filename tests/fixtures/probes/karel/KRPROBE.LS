/PROG  KRPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "KrProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 25;
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
   1:  !RAPID KarelProbe.KrProbe ;
   2:  R[1:krDone]=0    ;
   3:  R[2:krX]=100    ;
   4:  R[3:krY]=10    ;
   5:  PR[99,1]=100    ;
   6:  PR[99,2]=(-50)    ;
   7:  PR[99,3]=300    ;
   8:  PR[99,4]=30    ;
   9:  PR[99,5]=(-20)    ;
  10:  PR[99,6]=45    ;
  11:  PR[98,1]=10    ;
  12:  PR[98,2]=20    ;
  13:  PR[98,3]=30    ;
  14:  PR[98,4]=10    ;
  15:  PR[98,5]=40    ;
  16:  PR[98,6]=(-60)    ;
  17:  CALL CA_POSEMULT(99,98,97) ;
  18:  PR[95,1]=0    ;
  19:  PR[95,2]=0    ;
  20:  PR[95,3]=10    ;
  21:  PR[95,4]=0    ;
  22:  PR[95,5]=0    ;
  23:  PR[95,6]=90    ;
  24:  CALL CA_POSEMULT(97,95,96) ;
  25:  R[1:krDone]=1    ;
/POS
/END
