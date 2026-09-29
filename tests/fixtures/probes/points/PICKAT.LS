/PROG  PICKAT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "PickAt";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 18;
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
   1:  !RAPID PointProbe.PickAt ;
   2:  PR[94]=PR[99]    ;
   3:  PR[94,3]=PR[94,3]+40    ;
   4:  UFRAME_NUM=1 ;
   5:  UTOOL_NUM=1 ;
   6:J PR[94] 22% FINE    ;
   7:  PR[R[90]]=LPOS    ;
   8:  R[90]=R[90]+1    ;
   9:L PR[99] 200mm/sec FINE    ;
  10:  PR[R[90]]=LPOS    ;
  11:  R[90]=R[90]+1    ;
  12:  PR[94]=PR[99]    ;
  13:  PR[94,1]=PR[94,1]+10    ;
  14:  PR[94,2]=PR[94,2]+(-20)    ;
  15:  PR[94,3]=PR[94,3]+40    ;
  16:L PR[94] 1000mm/sec FINE    ;
  17:  PR[R[90]]=LPOS    ;
  18:  R[90]=R[90]+1    ;
/POS
/END
