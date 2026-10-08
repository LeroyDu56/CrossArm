/PROG  FICONV
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FiConv";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 53;
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
   3:  !RAPID FuncInlineProbe.FiConv ;
   4:  R[1:fiDone]=0    ;
   5:  CALL FICALIB    ;
   6:  CALL FIINIT    ;
   7:  UFRAME_NUM=0 ;
   8:  UTOOL_NUM=1 ;
   9:J P[1] 11% FINE    ;
  10:  UTOOL_NUM=2 ;
  11:  PR[96]=LPOS    ;
  12:  UTOOL_NUM=3 ;
  13:J P[2] 11% FINE    ;
  14:  UTOOL_NUM=2 ;
  15:  PR[95]=LPOS    ;
  16:  UTOOL_NUM=4 ;
  17:J P[3] 11% FINE    ;
  18:  UTOOL_NUM=2 ;
  19:  PR[94]=LPOS    ;
  20:  UTOOL_NUM=5 ;
  21:J P[4] 11% FINE    ;
  22:  UTOOL_NUM=2 ;
  23:  PR[93]=LPOS    ;
  24:  UTOOL_NUM=6 ;
  25:J P[5] 11% FINE    ;
  26:  UTOOL_NUM=2 ;
  27:  PR[92]=LPOS    ;
  28:  UTOOL_NUM=7 ;
  29:J P[6] 11% FINE    ;
  30:  UTOOL_NUM=2 ;
  31:  PR[91]=LPOS    ;
  32:  UTOOL_NUM=8 ;
  33:J P[7] 11% FINE    ;
  34:  UTOOL_NUM=2 ;
  35:  PR[90]=LPOS    ;
  36:  UTOOL_NUM=9 ;
  37:J P[8] 11% FINE    ;
  38:  UTOOL_NUM=2 ;
  39:  PR[89]=LPOS    ;
  40:  UTOOL[10]=PR[99] ;
  41:  UTOOL_NUM=10 ;
  42:J P[9] 11% FINE    ;
  43:  UTOOL_NUM=2 ;
  44:  PR[88]=LPOS    ;
  45:  UFRAME_NUM=1 ;
  46:J P[10] 11% FINE    ;
  47:  UFRAME_NUM=0 ;
  48:  PR[87]=LPOS    ;
  49:  UFRAME_NUM=2 ;
  50:J P[11] 11% FINE    ;
  51:  UFRAME_NUM=0 ;
  52:  PR[86]=LPOS    ;
  53:  R[1:fiDone]=1    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -160.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 3,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -160.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 4,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -160.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 5,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -160.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 6,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -160.000 deg
};
P[6]{
   GP1:
	UF : 0, UT : 7,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -160.000 deg
};
P[7]{
   GP1:
	UF : 0, UT : 8,		CONFIG : 'N U T, 0, 0, 1',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[8]{
   GP1:
	UF : 0, UT : 9,		CONFIG : 'N U T, 0, 0, 1',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[9]{
   GP1:
	UF : 0, UT : 10,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[10]{
   GP1:
	UF : 1, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[11]{
   GP1:
	UF : 2, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
