/PROG  PTPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "point probe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 23;
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
   1:  !CrossArm point probe ;
   2:  PR[100]=P[1]    ;
   3:  UTOOL[1]=PR[100] ;
   4:  PR[100]=P[2]    ;
   5:  UTOOL[2]=PR[100] ;
   6:  PR[100]=P[3]    ;
   7:  UFRAME[1]=PR[100] ;
   8:  PR[100]=P[4]    ;
   9:  UFRAME[2]=PR[100] ;
  10:  PR[89]=P[5]    ;
  11:  PR[90]=P[6]    ;
  12:  PR[91]=P[7]    ;
  13:  PR[92]=P[8]    ;
  14:  PR[88]=P[9]    ;
  15:  PR[49]=P[10]    ;
  16:  UTOOL[9]=PR[49] ;
  17:  UFRAME_NUM=0 ;
  18:  UTOOL_NUM=9 ;
  19:J P[11] 10% FINE    ;
  20:  R[90]=1    ;
  21:  CALL POINTPROBE    ;
  22:  R[90]=45    ;
  23:  CALL POINTDIRECT    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    10.000  mm,	Y =    -5.000  mm,	Z =   120.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    25.000  mm,	Y =    10.000  mm,	Z =   140.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =    15.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =  -150.000  mm,	Z =   650.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =    10.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1150.000  mm,	Y =  -100.000  mm,	Z =   600.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =   -10.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[6]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =   -40.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[7]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    60.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[8]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    60.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[9]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   120.000  mm,	Y =    40.000  mm,	Z =   240.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[10]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[11]{
   GP1:
	UF : 0, UT : 9,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
/END
