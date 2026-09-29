/PROG  LIFT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Lift";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 27;
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
   1:  !RAPID PointProbe.Lift ;
   2:  PR[94]=PR[96]    ;
   3:  PR[94,1]=0    ;
   4:  PR[94,2]=0    ;
   5:  PR[94,3]=AR[1]*(-1)    ;
   6:  PR[94,4]=0    ;
   7:  PR[94,5]=0    ;
   8:  PR[94,6]=0    ;
   9:  UFRAME_NUM=1 ;
  10:  UTOOL_NUM=1 ;
  11:L PR[96] 200mm/sec FINE Tool_Offset,PR[94]    ;
  12:  UFRAME_NUM=0 ;
  13:  UTOOL_NUM=9 ;
  14:  PR[R[90]]=LPOS    ;
  15:  R[90]=R[90]+1    ;
  16:  UFRAME_NUM=1 ;
  17:  UTOOL_NUM=1 ;
  18:  PR[93]=PR[96]    ;
  19:  PR[93,1]=PR[93,1]+5    ;
  20:  PR[93,3]=PR[93,3]-AR[1]    ;
  21:L PR[93] 200mm/sec FINE    ;
  22:  UFRAME_NUM=0 ;
  23:  UTOOL_NUM=9 ;
  24:  PR[R[90]]=LPOS    ;
  25:  R[90]=R[90]+1    ;
  26:  UFRAME_NUM=1 ;
  27:  UTOOL_NUM=1 ;
/POS
/END
