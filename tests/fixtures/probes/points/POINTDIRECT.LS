/PROG  POINTDIRECT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "PointDirect";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 87;
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
  40:L P[13] 500mm/sec FINE    ;
  41:  PR[R[90]]=LPOS ;
  42:  R[90]=R[90]+1    ;
  43:J P[14] 22% FINE    ;
  44:  PR[R[90]]=LPOS ;
  45:  R[90]=R[90]+1    ;
  46:L P[15] 200mm/sec FINE    ;
  47:  PR[R[90]]=LPOS ;
  48:  R[90]=R[90]+1    ;
  49:L P[16] 1000mm/sec FINE    ;
  50:  PR[R[90]]=LPOS ;
  51:  R[90]=R[90]+1    ;
  52:L P[17] 500mm/sec FINE    ;
  53:  PR[R[90]]=LPOS ;
  54:  R[90]=R[90]+1    ;
  55:J P[18] 22% FINE    ;
  56:  PR[R[90]]=LPOS ;
  57:  R[90]=R[90]+1    ;
  58:L P[19] 200mm/sec FINE    ;
  59:  PR[R[90]]=LPOS ;
  60:  R[90]=R[90]+1    ;
  61:L P[20] 1000mm/sec FINE    ;
  62:  PR[R[90]]=LPOS ;
  63:  R[90]=R[90]+1    ;
  64:L P[21] 500mm/sec FINE    ;
  65:  PR[R[90]]=LPOS ;
  66:  R[90]=R[90]+1    ;
  67:J P[22] 22% FINE    ;
  68:  PR[R[90]]=LPOS ;
  69:  R[90]=R[90]+1    ;
  70:L P[23] 200mm/sec FINE    ;
  71:  PR[R[90]]=LPOS ;
  72:  R[90]=R[90]+1    ;
  73:L P[24] 1000mm/sec FINE    ;
  74:  PR[R[90]]=LPOS ;
  75:  R[90]=R[90]+1    ;
  76:L P[25] 500mm/sec FINE    ;
  77:  PR[R[90]]=LPOS ;
  78:  R[90]=R[90]+1    ;
  79:J P[26] 22% FINE    ;
  80:  PR[R[90]]=LPOS ;
  81:  R[90]=R[90]+1    ;
  82:L P[27] 200mm/sec FINE    ;
  83:  PR[R[90]]=LPOS ;
  84:  R[90]=R[90]+1    ;
  85:L P[28] 1000mm/sec FINE    ;
  86:  PR[R[90]]=LPOS ;
  87:  R[90]=R[90]+1    ;
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
P[13]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[14]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[15]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[16]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    50.000  mm,	Y =   -60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[17]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =   -40.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[18]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =   -40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[19]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =   -40.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[20]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   110.000  mm,	Y =   -60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[21]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    60.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[22]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[23]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    60.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[24]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    50.000  mm,	Y =    40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[25]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    60.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[26]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[27]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    60.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[28]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   110.000  mm,	Y =    40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
