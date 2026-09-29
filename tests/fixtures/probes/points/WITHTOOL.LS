/PROG  WITHTOOL
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "WithTool";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 26;
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
   1:  !RAPID PointProbe.WithTool ;
   2:  PR[93]=PR[95]    ;
   3:  PR[93,3]=PR[93,3]+40    ;
   4:  UFRAME_NUM=AR[2] ;
   5:  UTOOL_NUM=AR[1] ;
   6:J PR[93] 22% FINE    ;
   7:  UFRAME_NUM=0 ;
   8:  UTOOL_NUM=9 ;
   9:  PR[R[90]]=LPOS    ;
  10:  R[90]=R[90]+1    ;
  11:  UFRAME_NUM=AR[2] ;
  12:  UTOOL_NUM=AR[1] ;
  13:L PR[95] 200mm/sec FINE    ;
  14:  UFRAME_NUM=0 ;
  15:  UTOOL_NUM=9 ;
  16:  PR[R[90]]=LPOS    ;
  17:  R[90]=R[90]+1    ;
  18:  UFRAME_NUM=AR[2] ;
  19:  UTOOL_NUM=AR[1] ;
  20:L PR[88] 200mm/sec FINE    ;
  21:  UFRAME_NUM=0 ;
  22:  UTOOL_NUM=9 ;
  23:  PR[R[90]]=LPOS    ;
  24:  R[90]=R[90]+1    ;
  25:  UFRAME_NUM=AR[2] ;
  26:  UTOOL_NUM=AR[1] ;
/POS
/END
