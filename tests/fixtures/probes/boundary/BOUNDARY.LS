/PROG  BOUNDARY
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "J6 boundary";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 43;
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
   1:  PR[20]=P[9]    ;
   2:  UTOOL[1]=PR[20] ;
   3:  PR[20]=P[10]    ;
   4:  UTOOL[2]=PR[20] ;
   5:  UFRAME_NUM=0 ;
   6:  UTOOL_NUM=1 ;
   7:  !pAhead ;
   8:  UTOOL_NUM=1 ;
   9:J P[8] 30% FINE    ;
  10:  UTOOL_NUM=1 ;
  11:J P[1] 11% FINE    ;
  12:  UTOOL_NUM=2 ;
  13:  !pAheadTool ;
  14:  UTOOL_NUM=1 ;
  15:J P[8] 30% FINE    ;
  16:  UTOOL_NUM=2 ;
  17:J P[2] 11% FINE    ;
  18:  UTOOL_NUM=1 ;
  19:  !pAheadHigh ;
  20:  UTOOL_NUM=1 ;
  21:J P[8] 30% FINE    ;
  22:  UTOOL_NUM=1 ;
  23:J P[3] 11% FINE    ;
  24:  !pTurned ;
  25:  UTOOL_NUM=1 ;
  26:J P[8] 30% FINE    ;
  27:  UTOOL_NUM=1 ;
  28:J P[4] 11% FINE    ;
  29:  !pTurnedBack ;
  30:  UTOOL_NUM=1 ;
  31:J P[8] 30% FINE    ;
  32:  UTOOL_NUM=1 ;
  33:J P[5] 11% FINE    ;
  34:  !pAside ;
  35:  UTOOL_NUM=1 ;
  36:J P[8] 30% FINE    ;
  37:  UTOOL_NUM=1 ;
  38:J P[6] 11% FINE    ;
  39:  !pSide45 ;
  40:  UTOOL_NUM=1 ;
  41:J P[8] 30% FINE    ;
  42:  UTOOL_NUM=1 ;
  43:J P[7] 11% FINE    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 1',
	X =  1300.000  mm,	Y =     0.000  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 1',
	X =  1300.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 1',
	X =  1100.000  mm,	Y =     0.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 1',
	X =  1300.000  mm,	Y =     0.000  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -179.900 deg
};
P[5]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1300.000  mm,	Y =     0.000  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   179.900 deg
};
P[6]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 1',
	X =  1126.333  mm,	Y =   650.000  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -150.000 deg
};
P[7]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 1',
	X =  1300.000  mm,	Y =  -300.000  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -135.000 deg
};
P[8]{
   GP1:
	UF : 0, UT : 1,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
P[9]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[10]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   200.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
