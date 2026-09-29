/PROG  TURN
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Turn";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 33;
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
   1:  !RAPID PointProbe.Turn ;
   2:  PR[95]=PR[97]    ;
   3:  PR[95,1]=0    ;
   4:  PR[95,2]=0    ;
   5:  PR[95,3]=(-30)    ;
   6:  PR[95,4]=0    ;
   7:  PR[95,5]=0    ;
   8:  PR[95,6]=0    ;
   9:  UFRAME_NUM=1 ;
  10:  UTOOL_NUM=1 ;
  11:L PR[97] 200mm/sec FINE Tool_Offset,PR[95]    ;
  12:  PR[R[90]]=LPOS    ;
  13:  R[90]=R[90]+1    ;
  14:  PR[95]=PR[97]    ;
  15:  PR[95,1]=10    ;
  16:  PR[95,2]=(-5)    ;
  17:  PR[95,3]=(-20)    ;
  18:  PR[95,4]=0    ;
  19:  PR[95,5]=0    ;
  20:  PR[95,6]=30    ;
  21:L PR[97] 200mm/sec FINE Tool_Offset,PR[95]    ;
  22:  PR[R[90]]=LPOS    ;
  23:  R[90]=R[90]+1    ;
  24:  PR[95]=PR[97]    ;
  25:  PR[95,1]=0    ;
  26:  PR[95,2]=0    ;
  27:  PR[95,3]=(-20)    ;
  28:  PR[95,4]=6.237    ;
  29:  PR[95,5]=(-7.817)    ;
  30:  PR[95,6]=14.153    ;
  31:J PR[97] 22% FINE Tool_Offset,PR[95]    ;
  32:  PR[R[90]]=LPOS    ;
  33:  R[90]=R[90]+1    ;
/POS
/END
