/PROG  PALLETDIRECT
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "PalletDirect";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 94;
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
   1:  !RAPID PalletProbe.PalletDirect ;
   2:  UFRAME_NUM=1 ;
   3:  UTOOL_NUM=1 ;
   4:L P[1] 500mm/sec FINE    ;
   5:  UFRAME_NUM=0 ;
   6:  UTOOL_NUM=9 ;
   7:  PR[R[90]]=LPOS    ;
   8:  R[90]=R[90]+1    ;
   9:  UFRAME_NUM=1 ;
  10:  UTOOL_NUM=1 ;
  11:L P[2] 200mm/sec FINE    ;
  12:  UFRAME_NUM=0 ;
  13:  UTOOL_NUM=9 ;
  14:  PR[R[90]]=LPOS    ;
  15:  R[90]=R[90]+1    ;
  16:  UFRAME_NUM=1 ;
  17:  UTOOL_NUM=1 ;
  18:L P[3] 500mm/sec FINE    ;
  19:  UFRAME_NUM=0 ;
  20:  UTOOL_NUM=9 ;
  21:  PR[R[90]]=LPOS    ;
  22:  R[90]=R[90]+1    ;
  23:  UFRAME_NUM=1 ;
  24:  UTOOL_NUM=1 ;
  25:L P[4] 500mm/sec FINE    ;
  26:  UFRAME_NUM=0 ;
  27:  UTOOL_NUM=9 ;
  28:  PR[R[90]]=LPOS    ;
  29:  R[90]=R[90]+1    ;
  30:  UFRAME_NUM=1 ;
  31:  UTOOL_NUM=1 ;
  32:L P[5] 200mm/sec FINE    ;
  33:  UFRAME_NUM=0 ;
  34:  UTOOL_NUM=9 ;
  35:  PR[R[90]]=LPOS    ;
  36:  R[90]=R[90]+1    ;
  37:  UFRAME_NUM=1 ;
  38:  UTOOL_NUM=1 ;
  39:L P[6] 500mm/sec FINE    ;
  40:  UFRAME_NUM=0 ;
  41:  UTOOL_NUM=9 ;
  42:  PR[R[90]]=LPOS    ;
  43:  R[90]=R[90]+1    ;
  44:  UFRAME_NUM=1 ;
  45:  UTOOL_NUM=1 ;
  46:L P[7] 500mm/sec FINE    ;
  47:  UFRAME_NUM=0 ;
  48:  UTOOL_NUM=9 ;
  49:  PR[R[90]]=LPOS    ;
  50:  R[90]=R[90]+1    ;
  51:  UFRAME_NUM=1 ;
  52:  UTOOL_NUM=1 ;
  53:L P[8] 200mm/sec FINE    ;
  54:  UFRAME_NUM=0 ;
  55:  UTOOL_NUM=9 ;
  56:  PR[R[90]]=LPOS    ;
  57:  R[90]=R[90]+1    ;
  58:  UFRAME_NUM=1 ;
  59:  UTOOL_NUM=1 ;
  60:L P[9] 500mm/sec FINE    ;
  61:  UFRAME_NUM=0 ;
  62:  UTOOL_NUM=9 ;
  63:  PR[R[90]]=LPOS    ;
  64:  R[90]=R[90]+1    ;
  65:  UFRAME_NUM=1 ;
  66:  UTOOL_NUM=1 ;
  67:L P[10] 500mm/sec FINE    ;
  68:  UFRAME_NUM=0 ;
  69:  UTOOL_NUM=9 ;
  70:  PR[R[90]]=LPOS    ;
  71:  R[90]=R[90]+1    ;
  72:  UFRAME_NUM=1 ;
  73:  UTOOL_NUM=1 ;
  74:L P[11] 200mm/sec FINE    ;
  75:  UFRAME_NUM=0 ;
  76:  UTOOL_NUM=9 ;
  77:  PR[R[90]]=LPOS    ;
  78:  R[90]=R[90]+1    ;
  79:  UFRAME_NUM=1 ;
  80:  UTOOL_NUM=1 ;
  81:L P[12] 500mm/sec FINE    ;
  82:  UFRAME_NUM=0 ;
  83:  UTOOL_NUM=9 ;
  84:  PR[R[90]]=LPOS    ;
  85:  R[90]=R[90]+1    ;
  86:  UFRAME_NUM=1 ;
  87:  UTOOL_NUM=1 ;
  88:L P[13] 200mm/sec FINE    ;
  89:  UFRAME_NUM=0 ;
  90:  UTOOL_NUM=9 ;
  91:  PR[R[90]]=LPOS    ;
  92:  R[90]=R[90]+1    ;
  93:  UFRAME_NUM=1 ;
  94:  UTOOL_NUM=1 ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   270.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =   -40.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   130.000  mm,	Y =   -20.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[4]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   130.000  mm,	Y =   -40.000  mm,	Z =   270.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[5]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   130.000  mm,	Y =   -40.000  mm,	Z =   230.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[6]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   220.000  mm,	Y =   -20.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[7]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    70.000  mm,	Y =   -20.000  mm,	Z =   295.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -90.000 deg
};
P[8]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    70.000  mm,	Y =   -20.000  mm,	Z =   255.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -90.000 deg
};
P[9]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   130.000  mm,	Y =     0.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[10]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   160.000  mm,	Y =   -20.000  mm,	Z =   295.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -90.000 deg
};
P[11]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   160.000  mm,	Y =   -20.000  mm,	Z =   255.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   -90.000 deg
};
P[12]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   220.000  mm,	Y =     0.000  mm,	Z =   290.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[13]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   235.000  mm,	Y =    10.000  mm,	Z =   320.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
