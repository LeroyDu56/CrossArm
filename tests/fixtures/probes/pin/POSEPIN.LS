/PROG  POSEPIN
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "pose probe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 148;
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
   1:  !CrossArm pose probe ;
   2:  !load the frames ;
   3:  PR[21]=P[17]    ;
   4:  UTOOL[1]=PR[21] ;
   5:  PR[22]=P[18]    ;
   6:  UTOOL[2]=PR[22] ;
   7:  PR[23]=P[19]    ;
   8:  UTOOL[3]=PR[23] ;
   9:  PR[29]=P[20]    ;
  10:  UTOOL[9]=PR[29] ;
  11:  PR[26]=P[21]    ;
  12:  UFRAME[1]=PR[26] ;
  13:  PR[27]=P[22]    ;
  14:  UFRAME[2]=PR[27] ;
  15:  !known start ;
  16:  UFRAME_NUM=0 ;
  17:  UTOOL_NUM=9 ;
  18:J P[23] 10% FINE    ;
  19:  PR[50]=LPOS    ;
  20:  PR[70]=JPOS    ;
  21:  !move 1 ;
  22:  UFRAME_NUM=0 ;
  23:  UTOOL_NUM=1 ;
  24:J P[1] 4% FINE    ;
  25:  UFRAME_NUM=0 ;
  26:  UTOOL_NUM=9 ;
  27:  PR[51]=LPOS    ;
  28:  PR[71]=JPOS    ;
  29:  !move 2 ;
  30:  UFRAME_NUM=0 ;
  31:  UTOOL_NUM=2 ;
  32:J P[2] 4% FINE    ;
  33:  UFRAME_NUM=0 ;
  34:  UTOOL_NUM=9 ;
  35:  PR[52]=LPOS    ;
  36:  PR[72]=JPOS    ;
  37:  !move 3 ;
  38:  UFRAME_NUM=1 ;
  39:  UTOOL_NUM=1 ;
  40:J P[3] 4% FINE    ;
  41:  UFRAME_NUM=0 ;
  42:  UTOOL_NUM=9 ;
  43:  PR[53]=LPOS    ;
  44:  PR[73]=JPOS    ;
  45:  !move 4 ;
  46:  UFRAME_NUM=1 ;
  47:  UTOOL_NUM=3 ;
  48:J P[4] 4% FINE    ;
  49:  UFRAME_NUM=0 ;
  50:  UTOOL_NUM=9 ;
  51:  PR[54]=LPOS    ;
  52:  PR[74]=JPOS    ;
  53:  !move 5 ;
  54:  UFRAME_NUM=2 ;
  55:  UTOOL_NUM=2 ;
  56:J P[5] 4% FINE    ;
  57:  UFRAME_NUM=0 ;
  58:  UTOOL_NUM=9 ;
  59:  PR[55]=LPOS    ;
  60:  PR[75]=JPOS    ;
  61:  !move 6 ;
  62:  UFRAME_NUM=2 ;
  63:  UTOOL_NUM=3 ;
  64:J P[6] 4% FINE    ;
  65:  UFRAME_NUM=0 ;
  66:  UTOOL_NUM=9 ;
  67:  PR[56]=LPOS    ;
  68:  PR[76]=JPOS    ;
  69:  !move 7 ;
  70:  UFRAME_NUM=1 ;
  71:  UTOOL_NUM=2 ;
  72:J P[7] 4% FINE    ;
  73:  UFRAME_NUM=0 ;
  74:  UTOOL_NUM=9 ;
  75:  PR[57]=LPOS    ;
  76:  PR[77]=JPOS    ;
  77:  !move 8 ;
  78:  UFRAME_NUM=2 ;
  79:  UTOOL_NUM=1 ;
  80:J P[8] 4% FINE    ;
  81:  UFRAME_NUM=0 ;
  82:  UTOOL_NUM=9 ;
  83:  PR[58]=LPOS    ;
  84:  PR[78]=JPOS    ;
  85:  !move 9 ;
  86:  UFRAME_NUM=1 ;
  87:  UTOOL_NUM=1 ;
  88:J P[9] 4% FINE    ;
  89:  UFRAME_NUM=0 ;
  90:  UTOOL_NUM=9 ;
  91:  PR[59]=LPOS    ;
  92:  PR[79]=JPOS    ;
  93:  !move 10 ;
  94:  UFRAME_NUM=2 ;
  95:  UTOOL_NUM=2 ;
  96:J P[10] 4% FINE    ;
  97:  UFRAME_NUM=0 ;
  98:  UTOOL_NUM=9 ;
  99:  PR[60]=LPOS    ;
 100:  PR[80]=JPOS    ;
 101:  !move 11 ;
 102:  UFRAME_NUM=2 ;
 103:  UTOOL_NUM=2 ;
 104:J P[11] 4% FINE    ;
 105:  UFRAME_NUM=0 ;
 106:  UTOOL_NUM=9 ;
 107:  PR[61]=LPOS    ;
 108:  PR[81]=JPOS    ;
 109:  !move 12 ;
 110:  UFRAME_NUM=2 ;
 111:  UTOOL_NUM=3 ;
 112:J P[12] 4% FINE    ;
 113:  UFRAME_NUM=0 ;
 114:  UTOOL_NUM=9 ;
 115:  PR[62]=LPOS    ;
 116:  PR[82]=JPOS    ;
 117:  !move 13 ;
 118:  UFRAME_NUM=0 ;
 119:  UTOOL_NUM=2 ;
 120:J P[13] 4% FINE    ;
 121:  UFRAME_NUM=0 ;
 122:  UTOOL_NUM=9 ;
 123:  PR[63]=LPOS    ;
 124:  PR[83]=JPOS    ;
 125:  !move 14 ;
 126:  UFRAME_NUM=1 ;
 127:  UTOOL_NUM=3 ;
 128:J P[14] 4% FINE    ;
 129:  UFRAME_NUM=0 ;
 130:  UTOOL_NUM=9 ;
 131:  PR[64]=LPOS    ;
 132:  PR[84]=JPOS    ;
 133:  !move 15 ;
 134:  UFRAME_NUM=0 ;
 135:  UTOOL_NUM=1 ;
 136:J P[15] 4% FINE    ;
 137:  UFRAME_NUM=0 ;
 138:  UTOOL_NUM=9 ;
 139:  PR[65]=LPOS    ;
 140:  PR[85]=JPOS    ;
 141:  !move 16 ;
 142:  UFRAME_NUM=0 ;
 143:  UTOOL_NUM=3 ;
 144:J P[16] 4% FINE    ;
 145:  UFRAME_NUM=0 ;
 146:  UTOOL_NUM=9 ;
 147:  PR[66]=LPOS    ;
 148:  PR[86]=JPOS    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1070.000  mm,	Y =   -50.000  mm,	Z =   520.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =  1029.037  mm,	Y =  -262.827  mm,	Z =   380.000  mm,
	W =  -180.000 deg,	P =   -30.000 deg,	R =  -160.000 deg
};
P[3]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   284.179  mm,	Y =   -61.599  mm,	Z =   164.052  mm,
	W =   170.000 deg,	P =      .000 deg,	R =   135.000 deg
};
P[4]{
   GP1:
	UF : 1, UT : 3,		CONFIG : 'N U T, 0, 0, 0',
	X =    80.888  mm,	Y =  -141.301  mm,	Z =   154.884  mm,
	W =   170.000 deg,	P =     -.000 deg,	R =   100.000 deg
};
P[5]{
   GP1:
	UF : 2, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =    88.988  mm,	Y =    76.287  mm,	Z =    83.554  mm,
	W =  -175.417 deg,	P =   -29.572 deg,	R =   157.723 deg
};
P[6]{
   GP1:
	UF : 2, UT : 3,		CONFIG : 'N U T, 0, 0, 0',
	X =   218.586  mm,	Y =   -46.026  mm,	Z =    65.809  mm,
	W =   173.693 deg,	P =     3.625 deg,	R =   100.054 deg
};
P[7]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   490.294  mm,	Y =   -52.682  mm,	Z =    28.662  mm,
	W =  -170.782 deg,	P =   -29.679 deg,	R =   155.406 deg
};
P[8]{
   GP1:
	UF : 2, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   -46.535  mm,	Y =   157.865  mm,	Z =   220.839  mm,
	W =  -179.304 deg,	P =    -3.939 deg,	R =  -115.024 deg
};
P[9]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   344.179  mm,	Y =  -101.599  mm,	Z =   194.052  mm,
	W =   170.000 deg,	P =      .000 deg,	R =   135.000 deg
};
P[10]{
   GP1:
	UF : 2, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =    38.988  mm,	Y =    96.287  mm,	Z =    48.554  mm,
	W =  -175.417 deg,	P =   -29.572 deg,	R =   157.723 deg
};
P[11]{
   GP1:
	UF : 2, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =    43.230  mm,	Y =    59.263  mm,	Z =    60.831  mm,
	W =  -175.417 deg,	P =   -29.572 deg,	R =   157.723 deg
};
P[12]{
   GP1:
	UF : 2, UT : 3,		CONFIG : 'N U T, 0, 0, 0',
	X =   212.629  mm,	Y =   -43.891  mm,	Z =   115.407  mm,
	W =   172.757 deg,	P =     -.636 deg,	R =    65.294 deg
};
P[13]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =  1012.780  mm,	Y =  -258.102  mm,	Z =   376.340  mm,
	W =  -161.826 deg,	P =   -17.032 deg,	R =  -178.751 deg
};
P[14]{
   GP1:
	UF : 1, UT : 3,		CONFIG : 'N U T, 0, 0, 0',
	X =    80.888  mm,	Y =  -141.301  mm,	Z =   154.884  mm,
	W =   155.000 deg,	P =     -.000 deg,	R =   100.000 deg
};
P[15]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1070.000  mm,	Y =    30.000  mm,	Z =   560.000  mm,
	W =   180.000 deg,	P =   -10.000 deg,	R =   180.000 deg
};
P[16]{
   GP1:
	UF : 0, UT : 3,		CONFIG : 'N U T, 0, 0, 0',
	X =  1070.000  mm,	Y =   -50.000  mm,	Z =   520.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[17]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   -30.000  mm,	Y =    50.000  mm,	Z =   180.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[18]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -25.000  mm,	Z =   220.000  mm,
	W =     0.000 deg,	P =    30.000 deg,	R =   180.000 deg
};
P[19]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   -15.000  mm,	Y =   -60.000  mm,	Z =   150.000  mm,
	W =   -20.000 deg,	P =     0.000 deg,	R =   -90.000 deg
};
P[20]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[21]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   839.462  mm,	Y =  -298.349  mm,	Z =   150.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =    30.000 deg
};
P[22]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   948.821  mm,	Y =   247.471  mm,	Z =   339.903  mm,
	W =     3.864 deg,	P =    -1.034 deg,	R =   -10.035 deg
};
P[23]{
   GP1:
	UF : 0, UT : 9,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
/END
