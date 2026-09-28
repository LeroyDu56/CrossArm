/PROG  PATHPROBE
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "path probe";
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
   1:  !CrossArm path probe ;
   2:  PR[20]=P[19]    ;
   3:  UTOOL[1]=PR[20] ;
   4:  !RAPID PathProbe.Path ;
   5:  UFRAME_NUM=0 ;
   6:  UTOOL_NUM=1 ;
   7:J P[1] 50% FINE    ;
   8:L P[2] 1000mm/sec CNT17    ;
   9:L P[3] 300mm/sec FINE    ;
  10:J P[1] 50% FINE    ;
  11:L P[2] 1000mm/sec CNT39    ;
  12:L P[3] 300mm/sec FINE    ;
  13:J P[1] 50% FINE    ;
  14:L P[2] 1000mm/sec CNT59    ;
  15:L P[3] 300mm/sec FINE    ;
  16:J P[1] 50% FINE    ;
  17:L P[4] 1000mm/sec CNT17    ;
  18:L P[3] 300mm/sec FINE    ;
  19:J P[1] 50% FINE    ;
  20:L P[4] 1000mm/sec CNT39    ;
  21:L P[3] 300mm/sec FINE    ;
  22:J P[1] 50% FINE    ;
  23:L P[4] 1000mm/sec CNT59    ;
  24:L P[3] 300mm/sec FINE    ;
  25:J P[1] 50% FINE    ;
  26:L P[5] 1000mm/sec CNT17    ;
  27:L P[3] 300mm/sec FINE    ;
  28:J P[1] 50% FINE    ;
  29:L P[5] 1000mm/sec CNT39    ;
  30:L P[3] 300mm/sec FINE    ;
  31:J P[1] 50% FINE    ;
  32:L P[5] 1000mm/sec CNT59    ;
  33:L P[3] 300mm/sec FINE    ;
  34:J P[1] 50% FINE    ;
  35:J P[2] 50% CNT30    ;
  36:L P[3] 300mm/sec FINE    ;
  37:J P[1] 50% FINE    ;
  38:J P[2] 50% CNT65    ;
  39:L P[3] 300mm/sec FINE    ;
  40:J P[1] 50% FINE    ;
  41:J P[2] 50% CNT99    ;
  42:L P[3] 300mm/sec FINE    ;
  43:J P[3] 50% FINE    ;
  44:L P[2] 300mm/sec CNT16    ;
  45:L P[1] 1000mm/sec FINE    ;
  46:J P[3] 50% FINE    ;
  47:L P[2] 300mm/sec CNT37    ;
  48:L P[1] 1000mm/sec FINE    ;
  49:J P[3] 50% FINE    ;
  50:L P[2] 300mm/sec CNT57    ;
  51:L P[1] 1000mm/sec FINE    ;
  52:J P[3] 50% FINE    ;
  53:L P[5] 300mm/sec CNT16    ;
  54:L P[1] 1000mm/sec FINE    ;
  55:J P[3] 50% FINE    ;
  56:L P[5] 300mm/sec CNT37    ;
  57:L P[1] 1000mm/sec FINE    ;
  58:J P[3] 50% FINE    ;
  59:L P[5] 300mm/sec CNT57    ;
  60:L P[1] 1000mm/sec FINE    ;
  61:J P[3] 50% FINE    ;
  62:L P[2] 300mm/sec CNT16    ;
  63:J P[1] 50% FINE    ;
  64:J P[3] 50% FINE    ;
  65:L P[2] 300mm/sec CNT37    ;
  66:J P[1] 50% FINE    ;
  67:J P[3] 50% FINE    ;
  68:L P[2] 300mm/sec CNT57    ;
  69:J P[1] 50% FINE    ;
  70:J P[6] 50% FINE    ;
  71:L P[7] 600mm/sec CNT21    ;
  72:L P[8] 600mm/sec FINE    ;
  73:J P[6] 50% FINE    ;
  74:L P[7] 600mm/sec CNT35    ;
  75:L P[8] 600mm/sec FINE    ;
  76:J P[6] 50% FINE    ;
  77:L P[7] 600mm/sec CNT59    ;
  78:L P[8] 600mm/sec FINE    ;
  79:J P[9] 50% FINE    ;
  80:L P[10] 600mm/sec CNT26    ;
  81:L P[11] 600mm/sec FINE    ;
  82:J P[9] 50% FINE    ;
  83:L P[10] 600mm/sec CNT59    ;
  84:L P[11] 600mm/sec FINE    ;
  85:J P[9] 50% FINE    ;
  86:L P[10] 600mm/sec CNT26    ;
  87:L P[12] 600mm/sec FINE    ;
  88:J P[9] 50% FINE    ;
  89:L P[10] 600mm/sec CNT59    ;
  90:L P[12] 600mm/sec FINE    ;
  91:J P[13] 50% FINE    ;
  92:L P[14] 300mm/sec CNT42    ;
  93:L P[15] 300mm/sec CNT42    ;
  94:L P[16] 300mm/sec CNT42    ;
  95:L P[17] 300mm/sec CNT42    ;
  96:L P[18] 300mm/sec FINE    ;
  97:J P[13] 50% FINE    ;
  98:L P[14] 300mm/sec CNT59    ;
  99:L P[15] 300mm/sec CNT59    ;
 100:L P[16] 300mm/sec CNT59    ;
 101:L P[17] 300mm/sec CNT59    ;
 102:L P[18] 300mm/sec FINE    ;
 103:J P[13] 50% FINE    ;
 104:L P[14] 600mm/sec CNT26    ;
 105:L P[15] 600mm/sec CNT26    ;
 106:L P[16] 600mm/sec CNT26    ;
 107:L P[17] 600mm/sec CNT26    ;
 108:L P[18] 600mm/sec FINE    ;
 109:J P[13] 50% FINE    ;
 110:L P[14] 600mm/sec CNT35    ;
 111:L P[15] 600mm/sec CNT35    ;
 112:L P[16] 600mm/sec CNT35    ;
 113:L P[17] 600mm/sec CNT35    ;
 114:L P[18] 600mm/sec FINE    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =  -250.000  mm,	Z =   950.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1300.000  mm,	Y =   100.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1300.000  mm,	Y =   100.000  mm,	Z =   700.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1300.000  mm,	Y =   100.000  mm,	Z =   750.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1300.000  mm,	Y =   100.000  mm,	Z =   720.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[6]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1200.000  mm,	Y =  -150.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[7]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1200.000  mm,	Y =  -150.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[8]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1200.000  mm,	Y =  -140.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[9]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1250.000  mm,	Y =  -350.000  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[10]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1250.000  mm,	Y =   -50.000  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[11]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1391.421  mm,	Y =    91.421  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[12]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1391.421  mm,	Y =  -191.421  mm,	Z =   900.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[13]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1150.000  mm,	Y =  -100.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[14]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1200.000  mm,	Y =  -100.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[15]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1200.000  mm,	Y =   -50.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[16]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1250.000  mm,	Y =   -50.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[17]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1250.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[18]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1300.000  mm,	Y =     0.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   135.000 deg
};
P[19]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
