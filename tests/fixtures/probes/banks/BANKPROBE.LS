/PROG  BANKPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "bank probe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 168;
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
   1:  !CrossArm frame bank probe ;
   2:  R[40]=0    ;
   3:  !store the frames ;
   4:  PR[100]=P[17]    ;
   5:  UTOOL[1]=PR[100] ;
   6:  PR[99]=P[18]    ;
   7:  PR[97]=P[19]    ;
   8:  PR[98]=P[20]    ;
   9:  PR[96]=P[21]    ;
  10:  PR[21]=P[23]    ;
  11:  UTOOL[9]=PR[21] ;
  12:  !known start ;
  13:  UFRAME_NUM=0 ;
  14:  UTOOL_NUM=9 ;
  15:J P[22] 10% FINE    ;
  16:  PR[50]=LPOS    ;
  17:  PR[70]=JPOS    ;
  18:  !move 1 ;
  19:  UFRAME_NUM=0 ;
  20:  UTOOL_NUM=1 ;
  21:J P[1] 4% FINE    ;
  22:  UFRAME_NUM=0 ;
  23:  UTOOL_NUM=9 ;
  24:  PR[51]=LPOS    ;
  25:  PR[71]=JPOS    ;
  26:  !move 2 ;
  27:  UFRAME_NUM=0 ;
  28:  UTOOL[2]=PR[99] ;
  29:  UTOOL_NUM=2 ;
  30:J P[2] 4% FINE    ;
  31:  UFRAME_NUM=0 ;
  32:  UTOOL_NUM=9 ;
  33:  PR[52]=LPOS    ;
  34:  PR[72]=JPOS    ;
  35:  !move 3 ;
  36:  UFRAME[1]=PR[98] ;
  37:  UFRAME_NUM=1 ;
  38:  UTOOL_NUM=1 ;
  39:J P[3] 4% FINE    ;
  40:  UFRAME_NUM=0 ;
  41:  UTOOL_NUM=9 ;
  42:  PR[53]=LPOS    ;
  43:  PR[73]=JPOS    ;
  44:  !move 4 ;
  45:  UFRAME[1]=PR[98] ;
  46:  UFRAME_NUM=1 ;
  47:  UTOOL[2]=PR[97] ;
  48:  UTOOL_NUM=2 ;
  49:J P[4] 4% FINE    ;
  50:  UFRAME_NUM=0 ;
  51:  UTOOL_NUM=9 ;
  52:  PR[54]=LPOS    ;
  53:  PR[74]=JPOS    ;
  54:  !move 5 ;
  55:  UFRAME[1]=PR[96] ;
  56:  UFRAME_NUM=1 ;
  57:  UTOOL[2]=PR[99] ;
  58:  UTOOL_NUM=2 ;
  59:J P[5] 4% FINE    ;
  60:  UFRAME_NUM=0 ;
  61:  UTOOL_NUM=9 ;
  62:  PR[55]=LPOS    ;
  63:  PR[75]=JPOS    ;
  64:  !move 6 ;
  65:  UFRAME[1]=PR[96] ;
  66:  UFRAME_NUM=1 ;
  67:  UTOOL[2]=PR[97] ;
  68:  UTOOL_NUM=2 ;
  69:J P[6] 4% FINE    ;
  70:  UFRAME_NUM=0 ;
  71:  UTOOL_NUM=9 ;
  72:  PR[56]=LPOS    ;
  73:  PR[76]=JPOS    ;
  74:  !move 7 ;
  75:  UFRAME[1]=PR[98] ;
  76:  UFRAME_NUM=1 ;
  77:  UTOOL[2]=PR[99] ;
  78:  UTOOL_NUM=2 ;
  79:J P[7] 4% FINE    ;
  80:  UFRAME_NUM=0 ;
  81:  UTOOL_NUM=9 ;
  82:  PR[57]=LPOS    ;
  83:  PR[77]=JPOS    ;
  84:  !move 8 ;
  85:  UFRAME[1]=PR[96] ;
  86:  UFRAME_NUM=1 ;
  87:  UTOOL_NUM=1 ;
  88:J P[8] 4% FINE    ;
  89:  UFRAME_NUM=0 ;
  90:  UTOOL_NUM=9 ;
  91:  PR[58]=LPOS    ;
  92:  PR[78]=JPOS    ;
  93:  !move 9 ;
  94:  UFRAME[1]=PR[98] ;
  95:  UFRAME_NUM=1 ;
  96:  UTOOL_NUM=1 ;
  97:J P[9] 4% FINE    ;
  98:  UFRAME_NUM=0 ;
  99:  UTOOL_NUM=9 ;
 100:  PR[59]=LPOS    ;
 101:  PR[79]=JPOS    ;
 102:  !move 10 ;
 103:  UFRAME[1]=PR[96] ;
 104:  UFRAME_NUM=1 ;
 105:  UTOOL[2]=PR[99] ;
 106:  UTOOL_NUM=2 ;
 107:J P[10] 4% FINE    ;
 108:  UFRAME_NUM=0 ;
 109:  UTOOL_NUM=9 ;
 110:  PR[60]=LPOS    ;
 111:  PR[80]=JPOS    ;
 112:  !move 11 ;
 113:  UFRAME[1]=PR[96] ;
 114:  UFRAME_NUM=1 ;
 115:  UTOOL[2]=PR[99] ;
 116:  UTOOL_NUM=2 ;
 117:J P[11] 4% FINE    ;
 118:  UFRAME_NUM=0 ;
 119:  UTOOL_NUM=9 ;
 120:  PR[61]=LPOS    ;
 121:  PR[81]=JPOS    ;
 122:  !move 12 ;
 123:  UFRAME[1]=PR[96] ;
 124:  UFRAME_NUM=1 ;
 125:  UTOOL[2]=PR[97] ;
 126:  UTOOL_NUM=2 ;
 127:J P[12] 4% FINE    ;
 128:  UFRAME_NUM=0 ;
 129:  UTOOL_NUM=9 ;
 130:  PR[62]=LPOS    ;
 131:  PR[82]=JPOS    ;
 132:  !move 13 ;
 133:  UFRAME_NUM=0 ;
 134:  UTOOL[2]=PR[99] ;
 135:  UTOOL_NUM=2 ;
 136:J P[13] 4% FINE    ;
 137:  UFRAME_NUM=0 ;
 138:  UTOOL_NUM=9 ;
 139:  PR[63]=LPOS    ;
 140:  PR[83]=JPOS    ;
 141:  !move 14 ;
 142:  UFRAME[1]=PR[98] ;
 143:  UFRAME_NUM=1 ;
 144:  UTOOL[2]=PR[97] ;
 145:  UTOOL_NUM=2 ;
 146:J P[14] 4% FINE    ;
 147:  UFRAME_NUM=0 ;
 148:  UTOOL_NUM=9 ;
 149:  PR[64]=LPOS    ;
 150:  PR[84]=JPOS    ;
 151:  !move 15 ;
 152:  UFRAME_NUM=0 ;
 153:  UTOOL_NUM=1 ;
 154:J P[15] 4% FINE    ;
 155:  UFRAME_NUM=0 ;
 156:  UTOOL_NUM=9 ;
 157:  PR[65]=LPOS    ;
 158:  PR[85]=JPOS    ;
 159:  !move 16 ;
 160:  UFRAME_NUM=0 ;
 161:  UTOOL[2]=PR[97] ;
 162:  UTOOL_NUM=2 ;
 163:J P[16] 4% FINE    ;
 164:  UFRAME_NUM=0 ;
 165:  UTOOL_NUM=9 ;
 166:  PR[66]=LPOS    ;
 167:  PR[86]=JPOS    ;
 168:  R[40]=7    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1130.000  mm,	Y =    50.000  mm,	Z =   520.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   970.963  mm,	Y =  -337.173  mm,	Z =   380.000  mm,
	W =  -180.000 deg,	P =   -30.000 deg,	R =    20.000 deg
};
P[3]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   396.242  mm,	Y =   -34.389  mm,	Z =   181.417  mm,
	W =  -170.000 deg,	P =     -.000 deg,	R =   -45.000 deg
};
P[4]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   130.821  mm,	Y =  -254.348  mm,	Z =   149.674  mm,
	W =   150.000 deg,	P =      .000 deg,	R =   -80.000 deg
};
P[5]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =    -3.262  mm,	Y =    56.765  mm,	Z =    86.542  mm,
	W =   175.385 deg,	P =   -30.268 deg,	R =   -17.682 deg
};
P[6]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   268.270  mm,	Y =  -159.301  mm,	Z =    66.308  mm,
	W =   146.307 deg,	P =    -3.625 deg,	R =   -79.946 deg
};
P[7]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   398.184  mm,	Y =   -71.848  mm,	Z =    35.620  mm,
	W =   170.782 deg,	P =   -29.679 deg,	R =   -15.406 deg
};
P[8]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  -111.857  mm,	Y =   254.325  mm,	Z =   215.506  mm,
	W =   179.304 deg,	P =     3.939 deg,	R =    64.976 deg
};
P[9]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   456.242  mm,	Y =   -74.389  mm,	Z =   211.417  mm,
	W =  -170.000 deg,	P =     -.000 deg,	R =   -45.000 deg
};
P[10]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   -53.262  mm,	Y =    76.765  mm,	Z =    51.542  mm,
	W =   175.385 deg,	P =   -30.268 deg,	R =   -17.682 deg
};
P[11]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =    41.607  mm,	Y =    70.468  mm,	Z =    60.103  mm,
	W =   175.385 deg,	P =   -30.268 deg,	R =   -17.682 deg
};
P[12]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   295.122  mm,	Y =  -151.869  mm,	Z =   107.826  mm,
	W =   153.321 deg,	P =   -21.675 deg,	R =  -110.846 deg
};
P[13]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   987.220  mm,	Y =  -341.898  mm,	Z =   376.340  mm,
	W =  -161.826 deg,	P =   -17.032 deg,	R =     1.249 deg
};
P[14]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   130.821  mm,	Y =  -254.348  mm,	Z =   149.674  mm,
	W =   135.000 deg,	P =      .000 deg,	R =   -80.000 deg
};
P[15]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1130.000  mm,	Y =   130.000  mm,	Z =   560.000  mm,
	W =   180.000 deg,	P =   -10.000 deg,	R =     0.000 deg
};
P[16]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =  1130.000  mm,	Y =    50.000  mm,	Z =   520.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[17]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    30.000  mm,	Y =   -50.000  mm,	Z =   180.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[18]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   -40.000  mm,	Y =    25.000  mm,	Z =   220.000  mm,
	W =     0.000 deg,	P =    30.000 deg,	R =     0.000 deg
};
P[19]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    15.000  mm,	Y =    60.000  mm,	Z =   150.000  mm,
	W =   -20.000 deg,	P =     0.000 deg,	R =    90.000 deg
};
P[20]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   839.462  mm,	Y =  -298.349  mm,	Z =   150.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =    30.000 deg
};
P[21]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   948.821  mm,	Y =   247.471  mm,	Z =   339.903  mm,
	W =     3.864 deg,	P =    -1.034 deg,	R =   -10.035 deg
};
P[22]{
   GP1:
	UF : 0, UT : 9,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
P[23]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
