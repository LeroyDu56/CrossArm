/PROG  SETUP_FRAMES
/ATTR
OWNER		= MNEDITOR;
COMMENT		= "CrossArm frames";
PROG_SIZE	= 0;
CREATE		= DATE 26-01-01  TIME 00:00:00;
MODIFIED	= DATE 26-01-01  TIME 00:00:00;
FILE_NAME	= ;
VERSION		= 0;
LINE_COUNT	= 26;
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
   3:  !CrossArm: tool and user frames ;
   4:  !of the ABB backup ;
   5:  !PR[100] is overwritten ;
   6:  MESSAGE[Overwrites UTOOL/UFRAME] ;
   7:  PAUSE ;
   8:  !UTOOL[1] tool0 ;
   9:  PR[100]=P[1]    ;
  10:  UTOOL[1]=PR[100] ;
  11:  !UTOOL[2] tSuction ;
  12:  PR[100]=P[2]    ;
  13:  UTOOL[2]=PR[100] ;
  14:  !UTOOL[3] tGripper ;
  15:  PR[100]=P[3]    ;
  16:  UTOOL[3]=PR[100] ;
  17:  !UFRAME[1] wobjStack ;
  18:  PR[100]=P[4]    ;
  19:  UFRAME[1]=PR[100] ;
  20:  !UFRAME[2] wobjFixture ;
  21:  PR[100]=P[5]    ;
  22:  UFRAME[2]=PR[100] ;
  23:  !nOffsets: R[198] to R[200] ;
  24:  R[198]=0    ;
  25:  R[199]=120    ;
  26:  R[200]=240    ;
/POS
P[1]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[2]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   120.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[3]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =     0.000  mm,	Y =     0.000  mm,	Z =   185.500  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[4]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =   800.000  mm,	Y =  -200.000  mm,	Z =     0.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =     0.000 deg
};
P[5]{
   GP1:
	UF : 0, UT : 1,		CONFIG : 'N U T, 0, 0, 0',
	X =  1250.000  mm,	Y =  -400.000  mm,	Z =   720.000  mm,
	W =     0.000 deg,	P =     0.000 deg,	R =    90.000 deg
};
/END
