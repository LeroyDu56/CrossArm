/PROG  POINTDIRECT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "PointDirect";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 39;
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
   1:  !RAPID PointProbe.PointDirect ;
   2:  UFRAME_NUM=1 ;
   3:  UTOOL_NUM=1 ;
   4:J P[1] 22% FINE    ;
   5:  PR[R[90]]=LPOS ;
   6:  R[90]=R[90]+1    ;
   7:L P[2] 200mm/sec FINE    ;
   8:  PR[R[90]]=LPOS ;
   9:  R[90]=R[90]+1    ;
  10:L P[3] 1000mm/sec FINE    ;
  11:  PR[R[90]]=LPOS ;
  12:  R[90]=R[90]+1    ;
  13:J P[4] 22% FINE    ;
  14:  PR[R[90]]=LPOS ;
  15:  R[90]=R[90]+1    ;
  16:L P[5] 200mm/sec FINE    ;
  17:  PR[R[90]]=LPOS ;
  18:  R[90]=R[90]+1    ;
  19:L P[6] 1000mm/sec FINE    ;
  20:  PR[R[90]]=LPOS ;
  21:  R[90]=R[90]+1    ;
  22:J P[7] 22% FINE    ;
  23:  PR[R[90]]=LPOS ;
  24:  R[90]=R[90]+1    ;
  25:L P[8] 200mm/sec FINE    ;
  26:  PR[R[90]]=LPOS ;
  27:  R[90]=R[90]+1    ;
  28:L P[9] 1000mm/sec FINE    ;
  29:  PR[R[90]]=LPOS ;
  30:  R[90]=R[90]+1    ;
  31:J P[10] 22% FINE    ;
  32:  PR[R[90]]=LPOS ;
  33:  R[90]=R[90]+1    ;
  34:L P[11] 200mm/sec FINE    ;
  35:  PR[R[90]]=LPOS ;
  36:  R[90]=R[90]+1    ;
  37:L P[12] 1000mm/sec FINE    ;
  38:  PR[R[90]]=LPOS ;
  39:  R[90]=R[90]+1    ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    60.000  mm,	Y =    20.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    60.000  mm,	Y =    20.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    70.000  mm,	Y =     0.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[4]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   170.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[5]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   170.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[6]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   190.000  mm,	Y =   150.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[7]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   120.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[8]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   120.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[9]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   190.000  mm,	Y =   100.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[10]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   210.000  mm,	Y =   120.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[11]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   210.000  mm,	Y =   120.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[12]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   220.000  mm,	Y =   100.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
