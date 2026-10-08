/PROG  KPCONV
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "KpConv";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 43;
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
   3:  !RAPID KarelPoseProbe.KpConv ;
   4:  R[1:kpDone]=0    ;
   5:  UFRAME_NUM=0 ;
   6:  UTOOL_NUM=1 ;
   7:J P[1] 11% FINE    ;
   8:  PR[99]=LPOS    ;
   9:L P[2] 500mm/sec FINE    ;
  10:  PR[98]=LPOS    ;
  11:L P[3] 500mm/sec FINE    ;
  12:  PR[97]=LPOS    ;
  13:  !l.27 kpWobj.uframe:=DefFrame(kpM ;
  14:  CALL CA_DEFFRAME(99,98,97,96,3) ;
  15:  UFRAME[1]=PR[96] ;
  16:  UFRAME_NUM=1 ;
  17:  UTOOL_NUM=1 ;
  18:L P[4] 500mm/sec FINE    ;
  19:  UFRAME_NUM=0 ;
  20:  PR[95]=LPOS    ;
  21:  CALL CA_RELTOOL(98,94,0,0,(-30),0,0,(-90)) ;
  22:  UFRAME_NUM=0 ;
  23:  UTOOL_NUM=1 ;
  24:L PR[94] 500mm/sec FINE    ;
  25:  PR[93]=LPOS    ;
  26:  R[2:Calc1]=PR[99,2]-(-100)    ;
  27:  PR[92,1]=PR[99,1]-900    ;
  28:  PR[92,2]=R[2:Calc1]+5    ;
  29:  PR[92,3]=0    ;
  30:  PR[92,4]=0    ;
  31:  PR[92,5]=0    ;
  32:  PR[92,6]=0    ;
  33:  !l.34 kpTool.tframe:=PoseMult(kpT ;
  34:  PR[91]=UTOOL[2] ;
  35:  CALL CA_POSEINV(92,90) ;
  36:  CALL CA_POSEMULT(91,90,96) ;
  37:  UTOOL[2]=PR[96] ;
  38:  UFRAME_NUM=0 ;
  39:  UTOOL_NUM=2 ;
  40:L P[5] 500mm/sec FINE    ;
  41:  UTOOL_NUM=1 ;
  42:  PR[89]=LPOS    ;
  43:  R[1:kpDone]=1    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   900.000  mm,	Y =  -100.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =    50.000  mm,	Z =   820.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   950.000  mm,	Y =   150.000  mm,	Z =   780.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[4]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   100.000  mm,	Y =    50.000  mm,	Z =   -50.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =   900.000  mm,	Y =  -100.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
