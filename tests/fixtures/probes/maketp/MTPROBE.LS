/PROG  MTPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "MtProbe";
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
   1:  !RAPID MakeTpProbe.MtProbe ;
   2:  R[1:mtSum]=0    ;
   3:  R[2:mtCalls]=0    ;
   4:  R[3:mtFlag]=0    ;
   5:  UFRAME_NUM=0 ;
   6:  UTOOL_NUM=1 ;
   7:J P[1] 22% FINE    ;
   8:  FOR R[4:i]=1 TO 5 ;
   9:  R[5:Calc2]=R[4:i]*2    ;
  10:  R[1:mtSum]=R[1:mtSum]+R[5:Calc2]    ;
  11:  CALL MTCOUNT    ;
  12:  ENDFOR ;
  13:  IF (R[1:mtSum]=30) THEN ;
  14:  R[3:mtFlag]=100    ;
  15:  ENDIF ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=    90.000 deg,	J6=   180.000 deg
};
/END
