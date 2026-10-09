/PROG  FRCONV
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "FrConv";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 51;
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
   3:  !RAPID FuncResultProbe.FrConv ;
   4:  R[1:frDone]=0    ;
   5:  UFRAME_NUM=0 ;
   6:  UTOOL_NUM=1 ;
   7:J P[1] 11% FINE    ;
   8:  PR[99]=LPOS    ;
   9:L P[2] 500mm/sec FINE    ;
  10:  PR[98]=LPOS    ;
  11:  CALL XFRGAP(99,98,2) ;
  12:  R[3:frGap]=R[2:result]    ;
  13:  CALL XFRMID(99,98,97) ;
  14:  PR[96]=PR[97]    ;
  15:  UFRAME_NUM=0 ;
  16:  UTOOL_NUM=1 ;
  17:L PR[96] 500mm/sec FINE    ;
  18:  PR[95]=LPOS    ;
  19:  !l.29 frHub.uframe.trans:=frMid.t ;
  20:  PR[94]=UFRAME[1] ;
  21:  PR[94,1]=PR[96,1]    ;
  22:  PR[94,2]=PR[96,2]    ;
  23:  PR[94,3]=PR[96,3]    ;
  24:  UFRAME[1]=PR[94] ;
  25:  UFRAME_NUM=1 ;
  26:L P[3] 500mm/sec FINE    ;
  27:  UFRAME_NUM=0 ;
  28:  PR[93]=LPOS    ;
  29:  PR[91]=P[1]    ;
  30:  PR[90]=P[2]    ;
  31:  CALL XFRFIT(91,90,R[3:frGap],92) ;
  32:  !l.32 frRing.uframe:=FrFit(frA,fr ;
  33:  UFRAME[2]=PR[92] ;
  34:  UFRAME_NUM=2 ;
  35:  UTOOL_NUM=1 ;
  36:L P[4] 500mm/sec FINE    ;
  37:  UFRAME_NUM=0 ;
  38:  PR[89]=LPOS    ;
  39:  CALL XFROFS(2,88) ;
  40:  !l.35 frProbe.tframe.trans:=FrOff ;
  41:  PR[94]=UTOOL[2] ;
  42:  PR[94,1]=PR[88,1]    ;
  43:  PR[94,2]=PR[88,2]    ;
  44:  PR[94,3]=PR[88,3]    ;
  45:  UTOOL[2]=PR[94] ;
  46:  UFRAME_NUM=0 ;
  47:  UTOOL_NUM=2 ;
  48:L P[5] 500mm/sec FINE    ;
  49:  UTOOL_NUM=1 ;
  50:  PR[87]=LPOS    ;
  51:  R[1:frDone]=1    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1000.000  mm,	Y =   -40.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1060.000  mm,	Y =    40.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[3]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[4]{
   GP1:
	UF : 2, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =   -60.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 2,		CONFIG : 'N U T, 0, 0, 0',
	X =  1060.000  mm,	Y =    40.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
