/PROG  TURN
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Turn";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 45;
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
   2:  PR[94]=PR[97]    ;
   3:  PR[94,1]=0    ;
   4:  PR[94,2]=0    ;
   5:  PR[94,3]=(-30)    ;
   6:  PR[94,4]=0    ;
   7:  PR[94,5]=0    ;
   8:  PR[94,6]=0    ;
   9:  UFRAME_NUM=1 ;
  10:  UTOOL_NUM=1 ;
  11:L PR[97] 200mm/sec FINE Tool_Offset,PR[94]    ;
  12:  UFRAME_NUM=0 ;
  13:  UTOOL_NUM=9 ;
  14:  PR[R[90]]=LPOS    ;
  15:  R[90]=R[90]+1    ;
  16:  UFRAME_NUM=1 ;
  17:  UTOOL_NUM=1 ;
  18:  PR[94]=PR[97]    ;
  19:  PR[94,1]=10    ;
  20:  PR[94,2]=(-5)    ;
  21:  PR[94,3]=(-20)    ;
  22:  PR[94,4]=0    ;
  23:  PR[94,5]=0    ;
  24:  PR[94,6]=30    ;
  25:L PR[97] 200mm/sec FINE Tool_Offset,PR[94]    ;
  26:  UFRAME_NUM=0 ;
  27:  UTOOL_NUM=9 ;
  28:  PR[R[90]]=LPOS    ;
  29:  R[90]=R[90]+1    ;
  30:  UFRAME_NUM=1 ;
  31:  UTOOL_NUM=1 ;
  32:  PR[94]=PR[97]    ;
  33:  PR[94,1]=0    ;
  34:  PR[94,2]=0    ;
  35:  PR[94,3]=(-20)    ;
  36:  PR[94,4]=6.237    ;
  37:  PR[94,5]=(-7.817)    ;
  38:  PR[94,6]=14.153    ;
  39:J PR[97] 22% FINE Tool_Offset,PR[94]    ;
  40:  UFRAME_NUM=0 ;
  41:  UTOOL_NUM=9 ;
  42:  PR[R[90]]=LPOS    ;
  43:  R[90]=R[90]+1    ;
  44:  UFRAME_NUM=1 ;
  45:  UTOOL_NUM=1 ;
/POS
/END
