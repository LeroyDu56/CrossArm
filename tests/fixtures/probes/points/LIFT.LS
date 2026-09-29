/PROG  LIFT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "Lift";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 19;
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
   2:  PR[95]=PR[96]    ;
   3:  PR[95,1]=0    ;
   4:  PR[95,2]=0    ;
   5:  PR[95,3]=AR[1]*(-1)    ;
   6:  PR[95,4]=0    ;
   7:  PR[95,5]=0    ;
   8:  PR[95,6]=0    ;
   9:  UFRAME_NUM=1 ;
  10:  UTOOL_NUM=1 ;
  11:L PR[96] 200mm/sec FINE Tool_Offset,PR[95]    ;
  12:  PR[R[90]]=LPOS    ;
  13:  R[90]=R[90]+1    ;
  14:  PR[94]=PR[96]    ;
  15:  PR[94,1]=PR[94,1]+5    ;
  16:  PR[94,3]=PR[94,3]-AR[1]    ;
  17:L PR[94] 200mm/sec FINE    ;
  18:  PR[R[90]]=LPOS    ;
  19:  R[90]=R[90]+1    ;
/POS
/END
