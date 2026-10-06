/PROG  SPDPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "SpdProbe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 36;
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
   1:  !RAPID SpeedArgProbe.SpdProbe ;
   2:  R[5:nCalls]=0    ;
   3:  UFRAME_NUM=0 ;
   4:  UTOOL_NUM=1 ;
   5:J P[1] 22% FINE    ;
   6:  TIMER[1]=RESET ;
   7:  TIMER[1]=START ;
   8:  CALL SPDMOVES(400,9,100,100) ;
   9:  TIMER[1]=STOP ;
  10:  R[6:nT1]=TIMER[1]    ;
  11:  UFRAME_NUM=0 ;
  12:  UTOOL_NUM=1 ;
  13:J P[1] 22% FINE    ;
  14:  TIMER[1]=RESET ;
  15:  TIMER[1]=START ;
  16:  CALL SPDMOVES(200,4,100,97) ;
  17:  TIMER[1]=STOP ;
  18:  R[7:nT2]=TIMER[1]    ;
  19:  UFRAME_NUM=0 ;
  20:  UTOOL_NUM=1 ;
  21:J P[1] 22% FINE    ;
  22:  TIMER[1]=RESET ;
  23:  TIMER[1]=START ;
  24:J P[2] 9% CNT100    ;
  25:L P[3] 400mm/sec CNT100    ;
  26:L P[4] 400mm/sec FINE    ;
  27:  TIMER[1]=STOP ;
  28:  R[8:nT3]=TIMER[1]    ;
  29:J P[1] 22% FINE    ;
  30:  TIMER[1]=RESET ;
  31:  TIMER[1]=START ;
  32:J P[2] 4% CNT100    ;
  33:L P[3] 200mm/sec CNT97    ;
  34:L P[4] 200mm/sec FINE    ;
  35:  TIMER[1]=STOP ;
  36:  R[9:nT4]=TIMER[1]    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=    90.000 deg,	J6=   180.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =    50.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =   250.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =   250.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
