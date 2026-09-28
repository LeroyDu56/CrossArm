/PROG  COMPPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "compute probe";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 132;
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
   1:  !CrossArm compute probe ;
   2:  !SETUP_FRAMES ;
   3:  PR[100]=P[7]    ;
   4:  UTOOL[1]=PR[100] ;
   5:  PR[100]=P[8]    ;
   6:  UTOOL[2]=PR[100] ;
   7:  PR[100]=P[9]    ;
   8:  UFRAME[1]=PR[100] ;
   9:  PR[100]=P[10]    ;
  10:  UFRAME[2]=PR[100] ;
  11:  PR[99]=P[11]    ;
  12:  PR[98]=P[12]    ;
  13:  PR[97]=P[13]    ;
  14:  PR[96]=P[14]    ;
  15:  PR[95]=P[15]    ;
  16:  PR[94]=P[16]    ;
  17:  PR[29]=P[17]    ;
  18:  UTOOL[9]=PR[29] ;
  19:  !known start ;
  20:  UFRAME_NUM=0 ;
  21:  UTOOL_NUM=9 ;
  22:J P[18] 10% FINE    ;
  23:  PR[50]=LPOS    ;
  24:  PR[70]=JPOS    ;
  25:  !l.38 tBuilt := MakeTool(tBase, s ;
  26:  UTOOL[1]=PR[99] ;
  27:  UFRAME_NUM=0 ;
  28:  UTOOL_NUM=1 ;
  29:  !move 1 ;
  30:  UFRAME_NUM=0 ;
  31:  UTOOL_NUM=1 ;
  32:J P[1] 4% FINE    ;
  33:  UFRAME_NUM=0 ;
  34:  UTOOL_NUM=9 ;
  35:  PR[51]=LPOS    ;
  36:  PR[71]=JPOS    ;
  37:  !l.40 wCopy.uframe := wBase.ufram ;
  38:  UFRAME[1]=PR[98] ;
  39:  UFRAME_NUM=1 ;
  40:  !move 2 ;
  41:  UFRAME_NUM=1 ;
  42:  UTOOL_NUM=1 ;
  43:J P[2] 4% FINE    ;
  44:  UFRAME_NUM=0 ;
  45:  UTOOL_NUM=9 ;
  46:  PR[52]=LPOS    ;
  47:  PR[72]=JPOS    ;
  48:  !l.42 wDef.uframe := DefFrame(pD1 ;
  49:  UFRAME[2]=PR[97] ;
  50:  UFRAME_NUM=2 ;
  51:  UTOOL_NUM=2 ;
  52:  !move 3 ;
  53:  UFRAME_NUM=2 ;
  54:  UTOOL_NUM=2 ;
  55:J P[3] 4% FINE    ;
  56:  UFRAME_NUM=0 ;
  57:  UTOOL_NUM=9 ;
  58:  PR[53]=LPOS    ;
  59:  PR[73]=JPOS    ;
  60:  !l.44 wDef.uframe := DefFrame(pD1 ;
  61:  UFRAME[2]=PR[96] ;
  62:  UFRAME_NUM=2 ;
  63:  !move 4 ;
  64:  UFRAME_NUM=2 ;
  65:  UTOOL_NUM=2 ;
  66:J P[3] 4% FINE    ;
  67:  UFRAME_NUM=0 ;
  68:  UTOOL_NUM=9 ;
  69:  PR[54]=LPOS    ;
  70:  PR[74]=JPOS    ;
  71:  !l.46 wDef.uframe := DefFrame(pD1 ;
  72:  UFRAME[2]=PR[95] ;
  73:  UFRAME_NUM=2 ;
  74:  !move 5 ;
  75:  UFRAME_NUM=2 ;
  76:  UTOOL_NUM=2 ;
  77:J P[3] 4% FINE    ;
  78:  UFRAME_NUM=0 ;
  79:  UTOOL_NUM=9 ;
  80:  PR[55]=LPOS    ;
  81:  PR[75]=JPOS    ;
  82:  !l.48 pC := pT4 ;
  83:  !l.49 pC.trans := PoseVect(PoseIn ;
  84:  !l.50 pC.rot := OrientZYX(EulerZY ;
  85:  UFRAME_NUM=0 ;
  86:  !move 6 ;
  87:  UFRAME_NUM=0 ;
  88:  UTOOL_NUM=2 ;
  89:J P[4] 4% FINE    ;
  90:  UFRAME_NUM=0 ;
  91:  UTOOL_NUM=9 ;
  92:  PR[56]=LPOS    ;
  93:  PR[76]=JPOS    ;
  94:  !move 7 ;
  95:  UFRAME_NUM=0 ;
  96:  UTOOL_NUM=2 ;
  97:J P[5] 4% FINE    ;
  98:  UFRAME_NUM=0 ;
  99:  UTOOL_NUM=9 ;
 100:  PR[57]=LPOS    ;
 101:  PR[77]=JPOS    ;
 102:  !l.53 tBuilt := MakeTool(tBase, [ ;
 103:  UTOOL[1]=PR[94] ;
 104:  UTOOL_NUM=1 ;
 105:  !move 8 ;
 106:  UFRAME_NUM=0 ;
 107:  UTOOL_NUM=1 ;
 108:J P[1] 4% FINE    ;
 109:  UFRAME_NUM=0 ;
 110:  UTOOL_NUM=9 ;
 111:  PR[58]=LPOS    ;
 112:  PR[78]=JPOS    ;
 113:  !move 9 ;
 114:  UFRAME_NUM=0 ;
 115:  UTOOL_NUM=1 ;
 116:J P[6] 4% FINE    ;
 117:  UFRAME_NUM=0 ;
 118:  UTOOL_NUM=9 ;
 119:  PR[59]=LPOS    ;
 120:  PR[79]=JPOS    ;
 121:  !l.56 wDef.uframe := DefFrame(pD1 ;
 122:  UFRAME[2]=PR[97] ;
 123:  UFRAME_NUM=2 ;
 124:  UTOOL_NUM=2 ;
 125:  !move 10 ;
 126:  UFRAME_NUM=2 ;
 127:  UTOOL_NUM=2 ;
 128:J P[3] 4% FINE    ;
 129:  UFRAME_NUM=0 ;
 130:  UTOOL_NUM=9 ;
 131:  PR[60]=LPOS    ;
 132:  PR[80]=JPOS    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =    50.000  mm,	Z =   500.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   200.000  mm,	Y =   100.000  mm,	Z =   300.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 2, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    50.000  mm,	Z =   350.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =  1070.000  mm,	Y =  -220.000  mm,	Z =   600.000  mm,
	W =   172.000 deg,	P =     5.000 deg,	R =    25.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =  1070.970  mm,	Y =  -211.870  mm,	Z =   649.325  mm,
	W =   170.782 deg,	P =     1.976 deg,	R =     5.191 deg
};
P[6]{
   GP1:
	UF : 0, UT : 1,	
	J1=    10.000 deg,	J2=   -10.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -60.000 deg,	J6=   150.000 deg
};
P[7]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   100.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[8]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    20.000  mm,	Y =   -30.000  mm,	Z =   200.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[9]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =    50.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =   -10.000 deg
};
P[10]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[11]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    35.000  mm,	Y =   -40.000  mm,	Z =   240.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =    25.000 deg
};
P[12]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   900.970  mm,	Y =  -191.870  mm,	Z =   149.325  mm,
	W =    -8.741 deg,	P =     3.541 deg,	R =    15.079 deg
};
P[13]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   950.000  mm,	Y =  -150.000  mm,	Z =   120.000  mm,
	W =     7.634 deg,	P =     2.561 deg,	R =    26.565 deg
};
P[14]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1150.000  mm,	Y =   -50.000  mm,	Z =   110.000  mm,
	W =     7.634 deg,	P =     2.561 deg,	R =    26.565 deg
};
P[15]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1088.922  mm,	Y =   -80.539  mm,	Z =   113.054  mm,
	W =     7.634 deg,	P =     2.561 deg,	R =    26.565 deg
};
P[16]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    20.000  mm,	Y =    -5.000  mm,	Z =   170.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =   -40.000 deg
};
P[17]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[18]{
   GP1:
	UF : 0, UT : 9,	
	J1=     0.000 deg,	J2=     0.000 deg,	J3=     0.000 deg,
	J4=     0.000 deg,	J5=   -90.000 deg,	J6=     0.000 deg
};
/END
