/PROG  CFGPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CONFIG probe    ";
PROG_SIZE	= 1446;
CREATE		= DATE 26-09-18  TIME 13:33:06;
MODIFIED	= DATE 26-09-18  TIME 13:35:28;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 17;
MEMORY_SIZE	= 1750;
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
   1:  !CrossArm CONFIG probe ;
   2:J P[1] 10% FINE    ;
   3:J P[2] 10% FINE    ;
   4:J P[3] 10% FINE    ;
   5:J P[4] 10% FINE    ;
   6:J P[5] 10% FINE    ;
   7:J P[6] 10% FINE    ;
   8:J P[7] 10% FINE    ;
   9:J P[8] 10% FINE    ;
  10:J P[9] 10% FINE    ;
  11:J P[10] 10% FINE    ;
  12:J P[11] 10% FINE    ;
  13:J P[12] 10% FINE    ;
  14:J P[13] 10% FINE    ;
  15:J P[14] 10% FINE    ;
  16:J P[15] 10% FINE    ;
  17:J P[16] 10% FINE    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   965.000  mm,	Y =     0.000  mm,	Z =   965.000  mm,
	W =  -180.000 deg,	P =      .000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'F U T, 0, 0, 0',
	X =   965.000  mm,	Y =     0.000  mm,	Z =  1145.000  mm,
	W =     -.000 deg,	P =      .000 deg,	R =  -180.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1042.942  mm,	Y =     0.000  mm,	Z =  1010.000  mm,
	W =   180.000 deg,	P =   -60.000 deg,	R =     0.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'F U T, 0, 0, 0',
	X =  1042.942  mm,	Y =     0.000  mm,	Z =  1100.000  mm,
	W =     -.000 deg,	P =   -60.000 deg,	R =   180.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 1, 0',
	X =   965.000  mm,	Y =     7.844  mm,	Z =  1144.657  mm,
	W =    -5.000 deg,	P =     -.000 deg,	R =      .000 deg
};
P[6]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, -1, 0',
	X =   965.000  mm,	Y =    -7.844  mm,	Z =  1144.657  mm,
	W =     5.000 deg,	P =     -.000 deg,	R =     -.000 deg
};
P[7]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 1',
	X =   965.000  mm,	Y =     0.000  mm,	Z =   965.000  mm,
	W =   180.000 deg,	P =     -.000 deg,	R =  -170.000 deg
};
P[8]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, -1',
	X =   965.000  mm,	Y =     0.000  mm,	Z =   965.000  mm,
	W =  -180.000 deg,	P =     -.000 deg,	R =   170.000 deg
};
P[9]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 1',
	X =   965.000  mm,	Y =     0.000  mm,	Z =   965.000  mm,
	W =   180.000 deg,	P =      .000 deg,	R =   -10.000 deg
};
P[10]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N D T, 0, 0, 0',
	X =   951.688  mm,	Y =     0.000  mm,	Z =  1476.740  mm,
	W =   180.000 deg,	P =   -60.000 deg,	R =     0.000 deg
};
P[11]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1168.195  mm,	Y =     0.000  mm,	Z =   -64.785  mm,
	W =  -180.000 deg,	P =    60.000 deg,	R =     0.000 deg
};
P[12]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N D B, 0, 0, 0',
	X =  -374.813  mm,	Y =     0.000  mm,	Z =  -434.773  mm,
	W =  -180.000 deg,	P =    80.000 deg,	R =     0.000 deg
};
P[13]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U B, 0, 0, 0',
	X =  -621.015  mm,	Y =     0.000  mm,	Z =  1318.185  mm,
	W =   180.000 deg,	P =   -80.000 deg,	R =     0.000 deg
};
P[14]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N D T, 0, 0, 0',
	X =   833.907  mm,	Y =     0.000  mm,	Z =  1318.185  mm,
	W =   180.000 deg,	P =   -80.000 deg,	R =     0.000 deg
};
P[15]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     -.000  mm,	Y =   965.000  mm,	Z =   965.000  mm,
	W =  -180.000 deg,	P =      .000 deg,	R =    90.000 deg
};
P[16]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  -835.714  mm,	Y =  -482.500  mm,	Z =   965.000  mm,
	W =  -180.000 deg,	P =      .000 deg,	R =  -150.000 deg
};
/END
