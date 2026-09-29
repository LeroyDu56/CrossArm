/PROG  POINTDIRECT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "PointDirect";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 114;
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
   5:  PR[R[90]]=LPOS    ;
   6:  R[90]=R[90]+1    ;
   7:L P[2] 200mm/sec FINE    ;
   8:  PR[R[90]]=LPOS    ;
   9:  R[90]=R[90]+1    ;
  10:L P[3] 1000mm/sec FINE    ;
  11:  PR[R[90]]=LPOS    ;
  12:  R[90]=R[90]+1    ;
  13:J P[4] 22% FINE    ;
  14:  PR[R[90]]=LPOS    ;
  15:  R[90]=R[90]+1    ;
  16:L P[5] 200mm/sec FINE    ;
  17:  PR[R[90]]=LPOS    ;
  18:  R[90]=R[90]+1    ;
  19:L P[6] 1000mm/sec FINE    ;
  20:  PR[R[90]]=LPOS    ;
  21:  R[90]=R[90]+1    ;
  22:J P[7] 22% FINE    ;
  23:  PR[R[90]]=LPOS    ;
  24:  R[90]=R[90]+1    ;
  25:L P[8] 200mm/sec FINE    ;
  26:  PR[R[90]]=LPOS    ;
  27:  R[90]=R[90]+1    ;
  28:L P[9] 1000mm/sec FINE    ;
  29:  PR[R[90]]=LPOS    ;
  30:  R[90]=R[90]+1    ;
  31:J P[10] 22% FINE    ;
  32:  PR[R[90]]=LPOS    ;
  33:  R[90]=R[90]+1    ;
  34:L P[11] 200mm/sec FINE    ;
  35:  PR[R[90]]=LPOS    ;
  36:  R[90]=R[90]+1    ;
  37:L P[12] 1000mm/sec FINE    ;
  38:  PR[R[90]]=LPOS    ;
  39:  R[90]=R[90]+1    ;
  40:L P[13] 200mm/sec FINE    ;
  41:  PR[R[90]]=LPOS    ;
  42:  R[90]=R[90]+1    ;
  43:L P[14] 200mm/sec FINE    ;
  44:  PR[R[90]]=LPOS    ;
  45:  R[90]=R[90]+1    ;
  46:J P[15] 22% FINE    ;
  47:  PR[R[90]]=LPOS    ;
  48:  R[90]=R[90]+1    ;
  49:L P[16] 200mm/sec FINE    ;
  50:  PR[R[90]]=LPOS    ;
  51:  R[90]=R[90]+1    ;
  52:L P[17] 200mm/sec FINE    ;
  53:  PR[R[90]]=LPOS    ;
  54:  R[90]=R[90]+1    ;
  55:L P[18] 500mm/sec FINE    ;
  56:  PR[R[90]]=LPOS    ;
  57:  R[90]=R[90]+1    ;
  58:J P[19] 22% FINE    ;
  59:  PR[R[90]]=LPOS    ;
  60:  R[90]=R[90]+1    ;
  61:L P[20] 200mm/sec FINE    ;
  62:  PR[R[90]]=LPOS    ;
  63:  R[90]=R[90]+1    ;
  64:L P[21] 1000mm/sec FINE    ;
  65:  PR[R[90]]=LPOS    ;
  66:  R[90]=R[90]+1    ;
  67:L P[22] 500mm/sec FINE    ;
  68:  PR[R[90]]=LPOS    ;
  69:  R[90]=R[90]+1    ;
  70:L P[23] 500mm/sec FINE    ;
  71:  PR[R[90]]=LPOS    ;
  72:  R[90]=R[90]+1    ;
  73:J P[24] 22% FINE    ;
  74:  PR[R[90]]=LPOS    ;
  75:  R[90]=R[90]+1    ;
  76:L P[25] 200mm/sec FINE    ;
  77:  PR[R[90]]=LPOS    ;
  78:  R[90]=R[90]+1    ;
  79:L P[26] 1000mm/sec FINE    ;
  80:  PR[R[90]]=LPOS    ;
  81:  R[90]=R[90]+1    ;
  82:L P[27] 500mm/sec FINE    ;
  83:  PR[R[90]]=LPOS    ;
  84:  R[90]=R[90]+1    ;
  85:L P[28] 500mm/sec FINE    ;
  86:  PR[R[90]]=LPOS    ;
  87:  R[90]=R[90]+1    ;
  88:J P[29] 22% FINE    ;
  89:  PR[R[90]]=LPOS    ;
  90:  R[90]=R[90]+1    ;
  91:L P[30] 200mm/sec FINE    ;
  92:  PR[R[90]]=LPOS    ;
  93:  R[90]=R[90]+1    ;
  94:L P[31] 1000mm/sec FINE    ;
  95:  PR[R[90]]=LPOS    ;
  96:  R[90]=R[90]+1    ;
  97:L P[32] 500mm/sec FINE    ;
  98:  PR[R[90]]=LPOS    ;
  99:  R[90]=R[90]+1    ;
 100:L P[33] 500mm/sec FINE    ;
 101:  PR[R[90]]=LPOS    ;
 102:  R[90]=R[90]+1    ;
 103:J P[34] 22% FINE    ;
 104:  PR[R[90]]=LPOS    ;
 105:  R[90]=R[90]+1    ;
 106:L P[35] 200mm/sec FINE    ;
 107:  PR[R[90]]=LPOS    ;
 108:  R[90]=R[90]+1    ;
 109:L P[36] 1000mm/sec FINE    ;
 110:  PR[R[90]]=LPOS    ;
 111:  R[90]=R[90]+1    ;
 112:L P[37] 500mm/sec FINE    ;
 113:  PR[R[90]]=LPOS    ;
 114:  R[90]=R[90]+1    ;
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
	X =    60.000  mm,	Y =    20.000  mm,	Z =   280.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[14]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    70.000  mm,	Y =    25.000  mm,	Z =   270.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -30.000 deg
};
P[15]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    60.000  mm,	Y =    20.000  mm,	Z =   270.000  mm,
	W =  -173.763 deg,	P =     7.817 deg,	R =   -14.153 deg
};
P[16]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   180.000  mm,	Y =   120.000  mm,	Z =   275.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[17]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   185.000  mm,	Y =   120.000  mm,	Z =   225.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[18]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[19]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[20]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[21]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    50.000  mm,	Y =   -60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[22]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    45.000  mm,	Y =   -40.000  mm,	Z =   245.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -20.000 deg
};
P[23]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =   -40.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[24]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =   -40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[25]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =   -40.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[26]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   110.000  mm,	Y =   -60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[27]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   105.000  mm,	Y =   -40.000  mm,	Z =   245.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -20.000 deg
};
P[28]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    60.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[29]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[30]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    60.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[31]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    50.000  mm,	Y =    40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[32]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    45.000  mm,	Y =    60.000  mm,	Z =   245.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -20.000 deg
};
P[33]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    60.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[34]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    60.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[35]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    60.000  mm,	Z =   250.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[36]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   110.000  mm,	Y =    40.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[37]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   105.000  mm,	Y =    60.000  mm,	Z =   245.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -20.000 deg
};
/END
