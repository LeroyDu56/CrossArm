/PROG  COUNTDOWN
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CountDown";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 15;
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
   3:  !RAPID LogicAndIo.CountDown ;
   4:  FOR R[5:k]=3 DOWNTO 1 ;
   5:  R[6:nLayer]=R[5:k]    ;
   6:  WAIT    .50(sec) ;
   7:  ENDFOR ;
   8:  WAIT (DI[1]=OFF OR R[6:nLayer]<>0)    ;
   9:  IF (DI[3]=ON) THEN ;
  10:  ABORT ;
  11:  ENDIF ;
  12:  IF (R[6:nLayer]>2) THEN ;
  13:  END ;
  14:  ENDIF ;
  15:  WAIT   1.50(sec) ;
/POS
/END
