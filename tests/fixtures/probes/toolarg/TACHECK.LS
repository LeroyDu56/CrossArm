/PROG  TACHECK
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "TaCheck";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 14;
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
   1:  !CrossArm EVALUATION copy ;
   2:  !production use needs a licence ;
   3:  !RAPID ToolArgProbe.TaCheck ;
   4:  R[4:bOk]=AR[2]    ;
   5:  IF (AR[3]=1) THEN ;
   6:  UFRAME_NUM=0 ;
   7:  UTOOL_NUM=1 ;
   8:L PR[96] 500mm/sec FINE    ;
   9:  ENDIF ;
  10:  IF (AR[1]<500) THEN ;
  11:  R[4:bOk]=1    ;
  12:  ELSE ;
  13:  R[4:bOk]=0    ;
  14:  ENDIF ;
/POS
/END
