/PROG  BFCONV
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "BfConv";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 25;
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
   3:  !RAPID BranchFrameProbe.BfConv ;
   4:  R[1:bfDone]=0    ;
   5:  CALL BFTURN(1,30) ;
   6:  UFRAME_NUM=1 ;
   7:  UTOOL_NUM=1 ;
   8:L P[1] 500mm/sec FINE    ;
   9:  UFRAME_NUM=0 ;
  10:  PR[99]=LPOS    ;
  11:  UFRAME_NUM=2 ;
  12:L P[2] 500mm/sec FINE    ;
  13:  UFRAME_NUM=0 ;
  14:  PR[98]=LPOS    ;
  15:  CALL BFTURN(2,135) ;
  16:  UFRAME_NUM=1 ;
  17:  UTOOL_NUM=1 ;
  18:L P[1] 500mm/sec FINE    ;
  19:  UFRAME_NUM=0 ;
  20:  PR[97]=LPOS    ;
  21:  UFRAME_NUM=2 ;
  22:L P[2] 500mm/sec FINE    ;
  23:  UFRAME_NUM=0 ;
  24:  PR[96]=LPOS    ;
  25:  R[1:bfDone]=1    ;
/POS
P[1]{
   GP1:
	UF : 1, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =    80.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
P[2]{
   GP1:
	UF : 2, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =    40.000  mm,	Y =    30.000  mm,	Z =    80.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =   180.000 deg
};
/END
