/PROG  COUNTDOWN
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CountDown       ";
PROG_SIZE	= 404;
CREATE		= DATE 26-09-18  TIME 12:13:30;
MODIFIED	= DATE 26-09-18  TIME 12:13:30;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 13;
MEMORY_SIZE	= 724;
PROTECT		= READ_WRITE;
TCD:  STACK_SIZE	= 0,
      TASK_PRIORITY	= 50,
      TIME_SLICE	= 0,
      BUSY_LAMP_OFF	= 0,
      ABORT_REQUEST	= 0,
      PAUSE_REQUEST	= 0;
DEFAULT_GROUP	= 1,*,*,*,*;
CONTROL_CODE	= 00000000 00000000;
LOCAL_REGISTERS	= 0,0,0;
/MN
   1:  !RAPID LogicAndIo.CountDown ;
   2:  FOR R[5:k]=3 DOWNTO 1 ;
   3:  R[6:nLayer]=R[5:k]    ;
   4:  WAIT    .50(sec) ;
   5:  ENDFOR ;
   6:  WAIT (DI[1]=OFF OR R[6:nLayer]<>0)    ;
   7:  IF (DI[3]=ON) THEN ;
   8:  ABORT ;
   9:  ENDIF ;
  10:  IF (R[6:nLayer]>2) THEN ;
  11:  END ;
  12:  ENDIF ;
  13:  WAIT   1.50(sec) ;
/POS
/END
