/PROG  OPTARGPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "OptArgProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 24;
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
   1:  !RAPID OptArgProbe.OptArgProbe ;
   2:  R[7:nBefore]=1    ;
   3:  R[8:nCount]=5    ;
   4:  R[9:nKept]=7    ;
   5:  CALL STATION(3,1,200,1,1,0,'',1,R[8:nCount],0) ;
   6:  R[8:nCount]=R[1:Count]    ;
   7:  CALL STATION(4,0,0,1,0,0,'',0,0,1) ;
   8:  CALL STATION(5,0,0,0,0,1,'AB',0,0,0) ;
   9:  CALL STATION(6,0,0,0,0,0,'',0,0,0) ;
  10:  CALL RELAY(1,50) ;
  11:  CALL RELAY(0,0) ;
  12:  CALL INBAND(R[8:nCount],10,1,3,10) ;
  13:  IF (R[10:result]=1) THEN ;
  14:  R[11:nBand]=R[11:nBand]+1    ;
  15:  ENDIF ;
  16:  CALL INBAND(R[8:nCount],10,0,0,10) ;
  17:  IF (R[10:result]=1) THEN ;
  18:  R[11:nBand]=R[11:nBand]+10    ;
  19:  ENDIF ;
  20:  CALL INBAND(R[8:nCount],8,0,0,10) ;
  21:  IF (R[10:result]=1) THEN ;
  22:  R[11:nBand]=R[11:nBand]+100    ;
  23:  ENDIF ;
  24:  R[12:nAfter]=1    ;
/POS
/END
