/PROG  SPDMOVES
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "SpdMoves";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 21;
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
   1:  !RAPID SpeedArgProbe.SpdMoves ;
   2:  R[1:v.tcp]=AR[1]    ;
   3:  R[2:v.joint]=AR[2]    ;
   4:  R[3:z.cnt]=AR[3]    ;
   5:  R[4:z.cnt2]=AR[4]    ;
   6:  UFRAME_NUM=0 ;
   7:  UTOOL_NUM=1 ;
   8:  IF R[3:z.cnt]>100,JMP LBL[1] ;
   9:J P[1] R[2]% CNT R[3]    ;
  10:  JMP LBL[2] ;
  11:  LBL[1] ;
  12:J P[1] R[2]% FINE    ;
  13:  LBL[2] ;
  14:  IF R[4:z.cnt2]>100,JMP LBL[3] ;
  15:L P[2] R[1]mm/sec CNT R[4]    ;
  16:  JMP LBL[4] ;
  17:  LBL[3] ;
  18:L P[2] R[1]mm/sec FINE    ;
  19:  LBL[4] ;
  20:L P[3] R[1]mm/sec FINE    ;
  21:  R[5:nCalls]=R[5:nCalls]+1    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =    50.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =   250.000  mm,	Z =  1000.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1100.000  mm,	Y =   250.000  mm,	Z =   800.000  mm,
	W =   180.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
/END
