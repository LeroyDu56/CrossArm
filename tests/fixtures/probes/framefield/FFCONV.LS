/PROG  FFCONV
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FfConv";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 131;
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
   1:  !CrossArm EVALUATION copy ;
   2:  !production use needs a licence ;
   3:  !RAPID FrameFieldProbe.FfConv ;
   4:  R[1:ffDone]=0    ;
   5:  UFRAME_NUM=0 ;
   6:  UTOOL_NUM=1 ;
   7:J P[1] 11% FINE    ;
   8:  PR[97]=LPOS    ;
   9:  PR[96]=P[2]    ;
  10:  R[2:Calc1]=PR[97,3]-760    ;
  11:  PR[96,3]=PR[96,3]+R[2:Calc1]    ;
  12:  !l.39 ffStylus.tframe.trans:=ffOf ;
  13:  PR[95]=UTOOL[2] ;
  14:  PR[95,1]=PR[96,1]    ;
  15:  PR[95,2]=PR[96,2]    ;
  16:  PR[95,3]=PR[96,3]    ;
  17:  UTOOL[2]=PR[95] ;
  18:  !l.40 ffStylus.tframe.trans.x:=ff ;
  19:  PR[95]=UTOOL[2] ;
  20:  PR[95,1]=PR[97,1]-1040    ;
  21:  UTOOL[2]=PR[95] ;
  22:  UTOOL_NUM=2 ;
  23:L P[3] 500mm/sec FINE    ;
  24:  UTOOL_NUM=1 ;
  25:  PR[94]=LPOS    ;
  26:J P[4] 11% FINE    ;
  27:  PR[93]=LPOS    ;
  28:  !l.45 ffPallet.uframe.trans:=ffM1 ;
  29:  PR[95]=UFRAME[1] ;
  30:  PR[95,1]=PR[93,1]    ;
  31:  PR[95,2]=PR[93,2]    ;
  32:  PR[95,3]=PR[93,3]    ;
  33:  UFRAME[1]=PR[95] ;
  34:  !l.46 ffPallet.uframe.rot:=ffM1.r ;
  35:  PR[95]=UFRAME[1] ;
  36:  PR[95,4]=PR[93,4]    ;
  37:  PR[95,5]=PR[93,5]    ;
  38:  PR[95,6]=PR[93,6]    ;
  39:  UFRAME[1]=PR[95] ;
  40:  !l.47 ffPallet.oframe:=[[0,0,0],[ ;
  41:  UFRAME_NUM=1 ;
  42:L P[5] 500mm/sec FINE    ;
  43:  UFRAME_NUM=0 ;
  44:  PR[92]=LPOS    ;
  45:  !l.50 ffNest1.uframe:=ffPallet.uf ;
  46:  PR[95]=UFRAME[1] ;
  47:  UFRAME[2]=PR[95] ;
  48:  !l.51 ffNest3.uframe:=ffPallet.uf ;
  49:  PR[95]=UFRAME[1] ;
  50:  UFRAME[6]=PR[95] ;
  51:  !l.52 ffNest4.uframe:=ffPallet.uf ;
  52:  PR[95]=UFRAME[1] ;
  53:  UFRAME[7]=PR[95] ;
  54:  !l.53 ffNest5.uframe:=ffPallet.uf ;
  55:  PR[95]=UFRAME[1] ;
  56:  UFRAME[8]=PR[95] ;
  57:  !l.54 ffNest6.uframe:=ffPallet.uf ;
  58:  PR[95]=UFRAME[1] ;
  59:  PR[99]=PR[95]    ;
  60:  !l.55 ffNest7.uframe:=ffPallet.uf ;
  61:  PR[95]=UFRAME[1] ;
  62:  PR[98]=PR[95]    ;
  63:  !l.56 ffNest8.uframe:=ffPallet.uf ;
  64:  PR[95]=UFRAME[1] ;
  65:  PR[91,1]=30    ;
  66:  PR[91,2]=0    ;
  67:  PR[91,3]=0    ;
  68:  PR[91,4]=0    ;
  69:  PR[91,5]=0    ;
  70:  PR[91,6]=0    ;
  71:  CALL CA_POSEMULT(95,91,95) ;
  72:  UFRAME[3]=PR[95] ;
  73:  !l.57 ffNest9.uframe:=ffPallet.uf ;
  74:  PR[95]=UFRAME[1] ;
  75:  PR[91,1]=0    ;
  76:  PR[91,2]=20    ;
  77:  PR[91,3]=0    ;
  78:  PR[91,4]=0    ;
  79:  PR[91,5]=0    ;
  80:  PR[91,6]=30    ;
  81:  CALL CA_POSEMULT(95,91,95) ;
  82:  UFRAME[4]=PR[95] ;
  83:  !l.58 ffNest2.uframe:=[ffM2.trans ;
  84:  PR[95,1]=PR[97,1]    ;
  85:  PR[95,2]=PR[97,2]    ;
  86:  PR[95,3]=PR[97,3]    ;
  87:  PR[90]=UFRAME[1] ;
  88:  PR[95,4]=PR[90,4]    ;
  89:  PR[95,5]=PR[90,5]    ;
  90:  PR[95,6]=PR[90,6]    ;
  91:  UFRAME[5]=PR[95] ;
  92:  UFRAME_NUM=2 ;
  93:  UTOOL_NUM=1 ;
  94:L P[6] 500mm/sec FINE    ;
  95:  UFRAME_NUM=0 ;
  96:  PR[89]=LPOS    ;
  97:  UFRAME_NUM=3 ;
  98:L P[7] 500mm/sec FINE    ;
  99:  UFRAME_NUM=0 ;
 100:  PR[88]=LPOS    ;
 101:  UFRAME_NUM=4 ;
 102:L P[8] 500mm/sec FINE    ;
 103:  UFRAME_NUM=0 ;
 104:  PR[87]=LPOS    ;
 105:  UFRAME_NUM=5 ;
 106:L P[9] 500mm/sec FINE    ;
 107:  UFRAME_NUM=0 ;
 108:  PR[86]=LPOS    ;
 109:  UFRAME_NUM=6 ;
 110:L P[10] 500mm/sec FINE    ;
 111:  UFRAME_NUM=0 ;
 112:  PR[85]=LPOS    ;
 113:  UFRAME_NUM=7 ;
 114:L P[11] 500mm/sec FINE    ;
 115:  UFRAME_NUM=0 ;
 116:  PR[84]=LPOS    ;
 117:  UFRAME_NUM=8 ;
 118:L P[12] 500mm/sec FINE    ;
 119:  UFRAME_NUM=0 ;
 120:  PR[83]=LPOS    ;
 121:  UFRAME[9]=PR[99] ;
 122:  UFRAME_NUM=9 ;
 123:L P[13] 500mm/sec FINE    ;
 124:  UFRAME_NUM=0 ;
 125:  PR[82]=LPOS    ;
 126:  UFRAME[9]=PR[98] ;
 127:  UFRAME_NUM=9 ;
 128:L P[14] 500mm/sec FINE    ;
 129:  UFRAME_NUM=0 ;
 130:  PR[81]=LPOS    ;
 131:  R[1:ffDone]=1    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1050.000  mm,	Y =    80.000  mm,	Z =   780.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   150.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =  1050.000  mm,	Y =    80.000  mm,	Z =   780.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   950.000  mm,	Y =   -60.000  mm,	Z =   820.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -160.000 deg
};
P[5]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[6]{
   GP1:
	UF : 2, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[7]{
   GP1:
	UF : 3, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[8]{
   GP1:
	UF : 4, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[9]{
   GP1:
	UF : 5, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[10]{
   GP1:
	UF : 6, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[11]{
   GP1:
	UF : 7, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[12]{
   GP1:
	UF : 8, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[13]{
   GP1:
	UF : 9, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[14]{
   GP1:
	UF : 9, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
