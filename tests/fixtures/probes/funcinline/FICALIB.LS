/PROG  FICALIB
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FiCalib";
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
   3:  !RAPID FuncInlineProbe.FiCalib ;
   4:  UFRAME_NUM=0 ;
   5:  UTOOL_NUM=2 ;
   6:J P[1] 11% FINE    ;
   7:  PR[85]=LPOS    ;
   8:  !l.117 fiGrip.tframe.trans.x:=fiM ;
   9:  PR[84]=PR[98]    ;
  10:  PR[84,1]=PR[85,1]-1040    ;
  11:  PR[98]=PR[84]    ;
  12:  !l.118 fiGrip.tframe.trans.z:=fiM ;
  13:  PR[84]=PR[98]    ;
  14:  PR[84,3]=PR[85,3]-640    ;
  15:  PR[98]=PR[84]    ;
  16:  UTOOL_NUM=2 ;
  17:J P[2] 11% FINE    ;
  18:  PR[83]=LPOS    ;
  19:  !l.121 fiCam.tframe.trans.z:=fiM1 ;
  20:  PR[84]=PR[97]    ;
  21:  PR[84,3]=PR[83,3]-700    ;
  22:  PR[97]=PR[84]    ;
  23:  !l.122 fiCam.tframe.rot:=fiM1.rot ;
  24:  PR[84]=PR[97]    ;
  25:  PR[84,4]=PR[83,4]    ;
  26:  PR[84,5]=PR[83,5]    ;
  27:  PR[84,6]=PR[83,6]    ;
  28:  PR[97]=PR[84]    ;
  29:  !l.123 fiTable.uframe.trans:=fiM1 ;
  30:  PR[84]=UFRAME[3] ;
  31:  PR[84,1]=PR[83,1]    ;
  32:  PR[84,2]=PR[83,2]    ;
  33:  PR[84,3]=PR[83,3]    ;
  34:  UFRAME[3]=PR[84] ;
  35:  !l.124 fiTable.uframe.rot:=fiM1.r ;
  36:  PR[84]=UFRAME[3] ;
  37:  PR[84,4]=PR[83,4]    ;
  38:  PR[84,5]=PR[83,5]    ;
  39:  PR[84,6]=PR[83,6]    ;
  40:  UFRAME[3]=PR[84] ;
  41:  UFRAME_NUM=0 ;
  42:  UTOOL[10]=PR[98] ;
  43:  UTOOL_NUM=10 ;
  44:J P[3] 11% FINE    ;
  45:  UTOOL_NUM=2 ;
  46:  PR[82]=LPOS    ;
  47:  UTOOL[10]=PR[97] ;
  48:  UTOOL_NUM=10 ;
  49:J P[4] 11% FINE    ;
  50:  UTOOL_NUM=2 ;
  51:  PR[81]=LPOS    ;
  52:  UFRAME_NUM=3 ;
  53:J P[5] 11% FINE    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =  1050.000  mm,	Y =    80.000  mm,	Z =   780.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   950.000  mm,	Y =   -60.000  mm,	Z =   820.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -160.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 10,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =  -160.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 10,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =     0.000  mm,	Z =   700.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[5]{
   GP1:
	UF : 3, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
