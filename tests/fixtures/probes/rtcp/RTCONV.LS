/PROG  RTCONV
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "RtConv";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 24;
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
   3:  !RAPID RtcpProbe.RtConv ;
   4:  R[1:rtDone]=0    ;
   5:  UFRAME_NUM=1 ;
   6:  UTOOL_NUM=1 ;
   7:L P[1] 20mm/sec FINE RTCP    ;
   8:  UFRAME_NUM=0 ;
   9:  UTOOL_NUM=2 ;
  10:  PR[98]=LPOS    ;
  11:  UFRAME_NUM=1 ;
  12:  UTOOL_NUM=1 ;
  13:C P[2]    
    :  P[3] 20mm/sec FINE RTCP    ;
  14:  UFRAME_NUM=0 ;
  15:  UTOOL_NUM=2 ;
  16:  PR[97]=LPOS    ;
  17:  UFRAME_NUM=1 ;
  18:  UTOOL_NUM=1 ;
  19:L P[4] 20mm/sec CNT100 RTCP    ;
  20:L P[5] 20mm/sec FINE RTCP    ;
  21:  UFRAME_NUM=0 ;
  22:  UTOOL_NUM=2 ;
  23:  PR[96]=LPOS    ;
  24:  R[1:rtDone]=1    ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   -62.831  mm,	Y =    -6.033  mm,	Z =     6.394  mm,
	W =  -169.096 deg,	P =    -5.041 deg,	R =  -155.481 deg
};
P[2]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   -38.524  mm,	Y =    54.641  mm,	Z =    11.870  mm,
	W =   180.000 deg,	P =   -10.000 deg,	R =   180.000 deg
};
P[3]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    18.688  mm,	Y =    51.346  mm,	Z =     5.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   160.000 deg
};
P[4]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    30.872  mm,	Y =   -39.331  mm,	Z =     8.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   165.000 deg
};
P[5]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    30.872  mm,	Y =   -39.331  mm,	Z =     0.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   165.000 deg
};
/END
