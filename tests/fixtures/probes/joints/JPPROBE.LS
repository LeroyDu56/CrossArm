/PROG  JPPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "JpProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 70;
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
   1:  !RAPID JointProbe.JpProbe ;
   2:  R[1:jpA1]=0    ;
   3:  R[2:jpA2]=0    ;
   4:  R[3:jpA3]=0    ;
   5:  R[4:jpA4]=0    ;
   6:  R[5:jpA5]=0    ;
   7:  R[6:jpA6]=0    ;
   8:  R[7:jpB1]=0    ;
   9:  R[8:jpB2]=0    ;
  10:  R[9:jpB3]=0    ;
  11:  R[10:jpB4]=0    ;
  12:  R[11:jpB5]=0    ;
  13:  R[12:jpB6]=0    ;
  14:  R[13:jpBack1]=0    ;
  15:  R[14:jpBack2]=0    ;
  16:  R[15:jpBack3]=0    ;
  17:  R[16:jpBack4]=0    ;
  18:  R[17:jpBack5]=0    ;
  19:  R[18:jpBack6]=0    ;
  20:  R[19:jpHigh]=0    ;
  21:  R[20:jpLow]=0    ;
  22:  R[21:jpSum]=0    ;
  23:  UFRAME_NUM=0 ;
  24:  UTOOL_NUM=1 ;
  25:J P[1] 22% FINE    ;
  26:  PR[99]=JPOS    ;
  27:  R[1:jpA1]=PR[99,1]    ;
  28:  R[2:jpA2]=PR[99,2]    ;
  29:  R[22:Calc1]=PR[99,3]+PR[99,2]    ;
  30:  R[3:jpA3]=R[22:Calc1]*(-1)    ;
  31:  R[4:jpA4]=PR[99,4]*(-1)    ;
  32:  R[5:jpA5]=PR[99,5]*(-1)    ;
  33:  R[6:jpA6]=180-PR[99,6]    ;
  34:  PR[98]=PR[99]    ;
  35:  IF (PR[99,2]>(-30)) THEN ;
  36:  R[19:jpHigh]=1    ;
  37:  ENDIF ;
  38:  R[22:Calc1]=PR[99,3]+PR[99,2]    ;
  39:  R[22:Calc1]=R[22:Calc1]*(-1)    ;
  40:  IF (R[22:Calc1]>25) THEN ;
  41:  R[19:jpHigh]=R[19:jpHigh]+10    ;
  42:  ENDIF ;
  43:  R[22:Calc1]=PR[99,5]*(-1)    ;
  44:  F[1]=(R[22:Calc1]<(-40)) ;
  45:  IF (F[1]=ON) THEN ;
  46:  R[20:jpLow]=1    ;
  47:  ENDIF ;
  48:  R[22:Calc1]=PR[99,4]*(-1)    ;
  49:  R[23:Calc2]=180-PR[99,6]    ;
  50:  R[21:jpSum]=R[22:Calc1]+R[23:Calc2]    ;
  51:J P[2] 22% FINE    ;
  52:  PR[99]=JPOS    ;
  53:  R[7:jpB1]=PR[99,1]    ;
  54:  R[8:jpB2]=PR[99,2]    ;
  55:  R[22:Calc1]=PR[99,3]+PR[99,2]    ;
  56:  R[9:jpB3]=R[22:Calc1]*(-1)    ;
  57:  R[10:jpB4]=PR[99,4]*(-1)    ;
  58:  R[11:jpB5]=PR[99,5]*(-1)    ;
  59:  R[12:jpB6]=180-PR[99,6]    ;
  60:  UTOOL_NUM=2 ;
  61:J P[3] 22% FINE    ;
  62:J PR[98] 22% FINE    ;
  63:  PR[99]=JPOS    ;
  64:  R[13:jpBack1]=PR[99,1]    ;
  65:  R[14:jpBack2]=PR[99,2]    ;
  66:  R[22:Calc1]=PR[99,3]+PR[99,2]    ;
  67:  R[15:jpBack3]=R[22:Calc1]*(-1)    ;
  68:  R[16:jpBack4]=PR[99,4]*(-1)    ;
  69:  R[17:jpBack5]=PR[99,5]*(-1)    ;
  70:  R[18:jpBack6]=180-PR[99,6]    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,	
	J1=    10.000 deg,	J2=   -20.000 deg,	J3=   -10.000 deg,
	J4=   -40.000 deg,	J5=    50.000 deg,	J6=   120.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,	
	J1=   -30.000 deg,	J2=    15.000 deg,	J3=    -5.000 deg,
	J4=   100.000 deg,	J5=   -70.000 deg,	J6=   330.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 2,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=    90.000 deg,	J6=   180.000 deg
};
/END
